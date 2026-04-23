"""
Order validation for STRATEGY_MATCH events.

Validates incoming strategy match events against the D-04
validation rules before they are converted to order commands.
"""
from dataclasses import dataclass, field


VALID_ENTRY_TYPES = {"MARKET", "LIMIT", "STOP"}
VALID_DIRECTIONS = {"BUY", "SELL"}
SUPPORTED_SIZE_MODES = {"FIXED_LOT", "FIXED_UNITS", "RISK_FIXED_AMOUNT"}  # FIXED_UNITS alias for FIXED_LOT


@dataclass
class ValidationResult:
    valid: bool
    errors: list[str] = field(default_factory=list)


def validate_strategy_match(event: dict) -> ValidationResult:
    """Validate a STRATEGY_MATCH event data dict.

    Accepts both Phase 26 field names (side, sl, tp, FIXED_UNITS)
    and Phase 29 canonical names (direction, sl_absolute, tp_absolute, FIXED_LOT).
    """
    errors = []

    # Rule: event type must be STRATEGY_MATCH
    if event.get("type") != "STRATEGY_MATCH":
        errors.append('event type must be "STRATEGY_MATCH"')

    data = event.get("data")
    if data is None:
        return ValidationResult(valid=False, errors=["data field is missing"])

    # Rule: entry_type must be valid
    entry_type = data.get("entry_type")
    if entry_type not in VALID_ENTRY_TYPES:
        errors.append(f'invalid entry_type: {entry_type!r}')

    # Rule: direction must be valid (accept "side" alias from Phase 26)
    direction = data.get("direction") or data.get("side")
    if direction not in VALID_DIRECTIONS:
        errors.append(f'invalid direction: {direction!r}')

    # Rule: size_mode must be supported
    size_mode = data.get("size_mode")
    if size_mode not in SUPPORTED_SIZE_MODES:
        if size_mode == "RISK_PERCENT":
            errors.append("RISK_PERCENT not yet supported")
        else:
            errors.append(f'unsupported size_mode: {size_mode!r}')

    # Rule: size_value must be > 0
    size_value = data.get("size_value", 0)
    if not (isinstance(size_value, (int, float)) and size_value > 0):
        errors.append(f'size_value must be > 0, got {size_value!r}')

    # Rule: sl_absolute must not be None (accept "sl" alias from Phase 26)
    sl = data.get("sl_absolute") or data.get("sl")
    if sl is None:
        errors.append("sl_absolute (or sl) must not be None")

    # Rule: tp_absolute must not be None (accept "tp" alias from Phase 26)
    tp = data.get("tp_absolute") or data.get("tp")
    if tp is None:
        errors.append("tp_absolute (or tp) must not be None")

    # Rule: magic_number must be > 0
    magic_number = data.get("magic_number", 0)
    if not (isinstance(magic_number, (int, float)) and magic_number > 0):
        errors.append(f'magic_number must be > 0, got {magic_number!r}')

    # Rule: LIMIT/STOP orders require entry_price > 0
    if entry_type in {"LIMIT", "STOP"}:
        entry_price = data.get("entry_price", 0)
        entry_price_num = None
        if isinstance(entry_price, (int, float)):
            entry_price_num = float(entry_price)
        elif isinstance(entry_price, str):
            try:
                entry_price_num = float(entry_price.strip())
            except ValueError:
                entry_price_num = None

        if not (isinstance(entry_price_num, float) and entry_price_num > 0):
            errors.append(f'{entry_type} order requires entry_price > 0')

    if errors:
        return ValidationResult(valid=False, errors=errors)
    return ValidationResult(valid=True)
