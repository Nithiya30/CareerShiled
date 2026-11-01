import os
import sys
import json
import joblib
import datetime
from pathlib import Path
import pandas as pd
import numpy as np

from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.svm import LinearSVC
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    average_precision_score,
    classification_report
)

# Ensure backend root on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.config import settings

def train_and_evaluate():
    print("[CareerShield ML Engine] Commencing training pipeline...")
    
    # 1. Load Processed Data
    data_path = settings.PROCESSED_JOBS_FILE
    if not data_path.exists():
        print(f"Error: {data_path} not found. Running prepare_job_data.py first...")
        from scripts.prepare_job_data import prepare_job_data
        prepare_job_data()

    df = pd.read_csv(data_path)
    print(f"-> Loaded {len(df)} processed job samples.")

    X = df["cleaned_text"].astype(str)
    y = df["fraudulent"].astype(int)

    # 2. Stratified Train/Test Split (Prevent Data Leakage)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.25, random_state=42, stratify=y
    )
    print(f"-> Train split: {len(X_train)} samples (Fraud: {y_train.sum()})")
    print(f"-> Test split:  {len(X_test)} samples (Fraud: {y_test.sum()})")

    # 3. TF-IDF Vectorization
    print("-> Fitting TF-IDF Vectorizer (ngram_range=(1,2), sublinear_tf=True)...")
    vectorizer = TfidfVectorizer(
        ngram_range=(1, 2),
        sublinear_tf=True,
        max_features=10000,
        stop_words="english"
    )
    X_train_vec = vectorizer.fit_transform(X_train)
    X_test_vec = vectorizer.transform(X_test)

    # 4. Train Model 1: Logistic Regression (Primary)
    print("-> Training Logistic Regression with balanced class weights...")
    lr_model = LogisticRegression(
        class_weight="balanced",
        max_iter=1000,
        random_state=42,
        solver="lbfgs"
    )
    lr_model.fit(X_train_vec, y_train)

    # Predictions & Probabilities
    lr_preds = lr_model.predict(X_test_vec)
    lr_probs = lr_model.predict_proba(X_test_vec)[:, 1]

    lr_acc = float(accuracy_score(y_test, lr_preds))
    lr_prec = float(precision_score(y_test, lr_preds, zero_division=0))
    lr_rec = float(recall_score(y_test, lr_preds, zero_division=0))
    lr_f1 = float(f1_score(y_test, lr_preds, zero_division=0))
    lr_roc = float(roc_auc_score(y_test, lr_probs))
    lr_pr = float(average_precision_score(y_test, lr_probs))

    print(f"   [Logistic Regression] Acc: {lr_acc:.4f} | Prec: {lr_prec:.4f} | Rec: {lr_rec:.4f} | F1: {lr_f1:.4f} | ROC: {lr_roc:.4f} | PR-AUC: {lr_pr:.4f}")

    # 5. Train Model 2: Linear SVM for Empirical Comparison (Section 33)
    print("-> Training Linear SVM (Calibrated) for comparison...")
    base_svm = LinearSVC(
        class_weight="balanced",
        random_state=42,
        max_iter=2000,
        dual="auto"
    )
    calibrated_svm = CalibratedClassifierCV(base_svm, cv=3)
    calibrated_svm.fit(X_train_vec, y_train)

    svm_preds = calibrated_svm.predict(X_test_vec)
    svm_probs = calibrated_svm.predict_proba(X_test_vec)[:, 1]

    svm_acc = float(accuracy_score(y_test, svm_preds))
    svm_prec = float(precision_score(y_test, svm_preds, zero_division=0))
    svm_rec = float(recall_score(y_test, svm_preds, zero_division=0))
    svm_f1 = float(f1_score(y_test, svm_preds, zero_division=0))
    svm_roc = float(roc_auc_score(y_test, svm_probs))
    svm_pr = float(average_precision_score(y_test, svm_probs))

    print(f"   [Linear SVM]          Acc: {svm_acc:.4f} | Prec: {svm_prec:.4f} | Rec: {svm_rec:.4f} | F1: {svm_f1:.4f} | ROC: {svm_roc:.4f} | PR-AUC: {svm_pr:.4f}")

    # 6. Save Model Artifacts
    settings.MODELS_DIR.mkdir(parents=True, exist_ok=True)
    settings.ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

    joblib.dump(lr_model, settings.JOB_MODEL_PATH)
    joblib.dump(vectorizer, settings.VECTORIZER_PATH)
    joblib.dump(calibrated_svm, settings.SVM_MODEL_PATH)
    print(f"-> Saved model files to {settings.MODELS_DIR}")

    # 7. Save Actual Measured Metrics JSON (Never Hardcoded!)
    metrics_data = {
        "trained_at": datetime.datetime.utcnow().isoformat(),
        "training_samples": int(len(X_train)),
        "test_samples": int(len(X_test)),
        "features_count": int(X_train_vec.shape[1]),
        "logistic_regression": {
            "accuracy": round(lr_acc, 4),
            "precision": round(lr_prec, 4),
            "recall": round(lr_rec, 4),
            "f1": round(lr_f1, 4),
            "roc_auc": round(lr_roc, 4),
            "pr_auc": round(lr_pr, 4)
        },
        "linear_svm": {
            "accuracy": round(svm_acc, 4),
            "precision": round(svm_prec, 4),
            "recall": round(svm_rec, 4),
            "f1": round(svm_f1, 4),
            "roc_auc": round(svm_roc, 4),
            "pr_auc": round(svm_pr, 4)
        }
    }

    with open(settings.METRICS_PATH, "w", encoding="utf-8") as f:
        json.dump(metrics_data, f, indent=2)
    print(f"-> Saved real measured metrics to {settings.METRICS_PATH}")
    print("[CareerShield ML Engine] Training completed successfully.")

if __name__ == "__main__":
    train_and_evaluate()
