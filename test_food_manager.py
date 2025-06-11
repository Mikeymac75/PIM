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
        # Verify the actual stored quantity string in the database
        conn = self.manager._get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT quantity FROM inventory_items WHERE product_id = ?", (product_id,))
        db_quantity_str = cursor.fetchone()['quantity']
        conn.close()
        # After consuming 3.0 from "10 units" (parsed as 10.0), new quantity is 7.0, stored as "7"
        self.assertEqual(db_quantity_str, "7")


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
        
        # Add stock with plain numeric strings, as expected by add_inventory_stock now
        self._add_inventory_stock(product_id_grapes, "100")
        self._add_inventory_stock(product_id_grapes, "150") # Another batch

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
        # Add stock with plain numeric string
        self._add_inventory_stock(p_milk_id, "1")

        for i in range(1, 8): # 7 days of consumption, 1L per day
            self._add_historical_consumption(p_milk_id, product_name, 1, i)

        shopping_list = self.manager.get_shopping_list_items()
        self.assertEqual(len(shopping_list), 1)
        item = shopping_list[0]
        self.assertEqual(item['name'], product_name)
        self.assertEqual(item['unit_of_measure'], product_unit)
        self.assertEqual(item['current_quantity_display'], f"1.00 {product_unit}") # Verify formatted display
        self.assertIsInstance(item['recommended_purchase_amount'], float) # Verify type
        self.assertEqual(item['purchase_location'], "Sobeys")
        self.assertAlmostEqual(item['recommended_purchase_amount'], 8.0) # Expected: Par(2) + CycleConsumption(7) - CurrentStock(1) = 8
        self.assertEqual(item['par_level'], 2)
        self.assertEqual(item['days_to_next_shop'], 7)

    def test_get_shopping_list_costco_item_needed(self):
        product_name = "Paper Towels"
        product_unit = "rolls"
        p_paper_id = self._create_product(name=product_name, unit_of_measure=product_unit, par_level=6, purchase_location="Costco", default_expiry_days=100)
        # Add stock with plain numeric string
        self._add_inventory_stock(p_paper_id, "2")

        self._add_historical_consumption(p_paper_id, product_name, 1, 5)  # Consumed 1 roll 5 days ago
        self._add_historical_consumption(p_paper_id, product_name, 1, 15) # Consumed 1 roll 15 days ago
        self._add_historical_consumption(p_paper_id, product_name, 1, 25) # Consumed 1 roll 25 days ago
        # Avg daily consumption = 3 rolls / 30 days = 0.1 rolls/day

        shopping_list = self.manager.get_shopping_list_items()
        self.assertEqual(len(shopping_list), 1)
        item = shopping_list[0]
        self.assertEqual(item['name'], product_name)
        self.assertEqual(item['unit_of_measure'], product_unit)
        self.assertEqual(item['current_quantity_display'], f"2.00 {product_unit}")
        self.assertIsInstance(item['recommended_purchase_amount'], float)
        self.assertEqual(item['purchase_location'], "Costco")
         # Expected: Par(6) + CycleConsumption(0.1 * 21 = 2.1) - CurrentStock(2) = 6.1
        self.assertAlmostEqual(item['recommended_purchase_amount'], 6.1)
        self.assertEqual(item['par_level'], 6)
        self.assertEqual(item['days_to_next_shop'], 21)

    def test_get_shopping_list_mixed_items_no_filter(self):
        p_sobeys_id = self._create_product("Sobeys Item", par_level=2, purchase_location="Sobeys", unit_of_measure="units")
        self._add_inventory_stock(p_sobeys_id, "0.5") # Stock below par
        self._add_historical_consumption(p_sobeys_id,"Sobeys Item", 7, 3)

        p_costco_id = self._create_product("Costco Item", par_level=2, purchase_location="Costco", unit_of_measure="units")
        self._add_inventory_stock(p_costco_id, "0.5") # Stock below par
        self._add_historical_consumption(p_costco_id, "Costco Item", 21, 5)

        shopping_list = self.manager.get_shopping_list_items()
        self.assertEqual(len(shopping_list), 2)
        self.assertTrue(any(it['name'] == "Sobeys Item" for it in shopping_list))
        self.assertTrue(any(it['name'] == "Costco Item" for it in shopping_list))
        for item in shopping_list: # Check all items
            self.assertIn('unit_of_measure', item)
            self.assertEqual(item['unit_of_measure'], "units")
            self.assertIsInstance(item['recommended_purchase_amount'], float)
            self.assertTrue(item['current_quantity_display'].endswith(" units"))


    def test_get_shopping_list_filter_by_sobeys(self):
        p_sobeys_id = self._create_product("Sobeys Apples", par_level=2, purchase_location="Sobeys", unit_of_measure="units")
        self._add_inventory_stock(p_sobeys_id, "0.5")
        self._add_historical_consumption(p_sobeys_id, "Sobeys Apples", 7, 1)

        p_costco_id = self._create_product("Costco Oranges", par_level=2, purchase_location="Costco", unit_of_measure="units")
        self._add_inventory_stock(p_costco_id, "0.5")
        self._add_historical_consumption(p_costco_id, "Costco Oranges", 21, 1)

        shopping_list = self.manager.get_shopping_list_items(store_filter="Sobeys")
        self.assertEqual(len(shopping_list), 1)
        self.assertEqual(shopping_list[0]['name'], "Sobeys Apples")
        self.assertEqual(shopping_list[0]['unit_of_measure'], "units")
        self.assertTrue(shopping_list[0]['current_quantity_display'].endswith(" units"))
        self.assertIsInstance(shopping_list[0]['recommended_purchase_amount'], float)


    def test_get_shopping_list_filter_by_costco(self):
        p_sobeys_id = self._create_product("Sobeys Apples", par_level=2, purchase_location="Sobeys", unit_of_measure="units")
        self._add_inventory_stock(p_sobeys_id, "0.5")
        self._add_historical_consumption(p_sobeys_id, "Sobeys Apples", 7, 1)

        p_costco_id = self._create_product("Costco Oranges", par_level=2, purchase_location="Costco", unit_of_measure="units")
        self._add_inventory_stock(p_costco_id, "0.5")
        self._add_historical_consumption(p_costco_id, "Costco Oranges", 21, 1)

        shopping_list = self.manager.get_shopping_list_items(store_filter="Costco")
        self.assertEqual(len(shopping_list), 1)
        self.assertEqual(shopping_list[0]['name'], "Costco Oranges")
        self.assertEqual(shopping_list[0]['unit_of_measure'], "units")

    def test_get_shopping_list_search_term(self):
        p1_id = self._create_product("Organic Apples", par_level=2, purchase_location="Sobeys", unit_of_measure="units")
        self._add_inventory_stock(p1_id, "0.5")
        self._add_historical_consumption(p1_id, "Organic Apples", 7, 1)

        p2_id = self._create_product("Apple Pie", par_level=2, purchase_location="Sobeys", unit_of_measure="units")
        self._add_inventory_stock(p2_id, "0.5")
        self._add_historical_consumption(p2_id, "Apple Pie", 7, 1)

        p3_id = self._create_product("Orange Juice", par_level=2, purchase_location="Sobeys", unit_of_measure="units")
        self._add_inventory_stock(p3_id, "0.5")
        self._add_historical_consumption(p3_id, "Orange Juice", 7, 1)


        shopping_list_apple = self.manager.get_shopping_list_items(search_term="Apple")
        self.assertEqual(len(shopping_list_apple), 2)
        self.assertTrue(any(it['name'] == "Organic Apples" for it in shopping_list_apple))
        self.assertTrue(any(it['name'] == "Apple Pie" for it in shopping_list_apple))
        for item in shopping_list_apple:
            self.assertEqual(item['unit_of_measure'], "units")
            self.assertIsInstance(item['recommended_purchase_amount'], float)


        shopping_list_pie = self.manager.get_shopping_list_items(search_term="Pie")
        self.assertEqual(len(shopping_list_pie), 1)
        self.assertEqual(shopping_list_pie[0]['name'], "Apple Pie")
        self.assertEqual(shopping_list_pie[0]['unit_of_measure'], "units")


        shopping_list_organic_apples = self.manager.get_shopping_list_items(search_term="Organic Apples")
        self.assertEqual(len(shopping_list_organic_apples), 1)
        self.assertEqual(shopping_list_organic_apples[0]['name'], "Organic Apples")
        self.assertEqual(shopping_list_organic_apples[0]['unit_of_measure'], "units")


    def test_get_shopping_list_item_no_purchase_location_on_product(self):
        p_id = self._create_product("Mystery Item", par_level=2, purchase_location=None, unit_of_measure="units") # No purchase location
        self._add_inventory_stock(p_id, "0.5")
        self._add_historical_consumption(p_id, "Mystery Item", 7, 1)
        self.assertEqual(self.manager.get_shopping_list_items(), []) # Should not appear on list

    def test_get_shopping_list_item_zero_par_level_on_product(self):
        p_id = self._create_product("Zero Par Item", par_level=0, purchase_location="Sobeys", unit_of_measure="units") # Par level 0
        self._add_inventory_stock(p_id, "0.5")
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
        current_stock_numeric_str = "5.0" # How it's added to stock
        current_stock_numeric = 5.0 # The float value
        par_level = 3.0
        daily_consumption_rate = 1.0
        purchase_location = "Sobeys" # 7-day cycle

        p_id = self._create_product(name=product_name, unit_of_measure=product_unit,
                                    par_level=par_level, purchase_location=purchase_location, default_expiry_days=30)
        self._add_inventory_stock(p_id, current_stock_numeric_str) # Use numeric string for adding stock

        for i in range(1, 31):
            self._add_historical_consumption(p_id, product_name, daily_consumption_rate, i)

        shopping_list = self.manager.get_shopping_list_items()
        self.assertEqual(len(shopping_list), 1)
        item = shopping_list[0]
        self.assertEqual(item['name'], product_name)
        self.assertEqual(item['unit_of_measure'], product_unit)
        self.assertEqual(item['current_quantity_display'], f"{current_stock_numeric:.2f} {product_unit}")
        self.assertIsInstance(item['recommended_purchase_amount'], float)


        self.assertAlmostEqual(item['avg_daily_consumption'], daily_consumption_rate, places=2)

        expected_proj_consumption = daily_consumption_rate * 7 # Sobeys cycle (7 days)
        expected_target_stock = par_level + expected_proj_consumption
        expected_reco = expected_target_stock - current_stock_numeric

        self.assertAlmostEqual(item['recommended_purchase_amount'], expected_reco, places=2)

