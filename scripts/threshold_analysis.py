"""Анализ precision/recall при разных порогах confidence.

Запуск:
    python3 scripts/threshold_analysis.py --dataset eval_dataset.json
"""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

import matplotlib.pyplot as plt
from rapidfuzz import fuzz

from data_loader import DataLoader
from resume_parser import ResumeParser


def _load_dataset(path: Path) -> List[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("eval_dataset.json должен содержать список объектов")
    return data


def _confidence_for_skill(skill: Dict[str, Any]) -> Tuple[float, str]:
    raw_name = (skill.get("raw_name") or skill.get("name") or "").strip()
    name = (skill.get("name") or "").strip()
    if not name:
        return 0.0, "llm_unknown"

    if raw_name and raw_name.lower() == name.lower():
        return 1.0, "exact"

    ratio = fuzz.ratio(raw_name.lower(), name.lower()) if raw_name and name else 0
    if ratio > 85:
        return 0.9, "fuzzy"

    if name == raw_name and str(skill.get("classification_source") or "") == "llm_unknown":
        return 0.5, "llm_unknown"

    llm_conf = skill.get("llm_rerank_confidence")
    try:
        llm_conf = float(llm_conf) if llm_conf is not None else 0.75
    except Exception:
        llm_conf = 0.75
    return max(0.6, min(0.95, llm_conf)), "vector_llm"


def _micro_pr(predictions: List[List[str]], expected: List[List[str]]) -> Tuple[float, float, float]:
    tp = 0
    fp = 0
    fn = 0
    for pred_row, exp_row in zip(predictions, expected):
        p = set(pred_row)
        e = set(exp_row)
        tp += len(p & e)
        fp += len(p - e)
        fn += len(e - p)
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    if precision + recall == 0:
        f1 = 0.0
    else:
        f1 = 2 * precision * recall / (precision + recall)
    return precision, recall, f1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="eval_dataset.json")
    parser.add_argument("--min-threshold", type=float, default=0.50)
    parser.add_argument("--max-threshold", type=float, default=0.85)
    parser.add_argument("--step", type=float, default=0.05)
    args = parser.parse_args()

    dataset = _load_dataset(Path(args.dataset).resolve())
    data_loader = DataLoader()
    resume_parser = ResumeParser()

    parsed_rows: List[List[Dict[str, Any]]] = []
    expected_rows: List[List[str]] = []
    for row in dataset:
        resume_text = str(row.get("resume_text", ""))
        out = resume_parser.parse_skills_v2(resume_text, data_loader.skills)
        parsed_rows.append(out.get("skills", []))
        expected_rows.append([str(x) for x in row.get("expected_skills", [])])

    thresholds: List[float] = []
    precisions: List[float] = []
    recalls: List[float] = []
    f1_scores: List[float] = []

    current = args.min_threshold
    while current <= args.max_threshold + 1e-9:
        filtered_predictions: List[List[str]] = []
        for skills in parsed_rows:
            keep: List[str] = []
            for s in skills:
                conf, _band = _confidence_for_skill(s)
                if conf >= current and s.get("name"):
                    keep.append(str(s["name"]))
            filtered_predictions.append(keep)

        p, r, f1 = _micro_pr(filtered_predictions, expected_rows)
        thresholds.append(round(current, 2))
        precisions.append(p)
        recalls.append(r)
        f1_scores.append(f1)
        current += args.step

    out_dir = Path("eval_results")
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    csv_path = out_dir / f"{ts}_threshold_analysis.csv"
    png_path = out_dir / f"{ts}_threshold_pr_curve.png"

    with csv_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["threshold", "precision", "recall", "f1"])
        for t, p, r, f1 in zip(thresholds, precisions, recalls, f1_scores):
            w.writerow([t, p, r, f1])

    plt.figure(figsize=(8, 6))
    plt.plot(recalls, precisions, marker="o")
    for t, p, r in zip(thresholds, precisions, recalls):
        plt.annotate(f"{t:.2f}", (r, p), textcoords="offset points", xytext=(4, 4), fontsize=8)
    plt.xlabel("Recall")
    plt.ylabel("Precision")
    plt.title("Precision-Recall curve by confidence threshold")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(png_path, dpi=180)

    print(f"CSV: {csv_path}")
    print(f"PNG: {png_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
