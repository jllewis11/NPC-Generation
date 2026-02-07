import os
import re
import subprocess
import threading
import atexit
from pathlib import Path
import time

from app.npcchat import npc_chat_router, shutdown, clear_history_router
from app.backend_client import (
    backend_url_from_env,
    image_generate as backend_image_generate,
    image_to_3d as backend_image_to_3d,
    image_upload as backend_image_upload,
    list_characters as backend_list_characters,
    list_environments as backend_list_environments,
    load_character as backend_load_character,
    save_character as backend_save_character,
    load_environment as backend_load_environment,
    save_environment as backend_save_environment,
)
import gradio as gr
import json


BACKEND_MODE_LOCAL = "Local FastAPI"
BACKEND_MODE_MODAL = "Modal (deployed)"

_MODAL_SERVE_PROCESS: subprocess.Popen[str] | None = None
_MODAL_SERVE_URL: str = ""
_MODAL_SERVE_LOCK = threading.Lock()

# #region agent log
def _dbg_log(hypothesis_id: str, location: str, message: str, data: dict | None = None, run_id: str = "run_modal_resolve_1") -> None:
    try:
        payload = {
            "sessionId": "debug-session",
            "runId": run_id,
            "hypothesisId": hypothesis_id,
            "location": location,
            "message": message,
            "data": data or {},
            "timestamp": int(time.time() * 1000),
        }
        log_path = os.getenv("NPC_DEBUG_LOG_PATH", str((Path(__file__).resolve().parent / ".cursor" / "debug.log").resolve()))
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        pass
# #endregion agent log


def _normalize_backend_mode(raw: str | None) -> str:
    """
    Gradio Radio `value` MUST be one of `choices`.

    We previously used other labels ("Remote (FastAPI / Modal)", "Local (in-process)"),
    so accept those to avoid crashing when users still have old env vars.
    """
    if not raw:
        return BACKEND_MODE_LOCAL
    value = raw.strip()
    normalized = value.lower()

    legacy_map = {
        "local (in-process)": BACKEND_MODE_LOCAL,
        "local": BACKEND_MODE_LOCAL,
        "remote (fastapi / modal)": BACKEND_MODE_MODAL,
        "remote": BACKEND_MODE_MODAL,
        "modal": BACKEND_MODE_MODAL,
        "modal (deployed)": BACKEND_MODE_MODAL,
        "local fastapi": BACKEND_MODE_LOCAL,
    }

    if normalized in legacy_map:
        return legacy_map[normalized]
    if value in {BACKEND_MODE_LOCAL, BACKEND_MODE_MODAL}:
        return value
    return BACKEND_MODE_LOCAL


def _project_root() -> Path:
    return Path(__file__).resolve().parent


def _modal_serve_is_running() -> bool:
    global _MODAL_SERVE_PROCESS
    p = _MODAL_SERVE_PROCESS
    return p is not None and p.poll() is None


def _get_modal_serve_url() -> str:
    with _MODAL_SERVE_LOCK:
        return _MODAL_SERVE_URL


def _set_modal_serve_url(url: str) -> None:
    global _MODAL_SERVE_URL
    with _MODAL_SERVE_LOCK:
        _MODAL_SERVE_URL = url


def start_modal_serve_in_background() -> str:
    """
    Start `modal serve modal_app.py` as a background subprocess.

    This is meant for local dev: it will run as long as this Python process runs.
    The Modal CLI prints a `-dev.modal.run` URL; we best-effort parse and expose it.

    Controlled via env vars:
    - NPC_START_MODAL_SERVE=1 to auto-start on `python main.py`
    - NPC_MODAL_APP_REF=modal_app.py (default)
    - NPC_MODAL_SERVE_TIMEOUT=<float seconds> (optional)
    - NPC_MODAL_ENVIRONMENT=<name> (optional; maps to `modal serve -e`)
    """
    global _MODAL_SERVE_PROCESS

    if _modal_serve_is_running():
        return "Modal dev server already running."

    app_ref = (os.getenv("NPC_MODAL_APP_REF") or "modal_app.py").strip()
    timeout = (os.getenv("NPC_MODAL_SERVE_TIMEOUT") or "").strip()
    modal_env = (os.getenv("NPC_MODAL_ENVIRONMENT") or os.getenv("MODAL_ENVIRONMENT") or "").strip()

    cmd: list[str] = ["modal", "serve", app_ref]
    if timeout:
        cmd.extend(["--timeout", timeout])
    if modal_env:
        cmd.extend(["-e", modal_env])

    log_path = _project_root() / ".cursor" / "modal_serve.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        p = subprocess.Popen(
            cmd,
            cwd=str(_project_root()),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        _MODAL_SERVE_PROCESS = p
        _dbg_log("H3", "main.py:start_modal_serve_in_background", "started modal serve subprocess", data={"cmd": cmd, "cwd": str(_project_root())})
    except FileNotFoundError:
        _MODAL_SERVE_PROCESS = None
        _dbg_log("H3", "main.py:start_modal_serve_in_background", "modal cli not found", data={"cmd": cmd})
        return "Failed to start Modal dev server: `modal` CLI not found on PATH."
    except Exception as e:
        _MODAL_SERVE_PROCESS = None
        _dbg_log("H3", "main.py:start_modal_serve_in_background", "failed to start modal serve", data={"error": str(e)[:400], "cmd": cmd})
        return f"Failed to start Modal dev server: {e}"

    url_regex = re.compile(r"(https?://[^\s]+modal\.run[^\s]*)")

    def _pump() -> None:
        nonlocal p
        try:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"\n--- modal serve started: {' '.join(cmd)} ---\n")
                if p.stdout is None:
                    return
                for line in p.stdout:
                    f.write(line)
                    m = url_regex.search(line)
                    if m:
                        url = m.group(1).strip()
                        _set_modal_serve_url(url)
                        _dbg_log("H4", "main.py:start_modal_serve_in_background:_pump", "detected modal serve url", data={"url": url[:220]})
        except Exception:
            return

    t = threading.Thread(target=_pump, daemon=True)
    t.start()
    return f"Started Modal dev server. Logs: {log_path}"


