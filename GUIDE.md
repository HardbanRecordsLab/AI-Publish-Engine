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
- **PostgreSQL** — database, in a Docker container shared with other
  services on the same VPS (falls back to a local JSON file if unreachable)
- **Nginx** — reverse proxy (host-level)
- **PM2** — process manager

There is no job queue. An earlier Redis/`arq` integration was removed —
generation jobs run in a plain Python `threading.Thread` per request. If you
need horizontal worker scaling later, that's the place to reintroduce a real
queue rather than assuming one already exists.

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

The production database runs inside a Docker container (`hbrl-postgres`)
that is **shared with other, unrelated services on the same VPS** — it is
not a dedicated container for this app. Confirmed by direct inspection;
do not assume `docker restart`/`docker rm` on this container only affects
AI Publish Engine.

### Connection info (production)

| Field | Value |
|-------|-------|
| Host | 127.0.0.1 (bound to localhost only) |
| Port | 5432 |
| Container | `hbrl-postgres` |
| Database | `ai_publish_engine` |
| User | `hbrl_admin` |
| Password | *(in `.env`, `DATABASE_URL`)* |

For local development, `docker-compose.yml` in this repo spins up a
**separate, disposable** Postgres (`aipublish`/`aipublish`) — not the same
database as production, and not something you connect to over SSH.

### Useful commands (production, over SSH)

```bash
# Connect to the shared PostgreSQL container
docker exec -it hbrl-postgres psql -U hbrl_admin -d ai_publish_engine

# List tables
docker exec -it hbrl-postgres psql -U hbrl_admin -d ai_publish_engine -c '\dt'

# Backup database
docker exec -t hbrl-postgres pg_dump -U hbrl_admin ai_publish_engine > backup.sql

# Restore database
cat backup.sql | docker exec -i hbrl-postgres psql -U hbrl_admin ai_publish_engine
```

### Migrations

Schema is managed by Alembic (`alembic/`). `backend/core/database.py` runs
`alembic upgrade head` automatically on startup. On a *fresh* database this
creates the schema from scratch; on the existing production database (whose
tables were originally created by hand) it's already stamped at the current
head, so `upgrade` is a no-op there — it only matters for the next migration
you add.

### Automated backups

