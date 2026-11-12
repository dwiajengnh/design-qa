#!/usr/bin/env bash
# Upload local images to Notion after creating upload slots with the Notion MCP `notion-create-file-upload` tool.
#
# Usage: notion_upload.sh <manifest.txt>
# manifest.txt — one line per file: <upload_url> <authorization header value without "Bearer "> <local file path>
# Prints "<http status> <file> <file_upload_id>" per line. Use `file-upload://<file_upload_id>` as the image src.
set -euo pipefail
while read -r url token file; do
  [ -z "${url:-}" ] && continue
  body=$(curl -s -w '\n%{http_code}' -X POST "$url" -H "authorization: Bearer $token" -F "file=@${file};type=image/png")
  code=$(printf '%s' "$body" | tail -n1)
  fid=$(printf '%s' "$body" | sed -n 's/.*"file_upload_id":"\([^"]*\)".*/\1/p' | head -n1)
  echo "$code $file $fid"
done < "$1"
