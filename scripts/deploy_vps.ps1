$ErrorActionPreference = "Continue"
$PSDefaultParameterValues['*:Encoding'] = 'utf8'

$SSH_KEY = "C:\Users\HRL\.ssh\id_ed25519"
$VPS = "root@84.247.162.167"
$REMOTE_DIR = "/var/www/ai-publish-engine"
$LOCAL_DIR = "G:\ebook builder"

function Run-SSH($cmd) {
    ssh -i $SSH_KEY $VPS $cmd 2>&1
    if ($LASTEXITCODE -ne 0) { Write-Host "WARN: exit code $LASTEXITCODE" -ForegroundColor Yellow }
}

function Run-SCP($from, $to) {
    scp -i $SSH_KEY $from $to 2>&1
}

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host " AI Publishing Engine - VPS Deploy" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

Set-Location $LOCAL_DIR

# 1. Package
Write-Host "[1/7] Creating deployment package..." -ForegroundColor Cyan
$files = @(
    "backend", "templates", "frontend", "scripts", "tests",
    "requirements.txt", "ecosystem.config.js", ".env", "GUIDE.md"
)
tar -czf D:\Temp\ai-publish-deploy.tar.gz @files 2>&1 | Out-Null
Write-Host "   Package OK" -ForegroundColor Green

# 2. Remote dirs
Write-Host "[2/7] Creating remote directories..." -ForegroundColor Cyan
Run-SSH "mkdir -p $REMOTE_DIR/outputs $REMOTE_DIR/jobs $REMOTE_DIR/logs $REMOTE_DIR/templates/themes"
Write-Host "   Directories OK" -ForegroundColor Green

# 3. Transfer
Write-Host "[3/7] Transferring files..." -ForegroundColor Cyan
Run-SCP "D:\Temp\ai-publish-deploy.tar.gz" "$VPS`:$REMOTE_DIR/"
Run-SSH "cd $REMOTE_DIR && tar -xzf ai-publish-deploy.tar.gz && rm -f ai-publish-deploy.tar.gz && chmod -R 755 ."
Write-Host "   Files OK" -ForegroundColor Green

# 4. Dependencies
Write-Host "[4/7] Installing Python dependencies..." -ForegroundColor Cyan
Run-SSH "cd $REMOTE_DIR && if [ ! -d venv ]; then python3 -m venv venv; fi && source venv/bin/activate && pip install --upgrade pip -q && pip install -r requirements.txt -q && pip install uvicorn -q"
Run-SSH "cd $REMOTE_DIR && source venv/bin/activate && python -m playwright install chromium 2>/dev/null; echo 'Deps done'"
Write-Host "   Dependencies OK" -ForegroundColor Green

# 5. Database
Write-Host "[5/7] Setting up database..." -ForegroundColor Cyan
Run-SSH 'docker exec hbrl-postgres psql -U hbrl_admin -d hbrl_central -c "SELECT 1 FROM pg_database WHERE datname='\''ai_publish_engine'\''" 2>/dev/null | grep -q 1 || docker exec hbrl-postgres psql -U hbrl_admin -d hbrl_central -c "CREATE DATABASE ai_publish_engine" 2>/dev/null; docker exec hbrl-postgres psql -U hbrl_admin -d ai_publish_engine -c "CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, status TEXT DEFAULT '\''queued'\'', progress INTEGER DEFAULT 0, style TEXT, topic TEXT, content_type TEXT DEFAULT '\''ebook'\'', audience TEXT, tone TEXT, chapters TEXT, keywords TEXT, language TEXT DEFAULT '\''English'\'', output_path TEXT, epub_path TEXT, docx_path TEXT, website_path TEXT, html TEXT, error TEXT, created_at TIMESTAMP DEFAULT NOW());" 2>/dev/null || echo "DB init deferred (JSON fallback active)"'
Write-Host "   Database OK" -ForegroundColor Green

# 6. Nginx
Write-Host "[6/7] Configuring Nginx..." -ForegroundColor Cyan
$nginxConfig = @'
upstream ai_publish_backend {
    server 127.0.0.1:9109;
    keepalive 64;
}
server {
    listen 80;
    server_name ai-publish.hardbanrecordslab.online;
    return 301 https://$host$request_uri;
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
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
    }
    location /frontend/ {
        alias /var/www/ai-publish-engine/frontend/;
        try_files $uri $uri/ =404;
    }
    location /outputs/ {
        alias /var/www/ai-publish-engine/outputs/;
        internal;
    }
    access_log /var/log/nginx/ai-publish-access.log;
    error_log /var/log/nginx/ai-publish-error.log;
}
'@

Set-Content -Path D:\Temp\ai-publish-nginx.conf -Value $nginxConfig -Encoding ASCII
Run-SCP "D:\Temp\ai-publish-nginx.conf" "$VPS`:/etc/nginx/sites-available/ai-publish.hardbanrecordslab.online"
Run-SSH "ln -sf /etc/nginx/sites-available/ai-publish.hardbanrecordslab.online /etc/nginx/sites-enabled/ && nginx -t && nginx -s reload && echo 'Nginx OK'"
Write-Host "   Nginx OK" -ForegroundColor Green

# 7. Start PM2
Write-Host "[7/7] Starting PM2..." -ForegroundColor Cyan
Run-SSH "cd $REMOTE_DIR && source venv/bin/activate && pm2 start ecosystem.config.js 2>/dev/null || pm2 restart ecosystem.config.js 2>/dev/null && pm2 save"
Write-Host "   Starting PM2..." -ForegroundColor Cyan

Start-Sleep -Seconds 10

Run-SSH "curl -s http://127.0.0.1:9109/api/providers | python3 -m json.tool 2>/dev/null | head -5"
Run-SSH "curl -s http://127.0.0.1:9109/api/themes | python3 -c 'import sys,json; d=json.load(sys.stdin); print(f\"Themes: {len(d)}\")'"
Run-SSH "curl -s http://127.0.0.1:9109/api/topics | python3 -c 'import sys,json; d=json.load(sys.stdin); print(f\"Topics: {len(d)}\")'"

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host " ✅ AI Publishing Engine deployed!" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host " API:      https://ai-publish.hardbanrecordslab.online" -ForegroundColor White
Write-Host " Frontend: https://ai-publish.hardbanrecordslab.online/frontend/index.html" -ForegroundColor White
Write-Host " Docs:     https://ai-publish.hardbanrecordslab.online/docs" -ForegroundColor White
Write-Host " PM2:      pm2 logs ai-publish-engine" -ForegroundColor Gray