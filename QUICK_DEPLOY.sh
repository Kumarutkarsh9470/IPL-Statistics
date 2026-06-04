"""
Quick reference for Vercel deployment.
Copy these commands to deploy quickly.
"""

# ============ STEP 0: GitHub ============
git status
git add -A
git commit -m "Add deployment configuration and mock models"
git push origin main


# ============ STEP 1: Vercel CLI Setup (Optional, for local testing) ============
npm i -g vercel
vercel login


# ============ STEP 2: Deploy to Vercel (via Web Dashboard is easier) ============
# Via Web: Go to https://vercel.com → Connect GitHub repo → Deploy


# ============ STEP 3: Set Environment Variables in Vercel ============
# Dashboard → Settings → Environment Variables
# Add:
# DB_HOST = your-db.psdb.cloud
# DB_PORT = 3306
# DB_USER = xxxxx
# DB_PASSWORD = xxxxx
# DB_NAME = ipl_db
# RAILWAY_BACKEND_URL = https://your-railway-app.up.railway.app


# ============ STEP 4: Local Testing Before Deployment ============
pip install -r requirements.txt
python ml/generate_mock_models.py
uvicorn ml.serve:app --host 0.0.0.0 --port 8000


# ============ STEP 5: Check Logs ============
vercel logs <project-name>


# ============ HELPFUL COMMANDS ============

# Redeploy after changes
git push origin main
# (Vercel auto-redeploys on git push)

# View Vercel dashboard
vercel dashboard

# Check if models are loading
curl https://your-vercel-app.vercel.app/api/health
