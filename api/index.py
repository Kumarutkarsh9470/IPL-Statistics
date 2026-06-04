"""
Vercel Serverless Handler for FastAPI ML API.
This wrapper adapts FastAPI to work with Vercel Functions.

Deploy to Vercel with:
  vercel deploy --prod
"""
import sys
from pathlib import Path

# Add parent directory to path so we can import ml module
sys.path.insert(0, str(Path(__file__).parent.parent))

from ml.serve import app

# Vercel expects a callable named 'handler'
handler = app
