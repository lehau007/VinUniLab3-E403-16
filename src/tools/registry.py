import os
from typing import Any, Dict, List, Optional

from src.repositories.json_repo import JsonShopRepository
from src.repositories.sqlite_repo import SqliteShopRepository
from src.tools.catalog_tools import (
    check_stock,
    check_stock_by_id,
    compare_products,
    list_all_products,
    search_products,
)
from src.tools.pricing_tools import get_discount, list_coupons
from src.tools.shipping_tools import calc_shipping


def build_repository(
    backend: Optional[str] = None,
    json_data_dir: Optional[str] = None,
    sqlite_path: Optional[str] = None,
):
    selected_backend = (backend or os.getenv("DATA_BACKEND", "json")).strip().lower()

    if selected_backend == "sqlite":
        db_path = sqlite_path or os.getenv("SQLITE_PATH", "./db/shop.db")
        return SqliteShopRepository(db_path=db_path)

    data_dir = json_data_dir or os.getenv("JSON_DATA_DIR", "data")
    return JsonShopRepository(data_dir=data_dir)


def create_tool_registry(repo: Any) -> List[Dict[str, Any]]:
    def get_product(product_id: str) -> Dict[str, Any]:
        product = repo.get_product_by_id(product_id)
        if not product:
            return {"error": "item_not_found", "product_id": product_id}
        return product

    def estimate_total(
        product_id: str,
        quantity: int,
        coupon_code: str = "",
        destination: str = "hanoi",
    ) -> Dict[str, Any]:
        product = repo.get_product_by_id(product_id)
        if not product:
            return {"error": "item_not_found", "product_id": product_id}

        qty = max(int(quantity), 1)
        unit_price = float(product.get("price", 0))
        subtotal = unit_price * qty

        discount_pct = 0.0
        if coupon_code:
            discount_result = get_discount(coupon_code=coupon_code, repo=repo)
            discount_pct = float(discount_result.get("discount_pct", 0))

        discount_amount = subtotal * (discount_pct / 100.0)

        weight = float(product.get("weight", 0.0)) * qty
        shipping_result = calc_shipping(weight=weight, destination=destination)
        shipping_fee = float(shipping_result.get("shipping_fee", 0.0))

        total = subtotal - discount_amount + shipping_fee
        return {
            "product_id": product_id,
            "product_name": product.get("name"),
            "quantity": qty,
            "unit_price": unit_price,
            "subtotal": round(subtotal, 2),
            "discount_pct": discount_pct,
            "discount_amount": round(discount_amount, 2),
            "shipping_fee": round(shipping_fee, 2),
            "total": round(total, 2),
        }

    return [
        # ── Discovery tools ──────────────────────────────────────────
        {
            "name": "list_all_products",
            "description": (
                "List all products with id, name, price, and stock. "
                "Call this FIRST to discover product names and IDs. "
                "Args: none."
            ),
            "fn": lambda: list_all_products(repo=repo),
        },
        {
            "name": "search_products",
            "description": (
                "Search products by keyword (case-insensitive partial match). "
                "Returns matching products with id, name, price, stock. "
                "Args: keyword (str)."
            ),
            "fn": lambda keyword: search_products(keyword=keyword, repo=repo),
        },
        # ── Product detail tools ─────────────────────────────────────
        {
            "name": "get_product_by_id",
            "description": (
                "Return full product details (name, price, stock, weight) by product ID. "
                "Use after finding the ID from list_all_products or search_products. "
                "Args: product_id (str)."
            ),
            "fn": get_product,
        },
        {
            "name": "compare_products",
            "description": (
                "Compare two products side-by-side by their IDs. "
                "Returns both products' details and price difference. "
                "Args: product_id_1 (str), product_id_2 (str)."
            ),
            "fn": lambda product_id_1, product_id_2: compare_products(
                product_id_1=product_id_1, product_id_2=product_id_2, repo=repo
            ),
        },
        # ── Stock tools ──────────────────────────────────────────────
        {
            "name": "check_stock",
            "description": (
                "Check product stock by exact product name (case-insensitive). "
                "Args: item_name (str)."
            ),
            "fn": lambda item_name: check_stock(item_name=item_name, repo=repo),
        },
        {
            "name": "check_stock_by_id",
            "description": (
                "Check product stock by product ID. "
                "Prefer this after finding the ID from list_all_products. "
                "Args: product_id (str)."
            ),
            "fn": lambda product_id: check_stock_by_id(product_id=product_id, repo=repo),
        },
        # ── Pricing / coupon tools ───────────────────────────────────
        {
            "name": "list_coupons",
            "description": (
                "List all available coupon codes and their discount percentages. "
                "Args: none."
            ),
            "fn": lambda: list_coupons(repo=repo),
        },
        {
            "name": "get_discount",
            "description": (
                "Validate a coupon code and return its discount percentage. "
                "Returns 0% if coupon is not found. "
                "Args: coupon_code (str)."
            ),
            "fn": lambda coupon_code: get_discount(coupon_code=coupon_code, repo=repo),
        },
        # ── Shipping & order tools ───────────────────────────────────
        {
            "name": "calc_shipping",
            "description": (
                "Calculate shipping fee from package weight (kg) and destination city. "
                "Surcharge applies for HCM (+20%), Da Nang/Hai Phong (+10%), Can Tho (+15%). "
                "Args: weight (float), destination (str)."
            ),
            "fn": calc_shipping,
        },
        {
            "name": "estimate_total",
            "description": (
                "Estimate full order total: subtotal, discount, shipping, and grand total. "
                "Args: product_id (str), quantity (int), coupon_code (str, optional), destination (str, optional, default='hanoi')."
            ),
            "fn": estimate_total,
        },
    ]
