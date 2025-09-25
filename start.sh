#!/bin/bash

# HelperGPT Startup Script
# This script sets up and runs the HelperGPT backend system

echo "🤖 Starting HelperGPT Backend System..."

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "📚 Installing dependencies..."
pip install -r requirements.txt

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "⚠️  .env file not found. Please copy .env.example to .env and configure your settings."
    cp .env.example .env
    echo "✅ Created .env file from template. Please edit it with your Azure OpenAI credentials."
    exit 1
fi

# Create necessary directories
echo "📁 Creating directories..."
mkdir -p uploads
mkdir -p backups

# Run the application
echo "🚀 Starting HelperGPT API server..."
echo "📍 Access the API at: http://localhost:8000"
echo "📖 API Documentation at: http://localhost:8000/docs"
echo "⏹️  Press Ctrl+C to stop the server"

python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
