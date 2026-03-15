import logging
from typing import Dict, List, Any, Type
from .base import BaseStrategy

logger = logging.getLogger("aureus-signal.strategy-registry")

class StrategyRegistry:
    """Registry for managing and executing trading strategies."""
    
    def __init__(self):
        self._strategies: Dict[str, BaseStrategy] = {}

    def clear(self):
        """Clears all registered strategies."""
        self._strategies = {}

    def register(self, strategy: BaseStrategy):
        """Registers a strategy instance."""
        self._strategies[strategy.name] = strategy
        logger.info(f"[GLOBAL] [register] 1... Strategy registered: {strategy.name}")

    async def load_from_db(self, db, symbol: str):
        """
        Loads active strategies for a symbol from PostgreSQL.
        Supports both TemplateStrategy and specialized classes.
        """
        query = """
            SELECT t.id
            FROM aureus_strategy_templates t
            JOIN aureus_symbol_strategies ss ON t.id = ss.strategy_id
            WHERE ss.symbol = $1 AND ss.is_active = true
        """
        rows = await db.fetch(query, symbol)
        strategy_ids = [r['id'] for r in rows]
        await self.load_by_ids(db, symbol, strategy_ids)

    async def load_by_ids(self, db, symbol: str, strategy_ids: List[int]):
        """
        Loads strategies by their template IDs, regardless of 'active' status for the symbol.
        Uses template defaults if no symbol-specific override is found.
        """
        from .template import TemplateStrategy
        from .trend_continuation import TrendContinuationStrategy
        from .order_flow_dominance import OrderFlowDominanceStrategy
        import json

        # Mapping of Template Name to Strategy Class
        STRATEGY_MAP: Dict[str, Type[BaseStrategy]] = {
            "TREND_CONT": TrendContinuationStrategy,
            "SESSION_SWEEP": TrendContinuationStrategy,
            "ORDER_FLOW_DOM": OrderFlowDominanceStrategy
        }

        if not strategy_ids:
            self.clear()
            return

        # Query templates and join with symbol-specific overrides (if they exist)
        query = """
            SELECT t.id, t.name, t.config, t.min_score
            FROM aureus_strategy_templates t
            LEFT JOIN aureus_symbol_strategies ss ON t.id = ss.strategy_id AND ss.symbol = $1
            WHERE t.id = ANY($2)
        """
        rows = await db.fetch(query, symbol, strategy_ids)
        
        self.clear()
        for r in rows:
            name = r['name']
            config = json.loads(r['config']) if isinstance(r['config'], str) else r['config']
            config['id'] = r['id']
            config['name'] = name
            config['min_score_threshold'] = r['min_score']
            
            # Select class based on map, fallback to TemplateStrategy
            strat_class = STRATEGY_MAP.get(name, TemplateStrategy)
            strat = strat_class(config)
            
            self.register(strat)
            
        logger.info(f"[{symbol}] [load_by_ids] 1... Loaded {len(rows)} strategies (Target IDs: {strategy_ids})")

    def evaluate_all(self, df, signals, state_obj) -> List[Dict[str, Any]]:
        """Evaluates all registered strategies and returns signals for those that trigger."""
        triggered = []
        for name, strategy in self._strategies.items():
            try:
                result = strategy.evaluate(df, signals, state_obj)
                if result:
                    triggered.append(result)
            except Exception as e:
                logger.error(f"[GLOBAL] [evaluate_all] Error: Evaluating strategy {name}: {e}")
        return triggered

    def get_strategy(self, name: str) -> BaseStrategy:
        return self._strategies.get(name)

    def list_strategies(self) -> List[str]:
        return list(self._strategies.keys())
