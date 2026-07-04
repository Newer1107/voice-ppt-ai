# Application Server — Production Setup

> **Target:** Machine A (web server)  
> **Stack:** FastAPI + Next.js + PostgreSQL + Redis + Celery  
> **OS:** Ubuntu 24.04 LTS (or any systemd-based Linux)  
> **User:** Deploying as a non-root user with sudo

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Directory Layout](#2-directory-layout)
3. [System Dependencies](#3-system-dependencies)
4. [PostgreSQL](#4-postgresql)
5. [Redis](#5-redis)
6. [Backend (FastAPI)](#6-backend-fastapi)
7. [Frontend (Next.js)](#7-frontend-nextjs)
8. [Nginx](#8-nginx)
9. [Systemd Services](#9-systemd-services)
10. [Celery Worker](#10-celery-worker)
11. [Environment Variables](#11-environment-variables)
12. [Deployment Script](#12-deployment-script)
13. [Health Checks](#13-health-checks)
14. [Troubleshooting](#14-troubleshooting)

---

## 1. Prerequisites

```bash
# You need:
sudo user
git
curl
systemd

# Verify:
whoami
sudo -v
git --version
systemctl --version
```

---

## 2. Directory Layout

```
/opt/lecture-narrator/              # Application root
├── backend/                        # FastAPI app
│   ├── main.py
│   ├── src/
│   ├── requirements.txt
│   ├── alembic/
│   └── .env                        # Production secrets
├── frontend/                       # Next.js build output
│   ├── .next/
│   ├── public/
│   ├── package.json
│   └── .env.local                  # NEXT_PUBLIC_API_URL
├── data/                           # Runtime data (non-root writable)
│   ├── storage/
│   ├── voice_embeddings/
│   └── cache/
├── .env                            # Shared env vars
├── venv/                           # Python virtual environment
└── logs/                           # Application logs
```

---

## 3. System Dependencies

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Python 3.12
sudo apt install -y software-properties-common
sudo add-apt-repository -y ppa:deadsnakes/ppa
sudo apt install -y python3.12 python3.12-venv python3.12-dev

# Node.js 20
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs

# FFmpeg (for audio extraction)
sudo apt install -y ffmpeg

# Build tools (for Python packages)
sudo apt install -y build-essential libssl-dev libffi-dev

# Nginx
sudo apt install -y nginx

# Verify
python3.12 --version
node --version
ffmpeg -version
nginx -v
```

---

## 4. PostgreSQL

```bash
# Install
sudo apt install -y postgresql postgresql-contrib

# Start on boot
sudo systemctl enable postgresql
sudo systemctl start postgresql

# Create database and user
sudo -u postgres psql <<EOF
CREATE DATABASE lecture_narrator;
CREATE USER app_user WITH PASSWORD '$(openssl rand -base64 32)';
GRANT ALL PRIVILEGES ON DATABASE lecture_narrator TO app_user;
\c lecture_narrator
GRANT ALL ON SCHEMA public TO app_user;
EOF

# Save the generated password — you'll need it for .env
```

---

## 5. Redis

```bash
# Install
sudo apt install -y redis-server

# Configure password
sudo sed -i 's/# requirepass foobared/requirepass '"$(openssl rand -base64 32)"'/' /etc/redis/redis.conf

# Disable protected mode for local-only access
sudo sed -i 's/bind 127.0.0.1 ::1/bind 127.0.0.1/' /etc/redis/redis.conf

# Start on boot
sudo systemctl enable redis-server
sudo systemctl start redis-server

# Save the generated password — you'll need it for .env
```

---

## 6. Backend (FastAPI)

### 6.1 Deploy the code

```bash
# Create application user
sudo useradd -r -s /bin/false -d /opt/lecture-narrator app
sudo mkdir -p /opt/lecture-narrator
sudo chown app:app /opt/lecture-narrator

# Clone (or copy) the repository
sudo -u app git clone <your-repo-url> /opt/lecture-narrator/repo
# OR copy from local
sudo -u app cp -r /path/to/your/code/* /opt/lecture-narrator/repo/

# Create runtime directories
sudo -u app mkdir -p /opt/lecture-narrator/{data/storage,data/voice_embeddings,data/cache,logs}

cd /opt/lecture-narrator/repo/backend
```

### 6.2 Python virtual environment

```bash
cd /opt/lecture-narrator/repo/backend
python3.12 -m venv /opt/lecture-narrator/venv
source /opt/lecture-narrator/venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install gunicorn  # Production ASGI server alternative

# Deactivate when done
deactivate
```

### 6.3 Environment file

Create `/opt/lecture-narrator/.env`:

```bash
sudo -u app tee /opt/lecture-narrator/.env << 'EOF'
# Application
APP_NAME=AI Lecture Narrator
APP_VERSION=1.0.0
ENVIRONMENT=production
DEBUG=false
SECRET_KEY=<run: openssl rand -hex 32>

# Database — use the password from step 4
DATABASE_URL=postgresql+asyncpg://app_user:<password>@localhost:5432/lecture_narrator
DB_POOL_SIZE=10
DB_MAX_OVERFLOW=20

# Redis — use the password from step 5
REDIS_URL=redis://:<password>@localhost:6379/0
REDIS_RESULT_URL=redis://:<password>@localhost:6379/1

# JWT
JWT_SECRET_KEY=<run: openssl rand -hex 32>
JWT_ACCESS_EXPIRE_MINUTES=60
JWT_REFRESH_EXPIRE_DAYS=30

# AI GPU Server — point this at your Machine B
AI_SERVICE_URL=http://<gpu-server-ip>:8001
AI_API_KEY=<generate-a-shared-secret>

# Storage — project-relative paths (no root needed)
STORAGE_BACKEND=local
STORAGE_ROOT=data/storage

# CORS — your frontend domain(s)
CORS_ORIGINS=["https://lectures.yourdomain.com"]

# Rate limiting
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_WINDOW_SECONDS=60

# Upload limits
MAX_VIDEO_SIZE_BYTES=2147483648
MAX_AUDIO_SIZE_BYTES=524288000
MAX_PPTX_SIZE_BYTES=209715200
EOF

# Set permissions
sudo chmod 600 /opt/lecture-narrator/.env
```

### 6.4 Symlink .env into the backend directory

```bash
sudo -u app ln -sf /opt/lecture-narrator/.env /opt/lecture-narrator/repo/backend/.env
```

### 6.5 Run database migrations

```bash
cd /opt/lecture-narrator/repo/backend
sudo -u app /opt/lecture-narrator/venv/bin/alembic upgrade head
```

### 6.6 Verify the backend starts

```bash
sudo -u app /opt/lecture-narrator/venv/bin/uvicorn main:app \
  --host 127.0.0.1 \
  --port 8000

# In another terminal, test it:
curl http://127.0.0.1:8000/api/v1/health

# Press Ctrl+C to stop (we'll use systemd in production)
```

---

## 7. Frontend (Next.js)

```bash
cd /opt/lecture-narrator/repo/frontend

# Install dependencies
sudo -u app npm ci

# Create .env.local
sudo -u app tee /opt/lecture-narrator/repo/frontend/.env.local << 'EOF'
NEXT_PUBLIC_API_URL=https://lectures.yourdomain.com/api
EOF

# Build
sudo -u app npm run build
```

The build output goes to `frontend/.next/`. The frontend will be served by its own Node process (via systemd), proxied through Nginx.

---

## 8. Nginx

### 8.1 Create site config

```bash
sudo tee /etc/nginx/sites-available/lecture-narrator << 'EOF'
server {
    listen 80;
    server_name lectures.yourdomain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name lectures.yourdomain.com;

    # SSL — use Certbot or your own certificates
    ssl_certificate /etc/ssl/certs/lecture-narrator.crt;
    ssl_certificate_key /etc/ssl/private/lecture-narrator.key;

    # Security headers
    add_header Strict-Transport-Security "max-age=63072000" always;
    add_header X-Content-Type-Options nosniff;
    add_header X-Frame-Options DENY;
    add_header X-XSS-Protection "1; mode=block";

    # Request size limits
    client_max_body_size 10m;

    # ── Frontend ──────────────────────────────────────────────
    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # ── API ───────────────────────────────────────────────────
    location /api/ {
        proxy_pass http://127.0.0.1:8000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_buffering off;
    }

    # ── WebSocket ─────────────────────────────────────────────
    location /ws/ {
        proxy_pass http://127.0.0.1:8000/ws/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 86400s;
    }

    # ── Large uploads (lecture files) ─────────────────────────
    location /api/v1/lectures/upload {
        client_max_body_size 2048m;
        proxy_pass http://127.0.0.1:8000;
        proxy_read_timeout 300s;
    }
}
EOF
```

### 8.2 Enable the site

```bash
# Remove default site
sudo rm /etc/nginx/sites-enabled/default

# Enable our site
sudo ln -sf /etc/nginx/sites-available/lecture-narrator /etc/nginx/sites-enabled/

# Test config
sudo nginx -t

# Restart
sudo systemctl restart nginx
```

### 8.3 SSL with Certbot (recommended)

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d lectures.yourdomain.com
```

---

## 9. Systemd Services

### 9.1 Backend (FastAPI)

```bash
sudo tee /etc/systemd/system/lecture-backend.service << 'EOF'
[Unit]
Description=AI Lecture Narrator — Backend API
After=network.target postgresql.service redis-server.service
Wants=postgresql.service redis-server.service

[Service]
Type=simple
User=app
Group=app
WorkingDirectory=/opt/lecture-narrator/repo/backend
EnvironmentFile=/opt/lecture-narrator/.env
ExecStart=/opt/lecture-narrator/venv/bin/uvicorn main:app \
  --host 127.0.0.1 \
  --port 8000 \
  --workers 4 \
  --limit-max-requests 10000
Restart=always
RestartSec=5
StandardOutput=append:/opt/lecture-narrator/logs/backend.log
StandardError=append:/opt/lecture-narrator/logs/backend-error.log

[Install]
WantedBy=multi-user.target
EOF
```

### 9.2 Frontend (Next.js)

```bash
sudo tee /etc/systemd/system/lecture-frontend.service << 'EOF'
[Unit]
Description=AI Lecture Narrator — Frontend
After=network.target

[Service]
Type=simple
User=app
Group=app
WorkingDirectory=/opt/lecture-narrator/repo/frontend
ExecStart=/usr/bin/node /opt/lecture-narrator/repo/frontend/node_modules/.bin/next start \
  --port 3000
Restart=always
RestartSec=5
StandardOutput=append:/opt/lecture-narrator/logs/frontend.log
StandardError=append:/opt/lecture-narrator/logs/frontend-error.log
Environment=NODE_ENV=production
Environment=NEXT_PUBLIC_API_URL=https://lectures.yourdomain.com/api

[Install]
WantedBy=multi-user.target
EOF
```

### 9.3 Celery Worker

```bash
sudo tee /etc/systemd/system/lecture-celery-worker.service << 'EOF'
[Unit]
Description=AI Lecture Narrator — Celery Worker
After=network.target redis-server.service
Wants=redis-server.service

[Service]
Type=simple
User=app
Group=app
WorkingDirectory=/opt/lecture-narrator/repo/backend
EnvironmentFile=/opt/lecture-narrator/.env
ExecStart=/opt/lecture-narrator/venv/bin/celery -A src.worker.celery_app worker \
  -Q default,audio,transcription,llm,tts,pptx,priority_high \
  --concurrency=2 \
  -l INFO
Restart=always
RestartSec=10
StandardOutput=append:/opt/lecture-narrator/logs/celery-worker.log
StandardError=append:/opt/lecture-narrator/logs/celery-worker-error.log

[Install]
WantedBy=multi-user.target
EOF
```

### 9.4 Celery Beat (optional — for scheduled tasks)

```bash
sudo tee /etc/systemd/system/lecture-celery-beat.service << 'EOF'
[Unit]
Description=AI Lecture Narrator — Celery Beat
After=network.target redis-server.service
Wants=redis-server.service

[Service]
Type=simple
User=app
Group=app
WorkingDirectory=/opt/lecture-narrator/repo/backend
EnvironmentFile=/opt/lecture-narrator/.env
ExecStart=/opt/lecture-narrator/venv/bin/celery -A src.worker.celery_app beat -l INFO
Restart=always
RestartSec=10
StandardOutput=append:/opt/lecture-narrator/logs/celery-beat.log
StandardError=append:/opt/lecture-narrator/logs/celery-beat-error.log

[Install]
WantedBy=multi-user.target
EOF
```

### 9.5 Enable and start all services

```bash
sudo systemctl daemon-reload

# Enable on boot
sudo systemctl enable lecture-backend
sudo systemctl enable lecture-frontend
sudo systemctl enable lecture-celery-worker
# sudo systemctl enable lecture-celery-beat  # only if you need scheduled tasks

# Start
sudo systemctl start lecture-backend
sudo systemctl start lecture-frontend
sudo systemctl start lecture-celery-worker

# Check status
sudo systemctl status lecture-backend
sudo systemctl status lecture-frontend
sudo systemctl status lecture-celery-worker
```

### 9.6 Useful service commands

```bash
# View logs
sudo journalctl -u lecture-backend -f
sudo journalctl -u lecture-frontend -f
sudo journalctl -u lecture-celery-worker -f

# Restart after deploy
sudo systemctl restart lecture-backend
sudo systemctl restart lecture-frontend
sudo systemctl restart lecture-celery-worker

# Stop
sudo systemctl stop lecture-backend
sudo systemctl stop lecture-frontend
```

---

## 10. Celery Worker

The Celery worker processes the 8-stage pipeline in the background. It must be running for any lecture processing to happen.

### Queue configuration

The worker listens on 7 queues:

| Queue | Purpose | Concurrency |
|-------|---------|-------------|
| `default` | General tasks | 2 |
| `audio` | Audio extraction (ffmpeg, CPU) | 2 |
| `transcription` | GPU transcription calls | 1 |
| `llm` | LLM alignment + narration | 1 |
| `tts` | TTS audio generation | 1 |
| `pptx` | PPTX parsing + embedding | 2 |
| `priority_high` | User-facing sync tasks | 1 |

### Verify the worker is processing

```bash
# Check worker status
sudo journalctl -u lecture-celery-worker --since "5 minutes ago"

# Check Redis queue depth
redis-cli -a <password> LLEN celery

# Inspect active tasks
sudo -u app /opt/lecture-narrator/venv/bin/celery -A src.worker.celery_app inspect active
```

---

## 11. Environment Variables

### Production checklist

| Variable | Required | How to generate |
|----------|----------|-----------------|
| `SECRET_KEY` | **Yes** | `openssl rand -hex 32` |
| `DATABASE_URL` | **Yes** | From PostgreSQL setup (step 4) |
| `JWT_SECRET_KEY` | **Yes** | `openssl rand -hex 32` |
| `AI_SERVICE_URL` | **Yes** | `http://<gpu-server-ip>:8001` |
| `AI_API_KEY` | **Yes** | `openssl rand -base64 32` |
| `DB_PASSWORD` | **Yes** | From PostgreSQL setup |
| `REDIS_PASSWORD` | **Yes** | From Redis setup |
| `CORS_ORIGINS` | **Yes** | `["https://yourdomain.com"]` |

### Full production `.env`

```bash
# ── Application ────────────────────────────────────
APP_NAME=AI Lecture Narrator
APP_VERSION=1.0.0
ENVIRONMENT=production
DEBUG=false
SECRET_KEY=<openssl rand -hex 32>

# ── Database ───────────────────────────────────────
DATABASE_URL=postgresql+asyncpg://app_user:<pass>@localhost:5432/lecture_narrator
DB_PASSWORD=<from-step-4>
DB_POOL_SIZE=10
DB_MAX_OVERFLOW=20

# ── Redis ──────────────────────────────────────────
REDIS_URL=redis://:<pass>@localhost:6379/0
REDIS_RESULT_URL=redis://:<pass>@localhost:6379/1
REDIS_PASSWORD=<from-step-5>

# ── JWT ────────────────────────────────────────────
JWT_SECRET_KEY=<openssl rand -hex 32>
JWT_ACCESS_EXPIRE_MINUTES=60
JWT_REFRESH_EXPIRE_DAYS=30

# ── AI GPU Server ──────────────────────────────────
AI_SERVICE_URL=http://10.0.0.100:8001
AI_API_KEY=<shared-secret-with-gpu-server>

# ── Storage ────────────────────────────────────────
STORAGE_BACKEND=local
STORAGE_ROOT=data/storage

# ── Upload Limits ──────────────────────────────────
MAX_VIDEO_SIZE_BYTES=2147483648
MAX_AUDIO_SIZE_BYTES=524288000
MAX_PPTX_SIZE_BYTES=209715200

# ── Rate Limiting ──────────────────────────────────
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_WINDOW_SECONDS=60

# ── CORS ───────────────────────────────────────────
CORS_ORIGINS=["https://lectures.yourdomain.com"]
```

---

## 12. Deployment Script

Save this as `/opt/lecture-narrator/deploy.sh` for zero-downtime deploys:

```bash
#!/usr/bin/env bash
set -euo pipefail

APP_DIR=/opt/lecture-narrator
REPO_DIR=$APP_DIR/repo
BACKEND_DIR=$REPO_DIR/backend
FRONTEND_DIR=$REPO_DIR/frontend
VENV=$APP_DIR/venv
LOG=$APP_DIR/logs/deploy.log

echo "[$(date)] Starting deploy..." | tee -a $LOG

cd $REPO_DIR

# Pull latest code
echo "  Pulling code..." | tee -a $LOG
git pull origin main

# Install backend deps
echo "  Installing backend deps..." | tee -a $LOG
$VENV/bin/pip install -r $BACKEND_DIR/requirements.txt --quiet

# Run migrations
echo "  Running migrations..." | tee -a $LOG
$VENV/bin/alembic -c $BACKEND_DIR/alembic.ini upgrade head

# Build frontend
echo "  Building frontend..." | tee -a $LOG
cd $FRONTEND_DIR
npm ci --quiet
npm run build

# Restart services
echo "  Restarting services..." | tee -a $LOG
sudo systemctl restart lecture-backend
sudo systemctl restart lecture-frontend
sudo systemctl restart lecture-celery-worker

# Health check
echo "  Health check..." | tee -a $LOG
sleep 5
curl -sf http://127.0.0.1:8000/api/v1/health || {
    echo "  FAILED: Backend not responding" | tee -a $LOG
    exit 1
}

echo "[$(date)] Deploy complete." | tee -a $LOG
```

```bash
sudo chmod +x /opt/lecture-narrator/deploy.sh
sudo chown app:app /opt/lecture-narrator/deploy.sh
```

---

## 13. Health Checks

### Manual checks

```bash
# Backend API
curl http://127.0.0.1:8000/api/v1/health

# Frontend
curl -I http://127.0.0.1:3000

# Nginx (external)
curl -I https://lectures.yourdomain.com

# PostgreSQL
pg_isready -U app_user -d lecture_narrator

# Redis
redis-cli -a <password> ping

# Celery worker
sudo -u app /opt/lecture-narrator/venv/bin/celery -A src.worker.celery_app status
```

### Monitoring endpoints

| Endpoint | What it checks |
|----------|---------------|
| `GET /api/v1/health` | Backend, PostgreSQL, Redis connectivity |

Add these to your monitoring system (Prometheus, Datadog, UptimeRobot, etc.).

---

## 14. Troubleshooting

### Backend won't start

```bash
# Check logs
sudo journalctl -u lecture-backend --since "10 minutes ago" --no-pager

# Common issues:
# 1. Database not running -> sudo systemctl status postgresql
# 2. Redis not running    -> sudo systemctl status redis-server
# 3. Missing .env file    -> check /opt/lecture-narrator/.env exists
# 4. Port already in use  -> sudo ss -tlnp | grep 8000
```

### Frontend won't start

```bash
# Check logs
sudo journalctl -u lecture-frontend --since "10 minutes ago" --no-pager

# Common issues:
# 1. Missing build -> cd /opt/lecture-narrator/repo/frontend && npm run build
# 2. Port conflict -> check next start port in service file
```

### Celery worker not processing tasks

```bash
# Check logs
sudo journalctl -u lecture-celery-worker --since "10 minutes ago" --no-pager

# Check Redis connection
redis-cli -a <password> ping

# Inspect worker
sudo -u app /opt/lecture-narrator/venv/bin/celery -A src.worker.celery_app inspect stats

# Check queue depth
redis-cli -a <password> LLEN celery
```

### File upload fails

```bash
# Check disk space
df -h /opt/lecture-narrator/data/storage

# Check directory permissions
ls -la /opt/lecture-narrator/data/storage

# Nginx upload size limit
grep client_max_body_size /etc/nginx/sites-available/lecture-narrator
```

### Pipeline stage fails

```bash
# Check lecture status via API
curl -H "Authorization: Bearer <token>" \
  http://127.0.0.1:8000/api/v1/lectures/<id>/status

# Check Celery logs
sudo journalctl -u lecture-celery-worker --since "30 minutes ago" --no-pager

# Check if GPU server is reachable
curl http://<gpu-server-ip>:8001/ai/v1/health
```
