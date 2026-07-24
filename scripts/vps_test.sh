#!/bin/bash
set -e

echo "Artificial intelligence is transforming healthcare, finance, and education.
Machine learning enables pattern recognition and predictive analytics.
Deep learning uses neural networks to solve complex problems." > /tmp/test.txt

echo "--- Generating ---"
RESPONSE=$(curl -s -X POST http://127.0.0.1:9109/api/generate \
  -F "file=@/tmp/test.txt" \
  -F "style=business" \
  -F "provider=groq")
echo "$RESPONSE"

JOB_ID=$(echo "$RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin)['job_id'])")
echo "Job ID: $JOB_ID"

for i in $(seq 1 15); do
  sleep 10
  STATUS=$(curl -s "http://127.0.0.1:9109/api/status/$JOB_ID" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('status','?'), d.get('progress','?'))" 2>/dev/null)
  echo "Status $((i*10))s: $STATUS"
  echo "$STATUS" | grep -q "done\|failed" && break
done

echo ""
echo "--- Results ---"
find /var/www/ai-publish-engine/outputs/ -name "*$JOB_ID*" -ls 2>/dev/null || echo "No output files found"

echo ""
echo "--- Download tests ---"
curl -s -o "/tmp/${JOB_ID}.pdf" -w "PDF: HTTP %{http_code}, %{size_download} bytes\n" "http://127.0.0.1:9109/api/download/$JOB_ID?format=pdf" 2>/dev/null
curl -s -o "/tmp/${JOB_ID}.epub" -w "EPUB: HTTP %{http_code}, %{size_download} bytes\n" "http://127.0.0.1:9109/api/download/$JOB_ID?format=epub" 2>/dev/null
curl -s -o "/tmp/${JOB_ID}.docx" -w "DOCX: HTTP %{http_code}, %{size_download} bytes\n" "http://127.0.0.1:9109/api/download/$JOB_ID?format=docx" 2>/dev/null
curl -s -o "/tmp/${JOB_ID}.html" -w "Preview: HTTP %{http_code}, %{size_download} bytes\n" "http://127.0.0.1:9109/api/preview/$JOB_ID" 2>/dev/null

echo ""
echo "--- File sizes ---"
ls -lh /tmp/${JOB_ID}.* 2>/dev/null | awk '{print $5, $9}'
