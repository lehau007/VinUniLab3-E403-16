import pytest
import os
import sys
import sqlite3
import json
from pathlib import Path

# Add src to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.repositories.json_repo import JsonShopRepository
from src.repositories.sqlite_repo import SqliteShopRepository

# --- JSON Repository Tests ---
def test_json_repo_get_products(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    
    # Case: Multiple products
    with open(data_dir / "products.sample.json", "w") as f:
        json.dump([
            {"id": "p1", "name": "A"},
            {"id": "p2", "name": "B"}
        ], f)
    
    repo = JsonShopRepository(data_dir=str(data_dir))
    products = repo.get_products()
    assert len(products) == 2
    assert products[0]["id"] == "p1"

@pytest.mark.parametrize("search_id, expected_name", [
    ("p1", "A"),
    ("P1", "A"),
    ("NonExistent", None),
])
def test_json_repo_get_product_by_id(tmp_path, search_id, expected_name):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    with open(data_dir / "products.sample.json", "w") as f:
        json.dump([{"id": "p1", "name": "A"}], f)
        
    repo = JsonShopRepository(data_dir=str(data_dir))
    product = repo.get_product_by_id(search_id)
    if expected_name:
        assert product["name"] == expected_name
    else:
        assert product == {}

def test_json_repo_missing_files(tmp_path):
    repo = JsonShopRepository(data_dir=str(tmp_path))
    assert repo.get_products() == []
    assert repo.get_coupons() == []

# --- SQLite Repository Tests ---
@pytest.fixture
def sqlite_repo(tmp_path):
    db_path = tmp_path / "test.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE products (id TEXT PRIMARY KEY, name TEXT, price REAL, stock INTEGER, weight REAL)")
        conn.execute("INSERT INTO products VALUES ('p1', 'Alpha', 100, 5, 1.0)")
        conn.execute("INSERT INTO products VALUES ('p2', 'Beta', 200, 0, 0.5)")
        conn.execute("CREATE TABLE coupons (code TEXT PRIMARY KEY, discount_pct INTEGER)")
        conn.execute("INSERT INTO coupons VALUES ('S10', 10)")
    return SqliteShopRepository(db_path=str(db_path))

def test_sqlite_get_products_all(sqlite_repo):
    products = sqlite_repo.get_products()
    assert len(products) == 2
    assert "stock" in products[0]

@pytest.mark.parametrize("pid, expected_name", [
    ("p1", "Alpha"),
    ("P1", "Alpha"),
    ("p2", "Beta"),
    ("invalid", None),
])
def test_sqlite_get_product_by_id_cases(sqlite_repo, pid, expected_name):
    product = sqlite_repo.get_product_by_id(pid)
    if expected_name:
        assert product["name"] == expected_name
    else:
        assert product == {}

def test_sqlite_get_coupons_all(sqlite_repo):
    coupons = sqlite_repo.get_coupons()
    assert len(coupons) == 1
    assert coupons[0]["code"] == "S10"
    assert coupons[0]["discount_pct"] == 10

def test_sqlite_query_injection_safety(sqlite_repo):
    # Testing that it handles single quotes in params correctly
    res = sqlite_repo.get_product_by_id("p1' OR '1'='1")
    assert res == {}

def test_sqlite_empty_tables(tmp_path):
    db_path = tmp_path / "empty.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE products (id TEXT PRIMARY KEY, name TEXT, price REAL, stock INTEGER, weight REAL)")
        conn.execute("CREATE TABLE coupons (code TEXT PRIMARY KEY, discount_pct INTEGER)")
    repo = SqliteShopRepository(db_path=str(db_path))
    assert repo.get_products() == []
    assert repo.get_coupons() == []