`ai_publish_engine` is backed up **daily at 04:00** by
`/srv/hbrl/scripts/backup_hbrl_db.sh` — a script shared with other
HardbanRecordsLab services on this box (it backs up several databases in
the same `hbrl-postgres` container in one pass). Output goes to
`/srv/hbrl/backups/ai_publish_engine_<timestamp>.sql.gz`, retained 7 days.
This app's database was **not** in that script's list before this change;
if the backup schedule or retention ever needs to change, edit that shared
script directly (back up the original first — it's not part of this repo).

For an on-demand backup (e.g. right before a risky migration or deploy),
run `scripts/backup_db.sh` on the VPS — same mechanism, same destination,
just triggered manually instead of by cron.

Restore:

```bash
zcat /srv/hbrl/backups/ai_publish_engine_<timestamp>.sql.gz | \
  docker exec -i hbrl-postgres psql -U hbrl_admin ai_publish_engine
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

Book output (optional):
- `BOOK_BRAND` (default empty): optional tool brand printed in generated
  books — publisher line and "Created with …" on the copyright page, back
  cover, interactive-book footer. Empty = books carry only the author's name
  (from the form's "Author name" field), which is also the publisher in
  ONIX/KDP metadata.

Books are labelled in their own language (EN/PL/DE/ES/FR: "Rozdział",
"Spis treści", …, `backend/core/book_labels.py`), including the html/EPUB
`lang` attribute that drives hyphenation. Other languages get English labels
with the correct `lang` code.

EPUB validation: every generated EPUB is checked right after the build
(built-in rules for packaging, manifest, XHTML well-formedness, SVG
declaration, block-in-`<p>`) and, when `EPUBCHECK_JAR` points at the W3C
EPUBCheck jar (with its `lib/` folder beside it; Java required), by
EPUBCheck itself. The verdict is stored with the job and returned by
`GET /api/status/{job_id}` under `quality` (QA score, chapter scores,
`epub_valid`). AI-written text is HTML-escaped in all book templates.

Print interior (`POST /api/download/{job_id}/print?trim_size=6x9&isbn=…`)
is typeset from the saved book (`backend/core/print_book.py`): KDP trim
sizes, mirrored margins (wider at the spine), running heads (author on
left pages, title on right), centred folios, clean front matter (title
page, copyright page with the ISBN — check digit validated — and contents),
white paper whatever the theme, Polish/German/… hyphenation via `pyphen`,
no covers inside (KDP takes the cover as a separate file and prints the
barcode itself), and every chapter opening on a right-hand page. That last
part needs two render passes, since Chromium ignores `break-before: right`.
Jobs saved before book data existed fall back to wrapping their stored
HTML.

Translation (`POST /api/translate/{job_id}`, body `{"languages": [...]}`)
runs in the background: the saved book is translated chapter by chapter with
the writer model and rebuilt as HTML/EPUB/DOCX. Poll
`GET /api/translate/{job_id}` for status and download links.

Chapter writing (optional):
- `AI_WRITING_TEMPERATURE` (default `0.75`) and `AI_WRITING_TIMEOUT_SECONDS`
  (default `180`) apply only to the per-chapter writing calls.
- `AI_WRITER_PROVIDER` (default `openrouter`), `AI_WRITER_MODEL` (default
  `deepseek/deepseek-v4-pro`), `AI_WRITER_MAX_TOKENS` (default `12000`):
  the model chapters are written with first. Chosen for near-frontier
  long-form writing quality at a low per-token price. Requires
  `OPENROUTER_API_KEY`; without it, or if the call fails or returns bad
  JSON, writing falls back to the normal provider chain. Empty
  `AI_WRITER_PROVIDER` disables it.

### How content is generated

1. **AnalysisAgent** turns the source text into an outline (chapters,
   sections, a one-paragraph draft per section), following the form's
   language, audience, tone, chapter count and keywords.
2. **ResearchAgent** suggests examples, sources and ideas per chapter.
3. **EditorialAgent** writes every chapter out in full, one AI call per
   chapter, using the research notes and a summary of earlier chapters so
   they don't repeat each other. Target length per section depends on the
   output type (ebook ≈ 550 words, blog post ≈ 300, website/landing page
   shorter). A chapter whose call fails keeps its outline draft.
   Each written chapter then gets an editor's review (score 1-10 plus
   concrete fixes). A chapter scoring below `AI_REVIEW_MIN_SCORE`
   (default 7), or far under its target length, is rewritten once with
   those notes. Scores land in the job's QA report (`chapter_reviews`).
   `AI_CHAPTER_REVIEW=0` turns the review off.
4. **StructureAgent** then adds summaries, FAQs and checklists from the
   finished text, followed by fact-check, design, cover and finalization.

Expect 2-3 writer-model calls per chapter (write, review, sometimes a
rewrite), so jobs take longer and cost more tokens per book than the old
single-call generation.

The writer model is also used for the outline, the introduction/back-cover
copy, the marketing suite (Amazon listing, social, press, emails) and
translations. Every reader-facing prompt carries the job's language, and
none may invent statistics, testimonials, credentials or sources: the
References section is no longer AI-generated at all, since it used to come
back with fabricated citations.

---

## Updating the App (Re-deploy)

**As of this writing there is no `git pull`-based deploy** — the server has
no git remote configured (`git status` on the VPS reports "not a git
repository" until you deliberately set one up; see the CI/CD section below
if that has since changed). The verified, working process is a manual
sync over SSH:

```bash
# From your local machine, with the repo at its latest committed state:

# 1. Package the code that actually changed (never .env, outputs/, jobs/,
#    logs/, venv/ — those are runtime state or secrets, not code)
tar --exclude="__pycache__" -czf /tmp/deploy.tar.gz backend frontend alembic requirements.txt

# 2. Ship it
scp -i ~/.ssh/id_ed25519 /tmp/deploy.tar.gz root@84.247.162.167:/tmp/

# 3. On the server: extract, install, restart
ssh -i ~/.ssh/id_ed25519 root@84.247.162.167 '
  cd /var/www/ai-publish-engine
  tar -xzf /tmp/deploy.tar.gz
  source venv/bin/activate
  pip install -r requirements.txt -q
  pm2 restart ai-publish-engine
  sleep 3
  curl -s http://127.0.0.1:9109/api/health
'
```

**Before restarting, always diff the live database schema against what
your new code expects** (`\d jobs` / `\d admins` in psql) — a prior deploy
this way shipped code that assumed a column (`jobs.updated_at`) the live
table didn't have, which would have broken every job status update had it
not been caught before the restart. `alembic upgrade head` runs
automatically on startup but only helps if a migration for the new column
was actually written first.

If a GitHub remote has since been wired up (see `.github/workflows/ci.yml`),
prefer pushing to `main` and letting CI deploy — but verify that workflow
is actually green before trusting it; it was dormant (never once run) for
a long stretch of this project's history.

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
