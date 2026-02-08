#!/bin/bash

# nebulaONE API Server Startup Script
# Simple one-command script to start the server

echo "🚀 Starting nebulaONE API Server..."
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: Python 3 is not installed"
    exit 1
fi

# Check if required packages are installed
if ! python3 -c "import flask" 2>/dev/null; then
    echo "📦 Installing required packages..."
    pip3 install -r requirements.txt
    echo ""
fi

# Check if Playwright is installed (for token refresh)
if ! python3 -c "import playwright" 2>/dev/null; then
    echo "📦 Installing Playwright for token refresh..."
    pip3 install playwright python-dotenv
    python3 -m playwright install chromium
    echo ""
fi

# Start the server
echo "🎯 Launching API server on http://localhost:8000"
echo ""
exec python3 api_server.py
