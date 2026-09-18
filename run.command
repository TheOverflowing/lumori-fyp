#!/bin/zsh
set -e
cd "$(dirname "$0")"
if [[ ! -x .venv/bin/python ]]; then
  print '请先按照 README.md 创建虚拟环境并安装依赖。'
  exit 1
fi
exec .venv/bin/python -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8765
