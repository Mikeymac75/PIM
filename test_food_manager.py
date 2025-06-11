import unittest
import sqlite3
from datetime import date, timedelta
from Food_manager import InventoryManager

class TestInventoryManager(unittest.TestCase):

    def setUp(self):
        """Set up an in-memory SQLite database for each test."""
        self.manager = InventoryManager(db_filepath=":memory:")
        self.today = date.today()
        self.today_str = self.today.isoformat()

    def _create_product(self, name="Test Product", category="Test Category", subcategory="Test Subcategory",
                        unit_of_measure="units", default_expiry_days=10, par_level=0,
                        max_holding_amount=0, purchase_location=None):
        """Helper to create a product for tests. Returns the product_id."""
        result = self.manager.create_product(
            name, category, subcategory, unit_of_measure, default_expiry_days,
            par_level, max_holding_amount, purchase_location
        )
        self.assertTrue(result.get("success"), f"Failed to create product: {result.get('message')}")
        self.assertIsNotNone(result.get("product_id"))
        return result["product_id"]

    def _add_inventory_stock(self, product_id, quantity_str, purchase_date_str=None):
        """Helper to add inventory stock for a given product_id."""
        if purchase_date_str is None:
            purchase_date_str = self.today_str
        return self.manager.add_inventory_stock(product_id, quantity_str, purchase_date_str)

    def _add_historical_consumption(self, product_id, product_name, quantity_consumed, days_ago):
        """Helper to add historical consumption data for an item."""
        consumed_date = (self.today - timedelta(days=days_ago)).isoformat()
        conn = self.manager._get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO historical_items
            (product_id, name, quantity_consumed_this_time, original_quantity_string, purchase_date, expiry_date, consumed_date)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (product_id, product_name, quantity_consumed, "N/A", None, None, consumed_date))
        conn.commit()
        conn.close()

# --- Product Management Tests ---
class TestProductManagement(unittest.TestCase):
    def setUp(self):
        self.manager = InventoryManager(db_filepath=":memory:")
        self.today = date.today()

    def test_create_product_success(self):
        result = self.manager.create_product("Test Apple", "Fruit", "Red Apples", "pcs", 14, 5, 20, "Local Farm")
        self.assertTrue(result["success"])
        self.assertIsNotNone(result["product_id"])
        product_id = result["product_id"]

        retrieved_product = self.manager.get_product(product_id)
        self.assertIsNotNone(retrieved_product)
        self.assertEqual(retrieved_product["name"], "Test Apple")
        self.assertEqual(retrieved_product["category"], "Fruit")
        self.assertEqual(retrieved_product["subcategory"], "Red Apples")
        self.assertEqual(retrieved_product["unit_of_measure"], "pcs")
        self.assertEqual(retrieved_product["default_expiry_days"], 14)
        self.assertEqual(retrieved_product["par_level"], 5)
        self.assertEqual(retrieved_product["max_holding_amount"], 20)
        self.assertEqual(retrieved_product["purchase_location"], "Local Farm")

    def test_create_product_duplicate_name(self):
        self.manager.create_product("Test Banana", "Fruit", "Yellow", "pcs", 7)
        result = self.manager.create_product("Test Banana", "Fruit", "Green", "pcs", 5)
        self.assertFalse(result["success"])
        self.assertIn("already exists", result["message"])

    def test_create_product_missing_required_fields(self):
        # Test for missing name (other fields like unit_of_measure and default_expiry_days are also required by method signature)
        result_name = self.manager.create_product(name=None, category="Fruit", subcategory="Tropical", unit_of_measure="pcs", default_expiry_days=7)
        self.assertFalse(result_name["success"])
        self.assertIn("Missing required product fields", result_name["message"])

        result_unit = self.manager.create_product(name="Test Fruit", category="Fruit", subcategory="Tropical", unit_of_measure=None, default_expiry_days=7)
        self.assertFalse(result_unit["success"])
        self.assertIn("Missing required product fields", result_unit["message"])

        result_expiry = self.manager.create_product(name="Test Fruit 2", category="Fruit", subcategory="Tropical", unit_of_measure="pcs", default_expiry_days=None)
        self.assertFalse(result_expiry["success"])
        self.assertIn("Missing required product fields", result_expiry["message"])

    def test_get_product_success(self):
        res = self.manager.create_product("Test Cherry", "Fruit", "Dark", "kg", 7)
        product_id = res["product_id"]
        product = self.manager.get_product(product_id)
        self.assertIsNotNone(product)
        self.assertEqual(product["name"], "Test Cherry")

    def test_get_product_not_found(self):
        product = self.manager.get_product(999) # Non-existent ID
        self.assertIsNone(product)

    def test_get_product_by_name_success(self):
        self.manager.create_product("Test Date", "Fruit", "Dried", "pack", 180)
        product = self.manager.get_product_by_name("Test Date")
        self.assertIsNotNone(product)
        self.assertEqual(product["category"], "Fruit")

    def test_get_product_by_name_not_found(self):
        product = self.manager.get_product_by_name("NonExistent Product")
        self.assertIsNone(product)

    def test_get_all_products(self):
        self.manager.create_product("Product Alpha", "Cat A", "Sub A", "pcs", 10)
        self.manager.create_product("Product Zeta", "Cat B", "Sub B", "kg", 5) # Test order
        self.manager.create_product("Product Gamma", "Cat C", "Sub C", "box", 20)

        products = self.manager.get_all_products()
        self.assertEqual(len(products), 3)
        self.assertEqual(products[0]["name"], "Product Alpha") # Sorted by name
        self.assertEqual(products[1]["name"], "Product Gamma")
        self.assertEqual(products[2]["name"], "Product Zeta")

    def test_update_product_success(self):
        res = self.manager.create_product("Old Name", "Old Cat", "Old Sub", "old_unit", 10, 1, 2, "Old Loc")
        product_id = res["product_id"]

        update_result = self.manager.update_product(product_id, "New Name", "New Cat", "New Sub", "new_unit", 20, 3, 4, "New Loc")
        self.assertTrue(update_result["success"])

        updated_product = self.manager.get_product(product_id)
        self.assertEqual(updated_product["name"], "New Name")
        self.assertEqual(updated_product["category"], "New Cat")
        self.assertEqual(updated_product["default_expiry_days"], 20)
        self.assertEqual(updated_product["par_level"], 3)

    def test_update_product_name_conflict(self):
        self.manager.create_product("Existing Product", "Cat", "Sub", "pcs", 10)
        res_to_update = self.manager.create_product("Product To Update", "Cat", "Sub", "pcs", 5)
        product_id_to_update = res_to_update["product_id"]

        update_result = self.manager.update_product(product_id_to_update, "Existing Product", "New Cat", "New Sub", "new_unit", 20, 3, 4, "New Loc")
        self.assertFalse(update_result["success"])
        self.assertIn("already exist", update_result["message"])

    def test_update_product_not_found(self):
        update_result = self.manager.update_product(999, "New Name", "New Cat", "New Sub", "new_unit", 20, 3, 4, "New Loc")
        self.assertFalse(update_result["success"])
        self.assertIn("not found", update_result["message"])

    def tearDown(self):
        pass # In-memory DB is auto-cleaned

