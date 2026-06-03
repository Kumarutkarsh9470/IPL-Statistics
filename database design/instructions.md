# IPL Statistics & Predictions Portal Setup

Follow these instructions to set up the data pipeline, configure your database, and run the backend/frontend portal locally.

## 1. Prerequisites
- **Python 3.x**
- **XAMPP** 

Install the required Python packages by running:
```bash
pip install -r requirements.txt
```

## 2. Fetch the Raw Dataset
To keep the repository lightweight, raw data is excluded (`.gitignore`). You must download it manually:
1. Go to Kaggle: [IPL Dataset 2008-2025](https://www.kaggle.com/datasets/chaitu20/ipl-dataset2008-2025).
2. Download and extract the archive.
3. Rename the core dataset file to **`IPL.csv`**.
4. Place `IPL.csv` exactly inside the `data/raw/` directory in this project.

## 3. Database Credentials
The scripts use a dedicated local MySQL user to avoid using `root`. Open your MySQL console or PHPMyAdmin and create the following user with all privileges.
- **User:** `ipl_user`
- **Password:** `password123`
*(Note: If you want to use a different user like `root`, simply update the credentials at the top of `import_ipl.py` and inside `portal/backend/db.php`.)*

## 4. Run the Database Creation Pipeline
Open your terminal in the project's root directory and run:

1. **Clean & Standardize**:
   ```bash
   python EDA/process.py
   ```
   *This generates the cleaned dataset at `data/processed/cleaned_IPL.csv`.*

2. **Populate the Database**:
   ```bash
   python import_ipl.py
   ```
   *This script automatically creates the `ipl_db` database from cleaned data.*

## 5. Connecting Apache (Symlinking)
To serve the portal without moving your repository out of your development folder, we map it into XAMPP's `htdocs` via a symbolic link.

**For Linux Users:**
Open your terminal and run:
```bash
sudo ln -s /path/to/your/clone/IPL-statistics-predictions /opt/lampp/htdocs/IPL-statistics-predictions
```

**For Windows Users:**
Open **Command Prompt as Administrator** and run:
```cmd
mklink /D "C:\xampp\htdocs\IPL-statistics-predictions" "C:\path\to\your\clone\IPL-statistics-predictions"
```
*(Replace `/path/to/your/clone/` with the actual path to this repository on your machine).* 

## 6. Launch the Portal
1. Open the XAMPP Control Panel.
2. Ensure both **Apache** and **MySQL** are running.
3. Visit [http://localhost/IPL-statistics-predictions/portal/](http://localhost/IPL-statistics-predictions/portal/) in your browser.
