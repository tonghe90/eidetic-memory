#!/bin/bash
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

# Create .env if not exists
if [ ! -f .env ]; then
  cp .env.example .env
  echo "✅ 已创建 .env，请填写 API Key 后重新运行"
  exit 1
fi

# Create data and wiki dirs
mkdir -p data wiki/topics wiki/people wiki/conversations

# Install Python deps
if [ ! -d .venv ]; then
  echo "📦 创建 Python 虚拟环境..."
  python3 -m venv .venv
fi
source .venv/bin/activate
pip install -q -r requirements.txt

# Install frontend deps
if [ ! -d frontend/node_modules ]; then
  echo "📦 安装前端依赖..."
  cd frontend && npm install && cd ..
fi

# Start backend
echo "🚀 启动后端 http://localhost:8765"
uvicorn backend.main:app --host 0.0.0.0 --port 8765 --reload &
BACKEND_PID=$!

# Start frontend
echo "🚀 启动前端 http://localhost:5173"
cd frontend && npm run dev &
FRONTEND_PID=$!

echo ""
echo "✅ LLM Wiki 已启动"
echo "   前端: http://localhost:5173"
echo "   API:  http://localhost:8765"
echo ""
echo "按 Ctrl+C 停止"

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null" EXIT
wait
