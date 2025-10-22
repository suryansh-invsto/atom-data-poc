#!/bin/bash
set -e

echo "🚀 Setting up Cache Architecture POC"
echo "======================================"

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed"
    exit 1
fi

echo "✓ Python 3 found: $(python3 --version)"

# Create virtual environment
if [ ! -d "venv" ]; then
    echo ""
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
    echo "✓ Virtual environment created"
else
    echo "✓ Virtual environment already exists"
fi

# Activate virtual environment
echo ""
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo ""
echo "📥 Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt
echo "✓ Dependencies installed"

# Start Redis
echo ""
echo "🚀 Starting Redis..."
if ! docker info &> /dev/null; then
    echo "❌ Docker is not running. Please start Docker and try again."
    exit 1
fi

docker-compose up -d
echo "✓ Redis started"

# Wait for Redis to be ready
echo ""
echo "⏳ Waiting for Redis to be ready..."
sleep 3

# Test Redis connection
if docker-compose exec -T redis redis-cli ping &> /dev/null; then
    echo "✓ Redis is ready"
else
    echo "❌ Redis is not responding"
    exit 1
fi

echo ""
echo "======================================"
echo "✅ Setup complete!"
echo ""
echo "To run the tests:"
echo "  source venv/bin/activate"
echo "  python main.py --mode 2-tier --duration 60"
echo "  python main.py --mode 3-tier --duration 60"
echo "  python generate_report.py"
echo ""
echo "To view logs:"
echo "  docker-compose logs -f redis"
echo ""
echo "To stop Redis:"
echo "  docker-compose down"
