TPO_TAG_MAPPING = {
    ("va_rejection", "long"): "tpo_va_rejection_bull",
    ("va_rejection", "short"): "tpo_va_rejection_bear",
    ("va_breakout_acceptance", "long"): "tpo_va_breakout_bull",
    ("va_breakout_acceptance", "short"): "tpo_va_breakout_bear",
    ("trend_pullback", "long"): "tpo_trend_pullback_bull",
    ("trend_pullback", "short"): "tpo_trend_pullback_bear",
}


def tpo_strategy_tags_from_candidates(candidates, min_score=0.75):
    tags = []
    debug = []
    sides = set()

    for candidate in candidates:
        setup = candidate.get("setup")
        side = candidate.get("side")
        reasons = list(candidate.get("reasons") or [])
        tag = TPO_TAG_MAPPING.get((setup, side))
        item = {
            "setup": setup,
            "side": side,
            "score": candidate.get("score", 0.0),
            "tag": tag,
            "reasons": reasons,
        }

        if not candidate.get("valid", False):
            item["status"] = "invalid"
            debug.append(item)
            continue
        if side is None:
            item["status"] = "missing_side"
            debug.append(item)
            continue
        if tag is None:
            item["status"] = "unknown_mapping"
            debug.append(item)
            continue
        if candidate.get("score", 0.0) < min_score:
            item["status"] = "below_min_score"
            debug.append(item)
            continue

        item["status"] = "emitted"
        debug.append(item)
        tags.append(tag)
        sides.add("bull" if side == "long" else "bear")

    if len(sides) > 1:
        return {
            "tags": [],
            "suppressed": True,
            "reasons": ["conflicting_tpo_sides"],
            "debug": [item for item in debug if item.get("status") == "emitted"],
        }

    return {"tags": tags, "suppressed": False, "reasons": [], "debug": debug}
