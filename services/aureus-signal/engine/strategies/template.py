import json
from .base import BaseStrategy
import pandas as pd
from typing import Dict, Any, Optional

class TemplateStrategy(BaseStrategy):
    """
    Advanced strategy based on a weighted sequence of signal tags.
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(
            config['name'], 
            strategy_id=config.get('id', 0), 
            weight=config.get('weight', 1.0)
        )
        self.min_score = config.get('min_score_threshold', 10.0)
        self.sequence = config.get('sequence', []) # List of {tag, weight, required}
        self.exit_config = config.get('exit_config', {})

    def evaluate(self, df: pd.DataFrame, signals: Dict[str, Any], state_obj: Any) -> Optional[Dict[str, Any]]:
        total_score = 0.0
        details = []
        last_found_index = -1
        missing_required = False
        
        history = state_obj.signal_history
        sequence_progress = [] # Track status of each step for UI
        matched_steps = 0
        origin_timestamp = None
        
        # Optimization: Pre-calculate last seen indices for all tags in history (O(N))
        # This makes the reset check O(1) inside the sequence loop.
        last_seen_index = {}
        for i, item in enumerate(history):
            last_seen_index[item['tag']] = i

        for i, step in enumerate(self.sequence):
            tag = step['tag']
            weight = step['weight']
            required = step.get('required', False)
            max_wait = step.get('max_wait', 0)
            reset_tags = step.get('reset_signals', [])
            
            found = False
            found_time = None
            
            # Start searching from last_found_index + 1
            search_ptr = last_found_index + 1
            
            while search_ptr < len(history):
                if history[search_ptr]['tag'] == tag:
                    # Check if this occurrence was reset later
                    is_reset = False
                    if reset_tags:
                        for rt in reset_tags:
                            if last_seen_index.get(rt, -1) > search_ptr:
                                is_reset = True
                                break
                    
                    if is_reset:
                        # Skip this match and keep searching FORWARD for a newer valid 'tag'
                        search_ptr += 1
                        continue

                    # Enforce max_wait if defined
                    if max_wait > 0 and last_found_index != -1:
                        last_time = history[last_found_index]['t']
                        current_time = history[search_ptr]['t']
                        candle_diff = (current_time - last_time) / 60
                        if candle_diff > max_wait:
                            search_ptr += 1
                            continue

                    # Valid match found
                    found = True
                    last_found_index = search_ptr
                    total_score += weight
                    details.append(f"Found {tag}")
                    found_time = history[search_ptr]['t']
                    matched_steps += 1
                    
                    # Store origin_timestamp when first step is found
                    if i == 0:
                        origin_timestamp = found_time
                    break
                
                search_ptr += 1
            
            step_status = {
                "tag": tag,
                "weight": weight,
                "required": required,
                "max_wait": max_wait,
                "reset_signals": step.get('reset_signals', []),
                "status": "matched" if found else ("waiting" if required else "missed"),
                "time": found_time
            }
            sequence_progress.append(step_status)

            if not found:
                if required:
                    missing_required = True
                    break
                else:
                    details.append(f"Missing {tag}")

        # Always update the tracking state for UI monitoring, even if not fully triggered
        progress_data = {
            "strategy": self.name,
            "strategy_id": self.strategy_id,
            "progress_pct": (matched_steps / len(self.sequence)) * 100 if self.sequence else 0,
            "origin_timestamp": origin_timestamp,
            "sequence": sequence_progress,
            "t": int(df.iloc[-1]['t'])
        }
        
        # We can store this in state_obj so the dashboard can fetch it
        if not hasattr(state_obj, 'strategy_progress'):
            state_obj.strategy_progress = {}
        state_obj.strategy_progress[self.name] = progress_data

        if missing_required:
            return None

        if total_score >= self.min_score:
            return {
                "strategy": self.name,
                "strategy_id": self.strategy_id,
                "origin_timestamp": origin_timestamp,
                "score": total_score,
                "details": json.dumps(details),
                "progress": json.dumps(progress_data),
                "t": int(df.iloc[-1]['t']),
                "msg": f"Strategy {self.name} triggered with score {total_score}",
                "exit_config": self.exit_config
            }
            
        return None
