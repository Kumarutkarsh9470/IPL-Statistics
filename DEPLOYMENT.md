# 🚀 IPL Analytics - Free Deployment Guide (Option A)

**Architecture:** Frontend (Vercel) + Python ML API (Vercel) + PHP Backend (Railway) + Database (Planet Scale)

---

## 📋 Quick Summary

| Service                 | Provider             | Free Tier           | Cost      |
| ----------------------- | -------------------- | ------------------- | --------- |
| Frontend (HTML/CSS/JS)  | **Vercel**           | ✅ Yes              | $0/mo     |
| ML API (Python/FastAPI) | **Vercel Functions** | ✅ Yes              | $0/mo     |
| PHP Backend             | **Railway**          | ✅ Yes (500 hrs/mo) | $0/mo     |
| MySQL Database          | **Planet Scale**     | ✅ Yes              | $0/mo     |
| **Total**               |                      |                     | **$0/mo** |

---

## 🗂️ Pre-Deployment Checklist

- [x] ✅ Mock ML models generated
- [ ] GitHub repository pushed
- [ ] Vercel account created
- [ ] Railway account created
- [ ] Planet Scale account created
- [ ] Database migrated to Planet Scale
- [ ] Environment variables configured

---

## 📝 Step-by-Step Deployment Guide

### **STEP 0: Prepare Your GitHub Repository** (5 minutes)

Your project is already in GitHub. Make sure all files are committed:

```bash
cd c:\Users\My\Desktop\dbms\IPL-Statistics
git status
git add -A
git commit -m "Add deployment configuration and mock models"
git push origin main
```

---

### **STEP 1: Set Up Planet Scale Database (10 minutes)**

**What:** Managed MySQL hosting (free tier: 5 GB storage, 10M monthly reads)

#### 1.1 Create Account

1. Go to https://planetscale.com
2. Sign up with GitHub (easier)
3. Verify email

#### 1.2 Create Database

1. Click **Create Database**
2. Database name: `ipl-db`
3. Region: Choose closest to your users
4. Pricing: **Free tier**
5. Click **Create database**

#### 1.3 Export Local MySQL

```bash
# From your machine (requires MySQL installed)
mysqldump -u ipl_user -ppassword123 ipl_db > ipl_db_backup.sql
```

#### 1.4 Import to Planet Scale

1. Open Planet Scale database dashboard
2. Click **Branches** → **main**
3. Click **Import data**
4. Upload `ipl_db_backup.sql` or use SQL client

#### 1.5 Get Connection String

1. In Planet Scale dashboard, click **Connect**
2. Select **Node.js** driver
3. Copy the connection string (looks like: `mysql://username:password@host/database`)
4. **Save this** — you'll need it later

---

### **STEP 2: Deploy PHP Backend to Railway (15 minutes)**

**What:** PHP hosting for your Portal APIs

#### 2.1 Create Railway Account

1. Go to https://railway.app
2. Sign up with GitHub
3. Authorize access to your repositories

#### 2.2 Deploy PHP Service

1. In Railway, click **Create Project**
2. Select **Deploy from GitHub repo**
3. Choose your `IPL-Statistics` repository
4. Select **PHP** as the environment

#### 2.3 Configure Environment Variables

In Railway dashboard:

```
DB_HOST = <planet_scale_host>
DB_PORT = 3306
DB_USER = <planet_scale_username>
DB_PASSWORD = <planet_scale_password>
DB_NAME = ipl_db
```

#### 2.4 Set Startup Command

In Railway **Settings**:

```
Start Command: php -S 0.0.0.0:8080 -t portal/backend
```

Or create `Procfile`:

```
web: php -S 0.0.0.0:$PORT -t portal/backend
```

#### 2.5 Get Railway URL

1. Click **Deployments**
2. Find the public URL (example: `https://your-app.up.railway.app`)
3. **Save this** — API endpoints will be: `https://your-app.up.railway.app/api/...`

---

### **STEP 3: Deploy ML API to Vercel (10 minutes)**

**What:** Python FastAPI as serverless functions

#### 3.1 Create Vercel Account

1. Go to https://vercel.com
2. Sign up with GitHub
3. Authorize access

#### 3.2 Deploy Project

1. Click **Add New Project**
2. Select your GitHub repository `IPL-Statistics`
3. Vercel auto-detects as Python project

#### 3.3 Configure Environment Variables

In Vercel **Environment Variables**:

```
DB_HOST = <planet_scale_host>
DB_PORT = 3306
DB_USER = <planet_scale_username>
DB_PASSWORD = <planet_scale_password>
DB_NAME = ipl_db
RAILWAY_BACKEND_URL = https://your-railway-app.up.railway.app
```

#### 3.4 Deploy

1. Click **Deploy**
2. Wait for build to complete (2-3 minutes)
3. Get Vercel URL (example: `https://ipl-stats.vercel.app`)

#### 3.5 Test ML API

```bash
# Health check
curl https://ipl-stats.vercel.app/api/health

# Should return:
# {"status": "ok", "models_loaded": {...}}
```

---

### **STEP 4: Deploy Frontend to Vercel (5 minutes)**

#### 4.1 Update Frontend API URLs

**File:** `portal/js/main.js`

Replace hardcoded URLs with environment variables:

```javascript
// Before:
const PHP_API = "http://localhost/api/";
const ML_API = "http://localhost:8000/api/predict/";

// After:
const PHP_API =
  window.location.hostname === "localhost"
    ? "http://localhost/api/"
    : "https://your-railway-app.up.railway.app/api/";

const ML_API =
  window.location.hostname === "localhost"
    ? "http://localhost:8000/api/predict/"
    : "https://ipl-stats.vercel.app/api/predict/";
```

