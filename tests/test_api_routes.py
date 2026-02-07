import importlib
import json
import sys
import types
import uuid
from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

# Ensure the repo root is importable (so `import app.api` works even if pytest isn't
# executed with the repo root on sys.path).
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _png_bytes(color=(255, 0, 0, 255), size=(32, 32)) -> bytes:
    img = Image.new("RGBA", size, color)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture()
def api_module(monkeypatch, tmp_path):
    # Ensure any route that needs Together key doesn't fail early.
    monkeypatch.setenv("TOGETHER_API_KEY", "test-key")
    # Isolate asset writes (uploads/generation) to a temp directory.
    monkeypatch.setenv("NPC_ASSETS_DIR", str(tmp_path / "assets"))
    # Default TTL for upload tests; can be overridden per-test.
    monkeypatch.setenv("NPC_TEMP_UPLOAD_TTL_SECONDS", "300")

    # ChromaDB imports can pull in heavy numeric/native deps; in some environments this
    # can segfault. For route-level tests, stub chromadb so `import app.api` is safe.
    class _DummyChromaClient:
        def __init__(self, *args, **kwargs):
            pass

        def get_or_create_collection(self, name: str):
            raise RuntimeError("chromadb is stubbed in tests")

    dummy_chromadb = types.SimpleNamespace(CloudClient=_DummyChromaClient, PersistentClient=_DummyChromaClient)
    sys.modules["chromadb"] = dummy_chromadb

    # app/api.py calls `load_dotenv()` at import time. In this sandbox, reading the
    # repo `.env` may be disallowed (often gitignored), causing PermissionError.
    # Stub dotenv so imports are deterministic.
    sys.modules["dotenv"] = types.SimpleNamespace(load_dotenv=lambda *args, **kwargs: False)

    import app.api as api

    importlib.reload(api)
    return api


@pytest.fixture()
def client(api_module):
    return TestClient(api_module.app)


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body.get("status") == "healthy"


def test_image_presets_crud(client):
    # Upsert
    r = client.put("/image/presets", json={"name": "MyCharPreset", "kind": "character", "prompt": "anime style"})
    assert r.status_code == 200
    assert r.json().get("ok") is True

    # List
    r = client.get("/image/presets")
    assert r.status_code == 200
    presets = r.json().get("presets", [])
    assert any(p.get("name") == "MyCharPreset" and p.get("kind") == "character" for p in presets)

    # Delete
    r = client.delete("/image/presets/MyCharPreset")
    assert r.status_code == 200
    assert r.json().get("ok") is True


def test_config_list_routes(client):
    r = client.get("/config/characters")
    assert r.status_code == 200
    chars = r.json().get("files", [])
    assert isinstance(chars, list)
    assert any(fn.lower().endswith(".json") for fn in chars)

    r = client.get("/config/environments")
    assert r.status_code == 200
    envs = r.json().get("files", [])
    assert isinstance(envs, list)
    assert any(fn.lower().endswith(".json") for fn in envs)


def test_config_load_routes(client):
    r = client.post("/config/character/load", json={"filename": "KaiyaStarling.json"})
    assert r.status_code == 200
    body = r.json()
    assert body.get("ok") is True
    assert isinstance(body.get("character"), dict)

    r = client.post("/config/environment/load", json={"filename": "environment.json"})
    assert r.status_code == 200
    body = r.json()
    assert body.get("ok") is True
    assert isinstance(body.get("environment"), dict)


def test_config_save_routes_roundtrip(client):
    # Save files into JSONData and clean up afterwards.
    repo_root = Path(__file__).resolve().parents[1]
    json_dir = repo_root / "JSONData"

    char_fn = f"pytest_character_{uuid.uuid4().hex}.json"
    env_fn = f"pytest_environment_{uuid.uuid4().hex}.json"
    char_path = json_dir / char_fn
    env_path = json_dir / env_fn

    character_obj = {
        "name": "PyTest Char",
        "age": 21,
        "gender": "N/A",
        "personalities": ["Curious"],
        "appearance": {"description": "test", "height": "0", "weight": "0", "hair": "none", "eyes": "none"},
        "background": {"hometown": "test", "family": "test", "motivation": "test"},
        "skills": ["testing"],
        "secrets": ["none"],
    }
    env_obj = {
        "era": "Test Era",
        "time_period": "Now",
        "detail": {
            "Environment": "A blank room",
            "Social and Economic Aspects": "",
            "Livelihood": "",
            "Social Hierarchy": "",
            "Cultural Norms": "",
            "Natural Environment": "",
            "Political Climate": "",
        },
        "guardrails": {
            "AI Safety": "",
            "Undesirable Topics": "",
            "Harmful Content": "",
            "Sensitive Information": "",
            "Inappropriate Content": "",
            "Logical Consistency": "",
        },
    }

    try:
        r = client.post("/config/character/save", json={"filename": char_fn, "character": character_obj})
        assert r.status_code == 200
        assert r.json().get("ok") is True
        assert char_path.exists()

        r = client.post("/config/environment/save", json={"filename": env_fn, "environment": env_obj})
        assert r.status_code == 200
        assert r.json().get("ok") is True
        assert env_path.exists()
    finally:
        if char_path.exists():
            char_path.unlink()
        if env_path.exists():
            env_path.unlink()


