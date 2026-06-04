#!/bin/bash
# Vercel Build Script
# This script runs during the Vercel build process

echo "🚀 Starting IPL-Statistics Deployment Build..."

# Install Python dependencies
echo "📦 Installing Python dependencies..."
pip install -r requirements.txt

# Check if ml/serve.py exists
if [ -f "ml/serve.py" ]; then
    echo "✅ FastAPI serve module found"
else
    echo "⚠️  Warning: ml/serve.py not found"
fi

# Check if models exist
if [ -d "ml/models" ]; then
    echo "✅ ML models directory found"
    ls -lh ml/models/ | head -10
else
    echo "⚠️  Warning: ml/models directory not found"
fi

echo "✅ Build completed successfully!"