# Original TestInventoryManager starts here, will be updated later
class TestInventoryManager(unittest.TestCase):

    def setUp(self):
        """Set up an in-memory SQLite database for each test."""
        self.manager = InventoryManager(db_filepath=":memory:")
        self.today = date.today()
        self.today_str = self.today.isoformat()

    def _create_product(self, name="Test Product", category="Test Category", subcategory="Test Subcategory",
                        unit_of_measure="units", default_expiry_days=10, par_level=0,
                        max_holding_amount=0, purchase_location=None):
        """Helper to create a product for tests. Returns the product_id."""
        result = self.manager.create_product(
            name, category, subcategory, unit_of_measure, default_expiry_days,
            par_level, max_holding_amount, purchase_location
        )
        self.assertTrue(result.get("success"), f"Failed to create product: {result.get('message')}")
        self.assertIsNotNone(result.get("product_id"))
        return result["product_id"]

    def _add_inventory_stock(self, product_id, quantity_str, purchase_date_str=None):
        """Helper to add inventory stock for a given product_id."""
        if purchase_date_str is None:
            purchase_date_str = self.today_str
        return self.manager.add_inventory_stock(product_id, quantity_str, purchase_date_str)

    def _add_historical_consumption(self, product_id, product_name, quantity_consumed, days_ago):
        """Helper to add historical consumption data for an item."""
        # Note: product_name is passed here for historical_items.name,
        # product_id links to the definitive product name.
        consumed_date = (self.today - timedelta(days=days_ago)).isoformat()
        conn = self.manager._get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO historical_items
            (product_id, name, quantity_consumed_this_time, original_quantity_string, purchase_date, expiry_date, consumed_date)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (product_id, product_name, quantity_consumed, "N/A", None, None, consumed_date))
        conn.commit()
        conn.close()

    def test_add_inventory_stock_success(self):
        """Test adding an item and retrieving it, including purchase_location."""
        product_id = self._create_product(name="Test Apple", category="Fruit", default_expiry_days=7, purchase_location="Sobeys")

        self._add_inventory_stock(product_id, "5 units")

        inventory = self.manager.get_current_inventory()
        self.assertEqual(len(inventory), 1)
        item = inventory[0]
        self.assertEqual(item['product_id'], product_id)
        self.assertEqual(item['product_name'], "Test Apple") # Name from product table
        self.assertEqual(item['quantity'], "5 units")
        self.assertEqual(item['purchase_date'], self.today)
        self.assertEqual(item['expiry_date'], self.today + timedelta(days=7)) # Based on product default_expiry_days
        self.assertEqual(item['category'], "Fruit") # Category from product table
        self.assertEqual(item['purchase_location'], "Sobeys") # Purchase location from product table

    def test_add_inventory_stock_product_not_found(self):
        result = self._add_inventory_stock(product_id=999, quantity_str="10 units")
        self.assertFalse(result["success"])
        self.assertIn("Product with ID 999 not found", result["message"])


    def test_consume_item_partial(self):
        """Test consuming part of an item's stock."""
        product_id = self._create_product(name="Test Banana", unit_of_measure="units", default_expiry_days=5)
        self._add_inventory_stock(product_id, "10 units")

        result = self.manager.consume_item("Test Banana", 3.0) # Consume by product name
        self.assertTrue(result['success'])

        inventory = self.manager.get_current_inventory()
        self.assertEqual(len(inventory), 1)
        item_stock = inventory[0]
        self.assertEqual(item_stock['product_name'], "Test Banana")
        # Quantity should be updated based on the parsing and reconstruction logic in consume_item
        # If original was "10 units", and 3 consumed, new might be "7.0 units" or "7 units"
        self.assertTrue(item_stock['quantity'] == "7.0 units" or item_stock['quantity'] == "7 units")


        historical_items = self.manager.get_historical_inventory()
        self.assertEqual(len(historical_items), 1)
        consumed_item_record = historical_items[0]
        self.assertEqual(consumed_item_record['product_id'], product_id)
        self.assertEqual(consumed_item_record['name'], "Test Banana") # Should be product name
        self.assertEqual(consumed_item_record['quantity_consumed_this_time'], 3.0)

    def test_consume_item_full(self):
        """Test consuming an entire item's stock."""
        product_id = self._create_product(name="Test Orange", unit_of_measure="units", default_expiry_days=3)
        self._add_inventory_stock(product_id, "2 units")

        result = self.manager.consume_item("Test Orange", 2.0)
        self.assertTrue(result['success'])
        
        inventory = self.manager.get_current_inventory()
        self.assertEqual(len(inventory), 0) # Stock should be gone

        historical_items = self.manager.get_historical_inventory()
        self.assertEqual(len(historical_items), 1)
        consumed_item_record = historical_items[0]
        self.assertEqual(consumed_item_record['product_id'], product_id)
        self.assertEqual(consumed_item_record['name'], "Test Orange")
        self.assertEqual(consumed_item_record['quantity_consumed_this_time'], 2.0)

    def test_get_total_item_quantity(self):
        """Test getting total quantity of a product with multiple stock batches, by ID and name."""
        product_id_grapes = self._create_product(name="Test Grapes", unit_of_measure="g", default_expiry_days=7)
        
        self._add_inventory_stock(product_id_grapes, "100 g")
        self._add_inventory_stock(product_id_grapes, "150 g") # Another batch

        # Test by product name
        total_quantity_by_name = self.manager.get_total_item_quantity("Test Grapes")
        self.assertEqual(total_quantity_by_name, 250.0)

        # Test by product ID
        total_quantity_by_id = self.manager.get_total_item_quantity(product_id_grapes)
        self.assertEqual(total_quantity_by_id, 250.0)

        # Test for a product with no stock
        product_id_apples = self._create_product(name="Test Apples", unit_of_measure="pcs", default_expiry_days=10)
        total_quantity_no_stock = self.manager.get_total_item_quantity("Test Apples")
        self.assertEqual(total_quantity_no_stock, 0.0)
        total_quantity_no_stock_id = self.manager.get_total_item_quantity(product_id_apples)
        self.assertEqual(total_quantity_no_stock_id, 0.0)

        # Test for non-existent product
        total_quantity_non_existent = self.manager.get_total_item_quantity("NonExistent Product")
        self.assertEqual(total_quantity_non_existent, 0.0)
        total_quantity_non_existent_id = self.manager.get_total_item_quantity(9999)
        self.assertEqual(total_quantity_non_existent_id, 0.0)


    def test_check_for_expiring_items(self):
        """Test identifying expiring and expired items based on product default expiry and purchase date."""
        # Product 1: Milk, default expiry 2 days
        p_milk_id = self._create_product(name="Expiring Soon Milk", default_expiry_days=2)
        self._add_inventory_stock(p_milk_id, "1L", self.today_str) # Expires in 2 days from today

        # Product 2: Bread, default expiry 1 day
        p_bread_id = self._create_product(name="Expired Bread", default_expiry_days=1)
        # Purchased 5 days ago, default expiry 1 day, so expired 4 days ago.
        self._add_inventory_stock(p_bread_id, "1 loaf", (self.today - timedelta(days=5)).isoformat())

        # Product 3: Juice, default expiry 10 days
        p_juice_id = self._create_product(name="Fresh Juice", default_expiry_days=10)
        self._add_inventory_stock(p_juice_id, "2L", self.today_str) # Not expiring soon (expires in 10 days)
        
        # Check for items expiring within 3 days
        # The check_for_expiring_items method itself queries inventory_items directly for expiry_date
        # and doesn't need product context for its core logic, but the setup now uses products.
        expiring_items_list = self.manager.check_for_expiring_items(days_threshold=3)
        
        # The 'name' in the result of check_for_expiring_items comes from inventory_items.name,
        # which is populated from products.name when stock is added.
        expiring_names = [item['name'] for item in expiring_items_list]
        self.assertIn("Expiring Soon Milk", expiring_names)
        self.assertIn("Expired Bread", expiring_names)
        self.assertNotIn("Fresh Juice", expiring_names)
        self.assertEqual(len(expiring_items_list), 2)

    def test_project_demand(self):
        """Test demand projection based on historical consumption and current stock, using product_id."""
        product_name = "Projector Product"
        product_unit = "widgets"
        product_id = self._create_product(name=product_name, unit_of_measure=product_unit, default_expiry_days=30)

        # Add initial stock
        self._add_inventory_stock(product_id, "20 widgets")

        # Manually insert historical consumption data for this product_id
        self._add_historical_consumption(product_id, product_name, 10.0, days_ago=1)  # Consumed 10 widgets 1 day ago
        self._add_historical_consumption(product_id, product_name, 10.0, days_ago=5)  # Consumed 10 widgets 5 days ago
        self._add_historical_consumption(product_id, product_name, 10.0, days_ago=10) # Consumed 10 widgets 10 days ago
        # Total consumed in last 30 days = 30 widgets. Avg daily = 30/30 = 1 widget/day.

        # Test projection by product ID
        projection_by_id = self.manager.project_demand(product_id, lookback_days=30, projection_days=7)

        self.assertTrue(projection_by_id['success'])
        self.assertEqual(projection_by_id['product_id'], product_id)
        self.assertEqual(projection_by_id['product_name'], product_name)
        self.assertEqual(projection_by_id['unit_of_measure'], product_unit)
        self.assertEqual(projection_by_id['current_stock'], 20.0) # Current stock
        self.assertAlmostEqual(projection_by_id['avg_daily_consumption'], 1.0) # 30 units / 30 days
        self.assertEqual(projection_by_id['projected_need'], 7.0) # 1.0 units/day * 7 days

        # Test projection by product name (should yield same results)
        projection_by_name = self.manager.project_demand(product_name, lookback_days=30, projection_days=7)
        self.assertTrue(projection_by_name['success'])
        self.assertEqual(projection_by_name['product_id'], product_id)
        self.assertEqual(projection_by_name['product_name'], product_name)
        self.assertEqual(projection_by_name['current_stock'], 20.0)
        self.assertAlmostEqual(projection_by_name['avg_daily_consumption'], 1.0)
        self.assertEqual(projection_by_name['projected_need'], 7.0)

    def test_add_inventory_stock_invalid_date_format(self):
        """Test adding item stock with invalid date format."""
        product_id = self._create_product(name="Date Test Product")
        result = self._add_inventory_stock(product_id, "1 unit", "2023/01/01") # Wrong format
        self.assertFalse(result['success'])
        self.assertIn("Invalid date or expiry day format", result['message'])

    def test_consume_item_product_not_found_in_products_table(self):
        """Test consuming a product name that doesn't exist in products table."""
        result = self.manager.consume_item("NonExistent Product", 1.0)
        self.assertFalse(result['success'])
        self.assertIn("Product 'NonExistent Product' not found in products table.", result['message'])

    def test_consume_item_product_exists_but_no_stock(self):
        """Test consuming a product that exists but has no stock in inventory_items."""
        self._create_product(name="NoStock Product") # Product exists
        result = self.manager.consume_item("NoStock Product", 1.0) # But no stock added
        self.assertFalse(result['success'])
        self.assertIn("Item 'NoStock Product' not found in inventory.", result['message'])


    def tearDown(self):
        """Clean up resources, if any (though in-memory DB is auto-cleaned)."""
        # For in-memory DB, connection closure might not be strictly necessary here
        # as it's per-test, but good practice if it were a file-based DB.
        pass

    # --- Tests for get_shopping_list_items ---

    def test_get_shopping_list_empty_inventory_and_products(self):
        self.assertEqual(self.manager.get_shopping_list_items(), [])

    def test_get_shopping_list_no_qualifying_products(self):
        # Product with high stock compared to par and zero consumption
        p_apples_id = self._create_product(name="Apples", par_level=5, purchase_location="Sobeys", unit_of_measure="units")
        self._add_inventory_stock(p_apples_id, "20 units")

        # Product with par level 0
        p_oranges_id = self._create_product(name="Oranges", par_level=0, purchase_location="Sobeys", unit_of_measure="units")
        self._add_inventory_stock(p_oranges_id, "5 units")
        self._add_historical_consumption(p_oranges_id, "Oranges", 1, 1) # Some consumption

        self.assertEqual(self.manager.get_shopping_list_items(), [])

    def test_get_shopping_list_sobeys_item_needed(self):
        product_name = "Milk"
        product_unit = "L"
        p_milk_id = self._create_product(name=product_name, unit_of_measure=product_unit, par_level=2, purchase_location="Sobeys", default_expiry_days=7)
        self._add_inventory_stock(p_milk_id, "1 L")

        for i in range(1, 8): # 7 days of consumption, 1L per day
            self._add_historical_consumption(p_milk_id, product_name, 1, i)

        shopping_list = self.manager.get_shopping_list_items()
        self.assertEqual(len(shopping_list), 1)
        item = shopping_list[0]
        self.assertEqual(item['name'], product_name)
        self.assertEqual(item['unit_of_measure'], product_unit)
        self.assertEqual(item['purchase_location'], "Sobeys")
        self.assertAlmostEqual(item['recommended_purchase_amount'], 8.0) # Expected: Par(2) + CycleConsumption(7) - CurrentStock(1) = 8
        self.assertEqual(item['par_level'], 2)
        self.assertEqual(item['days_to_next_shop'], 7)

    def test_get_shopping_list_costco_item_needed(self):
        product_name = "Paper Towels"
        product_unit = "rolls"
        p_paper_id = self._create_product(name=product_name, unit_of_measure=product_unit, par_level=6, purchase_location="Costco", default_expiry_days=100)
        self._add_inventory_stock(p_paper_id, "2 rolls")

        self._add_historical_consumption(p_paper_id, product_name, 1, 5)  # Consumed 1 roll 5 days ago
        self._add_historical_consumption(p_paper_id, product_name, 1, 15) # Consumed 1 roll 15 days ago
        self._add_historical_consumption(p_paper_id, product_name, 1, 25) # Consumed 1 roll 25 days ago
        # Avg daily consumption = 3 rolls / 30 days = 0.1 rolls/day

        shopping_list = self.manager.get_shopping_list_items()
        self.assertEqual(len(shopping_list), 1)
        item = shopping_list[0]
        self.assertEqual(item['name'], product_name)
        self.assertEqual(item['purchase_location'], "Costco")
         # Expected: Par(6) + CycleConsumption(0.1 * 21 = 2.1) - CurrentStock(2) = 6.1
        self.assertAlmostEqual(item['recommended_purchase_amount'], 6.1)
        self.assertEqual(item['par_level'], 6)
        self.assertEqual(item['days_to_next_shop'], 21)

    def test_get_shopping_list_mixed_items_no_filter(self):
        p_sobeys_id = self._create_product("Sobeys Item", par_level=2, purchase_location="Sobeys", unit_of_measure="units")
        self._add_inventory_stock(p_sobeys_id, "0.5 units") # Stock below par
        self._add_historical_consumption(p_sobeys_id,"Sobeys Item", 7, 3) # Avg consumption 7/30 = 0.233. Need 7*0.233 = 1.63 for cycle. Target 2+1.63=3.63. Buy 3.63-0.5 = 3.13

        p_costco_id = self._create_product("Costco Item", par_level=2, purchase_location="Costco", unit_of_measure="units")
        self._add_inventory_stock(p_costco_id, "0.5 units") # Stock below par
        self._add_historical_consumption(p_costco_id, "Costco Item", 21, 5) # Avg consumption 21/30 = 0.7. Need 21*0.7 = 14.7 for cycle. Target 2+14.7=16.7. Buy 16.7-0.5 = 16.2

        shopping_list = self.manager.get_shopping_list_items()
        self.assertEqual(len(shopping_list), 2)
        self.assertTrue(any(it['name'] == "Sobeys Item" for it in shopping_list))
        self.assertTrue(any(it['name'] == "Costco Item" for it in shopping_list))

    def test_get_shopping_list_filter_by_sobeys(self):
        p_sobeys_id = self._create_product("Sobeys Apples", par_level=2, purchase_location="Sobeys", unit_of_measure="units")
        self._add_inventory_stock(p_sobeys_id, "0.5 units")
        self._add_historical_consumption(p_sobeys_id, "Sobeys Apples", 7, 1)

        p_costco_id = self._create_product("Costco Oranges", par_level=2, purchase_location="Costco", unit_of_measure="units")
        self._add_inventory_stock(p_costco_id, "0.5 units")
        self._add_historical_consumption(p_costco_id, "Costco Oranges", 21, 1)

        shopping_list = self.manager.get_shopping_list_items(store_filter="Sobeys")
        self.assertEqual(len(shopping_list), 1)
        self.assertEqual(shopping_list[0]['name'], "Sobeys Apples")

    def test_get_shopping_list_filter_by_costco(self):
        p_sobeys_id = self._create_product("Sobeys Apples", par_level=2, purchase_location="Sobeys", unit_of_measure="units")
        self._add_inventory_stock(p_sobeys_id, "0.5 units")
        self._add_historical_consumption(p_sobeys_id, "Sobeys Apples", 7, 1)

        p_costco_id = self._create_product("Costco Oranges", par_level=2, purchase_location="Costco", unit_of_measure="units")
        self._add_inventory_stock(p_costco_id, "0.5 units")
        self._add_historical_consumption(p_costco_id, "Costco Oranges", 21, 1)

        shopping_list = self.manager.get_shopping_list_items(store_filter="Costco")
        self.assertEqual(len(shopping_list), 1)
        self.assertEqual(shopping_list[0]['name'], "Costco Oranges")

    def test_get_shopping_list_search_term(self):
        p1_id = self._create_product("Organic Apples", par_level=2, purchase_location="Sobeys", unit_of_measure="units")
        self._add_inventory_stock(p1_id, "0.5 units")
        self._add_historical_consumption(p1_id, "Organic Apples", 7, 1)

        p2_id = self._create_product("Apple Pie", par_level=2, purchase_location="Sobeys", unit_of_measure="units")
        self._add_inventory_stock(p2_id, "0.5 units")
        self._add_historical_consumption(p2_id, "Apple Pie", 7, 1)

        p3_id = self._create_product("Orange Juice", par_level=2, purchase_location="Sobeys", unit_of_measure="units")
        self._add_inventory_stock(p3_id, "0.5 units")
        self._add_historical_consumption(p3_id, "Orange Juice", 7, 1)


        shopping_list_apple = self.manager.get_shopping_list_items(search_term="Apple")
        self.assertEqual(len(shopping_list_apple), 2)
        self.assertTrue(any(it['name'] == "Organic Apples" for it in shopping_list_apple))
        self.assertTrue(any(it['name'] == "Apple Pie" for it in shopping_list_apple))

        shopping_list_pie = self.manager.get_shopping_list_items(search_term="Pie")
        self.assertEqual(len(shopping_list_pie), 1)
        self.assertEqual(shopping_list_pie[0]['name'], "Apple Pie")

        shopping_list_organic_apples = self.manager.get_shopping_list_items(search_term="Organic Apples")
        self.assertEqual(len(shopping_list_organic_apples), 1)
        self.assertEqual(shopping_list_organic_apples[0]['name'], "Organic Apples")


    def test_get_shopping_list_item_no_purchase_location_on_product(self):
        p_id = self._create_product("Mystery Item", par_level=2, purchase_location=None, unit_of_measure="units") # No purchase location
        self._add_inventory_stock(p_id, "0.5 units")
        self._add_historical_consumption(p_id, "Mystery Item", 7, 1)
        self.assertEqual(self.manager.get_shopping_list_items(), []) # Should not appear on list

    def test_get_shopping_list_item_zero_par_level_on_product(self):
        p_id = self._create_product("Zero Par Item", par_level=0, purchase_location="Sobeys", unit_of_measure="units") # Par level 0
        self._add_inventory_stock(p_id, "0.5 units")
        self._add_historical_consumption(p_id, "Zero Par Item", 7, 1)
        self.assertEqual(self.manager.get_shopping_list_items(), []) # Should not appear

    # test_get_shopping_list_item_none_par_level was about DB allowing None.
    # Our create_product has default for par_level, and update_product also.
    # So direct insertion was the only way. If that's not possible or not desired,
    # this test might be less relevant unless we explicitly want to test DB constraints vs application logic.
    # Given the current setup, a product will always have a par_level (default 0).
    # So, "None" par level test as previously written is not directly applicable via manager methods.
    # A product with par_level=0 is covered by the above test.

    def test_get_shopping_list_recommendation_logic_product_centric(self):
        product_name = "Test Item Reco"
        product_unit = "units"
        current_stock_numeric = 5.0
        par_level = 3.0
        daily_consumption_rate = 1.0
        purchase_location = "Sobeys" # 7-day cycle

        p_id = self._create_product(name=product_name, unit_of_measure=product_unit,
                                    par_level=par_level, purchase_location=purchase_location, default_expiry_days=30)
        self._add_inventory_stock(p_id, f"{current_stock_numeric} {product_unit}")

        for i in range(1, 31):
            self._add_historical_consumption(p_id, product_name, daily_consumption_rate, i)

        shopping_list = self.manager.get_shopping_list_items()
        self.assertEqual(len(shopping_list), 1)
        item = shopping_list[0]
        self.assertEqual(item['name'], product_name)

        self.assertAlmostEqual(item['avg_daily_consumption'], daily_consumption_rate, places=2)

        expected_proj_consumption = daily_consumption_rate * 7 # Sobeys cycle (7 days)
        expected_target_stock = par_level + expected_proj_consumption
        expected_reco = expected_target_stock - current_stock_numeric

        self.assertAlmostEqual(item['recommended_purchase_amount'], expected_reco, places=2)

