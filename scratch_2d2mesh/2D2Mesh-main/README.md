# Vision3D AI

> Turn any 2D image into a downloadable 3D model using AI.

Vision3D AI is a production-ready full-stack application that converts 2D images (JPG, PNG, WEBP) into 3D models (GLB/GLTF/OBJ) using AI-powered image-to-3D reconstruction. Users upload images, track generation progress in real time, inspect the model in a browser-based Three.js viewer, and download production-ready files.

---

## Architecture

```
┌──────────────────────────────┐        ┌──────────────────────────────┐
│     Frontend (Vite + React)  │        │   Edge (nginx reverse proxy) │
│  React Router · TypeScript   │  HTTPS │   TLS termination            │
│  Tailwind · Three.js (R3F)   │───────▶│   Rate limiting              │
│  Axios · JWT auth            │   /api │   Security headers           │
└──────────────┬───────────────┘        └──────────────┬───────────────┘
               │ static/CDN                             │
               ▼                                       ▼
┌───────────────────────────────────────────────────────────────────────┐
│                      Backend (FastAPI on GPU host)                     │
│  REST API · Pydantic · JWT (separate refresh key) · slowapi limits     │
│  Motor (async MongoDB) · Background job worker · local/S3 storage      │
│  AI engine: device detection, VRAM monitoring, timing, retries,        │
│             batch, output validation, GLB/GLTF/OBJ/preview exporters   │
├───────────────────────────────┬───────────────────────────────────────┤
│       MongoDB Atlas           │     S3-compatible object storage      │
│  users · projects · jobs      │     GLB/GLTF/OBJ/preview artifacts    │
│  uploads · sessions · usage   │     (AWS S3 · MinIO · Spaces · …)     │
└───────────────────────────────┴───────────────────────────────────────┘
```

**AI adapters** (pluggable, `backend/app/ai/`):

| Adapter | GPU required | Description |
|---------|-------------|-------------|
| `mock` | No | Bas-relief mesh from image luminance. For dev/CI. |
| `stable-fast-3d` | Yes | Stability AI's Stable Fast 3D model |
| `hunyuan3d` | Yes | Tencent's Hunyuan3D-2 model |
| `custom` | Depends | External command / Python subclass (see `custom_model.py`) |

---

## Repository Layout

```
├── Dockerfile.backend          # CPU (api) + GPU (ai) targets
├── Dockerfile.frontend         # Vite build -> nginx static
├── docker-compose.yml          # local development (Mongo + backend + frontend)
├── docker-compose.gpu.yml      # GPU dev overlay (backend on CUDA)
├── docker-compose.prod.yml     # production (GPU backend + nginx TLS edge)
├── nginx.conf                  # production reverse proxy / TLS / rate limiting
├── .env.example                # canonical production env vars
├── backend/                    # FastAPI application
│   ├── app/
│   │   ├── ai/                 # AI engine (models, inference, exporters, …)
│   │   ├── api/routes/         # REST endpoints
│   │   ├── core/               # security (JWT), rate limiting
│   │   ├── db/                 # Motor / MongoDB connection + indexes
│   │   ├── services/           # auth, projects, jobs, storage, …
│   │   ├── workers/            # background job processor
│   │   ├── config.py           # env-driven settings (canonical aliases)
│   │   └── main.py             # FastAPI entrypoint
│   ├── tests/
│   ├── requirements.txt        # core API deps
│   ├── requirements-ai.txt     # heavy AI deps (installed on GPU target)
│   └── .env.example
└── frontend/
    ├── src/                    # React SPA
    ├── package.json
    ├── nginx.conf              # internal static server config
    └── .env.example
```

---

## Prerequisites

- **Docker** + **Docker Compose v2.3+** (`docker compose`)
- **Node.js** 20+ and **npm** (local, non-Docker dev)
- **Python** 3.11+ (local, non-Docker dev)
- **MongoDB Atlas** (or local MongoDB) — production uses Atlas
- **S3-compatible object storage** — production only
- **NVIDIA driver + NVIDIA Container Toolkit** — only for GPU inference

---

## Quick Start (local development)

### Option A — Everything in Docker (recommended)

```bash
# 1. Configuration (canonical vars; works for both Docker and bare-metal)
cp .env.example .env

# 2. Boot MongoDB, backend (hot reload), frontend (hot reload)
docker compose up -d --build

# 3. Check it
docker compose ps
curl http://localhost:8000/api/v1/health
```

- Frontend: `http://localhost:5173`
- Backend API: `http://localhost:8000` · Swagger: `http://localhost:8000/docs`
- MongoDB: `mongodb://localhost:27017` (data in a named volume)

Stop everything: `docker compose down` · Wipe DB too: `docker compose down -v`

### Option B — Bare metal