def stop_modal_serve() -> str:
    global _MODAL_SERVE_PROCESS
    p = _MODAL_SERVE_PROCESS
    if p is None or p.poll() is not None:
        _MODAL_SERVE_PROCESS = None
        return "Modal dev server is not running."
    try:
        p.terminate()
    except Exception:
        pass
    _MODAL_SERVE_PROCESS = None
    return "Stopped Modal dev server."


def _local_backend_url_from_env() -> str:
    host = os.getenv("NPC_BACKEND_HOST", "127.0.0.1")
    port = os.getenv("NPC_BACKEND_PORT", "8000")
    return f"http://{host}:{port}"


def _resolve_base_url(backend_mode: str, backend_url: str) -> str:
    """
    Gradio always calls FastAPI over HTTP.

    - Local FastAPI: uses NPC_BACKEND_HOST/PORT
    - Modal deployment: uses the provided URL textbox or NPC_BACKEND_URL env
    """
    mode = (backend_mode or "").strip().lower()
    if mode.startswith("local"):
        chosen = _local_backend_url_from_env()
        _dbg_log(
            "H1",
            "main.py:_resolve_base_url",
            "resolved base_url (local mode)",
            data={
                "backend_mode": backend_mode,
                "backend_url_textbox": (backend_url or "")[:200],
                "chosen": chosen,
                "env_NPC_BACKEND_URL": (os.getenv("NPC_BACKEND_URL") or "")[:200],
                "detected_modal_serve_url": _get_modal_serve_url()[:200],
            },
        )
        return chosen

    # If we're in Modal mode but the textbox/env still points at localhost, prefer the
    # detected `modal serve` dev URL (if available). This makes local dev "just work"
    # without requiring users to click the "Use detected Modal dev URL" button.
    detected = _get_modal_serve_url().strip()
    raw = ((backend_url or "").strip() or backend_url_from_env()).strip()
    is_localhost = ("127.0.0.1" in raw) or ("localhost" in raw)
    if detected and is_localhost:
        chosen = detected
        _dbg_log(
            "H2",
            "main.py:_resolve_base_url",
            "overriding localhost base_url with detected modal serve url",
            data={
                "backend_mode": backend_mode,
                "backend_url_textbox": (backend_url or "")[:200],
                "raw": raw[:200],
                "chosen": chosen[:200],
                "detected_modal_serve_url": detected[:200],
            },
        )
        return chosen

    chosen = raw
    _dbg_log(
        "H2",
        "main.py:_resolve_base_url",
        "resolved base_url (modal/remote mode)",
        data={
            "backend_mode": backend_mode,
            "backend_url_textbox": (backend_url or "")[:200],
            "chosen": chosen,
            "env_NPC_BACKEND_URL": (os.getenv("NPC_BACKEND_URL") or "")[:200],
            "detected_modal_serve_url": _get_modal_serve_url()[:200],
        },
    )
    return chosen


def _load_image_from_backend_url(image_url: str, base_url: str):
    if not image_url:
        return None
    import io

    import requests
    from PIL import Image

    u = image_url if image_url.startswith("http") else base_url.rstrip("/") + image_url
    r = requests.get(u, timeout=60)
    r.raise_for_status()
    return Image.open(io.BytesIO(r.content)).convert("RGBA")


