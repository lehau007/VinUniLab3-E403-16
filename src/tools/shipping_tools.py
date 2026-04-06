from typing import Any, Dict

# Surcharge multipliers by destination (case-insensitive, common aliases supported).
_DESTINATION_SURCHARGES = {
    "hcm": 1.2,
    "ho chi minh": 1.2,
    "tp hcm": 1.2,
    "da nang": 1.1,
    "danang": 1.1,
    "hai phong": 1.1,
    "can tho": 1.15,
}

_BASE_FEE = 15_000.0
_PER_KG_FEE = 12_000.0


def calc_shipping(weight: float, destination: str) -> Dict[str, Any]:
    """Calculate shipping fee from package weight (kg) and destination city."""
    dest_key = destination.strip().lower()
    surcharge = _DESTINATION_SURCHARGES.get(dest_key, 1.0)
    shipping_fee = (_BASE_FEE + _PER_KG_FEE * max(weight, 0.0)) * surcharge
    return {
        "destination": destination,
        "weight_kg": weight,
        "surcharge_multiplier": surcharge,
        "shipping_fee": round(shipping_fee, 2),
    }
