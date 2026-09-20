#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
cp -n .env.example .env || true
python -m app.bootstrap

echo ""
echo "✓ 就绪。下一步："
echo "  source .venv/bin/activate"
echo "  python lessons/01_async_await.py"
echo "  uvicorn app.main:app --reload --port 8000"
