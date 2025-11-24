
import pytest
import json
import sqlite3
import app as flask_app # Import module to access globals
from Food_manager import InventoryManager
from RecipeManager import RecipeManager
from datetime import date

@pytest.fixture
def client():
    flask_app.app.config['TESTING'] = True
    flask_app.app.config['LOGIN_DISABLED'] = True

    # Setup isolated DB
    db_path = "test_ha_features.db"
    test_manager = InventoryManager(db_path)
    test_recipe_mngr = RecipeManager(db_path)

    # Monkeypatch globals in app module
    flask_app.manager = test_manager
    flask_app.recipe_mngr = test_recipe_mngr

    # Make them available for the test functions
    # We can attach them to the client or app, or just rely on flask_app.manager

    # Clean DB
    # IMPORTANT: Use the 'manager' imported from 'app' to ensure we are cleaning the same DB instance
    # that the tests will use, although we monkeypatched it so it should be same.
    # But just in case the monkeypatching timing is tricky.

    with manager._get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_keys = OFF")
        cursor.execute("DELETE FROM products")
        cursor.execute("DELETE FROM recipes")
        cursor.execute("DELETE FROM recipe_ingredients")
        cursor.execute("DELETE FROM inventory_items")
        cursor.execute("DELETE FROM PurchaseLog")
        cursor.execute("DELETE FROM categories")
        cursor.execute("DELETE FROM subcategories")
        cursor.execute("DELETE FROM user_shopping_list")
        cursor.execute("DELETE FROM product_aliases")
        cursor.execute("DELETE FROM sqlite_sequence")
        cursor.execute("PRAGMA foreign_keys = ON")
        conn.commit()

    with flask_app.app.test_client() as client:
        yield client

    # Cleanup
    import os
    if os.path.exists(db_path):
        os.remove(db_path)

def test_recursive_recipe_resolution(client):
    manager = flask_app.manager
    recipe_mngr = flask_app.recipe_mngr

    # 1. Create Base Products
    cat_res = manager.add_category("TestCat")
    cat_id = cat_res['category_id']
    flour_res = manager.create_product("Flour", cat_id, None, "kg", 100)
    water_res = manager.create_product("Water", cat_id, None, "L", 100)

    # 2. Create "Dough" Recipe (Flour + Water)
    dough_data = {
        "name": "Dough",
        "ingredients": [
            {"item_name": "Flour", "quantity_required": 0.5},
            {"item_name": "Water", "quantity_required": 0.2}
        ]
    }
    assert recipe_mngr.add_recipe(dough_data)['success']

    # 3. Create "Pizza Base" Recipe (Dough)
    # Must use SQL because "Dough" is NOT a product
    with recipe_mngr._get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('INSERT INTO recipes (name) VALUES (?)', ("Pizza Base",))
        pb_id = cursor.lastrowid
        cursor.execute('''
            INSERT INTO recipe_ingredients (recipe_id, item_name, quantity)
            VALUES (?, ?, ?)
        ''', (pb_id, "Dough", 1.0))
        conn.commit()

    # Add Stock
    manager.add_inventory_stock(flour_res['product_id'], "10", "2023-01-01")
    manager.add_inventory_stock(water_res['product_id'], "10", "2023-01-01")

    # Test Consumption
    payload = {
        "items": [
            {"item_name": "Pizza Base", "quantity": 2}
        ]
    }

    response = client.post('/inventory/consume', json=payload)
    data = response.get_json()

    if response.status_code != 200:
        print(f"Recursive Test Failed Response: {data}")

    assert response.status_code == 200
    assert data['success'] is True

    # Verify: 2 Pizza Bases -> 2 Doughs -> 1.0 Flour, 0.4 Water
    new_flour_qty = manager.get_total_item_quantity(flour_res['product_id'])
    assert new_flour_qty == 9.0 # 10 - 1.0

def test_product_priority(client):
    manager = flask_app.manager
    recipe_mngr = flask_app.recipe_mngr

    # Setup
    cat_res = manager.add_category("TestCat2")
    cat_id = cat_res['category_id']

    # Product "Cheese"
    cheese_prod = manager.create_product("Cheese", cat_id, None, "kg", 30)

    # Ingredients for Recipe Cheese
    milk_res = manager.create_product("Milk", cat_id, None, "L", 7)
    rennet_res = manager.create_product("Rennet", cat_id, None, "ml", 100)
    manager.add_inventory_stock(milk_res['product_id'], "100", "2023-01-01")

    # Recipe "Cheese"
    cheese_recipe = {
        "name": "Cheese",
        "ingredients": [
            {"item_name": "Milk", "quantity_required": 10},
            {"item_name": "Rennet", "quantity_required": 5}
        ]
    }
    assert recipe_mngr.add_recipe(cheese_recipe)['success']

    # Add Stock for Cheese Product
    manager.add_inventory_stock(cheese_prod['product_id'], "5", "2023-01-01")

    # Consume "Cheese"
    payload = {
        "items": [
            {"item_name": "Cheese", "quantity": 1}
        ]
    }

    response = client.post('/inventory/consume', json=payload)
    if response.status_code != 200:
        print(f"Priority Test Failed Response: {response.get_json()}")

    assert response.status_code == 200

    # Logic check: Should use Product stock, NOT Recipe ingredients
    new_cheese_qty = manager.get_total_item_quantity(cheese_prod['product_id'])
    new_milk_qty = manager.get_total_item_quantity(milk_res['product_id'])

    assert new_cheese_qty == 4.0
    assert new_milk_qty == 100.0

def test_log_purchase_api(client):
    manager = flask_app.manager

    cat_res = manager.add_category("TestCat3")
    cat_id = cat_res['category_id']
    prod_res = manager.create_product("TestItem", cat_id, None, "units", 30)
    pid = prod_res['product_id']

    # 1. Missing Quantity (Validation Check)
    resp = client.post('/api/log_purchase', json={"product_name": "TestItem"})
    assert resp.status_code == 400
    assert "quantity is required" in resp.get_json()['message']

    # 2. Missing Cost (Validation Check)
    resp = client.post('/api/log_purchase', json={"product_name": "TestItem", "quantity": 1})
    assert resp.status_code == 400
    assert "cost is required" in resp.get_json()['message']

    # 3. Success
    resp = client.post('/api/log_purchase', json={
        "product_name": "TestItem",
        "quantity": 5,
        "cost": 2.50
    })
    if resp.status_code != 200:
        print(f"API Test Failed Response: {resp.get_json()}")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['new_total'] == 5.0
