# NPC-Generation

NPC dialogue generation with a **FastAPI backend** (local or deployed on **Modal**) and a **Gradio UI** for chatting.

## Quickstart (local dev: FastAPI + Gradio together)

```bash
pip install -r requirements.txt
python main.py
```

- Running `python main.py` starts:
  - a local FastAPI server (default: `http://127.0.0.1:8000`)
  - the Gradio UI
- In the UI, choose:
  - **Local FastAPI** (uses the local server), or
  - **Modal (deployed)** (paste your `https://<...>.modal.run` URL)

## Environment variables

Required for generation + memory:
- **`TOGETHER_API_KEY`**: Together API key
- **`CHROMA_API_KEY`**, **`CHROMA_TENANT`**, **`CHROMA_DATABASE`**: ChromaDB Cloud credentials

Optional (UI/dev):
- **`NPC_BACKEND_URL`**: default backend URL used by the Gradio **Modal (deployed)** mode
- **`NPC_BACKEND_MODE`**: default UI selection (recommended values: `Local FastAPI` or `Modal (deployed)`)
- **`NPC_START_BACKEND`**: set to `0` to avoid starting FastAPI when running `python main.py`
- **`NPC_BACKEND_HOST`** / **`NPC_BACKEND_PORT`**: override local FastAPI bind (defaults: `127.0.0.1:8000`)

## Deploy backend to Modal

This repo includes a Modal ASGI deployment for **backend only** (`modal_app.py`).

```bash
modal deploy modal_app.py
```

You’ll get a public `.modal.run` URL for the FastAPI app.

Modal secrets expected by `modal_app.py`:
- `together-api-key` (contains `TOGETHER_API_KEY`)
- `chroma-cloud` (contains `CHROMA_API_KEY`, `CHROMA_TENANT`, `CHROMA_DATABASE`)

Example:

```bash
modal secret create together-api-key TOGETHER_API_KEY="..."
modal secret create chroma-cloud CHROMA_API_KEY="..." CHROMA_TENANT="..." CHROMA_DATABASE="..."
```

## Image generation + Image→3D (new)

This backend also exposes:

- `POST /image/generate`: generates **profile + full-body** images using Together FLUX.2-pro ([Together FLUX.2 docs](https://docs.together.ai/docs/quickstart-flux-2))
- `POST /image/upload`: uploads a local reference image to the backend and returns an `/assets/...` URL (useful for FLUX `reference_images`)
- `GET /image/presets`: list saved image prompt presets (stored under the backend assets dir; on Modal this is the assets Volume)
- `PUT /image/presets`: upsert a named prompt preset `{name, kind: "character"|"environment", prompt}`
- `DELETE /image/presets/{name}`: delete a prompt preset
- `POST /image/to-3d`: converts a generated image into a **GLB** using Microsoft TRELLIS.2 on a Modal GPU (only this route uses GPU; reference app: [HF Space](https://huggingface.co/spaces/microsoft/TRELLIS.2), [files](https://huggingface.co/spaces/microsoft/TRELLIS.2/tree/main))
- `GET /assets/{asset_id}` and `GET /assets/{asset_id}/download`: serves PNG/GLB artifacts

### Saved prompt presets (Gradio UI)

In `main.py` → **Character Image Generation**:
- Select a saved **Character JSON** and **Environment JSON**
- Optionally select saved **Character/Environment prompt presets**
- Click **Build prompt from selections →**

Preset management is available when Backend is set to **Modal (deployed)** (presets are stored on the Modal assets Volume).

### Local demo UI

Run the demo locally (it calls the backend over HTTP):

```bash
python image3d_demo.py
```

Set the backend URL via env:

```bash
export NPC_BACKEND_URL="https://<your-app>.modal.run"
```

## API (FastAPI)

- `GET /health`
- `POST /chat` body: `{ "message": "...", "history": [[user, npc], ...] }`
- `POST /clear-history`

## Repo layout (high level)

- `app/api.py`: FastAPI backend (single source of truth for generation)
- `main.py`: Gradio UI + local FastAPI runner (dev convenience)
- `modal_app.py`: Modal deployment (backend only)
- `JSONData/`: world + character JSON inputs


