#!/bin/sh
set -e
for d in /app/jobs /app/user_prompts /app/library /app/output /app/config; do
    mkdir -p "$d"
    chown -R appuser:appuser "$d" 2>/dev/null || true
done
exec gosu appuser "$@"