def image_generate_router(
    prompt: str,
    backend_mode: str,
    backend_url: str,
    profile_width: int,
    profile_height: int,
    full_width: int,
    full_height: int,
    reference_image,
    reference_image_url: str,
):
    base_url = _resolve_base_url(backend_mode=backend_mode, backend_url=backend_url)
    _dbg_log(
        "H5",
        "main.py:image_generate_router",
        "entered image_generate_router",
        data={
            "backend_mode": backend_mode,
            "base_url": base_url[:200],
            "backend_url_textbox": (backend_url or "")[:200],
            "has_reference_upload": reference_image is not None,
            "has_reference_url": bool((reference_image_url or "").strip()),
        },
    )
    if not base_url:
        raise gr.Error("Backend URL is empty. Paste your Modal `.modal.run` URL (or set NPC_BACKEND_URL).")
    if not prompt or not prompt.strip():
        raise gr.Error("Prompt is required.")

    reference_images: list[str] = []
    if isinstance(reference_image_url, str) and reference_image_url.strip():
        reference_images.append(reference_image_url.strip())

    # If a local reference image is provided, upload it first so Together can access it by URL.
    if reference_image is not None:
        try:
            from io import BytesIO
            from PIL import Image

            if isinstance(reference_image, Image.Image):
                img = reference_image
            else:
                # Some Gradio versions can provide numpy arrays; try converting.
                img = Image.fromarray(reference_image)
            img = img.convert("RGBA")
            buf = BytesIO()
            img.save(buf, format="PNG")
            uploaded = backend_image_upload(base_url=base_url, image_bytes=buf.getvalue(), filename="reference.png")
            uploaded_url = str(uploaded.get("image_url", "") or "").strip()
            _dbg_log("H6", "main.py:image_generate_router", "uploaded reference image", data={"uploaded_url": uploaded_url[:220], "base_url": base_url[:200]})
            if uploaded_url:
                # Together must be able to fetch the image URL (localhost URLs will fail).
                if ("127.0.0.1" in uploaded_url) or ("localhost" in uploaded_url):
                    _dbg_log("H7", "main.py:image_generate_router", "rejecting localhost upload url", data={"uploaded_url": uploaded_url[:220]})
                    raise gr.Error(
                        "Your reference image was uploaded to a LOCAL URL, which Together cannot access. "
                        "To use uploaded reference images, either:\n"
                        "- Switch Backend to 'Modal (deployed)' and use a Modal URL, or\n"
                        "- Set NPC_PUBLIC_BASE_URL to a publicly reachable base URL (e.g. an ngrok tunnel), or\n"
                        "- Paste a publicly reachable 'Reference image URL' instead of uploading.\n"
                        f"Got: {uploaded_url}"
                    )
                reference_images.append(uploaded_url)
        except Exception as e:
            _dbg_log("H8", "main.py:image_generate_router", "reference image upload failed", data={"error": str(e)[:400]})
            raise gr.Error(f"Failed to upload reference image: {e}")

    result = backend_image_generate(
        base_url=base_url,
        prompt=prompt.strip(),
        profile_width=int(profile_width),
        profile_height=int(profile_height),
        full_width=int(full_width),
        full_height=int(full_height),
        reference_images=reference_images or None,
    )
    profile_url = str(result.get("profile_image_url", "") or "")
    full_url = str(result.get("full_body_image_url", "") or "")

    profile_img = _load_image_from_backend_url(profile_url, base_url=base_url)
    full_img = _load_image_from_backend_url(full_url, base_url=base_url)

    return (
        profile_img,
        full_img,
        profile_url,
        full_url,
        str(result.get("profile_asset_id", "") or ""),
        str(result.get("full_body_asset_id", "") or ""),
        "Generated images successfully.",
    )


def image_to_3d_router(which: str, profile_id: str, full_id: str, backend_mode: str, backend_url: str):
    base_url = _resolve_base_url(backend_mode=backend_mode, backend_url=backend_url)
    if not base_url:
        raise gr.Error("Backend URL is empty. Paste your Modal `.modal.run` URL (or set NPC_BACKEND_URL).")

    asset_id = (profile_id or "").strip() if which == "Profile" else (full_id or "").strip()
    if not asset_id:
        raise gr.Error("No asset_id available. Generate images first.")

    result = backend_image_to_3d(base_url=base_url, asset_id=asset_id)
    return (
        str(result.get("glb_url", "") or ""),
        str(result.get("glb_download_url", "") or ""),
        "Generated GLB successfully.",
    )


def _parse_csv_list(s: str) -> list[str]:
    items: list[str] = []
    for part in (s or "").split(","):
        p = part.strip()
        if p:
            items.append(p)
    return items


def _build_character_json(
    name: str,
    age: int,
    gender: str,
    personalities_csv: str,
    appearance_description: str,
    appearance_height: str,
    appearance_weight: str,
    appearance_hair: str,
    appearance_eyes: str,
    background_hometown: str,
    background_family: str,
    background_motivation: str,
    skills_csv: str,
    secrets_csv: str,
) -> str:
    obj = {
        "name": (name or "").strip(),
        "age": int(age) if age is not None else 0,
        "gender": (gender or "").strip(),
        "personalities": _parse_csv_list(personalities_csv),
        "appearance": {
            "description": (appearance_description or "").strip(),
            "height": (appearance_height or "").strip(),
            "weight": (appearance_weight or "").strip(),
            "hair": (appearance_hair or "").strip(),
            "eyes": (appearance_eyes or "").strip(),
        },
        "background": {
            "hometown": (background_hometown or "").strip(),
            "family": (background_family or "").strip(),
            "motivation": (background_motivation or "").strip(),
        },
        "skills": _parse_csv_list(skills_csv),
        "secrets": _parse_csv_list(secrets_csv),
    }
    return json.dumps(obj, indent=2, ensure_ascii=False) + "\n"


