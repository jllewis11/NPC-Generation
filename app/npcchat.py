import os

from app.backend_client import backend_url_from_env, chat as remote_chat, clear_history as remote_clear_history


def _extract_gradio_message_text(msg: object) -> str:
    """
    Gradio may provide history items as dicts like:
      {"role": "user"|"assistant", "content": [{"text": "...", "type": "text"}], ...}
    This helper extracts a reasonable plain-text representation without being strict.
    """
    try:
        if isinstance(msg, str):
            return msg
        if isinstance(msg, dict):
            content = msg.get("content")
            if isinstance(content, list):
                parts: list[str] = []
                for c in content:
                    if isinstance(c, dict) and isinstance(c.get("text"), str):
                        parts.append(c["text"])
                if parts:
                    return "\n".join(parts).strip()
            # Fallbacks
            if isinstance(msg.get("text"), str):
                return msg["text"].strip()
            if isinstance(msg.get("content"), str):
                return str(msg.get("content", "")).strip()
        return str(msg).strip()
    except Exception:
        return ""


def _normalize_history_for_backend(history: object) -> tuple[list[list[str]], bool]:
    """
    FastAPI expects `history: List[List[str]]` (pairs of [player, assistant]).

    Newer Gradio versions sometimes send a list of dict "messages" (role/content).
    Convert that to pairs so the backend doesn't 422.
    """
    if not history:
        return [], False

    # Already in pair format?
    if isinstance(history, list) and all(isinstance(x, list) and len(x) >= 2 for x in history):
        pairs_from_pairs: list[list[str]] = []
        for x in history:
            try:
                u = x[0] if len(x) > 0 else ""
                a = x[1] if len(x) > 1 else ""
                pairs_from_pairs.append([str(u), str(a)])
            except Exception:
                continue
        return pairs_from_pairs, False

    # Dict message format
    if isinstance(history, list) and all(isinstance(x, dict) and "role" in x for x in history):
        pairs_from_messages: list[list[str]] = []
        pending_user: str | None = None
        for item in history:
            role = str(item.get("role", "")).lower()
            text = _extract_gradio_message_text(item)
            if role == "user":
                pending_user = text
            elif role == "assistant":
                if pending_user is None:
                    # No user message found; skip pairing.
                    continue
                pairs_from_messages.append([pending_user, text])
                pending_user = None
        return pairs_from_messages, True

    # Unknown format; best-effort fallback to empty to avoid 422.
    return [], True


def _local_backend_url_from_env() -> str:
    host = os.getenv("NPC_BACKEND_HOST", "127.0.0.1")
    port = os.getenv("NPC_BACKEND_PORT", "8000")
    return f"http://{host}:{port}"


def _resolve_base_url(backend_mode: str, backend_url: str) -> str:
    """
    Single source of truth: Gradio always calls FastAPI over HTTP.

    - Local FastAPI: uses NPC_BACKEND_HOST/PORT (or defaults)
    - Modal deployment: uses provided URL or NPC_BACKEND_URL env
    """
    mode = (backend_mode or "").strip().lower()
    if mode.startswith("local"):
        return _local_backend_url_from_env()
    return (backend_url or "").strip() or backend_url_from_env()


def npc_chat_router(message, history, backend_mode: str, backend_url: str):
    base_url = _resolve_base_url(backend_mode=backend_mode, backend_url=backend_url)
    if not base_url:
        return "Error: Backend URL is empty. Paste your Modal `.modal.run` URL (or set NPC_BACKEND_URL)."

    try:
        normalized_history, did_normalize = _normalize_history_for_backend(history)
        result = remote_chat(base_url=base_url, message=message, history=normalized_history)
        response_text = result.get("response", "")
        time_taken = result.get("time_taken", None)
        # IMPORTANT: The chat UI must display ONLY the character's dialogue.
        # Timing is still returned by the backend and captured in logs, but we don't prepend it to the message.
        return response_text
    except Exception as e:
        return f"Error calling backend ({base_url}): {e}"


def clear_history_router(backend_mode: str, backend_url: str):
    base_url = _resolve_base_url(backend_mode=backend_mode, backend_url=backend_url)
    if not base_url:
        return "Error: Backend URL is empty. Paste your Modal `.modal.run` URL (or set NPC_BACKEND_URL)."

    try:
        result = remote_clear_history(base_url=base_url)
        msg = result.get("message", "Cleared.")
        ok = result.get("success", True)
        return msg if ok else f"Failed: {msg}"
    except Exception as e:
        return f"Error calling backend ({base_url}): {e}"


def shutdown():
    # ChromaDB PersistentClient doesn't require explicit closing
    pass
