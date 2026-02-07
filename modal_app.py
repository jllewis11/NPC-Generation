"""
Modal deployment configuration for NPC Dialogue Generation API (Backend Only).

This deploys ONLY the FastAPI backend (app/api.py).
The Gradio interface (main.py and app/npcchat.py) remains local and is NOT deployed.
"""
import modal
from pathlib import Path

# Create a Modal image with backend dependencies only (no Gradio)
image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("sqlite3", "libsqlite3-dev")  # Install SQLite3 for ChromaDB
    .pip_install(
        "pysqlite3-binary",  # Bundles newer SQLite3 for ChromaDB compatibility
        "fastapi==0.104.1",
        "uvicorn[standard]==0.24.0",
        "python-dotenv==1.0.0",
        "chromadb>=0.5.0",  # Use latest version for v2 API support
        "requests",  # For direct HTTP calls to Together AI API
        "pydantic==2.5.0",
        "Pillow",
        # Note: Gradio is NOT included - only backend is deployed
    )
    .add_local_file("app/api.py", "/app/api.py")
    .add_local_file("app/__init__.py", "/app/__init__.py")  # Only copy backend files, not Gradio
    # Copy JSONData so the backend can list/select environments & characters on Modal.
    .add_local_dir("JSONData", "/JSONData")
)

# Create a Modal app
app = modal.App("npc-dialogue-api", image=image)

ASSETS_DIR = "/assets"
assets_volume = modal.Volume.from_name("npc-assets", create_if_missing=True)

# Persist model caches across cold starts (Hugging Face / torch, etc.)
# This makes TRELLIS behave more like a "hosted" model (downloads happen once).
TRELLIS_CACHE_DIR = "/root/.cache"
trellis_cache_volume = modal.Volume.from_name("trellis-cache", create_if_missing=True)

# TRELLIS.2 runs on GPU. We keep this separate from the FastAPI image so only the
# specific route that calls it uses a GPU container.
#
# NOTE: To match the HF Space behavior, TRELLIS.2 typically requires CUDA
# extensions (NVCC) and a heavier build. This image is intentionally separate.
trellis_image = (
    modal.Image.from_registry(
        # CUDA devel image provides NVCC for compiling extensions
        "nvidia/cuda:12.4.1-devel-ubuntu22.04",
        add_python="3.10",
    )
    .apt_install(
        "git",
        "ffmpeg",
        "libgl1",
        "libglib2.0-0",
        "build-essential",
        "cmake",
        "ninja-build",
    )
    .pip_install(
        # Torch/cu124 matches TRELLIS upstream setup guidance; Modal runtime provides GPUs.
        "torch==2.6.0",
        "torchvision==0.21.0",
        "numpy<2",
        "pillow",
        "opencv-python-headless",
        "imageio",
        "imageio-ffmpeg",
        "trimesh",
        "tqdm",
        "easydict",
        "transformers",
        "safetensors",
        # Some TRELLIS utilities
        "kornia",
        "timm",
        "lpips",
        "pandas",
        "tensorboard",
        "zstandard",
    )
    .run_commands(
        # Install TRELLIS.2 from source so we can compile CUDA extensions.
        "cd /root && rm -rf TRELLIS.2 && git clone --recursive https://github.com/microsoft/TRELLIS.2.git",
        # Install any additional python deps if the repo provides requirements.txt (repo is not a pip package).
        "cd /root/TRELLIS.2 && (test -f requirements.txt && pip install -r requirements.txt || true)",
        # IMPORTANT: Do NOT run `setup.sh` during the Modal image build.
        # The builder environment is CPU-only (no /dev/nvidia*), so TRELLIS's setup script
        # fails with: "Error: No supported GPU found".
        # We compile extensions at *runtime* inside the GPU container instead.
        "echo 'Skipping TRELLIS setup.sh at image build time; will compile at GPU runtime.'",
    )
)


