import unittest
import sqlite3
from Food_manager import InventoryManager
from datetime import date
import unittest.mock


class TestInventoryManager(unittest.TestCase):
    def setUp(self):
        """Set up a temporary in-memory database and populate it with test data."""
        self.manager = InventoryManager(db_filepath=":memory:")

        # Add categories
        cat_produce_result = self.manager.add_category("Produce")
        self.produce_cat_id = cat_produce_result['category_id']

        cat_meat_result = self.manager.add_category("Meat")
        self.meat_cat_id = cat_meat_result['category_id']

        cat_dairy_result = self.manager.add_category("Dairy")
        self.dairy_cat_id = cat_dairy_result['category_id']

        cat_bakery_result = self.manager.add_category("Bakery")
        self.bakery_cat_id = cat_bakery_result['category_id']

        cat_test_result = self.manager.add_category("Test")
        self.test_cat_id = cat_test_result['category_id']

        # This one is for add_item_to_list tests where category might be new from Excel
        # self.new_cat_excel_name = "New Category From Excel"
        # No need to pre-add it, test will try to add it via add_item_to_list

        # Add subcategories
        subcat_fruit_result = self.manager.add_subcategory("Fruit", self.produce_cat_id)
        self.fruit_subcat_id = subcat_fruit_result['subcategory_id']

        subcat_poultry_result = self.manager.add_subcategory("Poultry", self.meat_cat_id)
        self.poultry_subcat_id = subcat_poultry_result['subcategory_id']

        subcat_milk_result = self.manager.add_subcategory("Milk Products", self.dairy_cat_id)
        self.milk_subcat_id = subcat_milk_result['subcategory_id']

        subcat_bread_result = self.manager.add_subcategory("Bread", self.bakery_cat_id)
        self.bread_subcat_id = subcat_bread_result['subcategory_id']

        subcat_fish_result = self.manager.add_subcategory("Fish", self.meat_cat_id)
        self.fish_subcat_id = subcat_fish_result['subcategory_id']

        subcat_veg_result = self.manager.add_subcategory("Vegetable", self.produce_cat_id)
        self.veg_subcat_id = subcat_veg_result['subcategory_id']

        # Populate with diverse product data using new signature
        self.products_data_def = [
            {'name': 'Apples', 'category_id': self.produce_cat_id, 'subcategory_id': self.fruit_subcat_id, 'unit_of_measure': 'kg', 'default_expiry_days': 10, 'purchase_location': 'Store A', 'par_level': 5.0, 'max_holding_amount': 10.0},
            {'name': 'Bananas', 'category_id': self.produce_cat_id, 'subcategory_id': self.fruit_subcat_id, 'unit_of_measure': 'kg', 'default_expiry_days': 5, 'purchase_location': 'Store B', 'par_level': 2.0, 'max_holding_amount': 5.0},
            {'name': 'Chicken Breast', 'category_id': self.meat_cat_id, 'subcategory_id': self.poultry_subcat_id, 'unit_of_measure': 'kg', 'default_expiry_days': 3, 'purchase_location': 'Store A', 'par_level': 1.0, 'max_holding_amount': 3.0},
            {'name': 'Milk', 'category_id': self.dairy_cat_id, 'subcategory_id': self.milk_subcat_id, 'unit_of_measure': 'liter', 'default_expiry_days': 7, 'purchase_location': 'Store C', 'par_level': 2.0, 'max_holding_amount': 4.0},
            {'name': 'Bread', 'category_id': self.bakery_cat_id, 'subcategory_id': self.bread_subcat_id, 'unit_of_measure': 'loaf', 'default_expiry_days': 4, 'purchase_location': 'Store B', 'par_level': 1.0, 'max_holding_amount': 2.0},
            {'name': 'Organic Apples', 'category_id': self.produce_cat_id, 'subcategory_id': self.fruit_subcat_id, 'unit_of_measure': 'kg', 'default_expiry_days': 12, 'purchase_location': 'Store D', 'par_level': 3.0, 'max_holding_amount': 6.0},
            {'name': 'Salmon Fillet', 'category_id': self.meat_cat_id, 'subcategory_id': self.fish_subcat_id, 'unit_of_measure': 'kg', 'default_expiry_days': 2, 'purchase_location': 'Store A', 'par_level': 0.5, 'max_holding_amount': 1.5},
            {'name': 'Yogurt', 'category_id': self.dairy_cat_id, 'subcategory_id': self.milk_subcat_id, 'unit_of_measure': 'kg', 'default_expiry_days': 14, 'purchase_location': 'Store C', 'par_level': 4.0, 'max_holding_amount': 8.0},
            {'name': 'Carrots', 'category_id': self.produce_cat_id, 'subcategory_id': self.veg_subcat_id, 'unit_of_measure': 'kg', 'default_expiry_days': 10, 'purchase_location': 'Store B', 'par_level': 1.0, 'max_holding_amount': 2.5},
            {'name': 'Whole Wheat Bread', 'category_id': self.bakery_cat_id, 'subcategory_id': self.bread_subcat_id, 'unit_of_measure': 'loaf', 'default_expiry_days': 5, 'purchase_location': 'Store D', 'par_level': 1.0, 'max_holding_amount': 3.0},
        ]

        self.product_ids_setup = {} # To store actual IDs of created products

        for p_data in self.products_data_def:
            create_result = self.manager.create_product(
                name=p_data['name'],
                category_id=p_data['category_id'],
                subcategory_id=p_data.get('subcategory_id'),
                unit_of_measure=p_data['unit_of_measure'],
                default_expiry_days=p_data['default_expiry_days'],
                par_level=p_data.get('par_level', 0),
                max_holding_amount=p_data.get('max_holding_amount', 0),
                purchase_location=p_data.get('purchase_location')
            )
            self.assertTrue(create_result.get("success"), f"Failed to create product {p_data['name']}: {create_result.get('message')}")
            if create_result.get("success"):
                 self.product_ids_setup[p_data['name']] = create_result['product_id']


    def tearDown(self):
        """Close the database connection."""
        if self.manager and hasattr(self.manager, 'conn') and self.manager.conn:
            self.manager.close_connection()
            self.manager.conn = None

    # --- Category & Subcategory Tests ---
    def test_add_category_success(self):
        result = self.manager.add_category("Unique Category")
        self.assertTrue(result['success'])
        self.assertIsNotNone(result['category_id'])
        category_obj = self.manager.get_category_by_name("Unique Category")
        self.assertIsNotNone(category_obj)
        self.assertEqual(category_obj['name'], "Unique Category")
        self.assertEqual(category_obj['id'], result['category_id'])

    def test_add_category_duplicate(self):
        self.manager.add_category("Duplicate Cat")
        result = self.manager.add_category("Duplicate Cat")
        self.assertFalse(result['success'])
        self.assertIn("already exists", result.get('message', '').lower())

    def test_add_subcategory_success(self):
        result = self.manager.add_subcategory("New SubTest", self.produce_cat_id)
        self.assertTrue(result['success'])
        self.assertIsNotNone(result['subcategory_id'])
        subcat_obj = self.manager.get_subcategory_by_name_and_category_id("New SubTest", self.produce_cat_id)
        self.assertIsNotNone(subcat_obj)
        self.assertEqual(subcat_obj['name'], "New SubTest")
        self.assertEqual(subcat_obj['category_id'], self.produce_cat_id)
        self.assertEqual(subcat_obj['id'], result['subcategory_id'])

    def test_add_subcategory_duplicate(self):
        self.manager.add_subcategory("Duplicate SubTest", self.produce_cat_id)
        result = self.manager.add_subcategory("Duplicate SubTest", self.produce_cat_id)
        self.assertFalse(result['success'])
        self.assertIn("already exists", result.get('message', '').lower())

    def test_add_subcategory_invalid_category_id(self):
        result = self.manager.add_subcategory("Test Sub", 99999)
        self.assertFalse(result['success'])
        self.assertIn("not found", result.get('message', '').lower())

    def test_get_all_categories_with_subcategories(self):
        self.manager.add_subcategory("Citrus", self.produce_cat_id) # Add another for sorting test

        all_data = self.manager.get_all_categories_with_subcategories()
        self.assertIsInstance(all_data, list)

        category_names = [cat['name'] for cat in all_data]
        self.assertEqual(category_names, sorted(category_names), "Categories are not sorted by name.")

        produce_data = next((item for item in all_data if item["name"] == "Produce"), None)
        self.assertIsNotNone(produce_data)
        self.assertEqual(produce_data['id'], self.produce_cat_id)
        self.assertIn('subcategories', produce_data)
        self.assertIsInstance(produce_data['subcategories'], list)

        produce_subcategory_names = [sc['name'] for sc in produce_data['subcategories']]
        self.assertEqual(produce_subcategory_names, sorted(produce_subcategory_names), "Produce subcategories are not sorted by name.")

        fruit_data = next((sc for sc in produce_data['subcategories'] if sc["name"] == "Fruit"), None)
        self.assertIsNotNone(fruit_data)
        self.assertEqual(fruit_data['id'], self.fruit_subcat_id)
        self.assertEqual(fruit_data['category_id'], self.produce_cat_id)

    # --- Product Method Tests ---
    def test_get_all_products_basic(self):
        products = self.manager.get_all_products(page=1, per_page=len(self.products_data_def))
        self.assertEqual(len(products), len(self.products_data_def))
        fetched_names = sorted([p['name'] for p in products])
        expected_names = sorted([p['name'] for p in self.products_data_def])
        self.assertListEqual(fetched_names, expected_names)
        # Check if category_name is present
        self.assertTrue(all('category_name' in p for p in products))


    def test_get_all_products_category_filter(self):
        products = self.manager.get_all_products(category='Produce')
        self.assertEqual(len(products), 4)
        self.assertTrue(all(p['category_name'] == 'Produce' for p in products))

    def test_update_product(self):
        product_id_to_update = self.product_ids_setup['Apples']
        updated_data = {
            "name": "Golden Apples",
            "category_id": self.dairy_cat_id, # Change category to Dairy
            "subcategory_id": self.milk_subcat_id, # Change subcategory
            "unit_of_measure": "bag",
            "default_expiry_days": 20,
            "par_level": 10.0,
            "max_holding_amount": 25.0,
            "purchase_location": "Farm Fresh"
        }
        result = self.manager.update_product(product_id_to_update, **updated_data)
        self.assertTrue(result.get("success"))

        updated_product = self.manager.get_product(product_id_to_update)
        self.assertEqual(updated_product['name'], "Golden Apples")
        self.assertEqual(updated_product['category_id'], self.dairy_cat_id)
        self.assertEqual(updated_product['category_name'], "Dairy") # Check name
        self.assertEqual(updated_product['subcategory_id'], self.milk_subcat_id)
        self.assertEqual(updated_product['subcategory_name'], "Milk Products") # Check name
        self.assertEqual(updated_product['unit_of_measure'], "bag")


    # --- add_item_to_list Tests (Excel import simulation) ---
    def test_add_item_to_list_existing_product_cat_subcat(self):
        # Product "Apples" with category "Produce" (ID: self.produce_cat_id)
        # and subcategory "Fruit" (ID: self.fruit_subcat_id) already exists from setUp
        result = self.manager.add_item_to_list(
            name="Apples", quantity_str="2 kg", purchase_date_str="2024-01-01", expiry_days=10,
            category="Produce", subcategory="Fruit", unit_of_measure="kg"
        )
        self.assertTrue(result.get("success"), result.get("message"))
        self.assertIn("Item 'Apples' added to inventory.", result.get("message"))
        self.assertEqual(len(result.get("warnings", [])), 0) # No UoM or cat/subcat name mismatch

    def test_add_item_to_list_new_product_existing_cat_new_subcat_action_required(self):
        result = self.manager.add_item_to_list(
            name="New Exotic Fruit", quantity_str="5 pcs", purchase_date_str="2024-01-01", expiry_days=7,
            category="Produce", subcategory="Exotic Fruits", unit_of_measure="pcs"
        )
        self.assertFalse(result.get("success"))
        self.assertEqual(result.get("action_required"), "confirm_new_subcategory")
        self.assertEqual(result['confirmation_details']['category_id'], self.produce_cat_id)
        self.assertEqual(result['confirmation_details']['category_name'], "Produce")
        self.assertEqual(result['confirmation_details']['new_subcategory_name'], "Exotic Fruits")
        self.assertIsNotNone(result.get("product_data"))

    def test_add_item_to_list_new_product_new_category_action_required(self):
        result = self.manager.add_item_to_list(
            name="Artisan Cheese", quantity_str="200g", purchase_date_str="2024-01-01", expiry_days=30,
            category="Artisan Goods", subcategory="Cheese", unit_of_measure="g"
        )
        self.assertFalse(result.get("success"))
        self.assertEqual(result.get("action_required"), "confirm_new_category")
        self.assertEqual(result['confirmation_details']['new_category_name'], "Artisan Goods")
        self.assertEqual(result['confirmation_details']['new_subcategory_name'], "Cheese")
        self.assertIsNotNone(result.get("product_data"))

    def test_add_item_to_list_confirmation_flow_new_category(self):
        # Step 1: Initial call that triggers confirm_new_category
        initial_result = self.manager.add_item_to_list(
            name="Kombucha", quantity_str="1 bottle", purchase_date_str="2024-01-15", expiry_days=45,
            category="Fermented Drinks", subcategory="Tea Based", unit_of_measure="bottle"
        )
        self.assertEqual(initial_result.get("action_required"), "confirm_new_category")
        product_data = initial_result["product_data"]

        # Step 2: Call again with confirmation
        confirmed_result = self.manager.add_item_to_list(
            **product_data, # Spread the original product data
            confirmed_action="confirm_new_category"
        )
        self.assertTrue(confirmed_result.get("success"), confirmed_result.get("message"))
        self.assertIn("Item 'Kombucha' added to inventory.", confirmed_result.get("message"))

        # Verify product, category, and subcategory were created
        product = self.manager.get_product_by_name("Kombucha")
        self.assertIsNotNone(product)
        self.assertIsNotNone(product['category_id'])
        self.assertIsNotNone(product['subcategory_id'])
        category = self.manager.get_category_by_name("Fermented Drinks")
        self.assertIsNotNone(category)
        self.assertEqual(product['category_id'], category['id'])
        subcategory = self.manager.get_subcategory_by_name_and_category_id("Tea Based", category['id'])
        self.assertIsNotNone(subcategory)
        self.assertEqual(product['subcategory_id'], subcategory['id'])

    def test_add_item_to_list_confirmation_flow_new_subcategory(self):
        # Step 1: Initial call (Produce category exists, new subcategory "Tropical")
        initial_result = self.manager.add_item_to_list(
            name="Mangoes", quantity_str="3 pcs", purchase_date_str="2024-01-15", expiry_days=10,
            category="Produce", subcategory="Tropical", unit_of_measure="pcs"
        )
        self.assertEqual(initial_result.get("action_required"), "confirm_new_subcategory")
        product_data = initial_result["product_data"]
        confirmation_details = initial_result["confirmation_details"]

        # Step 2: Call again with confirmation
        confirmed_result = self.manager.add_item_to_list(
            **product_data,
            confirmed_action="confirm_new_subcategory",
            temp_category_id=confirmation_details['category_id']
        )
        self.assertTrue(confirmed_result.get("success"), confirmed_result.get("message"))
        self.assertIn("Item 'Mangoes' added to inventory.", confirmed_result.get("message"))

        product = self.manager.get_product_by_name("Mangoes")
        self.assertIsNotNone(product)
        self.assertEqual(product['category_id'], self.produce_cat_id)
        subcategory = self.manager.get_subcategory_by_name_and_category_id("Tropical", self.produce_cat_id)
        self.assertIsNotNone(subcategory)
        self.assertEqual(product['subcategory_id'], subcategory['id'])

    def test_add_item_to_list_with_cost_and_vendor(self):
        # Product "Apples" exists.
        product_id_apples = self.product_ids_setup["Apples"]
        result = self.manager.add_item_to_list(
            name="Apples", quantity_str="3 kg", purchase_date_str="2024-03-20", expiry_days=10,
            category="Produce", subcategory="Fruit", unit_of_measure="kg",
            cost_per_unit_str="0.99", vendor="Farm Fresh"
        )
        self.assertTrue(result.get("success"), result.get("message"))
        self.assertIsNotNone(result.get("item_id"), "Stock item ID should be present")
        self.assertIsNotNone(result.get("purchase_log_id"), "PurchaseLog ID should be present")

        # Verify PurchaseLog entry
        conn = self.manager._get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM PurchaseLog WHERE id = ?", (result["purchase_log_id"],))
        log_entry = cursor.fetchone()
        conn.close()

        self.assertIsNotNone(log_entry)
        self.assertEqual(log_entry["product_id"], product_id_apples)
        self.assertEqual(log_entry["quantity_purchased"], 3.0)
        self.assertEqual(log_entry["cost_per_unit"], 0.99)
        self.assertEqual(log_entry["vendor"], "Farm Fresh")

    def test_add_item_to_list_without_cost_and_vendor(self):
        # Product "Bananas" exists.
        result = self.manager.add_item_to_list(
            name="Bananas", quantity_str="12 units", purchase_date_str="2024-03-21", expiry_days=5,
            category="Produce", subcategory="Fruit", unit_of_measure="units"
            # No cost_per_unit_str or vendor provided
        )
        self.assertTrue(result.get("success"), result.get("message"))
        self.assertIsNotNone(result.get("item_id"), "Stock item ID should be present")
        self.assertIsNone(result.get("purchase_log_id"), "PurchaseLog ID should NOT be present when no cost info")

        # Verify no PurchaseLog entry was created for this specific operation
        # This is harder to test directly without knowing how many logs existed before.
        # We rely on purchase_log_id being None in the result.

    def test_add_item_to_list_new_product_with_cost(self):
        # Using existing category "Produce" and subcategory "Fruit" to simplify and avoid confirmation logic for this test.
        # This test focuses on ensuring a new product creation via add_item_to_list also logs purchase if cost is provided.
        result_new_prod_cost = self.manager.add_item_to_list(
            name="NewCostlyFruit", quantity_str="1 kg", purchase_date_str="2024-03-23", expiry_days=7,
            category="Produce", subcategory="Fruit", unit_of_measure="kg", # Existing cat/subcat
            cost_per_unit_str="3.00", vendor="Specialty Store"
        )
        self.assertTrue(result_new_prod_cost.get("success"), f"add_item_to_list failed: {result_new_prod_cost.get('message')}")
        self.assertIsNotNone(result_new_prod_cost.get("item_id"))
        self.assertIsNotNone(result_new_prod_cost.get("purchase_log_id"))

        new_product = self.manager.get_product_by_name("NewCostlyFruit")
        self.assertIsNotNone(new_product, "New product 'NewCostlyFruit' was not created.")

        conn = self.manager._get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM PurchaseLog WHERE id = ?", (result_new_prod_cost["purchase_log_id"],))
        log_entry = cursor.fetchone()
        conn.close()

        self.assertIsNotNone(log_entry, "PurchaseLog entry not found for NewCostlyFruit.")
        self.assertEqual(log_entry["product_id"], new_product["id"])
        self.assertEqual(log_entry["cost_per_unit"], 3.00)
        self.assertEqual(log_entry["vendor"], "Specialty Store")


    def test_add_item_to_list_invalid_cost(self):
        result = self.manager.add_item_to_list(
            name="Apples", quantity_str="1 kg", purchase_date_str="2024-03-20", expiry_days=10,
            category="Produce", subcategory="Fruit", unit_of_measure="kg",
            cost_per_unit_str="-1.0", vendor="Invalid Vendor" # Negative cost
        )
        self.assertFalse(result.get("success"))
        self.assertIn("cannot be negative", result.get("message", "").lower())

        result_text_cost = self.manager.add_item_to_list(
            name="Apples", quantity_str="1 kg", purchase_date_str="2024-03-20", expiry_days=10,
            category="Produce", subcategory="Fruit", unit_of_measure="kg",
            cost_per_unit_str="abc", vendor="Invalid Vendor" # Non-numeric cost
        )
        self.assertFalse(result_text_cost.get("success"))
        self.assertIn("not a valid number", result_text_cost.get("message", "").lower())


    # --- Remaining tests from previous state, ensure they still pass or adapt them ---
    def test_get_current_inventory_default_behavior(self):
        product_apples_id = self.product_ids_setup["Apples"]
        product_bananas_id = self.product_ids_setup["Bananas"]

        self.manager.add_inventory_stock(product_id=product_apples_id, quantity_str="5", purchase_date_str="2023-01-10")
        self.manager.add_inventory_stock(product_id=product_bananas_id, quantity_str="10", purchase_date_str="2023-01-10")

        current_inventory = self.manager.get_current_inventory(sort_by='expiry_date', sort_order='ASC', page=None, per_page=None)
        self.assertEqual(len(current_inventory), 2)
        self.assertEqual(current_inventory[0]['product_name'], "Bananas")
        self.assertEqual(current_inventory[1]['product_name'], "Apples")
        self.assertEqual(current_inventory[0]['category_name'], "Produce") # Check new field


    def test_get_historical_inventory_default_behavior(self):
        product_apples_id = self.product_ids_setup["Apples"]
        product_bananas_id = self.product_ids_setup["Bananas"]

        self.manager.add_inventory_stock(product_id=product_apples_id, quantity_str="5", purchase_date_str="2023-01-01")
        self.manager.add_inventory_stock(product_id=product_bananas_id, quantity_str="10", purchase_date_str="2023-01-01")

        with unittest.mock.patch('Food_manager.date') as mock_date_fm:
            mock_date_fm.today.return_value = date(2023, 1, 5)
            self.manager.consume_item("Apples", 2.0)
            mock_date_fm.today.return_value = date(2023, 1, 7)
            self.manager.consume_item("Bananas", 3.0)

        historical_inventory = self.manager.get_historical_inventory(sort_by='consumed_date', sort_order='DESC', page=None, per_page=None)
        self.assertEqual(len(historical_inventory), 2)
        self.assertEqual(historical_inventory[0]['product_display_name'], "Bananas")
        self.assertEqual(historical_inventory[1]['product_display_name'], "Apples")
        self.assertEqual(historical_inventory[0]['category_name'], "Produce") # Check new field

