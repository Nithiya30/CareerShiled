import sys
import json
from pathlib import Path
import pandas as pd
import joblib

from sklearn.metrics import classification_report, confusion_matrix

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.config import settings

def evaluate():
    print("[CareerShield Model Evaluation]")
    if not settings.METRICS_PATH.exists():
        print(f"Metrics file {settings.METRICS_PATH} not found. Please train models first.")
        return

    with open(settings.METRICS_PATH, "r", encoding="utf-8") as f:
        metrics = json.load(f)

    print("=" * 60)
    print("CAREERSHIELD EMPIRICAL EVALUATION METRICS REPORT")
    print("=" * 60)
    print(f"Trained Timestamp : {metrics.get('trained_at')}")
    print(f"Training Samples  : {metrics.get('training_samples')}")
    print(f"Test Samples      : {metrics.get('test_samples')}")
    print(f"TF-IDF Features   : {metrics.get('features_count')}")
    print("-" * 60)

    lr = metrics.get("logistic_regression", {})
    svm = metrics.get("linear_svm", {})

    print(f"{'Metric':<15} | {'Logistic Regression':<20} | {'Linear SVM':<15}")
    print("-" * 60)
    for m in ["accuracy", "precision", "recall", "f1", "roc_auc", "pr_auc"]:
        lr_val = lr.get(m, 0.0)
        svm_val = svm.get(m, 0.0)
        print(f"{m.upper():<15} | {lr_val*100:>18.2f}% | {svm_val*100:>13.2f}%")
    print("=" * 60)

if __name__ == "__main__":
    evaluate()
