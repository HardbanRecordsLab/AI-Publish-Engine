# Technical Guide — AI Publish Engine

## Deployment

The application runs as a **Python/FastAPI** service behind **Nginx**, managed by **PM2**.

### Server Access

```bash
ssh root@84.247.162.167
```

### Project Location

```bash
/var/www/ai-publish-engine/
```

### Stack

- **Python 3.12** (FastAPI) — backend API
- **PostgreSQL** — database (runs locally or via Docker)
- **Redis** (optional) — job queue via arq
- **Nginx** — reverse proxy (host-level)
- **PM2** — process manager

---

## PM2 Management

The Python app is managed by **PM2** (process manager).

| Action | Command |
|--------|---------|
| Start | `pm2 start ecosystem.config.js` |
| Restart | `pm2 restart ai-publish-engine` |
| Stop | `pm2 stop ai-publish-engine` |
| Status | `pm2 status` |
| Logs | `pm2 logs ai-publish-engine` |
| Monitor | `pm2 monit` |
| Save | `pm2 save` |
| Startup | `pm2 startup` |

PM2 processes persist across reboots when saved via `pm2 save`.

---

## Nginx Configuration

Nginx serves as a reverse proxy, forwarding requests to the Python app on port 9109.

### Config Location

```bash
/etc/nginx/sites-available/ai-publish-engine
```

### Symlink to enable

```bash
/etc/nginx/sites-enabled/ai-publish-engine
```

### Common commands

```bash
nginx -t                    # test config
systemctl restart nginx     # reload nginx
```

---

## Database — PostgreSQL

### Connection info

| Field | Value |
|-------|-------|
| Host | localhost |
| Port | 5432 |
| Database | `aipublish` |
| User | `aipublish` |
| Password | *(in .env file)* |

### Useful commands

```bash
# Connect to PostgreSQL container
docker exec -it postgres-db psql -U aipublish -d aipublish

# List tables
docker exec -it postgres-db psql -U aipublish -d aipublish -c '\dt'

# Backup database
docker exec -t postgres-db pg_dump -U aipublish aipublish > backup.sql

# Restore database
cat backup.sql | docker exec -i postgres-db psql -U aipublish aipublish
```

---

## Logs Location

| Source | Location |
|--------|----------|
| PM2 logs | `pm2 logs ai-publish-engine` |
| PM2 log files | `~/.pm2/logs/` |
| App logs | `logs/out.log` and `logs/err.log` |
| Nginx access | `/var/log/nginx/access.log` |
| Nginx error | `/var/log/nginx/error.log` |

---

## Environment Variables

Configuration is in `/var/www/ai-publish-engine/.env`.

| Variable | Description |
|----------|-------------|
| `AI_PROVIDER` | Default AI provider (groq, gemini, openrouter, mistral, openai) |
| `GROQ_API_KEY` | API key for Groq |
| `GEMINI_API_KEY` | API key for Gemini |
| `OPENROUTER_API_KEY` | API key for OpenRouter |
| `MISTRAL_API_KEY` | API key for Mistral |
| `OPENAI_API_KEY` | API key for OpenAI |
| `DATABASE_URL` | PostgreSQL connection string (optional, falls back to JSON file) |
| `PORT` | App port (default: 9109) |
| `SECRET_KEY` | Admin JWT secret (optional, auto-generated if empty) |
| `CORS_ORIGINS` | Comma-separated allowed origins (empty = allow all) |
| `OUTPUT_DIR` | Output directory path |
| `JOB_FILE` | JSON job storage path |
| `WORKERS` | Number of uvicorn workers (default: 2) |
| `LOG_LEVEL` | Logging level (debug, info, warning, error) |

Per-provider model override (optional):
- `GROQ_MODEL`, `GEMINI_MODEL`, `OPENROUTER_MODEL`, `MISTRAL_MODEL`, `OPENAI_MODEL`

---

## Updating the App (Re-deploy)

```bash
cd /var/www/ai-publish-engine

# 1. Pull latest code
git pull origin main

# 2. Install new dependencies
source venv/bin/activate
pip install -r requirements.txt

# 3. Run database migrations (auto-applied on startup)

# 4. Restart the app
pm2 restart ai-publish-engine

# 5. Verify
pm2 status
```

---

## Available Endpoints

| Method | Route | Description |
|--------|-------|-------------|
| GET | `/` | Main page (index.html) |
| GET | `/admin` | Admin dashboard |
| GET | `/api/health` | Health check |
| GET | `/api/providers` | List AI providers |
| POST | `/api/generate` | Generate content (ebook, website, etc.) |
| POST | `/api/generate-batch` | Batch generate from multiple files |
| GET | `/api/status/{job_id}` | Get job status |
| GET | `/api/jobs` | List all jobs |
| GET | `/api/download/{job_id}` | Download result (pdf, epub, docx, website) |
| POST | `/api/cancel/{job_id}` | Cancel a job |
| GET | `/api/preview/{job_id}` | HTML preview |
| GET | `/api/reader/{job_id}` | Reader view |
| DELETE | `/api/admin/jobs/{job_id}` | Delete a job (admin) |
| POST | `/api/admin/jobs/{job_id}/retry` | Retry a failed job (admin) |
| GET | `/api/embed/{job_id}` | Embeddable book |
| POST | `/api/marketing/generate/{job_id}` | Generate marketing content |
| POST | `/api/translate/{job_id}` | Translate content |
| POST | `/api/coach/start` | AI Writing Coach |
| POST | `/api/proofread/{job_id}` | Proofreading |
| POST | `/api/beta-read/{job_id}` | Beta Reader feedback |
| GET | `/api/format-check/{job_id}` | KDP Format Check |
| GET | `/api/themes` | List available themes |
| GET | `/api/templates` | List available templates |
| GET | `/api/topics` | List content topics |
| GET | `/api/print-sizes` | List available print sizes |
| POST | `/api/download/{job_id}/print` | Generate print-ready PDF |
| POST | `/api/admin/login` | Admin login |
| GET | `/api/admin/check` | Verify admin token |
| GET | `/api/publish/platforms` | List publishing platforms |
| POST | `/api/publish/metadata/{job_id}` | Generate publishing metadata |
| POST | `/api/launch-page/{job_id}` | Generate book launch page |
| POST | `/api/series/create` | Create book series |
| GET | `/api/guide` | This guide |
| WS | `/ws/progress/{job_id}` | WebSocket progress updates |
