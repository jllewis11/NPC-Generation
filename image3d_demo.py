import os

import gradio as gr
from PIL import Image
import requests

from app.backend_client import backend_url_from_env, image_generate, image_to_3d, image_upload


def _default_backend_url() -> str:
    return os.getenv("NPC_BACKEND_URL") or backend_url_from_env() or ""


def _gen(prompt: str, backend_url: str, reference_image, reference_image_url: str):
    if not backend_url:
        raise gr.Error("Backend URL is empty. Set NPC_BACKEND_URL or paste your Modal URL.")
    if not prompt or not prompt.strip():
        raise gr.Error("Prompt is required.")

    reference_images: list[str] = []
    if isinstance(reference_image_url, str) and reference_image_url.strip():
        reference_images.append(reference_image_url.strip())

    if reference_image is not None:
        try:
            import io

            buf = io.BytesIO()
            if isinstance(reference_image, Image.Image):
                img = reference_image
            else:
                img = Image.fromarray(reference_image)
            img = img.convert("RGBA")
            img.save(buf, format="PNG")
            uploaded = image_upload(base_url=backend_url, image_bytes=buf.getvalue(), filename="reference.png")
            u = str(uploaded.get("image_url", "") or "").strip()
            if u:
                if ("127.0.0.1" in u) or ("localhost" in u):
                    raise gr.Error(
                        "Reference image upload returned a LOCAL URL, which Together cannot access. "
                        "Use a publicly reachable backend (Modal) or paste a public Reference image URL instead. "
                        f"Got: {u}"
                    )
                reference_images.append(u)
        except Exception as e:
            raise gr.Error(f"Failed to upload reference image: {e}")

    result = image_generate(base_url=backend_url, prompt=prompt.strip(), reference_images=reference_images or None)
    profile_url = result.get("profile_image_url", "")
    full_url = result.get("full_body_image_url", "")

    def _load(url: str) -> Image.Image | None:
        if not url:
            return None
        u = url if url.startswith("http") else backend_url.rstrip("/") + url
        r = requests.get(u, timeout=60)
        r.raise_for_status()
        return Image.open(io.BytesIO(r.content)).convert("RGBA")

    import io

    return (
        _load(profile_url),
        _load(full_url),
        profile_url,
        full_url,
        result.get("profile_asset_id", ""),
        result.get("full_body_asset_id", ""),
    )


def _to3d(which: str, profile_id: str, full_id: str, backend_url: str):
    if not backend_url:
        raise gr.Error("Backend URL is empty. Set NPC_BACKEND_URL or paste your Modal URL.")
    asset_id = profile_id if which == "Profile" else full_id
    if not asset_id:
        raise gr.Error("No asset_id available. Generate images first.")
    result = image_to_3d(base_url=backend_url, asset_id=asset_id)
    return result.get("glb_url", ""), result.get("glb_download_url", "")


def build_demo() -> gr.Blocks:
    with gr.Blocks(title="FLUX.2-pro → TRELLIS.2 (Image → 3D)") as demo:
        gr.Markdown("# FLUX.2-pro → TRELLIS.2 (Image → 3D)\n\nGenerate a profile + full-body image, then convert one into a GLB 3D asset.")

        backend_url = gr.Textbox(
            label="Backend URL",
            value=_default_backend_url(),
            placeholder="https://<your-app>.modal.run",
        )

        prompt = gr.Textbox(
            label="Prompt",
            placeholder="Describe your character (style, clothing, setting, etc.)",
            lines=4,
        )

        with gr.Row():
            reference_image = gr.Image(label="Reference image (optional)", type="pil")
            reference_image_url = gr.Textbox(
                label="Reference image URL (optional)",
                placeholder="https://... (publicly accessible image URL)",
            )

        with gr.Row():
            gen_btn = gr.Button("Generate profile + full body", variant="primary")
            status = gr.Textbox(label="Status", value="", interactive=False)

        with gr.Row():
            profile_img = gr.Image(label="Profile")
            full_img = gr.Image(label="Full body")

        profile_url = gr.Textbox(label="Profile image URL", interactive=False)
        full_url = gr.Textbox(label="Full body image URL", interactive=False)

        profile_id = gr.Textbox(label="Profile asset_id", interactive=False)
        full_id = gr.Textbox(label="Full body asset_id", interactive=False)

        gen_btn.click(
            fn=_gen,
            inputs=[prompt, backend_url, reference_image, reference_image_url],
            outputs=[profile_img, full_img, profile_url, full_url, profile_id, full_id],
        )

        gr.Markdown("## Convert to 3D (GLB)")
        which = gr.Radio(choices=["Profile", "Full body"], value="Profile", label="Which image to convert?")
        convert_btn = gr.Button("Convert selected image to GLB (GPU)", variant="primary")
        with gr.Row():
            glb_view = gr.Model3D(label="GLB preview (URL)")
            glb_download = gr.Textbox(label="GLB download URL", interactive=False)

        convert_btn.click(
            fn=_to3d,
            inputs=[which, profile_id, full_id, backend_url],
            outputs=[glb_view, glb_download],
        )

    return demo


if __name__ == "__main__":
    build_demo().launch()


