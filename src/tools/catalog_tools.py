from typing import Any, Dict, List


def list_all_products(repo: Any) -> Dict[str, Any]:
    """Return catalog overview with key fields for product discovery."""
    products = repo.get_products()
    normalized = [
        {
            "id": p.get("id"),
            "name": p.get("name"),
            "price": p.get("price", 0),
            "stock": p.get("stock", 0),
        }
        for p in products
    ]
    return {"count": len(normalized), "products": normalized}


def search_products(keyword: str, repo: Any) -> Dict[str, Any]:
    """Fuzzy search products by keyword (case-insensitive partial match)."""
    products = repo.get_products()
    keyword_lower = keyword.strip().lower()
    matches = [
        {
            "id": p.get("id"),
            "name": p.get("name"),
            "price": p.get("price", 0),
            "stock": p.get("stock", 0),
        }
        for p in products
        if keyword_lower in p.get("name", "").lower()
    ]
    if not matches:
        return {"error": "no_matches", "keyword": keyword}
    return {"count": len(matches), "products": matches}


def check_stock(item_name: str, repo: Any) -> Dict[str, Any]:
    """Check stock by exact product name (case-insensitive)."""
    products = repo.get_products()
    for p in products:
        if p.get("name", "").lower() == item_name.strip().lower():
            return {"id": p.get("id"), "item": p.get("name"), "stock": p.get("stock", 0)}
    return {"error": "item_not_found", "item": item_name}


def check_stock_by_id(product_id: str, repo: Any) -> Dict[str, Any]:
    """Check stock by product ID."""
    product = repo.get_product_by_id(product_id)
    if not product:
        return {"error": "item_not_found", "product_id": product_id}
    return {
        "id": product.get("id"),
        "item": product.get("name"),
        "stock": product.get("stock", 0),
    }


def compare_products(product_id_1: str, product_id_2: str, repo: Any) -> Dict[str, Any]:
    """Compare two products side-by-side by their IDs."""
    p1 = repo.get_product_by_id(product_id_1)
    p2 = repo.get_product_by_id(product_id_2)

    if not p1 and not p2:
        return {"error": "both_not_found", "ids": [product_id_1, product_id_2]}
    if not p1:
        return {"error": "item_not_found", "product_id": product_id_1}
    if not p2:
        return {"error": "item_not_found", "product_id": product_id_2}

    def _summary(p: Dict) -> Dict[str, Any]:
        return {
            "id": p.get("id"),
            "name": p.get("name"),
            "price": p.get("price", 0),
            "stock": p.get("stock", 0),
            "weight": p.get("weight", 0),
        }

    price_diff = (p1.get("price", 0) or 0) - (p2.get("price", 0) or 0)
    return {
        "product_1": _summary(p1),
        "product_2": _summary(p2),
        "price_difference": price_diff,
        "cheaper": p1.get("name") if price_diff <= 0 else p2.get("name"),
    }
