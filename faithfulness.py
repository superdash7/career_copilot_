"""Faithfulness-метрика на основе ROUGE-L."""

from rouge_score import rouge_scorer


def rouge_l_faithfulness(candidate_text: str, reference_text: str) -> float:
    candidate = (candidate_text or "").strip()
    reference = (reference_text or "").strip()
    if not candidate or not reference:
        return 0.0
    scorer = rouge_scorer.RougeScorer(["rougeL"], use_stemmer=False)
    score = scorer.score(reference, candidate)["rougeL"].fmeasure
    return float(score)


def is_faithful(candidate_text: str, reference_text: str, threshold: float = 0.3) -> bool:
    return rouge_l_faithfulness(candidate_text, reference_text) > threshold
