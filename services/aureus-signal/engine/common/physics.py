
def is_touching(price_high: float, price_low: float, zone_top: float, zone_bottom: float) -> bool:
    """Check if a price range touches a given zone."""
    return price_low <= zone_top and price_high >= zone_bottom

def is_fully_contained(price_high: float, price_low: float, zone_top: float, zone_bottom: float) -> bool:
    """Check if a price range is fully inside a given zone."""
    return price_high <= zone_top and price_low >= zone_bottom

def has_closed_above(close: float, level: float) -> bool:
    return close > level

def has_closed_below(close: float, level: float) -> bool:
    return close < level