```bash
# --- Backend ---
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Optional, only if running the real AI models (needs GPU):
pip install -r requirements-ai.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# --- Frontend (second terminal) ---
cd frontend
npm install
npm run dev                        # http://localhost:5173
```

### Database connection

```bash
# Bare metal (local MongoDB)
mongod --dbpath ./data/db

# Atlas: put your connection string in .env
DATABASE_URL=mongodb+srv://user:pass@cluster0.mongodb.net/?retryWrites=true&w=majority
```

Indexes are created automatically at startup (users, projects, jobs, model metadata, usage records, sessions with a TTL index).

---

## GPU Development

```bash
# Host prerequisites
nvidia-smi                                   # driver present?
sudo apt install -y nvidia-container-toolkit # or the Docker Desktop equivalent
sudo systemctl restart docker                # apply

# Build the AI image (torch/diffusers — first build downloads several GB)
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d --build

# Verify the GPU is visible inside the container
docker compose -f docker-compose.yml -f docker-compose.gpu.yml exec backend \
  python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"

# /api/v1/health should report the AI model and (via /models) its device
curl http://localhost:8000/api/v1/health
```

The backend auto-detects CUDA (`AI_DEVICE=auto`) and falls back to CPU when no GPU is present. `AI_MODEL=mock` is the safe default for CPU-only dev.

---

## Production Build & Deployment

### 1. Configure

```bash
cp .env.example .env
# Edit .env: JWT_SECRET, JWT_REFRESH_SECRET, DATABASE_URL (Atlas),
# STORAGE_BUCKET/STORAGE_ENDPOINT/STORAGE_ACCESS_KEY/STORAGE_SECRET_KEY,
# FRONTEND_URL, BACKEND_URL, AI_MODEL.
```

Generate secrets:

```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"   # repeat twice
```

### 2. TLS certificates

```bash
mkdir -p certs
# Testing / self-signed:
openssl req -x509 -nodes -newkey rsa:2048 -days 365 \
  -keyout certs/privkey.pem -out certs/fullchain.pem \
  -subj "/CN=vision3d.example.com"
# Production (Let's Encrypt), run on the host before/after first boot:
sudo apt install -y certbot
sudo certbot certonly --standalone -d vision3d.example.com -d api.vision3d.example.com
cp /etc/letsencrypt/live/vision3d.example.com/fullchain.pem certs/
cp /etc/letsencrypt/live/vision3d.example.com/privkey.pem  certs/
```

### 3. Deploy

```bash
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs -f backend
docker compose -f docker-compose.prod.yml down
```

Production topology: `nginx:443 (TLS + rate limit) → frontend (static SPA)` and `nginx → /api/* → backend (GPU)`. The backend talks to MongoDB Atlas and S3-compatible storage.

**Custom AI model:** mount your weights at `./models` and set `MODEL_PATH=/models/vision3d-custom` plus `CUSTOM_MODEL_COMMAND` (see `backend/app/ai/models/custom_model.py`).

### Health checks & logging

- `/api/v1/health` returns `200` (with `database: degraded`) even if MongoDB is down, so the Docker healthcheck reflects true liveness.
- `LOG_JSON=true` emits structured JSON logs to stdout (aggregate with the log collector of your choice). `docker compose -f docker-compose.prod.yml logs backend` shows them.
- Set `ENVIRONMENT=production` to disable Swagger/Redoc.

### Scaling & operations

- Keep `--workers 1`: the in-process job worker and the loaded AI model are per-process. Scale by adding hosts, not workers.
- Swap the in-memory rate limiter for a Redis-backed one if you run multiple instances (`backend/app/core/ratelimit.py`).
- Back up the `storage_data` volume or rely on S3 for durable artifacts.

---

## Environment Variables

### Backend — canonical (`/backend/.env` or root `.env`, loaded by Docker)

