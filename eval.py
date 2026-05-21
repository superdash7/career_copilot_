"""Evaluation pipeline for resume extraction/normalization/gap analysis.

Usage:
    python3 eval.py --version v2 --verbose
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple
import random

from data_loader import DataLoader, GRADE_TO_PARAM_ORDINAL
from confidence_utils import get_skill_confidence
from eval_metrics.faithfulness import rouge_l_faithfulness
from gap_analyzer import GapAnalyzer
from plan_generator import PlanGenerator
from resume_parser import ResumeParser


@dataclass
class SampleMetrics:
    sample_id: str
    extraction_precision: float
    extraction_recall: float
    extraction_f1: float
    normalization_accuracy: float
    gap_precision: float
    gap_recall: float
    gap_f1: float
    faithfulness_rouge_l: float
    faithful: bool
    latency_sec: float
    estimated_input_tokens: int
    estimated_output_tokens: int
    estimated_cost_usd: float
    confidence_avg: float
    confidence_ece: float
    confidence_brier: float
    retrieval_hybrid_share: float
    constraint_violations: int


def _set_metrics(predicted: List[str], expected: List[str]) -> Tuple[float, float, float]:
    pred = {s.strip() for s in predicted if s and s.strip()}
    exp = {s.strip() for s in expected if s and s.strip()}
    if not pred and not exp:
        return 1.0, 1.0, 1.0
    if not pred:
        return 0.0, 0.0, 0.0
    tp = len(pred & exp)
    precision = tp / len(pred) if pred else 0.0
    recall = tp / len(exp) if exp else 0.0
    if precision + recall == 0:
        f1 = 0.0
    else:
        f1 = 2 * precision * recall / (precision + recall)
    return precision, recall, f1


def _jaccard(predicted: List[str], expected: List[str]) -> float:
    pred = {s.strip() for s in predicted if s and s.strip()}
    exp = {s.strip() for s in expected if s and s.strip()}
    union = pred | exp
    if not union:
        return 1.0
    return len(pred & exp) / len(union)


def _estimate_tokens(text: str) -> int:
    # Лёгкая приближённая оценка.
    return max(1, len((text or "").strip()) // 4)


def _estimate_cost_usd(
    input_tokens: int,
    output_tokens: int,
    input_price_per_1m: float,
    output_price_per_1m: float,
) -> float:
    return (input_tokens / 1_000_000) * input_price_per_1m + (output_tokens / 1_000_000) * output_price_per_1m


def _bootstrap_mean_ci(values: List[float], iterations: int = 500, alpha: float = 0.05) -> Dict[str, float]:
    if not values:
        return {"mean": 0.0, "ci_low": 0.0, "ci_high": 0.0}
    if len(values) == 1:
        v = float(values[0])
        return {"mean": v, "ci_low": v, "ci_high": v}
    means = []
    n = len(values)
    for _ in range(iterations):
        sample = [values[random.randrange(0, n)] for _ in range(n)]
        means.append(sum(sample) / n)
    means.sort()
    low_i = int((alpha / 2) * len(means))
    high_i = int((1 - alpha / 2) * len(means)) - 1
    low_i = max(0, min(low_i, len(means) - 1))
    high_i = max(0, min(high_i, len(means) - 1))
    return {
        "mean": float(sum(values) / n),
        "ci_low": float(means[low_i]),
        "ci_high": float(means[high_i]),
    }


def _error_taxonomy_row(
    expected_skills: List[str],
    predicted_skills: List[str],
    parsed_skills: List[Dict[str, Any]],
) -> Dict[str, int]:
    expected = {s.strip() for s in expected_skills if s and s.strip()}
    predicted = {s.strip() for s in predicted_skills if s and s.strip()}
    unknown_count = sum(1 for s in parsed_skills if bool(s.get("is_unknown")))
    llm_unknown_band = sum(1 for s in parsed_skills if str(s.get("retrieval_mode") or "") == "llm_unknown")
    fp = len(predicted - expected)
    fn = len(expected - predicted)
    return {
        "false_positives": fp,
        "false_negatives": fn,
        "unknown_skills": unknown_count,
        "llm_unknown_mode_hits": llm_unknown_band,
    }


def _calc_ece_brier(confidences: List[float], labels: List[int], bins: int = 10) -> Tuple[float, float]:
    if not confidences or not labels or len(confidences) != len(labels):
        return 0.0, 0.0
    n = len(confidences)
    ece = 0.0
    brier = 0.0
    for c, y in zip(confidences, labels):
        c = max(0.0, min(1.0, float(c)))
        brier += (c - float(y)) ** 2
    brier /= n

    for b in range(bins):
        lo = b / bins
        hi = (b + 1) / bins
        idx = [i for i, c in enumerate(confidences) if (lo <= c < hi) or (b == bins - 1 and c == 1.0)]
        if not idx:
            continue
        avg_conf = sum(confidences[i] for i in idx) / len(idx)
        avg_acc = sum(labels[i] for i in idx) / len(idx)
        ece += (len(idx) / n) * abs(avg_conf - avg_acc)
    return float(ece), float(brier)


def _plan_constraint_violations(plan_text: str) -> int:
    text = (plan_text or "").lower()
    violations = 0
    banned_tokens = [
        "курс",
        "курсы",
        "тренинг",
        "тренинги",
        "bootcamp",
        "удеми",
        "coursera",
        "skillbox",
    ]
    if any(tok in text for tok in banned_tokens):
        violations += 1
    if "книга" not in text and "книг" not in text:
        violations += 1
    return violations


def _aggregate_error_taxonomy(rows: List[Dict[str, int]]) -> Dict[str, int]:
    out = {
        "false_positives": 0,
        "false_negatives": 0,
        "unknown_skills": 0,
        "llm_unknown_mode_hits": 0,
    }
    for r in rows:
        for k in out:
            out[k] += int(r.get(k, 0))
    return out


def _run_retrieval_ablation(
    dataset: List[Dict[str, Any]],
    parser: ResumeParser,
    data_loader: DataLoader,
) -> Dict[str, Dict[str, float]]:
    from rag_service import get_skills_v2_candidates

    modes = ["dense_only", "lexical_only", "hybrid_rerank"]
    out: Dict[str, Dict[str, float]] = {}
    for mode in modes:
        f1_values: List[float] = []
        for row in dataset:
            resume_text = str(row.get("resume_text", ""))
            expected_skills = [str(x) for x in row.get("expected_skills", [])]
            raw_skills = parser._extract_raw_skills(resume_text, request_id=f"abl-{mode}")  # noqa: SLF001
            predicted: List[str] = []
            for rs in raw_skills:
                cands = get_skills_v2_candidates(rs, top_k=1, retrieval_mode=mode)
                if cands and cands[0].get("name"):
                    predicted.append(str(cands[0]["name"]))
            _p, _r, f1 = _set_metrics(predicted, expected_skills)
            f1_values.append(f1)
        ci = _bootstrap_mean_ci(f1_values)
        out[mode] = {
            "f1_mean": ci["mean"],
            "f1_ci_low": ci["ci_low"],
            "f1_ci_high": ci["ci_high"],
        }
    return out


def _load_dataset(path: Path) -> List[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("eval_dataset.json должен содержать список объектов")
    return data


def _run_resume_pipeline(
    version: str,
    parser: ResumeParser,
    resume_text: str,
    skills_dicts: List[Dict[str, Any]],
) -> Dict[str, Any]:
    if version == "v1":
        names = [(s.get("Навык") or s.get("name") or "").strip() for s in skills_dicts]
        names = [n for n in names if n]
        legacy = parser._legacy_parse_skills(resume_text, names)  # noqa: SLF001
        skills = []
        for s in legacy.get("skills", []):
            name = (s.get("name") or "").strip()
            if not name:
                continue
            skills.append({"name": name, "level": int(s.get("level") or 1)})
        return {"skills": skills, "used_fallback": False}
    return parser.parse_skills_v2(resume_text, skills_dicts)


def _build_user_skills(parsed_skills: List[Dict[str, Any]], atlas_param_names: List[str]) -> Dict[str, int]:
    # Для eval используем внутреннюю шкалу 1..3.
    user_skills: Dict[str, int] = {}
    for s in parsed_skills:
        name = (s.get("name") or "").strip()
        if not name:
            continue
        lvl = s.get("level", 1)
        try:
            lvl = int(lvl)
        except Exception:
            lvl = 1
        lvl = max(1, min(3, lvl))
        if name not in user_skills or lvl > user_skills[name]:
            user_skills[name] = lvl

    # Чтобы gap-анализ для growth совпадал с API-логикой.
    cur_param_ordinal = GRADE_TO_PARAM_ORDINAL.get("Middle", 2)
    for p in atlas_param_names:
        user_skills.setdefault(p, cur_param_ordinal)
    return user_skills


def _build_reference_tasks(data_loader: DataLoader, gap_names: List[str], target_grade: str = "Middle") -> str:
    chunks: List[str] = []
    for name in gap_names:
        detail = data_loader.get_skill_detail(name, target_grade)
        if not detail:
            continue
        tasks = (detail.get("tasks") or "").strip()
        if tasks:
            chunks.append(f"{name}: {tasks}")
    return "\n".join(chunks)


def run_eval(
    dataset: List[Dict[str, Any]],
    version: str,
    verbose: bool,
    input_price_per_1m: float,
    output_price_per_1m: float,
    retrieval_mode: Optional[str] = None,
) -> Dict[str, Any]:
    data_loader = DataLoader()
    parser = ResumeParser()
    analyzer = GapAnalyzer()
    plan_gen = PlanGenerator()
    atlas_param_names = list(data_loader.atlas_map.keys())

    per_sample: List[SampleMetrics] = []
    taxonomy_rows: List[Dict[str, int]] = []
    taxonomy_acc = {"false_positives": 0, "false_negatives": 0, "unknown_skills": 0, "llm_unknown_mode_hits": 0}

    for row in dataset:
        sample_id = str(row.get("id", "unknown"))
        resume_text = str(row.get("resume_text", ""))
        expected_skills = [str(x) for x in row.get("expected_skills", [])]
        expected_gaps = [str(x) for x in row.get("expected_gaps", [])]
        target_role = str(row.get("target_role", "")).strip() or "Менеджер продукта"

        started = time.perf_counter()
        parsed = _run_resume_pipeline(
            version,
            parser,
            resume_text,
            data_loader.skills,
            retrieval_mode=retrieval_mode,
        )
        latency = time.perf_counter() - started
        parsed_skills = parsed.get("skills", []) or []
        predicted_skills = [(s.get("name") or "").strip() for s in parsed_skills if s.get("name")]
        expected_skill_set = {s.strip() for s in expected_skills if s and s.strip()}
        confidence_vals: List[float] = []
        confidence_labels: List[int] = []
        hybrid_hits = 0
        for s in parsed_skills:
            conf, _band = get_skill_confidence(s)
            confidence_vals.append(conf)
            name = (s.get("name") or "").strip()
            confidence_labels.append(1 if name and name in expected_skill_set else 0)
            if str(s.get("retrieval_mode") or "").startswith("hybrid"):
                hybrid_hits += 1

        p, r, f1 = _set_metrics(predicted_skills, expected_skills)
        normalization_acc = _jaccard(predicted_skills, expected_skills)
        taxonomy_rows.append(_error_taxonomy_row(expected_skills, predicted_skills, parsed_skills))
        row_tax = _error_taxonomy_row(expected_skills, predicted_skills, parsed_skills)
        for k in taxonomy_acc:
            taxonomy_acc[k] += int(row_tax.get(k, 0))

        user_skills = _build_user_skills(parsed_skills, atlas_param_names)
        target_internal = data_loader.get_internal_role_name(target_role)
        reqs = data_loader.get_role_requirements(target_internal, "Middle")
        structured = analyzer.analyze_structured(user_skills, reqs, atlas_param_names, data_loader.atlas_map)
        predicted_gaps = [g.get("name", "") for g in structured.get("skill_gaps", []) if g.get("name")]

        gp, gr, gf1 = _set_metrics(predicted_gaps, expected_gaps)

        # Faithfulness: сравниваем план с задачами из clean_skills.json.
        gap_basis = expected_gaps if expected_gaps else predicted_gaps[:8]
        reference_tasks = _build_reference_tasks(data_loader, gap_basis, target_grade="Middle")
        if plan_gen.client:
            candidate_plan = plan_gen.generate_plan_702010(
                scenario_type="eval",
                step1_markdown="",
                target_name=target_role,
                context="Только для оценки faithfulness.",
                skill_context=reference_tasks,
                strong_skills=[],
                gap_summary={"skill_gaps": [{"name": n, "delta": 1} for n in gap_basis]},
            )
        else:
            candidate_plan = reference_tasks
        faithfulness = rouge_l_faithfulness(candidate_plan, reference_tasks)
        faithful = faithfulness > 0.3
        violations = _plan_constraint_violations(candidate_plan)
        ece, brier = _calc_ece_brier(confidence_vals, confidence_labels, bins=10)
        confidence_avg = sum(confidence_vals) / len(confidence_vals) if confidence_vals else 0.0
        retrieval_share = hybrid_hits / len(parsed_skills) if parsed_skills else 0.0

        # Оценка cost (упрощённо): текст резюме + выход parser.
        input_tokens = _estimate_tokens(resume_text)
        output_tokens = _estimate_tokens(json.dumps(parsed_skills, ensure_ascii=False))
        # v2 использует больше LLM-вызовов.
        if version == "v2":
            input_tokens *= 3
            output_tokens *= 3
        est_cost = _estimate_cost_usd(
            input_tokens,
            output_tokens,
            input_price_per_1m=input_price_per_1m,
            output_price_per_1m=output_price_per_1m,
        )

        m = SampleMetrics(
            sample_id=sample_id,
            extraction_precision=p,
            extraction_recall=r,
            extraction_f1=f1,
            normalization_accuracy=normalization_acc,
            gap_precision=gp,
            gap_recall=gr,
            gap_f1=gf1,
            faithfulness_rouge_l=faithfulness,
            faithful=faithful,
            latency_sec=latency,
            estimated_input_tokens=input_tokens,
            estimated_output_tokens=output_tokens,
            estimated_cost_usd=est_cost,
            confidence_avg=confidence_avg,
            confidence_ece=ece,
            confidence_brier=brier,
            retrieval_hybrid_share=retrieval_share,
            constraint_violations=violations,
        )
        per_sample.append(m)

        if verbose:
            print(
                f"[{sample_id}] F1={f1:.3f}, norm_acc={normalization_acc:.3f}, "
                f"gap_f1={gf1:.3f}, faith={faithfulness:.3f}, "
                f"ECE={ece:.3f}, viol={violations}, latency={latency:.2f}s"
            )

    def avg(fn):
        return sum(fn(x) for x in per_sample) / len(per_sample) if per_sample else 0.0

    extraction_f1_vals = [x.extraction_f1 for x in per_sample]
    norm_acc_vals = [x.normalization_accuracy for x in per_sample]
    gap_f1_vals = [x.gap_f1 for x in per_sample]
    confidence_ece_vals = [x.confidence_ece for x in per_sample]
    taxonomy = _aggregate_error_taxonomy(taxonomy_rows)
    summary = {
        "samples": len(per_sample),
        "extraction": {
            "precision": avg(lambda x: x.extraction_precision),
            "recall": avg(lambda x: x.extraction_recall),
            "f1": avg(lambda x: x.extraction_f1),
            "f1_ci95": _bootstrap_mean_ci(extraction_f1_vals),
        },
        "normalization_accuracy": avg(lambda x: x.normalization_accuracy),
        "normalization_ci95": _bootstrap_mean_ci(norm_acc_vals),
        "gap_detection": {
            "precision": avg(lambda x: x.gap_precision),
            "recall": avg(lambda x: x.gap_recall),
            "f1": avg(lambda x: x.gap_f1),
            "f1_ci95": _bootstrap_mean_ci(gap_f1_vals),
        },
        "faithfulness": {
            "avg_rouge_l": avg(lambda x: x.faithfulness_rouge_l),
            "faithful_rate": avg(lambda x: 1.0 if x.faithful else 0.0),
            "threshold": 0.3,
        },
        "confidence_calibration": {
            "avg_confidence": avg(lambda x: x.confidence_avg),
            "ece": avg(lambda x: x.confidence_ece),
            "brier": avg(lambda x: x.confidence_brier),
        },
        "retrieval_ablation": {
            "hybrid_share_avg": avg(lambda x: x.retrieval_hybrid_share),
            "mode": retrieval_mode or "hybrid_rerank",
        },
        "constraint_violations": {
            "avg_violations_per_sample": avg(lambda x: x.constraint_violations),
            "total_violations": int(sum(x.constraint_violations for x in per_sample)),
        },
        "latency_sec_avg": avg(lambda x: x.latency_sec),
        "cost": {
            "total_usd": sum(x.estimated_cost_usd for x in per_sample),
            "avg_usd_per_sample": avg(lambda x: x.estimated_cost_usd),
            "total_input_tokens": int(sum(x.estimated_input_tokens for x in per_sample)),
            "total_output_tokens": int(sum(x.estimated_output_tokens for x in per_sample)),
        },
        "bootstrap_ci": {
            "extraction_f1": _bootstrap_mean_ci(extraction_f1_vals),
            "normalization_accuracy": _bootstrap_mean_ci(norm_acc_vals),
            "gap_f1": _bootstrap_mean_ci(gap_f1_vals),
            "confidence_ece": _bootstrap_mean_ci(confidence_ece_vals),
        },
        "error_taxonomy": taxonomy,
    }
    if retrieval_mode is None:
        summary["retrieval_ablation"]["matrix"] = _run_retrieval_ablation(
            dataset=dataset,
            parser=parser,
            data_loader=data_loader,
        )

    return {
        "version": version,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "summary": summary,
        "samples": [asdict(x) for x in per_sample],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", choices=["v1", "v2"], default="v2")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--dataset", default="eval_dataset.json")
    parser.add_argument("--input-price-per-1m", type=float, default=5.0)
    parser.add_argument("--output-price-per-1m", type=float, default=15.0)
    parser.add_argument(
        "--retrieval-mode",
        choices=["dense_only", "lexical_only", "hybrid_rerank"],
        default=None,
    )
    args = parser.parse_args()

    dataset_path = Path(args.dataset).resolve()
    dataset = _load_dataset(dataset_path)
    result = run_eval(
        dataset=dataset,
        version=args.version,
        verbose=args.verbose,
        input_price_per_1m=args.input_price_per_1m,
        output_price_per_1m=args.output_price_per_1m,
        retrieval_mode=args.retrieval_mode,
    )

    out_dir = Path("eval_results")
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    out_file = out_dir / f"{ts}_{args.version}.json"
    out_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))
    print(f"\nСохранено: {out_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
