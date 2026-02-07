import os
from typing import Any, Dict, List, Optional

import requests


def _normalize_base_url(base_url: str) -> str:
    base_url = (base_url or "").strip()
    if not base_url:
        return ""
    return base_url[:-1] if base_url.endswith("/") else base_url


def backend_url_from_env() -> str:
    """
    Returns the configured backend URL from env, if present.

    - NPC_BACKEND_URL: preferred
    - MODAL_BACKEND_URL: fallback
    """
    return _normalize_base_url(os.getenv("NPC_BACKEND_URL") or os.getenv("MODAL_BACKEND_URL") or "")


def health(base_url: str, timeout_s: float = 10.0) -> Dict[str, Any]:
    base_url = _normalize_base_url(base_url)
    if not base_url:
        raise ValueError("Backend base_url is empty")
    resp = requests.get(f"{base_url}/health", timeout=timeout_s)
    resp.raise_for_status()
    return resp.json()


def chat(
    base_url: str,
    message: str,
    history: Optional[List[List[str]]] = None,
    timeout_s: float = 90.0,
) -> Dict[str, Any]:
    """
    Calls POST /chat on the FastAPI backend.

    Expected response:
      { "response": str, "time_taken": float }
    """
    base_url = _normalize_base_url(base_url)
    if not base_url:
        raise ValueError("Backend base_url is empty")

    payload = {"message": message, "history": history or []}
    resp = requests.post(
        f"{base_url}/chat",
        json=payload,
        headers={"content-type": "application/json"},
        timeout=timeout_s,
    )
    resp.raise_for_status()
    return resp.json()


def clear_history(base_url: str, timeout_s: float = 30.0) -> Dict[str, Any]:
    """
    Calls POST /clear-history on the FastAPI backend.
    """
    base_url = _normalize_base_url(base_url)
    if not base_url:
        raise ValueError("Backend base_url is empty")
    resp = requests.post(f"{base_url}/clear-history", timeout=timeout_s)
    resp.raise_for_status()
    return resp.json()


def image_generate(
    base_url: str,
    prompt: str,
    profile_width: int = 768,
    profile_height: int = 768,
    full_width: int = 832,
    full_height: int = 1216,
    reference_images: Optional[List[str]] = None,
    timeout_s: float = 180.0,
) -> Dict[str, Any]:
    """
    Calls POST /image/generate on the backend.
    """
    base_url = _normalize_base_url(base_url)
    if not base_url:
        raise ValueError("Backend base_url is empty")
    payload = {
        "prompt": prompt,
        "profile": {"width": profile_width, "height": profile_height},
        "full_body": {"width": full_width, "height": full_height},
    }
    refs = [str(u).strip() for u in (reference_images or []) if str(u).strip()]
    if refs:
        payload["reference_images"] = refs
    resp = requests.post(
        f"{base_url}/image/generate",
        json=payload,
        headers={"content-type": "application/json"},
        timeout=timeout_s,
    )
    resp.raise_for_status()
    return resp.json()

def image_upload(
    base_url: str,
    image_bytes: bytes,
    filename: str = "reference.png",
    timeout_s: float = 60.0,
) -> Dict[str, Any]:
    """
    Calls POST /image/upload (multipart) to store an image and receive a URL suitable
    for Together `reference_images`.
    """
    base_url = _normalize_base_url(base_url)
    if not base_url:
        raise ValueError("Backend base_url is empty")
    if not image_bytes:
        raise ValueError("image_bytes is empty")

    files = {"file": (filename, image_bytes, "image/png")}
    resp = requests.post(f"{base_url}/image/upload", files=files, timeout=timeout_s)
    resp.raise_for_status()
    return resp.json()


def image_to_3d(
    base_url: str,
    asset_id: str,
    timeout_s: float = 1200.0,
) -> Dict[str, Any]:
    """
    Calls POST /image/to-3d on the backend.
    """
    base_url = _normalize_base_url(base_url)
    if not base_url:
        raise ValueError("Backend base_url is empty")
    payload = {"asset_id": asset_id}
    resp = requests.post(
        f"{base_url}/image/to-3d",
        json=payload,
        headers={"content-type": "application/json"},
        timeout=timeout_s,
    )
    resp.raise_for_status()
    return resp.json()


