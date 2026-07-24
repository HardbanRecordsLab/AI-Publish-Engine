#!/bin/bash
# ============================================================
# AI Publishing Engine - Deploy to VPS
# ssh deploy script
# ============================================================
set -e

VPS="root@84.247.162.167"
REMOTE_DIR="/var/www/ai-publish-engine"
SSH_KEY="C:/Users/HRL/.ssh/id_ed25519"
LOCAL_DIR="G:/ebook builder"

echo "=========================================="
echo " AI Publishing Engine - VPS Deploy"
echo "=========================================="

# 1. Create deployment package
echo ""
echo "[1/7] Creating deployment package..."
cd "$LOCAL_DIR"

# Export only what's needed
cat > .deploy_include.txt << EOF
backend/
templates/
frontend/
scripts/
tests/
requirements.txt
ecosystem.config.js
.env
EOF

tar -czf /tmp/ai-publish-deploy.tar.gz \
  $(cat .deploy_include.txt) 2>/dev/null || {
  # Fallback: find files manually
  tar -czf /tmp/ai-publish-deploy.tar.gz \
    backend/ templates/ frontend/ scripts/ tests/ \
    requirements.txt ecosystem.config.js .env 2>/dev/null
}

rm -f .deploy_include.txt
echo "   Package: /tmp/ai-publish-deploy.tar.gz ($(du -h /tmp/ai-publish-deploy.tar.gz | cut -f1))"

# 2. Create remote directories
echo ""
echo "[2/7] Creating remote directories..."
ssh -i "$SSH_KEY" "$VPS" "
  mkdir -p $REMOTE_DIR/{outputs,jobs,logs,templates/themes}
  chmod 755 $REMOTE_DIR/{outputs,jobs,logs}
  echo '   Directories OK'
"

# 3. Transfer files
echo ""
echo "[3/7] Transferring files to VPS..."
scp -i "$SSH_KEY" /tmp/ai-publish-deploy.tar.gz "$VPS:$REMOTE_DIR/"

ssh -i "$SSH_KEY" "$VPS" "
  cd $REMOTE_DIR
  tar -xzf ai-publish-deploy.tar.gz
  rm -f ai-publish-deploy.tar.gz
  chmod -R 755 .
  echo '   Files extracted'
"

# 4. Install Python dependencies
echo ""
echo "[4/7] Installing Python dependencies..."
ssh -i "$SSH_KEY" "$VPS" "
  cd $REMOTE_DIR
  if [ ! -d venv ]; then
    python3 -m venv venv
    echo '   Virtualenv created'
  fi
  source venv/bin/activate
  pip install --upgrade pip -q
  pip install -r requirements.txt -q
  pip install uvicorn -q
  echo '   Dependencies installed'
  
  # Install Playwright browser
  python -m playwright install chromium 2>/dev/null && echo '   Playwright installed' || echo '   Playwright already installed'
"

# 5. Create PostgreSQL container + database tables
echo ""
echo "[5/7] Setting up database..."
ssh -i "$SSH_KEY" "$VPS" "
  # Start PostgreSQL container if not exists
  docker ps -a --format '{{.Names}}' | grep -q hbrl-postgres || \
  docker run -d --name hbrl-postgres \
    --restart unless-stopped \
    -e POSTGRES_USER=hbrl_admin \
    -e POSTGRES_PASSWORD=HardbanRecordsLab2026\! \
    -e POSTGRES_DB=ai_publish_engine \
    -p 127.0.0.1:5432:5432 \
    -v hbrl-postgres-data:/var/lib/postgresql/data \
    postgres:16-alpine 2>/dev/null && echo '   PostgreSQL container created' || echo '   PostgreSQL already running'

  # Wait for PG to be ready
  for i in {1..10}; do
    docker exec hbrl-postgres pg_isready -U hbrl_admin -d ai_publish_engine 2>/dev/null && break
    sleep 2
  done

  # Create tables with all columns
  docker exec hbrl-postgres psql -U hbrl_admin -d ai_publish_engine -c \"
    CREATE TABLE IF NOT EXISTS jobs (
      id TEXT PRIMARY KEY,
      status TEXT DEFAULT 'queued',
      progress INTEGER DEFAULT 0,
      style TEXT DEFAULT '',
      topic TEXT DEFAULT '',
      content_type TEXT DEFAULT 'ebook',
      audience TEXT DEFAULT '',
      tone TEXT DEFAULT '',
      chapters TEXT DEFAULT '',
      keywords TEXT DEFAULT '',
      language TEXT DEFAULT 'English',
      output_path TEXT DEFAULT '',
      epub_path TEXT DEFAULT '',
      docx_path TEXT DEFAULT '',
      website_path TEXT DEFAULT '',
      html TEXT DEFAULT '',
      error TEXT DEFAULT '',
      book_data TEXT DEFAULT '',
      build_params TEXT DEFAULT '',
      created_at TIMESTAMP DEFAULT NOW()
    );
  \" 2>/dev/null && echo '   Tables OK' || echo '   Tables created'
