# IPL Statistics & Predictions

A full-stack IPL analytics and machine learning project for DA214 Database Management Systems.

## Team

- Debarghya Das - 241050049
- Ritwik Viswanathan - 240150043
- Maimoona Saifee - 240150031
- Kumar Utkatsh - 240150016
- Shafqat Jabbar - 240150019
- Huzefa Bhagat - 240150012

---

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Copy environment example and set secrets
copy .env.example .env
# Edit .env to set DB credentials and any API keys

# 3. Prepare data (place data/raw/IPL.csv first)
python EDA/process.py

# 3. Load into MySQL and train models
python import_ipl.py
python -m ml.features.build_features
python -m ml.train.train_match_outcome
python -m ml.train.train_score_predictor
python -m ml.train.train_player_perf

# 4. Start inference API
uvicorn ml.serve:app --host 0.0.0.0 --port 8000

# 5. Open portal (if using XAMPP)
# http://localhost/IPL-statistics-predictions/portal/
```

Refer to the Quick Start above for setup and architecture notes.

---

## Key Features

- **Data Engineering**: Ball-by-ball cleaning, EDA, and normalized MySQL loading
- **Machine Learning**: Match outcome, score projection, and player performance predictions
- **REST API**: FastAPI inference service with JSON responses
- **Dashboard**: Interactive web portal with analytics and predictions
- **Natural Language**: SQL query interface via Groq API
- **Robust player metadata enrichment**: Batting style, Bowling type added for all players
- **Venue details calculation**: Inferred the average boundary distance from online sources and calculated the outfield speed with a heuristic

---

## Tech Stack

| Component | Technology |
|-----------|------------|
| Data Processing | Python (pandas, numpy, scikit-learn) |
| Machine Learning | XGBoost, Random Forest, scikit-learn |
| Database | MySQL 5.7+ (normalized schema) |
| Backend APIs | FastAPI, PHP |
| Frontend | HTML5, CSS, JavaScript, Chart.js |
| Features | joblib, SQLAlchemy |
| Optional NL Queries | Groq API |

---

## Repository Structure (complete)

```
IPL-statistics-predictions/
├─ database design/
│  ├─ mysql_schema.sql
│  ├─ schema.sql
│  ├─ db_design.md
│  ├─ load_venue_data.py
│  ├─ instructions.md
│  ├─ ideas.txt
│  └─ .env
├─ data/
│  ├─ processed/
│  │  └─ cleaned_IPL.csv
│  └─ raw/
│     ├─ IPL.csv
│     ├─ player_profile_template.csv
│     ├─ player_profile.csv
│     ├─ venue_conditions_template.csv
│     └─ venue_conditions.csv
├─ EDA/
│  ├─ eda_pipeline.py
│  ├─ IPLstatsEDA.ipynb
│  ├─ process.py
│  └─ eda_outputs/
│     ├─ eda_report.md
│     └─ plots/
├─ eda_outputs/
│  └─ plots/
├─ ml/
│  ├─ __init__.py
│  ├─ build_lookups.py
│  ├─ config.py
│  ├─ db_connect.py
│  ├─ predict.py
│  ├─ serve.py
│  ├─ train_models.py
│  ├─ utils.py
│  ├─ evaluation/
│  │  ├─ match_outcome_report.json
│  │  ├─ player_batting_report.json
│  │  ├─ player_bowling_report.json
│  │  └─ score_predictor_report.json
│  ├─ features/
│  │  ├─ __init__.py
│  │  ├─ build_features.py
│  │  ├─ innings_features.py
│  │  ├─ match_features.py
│  │  ├─ player_features.py
│  │  └─ data/
│  │     ├─ batting_features.csv
│  │     ├─ bowling_features.csv
│  │     ├─ innings_features.csv
│  │     └─ match_features.csv
│  ├─ models/
│  │  ├─ feature_lookups.joblib
│  │  ├─ match_outcome_features.json
│  │  ├─ match_outcome.joblib
│  │  ├─ player_batting_meta.json
│  │  ├─ player_batting.joblib
│  │  ├─ player_bowling_meta.json
│  │  ├─ player_bowling.joblib
│  │  ├─ score_predictor_meta.json
│  │  └─ score_predictor.joblib
│  └─ routes/
│     ├─ __init__.py
│     ├─ chase_predict.py
│     ├─ match_predict.py
│     ├─ player_predict.py
│     ├─ score_predict.py
│     └─ top_performers_predict.py
├─ portal/
│  ├─ index.html
│  ├─ backend/
│  │  ├─ db.php
│  │  └─ api/
│  │     ├─ fortress.php
│  │     ├─ h2h.php
│  │     ├─ leaderboard.php
│  │     ├─ matchup.php
│  │     ├─ nl_query.php
│  │     ├─ predict.php
│  │     ├─ season_analysis.php
│  │     ├─ seasons.php
│  │     ├─ team_performance.php
│  │     ├─ teams.php
│  │     ├─ toss.php
│  │     ├─ venue_insights.php
│  │     └─ venues.php
│  ├─ css/
│  │  └─ style.css
│  └─ js/
│     └─ main.js
├─ train/
│  ├─ __init__.py
│  ├─ train_match_outcome.py
│  ├─ train_player_perf.py
│  └─ train_score_predictor.py
├─ import_ipl.py
├─ requirements.txt
├─ .gitignore
├─ .env
└─ README.md
```

---

## Setup Guide

### Prerequisites

- Python 3.10+
- MySQL 5.7+ (or MariaDB)
- XAMPP (Apache + PHP + MySQL) for portal (optional)
- Git

### Step 1: Clone & Install

```bash
git clone <repo-url>
cd IPL-statistics-predictions
pip install -r requirements.txt
```

### Step 2: Configure MySQL (example)

```sql
CREATE USER 'ipl_user'@'127.0.0.1' IDENTIFIED BY 'password123';
GRANT ALL PRIVILEGES ON ipl_db.* TO 'ipl_user'@'127.0.0.1';
FLUSH PRIVILEGES;
```

### Step 3: Setup Environment

```bash
# Create .env manually at project root and add:
# GROQ_API_KEY=your_key_here
# GROQ_MODEL=llama-3.1-8b-instant
```

### Step 4: Prepare Data

Place `IPL.csv` in `data/raw/`.

Metadata CSVs are optional:
- `data/raw/player_profile.csv`
- `data/raw/venue_conditions.csv`

If you do not have them, use the template files already in `data/raw/`:
- `player_profile_template.csv`
- `venue_conditions_template.csv`

Pipeline behavior without these files:
- ETL still runs successfully.
- Player style fields remain null when player profile data is missing.
- Venue outfield speed can still be partially inferred from match data.

### Step 5: Run Pipeline

Follow the Quick Start commands above to run the full pipeline.

---

## API Endpoints

FastAPI (http://localhost:8000/api) implements prediction endpoints. See the API Endpoints section in this README for request/response examples.

---

## Database Schema

Normalized schema includes `teams`, `venues`, `players`, `matches`, `deliveries`, and `venue_conditions`.
See `database design/mysql_schema.sql` for full DDL.

---

## ML Models

Key models live in `ml/models/` as joblib artifacts. Training scripts are in `ml/train/`.

---

## Project Workflows

- Data → cleaning → MySQL → features → training → models
- Inference via `ml/serve.py` (FastAPI)
- Portal uses PHP endpoints to read from MySQL and render visualizations

---

## Common Tasks

Train models:
```bash
python -m ml.features.build_features
python -m ml.train.train_match_outcome
```

Inspect a model:
```bash
python -c "import joblib; m = joblib.load('ml/models/match_outcome.joblib'); print(type(m))"
```

Check cleaned data:
```bash
head -5 data/processed/cleaned_IPL.csv
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "MySQL connection refused" | Ensure MySQL is running (`systemctl start mysql` or XAMPP control panel) |
| "Model file not found" | Re-run training: `python -m ml.train.train_match_outcome` |
| "FastAPI timeout" | Ensure port 8000 is available: `lsof -i :8000` |
| "Empty dashboard tables" | Check MySQL import completed: `python import_ipl.py` |
| "Feature mismatch error" | Rebuild features: `python -m ml.features.build_features` |

---

## Evaluation Reports

Model performance reports are saved to `ml/evaluation/`:

- `match_outcome_report.json` â€” ROC-AUC, accuracy, confusion matrix
- `score_predictor_report.json` â€” RMSE, MAE, prediction intervals
- `player_batting_report.json` â€” RÂ², residual analysis
- `player_bowling_report.json` â€” RÂ², residual analysis

---

## Future Improvements

- [ ] Automated test suite (pytest)
- [ ] CI/CD pipeline (GitHub Actions)
- [ ] Model versioning & drift monitoring
- [ ] Docker Compose for reproducible setup
- [ ] GraphQL API alternative
- [ ] Real-time live match predictions
- [ ] Player injury impact modeling

---