if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
        """Test adding item with invalid date format."""
        result = self.manager.add_item_to_list("Invalid Date Item", "1", "2023/01/01", 5) # Wrong format
        self.assertFalse(result['success'])
        self.assertIn("Invalid date", result['message'])

    def test_consume_item_not_found(self):
        """Test consuming an item that is not in inventory."""
        result = self.manager.consume_item("NonExistent Item", 1.0)
        self.assertFalse(result['success'])
        self.assertIn("not found", result['message'])

    def tearDown(self):
        """Clean up resources, if any (though in-memory DB is auto-cleaned)."""
        # For in-memory DB, connection closure might not be strictly necessary here
        # as it's per-test, but good practice if it were a file-based DB.
        pass

    # --- Tests for get_shopping_list_items ---

    def test_get_shopping_list_empty_inventory(self):
        self.assertEqual(self.manager.get_shopping_list_items(), [])

    def test_get_shopping_list_no_qualifying_items(self):
        # Item with high stock compared to par and zero consumption
        self._add_inventory_item("Apples", "20 units", self.today_str, 14, par_level=5, purchase_location="Sobeys")
        # Item with par level 0
        self._add_inventory_item("Oranges", "5 units", self.today_str, 10, par_level=0, purchase_location="Sobeys")
        self._add_historical_consumption("Oranges", 1, 1) # Some consumption

        self.assertEqual(self.manager.get_shopping_list_items(), [])

    def test_get_shopping_list_sobeys_item_needed(self):
        item_name = "Milk"
        self._add_inventory_item(item_name, "1 L", self.today_str, 7, par_level=2, purchase_location="Sobeys")
        # Consumed 0.5L daily for past 10 days = 5L total / 30 days lookback = avg 0.166 L/day
        # More direct: consumed 7L in last 7 days = 1L/day
        for i in range(1, 8): # 7 days of consumption
            self._add_historical_consumption(item_name, 1, i)

        # Current stock: 1L. Par: 2L. Avg daily consumption: 1L/day.
        # Sobeys shop is in 7 days.
        # Projected consumption in 7 days: 1 * 7 = 7L.
        # Stock at next Sobeys shop: 1 - 7 = -6L.
        # Target stock after Sobeys shop = Par (2) + Consumption for next cycle (7) = 9L.
        # Recommended purchase = Target (9) - Current (1) = 8L.

        shopping_list = self.manager.get_shopping_list_items()
        self.assertEqual(len(shopping_list), 1)
        item = shopping_list[0]
        self.assertEqual(item['name'], item_name)
        self.assertEqual(item['purchase_location'], "Sobeys")
        self.assertAlmostEqual(item['recommended_purchase_amount'], 8.0)
        self.assertEqual(item['par_level'], 2)
        self.assertEqual(item['days_to_next_shop'], 7) # Sobeys frequency

    def test_get_shopping_list_costco_item_needed(self):
        item_name = "Paper Towels"
        self._add_inventory_item(item_name, "2 rolls", self.today_str, 100, par_level=6, purchase_location="Costco")
        # Consumed 1 roll every 7 days for the past 28 days = 4 rolls total / 30 day lookback = avg 0.133 rolls/day
        # Let's simplify: 3 rolls consumed over 30 days. Avg daily = 0.1
        self._add_historical_consumption(item_name, 1, 5)
        self._add_historical_consumption(item_name, 1, 15)
        self._add_historical_consumption(item_name, 1, 25)

        # Current stock: 2 rolls. Par: 6 rolls. Avg daily consumption: 0.1 rolls/day.
        # Costco shop is in 21 days.
        # Projected consumption in 21 days: 0.1 * 21 = 2.1 rolls.
        # Stock at next Costco shop: 2 - 2.1 = -0.1 rolls.
        # Target stock after Costco shop = Par (6) + Consumption for next cycle (2.1) = 8.1 rolls.
        # Recommended purchase = Target (8.1) - Current (2) = 6.1 rolls.

        shopping_list = self.manager.get_shopping_list_items()
        self.assertEqual(len(shopping_list), 1)
        item = shopping_list[0]
        self.assertEqual(item['name'], item_name)
        self.assertEqual(item['purchase_location'], "Costco")
        self.assertAlmostEqual(item['recommended_purchase_amount'], 6.1)
        self.assertEqual(item['par_level'], 6)
        self.assertEqual(item['days_to_next_shop'], 21) # Costco frequency

    def test_get_shopping_list_mixed_items_no_filter(self):
        # Sobeys item
        self._add_inventory_item("Sobeys Item", "1 unit", self.today_str, 7, par_level=2, purchase_location="Sobeys")
        self._add_historical_consumption("Sobeys Item", 1, 1) # Avg daily 1/30, need more to trigger
        self._add_historical_consumption("Sobeys Item", 7, 3) # Avg daily (1+7)/30 = 0.26. Need 7*0.26 = 1.82 for next cycle. Par 2. Rec should be >0

        # Costco item
        self._add_inventory_item("Costco Item", "1 unit", self.today_str, 21, par_level=2, purchase_location="Costco")
        self._add_historical_consumption("Costco Item", 21, 5) # Avg daily 21/30 = 0.7. Need 21*0.7 = 14.7 for next cycle. Par 2. Rec should be >0

        shopping_list = self.manager.get_shopping_list_items()
        self.assertEqual(len(shopping_list), 2)
        self.assertTrue(any(it['name'] == "Sobeys Item" for it in shopping_list))
        self.assertTrue(any(it['name'] == "Costco Item" for it in shopping_list))

    def test_get_shopping_list_filter_by_sobeys(self):
        self._add_inventory_item("Sobeys Apples", "1 unit", self.today_str, 7, par_level=2, purchase_location="Sobeys")
        self._add_historical_consumption("Sobeys Apples", 7, 1) # Qualifies
        self._add_inventory_item("Costco Oranges", "1 unit", self.today_str, 21, par_level=2, purchase_location="Costco")
        self._add_historical_consumption("Costco Oranges", 21, 1) # Qualifies

        shopping_list = self.manager.get_shopping_list_items(store_filter="Sobeys")
        self.assertEqual(len(shopping_list), 1)
        self.assertEqual(shopping_list[0]['name'], "Sobeys Apples")

    def test_get_shopping_list_filter_by_costco(self):
        self._add_inventory_item("Sobeys Apples", "1 unit", self.today_str, 7, par_level=2, purchase_location="Sobeys")
        self._add_historical_consumption("Sobeys Apples", 7, 1)
        self._add_inventory_item("Costco Oranges", "1 unit", self.today_str, 21, par_level=2, purchase_location="Costco")
        self._add_historical_consumption("Costco Oranges", 21, 1)

        shopping_list = self.manager.get_shopping_list_items(store_filter="Costco")
        self.assertEqual(len(shopping_list), 1)
        self.assertEqual(shopping_list[0]['name'], "Costco Oranges")

    def test_get_shopping_list_search_term(self):
        self._add_inventory_item("Organic Apples", "1 unit", self.today_str, 7, par_level=2, purchase_location="Sobeys")
        self._add_historical_consumption("Organic Apples", 7, 1)
        self._add_inventory_item("Apple Pie", "1 unit", self.today_str, 7, par_level=2, purchase_location="Sobeys")
        self._add_historical_consumption("Apple Pie", 7, 1)
        self._add_inventory_item("Orange Juice", "1 unit", self.today_str, 7, par_level=2, purchase_location="Sobeys")
        self._add_historical_consumption("Orange Juice", 7, 1)

        shopping_list_apple = self.manager.get_shopping_list_items(search_term="Apple")
        self.assertEqual(len(shopping_list_apple), 2)
        self.assertTrue(any(it['name'] == "Organic Apples" for it in shopping_list_apple))
        self.assertTrue(any(it['name'] == "Apple Pie" for it in shopping_list_apple))

        shopping_list_pie = self.manager.get_shopping_list_items(search_term="Pie")
        self.assertEqual(len(shopping_list_pie), 1)
        self.assertEqual(shopping_list_pie[0]['name'], "Apple Pie")

        shopping_list_organic_apples = self.manager.get_shopping_list_items(search_term="Organic Apples")
        self.assertEqual(len(shopping_list_organic_apples), 1)
        self.assertEqual(shopping_list_organic_apples[0]['name'], "Organic Apples")


    def test_get_shopping_list_item_no_purchase_location(self):
        self._add_inventory_item("Mystery Item", "1 unit", self.today_str, 7, par_level=2, purchase_location=None)
        self._add_historical_consumption("Mystery Item", 7, 1) # Would qualify if it had a location
        self.assertEqual(self.manager.get_shopping_list_items(), [])

    def test_get_shopping_list_item_zero_par_level(self):
        self._add_inventory_item("Zero Par Item", "1 unit", self.today_str, 7, par_level=0, purchase_location="Sobeys")
        self._add_historical_consumption("Zero Par Item", 7, 1) # Would qualify if par > 0
        self.assertEqual(self.manager.get_shopping_list_items(), [])

    def test_get_shopping_list_item_none_par_level(self):
        # Test case where par_level might be None in DB (though schema defaults to 0)
        # Add item with par_level explicitly set to None if DB allows (our add method defaults it)
        conn = self.manager._get_db_connection()
        cursor = conn.cursor()
        item_name = "None Par Item"
        cursor.execute('''
            INSERT INTO inventory_items (name, quantity, purchase_date, expiry_date, par_level, purchase_location)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (item_name, "1 unit", self.today_str, (self.today + timedelta(days=7)).isoformat(), None, "Sobeys"))
        conn.commit()
        conn.close()
        self._add_historical_consumption(item_name, 7, 1)
        self.assertEqual(self.manager.get_shopping_list_items(), [])


    def test_get_shopping_list_recommendation_logic(self):
        item_name = "Test Item Reco"
        current_stock = 5
        par_level = 3
        daily_consumption_rate = 1
        purchase_location = "Sobeys" # 7-day cycle

        self._add_inventory_item(item_name, f"{current_stock} units", self.today_str, 30,
                                 par_level=par_level, purchase_location=purchase_location)

        # Simulate daily consumption for 30 days to establish avg rate
        for i in range(1, 31): # days ago
            self._add_historical_consumption(item_name, daily_consumption_rate, i)

        # Expected calculation:
        # Avg Daily Consumption should be very close to daily_consumption_rate (1)
        # Projection days for Sobeys = 7 days
        # Projected consumption until next shop = avg_daily_consumption * 7
        #   (approx. 1 * 7 = 7 units)
        # Stock at next shop = current_stock - projected_consumption_until_next_shop
        #   (approx. 5 - 7 = -2 units)
        # Target stock after shopping = par_level + projected_consumption_until_next_shop
        #   (approx. 3 + 7 = 10 units)
        # Recommended purchase amount = target_stock_after_shopping - current_stock
        #   (approx. 10 - 5 = 5 units)

        shopping_list = self.manager.get_shopping_list_items()
        self.assertEqual(len(shopping_list), 1)
        item = shopping_list[0]
        self.assertEqual(item['name'], item_name)
        # Verify avg daily consumption from projection_demand method
        # total consumed = 30 * 1 = 30. avg = 30/30 = 1.
        self.assertAlmostEqual(item['avg_daily_consumption'], daily_consumption_rate, places=2)

        expected_proj_consumption = daily_consumption_rate * 7 # Sobeys cycle
        expected_target_stock = par_level + expected_proj_consumption
        expected_reco = expected_target_stock - current_stock

        self.assertAlmostEqual(item['recommended_purchase_amount'], expected_reco, places=2)

if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