def _build_environment_json(
    era: str,
    time_period: str,
    detail_environment: str,
    detail_social_econ: str,
    detail_livelihood: str,
    detail_social_hierarchy: str,
    detail_cultural_norms: str,
    detail_natural_environment: str,
    detail_political_climate: str,
    guard_ai_safety: str,
    guard_undesirable_topics: str,
    guard_harmful_content: str,
    guard_sensitive_info: str,
    guard_inappropriate_content: str,
    guard_logical_consistency: str,
) -> str:
    obj = {
        "era": (era or "").strip(),
        "time_period": (time_period or "").strip(),
        "detail": {
            "Environment": (detail_environment or "").strip(),
            "Social and Economic Aspects": (detail_social_econ or "").strip(),
            "Livelihood": (detail_livelihood or "").strip(),
            "Social Hierarchy": (detail_social_hierarchy or "").strip(),
            "Cultural Norms": (detail_cultural_norms or "").strip(),
            "Natural Environment": (detail_natural_environment or "").strip(),
            "Political Climate": (detail_political_climate or "").strip(),
        },
        "guardrails": {
            "AI Safety": (guard_ai_safety or "").strip(),
            "Undesirable Topics": (guard_undesirable_topics or "").strip(),
            "Harmful Content": (guard_harmful_content or "").strip(),
            "Sensitive Information": (guard_sensitive_info or "").strip(),
            "Inappropriate Content": (guard_inappropriate_content or "").strip(),
            "Logical Consistency": (guard_logical_consistency or "").strip(),
        },
    }
    return json.dumps(obj, indent=2, ensure_ascii=False) + "\n"


def refresh_characters_router(backend_mode: str, backend_url: str):
    base_url = _resolve_base_url(backend_mode=backend_mode, backend_url=backend_url)
    if not base_url:
        raise gr.Error("Backend URL is empty.")
    data = backend_list_characters(base_url=base_url)
    files = list(data.get("files", []) or [])
    current = data.get("current", None)
    value = current if current in files else (files[0] if files else None)
    return gr.update(choices=files, value=value), f"Found {len(files)} character files."


def load_character_router(filename: str, backend_mode: str, backend_url: str):
    base_url = _resolve_base_url(backend_mode=backend_mode, backend_url=backend_url)
    if not base_url:
        raise gr.Error("Backend URL is empty.")
    if not filename:
        raise gr.Error("Select a character file to load.")
    data = backend_load_character(base_url=base_url, filename=filename)
    character = data.get("character", {})
    return json.dumps(character, indent=2, ensure_ascii=False) + "\n", f"Loaded character: {filename}"


def save_character_router(filename: str, character_json: str, backend_mode: str, backend_url: str):
    base_url = _resolve_base_url(backend_mode=backend_mode, backend_url=backend_url)
    if not base_url:
        raise gr.Error("Backend URL is empty.")
    fn = (filename or "").strip()
    if not fn:
        raise gr.Error("Filename is required (e.g. MyCharacter.json).")
    try:
        character_obj = json.loads(character_json or "{}")
    except Exception as e:
        raise gr.Error(f"Invalid JSON: {e}")
    backend_save_character(base_url=base_url, filename=fn, character=character_obj)
    saved_as = fn if fn.lower().endswith(".json") else fn + ".json"
    return f"Saved character to {saved_as}"


def refresh_environments_router(backend_mode: str, backend_url: str):
    base_url = _resolve_base_url(backend_mode=backend_mode, backend_url=backend_url)
    if not base_url:
        raise gr.Error("Backend URL is empty.")
    data = backend_list_environments(base_url=base_url)
    files = list(data.get("files", []) or [])
    current = data.get("current", None)
    value = current if current in files else (files[0] if files else None)
    return gr.update(choices=files, value=value), f"Found {len(files)} environment files."


def load_environment_router(filename: str, backend_mode: str, backend_url: str):
    base_url = _resolve_base_url(backend_mode=backend_mode, backend_url=backend_url)
    if not base_url:
        raise gr.Error("Backend URL is empty.")
    if not filename:
        raise gr.Error("Select an environment file to load.")
    data = backend_load_environment(base_url=base_url, filename=filename)
    env = data.get("environment", {})
    return json.dumps(env, indent=2, ensure_ascii=False) + "\n", f"Loaded environment: {filename}"


def save_environment_router(filename: str, environment_json: str, backend_mode: str, backend_url: str):
    base_url = _resolve_base_url(backend_mode=backend_mode, backend_url=backend_url)
    if not base_url:
        raise gr.Error("Backend URL is empty.")
    fn = (filename or "").strip()
    if not fn:
        raise gr.Error("Filename is required (e.g. MyEnvironment.json).")
    try:
        env_obj = json.loads(environment_json or "{}")
    except Exception as e:
        raise gr.Error(f"Invalid JSON: {e}")
    backend_save_environment(base_url=base_url, filename=fn, environment=env_obj)
    saved_as = fn if fn.lower().endswith(".json") else fn + ".json"
    return f"Saved environment to {saved_as}"


def _summarize_character_for_image_prompt(character: dict) -> str:
    if not isinstance(character, dict):
        return ""
    name = str(character.get("name", "") or "").strip()
    age = character.get("age", None)
    gender = str(character.get("gender", "") or "").strip()
    appearance = character.get("appearance", {}) if isinstance(character.get("appearance", {}), dict) else {}
    desc = str(appearance.get("description", "") or "").strip()
    hair = str(appearance.get("hair", "") or "").strip()
    eyes = str(appearance.get("eyes", "") or "").strip()
    height = str(appearance.get("height", "") or "").strip()
    skills = character.get("skills", [])
    skills_s = ""
    if isinstance(skills, list):
        skills_s = ", ".join([str(x).strip() for x in skills if str(x).strip()])[:240]

    parts: list[str] = []
    header_bits: list[str] = []
    if name:
        header_bits.append(name)
    if age is not None and str(age).strip():
        header_bits.append(f"{age} years old")
    if gender:
        header_bits.append(gender)
    if header_bits:
        parts.append("Character: " + ", ".join(header_bits) + ".")
    if desc:
        parts.append(f"Appearance: {desc}")
    if hair:
        parts.append(f"Hair: {hair}")
    if eyes:
        parts.append(f"Eyes: {eyes}")
    if height:
        parts.append(f"Height: {height}")
    if skills_s:
        parts.append(f"Skills vibe: {skills_s}")
    return " ".join([p for p in parts if p]).strip()