"

# 6. Configure Nginx
echo ""
echo "[6/7] Configuring Nginx..."
ssh -i "$SSH_KEY" "$VPS" "
  cat > /etc/nginx/sites-available/ai-publish.hardbanrecordslab.online << 'NGINX'
upstream ai_publish_backend {
    server 127.0.0.1:9109;
    keepalive 64;
}

server {
    listen 80;
    server_name ai-publish.hardbanrecordslab.online;
    return 301 https://\$host\$request_uri;
}

server {
    listen 443 ssl http2;
    server_name ai-publish.hardbanrecordslab.online;

    ssl_certificate /etc/letsencrypt/live/hardbanrecordslab.online/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/hardbanrecordslab.online/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    client_max_body_size 100M;

    location / {
        proxy_pass http://ai_publish_backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_cache_bypass \$http_upgrade;
        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
    }

    location /frontend/ {
        alias /var/www/ai-publish-engine/frontend/;
        try_files \$uri \$uri/ =404;
    }

    location /outputs/ {
        alias /var/www/ai-publish-engine/outputs/;
        internal;
    }

    location /api/docs {
        proxy_pass http://ai_publish_backend;
        proxy_set_header Host \$host;
    }

    access_log /var/log/nginx/ai-publish-access.log;
    error_log /var/log/nginx/ai-publish-error.log;
}
NGINX
  ln -sf /etc/nginx/sites-available/ai-publish.hardbanrecordslab.online /etc/nginx/sites-enabled/
  nginx -t && nginx -s reload && echo '   Nginx configured'
"

# 7. Start PM2
echo ""
echo "[7/7] Starting PM2..."
ssh -i "$SSH_KEY" "$VPS" "
  cd $REMOTE_DIR
  source venv/bin/activate
  pm2 start ecosystem.config.js 2>/dev/null || pm2 restart ecosystem.config.js 2>/dev/null
  pm2 save
  echo '   PM2 started'
  
  # Health check
  sleep 3
  curl -s http://127.0.0.1:9109/api/providers | python3 -m json.tool 2>/dev/null && echo '   API OK' || echo '   Waiting for API...'
  sleep 5
  curl -s http://127.0.0.1:9109/api/themes | python3 -c 'import sys,json; d=json.load(sys.stdin); print(f\"   Themes: {len(d)}\")' 2>/dev/null
  curl -s http://127.0.0.1:9109/api/topics | python3 -c 'import sys,json; d=json.load(sys.stdin); print(f\"   Topics: {len(d)}\")' 2>/dev/null
"

echo ""
echo "=========================================="
echo " ✅ AI Publishing Engine deployed!"
echo "=========================================="
echo ""
echo " API:      https://ai-publish.hardbanrecordslab.online"
echo " Docs:     https://ai-publish.hardbanrecordslab.online/docs"
echo " Frontend: https://ai-publish.hardbanrecordslab.online/frontend/index.html"
echo ""
echo " PM2:      pm2 list (on VPS)"
echo " Logs:     pm2 logs ai-publish-engine"
echo ""
echo " PostgreSQL: ai_publish_engine (via hbrl-postgres:5432)"
echo ""
