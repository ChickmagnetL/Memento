#!/usr/bin/env bash
# MVP end-to-end smoke test against a RUNNING stack.
# Prerequisites: backend on :8000, real chat+embedding configured,
# jq installed, and a Bilibili video URL with CC subtitles as $1.
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8000}"
VIDEO_URL="${1:?Usage: $0 <bilibili-url-with-cc-subtitles>}"

step() { printf '\n==> %s\n' "$1"; }

step "Health"
curl -sf "$BASE_URL/api/health" | jq -e '.status == "healthy" or .status == "ok"' > /dev/null

step "Create video"
VIDEO_ID=$(curl -sf -X POST "$BASE_URL/api/videos" \
  -H 'Content-Type: application/json' \
  -d "{\"url\": \"$VIDEO_URL\"}" | jq -r '.id')
echo "video_id=$VIDEO_ID"

step "Process video"
STATUS=$(curl -sf -X POST "$BASE_URL/api/videos/$VIDEO_ID/process" | jq -r '.status')
[ "$STATUS" = "completed" ] || { echo "FAIL: process status=$STATUS"; exit 1; }

step "Find document"
DOC_ID=$(curl -sf "$BASE_URL/api/documents" \
  | jq -r --arg vid "$VIDEO_ID" '[.[] | select(.video_id == $vid)][0].id')
[ "$DOC_ID" != "null" ] || { echo "FAIL: no document"; exit 1; }
echo "document_id=$DOC_ID"

step "Index document"
INDEXED=$(curl -sf -X POST "$BASE_URL/api/documents/$DOC_ID/index" | jq -r '.is_indexed')
[ "$INDEXED" = "true" ] || { echo "FAIL: not indexed"; exit 1; }

step "Search"
HITS=$(curl -sf -X POST "$BASE_URL/api/search" \
  -H 'Content-Type: application/json' \
  -d '{"query": "视频"}' | jq 'length')
[ "$HITS" -ge 1 ] || { echo "FAIL: no search hits"; exit 1; }

step "Chat (SSE)"
CHAT_BODY=$(curl -sf -N -X POST "$BASE_URL/api/chat" \
  -H 'Content-Type: application/json' \
  -d '{"message": "这个视频讲了什么？"}')
echo "$CHAT_BODY" | grep -q '"type": *"done"' || { echo "FAIL: no done event"; exit 1; }
echo "$CHAT_BODY" | grep -q '"type": *"error"' && { echo "FAIL: error event"; exit 1; }

step "ALL PASSED"
