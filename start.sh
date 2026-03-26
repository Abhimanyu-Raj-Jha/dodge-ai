#!/bin/bash

# Dodge AI Startup Script
# Usage: ./start.sh

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 Dodge AI Startup${NC}"
echo "================================"

# Check if OpenRouter API key is set
if [ -z "$OPENROUTER_API_KEY" ]; then
    echo -e "${YELLOW}⚠️  OPENROUTER_API_KEY not set!${NC}"
    echo ""
    echo "Please set your API key:"
    echo "  export OPENROUTER_API_KEY=\"your_key_here\""
    echo ""
    echo "Get a free key at: https://openrouter.ai"
    exit 1
fi

# Check Python version
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found. Please install Python 3.8+"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "✅ Python $PYTHON_VERSION found"

# Check if Flask is installed
if ! python3 -c "import flask" 2>/dev/null; then
    echo "📦 Installing Flask..."
    pip install flask
fi
echo "✅ Flask installed"

# Check if database exists, if not, ingest
if [ ! -f "data.db" ]; then
    echo "📊 Database not found. Running ingest..."
    python3 ingest.py
fi
echo "✅ Database ready"

# Kill any existing process on port 5001
if lsof -Pi :5001 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "🛑 Stopping existing process on port 5001..."
    pkill -9 -f "python3 app.py" || true
    sleep 2
fi

# Start the app
echo ""
echo -e "${GREEN}✨ Starting Dodge AI...${NC}"
echo "Opening http://localhost:5001 in 3 seconds..."
echo ""

python3 app.py &
PID=$!

sleep 3

# Try to open in browser
if command -v open &> /dev/null; then
    open http://localhost:5001
elif command -v xdg-open &> /dev/null; then
    xdg-open http://localhost:5001
else
    echo "📱 Go to: http://localhost:5001"
fi

wait $PID