| Variable | Default | Description |
|----------|---------|-------------|
| `ENVIRONMENT` | `development` | `development` \| `staging` \| `production` |
| `JWT_SECRET` | auto | Access-token signing secret (min 32 bytes) |
| `JWT_REFRESH_SECRET` | falls back to `JWT_SECRET` | Separate refresh-token key |
| `DATABASE_URL` | `mongodb://localhost:27017` | MongoDB Atlas/local connection string (alias: `MONGODB_URL`) |
| `MONGODB_DB_NAME` | `vision3d` | Database name |
| `AI_MODEL` | `mock` | `mock` \| `stable-fast-3d` \| `hunyuan3d` \| `custom` |
| `AI_DEVICE` | `auto` | `auto` \| `cpu` \| `cuda` |
| `MODEL_PATH` | — | Mounted custom model path (`{model_path}` template var) |
| `STORAGE_BACKEND` | `local` | `local` \| `s3` |
| `STORAGE_BUCKET` | — | S3 bucket (alias: `S3_BUCKET`) |
| `STORAGE_ENDPOINT` | — | S3-compatible endpoint (alias: `S3_ENDPOINT_URL`) |
| `STORAGE_ACCESS_KEY` | — | Access key (alias: `S3_ACCESS_KEY_ID`) |
| `STORAGE_SECRET_KEY` | — | Secret key (alias: `S3_SECRET_ACCESS_KEY`) |
| `S3_REGION` | `us-east-1` | S3 region |
| `FRONTEND_URL` | — | Public frontend origin; appended to CORS automatically |
| `BACKEND_URL` | `http://localhost:8000` | Public API origin (alias: `PUBLIC_BASE_URL`) |
| `CORS_ORIGINS` | localhost dev origins | Comma-separated allowed origins |
| `MAX_UPLOAD_SIZE_MB` | `10` | Upload size cap |
| `LOG_LEVEL` / `LOG_JSON` | `INFO` / `false` | Logging verbosity / structured JSON |
| `RATE_LIMIT_AUTH` / `RATE_LIMIT_UPLOAD` / `RATE_LIMIT_GENERAL` | `10/minute` / `30/hour` / `240/hour` | slowapi limits |
| `JOB_WORKER_ENABLED` | `true` | Background generation worker |
| `STABLE_FAST_3D_*`, `HUNYUAN3D_*` | — | Model repos, device, dtype |

See `backend/app/config.py` for the full list.

### Frontend (`/frontend/.env`, browser-side — only non-secret values)

| Variable | Default | Description |
|----------|---------|-------------|
| `VITE_API_URL` | `/api/v1` | API base URL (same-origin via proxy) |
| `VITE_APP_NAME` | `Vision3D AI` | App display name |

---

## Command Reference

| Task | Command |
|------|---------|
| Backend startup (dev) | `cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000` |
| Frontend startup (dev) | `cd frontend && npm run dev` |
| Docker startup (dev) | `docker compose up -d --build` |
| GPU development | `docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d --build` |
| Production build + deploy | `docker compose -f docker-compose.prod.yml up -d --build` |
| Backend image build (CPU) | `docker build -f Dockerfile.backend --target api -t vision3d-backend:api .` |
| Backend image build (GPU) | `docker build -f Dockerfile.backend --target ai -t vision3d-backend:ai .` |
| Frontend image build | `docker build -f Dockerfile.frontend -t vision3d-frontend:latest .` |
| Database connection | `DATABASE_URL=mongodb+srv://…` in `.env`; indexes auto-created |
| Tests (backend) | `cd backend && python -m pytest` |
| Lint/format (backend) | `cd backend && ruff check app tests && ruff format app tests` |
| Typecheck/lint (frontend) | `cd frontend && npm run typecheck && npm run lint` |
| Frontend production build (bare) | `cd frontend && npm run build && npm run preview` |

---

## API Endpoints (abridged)

- **Auth:** `POST /api/v1/auth/register` · `POST /api/v1/auth/login` · `POST /api/v1/auth/refresh` · `POST /api/v1/auth/logout`
- **Users:** `GET/PATCH /api/v1/users/me` · `GET /api/v1/users/me/stats` · `POST /api/v1/users/me/password`
- **Projects:** `GET/POST /api/v1/projects` · `GET/PATCH/DELETE /api/v1/projects/:id`
- **Uploads:** `POST /api/v1/uploads`
- **Jobs:** `POST /api/v1/jobs/projects/:id/generate` · `GET /api/v1/jobs/:id` · `POST /api/v1/jobs/:id/retry|cancel`
- **Models:** `GET /api/v1/projects/:id/model` (GLB) · `/model/gltf` · `/model/obj` · `/model/preview`
- **Admin:** `GET /api/v1/admin/stats` · `GET/PATCH /api/v1/admin/users`
- **Ops:** `GET /api/v1/health` · `GET /api/v1/models`

---

## Security

- Passwords hashed with **bcrypt**
- **JWT** access + refresh tokens (HS256), separate refresh secret, token type binding
- Protected routes with ownership validation; revoked sessions (TTL index)
- File type/MIME validation + maximum upload size
- **Rate limiting** — slowapi at the app layer + nginx `limit_req` at the edge
- CORS restricted to configured origins; `FRONTEND_URL` auto-allowed
- TLS termination, HSTS, `X-Frame-Options`, `nosniff`, Referrer-Policy
- Non-root backend user, `no-new-privileges`, secrets only via env vars (never committed)

---

## Testing

```bash
# Backend unit/integration tests
cd backend && python -m pytest

# Frontend typecheck + lint
cd frontend && npm run typecheck && npm run lint
```

---

## License

MIT
