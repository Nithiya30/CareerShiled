import sys
from pathlib import Path
import pandas as pd
import numpy as np

# Ensure backend root on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.config import settings
from utils.text_utils import combine_job_text, clean_text

def prepare_job_data():
    print("[Job Data Prep] Loading raw job fraud corpora...")
    raw_path = settings.RAW_DATA_DIR / "job_fraud" / "emscad_raw.csv"
    if not raw_path.exists():
        print(f"Error: {raw_path} not found. Please run download_data.py first.")
        sys.exit(1)

    df = pd.read_csv(raw_path)
    print(f"-> Loaded {len(df)} raw rows. Columns: {list(df.columns)}")

    # 1. Handle Duplicates
    dup_count = df.duplicated(subset=["title", "description"]).sum()
    if dup_count > 0:
        print(f"-> Removing {dup_count} duplicate records...")
        df = df.drop_duplicates(subset=["title", "description"])

    # 2. Handle Missing Values
    text_cols = ["title", "company_profile", "description", "requirements", "benefits",
                 "location", "department", "industry", "function", "employment_type",
                 "required_experience", "required_education", "salary_range"]
    
    for col in text_cols:
        if col in df.columns:
            df[col] = df[col].fillna("").astype(str).str.strip()

    # 3. Normalize Labels
    # Ensure binary integer target (0 = legitimate, 1 = fraudulent)
    if "fraudulent" in df.columns:
        df["fraudulent"] = df["fraudulent"].astype(int)
    elif "label" in df.columns:
        df["fraudulent"] = df["label"].apply(lambda x: 1 if str(x).lower() in ["1", "fake", "fraud"] else 0)

    # 4. Synthesize Combined Text Representation
    print("-> Concatenating and cleaning structured textual fields...")
    combined_texts = []
    cleaned_texts = []

    for _, row in df.iterrows():
        row_dict = row.to_dict()
        combined = combine_job_text(row_dict)
        combined_texts.append(combined)
        cleaned_texts.append(clean_text(combined))

    df["combined_text"] = combined_texts
    df["cleaned_text"] = cleaned_texts

    # Filter out empty or trivially short rows
    initial_len = len(df)
    df = df[df["cleaned_text"].str.len() > 20]
    print(f"-> Retained {len(df)} / {initial_len} valid postings after length filtering.")

    # 5. Class Balance Inspection
    counts = df["fraudulent"].value_counts()
    print(f"-> Final Class distribution: Legitimate (0): {counts.get(0, 0)}, Fraudulent (1): {counts.get(1, 0)}")

    # 6. Save Processed Dataset
    out_file = settings.PROCESSED_JOBS_FILE
    out_file.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_file, index=False)
    print(f"[Job Data Prep] Successfully processed and saved {len(df)} jobs to {out_file}")

if __name__ == "__main__":
    prepare_job_data()