def _summarize_environment_for_image_prompt(env: dict) -> str:
    if not isinstance(env, dict):
        return ""
    era = str(env.get("era", "") or "").strip()
    time_period = str(env.get("time_period", "") or "").strip()
    detail = env.get("detail", {}) if isinstance(env.get("detail", {}), dict) else {}
    environment = str(detail.get("Environment", "") or "").strip()
    cultural = str(detail.get("Cultural Norms", "") or "").strip()

    parts: list[str] = []
    header_bits: list[str] = []
    if era:
        header_bits.append(era)
    if time_period:
        header_bits.append(time_period)
    if header_bits:
        parts.append("Setting: " + " — ".join(header_bits) + ".")
    if environment:
        parts.append(f"Environment: {environment}")
    if cultural:
        parts.append(f"Cultural norms: {cultural}")
    return " ".join([p for p in parts if p]).strip()


def build_image_prompt_router(
    character_file: str,
    environment_file: str,
    extra_details: str,
    backend_mode: str,
    backend_url: str,
):
    base_url = _resolve_base_url(backend_mode=backend_mode, backend_url=backend_url)
    if not base_url:
        raise gr.Error("Backend URL is empty.")

    parts: list[str] = []

    if character_file:
        char_data = backend_load_character(base_url=base_url, filename=character_file)
        character = char_data.get("character", {})
        char_summary = _summarize_character_for_image_prompt(character)
        if char_summary:
            parts.append(char_summary)

    if environment_file:
        env_data = backend_load_environment(base_url=base_url, filename=environment_file)
        env = env_data.get("environment", {})
        env_summary = _summarize_environment_for_image_prompt(env)
        if env_summary:
            parts.append(env_summary)

    extra = (extra_details or "").strip()
    if extra:
        parts.append(extra)

    final_prompt = "\n\n".join([p for p in parts if p]).strip()
    if not final_prompt:
        raise gr.Error("Nothing selected. Choose a character/environment and/or presets, or add Extra details.")
    return final_prompt, "Built prompt from selections."


# Create Gradio Interface
# demo = gr.Interface(fn=instruction,
#                     inputs=[
#                         "file",
#                         gr.Slider(1,
#                                   20,
#                                   value=1,
#                                   label="Count",
#                                   info="Choose between 1 and 20")
#                     ],
#                     outputs=["json"],
#                     title="JSON File Reader",
#                     description="Upload a JSON file and see its contents.")

# demo.launch(share=True)