if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
        """Test adding item with invalid date format."""
        # This test was using add_item_to_list, which is deprecated.
        # Re-evaluating if this test is still needed or how it fits with add_inventory_stock
        # add_inventory_stock uses product's default_expiry_days, not one from parameters.
        # The date format for purchase_date is validated in add_inventory_stock.
        # Let's keep this as a general test for _add_inventory_stock if it handles date validation.
        product_id = self._create_product(name="Date Format Test Prod")
        result = self.manager.add_inventory_stock(product_id, "1", "2023/01/01") # Invalid date format
        self.assertFalse(result['success'])
        self.assertIn("Invalid date or expiry day format", result['message'])


    def test_consume_item_not_found(self):
        """Test consuming an item that is not in inventory (product exists, no stock)."""
        self._create_product(name="NoStockToConsume")
        result = self.manager.consume_item("NoStockToConsume", 1.0) # Product exists, but no stock
        self.assertFalse(result['success'])
        self.assertIn("Item 'NoStockToConsume' not found in inventory", result['message'])


    def tearDown(self):
        """Clean up resources, if any (though in-memory DB is auto-cleaned)."""
        pass

    # --- Tests for get_shopping_list_items (related to product integration) ---
    # The _add_inventory_item helper is not defined in this class, these tests will fail.
    # These tests need to use _create_product and _add_inventory_stock.
    # I will comment out these older shopping list tests as they are not compatible
    # with the product-centric approach and helper methods (_create_product, _add_inventory_stock)
    # The shopping list tests from the first TestInventoryManager class are more up-to-date.
    pass

    # --- Tests for adjust_inventory_batch ---
    def test_adjust_inventory_batch_quantity_decrease_no_projection_impact(self):
        product_id = self._create_product(name="Adjustable Nuts", unit_of_measure="g")
        add_result = self._add_inventory_stock(product_id, "100") # Add 100g
        self.assertIsNotNone(add_result.get("stock_item_id"), "stock_item_id should be returned by _add_inventory_stock")
        batch_id = add_result.get("stock_item_id")

        adjust_result = self.manager.adjust_inventory_batch(
            batch_id, "50", include_in_projections=False # new_quantity_str, include_in_projections
        )
        self.assertTrue(adjust_result["success"])

        # Verify inventory_items
        updated_batch = self.manager.get_inventory_batches_for_product(product_id, limit=1)[0]
        self.assertEqual(updated_batch["quantity"], "50")

        # Verify historical_items: NO new entry should be made for this adjustment.
        historical_items_after = self.manager.get_historical_inventory()
        # Filter for adjustment notes specifically for this batch
        adjustment_notes_for_batch = [
            h for h in historical_items_after
            if h.get('notes') and f"Batch ID {batch_id} quantity adjusted" in h['notes']
        ]
        self.assertEqual(len(adjustment_notes_for_batch), 0, "Historical log should not be created when include_in_projections is False.")

    def test_adjust_inventory_batch_quantity_decrease_with_projection_impact(self):
        product_id = self._create_product(name="Projected Nuts", unit_of_measure="g")
        add_result = self._add_inventory_stock(product_id, "200")
        self.assertIsNotNone(add_result.get("stock_item_id"))
        batch_id = add_result.get("stock_item_id")

        adjust_result = self.manager.adjust_inventory_batch(
            batch_id, "150", include_in_projections=True
        )
        self.assertTrue(adjust_result["success"])
        updated_batch = self.manager.get_inventory_batches_for_product(product_id, limit=1)[0]
        self.assertEqual(updated_batch["quantity"], "150")

        historical_items = self.manager.get_historical_inventory()
        adjustment_log = [h for h in historical_items if h['notes'] and f"Batch ID {batch_id} quantity adjusted" in h['notes']]
        self.assertEqual(len(adjustment_log), 1)
        self.assertEqual(adjustment_log[0]['quantity_consumed_this_time'], 50) # 200 - 150 = 50 "consumed"
        # Here, if include_in_projections=True was meant to create a *different* type of historical log,
        # the adjust_inventory_batch method would need to reflect that. Current impl logs same way.

    def test_adjust_inventory_batch_quantity_increase_with_projection_impact(self):
        product_id = self._create_product(name="More Nuts", unit_of_measure="g")
        add_result = self._add_inventory_stock(product_id, "50")
        self.assertIsNotNone(add_result.get("stock_item_id"))
        batch_id = add_result.get("stock_item_id")

        adjust_result = self.manager.adjust_inventory_batch(
            batch_id, "100", include_in_projections=True
        )
        self.assertTrue(adjust_result["success"])
        updated_batch = self.manager.get_inventory_batches_for_product(product_id, limit=1)[0]
        self.assertEqual(updated_batch["quantity"], "100")

        historical_items = self.manager.get_historical_inventory()
        adjustment_log = [h for h in historical_items if h['notes'] and f"Batch ID {batch_id} quantity adjusted" in h['notes']]
        self.assertEqual(len(adjustment_log), 1)
        self.assertEqual(adjustment_log[0]['quantity_consumed_this_time'], -50) # 50 - 100 = -50 "consumed" (means added)


    def test_adjust_inventory_batch_non_existent_id(self):
        result = self.manager.adjust_inventory_batch(999, "10")
        self.assertFalse(result["success"])
        self.assertIn("not found", result["message"])

    def test_adjust_inventory_batch_quantity_to_zero(self):
        product_id = self._create_product(name="Zero Nuts")
        add_result = self._add_inventory_stock(product_id, "10")
        self.assertIsNotNone(add_result.get("stock_item_id"))
        batch_id = add_result.get("stock_item_id")

        # Test deletion when include_in_projections is True (should log)
        adjust_result_proj_true = self.manager.adjust_inventory_batch(batch_id, "0", include_in_projections=True)
        self.assertTrue(adjust_result_proj_true["success"])
        self.assertIn(f"Batch ID {batch_id} ('Zero Nuts') deleted", adjust_result_proj_true["message"])

        # Verify item is deleted
        deleted_batch_check = self.manager.get_inventory_batches_for_product(product_id)
        self.assertEqual(len(deleted_batch_check), 0, "Batch should be deleted from inventory_items.")

        # Verify historical log was made
        historical_items_true = self.manager.get_historical_inventory()
        adjustment_log_true = [
            h for h in historical_items_true
            if h.get('notes') and f"Batch ID {batch_id} quantity adjusted" in h['notes'] and h['quantity_consumed_this_time'] == 10 # Original quantity
        ]
        self.assertEqual(len(adjustment_log_true), 1, "Historical log for deletion (proj=True) should exist.")

        # Re-add for next test case
        add_result_2 = self._add_inventory_stock(product_id, "15") # New batch ID
        batch_id_2 = add_result_2.get("stock_item_id")
        self.assertIsNotNone(batch_id_2)

        # Test deletion when include_in_projections is False (should NOT log adjustment for projection)
        historical_count_before_false = len([
            h for h in self.manager.get_historical_inventory()
            if h.get('notes') and f"Batch ID {batch_id_2} quantity adjusted" in h['notes']
        ])

        adjust_result_proj_false = self.manager.adjust_inventory_batch(batch_id_2, "0", include_in_projections=False)
        self.assertTrue(adjust_result_proj_false["success"])
        self.assertIn(f"Batch ID {batch_id_2} ('Zero Nuts') deleted", adjust_result_proj_false["message"])

        deleted_batch_check_2 = self.manager.get_inventory_batches_for_product(product_id)
        self.assertEqual(len(deleted_batch_check_2), 0, "Batch should be deleted (proj=False).")

        historical_count_after_false = len([
            h for h in self.manager.get_historical_inventory()
            if h.get('notes') and f"Batch ID {batch_id_2} quantity adjusted" in h['notes']
        ])
        self.assertEqual(historical_count_after_false, historical_count_before_false, "Historical log should NOT be created for deletion (proj=False).")


    def test_adjust_inventory_batch_dates(self):
        product_id = self._create_product(name="Date Nuts")
        add_result = self._add_inventory_stock(product_id, "10", self.today_str)
        self.assertIsNotNone(add_result.get("stock_item_id"))
        batch_id = add_result.get("stock_item_id")

        new_purchase_date = (self.today - timedelta(days=5)).isoformat()
        new_expiry_date = (self.today + timedelta(days=25)).isoformat()

        adjust_result = self.manager.adjust_inventory_batch(
            batch_id, "10", new_purchase_date, new_expiry_date
        )
        self.assertTrue(adjust_result["success"])

        updated_batch = self.manager.get_inventory_batches_for_product(product_id, limit=1)[0]
        self.assertEqual(updated_batch["purchase_date"].isoformat(), new_purchase_date)
        self.assertEqual(updated_batch["expiry_date"].isoformat(), new_expiry_date)

    def test_adjust_inventory_batch_invalid_input(self):
        product_id = self._create_product(name="Invalid Nuts")
        add_result = self._add_inventory_stock(product_id, "10")
        self.assertIsNotNone(add_result.get("stock_item_id"))
        batch_id = add_result.get("stock_item_id")

        # Invalid quantity
        result_neg_qty = self.manager.adjust_inventory_batch(batch_id, "-5")
        self.assertFalse(result_neg_qty["success"])
        self.assertIn("Quantity cannot be negative", result_neg_qty["message"])

        # Invalid purchase date format
        result_bad_pdate = self.manager.adjust_inventory_batch(batch_id, "10", "2023/13/01")
        self.assertFalse(result_bad_pdate["success"])
        self.assertIn("Invalid new purchase date format", result_bad_pdate["message"])

        # Invalid expiry date format
        result_bad_edate = self.manager.adjust_inventory_batch(batch_id, "10", None, "bad-date")
        self.assertFalse(result_bad_edate["success"])
        self.assertIn("Invalid new expiry date format", result_bad_edate["message"])

    # --- Tests for get_inventory_batches_for_product ---
    def test_get_inventory_batches_for_product_basic(self):
        p1_id = self._create_product("Product A")
        p2_id = self._create_product("Product B")

        # Batches for Product A
        self._add_inventory_stock(p1_id, "10 A1", (self.today - timedelta(days=2)).isoformat()) # ID 1 (approx)
        self._add_inventory_stock(p1_id, "20 A2", (self.today - timedelta(days=1)).isoformat()) # ID 2

        # Batches for Product B
        self._add_inventory_stock(p2_id, "30 B1", self.today_str) # ID 3

        batches_A = self.manager.get_inventory_batches_for_product(p1_id)
        self.assertEqual(len(batches_A), 2)
        self.assertTrue(all(b['product_id'] == p1_id for b in batches_A))
        # Default order is expiry ASC, then ID ASC.
        # P1 Stock: A1 (pdate today-2, exp today-2+10=today+8), A2 (pdate today-1, exp today-1+10=today+9)
        # Assuming default_expiry_days = 10 for product
        self.assertEqual(batches_A[0]['quantity'], "10 A1") # Earlier expiry
        self.assertEqual(batches_A[1]['quantity'], "20 A2")


        batches_B = self.manager.get_inventory_batches_for_product(p2_id)
        self.assertEqual(len(batches_B), 1)
        self.assertEqual(batches_B[0]['product_id'], p2_id)
        self.assertEqual(batches_B[0]['quantity'], "30 B1")


    def test_get_inventory_batches_limit(self):
        p_id = self._create_product("Limited Product")
        self._add_inventory_stock(p_id, "10 units")
        self._add_inventory_stock(p_id, "20 units")
        self._add_inventory_stock(p_id, "30 units")

        batches = self.manager.get_inventory_batches_for_product(p_id, limit=2)
        self.assertEqual(len(batches), 2)
        # Default order is expiry ASC, then ID ASC. Assuming all added today with same default expiry.
        # So, order by ID ASC.
        self.assertEqual(batches[0]['quantity'], "10 units")
        self.assertEqual(batches[1]['quantity'], "20 units")


    def test_get_inventory_batches_order_by_id_desc(self):
        p_id = self._create_product("ID Order Product", default_expiry_days=5)
        s1 = self._add_inventory_stock(p_id, "Batch1", (self.today - timedelta(days=2)).isoformat()) # Expires in 3 days
        s2 = self._add_inventory_stock(p_id, "Batch2", (self.today - timedelta(days=1)).isoformat()) # Expires in 4 days
        s3 = self._add_inventory_stock(p_id, "Batch3", self.today_str) # Expires in 5 days

        batches = self.manager.get_inventory_batches_for_product(p_id, order_by_id_desc=True)
        self.assertEqual(len(batches), 3)
        self.assertEqual(batches[0]['id'], s3.get('stock_item_id')) # Most recent ID
        self.assertEqual(batches[1]['id'], s2.get('stock_item_id'))
        self.assertEqual(batches[2]['id'], s1.get('stock_item_id'))

    def test_get_inventory_batches_order_by_purchase_date_desc(self):
        p_id = self._create_product("Purchase Order Product", default_expiry_days=30)
        # Add batches with purchase dates out of order of their ID
        s1 = self._add_inventory_stock(p_id, "Oldest Purchase", (self.today - timedelta(days=10)).isoformat())
        s2 = self._add_inventory_stock(p_id, "Newest Purchase", self.today_str)
        s3 = self._add_inventory_stock(p_id, "Middle Purchase", (self.today - timedelta(days=5)).isoformat())

        batches = self.manager.get_inventory_batches_for_product(p_id, order_by_purchase_desc=True)
        self.assertEqual(len(batches), 3)
        self.assertEqual(batches[0]['id'], s2.get('stock_item_id')) # Newest purchase
        self.assertEqual(batches[1]['id'], s3.get('stock_item_id')) # Middle purchase
        self.assertEqual(batches[2]['id'], s1.get('stock_item_id')) # Oldest purchase

    def test_get_inventory_batches_default_order_expiry_asc_id_asc(self):
        # This test requires careful setup of expiry dates.
        # The product's default_expiry_days is used by _add_inventory_stock.
        # To test sorting by expiry date, we need items with different expiry dates for the *same* product.

        self.setUp() # Reset DB for clean IDs and consistent product creation.

        p_mix_id = self._create_product("MixedExpiryProduct", default_expiry_days=10) # Default expiry for this product

        # Batch 1: purchase_date=today, default expiry=today+10.
        s_batch1_res = self._add_inventory_stock(p_mix_id, "StdExpiry", self.today_str)

        # Batch 2: purchase_date=today-5, default expiry=today-5+10 = today+5 (earliest expiry)
        s_batch2_res = self._add_inventory_stock(p_mix_id, "EarlyExpiry", (self.today - timedelta(days=5)).isoformat())

        # Batch 3: purchase_date=today-2, default expiry=today-2+10 = today+8 (middle expiry)
        # Add it last so its ID is higher than s_batch1_res if IDs are sequential, to test secondary sort by ID.
        s_batch3_res = self._add_inventory_stock(p_mix_id, "MidExpiry", (self.today - timedelta(days=2)).isoformat())

        batches = self.manager.get_inventory_batches_for_product(p_mix_id) # Default order

        # Expected order: Batch2 (expires today+5), Batch3 (expires today+8), Batch1 (expires today+10)
        self.assertEqual(len(batches), 3)
        self.assertEqual(batches[0]['id'], s_batch2_res.get('stock_item_id'))
        self.assertEqual(batches[1]['id'], s_batch3_res.get('stock_item_id'))
        self.assertEqual(batches[2]['id'], s_batch1_res.get('stock_item_id'))

    def test_get_inventory_batches_product_with_no_batches(self):
        p_id = self._create_product("No Batch Product")
        batches = self.manager.get_inventory_batches_for_product(p_id)
        self.assertEqual(len(batches), 0)

    def test_get_inventory_batches_invalid_product_id_format(self):
        # Test with a non-integer product_id string
        batches = self.manager.get_inventory_batches_for_product("not-an-id")
        self.assertEqual(len(batches), 0) # Method should handle gracefully and return empty list

        # Test with None product_id
        batches_none = self.manager.get_inventory_batches_for_product(None)
        self.assertEqual(len(batches_none), 0)


if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
