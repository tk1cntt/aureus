from .template import TemplateStrategy

def get_smc_trend_scalping_strategy():
    config = {
        "name": "SMC_Trend_Scalping",
        "weight": 10.0,
        "min_score_threshold": 20.0, # High confluence required
        "sequence": [
            {"tag": "ema_200_up", "weight": 5.0, "required": True},   # Long term trend
            {"tag": "choch_up", "weight": 8.0, "required": True},    # Market structure shift
            {"tag": "sweep_bull", "weight": 7.0, "required": True},  # Liquidity grab
            {"tag": "fvg_up", "weight": 3.0, "required": False},     # Displacement confirmation
            {"tag": "ema_21_up", "weight": 2.0, "required": False}   # Short term momentum
        ]
    }
    return TemplateStrategy(config)