# Create ChatInterface with clear history functionality
def build_demo() -> gr.Blocks:
    initial_backend_mode = _normalize_backend_mode(os.getenv("NPC_BACKEND_MODE"))
    with gr.Blocks(title="NPC Chat Interface") as demo:
        gr.Markdown("# NPC Studio\n\nChat with your NPC, generate character images (TogetherAI), and optionally convert an image to a 3D GLB (Modal GPU).")

        backend_mode = gr.Radio(
            choices=[BACKEND_MODE_LOCAL, BACKEND_MODE_MODAL],
            value=initial_backend_mode,
            label="Backend",
            info="Gradio always calls the FastAPI backend over HTTP (either local FastAPI or a deployed Modal URL).",
        )
        backend_url = gr.Textbox(
            label="Modal Backend URL (only for Modal mode)",
            value=os.getenv("NPC_BACKEND_URL") or os.getenv("MODAL_BACKEND_URL") or "",
            placeholder="https://<your-app>.modal.run",
        )

        # Local dev helper: start `modal serve` and grab the `-dev.modal.run` URL.
        with gr.Accordion("Local dev: Modal dev server (modal serve)", open=False):
            gr.Markdown(
                "This runs `modal serve` while this Python process is running, and tries to parse the emitted `-dev.modal.run` URL.\n\n"
                "Tip: set Backend to **Modal (deployed)** and click **Use detected Modal dev URL**."
            )
            with gr.Row():
                start_modal_btn = gr.Button("Start modal serve", variant="primary")
                stop_modal_btn = gr.Button("Stop modal serve", variant="stop")
            modal_status = gr.Textbox(label="Status", value="", interactive=False)
            detected_url = gr.Textbox(label="Detected Modal dev URL", value="", interactive=False)
            use_url_btn = gr.Button("Use detected Modal dev URL", variant="secondary")

            def _refresh_detected_url() -> str:
                return _get_modal_serve_url()

            start_modal_btn.click(fn=start_modal_serve_in_background, outputs=[modal_status])
            stop_modal_btn.click(fn=stop_modal_serve, outputs=[modal_status])
            use_url_btn.click(fn=_refresh_detected_url, outputs=[backend_url])
            demo.load(fn=_refresh_detected_url, outputs=[detected_url])

        with gr.Tabs():
            with gr.TabItem("Chat"):
                _chatbot = gr.ChatInterface(
                    fn=npc_chat_router,
                    title="NPC Conversation",
                    description="Have a conversation with the NPC character.",
                    additional_inputs=[backend_mode, backend_url],
                )

                with gr.Row():
                    clear_btn = gr.Button("🗑️ Clear Conversation History", variant="stop", size="sm")
                    status_output = gr.Textbox(
                        label="Status",
                        interactive=False,
                        visible=True,
                        value="",
                        container=True,
                    )

                clear_btn.click(
                    fn=clear_history_router,
                    inputs=[backend_mode, backend_url],
                    outputs=status_output,
                )

            with gr.TabItem("World Builder"):
                gr.Markdown("### Create / select Characters and Environments\n\nThese settings affect **Chat** by switching the backend's active character/environment.")

                with gr.Tabs():
                    with gr.TabItem("Characters"):
                        gr.Markdown("#### Select an existing character JSON")
                        with gr.Row():
                            character_file = gr.Dropdown(label="Character file", choices=[], value=None)
                            refresh_chars = gr.Button("Refresh list", variant="secondary")
                            load_char_btn = gr.Button("Load selected", variant="primary")
                        char_status = gr.Textbox(label="Status", value="", interactive=False)
                        loaded_char_json = gr.Code(label="Loaded character JSON (read-only view)", language="json", value="", interactive=False)

                        refresh_chars.click(
                            fn=refresh_characters_router,
                            inputs=[backend_mode, backend_url],
                            outputs=[character_file, char_status],
                        )
                        load_char_btn.click(
                            fn=load_character_router,
                            inputs=[character_file, backend_mode, backend_url],
                            outputs=[loaded_char_json, char_status],
                        )

                        gr.Markdown("#### Create a new character (based on `KaiyaStarling.json` keys)")
                        with gr.Row():
                            new_char_filename = gr.Textbox(label="Save as filename", placeholder="MyNewCharacter.json")
                            save_char_btn = gr.Button("Save character JSON", variant="primary")
                        save_char_status = gr.Textbox(label="Status", value="", interactive=False)

                        new_char_json = gr.Code(label="Character JSON to save (editable)", language="json", value="", interactive=True)

                        with gr.Row():
                            c_name = gr.Textbox(label="name")
                            c_age = gr.Number(label="age", value=30, precision=0)
                            c_gender = gr.Textbox(label="gender")
                        c_personalities = gr.Textbox(label="personalities (comma-separated)", placeholder="Adventurous, Inquisitive, ...")

                        gr.Markdown("**appearance**")
                        c_app_desc = gr.Textbox(label="appearance.description", lines=3)
                        with gr.Row():
                            c_app_height = gr.Textbox(label="appearance.height", placeholder="5'9")
                            c_app_weight = gr.Textbox(label="appearance.weight", placeholder="130 lbs")
                        with gr.Row():
                            c_app_hair = gr.Textbox(label="appearance.hair")
                            c_app_eyes = gr.Textbox(label="appearance.eyes")

                        gr.Markdown("**background**")
                        c_bg_hometown = gr.Textbox(label="background.hometown")
                        c_bg_family = gr.Textbox(label="background.family", lines=2)
                        c_bg_motivation = gr.Textbox(label="background.motivation", lines=2)

                        c_skills = gr.Textbox(label="skills (comma-separated)")
                        c_secrets = gr.Textbox(label="secrets (comma-separated)")

                        build_char_btn = gr.Button("Build JSON from fields →", variant="secondary")
                        build_char_btn.click(
                            fn=_build_character_json,
                            inputs=[
                                c_name,
                                c_age,
                                c_gender,
                                c_personalities,
                                c_app_desc,
                                c_app_height,
                                c_app_weight,
                                c_app_hair,
                                c_app_eyes,
                                c_bg_hometown,
                                c_bg_family,
                                c_bg_motivation,
                                c_skills,
                                c_secrets,
                            ],
                            outputs=[new_char_json],
                        )

                        save_char_btn.click(
                            fn=save_character_router,
                            inputs=[new_char_filename, new_char_json, backend_mode, backend_url],
                            outputs=[save_char_status],
                        )

                    with gr.TabItem("Environments"):
                        gr.Markdown("#### Select an existing environment JSON")
                        with gr.Row():
                            env_file = gr.Dropdown(label="Environment file", choices=[], value=None)
                            refresh_envs = gr.Button("Refresh list", variant="secondary")
                            load_env_btn = gr.Button("Load selected", variant="primary")
                        env_status = gr.Textbox(label="Status", value="", interactive=False)
                        loaded_env_json = gr.Code(label="Loaded environment JSON (read-only view)", language="json", value="", interactive=False)

                        refresh_envs.click(
                            fn=refresh_environments_router,
                            inputs=[backend_mode, backend_url],
                            outputs=[env_file, env_status],
                        )
                        load_env_btn.click(
                            fn=load_environment_router,
                            inputs=[env_file, backend_mode, backend_url],
                            outputs=[loaded_env_json, env_status],
                        )

                        gr.Markdown("#### Create a new environment (based on `environment.json` keys)")
                        with gr.Row():
                            new_env_filename = gr.Textbox(label="Save as filename", placeholder="MyNewEnvironment.json")
                            save_env_btn = gr.Button("Save environment JSON", variant="primary")
                        save_env_status = gr.Textbox(label="Status", value="", interactive=False)

                        new_env_json = gr.Code(label="Environment JSON to save (editable)", language="json", value="", interactive=True)

                        with gr.Row():
                            e_era = gr.Textbox(label="era", placeholder="Post-Interstellar Colonization")
                            e_time = gr.Textbox(label="time_period", placeholder="25th Century")

                        gr.Markdown("**detail**")
                        e_detail_env = gr.Textbox(label="detail.Environment", lines=2)
                        e_detail_soc = gr.Textbox(label="detail.Social and Economic Aspects", lines=2)
                        e_detail_live = gr.Textbox(label="detail.Livelihood", lines=2)
                        e_detail_hier = gr.Textbox(label="detail.Social Hierarchy", lines=2)
                        e_detail_cult = gr.Textbox(label="detail.Cultural Norms", lines=2)
                        e_detail_nat = gr.Textbox(label="detail.Natural Environment", lines=2)
                        e_detail_pol = gr.Textbox(label="detail.Political Climate", lines=2)

                        gr.Markdown("**guardrails**")
                        g_ai = gr.Textbox(label="guardrails.AI Safety", lines=2)
                        g_undes = gr.Textbox(label="guardrails.Undesirable Topics", lines=2)
                        g_harm = gr.Textbox(label="guardrails.Harmful Content", lines=2)
                        g_sens = gr.Textbox(label="guardrails.Sensitive Information", lines=2)
                        g_inapp = gr.Textbox(label="guardrails.Inappropriate Content", lines=2)
                        g_logic = gr.Textbox(label="guardrails.Logical Consistency", lines=2)

                        build_env_btn = gr.Button("Build JSON from fields →", variant="secondary")
                        build_env_btn.click(
                            fn=_build_environment_json,
                            inputs=[
                                e_era,
                                e_time,
                                e_detail_env,
                                e_detail_soc,
                                e_detail_live,
                                e_detail_hier,
                                e_detail_cult,
                                e_detail_nat,
                                e_detail_pol,
                                g_ai,
                                g_undes,
                                g_harm,
                                g_sens,
                                g_inapp,
                                g_logic,
                            ],
                            outputs=[new_env_json],
                        )

                        save_env_btn.click(
                            fn=save_environment_router,
                            inputs=[new_env_filename, new_env_json, backend_mode, backend_url],
                            outputs=[save_env_status],
                        )

                # Populate dropdowns on initial page load (best-effort).
                demo.load(
                    fn=refresh_characters_router,
                    inputs=[backend_mode, backend_url],
                    outputs=[character_file, char_status],
                )
                demo.load(
                    fn=refresh_environments_router,
                    inputs=[backend_mode, backend_url],
                    outputs=[env_file, env_status],
                )
            with gr.TabItem("Character Image Generation"):
                gr.Markdown("### Generate profile + full-body images (TogetherAI FLUX)\n\nThis runs via the backend route `POST /image/generate`.")

                gr.Markdown("#### Prompt builder (select saved Character + Environment JSON)\n\nBuild a prompt automatically from the selected JSON files, then optionally tweak it before generating.")

                with gr.Row():
                    img_character_file = gr.Dropdown(label="Character JSON", choices=[], value=None)
                    img_environment_file = gr.Dropdown(label="Environment JSON", choices=[], value=None)

                extra_details = gr.Textbox(
                    label="Extra style/details (appended)",
                    placeholder="e.g. cinematic lighting, ultra-detailed, concept art, neutral pose, white background",
                    lines=2,
                )

                with gr.Row():
                    build_prompt_btn = gr.Button("Build prompt from selections →", variant="secondary")
                    refresh_prompt_sources_btn = gr.Button("Refresh lists", variant="secondary")
                    prompt_build_status = gr.Textbox(label="Status", value="", interactive=False)

                prompt = gr.Textbox(
                    label="Character prompt",
                    placeholder="Describe your character (style, clothing, setting, etc.)",
                    lines=4,
                )

                refresh_prompt_sources_btn.click(
                    fn=refresh_characters_router,
                    inputs=[backend_mode, backend_url],
                    outputs=[img_character_file, prompt_build_status],
                )
                refresh_prompt_sources_btn.click(
                    fn=refresh_environments_router,
                    inputs=[backend_mode, backend_url],
                    outputs=[img_environment_file, prompt_build_status],
                )

                build_prompt_btn.click(
                    fn=build_image_prompt_router,
                    inputs=[
                        img_character_file,
                        img_environment_file,
                        extra_details,
                        backend_mode,
                        backend_url,
                    ],
                    outputs=[prompt, prompt_build_status],
                )

                # Populate prompt sources after components exist (avoid UnboundLocalError).
                demo.load(
                    fn=refresh_characters_router,
                    inputs=[backend_mode, backend_url],
                    outputs=[img_character_file, prompt_build_status],
                )
                demo.load(
                    fn=refresh_environments_router,
                    inputs=[backend_mode, backend_url],
                    outputs=[img_environment_file, prompt_build_status],
                )

                gr.Markdown("Optional: provide a reference image (upload or URL). This is passed to Together FLUX as `reference_images`.")
                with gr.Row():
                    reference_image = gr.Image(label="Reference image (optional)", type="pil")
                    reference_image_url = gr.Textbox(
                        label="Reference image URL (optional)",
                        placeholder="https://... (publicly accessible image URL)",
                    )

                with gr.Row():
                    profile_width = gr.Number(label="Profile width", value=768, precision=0)
                    profile_height = gr.Number(label="Profile height", value=768, precision=0)
                    full_width = gr.Number(label="Full-body width", value=832, precision=0)
                    full_height = gr.Number(label="Full-body height", value=1216, precision=0)

                with gr.Row():
                    gen_btn = gr.Button("Generate images", variant="primary")
                    gen_status = gr.Textbox(label="Status", value="", interactive=False)

                with gr.Row():
                    profile_img = gr.Image(label="Profile", type="pil")
                    full_img = gr.Image(label="Full body", type="pil")

                profile_url = gr.Textbox(label="Profile image URL", interactive=False)
                full_url = gr.Textbox(label="Full body image URL", interactive=False)

                profile_id = gr.Textbox(label="Profile asset_id", interactive=False)
                full_id = gr.Textbox(label="Full body asset_id", interactive=False)

                gen_btn.click(
                    fn=image_generate_router,
                    inputs=[
                        prompt,
                        backend_mode,
                        backend_url,
                        profile_width,
                        profile_height,
                        full_width,
                        full_height,
                        reference_image,
                        reference_image_url,
                    ],
                    outputs=[profile_img, full_img, profile_url, full_url, profile_id, full_id, gen_status],
                )

            with gr.TabItem("3D Model Generation (Modal GPU)"):
                gr.Markdown(
                    "### Convert an image asset to a GLB (TRELLIS.2)\n\n"
                    "This requires a GPU (typically run via Modal).\n\n"
                    "Tip: generate images in the previous tab first, then convert *Profile* or *Full body*."
                )
                with gr.Column() as modal_only_panel:
                    which = gr.Radio(choices=["Profile", "Full body"], value="Profile", label="Which image to convert?")
                    convert_btn = gr.Button("Convert selected image to GLB (GPU)", variant="primary")
                    convert_status = gr.Textbox(label="Status", value="", interactive=False)
                    with gr.Row():
                        glb_view = gr.Model3D(label="GLB preview (URL)")
                        glb_download = gr.Textbox(label="GLB download URL", interactive=False)

                    # Reuse the asset_id textboxes from the Image tab via "shared" component references.
                    convert_btn.click(
                        fn=image_to_3d_router,
                        inputs=[which, profile_id, full_id, backend_mode, backend_url],
                        outputs=[glb_view, glb_download, convert_status],
                    )

    return demo


