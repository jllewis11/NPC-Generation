"""
FastAPI application for NPC dialogue generation.
"""
# Patch sqlite3 before importing chromadb to avoid version issues
import sys
try:
    import pysqlite3  # type: ignore[import-not-found]
    sys.modules['sqlite3'] = pysqlite3
except ImportError:
    pass  # Fall back to system sqlite3 if pysqlite3 not available

from fastapi import FastAPI, HTTPException, Request, UploadFile, File
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Any, List, Optional
import os
import time
import json
from dotenv import load_dotenv
import chromadb
import uuid
# Use Together AI API directly via HTTP requests
import requests
import pathlib as _pathlib
import json as _json
from urllib.parse import urlparse as _urlparse

# Load environment variables
load_dotenv()

# #region agent log
def _dbg_log(hypothesis_id: str, location: str, message: str, data: dict | None = None, run_id: str = "run_upload_sig_fix") -> None:
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
        log_path = os.getenv("NPC_DEBUG_LOG_PATH", str((_pathlib.Path(__file__).parent.parent / ".cursor" / "debug.log").resolve()))
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(_json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        pass
# #endregion agent log

# Initialize FastAPI app
app = FastAPI(title="NPC Dialogue Generation API", version="1.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load environment and character data
environment_context = None
character_context = None
environment_filename: str | None = None
character_filename: str | None = None

# Load environment data from environment.json (use absolute path for Modal)
import pathlib
_json_path = pathlib.Path(__file__).parent.parent / "JSONData"
if not _json_path.exists():
    # Fallback to /JSONData for Modal deployment
    _json_path = pathlib.Path("/JSONData")

with open(_json_path / "environment.json", "r") as file:
    environment_data = json.load(file)
    environment_context = {
        "era": environment_data.get("era", ""),
        "time_period": environment_data.get("time_period", ""),
        "detail": environment_data.get("detail", {}),
        "guardrails": environment_data.get("guardrails", {})
    }
    environment_filename = "environment.json"

# Load character data from KaiyaStarling.json
with open(_json_path / "KaiyaStarling.json", "r") as file:
    character_context = json.load(file)
    character_filename = "KaiyaStarling.json"

# Initialize ChromaDB Cloud (lazy initialization in function)
_client = None
_llm = None

def get_chroma_client():
    """Lazy initialization of ChromaDB client."""
    global _client
    if _client is None:
        chroma_api_key = os.getenv("CHROMA_API_KEY")
        chroma_tenant = os.getenv("CHROMA_TENANT")
        chroma_database = os.getenv("CHROMA_DATABASE")
        
        if chroma_api_key and chroma_tenant and chroma_database:
            try:
                # Use CloudClient with v2 API (latest chromadb version)
                # CloudClient can be instantiated with just api_key if scoped to single DB
                # Or with tenant, database, and api_key explicitly
                _client = chromadb.CloudClient(
                    tenant=chroma_tenant,
                    database=chroma_database,
                    api_key=chroma_api_key
                )
                print(f"✓ Connected to ChromaDB Cloud: tenant={chroma_tenant}, database={chroma_database}")
            except Exception as e:
                # If CloudClient fails, log error and fall back to local
                print(f"Warning: ChromaDB Cloud connection failed: {e}")
                print("Falling back to local ChromaDB")
                persist_directory = os.getenv("CHROMA_PERSIST_DIR", "/data/chroma")
                os.makedirs(persist_directory, exist_ok=True)
                _client = chromadb.PersistentClient(path=persist_directory)
        else:
            # Fallback to local if cloud credentials not provided
            persist_directory = os.getenv("CHROMA_PERSIST_DIR", "/data/chroma")
            os.makedirs(persist_directory, exist_ok=True)
            _client = chromadb.PersistentClient(path=persist_directory)
    return _client

def get_together_api_key():
    """Get Together AI API key from environment."""
    api_key = os.getenv("TOGETHER_API_KEY")
    if not api_key:
        raise ValueError("TOGETHER_API_KEY environment variable is not set")
    return api_key


# Pydantic models for request/response
class ChatMessage(BaseModel):
    message: str
    history: Optional[List[List[str]]] = []


class ChatResponse(BaseModel):
    response: str
    time_taken: float


class ClearHistoryResponse(BaseModel):
    message: str
    success: bool


class ImageSize(BaseModel):
    width: int
    height: int


class ImageGenerateRequest(BaseModel):
    prompt: str
    # Optional per-image prompt overrides
    profile_prompt: Optional[str] = None
    full_body_prompt: Optional[str] = None
    # Optional reference image URLs to guide generation (Together FLUX `reference_images`)
    reference_images: Optional[List[str]] = None
    # Default sizes chosen to be within Together limits and sensible for avatar/full-body
    profile: ImageSize = Field(default_factory=lambda: ImageSize(width=768, height=768))
    full_body: ImageSize = Field(default_factory=lambda: ImageSize(width=832, height=1216))


class ImageGenerateResponse(BaseModel):
    profile_asset_id: str
    full_body_asset_id: str
    profile_image_url: str
    full_body_image_url: str


class ImageTo3DRequest(BaseModel):
    asset_id: str


class ImageTo3DResponse(BaseModel):
    glb_asset_id: str
    glb_url: str
    glb_download_url: str

class ImageUploadResponse(BaseModel):
    asset_id: str
    image_url: str


class ImagePromptPreset(BaseModel):
    """
    A reusable prompt snippet for image generation.

    - kind=character: describes the subject (appearance, outfit, style)
    - kind=environment: describes the setting/background/era
    """

    name: str
    kind: str = Field(pattern="^(character|environment)$")
    prompt: str


class ImagePromptPresetsResponse(BaseModel):
    presets: list[ImagePromptPreset]


class UpsertImagePromptPresetRequest(BaseModel):
    name: str
    kind: str = Field(pattern="^(character|environment)$")
    prompt: str


IMAGE_PROMPT_PRESETS_FILENAME = "image_prompt_presets.json"


def _image_prompt_presets_path() -> pathlib.Path:
    assets = _ensure_assets_dir()
    return assets / IMAGE_PROMPT_PRESETS_FILENAME


def _read_image_prompt_presets() -> dict[str, dict[str, str]]:
    """
    Storage format on disk:
      { "<name>": { "kind": "character|environment", "prompt": "..." }, ... }
    """
    path = _image_prompt_presets_path()
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8") or "{}")
        if not isinstance(raw, dict):
            return {}
        out: dict[str, dict[str, str]] = {}
        for k, v in raw.items():
            if not isinstance(k, str) or not isinstance(v, dict):
                continue
            kind = str(v.get("kind", "") or "")
            prompt = str(v.get("prompt", "") or "")
            if kind not in {"character", "environment"}:
                continue
            if not prompt.strip():
                continue
            out[k] = {"kind": kind, "prompt": prompt}
        return out
    except Exception:
        return {}


def _atomic_write_text(path: pathlib.Path, text: str) -> None:
    import os as _os
    import tempfile as _tempfile

    path.parent.mkdir(parents=True, exist_ok=True)
    with _tempfile.NamedTemporaryFile("w", delete=False, dir=str(path.parent), encoding="utf-8") as f:
        f.write(text)
        tmp = f.name
    _os.replace(tmp, str(path))


def _write_image_prompt_presets(data: dict[str, dict[str, str]]) -> None:
    path = _image_prompt_presets_path()
    payload = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    _atomic_write_text(path, payload)


TEMP_UPLOAD_TTL_SECONDS = int(os.getenv("NPC_TEMP_UPLOAD_TTL_SECONDS", "300"))  # default: 5 minutes


def _tmp_meta_path_for_asset(asset_id: str) -> pathlib.Path:
    assets = _ensure_assets_dir()
    return assets / f"{asset_id}.tmp.json"


def _write_tmp_meta(asset_id: str, expires_at_unix_s: float) -> None:
    meta = {
        "asset_id": asset_id,
        "kind": "temporary_upload",
        "created_at": time.time(),
        "expires_at": float(expires_at_unix_s),
        "ttl_seconds": float(expires_at_unix_s) - time.time(),
    }
    _tmp_meta_path_for_asset(asset_id).write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")


def _delete_asset_files(asset_id: str) -> None:
    """
    Best-effort delete of an asset (any known extension) and its temp metadata file.
    """
    assets = _ensure_assets_dir()
    for ext in (".png", ".jpg", ".jpeg", ".webp", ".glb"):
        p = assets / f"{asset_id}{ext}"
        try:
            if p.exists():
                p.unlink()
        except Exception:
            pass
    try:
        mp = _tmp_meta_path_for_asset(asset_id)
        if mp.exists():
            mp.unlink()
    except Exception:
        pass


def _enforce_temp_asset_not_expired(asset_id: str) -> None:
    """
    If an asset was uploaded as a temporary reference image, enforce its TTL.
    """
    mp = _tmp_meta_path_for_asset(asset_id)
    if not mp.exists():
        return
    try:
        meta = json.loads(mp.read_text(encoding="utf-8") or "{}")
        expires_at = float(meta.get("expires_at", 0.0) or 0.0)
    except Exception:
        expires_at = 0.0
    if time.time() >= expires_at:
        _delete_asset_files(asset_id)
        raise HTTPException(status_code=404, detail="Asset expired")


def _maybe_modal_commit_assets_volume() -> None:
    """
    In Modal, /assets is backed by a Volume. Writes may not be visible cross-container
    until committed. We call a tiny Modal function when available (see modal_app.py).
    """
    try:
        if not (os.getenv("MODAL_APP_NAME") or os.getenv("MODAL_TASK_ID")):
            return
        import modal  # type: ignore

        modal_app_name = os.getenv("MODAL_APP_NAME", "npc-dialogue-api")
        fn = modal.Function.lookup(modal_app_name, "commit_assets_volume")
        fn.remote()
    except Exception:
        # Best-effort: do not fail user requests if commit isn't available.
        return


@app.get("/image/presets", response_model=ImagePromptPresetsResponse)
async def list_image_prompt_presets():
    """
    List saved image prompt presets. Stored on the assets directory (Modal Volume on deploy).
    """
    data = _read_image_prompt_presets()
    presets: list[ImagePromptPreset] = []
    for name in sorted(data.keys(), key=lambda s: s.lower()):
        item = data[name]
        presets.append(ImagePromptPreset(name=name, kind=item["kind"], prompt=item["prompt"]))
    return ImagePromptPresetsResponse(presets=presets)


@app.put("/image/presets")
async def upsert_image_prompt_preset(body: UpsertImagePromptPresetRequest):
    name = (body.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="name is required")
    prompt = (body.prompt or "").strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="prompt is required")
    kind = (body.kind or "").strip()
    if kind not in {"character", "environment"}:
        raise HTTPException(status_code=400, detail="kind must be 'character' or 'environment'")

    data = _read_image_prompt_presets()
    data[name] = {"kind": kind, "prompt": prompt}
    _write_image_prompt_presets(data)
    _maybe_modal_commit_assets_volume()
    return {"ok": True, "name": name, "kind": kind}


@app.delete("/image/presets/{name}")
async def delete_image_prompt_preset(name: str):
    n = (name or "").strip()
    if not n:
        raise HTTPException(status_code=400, detail="name is required")
    data = _read_image_prompt_presets()
    if n in data:
        del data[n]
        _write_image_prompt_presets(data)
        _maybe_modal_commit_assets_volume()
    return {"ok": True, "deleted": n}


class ConfigFilesResponse(BaseModel):
    files: list[str]
    current: Optional[str] = None


class LoadCharacterRequest(BaseModel):
    filename: Optional[str] = None
    character: Optional[dict[str, Any]] = None


class SaveCharacterRequest(BaseModel):
    filename: str
    character: dict[str, Any]


class LoadEnvironmentRequest(BaseModel):
    filename: Optional[str] = None
    environment: Optional[dict[str, Any]] = None


class SaveEnvironmentRequest(BaseModel):
    filename: str
    environment: dict[str, Any]


def _json_dir() -> pathlib.Path:
    """
    Returns the JSONData directory used by this backend.
    """
    if _json_path.exists():
        return _json_path
    raise HTTPException(status_code=500, detail="JSONData directory not found on server")


def _safe_json_filename(filename: str) -> str:
    """
    Prevent path traversal and normalize filenames.
    """
    name = (filename or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="filename is required")
    if "/" in name or "\\" in name:
        raise HTTPException(status_code=400, detail="filename must not contain path separators")
    if not name.lower().endswith(".json"):
        name += ".json"
    return name


def _looks_like_character(obj: Any) -> bool:
    if not isinstance(obj, dict):
        return False
    required = {"name", "age", "gender", "personalities", "appearance", "background", "skills", "secrets"}
    return required.issubset(set(obj.keys()))


def _looks_like_environment(obj: Any) -> bool:
    if not isinstance(obj, dict):
        return False
    required = {"era", "time_period", "detail", "guardrails"}
    return required.issubset(set(obj.keys()))


def _list_json_files() -> list[str]:
    d = _json_dir()
    files = [p.name for p in d.iterdir() if p.is_file() and p.suffix.lower() == ".json"]
    files.sort(key=lambda x: x.lower())
    return files


@app.get("/config/characters", response_model=ConfigFilesResponse)
async def list_character_files():
    """
    List character JSON files available in JSONData (heuristic based on keys).
    """
    d = _json_dir()
    out: list[str] = []
    for fn in _list_json_files():
        try:
            data = json.loads((d / fn).read_text(encoding="utf-8"))
            if _looks_like_character(data):
                out.append(fn)
        except Exception:
            continue
    return ConfigFilesResponse(files=out, current=character_filename)


@app.get("/config/environments", response_model=ConfigFilesResponse)
async def list_environment_files():
    """
    List environment JSON files available in JSONData (heuristic based on keys).
    """
    d = _json_dir()
    out: list[str] = []
    for fn in _list_json_files():
        try:
            data = json.loads((d / fn).read_text(encoding="utf-8"))
            if _looks_like_environment(data):
                out.append(fn)
        except Exception:
            continue
    return ConfigFilesResponse(files=out, current=environment_filename)


@app.post("/config/character/load")
async def load_character(body: LoadCharacterRequest):
    """
    Set the active character for chat. Provide either:
    - filename: load from JSONData
    - character: inline JSON object (not persisted unless saved separately)
    """
    global character_context, character_filename

    if body.character is not None:
        if not _looks_like_character(body.character):
            raise HTTPException(status_code=400, detail="character object does not match expected schema")
        character_context = body.character
        character_filename = None
        return {"ok": True, "current": character_filename, "character": character_context}

    if not body.filename:
        raise HTTPException(status_code=400, detail="Provide either filename or character")
    fn = _safe_json_filename(body.filename)
    path = _json_dir() / fn
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Character file not found: {fn}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not _looks_like_character(data):
        raise HTTPException(status_code=400, detail=f"File does not look like a character JSON: {fn}")
    character_context = data
    character_filename = fn
    return {"ok": True, "current": character_filename, "character": character_context}


@app.post("/config/character/save")
async def save_character(body: SaveCharacterRequest):
    """
    Save a character JSON into JSONData.
    """
    d = _json_dir()
    fn = _safe_json_filename(body.filename)
    if not _looks_like_character(body.character):
        raise HTTPException(status_code=400, detail="character object does not match expected schema")
    path = d / fn
    path.write_text(json.dumps(body.character, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {"ok": True, "filename": fn}


@app.post("/config/environment/load")
async def load_environment(body: LoadEnvironmentRequest):
    """
    Set the active environment for chat. Provide either:
    - filename: load from JSONData
    - environment: inline JSON object (not persisted unless saved separately)
    """
    global environment_context, environment_filename

    if body.environment is not None:
        if not _looks_like_environment(body.environment):
            raise HTTPException(status_code=400, detail="environment object does not match expected schema")
        environment_context = body.environment
        environment_filename = None
        return {"ok": True, "current": environment_filename, "environment": environment_context}

    if not body.filename:
        raise HTTPException(status_code=400, detail="Provide either filename or environment")
    fn = _safe_json_filename(body.filename)
    path = _json_dir() / fn
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Environment file not found: {fn}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not _looks_like_environment(data):
        raise HTTPException(status_code=400, detail=f"File does not look like an environment JSON: {fn}")
    environment_context = {
        "era": data.get("era", ""),
        "time_period": data.get("time_period", ""),
        "detail": data.get("detail", {}),
        "guardrails": data.get("guardrails", {}),
    }
    environment_filename = fn
    return {"ok": True, "current": environment_filename, "environment": environment_context}


@app.post("/config/environment/save")
async def save_environment(body: SaveEnvironmentRequest):
    """
    Save an environment JSON into JSONData.
    """
    d = _json_dir()
    fn = _safe_json_filename(body.filename)
    if not _looks_like_environment(body.environment):
        raise HTTPException(status_code=400, detail="environment object does not match expected schema")
    path = d / fn
    path.write_text(json.dumps(body.environment, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {"ok": True, "filename": fn}


def extract_character_response(text):
    """Extract the character's dialogue from the model output."""
    import re

    def _strip_leading_meta_lines(s: str) -> str:
        """
        Remove leading "checklist"/meta lines that occasionally leak into outputs.
        Be tolerant of punctuation prefixes like ". " or "- ".
        """
        if not s:
            return s
        lines = [ln.rstrip() for ln in s.splitlines()]
        cleaned: list[str] = []
        dropping = True
        for ln in lines:
            raw = ln.strip()
            if dropping:
                if not raw:
                    continue
                low = raw.lstrip(".-*•> ").strip().lower()
                if (
                    low.startswith("also ensure")
                    or low.startswith("check for")
                    or low.startswith("make sure")
                    or low.startswith("now output")
                    or low.startswith("must wrap")
                    or low.startswith("so answer")
                    or low.startswith("the user asks")
                    or low.startswith("output format")
                    or low.startswith("example (follow")
                    or low.startswith("disallowed content")
                    or "disallowed content" in low
                    or "exactly one block" in low
                    or "it's safe" in low
                ):
                    continue
                # Some models leave a stray '.' before meta content; drop it if it's alone.
                if raw == ".":
                    continue
                dropping = False
            cleaned.append(ln)
        return "\n".join(cleaned).strip()
    
    # Strip common non-dialogue prefacing lines some models emit (seen in production logs)
    # e.g. "(add your response below)" or other parenthetical "instruction" lines.
    text = re.sub(r'^\s*\([^)]*response[^)]*\)\s*\n+', '', text, flags=re.IGNORECASE)

    # Remove any reasoning patterns
    text = re.sub(r'Here are my reasoning.*?$', '', text, flags=re.IGNORECASE | re.MULTILINE | re.DOTALL)
    text = re.sub(r'Here Are My Reasonings.*?$', '', text, flags=re.IGNORECASE | re.MULTILINE | re.DOTALL)
    text = re.sub(r'Let me think.*?$', '', text, flags=re.IGNORECASE | re.MULTILINE | re.DOTALL)
    text = re.sub(r'Okay,\s*let[’\']?s\s+see\..*?$', '', text, flags=re.IGNORECASE | re.MULTILINE | re.DOTALL)
    text = re.sub(r'Okay,\s*let[’\']?s\s+.*?$', '', text, flags=re.IGNORECASE | re.MULTILINE | re.DOTALL)
    # Common "planner" preambles (must NOT reach the user)
    text = re.sub(r'^\s*Okay,\s*i\s+need\s+to\s+.*?\n+', '', text, flags=re.IGNORECASE | re.MULTILINE)
    text = re.sub(r'^\s*The\s+user\s+asks:.*?\n+', '', text, flags=re.IGNORECASE | re.MULTILINE)
    text = re.sub(r'^\s*Must\s+wrap\s+.*?\n+', '', text, flags=re.IGNORECASE | re.MULTILINE)
    text = re.sub(r'^\s*So\s+answer:.*?\n+', '', text, flags=re.IGNORECASE | re.MULTILINE)
    text = _strip_leading_meta_lines(text)
    
    # Try to extract from <response> tags if present
    response_blocks = re.findall(r'<response>(.*?)</response>', text, flags=re.DOTALL | re.IGNORECASE)
    if response_blocks:
        # Prefer the "best" block: non-placeholder, longer, and (if multiple) the last one often contains the actual answer.
        def _score(block: str) -> tuple[int, int, int]:
            b = (block or "").strip()
            is_placeholder = b in {"...", "…"} or "i'm ..." in b.lower() or "i’m ..." in b.lower()
            meta_markers = [
                "also ensure",
                "check for",
                "make sure",
                "now output",
                "disallowed content",
                "it's safe",
                "guardrails",
                "exactly one block",
            ]
            has_meta = any(m in b.lower() for m in meta_markers)
            # Sort by: non-placeholder first, then length
            return (0 if is_placeholder else 1, 0 if has_meta else 1, len(b))

        best = max(response_blocks, key=_score).strip()
        # Clean up any remaining tags
        best = re.sub(r'<[^>]+>', '', best)
        best = re.sub(r'<\|[^|]+\|>', '', best)
        best = _strip_leading_meta_lines(best)
        return best

    # If the model opened a <response> tag but didn't close it, take everything after it.
    open_tag_match = re.search(r'<response>\s*([\s\S]+)$', text, re.IGNORECASE)
    if open_tag_match:
        extracted = open_tag_match.group(1).strip()
        extracted = re.sub(r'<[^>]+>', '', extracted)
        extracted = re.sub(r'<\|[^|]+\|>', '', extracted)
        extracted = _strip_leading_meta_lines(extracted)
        return extracted

    # If the model "drafts" by writing `She might say: "..."`, extract the quoted dialogue.
    drafted_dialogue = re.search(r'(?is)\b(?:she|he|they)\s+might\s+say:\s*["“](.+?)["”]', text)
    if drafted_dialogue:
        extracted = drafted_dialogue.group(1).strip()
        extracted = re.sub(r'<[^>]+>', '', extracted)
        extracted = re.sub(r'<\|[^|]+\|>', '', extracted)
        return extracted.strip()
    
    # If no tags, try to find the first substantial line that looks like dialogue
    lines = text.split('\n')
    for line in lines:
        line = line.strip()
        if line and len(line) > 10:
            # Skip if it looks like reasoning or meta-commentary
            if not any(word in line.lower() for word in ["here are", "reasoning", "let me think", "we need", "the user", "the system", "i need to", "i have to", "i must"]):
                # Check if it starts with dialogue-like content
                if line[0].isupper() or line.startswith(('"', "'")):
                    # Clean up any tags
                    line = re.sub(r'<[^>]+>', '', line)
                    line = re.sub(r'<\|[^|]+\|>', '', line)
                    return line.strip()
    
    # If all else fails, return the text cleaned up
    cleaned = re.sub(r'<[^>]+>', '', text)
    cleaned = re.sub(r'<\|[^|]+\|>', '', cleaned)
    cleaned = cleaned.strip()
    
    # Remove trailing incomplete text
    cleaned = re.sub(r'\?{3,}.*$', '', cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r'Okay let me think.*$', '', cleaned, flags=re.IGNORECASE | re.MULTILINE)
    
    cleaned = _strip_leading_meta_lines(cleaned)
    return cleaned.strip()


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "NPC Dialogue Generation API"}


def _assets_dir() -> str:
    # In Modal, modal_app.py sets NPC_ASSETS_DIR to a mounted Volume path.
    return os.getenv("NPC_ASSETS_DIR", str(pathlib.Path(__file__).parent.parent / "assets"))


def _ensure_assets_dir() -> pathlib.Path:
    p = pathlib.Path(_assets_dir())
    p.mkdir(parents=True, exist_ok=True)
    return p


def _asset_url(asset_id: str, request: Request | None = None) -> str:
    """
    Returns an absolute URL when possible so UIs hosted on a different origin
    (e.g. local Gradio calling a remote Modal backend) can still load assets.

    Priority:
    1) NPC_PUBLIC_BASE_URL or NPC_BACKEND_URL env (explicit override)
    2) request.base_url (derived from incoming HTTP request)
    3) relative /assets/... (fallback)
    """
    base = (os.getenv("NPC_PUBLIC_BASE_URL") or os.getenv("NPC_BACKEND_URL") or "").rstrip("/")
    if base:
        return f"{base}/assets/{asset_id}"
    if request is not None:
        base2 = str(request.base_url).rstrip("/")
        return f"{base2}/assets/{asset_id}"
    return f"/assets/{asset_id}"


def _find_asset_path(asset_id: str) -> pathlib.Path:
    assets = _ensure_assets_dir()
    # Search by known extensions
    for ext in (".png", ".jpg", ".jpeg", ".webp", ".glb"):
        candidate = assets / f"{asset_id}{ext}"
        if candidate.exists():
            return candidate
    raise HTTPException(status_code=404, detail=f"Asset not found: {asset_id}")


def _guess_media_type(path: pathlib.Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".glb":
        return "model/gltf-binary"
    if suffix == ".png":
        return "image/png"
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix == ".webp":
        return "image/webp"
    return "application/octet-stream"


def _download_url_to_bytes(url: str, timeout_s: float = 60.0) -> bytes:
    resp = requests.get(url, timeout=timeout_s)
    resp.raise_for_status()
    return resp.content


def _together_image_generate_to_png_bytes(
    prompt: str,
    width: int,
    height: int,
    reference_images: Optional[List[str]] = None,
) -> bytes:
    """
    Calls Together FLUX.2-pro to generate an image and returns PNG bytes.

    Together reference: https://docs.together.ai/docs/quickstart-flux-2
    """
    # #region agent log
    _dbg_log(
        "H5",
        "app/api.py:_together_image_generate_to_png_bytes:entry",
        "entered together image generate helper",
        data={
            "width": int(width),
            "height": int(height),
            "has_refs": bool(reference_images),
            "refs_count": len(reference_images or []),
            "refs_preview": [(str(u)[:120] + ("…" if len(str(u)) > 120 else "")) for u in (reference_images or [])][:3],
            "together_key_present": bool(os.getenv("TOGETHER_API_KEY")),
        },
        run_id="run_generate_500",
    )
    # #endregion agent log

    api_key = get_together_api_key()
    url = "https://api.together.xyz/v1/images/generations"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": "black-forest-labs/FLUX.2-pro",
        "prompt": prompt,
        "width": int(width),
        "height": int(height),
        # Ask Together for PNG directly; we still normalize to PNG below for safety/consistency.
        "output_format": "png",
    }
    refs = [str(u).strip() for u in (reference_images or []) if str(u).strip()]
    if refs:
        payload["reference_images"] = refs
    # #region agent log
    _dbg_log(
        "H6",
        "app/api.py:_together_image_generate_to_png_bytes:pre_request",
        "sending request to Together",
        data={
            "endpoint": url,
            "payload_keys": sorted(list(payload.keys())),
            "payload_prompt_len": len(prompt or ""),
            "reference_images_count": len(refs),
            "reference_images_contains_localhost": any(("127.0.0.1" in u) or ("localhost" in u) for u in refs),
        },
        run_id="run_generate_500",
    )
    # #endregion agent log

    r = requests.post(url, headers=headers, json=payload, timeout=120)
    try:
        r.raise_for_status()
    except Exception as e:
        # #region agent log
        _dbg_log(
            "H7",
            "app/api.py:_together_image_generate_to_png_bytes:http_error",
            "Together request failed",
            data={
                "status_code": getattr(r, "status_code", None),
                "response_text_preview": (getattr(r, "text", "") or "")[:600],
                "error_type": type(e).__name__,
            },
            run_id="run_generate_500",
        )
        # #endregion agent log
        raise

    data = r.json()
    try:
        image_url = data["data"][0]["url"]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected Together images response: {data}") from e

    raw = _download_url_to_bytes(image_url)
    # Normalize to PNG for consistent downstream processing
    from io import BytesIO
    from PIL import Image

    img = Image.open(BytesIO(raw)).convert("RGBA")
    out = BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


def _validate_reference_images_for_together(reference_images: list[str]) -> list[str]:
    """
    Together expects reference images to be accessible via public URL(s).
    Reject common local-only URLs (localhost/127.0.0.1) early with a clearer error.
    """
    bad: list[str] = []
    for raw in reference_images or []:
        u = (raw or "").strip()
        if not u:
            continue
        if u.startswith("/"):
            bad.append(u)
            continue
        if not (u.startswith("http://") or u.startswith("https://")):
            bad.append(u)
            continue
        host = (_urlparse(u).hostname or "").lower()
        if host in {"127.0.0.1", "localhost"}:
            bad.append(u)
    return bad

@app.post("/image/upload", response_model=ImageUploadResponse)
async def upload_image(request: Request, file: UploadFile = File(...)):
    """
    Upload an image to the backend assets store and return an absolute URL.

    This is mainly to support Together FLUX `reference_images`, which expects URLs.
    """
    _dbg_log("H1", "app/api.py:upload_image:entry", "entered upload_image", data={"filename": getattr(file, "filename", None), "content_type": getattr(file, "content_type", None)})
    if not file:
        raise HTTPException(status_code=400, detail="file is required")

    try:
        raw = await file.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read upload: {e}")

    if not raw:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    # Validate/normalize to PNG.
    try:
        from io import BytesIO
        from PIL import Image

        img = Image.open(BytesIO(raw))
        img = img.convert("RGBA")
        out = BytesIO()
        img.save(out, format="PNG")
        png_bytes = out.getvalue()
    except Exception:
        raise HTTPException(status_code=400, detail="Uploaded file is not a valid image")

    assets = _ensure_assets_dir()
    asset_id = str(uuid.uuid4())
    (assets / f"{asset_id}.png").write_bytes(png_bytes)
    # Mark uploads as temporary so they expire automatically (default 5 minutes).
    expires_at = time.time() + max(0, int(TEMP_UPLOAD_TTL_SECONDS))
    _write_tmp_meta(asset_id=asset_id, expires_at_unix_s=expires_at)
    _maybe_modal_commit_assets_volume()
    resp = ImageUploadResponse(asset_id=asset_id, image_url=_asset_url(asset_id, request=request))
    _dbg_log("H1", "app/api.py:upload_image:exit", "upload_image returning", data={"asset_id": asset_id, "image_url": resp.image_url})
    return resp


@app.get("/assets/{asset_id}")
async def get_asset(asset_id: str):
    _enforce_temp_asset_not_expired(asset_id)
    path = _find_asset_path(asset_id)
    return FileResponse(path, media_type=_guess_media_type(path))


@app.get("/assets/{asset_id}/download")
async def download_asset(asset_id: str):
    _enforce_temp_asset_not_expired(asset_id)
    path = _find_asset_path(asset_id)
    filename = path.name
    media_type = _guess_media_type(path)
    return FileResponse(path, media_type=media_type, filename=filename)


@app.post("/image/generate", response_model=ImageGenerateResponse)
async def generate_images(body: ImageGenerateRequest, request: Request):
    """
    Generate a profile image + full-body image via Together FLUX.2-pro.
    """
    assets = _ensure_assets_dir()
    prompt_base = body.prompt.strip()
    if not prompt_base:
        raise HTTPException(status_code=400, detail="prompt is required")
    _dbg_log(
        "H2",
        "app/api.py:generate_images:entry",
        "entered generate_images",
        data={
            "has_reference_images": bool(body.reference_images),
            "reference_images_count": len(body.reference_images or []),
            "reference_images_contains_localhost": any(
                ("127.0.0.1" in str(u)) or ("localhost" in str(u)) for u in (body.reference_images or [])
            ),
        },
        run_id="run_generate_500",
    )

    profile_prompt = (body.profile_prompt or f"{prompt_base}, portrait profile picture, centered face, clean background").strip()
    full_body_prompt = (body.full_body_prompt or f"{prompt_base}, full body, standing, character sheet, neutral pose").strip()
    reference_images = body.reference_images or []
    bad_refs = _validate_reference_images_for_together(reference_images)
    if bad_refs:
        _dbg_log(
            "H9",
            "app/api.py:generate_images:bad_reference_images",
            "rejecting reference_images that are not publicly reachable",
            data={"bad_refs": bad_refs[:3], "bad_refs_count": len(bad_refs)},
            run_id="run_generate_fix1",
        )
        raise HTTPException(
            status_code=400,
            detail=(
                "reference_images must be publicly reachable URLs. "
                "Together cannot fetch localhost/127.0.0.1 URLs. "
                "Use a public image URL, deploy the backend (Modal), or set NPC_PUBLIC_BASE_URL to a public tunnel/base URL. "
                f"Invalid: {bad_refs[:3]}"
            ),
        )

    try:
        profile_png = _together_image_generate_to_png_bytes(
            prompt=profile_prompt,
            width=body.profile.width,
            height=body.profile.height,
            reference_images=reference_images,
        )
        full_png = _together_image_generate_to_png_bytes(
            prompt=full_body_prompt,
            width=body.full_body.width,
            height=body.full_body.height,
            reference_images=reference_images,
        )
    except HTTPException:
        raise
    except Exception as e:
        _dbg_log(
            "H8",
            "app/api.py:generate_images:exception",
            "generate_images failed (non-HTTPException)",
            data={"error_type": type(e).__name__, "error": str(e)[:800]},
            run_id="run_generate_500",
        )
        raise HTTPException(status_code=500, detail=f"Image generation failed: {e}")

    profile_id = str(uuid.uuid4())
    full_id = str(uuid.uuid4())
    (assets / f"{profile_id}.png").write_bytes(profile_png)
    (assets / f"{full_id}.png").write_bytes(full_png)
    _maybe_modal_commit_assets_volume()

    return ImageGenerateResponse(
        profile_asset_id=profile_id,
        full_body_asset_id=full_id,
        profile_image_url=_asset_url(profile_id, request=request),
        full_body_image_url=_asset_url(full_id, request=request),
    )


@app.post("/image/to-3d", response_model=ImageTo3DResponse)
async def image_to_3d(body: ImageTo3DRequest, request: Request):
    """
    Convert an existing generated image (by asset_id) to GLB using TRELLIS.2 on Modal GPU.

    The FastAPI route stays CPU, but calls the Modal GPU function for the heavy work.
    """
    assets = _ensure_assets_dir()
    image_path = _find_asset_path(body.asset_id)
    if image_path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
        raise HTTPException(status_code=400, detail="asset_id must refer to an image asset")

    image_bytes = image_path.read_bytes()

    try:
        import modal

        modal_app_name = os.getenv("MODAL_APP_NAME", "npc-dialogue-api")
        fn = modal.Function.lookup(modal_app_name, "trellis_image_to_glb")
        glb_bytes: bytes = fn.remote(image_bytes)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TRELLIS GPU conversion failed: {e}")

    glb_id = str(uuid.uuid4())
    (assets / f"{glb_id}.glb").write_bytes(glb_bytes)
    _maybe_modal_commit_assets_volume()

    glb_url = _asset_url(glb_id, request=request)
    return ImageTo3DResponse(
        glb_asset_id=glb_id,
        glb_url=glb_url,
        glb_download_url=f"{glb_url}/download",
    )


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatMessage):
    """
    Generate NPC dialogue response based on user message and conversation history.
    """
    initial_time = time.time()

    if not character_context:
        raise HTTPException(status_code=500, detail="Character context not loaded.")
    
    character_name = character_context["name"]
    
    # Try to get ChromaDB collection, but continue without it if it fails
    collection = None
    results = None
    try:
        client = get_chroma_client()
        collection = client.get_or_create_collection(name=character_name.replace(" ", "_"))
        
        # Query ChromaDB for relevant conversation history
        results = collection.query(
            query_texts=[request.message],
            n_results=5
        )
    except Exception as e:
        print(f"Warning: ChromaDB error (continuing without memory): {e}")
        results = None

    # Filter out polluted results that contain reasoning patterns
    filtered_docs = []
    if results and 'documents' in results and results['documents']:
        for doc_list in results['documents']:
            for doc in doc_list:
                if doc and isinstance(doc, str):
                    # Check for common reasoning patterns
                    skip_patterns = [
                        "The user says",
                        "We need to respond",
                        "Here are my reasoning",
                        "Thus final answer",
                        "[BEGIN FINAL RESPONSE]",
                        "Your output:",
                        "The system expects"
                    ]
                    
                    should_skip = any(pattern in doc for pattern in skip_patterns)
                    
                    # Also skip if it's too long (likely contains reasoning)
                    if len(doc) > 500:
                        should_skip = True
                    
                    if not should_skip:
                        filtered_docs.append(doc)
    
    # Limit to 2 best results
    memory_context = "\n".join(filtered_docs[:2]) if filtered_docs else ""

    # Format environment context
    env_details = environment_context.get("detail", {}) if isinstance(environment_context, dict) else {}
    env_text = f"""
Era: {environment_context.get('era', 'Unknown') if isinstance(environment_context, dict) else 'Unknown'}
Time Period: {environment_context.get('time_period', 'Unknown') if isinstance(environment_context, dict) else 'Unknown'}

Environment: {env_details.get('Environment', 'Not specified')}
Social and Economic: {env_details.get('Social and Economic Aspects', 'Not specified')}
Cultural Norms: {env_details.get('Cultural Norms', 'Not specified')}
Political Climate: {env_details.get('Political Climate', 'Not specified')}
"""
    
    # Format guardrails
    guardrails = environment_context.get("guardrails", {}) if isinstance(environment_context, dict) else {}
    guardrails_text = "\n".join([f"- {key}: {value}" for key, value in guardrails.items()]) if guardrails else ""
    
    # Format character context into a readable description
    if character_context and isinstance(character_context, dict):
        appearance = character_context.get('appearance', {}) or {}
        background = character_context.get('background', {}) or {}
        personalities = character_context.get('personalities', []) or []
        skills = character_context.get('skills', []) or []
        secrets = character_context.get('secrets', []) or []
        
        char_desc = f"""
Name: {character_context.get('name', 'Unknown')}
Age: {character_context.get('age', 'Unknown')}
Gender: {character_context.get('gender', 'Unknown')}

Appearance: {appearance.get('description', 'Not specified')}
Height: {appearance.get('height', 'Unknown')}
Weight: {appearance.get('weight', 'Unknown')}
Hair: {appearance.get('hair', 'Unknown')}
Eyes: {appearance.get('eyes', 'Unknown')}

Personalities: {', '.join(personalities) if personalities else 'Not specified'}

Background:
- Hometown: {background.get('hometown', 'Unknown')}
- Family: {background.get('family', 'Unknown')}
- Motivation: {background.get('motivation', 'Unknown')}

Skills: {', '.join(skills) if skills else 'Not specified'}

Secrets: {', '.join(secrets) if secrets else 'None'}
"""
    else:
        char_desc = "Character information not available."
    
    # Build system message
    system_content = f"""You are {character_name}, a character in this world. You know everything about yourself from your character profile.

YOUR CHARACTER PROFILE:
{char_desc}

ENVIRONMENT CONTEXT:
{env_text}

Guardrails (important rules to follow):
{guardrails_text}

IMPORTANT: You know all the information in your character profile. When asked about yourself, you can share:
- Your name, age, appearance, and background
- Your personalities and how they influence you
- Your skills and abilities
- Your hometown, family, and motivation
- Your secrets (but be careful about when to reveal them)
- Information about Nova Terra and the environment you're from

Your speech pattern is influenced by your personalities: {', '.join(character_context.get('personalities', [])) if character_context and isinstance(character_context, dict) else 'Not specified'}.

CRITICAL INSTRUCTIONS:
- You MUST respond ONLY in first person.
- You MUST respond ONLY as {character_name}. 
- You MUST NOT show any reasoning, thinking steps, explanations, or meta-commentary.
- You MUST NOT write "Here are my reasonings", "Let me think", "I need to", or any similar phrases.
- You MUST NOT explain what you're doing or why.
- You MUST NOT mention guardrails, instructions, or system prompts.
- You MUST speak directly as {character_name} would speak in this situation.
- Your response MUST be ONLY the character's dialogue words, nothing else.
- Respond naturally and in character based on the conversation context.

OUTPUT FORMAT (MANDATORY):
- Output MUST be wrapped in XML tags exactly like:
  <response>...Kaiya's dialogue here...</response>
- Output MUST contain NOTHING outside the <response>...</response> tags.
- Do NOT output placeholders like "..." or "…".
- Output MUST contain exactly ONE <response>...</response> block.

Example (follow this pattern exactly):
Player: Tell me about yourself
Kaiya Starling: <response>I'm Kaiya Starling. I'm 30, and I’ve spent most of my life on the road—following trade routes, storms, and stories across Nova Terra.</response>

{f'Previous conversation context from memory:' + chr(10) + memory_context + chr(10) if memory_context else ''}
"""

    # Build conversation history for prompt
    conversation_history = ""
    if request.history:
        for entry in request.history[-10:]:  # Last 10 exchanges
            if isinstance(entry, list) and len(entry) >= 2:
                conversation_history += f"Player: {entry[0]}\n{character_name}: {entry[1]}\n\n"

    # Build full prompt
    full_prompt = f"""{system_content}

{conversation_history}Player: {request.message}

{character_name}:"""
    
    try:
        # Invoke the Together AI API directly via HTTP
        api_key = get_together_api_key()
        url = "https://api.together.xyz/v1/completions"
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "ServiceNow-AI/Apriel-1.6-15b-Thinker",
            "prompt": full_prompt,
            "max_tokens": 2000,
            "temperature": 0.7,
            # Do NOT stop on </response>; we want to receive it (if generated) and parse it.
            "stop": ["\n\nPlayer:", f"\n\n{character_name}:"],
        }

        response = requests.post(url, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        result = response.json()
        
        # Extract the response content
        raw_output = result["choices"][0]["text"].strip()
        
        # Extract clean character dialogue
        output_content = extract_character_response(raw_output)
        
        # If extraction failed or returned empty, use the raw output cleaned up
        if not output_content or len(output_content) < 5:
            output_content = extract_character_response(raw_output)
            if not output_content or len(output_content) < 5:
                output_content = raw_output.strip()

    except Exception as e:
        error_msg = f"Error generating response: {str(e)}"
        print(f"ERROR: {error_msg}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=error_msg)
    
    # Store clean response in ChromaDB
    if output_content and len(output_content) > 5:
        # Double-check it doesn't contain reasoning patterns
        reasoning_indicators = [
            "The user says",
            "We need to respond",
            "Here are my reasoning",
            "Thus final answer",
            "[BEGIN FINAL RESPONSE]",
            "Your output:",
            "The system expects"
        ]
        
        is_clean = not any(indicator in output_content for indicator in reasoning_indicators)
        
        if is_clean and len(output_content) < 1000 and collection:  # Reasonable dialogue length
            try:
                collection.add(
                    documents=[output_content],
                    metadatas=[{"time": time.time()}],
                    ids=[str(uuid.uuid4())]
                )
            except Exception as e:
                print(f"Warning: Failed to store in ChromaDB: {e}")

    time_taken = time.time() - initial_time

    return ChatResponse(response=output_content, time_taken=time_taken)


@app.post("/clear-history", response_model=ClearHistoryResponse)
async def clear_history():
    """
    Clear all conversation history for the current character from ChromaDB.
    """
    try:
        if not character_context:
            raise HTTPException(status_code=500, detail="Character context not loaded.")
        
        character_name = character_context["name"]
        collection_name = character_name.replace(" ", "_")
        
        # Get or create collection
        try:
            client = get_chroma_client()
            collection = client.get_or_create_collection(name=collection_name)
            
            # Delete all documents in the collection
            all_data = collection.get()
            if all_data and 'ids' in all_data and all_data['ids']:
                collection.delete(ids=all_data['ids'])
                return ClearHistoryResponse(
                    message=f"Cleared conversation history for {character_name}.",
                    success=True
                )
            else:
                return ClearHistoryResponse(
                    message=f"No history found for {character_name}.",
                    success=True
                )
        except Exception as e:
            error_msg = str(e)
            if "v1 API is deprecated" in error_msg or "410 Gone" in error_msg:
                return ClearHistoryResponse(
                    message=f"ChromaDB Cloud API version issue. Please check your ChromaDB Cloud configuration or update ChromaDB client version.",
                    success=False
                )
            return ClearHistoryResponse(
                message=f"Error connecting to ChromaDB: {error_msg}",
                success=False
            )
    except Exception as e:
        return ClearHistoryResponse(
            message=f"Error clearing history: {str(e)}",
            success=False
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