def list_image_prompt_presets(base_url: str, timeout_s: float = 20.0) -> Dict[str, Any]:
    """
    Calls GET /image/presets on the backend.
    """
    base_url = _normalize_base_url(base_url)
    if not base_url:
        raise ValueError("Backend base_url is empty")
    resp = requests.get(f"{base_url}/image/presets", timeout=timeout_s)
    resp.raise_for_status()
    return resp.json()


def upsert_image_prompt_preset(
    base_url: str,
    name: str,
    kind: str,
    prompt: str,
    timeout_s: float = 30.0,
) -> Dict[str, Any]:
    """
    Calls PUT /image/presets on the backend.
    """
    base_url = _normalize_base_url(base_url)
    if not base_url:
        raise ValueError("Backend base_url is empty")
    payload = {"name": name, "kind": kind, "prompt": prompt}
    resp = requests.put(
        f"{base_url}/image/presets",
        json=payload,
        headers={"content-type": "application/json"},
        timeout=timeout_s,
    )
    resp.raise_for_status()
    return resp.json()


def delete_image_prompt_preset(base_url: str, name: str, timeout_s: float = 30.0) -> Dict[str, Any]:
    """
    Calls DELETE /image/presets/{name} on the backend.
    """
    base_url = _normalize_base_url(base_url)
    if not base_url:
        raise ValueError("Backend base_url is empty")
    resp = requests.delete(f"{base_url}/image/presets/{name}", timeout=timeout_s)
    resp.raise_for_status()
    return resp.json()


def list_characters(base_url: str, timeout_s: float = 20.0) -> Dict[str, Any]:
    base_url = _normalize_base_url(base_url)
    if not base_url:
        raise ValueError("Backend base_url is empty")
    resp = requests.get(f"{base_url}/config/characters", timeout=timeout_s)
    resp.raise_for_status()
    return resp.json()


def list_environments(base_url: str, timeout_s: float = 20.0) -> Dict[str, Any]:
    base_url = _normalize_base_url(base_url)
    if not base_url:
        raise ValueError("Backend base_url is empty")
    resp = requests.get(f"{base_url}/config/environments", timeout=timeout_s)
    resp.raise_for_status()
    return resp.json()


def load_character(base_url: str, filename: str, timeout_s: float = 30.0) -> Dict[str, Any]:
    base_url = _normalize_base_url(base_url)
    if not base_url:
        raise ValueError("Backend base_url is empty")
    payload = {"filename": filename}
    resp = requests.post(
        f"{base_url}/config/character/load",
        json=payload,
        headers={"content-type": "application/json"},
        timeout=timeout_s,
    )
    resp.raise_for_status()
    return resp.json()


def save_character(base_url: str, filename: str, character: Dict[str, Any], timeout_s: float = 30.0) -> Dict[str, Any]:
    base_url = _normalize_base_url(base_url)
    if not base_url:
        raise ValueError("Backend base_url is empty")
    payload = {"filename": filename, "character": character}
    resp = requests.post(
        f"{base_url}/config/character/save",
        json=payload,
        headers={"content-type": "application/json"},
        timeout=timeout_s,
    )
    resp.raise_for_status()
    return resp.json()


def load_environment(base_url: str, filename: str, timeout_s: float = 30.0) -> Dict[str, Any]:
    base_url = _normalize_base_url(base_url)
    if not base_url:
        raise ValueError("Backend base_url is empty")
    payload = {"filename": filename}
    resp = requests.post(
        f"{base_url}/config/environment/load",
        json=payload,
        headers={"content-type": "application/json"},
        timeout=timeout_s,
    )
    resp.raise_for_status()
    return resp.json()


def save_environment(base_url: str, filename: str, environment: Dict[str, Any], timeout_s: float = 30.0) -> Dict[str, Any]:
    base_url = _normalize_base_url(base_url)
    if not base_url:
        raise ValueError("Backend base_url is empty")
    payload = {"filename": filename, "environment": environment}
    resp = requests.post(
        f"{base_url}/config/environment/save",
        json=payload,
        headers={"content-type": "application/json"},
        timeout=timeout_s,
    )
    resp.raise_for_status()
    return resp.json()

