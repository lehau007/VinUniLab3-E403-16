from typing import Any, Dict, List


def get_discount(coupon_code: str, repo: Any) -> Dict[str, Any]:
    """Validate a coupon code and return its discount percentage."""
    coupons = repo.get_coupons()
    for c in coupons:
        if c.get("code", "").lower() == coupon_code.strip().lower():
            return {"coupon": c.get("code"), "discount_pct": c.get("discount_pct", 0)}
    return {"coupon": coupon_code, "discount_pct": 0, "note": "coupon_not_found"}


def list_coupons(repo: Any) -> Dict[str, Any]:
    """List all available coupon codes and their discount percentages."""
    coupons = repo.get_coupons()
    normalized = [
        {"code": c.get("code"), "discount_pct": c.get("discount_pct", 0)}
        for c in coupons
    ]
    return {"count": len(normalized), "coupons": normalized}
