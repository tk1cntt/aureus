import importlib
import pkgutil
import logging
from engine.logging_common import get_logger
from typing import List, Dict, Optional
from .signals.base import BaseSignal
from .strategies.base import BaseStrategy

logger = get_logger(__name__)
class EngineRegistry:
    """Registry for managing and discovering Signals and Strategies."""
    
    def __init__(self):
        self.signals: Dict[str, BaseSignal] = {}
        self.strategies: List[BaseStrategy] = []

    def register_signal(self, tag: str, signal_instance: BaseSignal):
        self.signals[tag] = signal_instance
        logger.info(f"Registered Signal: {tag}")

    def register_strategy(self, strategy_instance: BaseStrategy):
        self.strategies.append(strategy_instance)
        logger.info(f"Registered Strategy: {strategy_instance.name}")

    def auto_load_signals(self, package_path="engine.signals"):
        """Automatically discovers and registers all signal classes in the package."""
        try:
            package = importlib.import_module(package_path)
            for _, module_name, _ in pkgutil.iter_modules(package.__path__):
                if module_name == "base": continue
                
                full_module_name = f"{package_path}.{module_name}"
                module = importlib.import_module(full_module_name)
                
                for attribute_name in dir(module):
                    attribute = getattr(module, attribute_name)
                    if isinstance(attribute, type) and issubclass(attribute, BaseSignal) and attribute is not BaseSignal:
                        # Instantiate and use the module_name as tag, or a class attribute
                        tag = getattr(attribute, "TAG", module_name)
                        self.register_signal(tag, attribute())
        except Exception as e:
            logger.error(f"Error auto-loading signals: {e}")

    def get_signal_by_tag(self, tag: str) -> Optional[BaseSignal]:
        return self.signals.get(tag)

    def get_all_signals(self) -> Dict[str, BaseSignal]:
        return self.signals

    def get_all_strategies(self) -> List[BaseStrategy]:
        return self.strategies