def start_local_fastapi_in_background(host: str, port: int) -> None:
    """
    Starts the FastAPI backend (app/api.py) in a background thread.

    This is intended for local development so you can run *both* FastAPI + Gradio via:
      python main.py
    """
    import threading

    import uvicorn

    def _run() -> None:
        from app.api import app as fastapi_app

        config = uvicorn.Config(
            fastapi_app,
            host=host,
            port=port,
            log_level=os.getenv("NPC_UVICORN_LOG_LEVEL", "info"),
            access_log=True,
        )
        server = uvicorn.Server(config)
        server.run()

    t = threading.Thread(target=_run, daemon=True)
    t.start()


if __name__ == "__main__":
    # "Better workflow" default: run a local FastAPI server and point Gradio at it.
    start_backend = os.getenv("NPC_START_BACKEND", "1").lower() not in {"0", "false", "no"}
    backend_host = os.getenv("NPC_BACKEND_HOST", "127.0.0.1")
    backend_port = int(os.getenv("NPC_BACKEND_PORT", "8000"))

    if start_backend:
        start_local_fastapi_in_background(host=backend_host, port=backend_port)
        os.environ.setdefault("NPC_BACKEND_MODE", "Local FastAPI")
        os.environ.setdefault("NPC_BACKEND_URL", f"http://{backend_host}:{backend_port}")
        _dbg_log("H9", "main.py:__main__", "started local fastapi", data={"NPC_BACKEND_URL": (os.getenv("NPC_BACKEND_URL") or "")[:200], "NPC_BACKEND_MODE": os.getenv("NPC_BACKEND_MODE")})

    # Local dev default: run `modal serve modal_app.py` alongside Gradio unless explicitly disabled.
    start_modal = os.getenv("NPC_START_MODAL_SERVE", "1").lower() in {"1", "true", "yes"}
    if start_modal:
        # Prefer Modal backend in the UI when explicitly requested.
        os.environ["NPC_BACKEND_MODE"] = BACKEND_MODE_MODAL
        msg = start_modal_serve_in_background()
        _dbg_log("H10", "main.py:__main__", "requested modal serve", data={"msg": msg[:240], "NPC_BACKEND_MODE": os.getenv("NPC_BACKEND_MODE"), "NPC_BACKEND_URL": (os.getenv("NPC_BACKEND_URL") or "")[:200]})

    atexit.register(lambda: stop_modal_serve())

    demo = build_demo()
    demo.launch()

    # Capture shutdown signals
    demo.close(shutdown)