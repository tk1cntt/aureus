import ast
from pathlib import Path


SEED_PATH = Path(__file__).resolve().parents[1] / "engine" / "strategies" / "seed_strategies.py"
EXPECTED = {
    "TPO_VA_REJECTION_BULL": ("tpo_va_rejection_bull", "BUY"),
    "TPO_VA_REJECTION_BEAR": ("tpo_va_rejection_bear", "SELL"),
    "TPO_VA_BREAKOUT_BULL": ("tpo_va_breakout_bull", "BUY"),
    "TPO_VA_BREAKOUT_BEAR": ("tpo_va_breakout_bear", "SELL"),
    "TPO_TREND_PULLBACK_BULL": ("tpo_trend_pullback_bull", "BUY"),
    "TPO_TREND_PULLBACK_BEAR": ("tpo_trend_pullback_bear", "SELL"),
}
TOP_KEYS = {"name", "is_active", "description", "min_score", "config"}
CONFIG_KEYS = {"min_score_threshold", "context_filters", "sequence", "trade_execution"}
SEQUENCE_KEYS = {"tag", "weight", "required", "max_wait", "reset_signals"}
TRADE_KEYS = {
    "direction",
    "entry_type",
    "entry_method",
    "size_mode",
    "size_value",
    "sl",
    "tp",
    "trailing",
    "capital_risk_pct",
    "early_exits",
}


def _strategy_templates():
    module = ast.parse(SEED_PATH.read_text(encoding="utf-8"))
    for node in module.body:
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "seed_system_strategies":
            for stmt in node.body:
                if isinstance(stmt, ast.Assign):
                    for target in stmt.targets:
                        if isinstance(target, ast.Name) and target.id == "strategies":
                            return ast.literal_eval(stmt.value)
    raise AssertionError("strategies literal not found")


def test_tpo_seed_templates_exist_with_expected_tags_and_directions():
    templates = {item["name"]: item for item in _strategy_templates()}

    assert set(EXPECTED).issubset(templates)
    for name, (tag, direction) in EXPECTED.items():
        template = templates[name]
        sequence_tags = [item["tag"] for item in template["config"]["sequence"]]

        assert tag in sequence_tags
        assert template["config"]["trade_execution"]["direction"] == direction


def test_tpo_seed_templates_match_contract_shape():
    templates = {item["name"]: item for item in _strategy_templates() if item["name"] in EXPECTED}

    for template in templates.values():
        assert TOP_KEYS <= set(template)
        config = template["config"]
        assert CONFIG_KEYS <= set(config)
        assert config["context_filters"]
        assert all(item.get("type") == "tpo_context" for item in config["context_filters"])
        assert {"D1", "H1", "M30"} <= set(config["context_filters"][0]["timeframes"])
        for sequence_item in config["sequence"]:
            assert SEQUENCE_KEYS <= set(sequence_item)
        assert TRADE_KEYS <= set(config["trade_execution"])