# --- Test Cases for Production Items (Garden & Harvest) ---
# (TestProductionItems class remains largely the same as its product creation was already updated)
class TestProductionItems(unittest.TestCase):
    def setUp(self):
        self.manager = InventoryManager(db_filepath=":memory:")
        # Add categories and subcategories needed for products
        self.produce_cat_id = self.manager.add_category("Produce")['category_id']
        self.herbs_cat_id = self.manager.add_category("Herbs")['category_id']

        # Add a product that can be associated
        self.product1_res = self.manager.create_product(name="Tomatoes", category_id=self.produce_cat_id, subcategory_id=None, unit_of_measure="kg", default_expiry_days=7)
        self.product1_id = self.product1_res['product_id']
        self.product2_res = self.manager.create_product(name="Basil", category_id=self.herbs_cat_id, subcategory_id=None, unit_of_measure="bunch", default_expiry_days=5)
        self.product2_id = self.product2_res['product_id']

    def tearDown(self):
        if self.manager and hasattr(self.manager, 'conn') and self.manager.conn:
            self.manager.close_connection()
            self.manager.conn = None


    def test_add_production_item_successful(self):
        result = self.manager.add_production_item(
            name="Tomato Plant A",
            associated_product_id=self.product1_id,
            plant_date_str="2024-01-01",
            time_to_harvest_days=60,
            expected_harvest_period_days=30,
            expected_yield_total=5.0,
            status="Growing"
        )
        self.assertTrue(result.get("success"))
        self.assertIsNotNone(result.get("item_id"))
        item = self.manager.get_production_item(result["item_id"])
        self.assertEqual(item['name'], "Tomato Plant A")
        self.assertEqual(item['associated_product_id'], self.product1_id)

    def test_add_production_item_validation_errors(self):
        # Invalid date
        result = self.manager.add_production_item(name="Test Plant", associated_product_id=self.product1_id, plant_date_str="invalid-date", time_to_harvest_days=1, expected_harvest_period_days=1, expected_yield_total=1)
        self.assertFalse(result.get("success"))
        self.assertIn("Invalid plant_date format", result.get("message"))

        # Missing required fields (e.g., name)
        result = self.manager.add_production_item(name="", associated_product_id=self.product1_id, plant_date_str="2024-01-01", time_to_harvest_days=1, expected_harvest_period_days=1, expected_yield_total=1)
        self.assertFalse(result.get("success"))
        self.assertIn("Missing required production item fields", result.get("message"))

    def test_get_production_item(self):
        add_result = self.manager.add_production_item(name="Test Get Plant", plant_date_str="2024-01-01", time_to_harvest_days=30, expected_harvest_period_days=15, expected_yield_total=2.0, associated_product_id=self.product1_id)
        item_id = add_result["item_id"]

        item = self.manager.get_production_item(item_id)
        self.assertIsNotNone(item)
        self.assertEqual(item['name'], "Test Get Plant")

        non_existent_item = self.manager.get_production_item(999)
        self.assertIsNone(non_existent_item)

    @unittest.mock.patch('Food_manager.date')
    def test_get_production_item_dynamic_status_and_yield(self, mock_date):
        plant_date = date(2024, 1, 1)
        add_result = self.manager.add_production_item(
            name="Dynamic Plant",
            plant_date_str=plant_date.isoformat(),
            time_to_harvest_days=30,
            expected_harvest_period_days=15,
            expected_yield_total=3.0,
            associated_product_id=self.product1_id
        )
        item_id = add_result["item_id"]

        mock_date.today.return_value = date(2024, 1, 15)
        item = self.manager.get_production_item(item_id)
        self.assertEqual(item['calculated_status'], "Growing")
        self.assertAlmostEqual(item['estimated_daily_yield'], 3.0 / 15)

        mock_date.today.return_value = date(2024, 2, 1)
        item = self.manager.get_production_item(item_id)
        self.assertEqual(item['calculated_status'], "Harvesting")

        mock_date.today.return_value = date(2024, 3, 1)
        item = self.manager.get_production_item(item_id)
        self.assertEqual(item['calculated_status'], "Finished")

        add_result_zero_period = self.manager.add_production_item(name="ZeroDayPlant", plant_date_str="2024-01-01", time_to_harvest_days=10, expected_harvest_period_days=0, expected_yield_total=5.0, associated_product_id=self.product1_id)
        item_zero_id = add_result_zero_period['item_id']
        mock_date.today.return_value = date(2024, 1, 15)
        item_zero = self.manager.get_production_item(item_zero_id)
        self.assertEqual(item_zero['estimated_daily_yield'], 0)
        self.assertEqual(item_zero['calculated_status'], "Finished")


    def test_get_all_production_items(self):
        items = self.manager.get_all_production_items()
        self.assertEqual(len(items), 0)

        self.manager.add_production_item(name="Plant A", plant_date_str="2024-03-01", time_to_harvest_days=10, expected_harvest_period_days=5, expected_yield_total=1, status="Growing", associated_product_id=self.product1_id)
        self.manager.add_production_item(name="Plant B", plant_date_str="2024-01-01", time_to_harvest_days=10, expected_harvest_period_days=5, expected_yield_total=2, status="Harvesting", associated_product_id=self.product2_id)
        self.manager.add_production_item(name="Plant C", plant_date_str="2024-02-01", time_to_harvest_days=10, expected_harvest_period_days=5, expected_yield_total=3, status="Growing", associated_product_id=self.product1_id)

        items = self.manager.get_all_production_items()
        self.assertEqual(len(items), 3)

        self.assertEqual(items[0]['name'], "Plant B")
        self.assertEqual(items[1]['name'], "Plant C")
        self.assertEqual(items[2]['name'], "Plant A")

        items_growing = self.manager.get_all_production_items(filters={'status': 'Growing'})
        self.assertEqual(len(items_growing), 2)
        self.assertTrue(all(item['status'] == 'Growing' for item in items_growing))

        items_harvesting = self.manager.get_all_production_items(filters={'status': 'Harvesting'})
        self.assertEqual(len(items_harvesting), 1)
        self.assertEqual(items_harvesting[0]['name'], "Plant B")


    def test_update_production_item(self):
        add_result = self.manager.add_production_item(name="Original Name", plant_date_str="2024-01-01", time_to_harvest_days=60, expected_harvest_period_days=30, expected_yield_total=5.0, associated_product_id=self.product1_id)
        item_id = add_result["item_id"]

        update_data = {"name": "Updated Name", "status": "Finished", "expected_yield_total": 7.5}
        result = self.manager.update_production_item(item_id, update_data)
        self.assertTrue(result.get("success"))

        updated_item = self.manager.get_production_item(item_id)
        self.assertEqual(updated_item['name'], "Updated Name")
        self.assertEqual(updated_item['status'], "Finished")
        self.assertEqual(updated_item['expected_yield_total'], 7.5)

        result_non_existent = self.manager.update_production_item(999, {"name": "Does not exist"})
        self.assertFalse(result_non_existent.get("success"))
        self.assertIn("not found", result_non_existent.get("message"))

    @unittest.mock.patch.object(InventoryManager, 'add_inventory_stock')
    def test_record_harvest(self, mock_add_inventory_stock):
        plant_date_str = "2023-01-01"
        prod_item_result = self.manager.add_production_item(
            name="Harvestable Tomato Plant", associated_product_id=self.product1_id,
            plant_date_str=plant_date_str, time_to_harvest_days=30,
            expected_harvest_period_days=30, expected_yield_total=10.0, status="Harvesting"
        )
        production_item_id = prod_item_result["item_id"]
        mock_add_inventory_stock.return_value = {"success": True, "message": "Stock added", "stock_item_id": 123}
        harvest_date_str = "2023-02-15"
        actual_harvest_amount = 2.5
        result = self.manager.record_harvest(production_item_id, actual_harvest_amount, harvest_date_str)
        self.assertTrue(result.get("success"))
        self.assertEqual(result.get("stock_item_id"), 123)
        mock_add_inventory_stock.assert_called_once_with(
            product_id=self.product1_id, quantity_str=str(actual_harvest_amount), purchase_date_str=harvest_date_str
        )

        mock_add_inventory_stock.reset_mock()
        result_non_existent = self.manager.record_harvest(999, 1.0, "2023-03-01")
        self.assertFalse(result_non_existent.get("success"))
        self.assertIn("not found", result_non_existent.get("message", "").lower())
        mock_add_inventory_stock.assert_not_called()

        prod_item_no_assoc_result = self.manager.add_production_item(name="Mystery Plant", associated_product_id=None, plant_date_str="2023-01-01", time_to_harvest_days=1,expected_harvest_period_days=1,expected_yield_total=1)
        prod_item_no_assoc_id = prod_item_no_assoc_result['item_id']
        result_no_assoc = self.manager.record_harvest(prod_item_no_assoc_id, 1.0, "2023-03-01")
        self.assertFalse(result_no_assoc.get("success"))
        self.assertIn("does not have an associated product id", result_no_assoc.get("message", "").lower())


