import pytest
import os
import sys

# Add src to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.tools.catalog_tools import list_all_products, check_stock, check_stock_by_id
from src.tools.pricing_tools import get_discount
from src.tools.shipping_tools import calc_shipping
from src.tools.registry import create_tool_registry

class MockRepo:
    def __init__(self, products=None, coupons=None):
        self.products = products or []
        self.coupons = coupons or []

    def get_products(self):
        return self.products
    
    def get_product_by_id(self, product_id):
        for p in self.products:
            if str(p.get("id")).lower() == str(product_id).lower():
                return p
        return None
    
    def get_coupons(self):
        return self.coupons

# --- Tests for list_all_products ---
@pytest.mark.parametrize("products, expected_count", [
    ([], 0),
    ([{"id": "p1", "name": "Laptop"}], 1),
    ([{"id": "p1", "name": "Laptop"}, {"id": "p2", "name": "Mouse"}], 2),
])
def test_list_all_products_cases(products, expected_count):
    repo = MockRepo(products=products)
    res = list_all_products(repo)
    assert res["count"] == expected_count
    assert len(res["products"]) == expected_count
    if expected_count > 0:
        assert "id" in res["products"][0]
        assert "name" in res["products"][0]
        assert "price" not in res["products"][0] # should be discovery only

# --- Tests for check_stock ---
@pytest.mark.parametrize("item_name, repo_products, expected_id, expected_stock, is_error", [
    ("Laptop", [{"id": "p1", "name": "Laptop", "stock": 5}], "p1", 5, False),
    ("laptop", [{"id": "p1", "name": "Laptop", "stock": 5}], "p1", 5, False),
    ("Mouse", [{"id": "p1", "name": "Laptop", "stock": 5}], None, 0, True),
    ("Laptop", [{"id": "p1", "name": "Laptop"}], "p1", 0, False), # Stock missing should be 0
])
def test_check_stock_cases(item_name, repo_products, expected_id, expected_stock, is_error):
    repo = MockRepo(products=repo_products)
    res = check_stock(item_name, repo)
    if is_error:
        assert "error" in res
        assert res["error"] == "item_not_found"
    else:
        assert res["id"] == expected_id
        assert res["stock"] == expected_stock

# --- Tests for check_stock_by_id ---
@pytest.mark.parametrize("product_id, repo_products, expected_stock, is_error", [
    ("p1", [{"id": "p1", "name": "Laptop", "stock": 5}], 5, False),
    ("P1", [{"id": "p1", "name": "Laptop", "stock": 5}], 5, False),
    ("invalid", [], 0, True),
])
def test_check_stock_by_id_cases(product_id, repo_products, expected_stock, is_error):
    repo = MockRepo(products=repo_products)
    res = check_stock_by_id(product_id, repo)
    if is_error:
        assert "error" in res
        assert res["error"] == "item_not_found"
    else:
        assert res["id"].lower() == product_id.lower()
        assert res["stock"] == expected_stock

# --- Tests for get_discount ---
@pytest.mark.parametrize("coupon_code, repo_coupons, expected_pct, expected_note", [
    ("SAVE10", [{"code": "SAVE10", "discount_pct": 10}], 10, None),
    ("save10", [{"code": "SAVE10", "discount_pct": 10}], 10, None),
    ("NONE", [], 0, "coupon_not_found"),
    ("EMPTY", [{"code": "EMPTY"}], 0, None), # missing pct field
])
def test_get_discount_cases(coupon_code, repo_coupons, expected_pct, expected_note):
    repo = MockRepo(coupons=repo_coupons)
    res = get_discount(coupon_code, repo)
    assert res["discount_pct"] == expected_pct
    if expected_note:
        assert res["note"] == expected_note

# --- Tests for calc_shipping ---
@pytest.mark.parametrize("weight, destination, expected_fee", [
    (1.0, "HN", 27000.0),      # 15000 + 12000*1 = 27000
    (2.0, "Hanoi ", 39000.0),  # case/space check
    (1.0, "HCM", 32400.0),     # 27000 * 1.2 = 32400
    (0.0, "HN", 15000.0),
    (-5.0, "HN", 15000.0),     # negative weight = 0
])
def test_calc_shipping_cases(weight, destination, expected_fee):
    res = calc_shipping(weight, destination)
    assert res["shipping_fee"] == expected_fee

# --- Tests for estimate_total ---
def test_estimate_total_full_calc():
    repo = MockRepo(
        products=[{"id": "p1", "name": "Laptop", "price": 100, "weight": 1.0}],
        coupons=[{"code": "SAVE50", "discount_pct": 50}]
    )
    tools = create_tool_registry(repo)
    estimate_fn = next(t["fn"] for t in tools if t["name"] == "estimate_total")

    # 10 units of $100 = 1000
    # 50% discount = 500
    # weight: 10 * 1kg = 10kg
    # shipping HN: 15000 + 12000*10 = 135000
    # total: 1000 - 500 + 135000 = 135500
    res = estimate_fn(product_id="p1", quantity=10, coupon_code="SAVE50", destination="HN")
    
    assert res["subtotal"] == 1000
    assert res["discount_amount"] == 500
    assert res["shipping_fee"] == 135000
    assert res["total"] == 135500

@pytest.mark.parametrize("pid, qty, coupon, dest, expected_error", [
    ("invalid", 1, "", "HN", "item_not_found"),
])
def test_estimate_total_errors(pid, qty, coupon, dest, expected_error):
    repo = MockRepo(products=[])
    tools = create_tool_registry(repo)
    estimate_fn = next(t["fn"] for t in tools if t["name"] == "estimate_total")
    res = estimate_fn(product_id=pid, quantity=qty, coupon_code=coupon, destination=dest)
    assert res["error"] == expected_error
