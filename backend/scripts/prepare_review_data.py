import sys
from pathlib import Path
import pandas as pd
import numpy as np

# Ensure backend root on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.config import settings
from utils.company_utils import normalize_company_name

def prepare_review_data():
    print("[Review Data Prep] Loading raw employee reviews...")
    raw_path = settings.RAW_DATA_DIR / "reviews" / "employee_reviews_raw.csv"
    if not raw_path.exists():
        print(f"Error: {raw_path} not found. Please run download_data.py first.")
        sys.exit(1)

    df = pd.read_csv(raw_path)
    print(f"-> Loaded {len(df)} raw review records. Columns: {list(df.columns)}")

    # 1. Normalize company names
    df["company"] = df["company"].fillna("Unknown").astype(str).str.strip()
    df["company_norm"] = df["company"].apply(normalize_company_name)

    # 2. Ensure standard required columns
    standard_columns = [
        "review_id", "company", "company_norm", "date", "rating", "review_text",
        "work_life_balance", "salary_benefits", "career_growth", "job_security",
        "management", "work_satisfaction", "skill_development", "culture", "workload",
        "likes", "dislikes", "source"
    ]

    for col in standard_columns:
        if col not in df.columns:
            if col in ["rating", "work_life_balance", "salary_benefits", "career_growth", "job_security",
                       "management", "work_satisfaction", "skill_development", "culture", "workload"]:
                df[col] = 3.0
            else:
                df[col] = ""

    # Ensure ratings are numeric bounded in [1.0, 5.0]
    rating_cols = ["rating", "work_life_balance", "salary_benefits", "career_growth", "job_security",
                   "management", "work_satisfaction", "skill_development", "culture", "workload"]
    for col in rating_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(3.0).clip(1.0, 5.0).round(1)

    # Filter out empty review texts
    df["review_text"] = df["review_text"].fillna("").astype(str).str.strip()
    df = df[df["review_text"].str.len() > 10]

    # Save to processed directory
    out_file = settings.PROCESSED_REVIEWS_FILE
    out_file.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_file, index=False)
    print(f"[Review Data Prep] Successfully normalized and saved {len(df)} employee reviews across {df['company'].nunique()} companies to {out_file}")

if __name__ == "__main__":
    prepare_review_data()