from datetime import timedelta # Ensure timedelta is imported

class TestFutureInventoryProjection(unittest.TestCase):
    def setUp(self):
        self.manager = InventoryManager(db_filepath=":memory:")
        # No categories needed for these specific tests unless products require them for creation.
        # For simplicity, assuming create_product doesn't strictly require category_id for these tests,
        # or passing None if it does. The method under test doesn't directly use category.

        # Product 1: Test Apples (for general tests)
        apple_res = self.manager.create_product(
            name="Test Apples", unit_of_measure="pcs", default_expiry_days=10,
            category_id=None, subcategory_id=None # Assuming these can be None
        )
        self.assertTrue(apple_res.get("success"), "Failed to create Test Apples")
        self.apple_product_id = apple_res['product_id']

        # Product 2: Test Oranges (for override rate test)
        orange_res = self.manager.create_product(
            name="Test Oranges", unit_of_measure="pcs", default_expiry_days=10,
            category_id=None, subcategory_id=None,
            consumption_override_rate=0.5
        )
        self.assertTrue(orange_res.get("success"), "Failed to create Test Oranges")
        self.orange_product_id = orange_res['product_id']

        # Product 3: Test Grapes (for spoilage and harvest interaction)
        grapes_res = self.manager.create_product(
            name="Test Grapes", unit_of_measure="bunch", default_expiry_days=5, # Shorter expiry
            category_id=None, subcategory_id=None
        )
        self.assertTrue(grapes_res.get("success"), "Failed to create Test Grapes")
        self.grapes_product_id = grapes_res['product_id']


    def tearDown(self):
        if self.manager and hasattr(self.manager, 'conn') and self.manager.conn:
            self.manager.close_connection()
            self.manager.conn = None

    def _add_historical_consumption(self, product_id, days_ago_start, days_ago_end, quantity_per_day):
        """Adds historical consumption records for a product over a date range."""
        today = date.today()
        for i in range(days_ago_end, days_ago_start + 1): # days_ago_end is further in past
            consumption_date = today - timedelta(days=i)
            # Simplified historical entry: actual purchase/expiry of consumed items not critical for avg calculation here
            self.manager._get_db_connection().execute('''
                INSERT INTO historical_items
                (product_id, name, quantity_consumed_this_time, original_quantity_string, purchase_date, expiry_date, consumed_date)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (product_id, f"Historical Product {product_id}", quantity_per_day, str(quantity_per_day),
                  (consumption_date - timedelta(days=10)).isoformat(), # Dummy purchase
                  (consumption_date + timedelta(days=1)).isoformat(),  # Dummy expiry
                  consumption_date.isoformat()))
        self.manager._get_db_connection().commit()

    def _assert_common_projection_structure(self, projection_list, expected_days):
        self.assertEqual(len(projection_list), expected_days)
        for item in projection_list:
            self.assertIn('date', item)
            self.assertIsInstance(item['date'], str)
            self.assertIn('opening_inventory', item)
            self.assertIn('harvest', item)
            self.assertIn('consumption', item)
            self.assertIn('shrink', item)
            self.assertIn('projected_ending_inventory', item)
            self.assertIn('depletion_date_reached', item)
            self.assertIsInstance(item['depletion_date_reached'], bool)

    def test_projection_simple_consumption(self):
        today_str = date.today().isoformat()
        self.manager.add_inventory_stock(self.apple_product_id, "10", today_str) # 10 units
        self._add_historical_consumption(self.apple_product_id, days_ago_start=1, days_ago_end=30, quantity_per_day=1) # Avg 1/day

        projection_days = 15
        projection = self.manager.get_future_inventory_projection(self.apple_product_id, projection_days)
        self._assert_common_projection_structure(projection, projection_days)

        depletion_day_index = -1
        for i, day_proj in enumerate(projection):
            self.assertEqual(day_proj['harvest'], 0)
            self.assertEqual(day_proj['shrink'], 0)
            if i < 10: # Consumes for 10 days
                self.assertEqual(day_proj['consumption'], 1)
                self.assertEqual(day_proj['projected_ending_inventory'], 10 - (i + 1))
                if day_proj['projected_ending_inventory'] == 0 and depletion_day_index == -1:
                    self.assertTrue(day_proj['depletion_date_reached'])
                    depletion_day_index = i
            else: # After depletion
                self.assertEqual(day_proj['consumption'], 0)
                self.assertEqual(day_proj['projected_ending_inventory'], 0)
                if depletion_day_index != -1: # Should remain true after first depletion
                     self.assertTrue(day_proj['depletion_date_reached'])


        self.assertEqual(depletion_day_index, 9) # Depletes on the 10th day (index 9)
        self.assertEqual(projection[9]['projected_ending_inventory'], 0)


    def test_projection_with_spoilage(self):
        purchase_date = date.today()
        # Product default expiry is 10 days. Batch expires on day 9 of projection (0-indexed) if purchased today.
        self.manager.add_inventory_stock(self.apple_product_id, "5", purchase_date.isoformat()) # 5 units
        self._add_historical_consumption(self.apple_product_id, days_ago_start=1, days_ago_end=30, quantity_per_day=0.2) # Avg 0.2/day

        projection_days = 15
        projection = self.manager.get_future_inventory_projection(self.apple_product_id, projection_days)
        self._assert_common_projection_structure(projection, projection_days)

        expiry_projection_day_index = 9 # Day 10 of projection, index 9 (since product default_expiry_days = 10)
                                        # Batch purchased today (day 0 of proj) expires on proj_day 9.

        total_consumed_before_expiry = 0
        for i in range(expiry_projection_day_index + 1):
            total_consumed_before_expiry += projection[i]['consumption']

        expected_shrink = 0
        if 5 - total_consumed_before_expiry > 0 : # if there's anything left to spoil
             # This is the tricky part: consumption on expiry day reduces what *could* spoil
             consumed_on_expiry_day = projection[expiry_projection_day_index]['consumption']
             qty_at_start_of_expiry_day = projection[expiry_projection_day_index]['opening_inventory']

             # Quantity that would be left if not for spoilage, *after* consumption on expiry day
             # No, this is simpler: amount_of_expiring_items_consumed + shrink_for_the_day = expiring_qty_today
             # expiring_qty_today is qty_at_start_of_expiry_day (if all from one batch expiring today)
             # Here, initial batch is 5 units.
             # qty_available_to_spoil_on_expiry_day = projection[expiry_projection_day_index]['opening_inventory']
             # This needs to be based on the specific batch's remaining quantity.
             # The logic in get_future_inventory_projection handles this by:
             # expiring_qty_today = sum of quantities of batches expiring today
             # amount_of_expiring_items_consumed = min(expiring_qty_today, consumed_amount_for_day)
             # shrink_for_the_day = expiring_qty_today - amount_of_expiring_items_consumed

             # For this test: 5 units initial. Consumed = 0.2 * 10 days = 2 units.
             # Remaining before spoilage on expiry day (at start of day 9) = 5 - (0.2 * 9) = 5 - 1.8 = 3.2
             # On day 9 (expiry day):
             # Opening inventory = 3.2
             # Consumption = 0.2
             # Inventory after consumption, before spoilage calc = 3.0
             # Expiring qty today (from this batch) = 3.2 (this is the original amount of the batch that is expiring if not consumed)
             # No, expiring_qty_today in the code refers to what's left of the batch at the start of the expiry day.
             # So, expiring_qty_today = 3.2
             # Amount of expiring items consumed = min(3.2, 0.2) = 0.2
             # Shrink = 3.2 - 0.2 = 3.0

             # Let's trace:
             # Day 0: Open 5, Cons 0.2, End 4.8
             # ...
             # Day 8: Open 5-(0.2*8)=3.4, Cons 0.2, End 3.2
             # Day 9 (Expiry): Open 3.2, Cons 0.2. Inventory before shrink = 3.0.
             # Expiring_qty_today (from this batch) = 3.2 (its remaining qty at start of day)
             # Amount_of_expiring_items_consumed = min(3.2, 0.2) = 0.2
             # Shrink = 3.2 - 0.2 = 3.0
             expected_shrink = 3.0

        self.assertAlmostEqual(projection[expiry_projection_day_index]['shrink'], expected_shrink, places=2)
        self.assertAlmostEqual(projection[expiry_projection_day_index]['consumption'], 0.2, places=2)
        # End Inv = Open (3.2) + Harvest (0) - Cons (0.2) - Shrink (3.0) = 0
        self.assertAlmostEqual(projection[expiry_projection_day_index]['projected_ending_inventory'], 0, places=2)
        self.assertTrue(projection[expiry_projection_day_index]['depletion_date_reached'])

        # After expiry, shrink should be 0
        if expiry_projection_day_index + 1 < projection_days:
            self.assertEqual(projection[expiry_projection_day_index + 1]['shrink'], 0)

    def test_projection_with_garden_harvest(self):
        # No initial inventory for Test Apples
        self._add_historical_consumption(self.apple_product_id, days_ago_start=1, days_ago_end=30, quantity_per_day=1) # Avg 1/day

        today = date.today()
        # Harvest starts on day 5 of projection (index 4)
        plant_date_for_harvest_on_day_5 = today + timedelta(days=4 - 30) # Plant 30 days before harvest starts on day 4

        self.manager.add_production_item(
            name="Apple Tree A",
            associated_product_id=self.apple_product_id,
            plant_date_str=plant_date_for_harvest_on_day_5.isoformat(),
            time_to_harvest_days=30, # Harvest starts on projection day 4
            expected_harvest_period_days=3, # Harvests on day 4, 5, 6
            expected_yield_total=6.0, # Results in 2 units/day
            status="Growing"
        )

        projection_days = 10
        projection = self.manager.get_future_inventory_projection(self.apple_product_id, projection_days)
        self._assert_common_projection_structure(projection, projection_days)

        # Harvest days are index 4, 5, 6
        harvest_days_indices = [4, 5, 6]
        for i, day_proj in enumerate(projection):
            self.assertEqual(day_proj['shrink'], 0)
            if i in harvest_days_indices:
                self.assertAlmostEqual(day_proj['harvest'], 2.0, places=2)
            else:
                self.assertEqual(day_proj['harvest'], 0)

            # Check inventory logic: Open + Harvest - Consumption = End
            expected_ending_inv = day_proj['opening_inventory'] + day_proj['harvest'] - day_proj['consumption']
            self.assertAlmostEqual(day_proj['projected_ending_inventory'], expected_ending_inv, places=2)

            if i > 0: # Opening inventory should match previous day's ending
                 self.assertAlmostEqual(day_proj['opening_inventory'], projection[i-1]['projected_ending_inventory'], places=2)

        # Specific day checks
        self.assertEqual(projection[3]['projected_ending_inventory'], 0) # Depleted before first harvest
        self.assertTrue(projection[3]['depletion_date_reached'])

        self.assertEqual(projection[4]['opening_inventory'], 0)
        self.assertEqual(projection[4]['harvest'], 2)
        self.assertEqual(projection[4]['consumption'], 1) # Avg cons is 1
        self.assertEqual(projection[4]['projected_ending_inventory'], 1)
        self.assertTrue(projection[4]['depletion_date_reached']) # Still true as it was reached before

        self.assertEqual(projection[5]['opening_inventory'], 1)
        self.assertEqual(projection[5]['harvest'], 2)
        self.assertEqual(projection[5]['consumption'], 1)
        self.assertEqual(projection[5]['projected_ending_inventory'], 2)

        self.assertEqual(projection[6]['opening_inventory'], 2)
        self.assertEqual(projection[6]['harvest'], 2)
        self.assertEqual(projection[6]['consumption'], 1)
        self.assertEqual(projection[6]['projected_ending_inventory'], 3)

        self.assertEqual(projection[7]['opening_inventory'], 3)
        self.assertEqual(projection[7]['harvest'], 0) # No harvest this day
        self.assertEqual(projection[7]['consumption'], 1)
        self.assertEqual(projection[7]['projected_ending_inventory'], 2)


    def test_projection_consumption_override_rate(self):
        today_str = date.today().isoformat()
        # Test Oranges has override rate of 0.5
        self.manager.add_inventory_stock(self.orange_product_id, "5", today_str)
        # Add some historical, but it should be ignored due to override
        self._add_historical_consumption(self.orange_product_id, days_ago_start=1, days_ago_end=30, quantity_per_day=10)

        projection_days = 15
        projection = self.manager.get_future_inventory_projection(self.orange_product_id, projection_days)
        self._assert_common_projection_structure(projection, projection_days)

        depletion_day_index = -1
        for i, day_proj in enumerate(projection):
            self.assertEqual(day_proj['harvest'], 0)
            self.assertEqual(day_proj['shrink'], 0)
            if i < 10: # 5 units / 0.5 units/day = 10 days
                self.assertAlmostEqual(day_proj['consumption'], 0.5, places=2)
                self.assertAlmostEqual(day_proj['projected_ending_inventory'], 5 - (0.5 * (i + 1)), places=2)
                if day_proj['projected_ending_inventory'] == 0 and depletion_day_index == -1:
                    self.assertTrue(day_proj['depletion_date_reached'])
                    depletion_day_index = i
            else:
                self.assertEqual(day_proj['consumption'], 0)
                self.assertEqual(day_proj['projected_ending_inventory'], 0)
                if depletion_day_index != -1:
                    self.assertTrue(day_proj['depletion_date_reached'])

        self.assertEqual(depletion_day_index, 9) # Depletes on 10th day (index 9)

    def test_projection_spoilage_and_consumption_interaction(self):
        # Grapes product: default_expiry_days=5
        # Add batch that expires in 2 projection days (purchase 3 days ago relative to today)
        purchase_date = date.today() - timedelta(days=3)
        # Expiry will be purchase_date + 5 days = today + 2 days. So, it expires on projection day 1 (0-indexed).
        self.manager.add_inventory_stock(self.grapes_product_id, "3", purchase_date.isoformat()) # 3 units
        self._add_historical_consumption(self.grapes_product_id, days_ago_start=1, days_ago_end=30, quantity_per_day=1) # Avg 1/day

        projection_days = 5
        projection = self.manager.get_future_inventory_projection(self.grapes_product_id, projection_days)
        self._assert_common_projection_structure(projection, projection_days)

        # Day 0 (today)
        self.assertAlmostEqual(projection[0]['opening_inventory'], 3, places=2)
        self.assertEqual(projection[0]['harvest'], 0)
        self.assertAlmostEqual(projection[0]['consumption'], 1, places=2)
        self.assertEqual(projection[0]['shrink'], 0)
        self.assertAlmostEqual(projection[0]['projected_ending_inventory'], 2, places=2)
        self.assertFalse(projection[0]['depletion_date_reached'])

        # Day 1 (Expiry Day for the initial batch)
        # Batch expires today (projection day 1). It had 2 units left at start of day.
        self.assertAlmostEqual(projection[1]['opening_inventory'], 2, places=2)
        self.assertEqual(projection[1]['harvest'], 0)
        self.assertAlmostEqual(projection[1]['consumption'], 1, places=2) # Consumes 1 of the 2 expiring units
        self.assertAlmostEqual(projection[1]['shrink'], 1, places=2)      # The other 1 unit spoils
        self.assertAlmostEqual(projection[1]['projected_ending_inventory'], 0, places=2)
        self.assertTrue(projection[1]['depletion_date_reached'])

        # Day 2
        self.assertAlmostEqual(projection[2]['opening_inventory'], 0, places=2)
        self.assertEqual(projection[2]['harvest'], 0)
        self.assertEqual(projection[2]['consumption'], 0) # No inventory to consume
        self.assertEqual(projection[2]['shrink'], 0)
        self.assertAlmostEqual(projection[2]['projected_ending_inventory'], 0, places=2)
        self.assertTrue(projection[2]['depletion_date_reached'])

    def test_projection_harvest_before_depletion_and_spoilage(self):
        # Grapes: default_expiry_days=5
        # Initial stock: 2 units, purchased 2 days ago, so expires on projection day 2 (0-indexed)
        purchase_date_initial = date.today() - timedelta(days=3) # Expires in 2 days from today
        self.manager.add_inventory_stock(self.grapes_product_id, "2", purchase_date_initial.isoformat())
        self._add_historical_consumption(self.grapes_product_id, days_ago_start=1, days_ago_end=30, quantity_per_day=1) # Avg 1/day

        # Production item: harvests 5 units on day 1 of projection (0-indexed)
        plant_date_for_harvest = date.today() + timedelta(days=1 - 10) # Plant 10 days before harvest on day 1
        self.manager.add_production_item(
            name="Grape Vine", associated_product_id=self.grapes_product_id,
            plant_date_str=plant_date_for_harvest.isoformat(), time_to_harvest_days=10, # Harvests on projection day 1
            expected_harvest_period_days=1, expected_yield_total=5.0, status="Growing"
        )

        projection_days = 7
        projection = self.manager.get_future_inventory_projection(self.grapes_product_id, projection_days)
        self._assert_common_projection_structure(projection, projection_days)

        # Day 0
        self.assertAlmostEqual(projection[0]['opening_inventory'], 2)
        self.assertEqual(projection[0]['harvest'], 0)
        self.assertAlmostEqual(projection[0]['consumption'], 1)
        self.assertEqual(projection[0]['shrink'], 0)
        self.assertAlmostEqual(projection[0]['projected_ending_inventory'], 1)
        self.assertFalse(projection[0]['depletion_date_reached'])

        # Day 1 (Harvest Day)
        self.assertAlmostEqual(projection[1]['opening_inventory'], 1)
        self.assertAlmostEqual(projection[1]['harvest'], 5) # Harvests 5
        self.assertAlmostEqual(projection[1]['consumption'], 1) # Consumes 1
        self.assertEqual(projection[1]['shrink'], 0) # Initial stock not expired yet
        self.assertAlmostEqual(projection[1]['projected_ending_inventory'], 5) # 1 (open) + 5 (harvest) - 1 (cons) = 5
        self.assertFalse(projection[1]['depletion_date_reached']) # Not depleted due to harvest

        # Day 2 (Original Expiry Day of initial batch)
        self.assertAlmostEqual(projection[2]['opening_inventory'], 5)
        self.assertEqual(projection[2]['harvest'], 0)
        self.assertAlmostEqual(projection[2]['consumption'], 1)
        # The initial batch (1 unit remaining after day 0) would have expired today.
        # On day 1, that 1 unit was part of the opening inventory.
        # Consumption on day 1 (1 unit) would have consumed this last unit of the initial batch.
        # So, no shrink from that batch.
        self.assertEqual(projection[2]['shrink'], 0)
        self.assertAlmostEqual(projection[2]['projected_ending_inventory'], 4)
        self.assertFalse(projection[2]['depletion_date_reached'])

    def test_projection_no_inventory_no_harvest(self):
        self._add_historical_consumption(self.apple_product_id, days_ago_start=1, days_ago_end=30, quantity_per_day=1) # Avg 1/day

        projection_days = 5
        projection = self.manager.get_future_inventory_projection(self.apple_product_id, projection_days)
        self._assert_common_projection_structure(projection, projection_days)

        for i, day_proj in enumerate(projection):
            self.assertEqual(day_proj['opening_inventory'], 0)
            self.assertEqual(day_proj['harvest'], 0)
            self.assertEqual(day_proj['consumption'], 0) # Cannot consume if no inventory
            self.assertEqual(day_proj['shrink'], 0)
            self.assertEqual(day_proj['projected_ending_inventory'], 0)
            self.assertTrue(day_proj['depletion_date_reached']) # Should be true from day 0

    def test_projection_product_not_found(self):
        projection_days = 5
        projection = self.manager.get_future_inventory_projection(999, projection_days)
        # Expecting a specific error structure
        self.assertIsInstance(projection, dict)
        self.assertFalse(projection.get('success'))
        self.assertIn("Product with ID 999 not found", projection.get('message', ''))

    # --- Tests for get_past_actual_inventory_summary ---

    def _assert_common_past_summary_structure(self, summary_list, expected_days):
        self.assertIsInstance(summary_list, list, "Summary should be a list.")
        self.assertEqual(len(summary_list), expected_days)
        if expected_days > 0:
            for item in summary_list:
                self.assertIn('date', item)
                self.assertIsInstance(item['date'], str)
                self.assertIn('actual_ending_inventory', item)
                self.assertIn('actual_consumption', item)
                self.assertIn('actual_shrink', item)
                self.assertEqual(item['actual_shrink'], 0) # Currently always 0
                self.assertIn('actual_harvest', item)
                self.assertEqual(item['actual_harvest'], 0) # Currently always 0
            # Check date order (ascending)
            for i in range(len(summary_list) - 1):
                self.assertTrue(summary_list[i]['date'] < summary_list[i+1]['date'])


    def test_get_past_summary_basic(self):
        days_past = 7
        today = date.today()

        # Add inventory: 10 units purchased 5 days ago, 5 units purchased 2 days ago
        self.manager.add_inventory_stock(self.apple_product_id, "10", (today - timedelta(days=5)).isoformat())
        self.manager.add_inventory_stock(self.apple_product_id, "5", (today - timedelta(days=2)).isoformat())

        # Add consumption: 1 unit consumed each day for the past 7 days
        # _add_historical_consumption adds records from days_ago_end to days_ago_start (inclusive)
        # For past 7 days ending yesterday: days_ago_start=1, days_ago_end=7
        self._add_historical_consumption(self.apple_product_id, days_ago_start=1, days_ago_end=days_past, quantity_per_day=1)

        summary = self.manager.get_past_actual_inventory_summary(self.apple_product_id, days_past)
        self._assert_common_past_summary_structure(summary, days_past)

        # Example verification for a couple of days
        # Day -7 (oldest entry, summary[0]):
        # Inventory history for (today - 7 days)
        # Consumption for (today - 7 days) should be 1
        date_7_days_ago = (today - timedelta(days=7)).isoformat()
        day_minus_7_summary = next((s for s in summary if s['date'] == date_7_days_ago), None)
        self.assertIsNotNone(day_minus_7_summary)
        self.assertEqual(day_minus_7_summary['actual_consumption'], 1)
        # Inventory for day_minus_7_summary['actual_ending_inventory'] will be based on get_daily_inventory_history.
        # If this is the first day of the 7-day window, and stock was added 5 days ago, inv should be 0.
        # Let's check a more recent day.

        # Day -1 (yesterday, summary[6]):
        date_yesterday = (today - timedelta(days=1)).isoformat()
        yesterday_summary = next((s for s in summary if s['date'] == date_yesterday), None)
        self.assertIsNotNone(yesterday_summary)
        self.assertEqual(yesterday_summary['actual_consumption'], 1)

        # To verify actual_ending_inventory, we can compare with get_daily_inventory_history
        # This tests if get_past_actual_inventory_summary correctly incorporates it.
        daily_hist = self.manager.get_daily_inventory_history(self.apple_product_id, days=days_past)
        daily_hist_map = {item['inventory_date']: item['quantity_on_hand'] for item in daily_hist}

        self.assertEqual(yesterday_summary['actual_ending_inventory'], daily_hist_map.get(date_yesterday, 0))

        # Check a day where stock was added
        date_2_days_ago = (today - timedelta(days=2)).isoformat() # Stock added on this day
        day_minus_2_summary = next((s for s in summary if s['date'] == date_2_days_ago), None)
        self.assertIsNotNone(day_minus_2_summary)
        self.assertEqual(day_minus_2_summary['actual_consumption'], 1)
        self.assertEqual(day_minus_2_summary['actual_ending_inventory'], daily_hist_map.get(date_2_days_ago, 0))


    def test_get_past_summary_no_consumption(self):
        days_past = 7
        today = date.today()
        self.manager.add_inventory_stock(self.apple_product_id, "10", (today - timedelta(days=3)).isoformat())

        summary = self.manager.get_past_actual_inventory_summary(self.apple_product_id, days_past)
        self._assert_common_past_summary_structure(summary, days_past)

        for item in summary:
            self.assertEqual(item['actual_consumption'], 0)

        # Check inventory for a day
        date_3_days_ago = (today - timedelta(days=3)).isoformat()
        day_summary = next((s for s in summary if s['date'] == date_3_days_ago), None)
        self.assertIsNotNone(day_summary)
        # Inventory should be 10 as it was just added and no consumption
        self.assertEqual(day_summary['actual_ending_inventory'], 10)


    def test_get_past_summary_no_inventory_history(self):
        days_past = 7
        self._add_historical_consumption(self.apple_product_id, days_ago_start=1, days_ago_end=days_past, quantity_per_day=2)

        summary = self.manager.get_past_actual_inventory_summary(self.apple_product_id, days_past)
        self._assert_common_past_summary_structure(summary, days_past)

        for item in summary:
            self.assertEqual(item['actual_ending_inventory'], 0)
            self.assertEqual(item['actual_consumption'], 2) # Consumption should still be reported

    def test_get_past_summary_partial_history(self):
        days_past = 7
        today = date.today()
        # Add inventory for a specific day in the past
        self.manager.add_inventory_stock(self.apple_product_id, "5", (today - timedelta(days=4)).isoformat()) # 4 days ago
        # Add consumption for only 2 days
        self._add_historical_consumption(self.apple_product_id, days_ago_start=3, days_ago_end=4, quantity_per_day=1) # 3 and 4 days ago

        summary = self.manager.get_past_actual_inventory_summary(self.apple_product_id, days_past)
        self._assert_common_past_summary_structure(summary, days_past)

        date_4_days_ago_str = (today - timedelta(days=4)).isoformat()
        date_3_days_ago_str = (today - timedelta(days=3)).isoformat()
        date_2_days_ago_str = (today - timedelta(days=2)).isoformat()

        summary_map = {item['date']: item for item in summary}

        self.assertEqual(summary_map[date_4_days_ago_str]['actual_consumption'], 1)
        # Inventory on day -4: 5 units added, 1 consumed = 4.
        # (Depends on exact timing of get_daily_inventory_history - it reports end of day stock)
        # If consumption is logged on day -4, and stock also added on day -4,
        # get_daily_inventory_history should show stock after consumption.
        # Let's verify against get_daily_inventory_history directly for that day.
        hist_day_4 = self.manager.get_daily_inventory_history(self.apple_product_id, days=4)
        val_day_4_hist = next((h['quantity_on_hand'] for h in hist_day_4 if h['inventory_date'] == date_4_days_ago_str),0)
        self.assertEqual(summary_map[date_4_days_ago_str]['actual_ending_inventory'], val_day_4_hist)


        self.assertEqual(summary_map[date_3_days_ago_str]['actual_consumption'], 1)

        self.assertEqual(summary_map[date_2_days_ago_str]['actual_consumption'], 0) # No consumption added for this day
        # Inventory for day -2 should be whatever was left from day -3
        hist_day_2 = self.manager.get_daily_inventory_history(self.apple_product_id, days=2)
        val_day_2_hist = next((h['quantity_on_hand'] for h in hist_day_2 if h['inventory_date'] == date_2_days_ago_str),0)
        self.assertEqual(summary_map[date_2_days_ago_str]['actual_ending_inventory'], val_day_2_hist)


    def test_get_past_summary_product_not_found(self):
        summary = self.manager.get_past_actual_inventory_summary(999, 7)
        self.assertIsInstance(summary, dict)
        self.assertFalse(summary.get('success'))
        self.assertIn("Product with ID 999 not found", summary.get('message', ''))

    def test_get_past_summary_invalid_days_past(self):
        summary_zero_days = self.manager.get_past_actual_inventory_summary(self.apple_product_id, 0)
        self.assertIsInstance(summary_zero_days, dict)
        self.assertFalse(summary_zero_days.get('success'))
        self.assertEqual(summary_zero_days.get('message'), "days_past must be a positive integer.")

        summary_negative_days = self.manager.get_past_actual_inventory_summary(self.apple_product_id, -1)
        self.assertIsInstance(summary_negative_days, dict)
        self.assertFalse(summary_negative_days.get('success'))
        self.assertEqual(summary_negative_days.get('message'), "days_past must be a positive integer.")

# --- Tests for get_inventory_batches_with_cost ---
class TestInventoryBatchesWithCost(unittest.TestCase):
    def setUp(self):
        self.manager = InventoryManager(db_filepath=":memory:")
        # Add categories
        self.cat1_id = self.manager.add_category("Cat1")['category_id']
        self.cat2_id = self.manager.add_category("Cat2")['category_id']

        # Add products
        self.prod1_id = self.manager.create_product("Product A", self.cat1_id, None, "kg", 10, purchase_location="Store X")['product_id']
        self.prod2_id = self.manager.create_product("Product B", self.cat2_id, None, "pcs", 5, purchase_location="Store Y")['product_id']
        self.prod3_id = self.manager.create_product("Product C", self.cat1_id, None, "ltr", 7, purchase_location="Store X")['product_id'] # No inventory

        # Add inventory batches (these call add_inventory_stock which uses product's default expiry)
        # Product A batches
        self.manager.log_purchase(self.prod1_id, "2024-01-01", 10.0, 1.00, "Vendor 1") # Batch A1, expires 2024-01-11
        self.manager.log_purchase(self.prod1_id, "2024-01-05", 5.0, 1.10, "Vendor 2")  # Batch A2, expires 2024-01-15

        # Product B batches
        self.manager.log_purchase(self.prod2_id, "2024-01-02", 20.0, 0.50, "Vendor 3") # Batch B1, expires 2024-01-07
        # Batch B2 - will have no direct cost entry on its purchase date
        self.manager.add_inventory_stock(self.prod2_id, "15", "2024-01-08") # expires 2024-01-13

        # Batch with zero quantity - should be filtered out
        zero_qty_batch_res = self.manager.add_inventory_stock(self.prod1_id, "0", "2024-01-03")
        # Update its quantity to 0 directly if add_inventory_stock prevents 0 qty string.
        # Assuming add_inventory_stock allows "0" and it translates to 0.
        # If not, we might need to consume it or adjust it to 0.
        # For simplicity, let's ensure the quantity is indeed 0.
        if zero_qty_batch_res.get('success'):
            conn = self.manager._get_db_connection()
            cursor = conn.cursor()
            cursor.execute("UPDATE inventory_items SET quantity = '0' WHERE id = ?", (zero_qty_batch_res['stock_item_id'],))
            conn.commit()
            conn.close()


    def tearDown(self):
        if self.manager and hasattr(self.manager, 'conn') and self.manager.conn:
            self.manager.close_connection()

    def test_get_batches_basic_retrieval_and_costing(self):
        batches = self.manager.get_inventory_batches_with_cost(page=1, per_page=10)
        self.assertEqual(len(batches), 4) # 2 for A, 2 for B. Zero qty batch for A is excluded.

        # Product A, Batch 1 (purchased 2024-01-01)
        batch_a1 = next((b for b in batches if b['product_id'] == self.prod1_id and b['purchase_date'] == "2024-01-01"), None)
        self.assertIsNotNone(batch_a1)
        self.assertEqual(batch_a1['product_name'], "Product A")
        self.assertEqual(float(batch_a1['quantity']), 10.0)
        self.assertEqual(batch_a1['cost_per_unit'], 1.00)
        self.assertEqual(batch_a1['vendor'], "Vendor 1")

        # Product A, Batch 2 (purchased 2024-01-05)
        batch_a2 = next((b for b in batches if b['product_id'] == self.prod1_id and b['purchase_date'] == "2024-01-05"), None)
        self.assertIsNotNone(batch_a2)
        self.assertEqual(float(batch_a2['quantity']), 5.0)
        self.assertEqual(batch_a2['cost_per_unit'], 1.10)
        self.assertEqual(batch_a2['vendor'], "Vendor 2")

        # Product B, Batch 1 (purchased 2024-01-02)
        batch_b1 = next((b for b in batches if b['product_id'] == self.prod2_id and b['purchase_date'] == "2024-01-02"), None)
        self.assertIsNotNone(batch_b1)
        self.assertEqual(float(batch_b1['quantity']), 20.0)
        self.assertEqual(batch_b1['cost_per_unit'], 0.50)
        self.assertEqual(batch_b1['vendor'], "Vendor 3")

        # Product B, Batch 2 (purchased 2024-01-08) - No direct cost entry
        batch_b2 = next((b for b in batches if b['product_id'] == self.prod2_id and b['purchase_date'] == "2024-01-08"), None)
        self.assertIsNotNone(batch_b2)
        self.assertEqual(float(batch_b2['quantity']), 15.0)
        self.assertIsNone(batch_b2['cost_per_unit']) # No PurchaseLog on this date for this product
        self.assertIsNone(batch_b2['vendor'])


    def test_get_batches_count(self):
        count = self.manager.get_inventory_batches_with_cost_count()
        self.assertEqual(count, 4) # Excludes zero quantity batch

    def test_get_batches_filter_search_term(self):
        batches = self.manager.get_inventory_batches_with_cost(search_term="Product A", page=1, per_page=10)
        self.assertEqual(len(batches), 2)
        self.assertTrue(all(b['product_name'] == "Product A" for b in batches))
        count = self.manager.get_inventory_batches_with_cost_count(search_term="Product A")
        self.assertEqual(count, 2)

    def test_get_batches_filter_category(self):
        batches = self.manager.get_inventory_batches_with_cost(category="Cat2", page=1, per_page=10)
        self.assertEqual(len(batches), 2) # Product B batches
        self.assertTrue(all(b['category_name'] == "Cat2" for b in batches))
        count = self.manager.get_inventory_batches_with_cost_count(category="Cat2")
        self.assertEqual(count, 2)

    def test_get_batches_filter_purchase_date(self):
        batches = self.manager.get_inventory_batches_with_cost(start_purchase_date="2024-01-05", end_purchase_date="2024-01-08", page=1, per_page=10)
        self.assertEqual(len(batches), 2) # Prod A (01-05), Prod B (01-08)
        dates = sorted([b['purchase_date'] for b in batches])
        self.assertListEqual(dates, ["2024-01-05", "2024-01-08"])
        count = self.manager.get_inventory_batches_with_cost_count(start_purchase_date="2024-01-05", end_purchase_date="2024-01-08")
        self.assertEqual(count, 2)

    def test_get_batches_filter_expiry_date(self):
        # Prod A1 expires 2024-01-11, Prod A2 expires 2024-01-15
        # Prod B1 expires 2024-01-07, Prod B2 expires 2024-01-13
        batches = self.manager.get_inventory_batches_with_cost(start_expiry_date="2024-01-10", end_expiry_date="2024-01-14", page=1, per_page=10)
        self.assertEqual(len(batches), 2) # Prod A1 (01-11), Prod B2 (01-13)
        exp_dates = sorted([b['expiry_date'] for b in batches])
        self.assertListEqual(exp_dates, ["2024-01-11", "2024-01-13"])

    def test_get_batches_sorting(self):
        # Sort by product name DESC
        batches_name_desc = self.manager.get_inventory_batches_with_cost(sort_by='product_name', sort_order='DESC', page=1, per_page=10)
        self.assertEqual(batches_name_desc[0]['product_name'], "Product B")
        self.assertEqual(batches_name_desc[1]['product_name'], "Product B")
        self.assertEqual(batches_name_desc[2]['product_name'], "Product A")
        self.assertEqual(batches_name_desc[3]['product_name'], "Product A")

        # Sort by quantity ASC
        batches_qty_asc = self.manager.get_inventory_batches_with_cost(sort_by='quantity', sort_order='ASC', page=1, per_page=10)
        self.assertEqual(float(batches_qty_asc[0]['quantity']), 5.0)  # Prod A2
        self.assertEqual(float(batches_qty_asc[1]['quantity']), 10.0) # Prod A1
        self.assertEqual(float(batches_qty_asc[2]['quantity']), 15.0) # Prod B2
        self.assertEqual(float(batches_qty_asc[3]['quantity']), 20.0) # Prod B1

    def test_get_batches_pagination(self):
        batches_page1 = self.manager.get_inventory_batches_with_cost(sort_by='product_name', sort_order='ASC', page=1, per_page=2)
        self.assertEqual(len(batches_page1), 2)
        self.assertEqual(batches_page1[0]['product_name'], "Product A") # Assuming A1 comes before A2
        self.assertEqual(batches_page1[1]['product_name'], "Product A")

        batches_page2 = self.manager.get_inventory_batches_with_cost(sort_by='product_name', sort_order='ASC', page=2, per_page=2)
        self.assertEqual(len(batches_page2), 2)
        self.assertEqual(batches_page2[0]['product_name'], "Product B")
        self.assertEqual(batches_page2[1]['product_name'], "Product B")

        count = self.manager.get_inventory_batches_with_cost_count()
        self.assertEqual(count, 4)


if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)

# Example of how to run this:
# Assuming this file is test_food_manager.py and Food_manager.py is in the same directory
# python -m unittest test_food_manager.py