@app.function(
    image=trellis_image,
    gpu="A100",
    timeout=60 * 20,  # TRELLIS + export can be slow on cold start
    volumes={TRELLIS_CACHE_DIR: trellis_cache_volume},
)
def trellis_image_to_glb(image_bytes: bytes) -> bytes:
    """
    Converts an input image (PNG/JPEG bytes) into a GLB (gltf-binary) blob.

    This function runs on GPU. FastAPI routes should call it via `.remote(...)`.
    """
    import os

    # Point HF/torch caches at the persisted Volume so downloads survive cold starts.
    os.environ.setdefault("HF_HOME", TRELLIS_CACHE_DIR + "/huggingface")
    os.environ.setdefault("HUGGINGFACE_HUB_CACHE", TRELLIS_CACHE_DIR + "/huggingface/hub")
    os.environ.setdefault("TRANSFORMERS_CACHE", TRELLIS_CACHE_DIR + "/huggingface/hub")
    os.environ.setdefault("TORCH_HOME", TRELLIS_CACHE_DIR + "/torch")

    os.environ["OPENCV_IO_ENABLE_OPENEXR"] = "1"
    os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"

    from io import BytesIO

    import torch
    from PIL import Image

    # Ensure TRELLIS native/CUDA extensions are built in the *GPU runtime* container.
    # Modal image builds are CPU-only, so doing this at build time fails.
    import subprocess
    from pathlib import Path as _Path

    marker = "/root/TRELLIS.2/.modal_setup_basic_done"
    if not os.path.exists(marker):
        print("[trellis] building extensions at runtime via `bash setup.sh --basic` (first run per container)")
        subprocess.check_call(["bash", "-lc", "cd /root/TRELLIS.2 && bash setup.sh --basic"])
        _Path(marker).write_text("ok")
        print("[trellis] setup complete")

    # Import TRELLIS pipeline
    import sys
    # Repo is cloned into the image at build time; it's not a pip-installable package.
    sys.path.insert(0, "/root/TRELLIS.2")
    from trellis2.pipelines import Trellis2ImageTo3DPipeline
    import o_voxel

    # Cache the pipeline in-process so the container behaves like a "hosted model":
    # after the first request in a warm container, subsequent requests reuse the model.
    global _TRELLIS_PIPELINE  # type: ignore[var-annotated]
    try:
        _TRELLIS_PIPELINE  # noqa: B018
    except NameError:
        _TRELLIS_PIPELINE = None

    if _TRELLIS_PIPELINE is None:
        pipeline = Trellis2ImageTo3DPipeline.from_pretrained("microsoft/TRELLIS.2-4B")
        pipeline.cuda()
        _TRELLIS_PIPELINE = pipeline
    else:
        pipeline = _TRELLIS_PIPELINE

    img = Image.open(BytesIO(image_bytes)).convert("RGBA")
    mesh = pipeline.run(img)[0]
    # Match upstream example: simplify to nvdiffrast limit
    mesh.simplify(16777216)

    glb = o_voxel.postprocess.to_glb(
        vertices=mesh.vertices,
        faces=mesh.faces,
        attr_volume=mesh.attrs,
        coords=mesh.coords,
        attr_layout=mesh.layout,
        voxel_size=mesh.voxel_size,
        aabb=[[-0.5, -0.5, -0.5], [0.5, 0.5, 0.5]],
        decimation_target=1000000,
        texture_size=4096,
        remesh=True,
        remesh_band=1,
        remesh_project=0,
        verbose=True,
    )

    # Export to bytes (robustly via temp file, since some exporters prefer filenames)
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        out_path = os.path.join(d, "out.glb")
        glb.export(out_path, extension_webp=True)
        with open(out_path, "rb") as f:
            return f.read()


@app.function(
    image=image,
    secrets=[
        modal.Secret.from_name("together-api-key"),  # Make sure to create this secret in Modal
        modal.Secret.from_name("chroma-cloud"),  # ChromaDB Cloud credentials
    ],
    timeout=300,  # 5 minute timeout for long-running requests
    volumes={ASSETS_DIR: assets_volume},
)
@modal.concurrent(max_inputs=100)  # Allow up to 100 concurrent requests per container
@modal.asgi_app()
def fastapi_app():
    """
    Deploy ONLY the FastAPI backend application as an ASGI app.
    
    This imports app.api (FastAPI backend) only.
    The Gradio interface (app.npcchat and main.py) is NOT deployed.
    """
    import os
    import sys
    
    # Add the app directory to Python path
    sys.path.insert(0, "/")
    
    # Ensure FastAPI knows where to store assets (shared Volume)
    os.environ.setdefault("NPC_ASSETS_DIR", ASSETS_DIR)
    os.environ.setdefault("MODAL_APP_NAME", "npc-dialogue-api")

    # Import and return ONLY the FastAPI backend (not Gradio)
    from app.api import app as fastapi_application
    return fastapi_application


@app.function(volumes={ASSETS_DIR: assets_volume})
def commit_assets_volume() -> None:
    """
    Best-effort Volume commit so assets written by the ASGI app become visible
    across containers (and persist) quickly.
    """
    assets_volume.commit()


@app.function(
    image=image,
    volumes={ASSETS_DIR: assets_volume},
    schedule=modal.Cron("*/1 * * * *"),  # every minute
    timeout=60,
)
def cleanup_temporary_uploads() -> dict:
    """
    Periodic cleanup for temporary uploads created by POST /image/upload.
    Deletes expired assets and commits the Volume.
    """
    import json
    import os
    import time
    from pathlib import Path

    assets_dir = Path(ASSETS_DIR)
    now = time.time()
    deleted = 0
    scanned = 0

    for meta_path in assets_dir.glob("*.tmp.json"):
        scanned += 1
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8") or "{}")
            expires_at = float(meta.get("expires_at", 0.0) or 0.0)
            asset_id = str(meta.get("asset_id", "") or meta_path.name.replace(".tmp.json", ""))
        except Exception:
            expires_at = 0.0
            asset_id = meta_path.name.replace(".tmp.json", "")

        if now < expires_at:
            continue

        # Delete the asset file(s) + marker.
        for ext in (".png", ".jpg", ".jpeg", ".webp", ".glb"):
            p = assets_dir / f"{asset_id}{ext}"
            try:
                if p.exists():
                    p.unlink()
            except Exception:
                pass
        try:
            if meta_path.exists():
                meta_path.unlink()
        except Exception:
            pass

        deleted += 1

    if deleted:
        assets_volume.commit()

    return {"ok": True, "scanned": scanned, "deleted": deleted}


@app.local_entrypoint()
def main():
    """
    Local entrypoint for testing.
    """
    print("Modal app configured. Deploy with: modal deploy modal_app.py")
    print("Or run locally with: modal run modal_app.py::fastapi_app")