#### 4.2 Update HTML References

**File:** `portal/index.html`

Make sure all CSS/JS paths are relative (they should be):

```html
<link rel="stylesheet" href="css/style.css" />
<script src="js/main.js"></script>
```

#### 4.3 Deploy Frontend

In Vercel:

1. Create **New Project**
2. Select repository
3. **Root Directory:** `portal`
4. Click **Deploy**

#### 4.4 Access Your Application

```
https://ipl-portal.vercel.app/
```

---

## 🌐 Final Architecture

```
┌─────────────────────────────────────┐
│  https://ipl-portal.vercel.app      │
│  Frontend (HTML/CSS/JS)             │
└──────────────┬──────────────────────┘
               │
      ┌────────┴────────┐
      ↓                 ↓
┌──────────────────┐  ┌─────────────────────────────┐
│ https://...      │  │ https://ipl-stats.vercel.app│
│ railway.app      │  │ ML API (Python/FastAPI)    │
│ PHP Backend      │  │ - /api/predict/match       │
│ - /api/teams     │  │ - /api/predict/score       │
│ - /api/venues    │  │ - /api/predict/player      │
└────────┬─────────┘  └─────────────┬────────────────┘
         │                          │
         └──────────────┬───────────┘
                        ↓
             ┌──────────────────────┐
             │  Planet Scale MySQL  │
             │  ipl-db              │
             └──────────────────────┘
```

---

## 🔑 Environment Variables Reference

### **Vercel (Python ML API)**

```env
DB_HOST=your-db.psdb.cloud
DB_PORT=3306
DB_USER=xxxxx
DB_PASSWORD=xxxxx
DB_NAME=ipl_db
RAILWAY_BACKEND_URL=https://your-railway-app.up.railway.app
```

### **Railway (PHP Backend)**

```env
DB_HOST=your-db.psdb.cloud
DB_PORT=3306
DB_USER=xxxxx
DB_PASSWORD=xxxxx
DB_NAME=ipl_db
```

### **Local Development (.env)**

```env
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=ipl_user
DB_PASSWORD=password123
DB_NAME=ipl_db
FASTAPI_HOST=0.0.0.0
FASTAPI_PORT=8000
```

---

## 🧪 Testing Your Deployment

### **Test Database Connection**

```bash
# From your local machine
python -c "
from ml.db_connect import get_engine
engine = get_engine()
print('✅ Database connected')
"
```

### **Test ML API**

```bash
curl https://ipl-stats.vercel.app/api/health
```

Expected response:

```json
{
  "status": "ok",
  "models_loaded": {
    "match_outcome": true,
    "score_predictor": true,
    "player_batting": true,
    "player_bowling": true
  },
  "prediction_endpoints": [...]
}
```

### **Test Frontend**

1. Open https://ipl-portal.vercel.app
2. Navigate to different tabs
3. Check browser console (F12) for API errors

---

## 📊 Monitoring & Logs

### **Vercel Logs**

```bash
vercel logs <project-name>
```

### **Railway Logs**

Dashboard → Select Project → **Logs**

### **Planet Scale**

Dashboard → Select Database → **Query Insights** / **Logs**

---

## 🆘 Troubleshooting

### **Issue: "Cannot connect to database"**

- ✅ Check Planet Scale connection string
- ✅ Verify database credentials in environment variables
- ✅ Check if IP is whitelisted (Planet Scale allows all by default)

### **Issue: "ML models not loading"**

- ✅ Verify `ml/models/*.joblib` files exist
- ✅ Check model file sizes aren't too large for Vercel
- ✅ Run `python ml/generate_mock_models.py` to regenerate

### **Issue: "CORS errors in browser"**

- ✅ Update `allow_origins` in `ml/serve.py`
- ✅ Check Railway and Vercel URLs are correct
- ✅ Verify frontend is sending correct API URLs

### **Issue: "PHP backend returns 404"**

- ✅ Check Railway deployment succeeded
- ✅ Verify API routes are correct: `/api/teams`, `/api/predict`, etc.
- ✅ Check `.env` variables in Railway dashboard

---

## 💾 After Deployment: Train Real Models

Once everything is deployed and working:

1. **Download IPL dataset** from Kaggle or your source
2. **Place in** `data/raw/IPL.csv`
3. **Run locally:**
   ```bash
   python EDA/process.py          # Clean data
   python import_ipl.py            # Load to local MySQL
   python -m ml.features.build_features
   python -m ml.train.train_match_outcome
   python -m ml.train.train_score_predictor
   python -m ml.train.train_player_perf
   ```
4. **Upload new models to GitHub and redeploy:**
   ```bash
   git add ml/models/
   git commit -m "Update with real trained models"
   git push
   ```
5. **Vercel auto-redeploys** with new models

---

## 📞 Support URLs

- **Vercel Docs:** https://vercel.com/docs
- **Railway Docs:** https://docs.railway.app
- **Planet Scale Docs:** https://planetscale.com/docs
- **FastAPI Docs:** https://fastapi.tiangolo.com

---

## ✅ Deployment Checklist

- [ ] GitHub repository up to date
- [ ] Planet Scale database created and migrated
- [ ] Railway PHP backend deployed
- [ ] Vercel ML API deployed
- [ ] Vercel frontend deployed
- [ ] All environment variables configured
- [ ] CORS configured for all origins
- [ ] API health checks pass
- [ ] Frontend loads and makes API calls
- [ ] Database queries working end-to-end

---

**🎉 You're live! Share your application URL with the team.**

```
Frontend: https://ipl-portal.vercel.app
ML API: https://ipl-stats.vercel.app
PHP API: https://your-app.up.railway.app
```
