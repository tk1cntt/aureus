from __future__ import annotations


def _round6(value: float) -> float:
    return round(float(value), 6)


def update_aggregate_score(records, strategy_name, symbol, timeframe, score_version):
    group_key = f"{strategy_name}|{symbol}|{timeframe}"

    filtered_scores = []
    for record in records or []:
        if record.get("score_version") != score_version:
            continue
        score = record.get("score_total")
        if score is None:
            continue
        filtered_scores.append(float(score))

    aggregate_score = None
    if filtered_scores:
        aggregate_score = _round6(sum(filtered_scores) / len(filtered_scores))

    return {
        "aggregate_score": aggregate_score,
        "trade_count": len(filtered_scores),
        "score_version": score_version,
        "group_key": group_key,
        "strategy": strategy_name,
        "symbol": symbol,
        "timeframe": timeframe,
    }
