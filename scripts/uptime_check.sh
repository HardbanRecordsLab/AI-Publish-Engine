#!/bin/bash
# Uptime monitor for AI Publish Engine — no external monitoring account
# needed. Polls the local health endpoint and alerts only on state
# *transitions* (healthy -> down, down -> healthy), not on every failed
# check, so it doesn't spam whatever channel it's wired to.
#
# Setup on the VPS:
#   chmod +x /var/www/ai-publish-engine/scripts/uptime_check.sh
#   crontab -e
#   */5 * * * * /var/www/ai-publish-engine/scripts/uptime_check.sh >> /var/www/ai-publish-engine/logs/uptime.log 2>&1
#
# Optional: set UPTIME_ALERT_WEBHOOK in .env to a Slack (or any
# Slack-compatible) incoming webhook URL to also get a message posted
# there on every transition. Without it, transitions are still logged
# to logs/uptime.log — check that file, or wire in your own alerting
# by reading STATE_FILE below.

set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HEALTH_URL="http://127.0.0.1:9109/api/health"
STATE_FILE="$APP_DIR/logs/.uptime_state"
TIMESTAMP="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

# Pull UPTIME_ALERT_WEBHOOK out of .env without executing the file (it
# may contain values that aren't safe to `source`).
WEBHOOK="$(grep -E '^UPTIME_ALERT_WEBHOOK=' "$APP_DIR/.env" 2>/dev/null | cut -d'=' -f2- || true)"

PREV_STATE="unknown"
[ -f "$STATE_FILE" ] && PREV_STATE="$(cat "$STATE_FILE")"

if curl -sf --max-time 10 "$HEALTH_URL" > /dev/null 2>&1; then
  CURR_STATE="up"
else
  CURR_STATE="down"
fi

notify() {
  local message="$1"
  echo "[$TIMESTAMP] $message"
  if [ -n "$WEBHOOK" ]; then
    curl -sf --max-time 10 -X POST -H 'Content-Type: application/json' \
      -d "{\"text\": \"$message\"}" "$WEBHOOK" > /dev/null 2>&1 || \
      echo "[$TIMESTAMP] WARNING: failed to POST to UPTIME_ALERT_WEBHOOK"
  fi
}

if [ "$CURR_STATE" != "$PREV_STATE" ]; then
  if [ "$CURR_STATE" = "down" ]; then
    notify "🔴 AI Publish Engine: health check FAILED ($HEALTH_URL not responding)"
  elif [ "$PREV_STATE" != "unknown" ]; then
    notify "🟢 AI Publish Engine: health check RECOVERED"
  fi
  echo "$CURR_STATE" > "$STATE_FILE"
fi
