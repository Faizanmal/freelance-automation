"""Offline ranking metrics — Precision@k, nDCG@k, recall, duplicate rate."""

from __future__ import annotations

import math
from typing import Iterable, Sequence


def precision_at_k(ranked_ids: Sequence[str], relevant: set[str], k: int) -> float:
    if k <= 0:
        return 0.0
    top = list(ranked_ids)[:k]
    if not top:
        return 0.0
    hits = sum(1 for item in top if item in relevant)
    return hits / len(top)


def recall_at_k(ranked_ids: Sequence[str], relevant: set[str], k: int) -> float:
    if not relevant:
        return 0.0
    top = set(list(ranked_ids)[:k])
    return len(top & relevant) / len(relevant)


def dcg_at_k(relevances: Sequence[float], k: int) -> float:
    total = 0.0
    for index, rel in enumerate(list(relevances)[:k]):
        total += (2**rel - 1) / math.log2(index + 2)
    return total


def ndcg_at_k(
    ranked_ids: Sequence[str],
    graded: dict[str, float],
    k: int,
) -> float:
    relevances = [float(graded.get(item_id, 0.0)) for item_id in list(ranked_ids)[:k]]
    ideal = sorted(graded.values(), reverse=True)
    ideal_dcg = dcg_at_k(ideal, k)
    if ideal_dcg <= 0:
        return 0.0
    return dcg_at_k(relevances, k) / ideal_dcg


def duplicate_rate(keys: Iterable[str]) -> float:
    items = list(keys)
    if not items:
        return 0.0
    return 1.0 - (len(set(items)) / len(items))


def summarize_run(
    *,
    ranked_ids: Sequence[str],
    relevant: set[str],
    graded: dict[str, float],
    duplicate_keys: Sequence[str],
    latency_ms: float,
    cost_usd: float = 0.0,
) -> dict[str, float]:
    return {
        "precision_at_5": round(precision_at_k(ranked_ids, relevant, 5), 4),
        "precision_at_10": round(precision_at_k(ranked_ids, relevant, 10), 4),
        "ndcg_at_10": round(ndcg_at_k(ranked_ids, graded, 10), 4),
        "recall_at_20": round(recall_at_k(ranked_ids, relevant, 20), 4),
        "duplicate_rate": round(duplicate_rate(duplicate_keys), 4),
        "latency_ms": round(latency_ms, 2),
        "cost_usd": round(cost_usd, 6),
    }
