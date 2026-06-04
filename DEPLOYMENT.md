# 🚀 IPL Analytics - Free Deployment Guide (Option A)

**Architecture:** Frontend (Vercel) + Python ML API (Vercel) + PHP Backend (Railway) + Database (FREE Options Below)

---

## 📋 Quick Summary - 100% FREE

| Service                 | Provider             | Free Tier       | Cost      |
| ----------------------- | -------------------- | --------------- | --------- |
| Frontend (HTML/CSS/JS)  | **Vercel**           | ✅ Yes          | $0/mo     |
| ML API (Python/FastAPI) | **Vercel Functions** | ✅ Yes          | $0/mo     |
| PHP Backend             | **Railway**          | ✅ $5/mo credit | $0/mo     |
| MySQL Database          | **Pick One Below**   | ✅ Yes          | $0/mo     |
| **Total**               |                      |                 | **$0/mo** |

### **Free Database Options** (Choose 1)

- **Option A:** Railway ($5 credit covers DB) ⭐ RECOMMENDED
- **Option B:** Render.com (PostgreSQL free tier)
- **Option C:** Google Cloud SQL (free tier)
- **Option D:** Local MySQL + Ngrok (expose locally)

---

## 🗂️ Pre-Deployment Checklist

- [x] ✅ Mock ML models generated
- [x] ✅ GitHub repository pushed
- [ ] Vercel account created
- [ ] Railway account created
- [ ] Database set up (choose option above)
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

### **STEP 1: Set Up Free Database** (10-15 minutes)

**Choose your free database option:**

#### **Option A: Railway (RECOMMENDED) - Includes $5/mo free credit**

**Most convenient - all services on one platform!**

##### 1.1 Create Railway Account & Get Free Credit

1. Go to https://railway.app
2. Sign up with GitHub
3. You automatically get **$5/month** free credit (enough for MySQL + PHP backend)

##### 1.2 Create MySQL Database on Railway

1. In Railway dashboard → **New Project**
2. Click **Add Service** → **MySQL**
3. Railway auto-provisions MySQL database
4. Click on MySQL service → **Variables**
5. Note these credentials:
   - `MYSQL_HOST`
   - `MYSQL_PORT`
   - `MYSQL_USER`
   - `MYSQL_PASSWORD`
   - `MYSQL_DATABASE`

##### 1.3 Access MySQL Database

```bash
# Install MySQL client (if not already)
# Then connect via Railway connection string
mysql -h <host> -u <user> -p<password> <database>

# Or import your backup
mysql -h <host> -u <user> -p<password> <database> < ipl_db_backup.sql
```

**✅ Done! Save credentials for later.**

---

#### **Option B: Render.com - Free PostgreSQL (alternative)**

If you prefer PostgreSQL instead of MySQL:

1. Go to https://render.com
2. Sign up with GitHub
3. Create **New** → **PostgreSQL**
4. Name: `ipl-db`
5. Region: US (free tier)
6. Get connection string
7. **Note:** You'll need to adapt PHP to PostgreSQL or use docker

---

#### **Option C: Google Cloud SQL - Free tier with limits**

1. Go to https://console.cloud.google.com
2. Create new project
3. Enable Cloud SQL API
4. Create MySQL instance
5. Free tier includes 1 small MySQL instance
6. Get credentials from Connection Details
7. **Note:** Requires credit card, but first $300 credit covers this

---

#### **Option D: Local MySQL + Ngrok - For development**

If you already have MySQL running locally:

```bash
# Install Ngrok (expose local MySQL)
npm install -g ngrok
# or download from https://ngrok.com

# Expose port 3306
ngrok tcp 3306

# This gives public URL to your local MySQL
# Use in production APIs
```

---

### **STEP 2: Deploy PHP Backend to Railway** (15 minutes)

**Same Railway account as database!**

#### 2.1 Add PHP Service to Railway

1. In Railway, go to your existing project
2. Click **Add Service** → **GitHub Repo**
3. Select `IPL-Statistics` repository
4. Select **PHP** environment

#### 2.2 Configure Environment Variables

Click on PHP service → **Variables**

Add these (from your MySQL database setup in Step 1):

```
DB_HOST = <from MySQL Variables>
DB_PORT = 3306
DB_USER = <from MySQL Variables>
DB_PASSWORD = <from MySQL Variables>
DB_NAME = <database name>
```

#### 2.3 Set Startup Command

Click PHP service → **Settings** → **Start Command**

```
php -S 0.0.0.0:$PORT -t portal/backend
```

#### 2.4 Get Railway Public URL

- Click **Deployments**
- Find PHP service public URL (e.g., `https://your-app.up.railway.app`)
- **Save this** — will use for frontend API calls

---

### **STEP 3: Deploy ML API to Vercel** (10 minutes)

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
        ┌──────────────────────────────┐
        │   Railway MySQL Database      │
        │  (Using $5/mo free credit)    │
        │   ipl-db                      │
        └──────────────────────────────┘
```

---

## 🔑 Environment Variables Reference

### **Vercel (Python ML API)**

```env
DB_HOST=<railway-mysql-host>
DB_PORT=3306
DB_USER=<railway-mysql-user>
DB_PASSWORD=<railway-mysql-password>
DB_NAME=<railway-mysql-database>
RAILWAY_BACKEND_URL=https://your-railway-app.up.railway.app
```

### **Railway (Both PHP Backend + MySQL Database)**

PHP service variables:

```env
DB_HOST=<from MySQL Variables tab>
DB_PORT=3306
DB_USER=<from MySQL Variables tab>
DB_PASSWORD=<from MySQL Variables tab>
DB_NAME=<from MySQL Variables tab>
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
- **Railway MySQL:** https://docs.railway.app/guides/mysql
- **FastAPI Docs:** https://fastapi.tiangolo.com
- **Render.com (Alternative DB):** https://render.com/docs

### **Alternative Free Database Docs**

- **Google Cloud SQL:** https://cloud.google.com/sql/docs
- **Ngrok (Local MySQL):** https://ngrok.com/docs

---

## ✅ Deployment Checklist

- [ ] GitHub repository up to date
- [ ] Railway account created (get $5/mo free credit)
- [ ] Railway MySQL database created
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
Database: Railway MySQL (free with $5 credit)
Total Cost: $0/month
```
