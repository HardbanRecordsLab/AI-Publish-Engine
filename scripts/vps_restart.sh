#!/bin/bash
cd /var/www/ai-publish-engine

# Kill old processes on port 9109
fuser -k 9109/tcp 2>/dev/null || true
sleep 2

# Restart PM2
pm2 delete ai-publish-engine 2>/dev/null || true
pm2 start ecosystem.config.js
pm2 save

echo "---PM2 started---"
sleep 8

echo "---API check---"
curl -s http://127.0.0.1:9109/api/providers | python3 -m json.tool 2>&1 | head -10
echo ""
curl -s http://127.0.0.1:9109/api/themes | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'Theme count: {len(d)}')" 2>&1
curl -s http://127.0.0.1:9109/api/topics | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'Topic count: {len(d)}')" 2>&1