def test_image_upload_and_asset_serving(client, api_module, monkeypatch):
    # Upload
    r = client.post("/image/upload", files={"file": ("ref.png", _png_bytes(), "image/png")})
    assert r.status_code == 200
    body = r.json()
    asset_id = body["asset_id"]

    # Fetch
    r = client.get(f"/assets/{asset_id}")
    assert r.status_code == 200
    assert r.headers.get("content-type", "").startswith("image/")
    assert len(r.content) > 10

    # Download endpoint
    r = client.get(f"/assets/{asset_id}/download")
    assert r.status_code == 200
    assert len(r.content) > 10


def test_temp_upload_expiry_enforced(client, api_module, monkeypatch):
    # Upload
    r = client.post("/image/upload", files={"file": ("ref.png", _png_bytes(), "image/png")})
    assert r.status_code == 200
    asset_id = r.json()["asset_id"]

    # Force-expire by editing the marker file in the assets dir.
    assets_dir = Path(api_module._assets_dir())
    meta_path = assets_dir / f"{asset_id}.tmp.json"
    assert meta_path.exists()
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["expires_at"] = 0
    meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")

    # Now asset should 404 and be deleted.
    r = client.get(f"/assets/{asset_id}")
    assert r.status_code == 404
    assert not (assets_dir / f"{asset_id}.png").exists()


def test_image_generate_rejects_localhost_reference(client):
    payload = {
        "prompt": "test",
        "reference_images": ["http://127.0.0.1:1234/x.png"],
        "profile": {"width": 64, "height": 64},
        "full_body": {"width": 64, "height": 64},
    }
    r = client.post("/image/generate", json=payload)
    assert r.status_code == 400


def test_image_generate_success(client, api_module, monkeypatch):
    png = _png_bytes()

    def fake_generate(*, prompt, width, height, reference_images=None):
        return png

    monkeypatch.setattr(api_module, "_together_image_generate_to_png_bytes", fake_generate)

    payload = {"prompt": "A knight", "profile": {"width": 64, "height": 64}, "full_body": {"width": 64, "height": 64}}
    r = client.post("/image/generate", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["profile_asset_id"]
    assert body["full_body_asset_id"]

    # Assets should be served.
    r = client.get(f"/assets/{body['profile_asset_id']}")
    assert r.status_code == 200
    r = client.get(f"/assets/{body['full_body_asset_id']}")
    assert r.status_code == 200


def test_image_to_3d_success(client, api_module, monkeypatch):
    # Seed an image asset so /image/to-3d can find it.
    assets = Path(api_module._assets_dir())
    assets.mkdir(parents=True, exist_ok=True)
    asset_id = uuid.uuid4().hex
    (assets / f"{asset_id}.png").write_bytes(_png_bytes())

    glb_bytes = b"glb-binary-placeholder"

    class DummyRemoteFn:
        def remote(self, image_bytes: bytes) -> bytes:
            assert image_bytes
            return glb_bytes

    class DummyFunction:
        @staticmethod
        def lookup(app_name: str, fn_name: str):
            assert fn_name == "trellis_image_to_glb"
            return DummyRemoteFn()

    dummy_modal = types.SimpleNamespace(Function=DummyFunction)
    monkeypatch.setitem(sys.modules, "modal", dummy_modal)

    r = client.post("/image/to-3d", json={"asset_id": asset_id})
    assert r.status_code == 200
    body = r.json()
    glb_id = body["glb_asset_id"]

    r = client.get(f"/assets/{glb_id}")
    assert r.status_code == 200
    assert r.headers.get("content-type", "").startswith("model/")
    assert r.content == glb_bytes


def test_chat_route_success(client, api_module, monkeypatch):
    # Avoid hitting Chroma in tests.
    def raise_chroma():
        raise RuntimeError("no chroma in tests")

    monkeypatch.setattr(api_module, "get_chroma_client", raise_chroma)

    class DummyResp:
        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"text": "<response>Hello there.</response>"}]}

    def fake_post(url, headers=None, json=None, timeout=None):
        return DummyResp()

    monkeypatch.setattr(api_module.requests, "post", fake_post)

    r = client.post("/chat", json={"message": "hi", "history": []})
    assert r.status_code == 200
    body = r.json()
    assert body["response"] == "Hello there."


def test_clear_history_route_success(client, api_module, monkeypatch):
    class DummyCollection:
        def __init__(self):
            self.deleted_ids = []

        def get(self):
            return {"ids": ["a", "b"]}

        def delete(self, ids):
            self.deleted_ids.extend(ids)

    class DummyClient:
        def __init__(self):
            self.col = DummyCollection()

        def get_or_create_collection(self, name: str):
            return self.col

    monkeypatch.setattr(api_module, "get_chroma_client", lambda: DummyClient())

    r = client.post("/clear-history")
    assert r.status_code == 200
    body = r.json()
    assert "Cleared" in body.get("message", "") or body.get("success") is True


