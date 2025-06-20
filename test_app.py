import unittest
import os
import sqlite3
from app import app, manager as app_manager
from Food_manager import InventoryManager

class TestAppProductList(unittest.TestCase):

    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        app.config['SECRET_KEY'] = 'test_secret_key'
        app.config['SERVER_NAME'] = 'localhost.test'

        self.app_context = app.app_context()
        self.app_context.push()

        self.client = app.test_client()

        self.original_db_filepath = app_manager.db_filepath
        app_manager.db_filepath = ":memory:"
        app_manager.conn = sqlite3.connect(":memory:")
        app_manager.conn.row_factory = sqlite3.Row
        app_manager._initialize_db()

        self.products_data = [
            {'id': 1, 'name': 'Apples', 'category': 'Produce', 'subcategory': 'Fruit', 'unit_of_measure': 'kg', 'default_expiry_days': 10, 'purchase_location': 'Store A'},
            {'id': 2, 'name': 'Bananas', 'category': 'Produce', 'subcategory': 'Fruit', 'unit_of_measure': 'kg', 'default_expiry_days': 5, 'purchase_location': 'Store B'},
            {'id': 3, 'name': 'Chicken Breast', 'category': 'Meat', 'subcategory': 'Poultry', 'unit_of_measure': 'kg', 'default_expiry_days': 3, 'purchase_location': 'Store A'},
            {'id': 4, 'name': 'Milk', 'category': 'Dairy', 'subcategory': 'Milk Products', 'unit_of_measure': 'liter', 'default_expiry_days': 7, 'purchase_location': 'Store C'},
            {'id': 5, 'name': 'Bread', 'category': 'Bakery', 'subcategory': 'Bread', 'unit_of_measure': 'loaf', 'default_expiry_days': 4, 'purchase_location': 'Store B'},
            {'id': 6, 'name': 'Organic Apples', 'category': 'Produce', 'subcategory': 'Fruit', 'unit_of_measure': 'kg', 'default_expiry_days': 12, 'purchase_location': 'Store D'},
            {'id': 7, 'name': 'Salmon Fillet', 'category': 'Meat', 'subcategory': 'Fish', 'unit_of_measure': 'kg', 'default_expiry_days': 2, 'purchase_location': 'Store A'},
            {'id': 8, 'name': 'Yogurt', 'category': 'Dairy', 'subcategory': 'Milk Products', 'unit_of_measure': 'kg', 'default_expiry_days': 14, 'purchase_location': 'Store C'},
            {'id': 9, 'name': 'Carrots', 'category': 'Produce', 'subcategory': 'Vegetable', 'unit_of_measure': 'kg', 'default_expiry_days': 10, 'purchase_location': 'Store B'},
            {'id': 10, 'name': 'Whole Wheat Bread', 'category': 'Bakery', 'subcategory': 'Bread', 'unit_of_measure': 'loaf', 'default_expiry_days': 5, 'purchase_location': 'Store D'},
        ]
        
        for p_data in self.products_data:
            app_manager.create_product(
                name=p_data['name'],
                category=p_data.get('category'),
                subcategory=p_data.get('subcategory'),
                unit_of_measure=p_data['unit_of_measure'],
                default_expiry_days=p_data['default_expiry_days'],
                purchase_location=p_data.get('purchase_location')
            )

    def tearDown(self):
        if app_manager.db_filepath == ":memory:" and app_manager.conn:
            app_manager.close_connection()
        
        app_manager.db_filepath = self.original_db_filepath
        app_manager.conn = None
        # app_manager._initialize_db() # Commented out

        self.app_context.pop()

    def test_products_page_loads(self):
        response = self.client.get('/products')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Product List", response.data)

    def test_filter_bar_elements_present(self):
        response = self.client.get('/products')
        self.assertEqual(response.status_code, 200)
        html_content = response.data.decode('utf-8')

        self.assertIn('name="search_term"', html_content)
        self.assertIn('name="category"', html_content)
        self.assertIn('name="purchase_location"', html_content)
        self.assertIn('type="submit"', html_content)
        self.assertIn('href="/products"', html_content)

    def test_filter_by_search_term(self):
        response = self.client.get('/products?search_term=Apples')
        self.assertEqual(response.status_code, 200)
        html_content = response.data.decode('utf-8')
        self.assertIn('Apples', html_content)
        self.assertIn('Organic Apples', html_content)
        self.assertNotIn('Bananas', html_content)
        # Pagination string "Page 1 of 1" is not shown if total_pages <= 1

    def test_filter_by_category(self):
        response = self.client.get('/products?category=Meat')
        self.assertEqual(response.status_code, 200)
        html_content = response.data.decode('utf-8')
        self.assertIn('Chicken Breast', html_content)
        self.assertIn('Salmon Fillet', html_content)
        self.assertNotIn('Apples', html_content)
        # Pagination string "Page 1 of 1" is not shown if total_pages <= 1

    def test_filter_by_purchase_location(self):
        response = self.client.get('/products?purchase_location=Store A')
        self.assertEqual(response.status_code, 200)
        html_content = response.data.decode('utf-8')
        self.assertIn('Apples', html_content)
        self.assertIn('Chicken Breast', html_content)
        self.assertIn('Salmon Fillet', html_content)
        self.assertNotIn('Bananas', html_content)
        # Pagination string "Page 1 of 1" is not shown if total_pages <= 1

    def test_sorting_by_name(self):
        response_asc = self.client.get('/products?sort_by=name&sort_order=ASC&per_page=10')
        html_asc = response_asc.data.decode('utf-8')
        positions = {}
        sorted_names = sorted([p['name'] for p in self.products_data])
        for name in sorted_names:
            positions[name] = html_asc.find(name)
        if len(sorted_names) >=3:
             self.assertTrue(positions[sorted_names[0]] < positions[sorted_names[1]] < positions[sorted_names[2]])

        response_desc = self.client.get('/products?sort_by=name&sort_order=DESC&per_page=10')
        html_desc = response_desc.data.decode('utf-8')
        positions_desc = {}
        for name in sorted_names:
            positions_desc[name] = html_desc.find(name)
        if len(sorted_names) >= 3:
            self.assertTrue(positions_desc[sorted_names[-1]] < positions_desc[sorted_names[-2]] < positions_desc[sorted_names[-3]])

    def test_pagination(self):
        response_p1 = self.client.get('/products?sort_by=name&sort_order=ASC&page=1&per_page=3')
        html_p1 = response_p1.data.decode('utf-8')
        sorted_names = sorted([p['name'] for p in self.products_data])
        self.assertIn(sorted_names[0], html_p1)
        self.assertIn(sorted_names[1], html_p1)
        self.assertIn(sorted_names[2], html_p1)
        self.assertNotIn(sorted_names[3], html_p1)
        self.assertIn("Page 1 of 4", html_p1)

        response_p2 = self.client.get('/products?sort_by=name&sort_order=ASC&page=2&per_page=3')
        html_p2 = response_p2.data.decode('utf-8')
        self.assertNotIn(sorted_names[2], html_p2)
        self.assertIn(sorted_names[3], html_p2)
        self.assertIn(sorted_names[4], html_p2)
        self.assertIn(sorted_names[5], html_p2)
        self.assertNotIn(sorted_names[6], html_p2)
        self.assertIn("Page 2 of 4", html_p2)

    def test_pagination_controls(self):
        response_p1 = self.client.get('/products?sort_by=name&sort_order=ASC&page=1&per_page=3')
        html_p1 = response_p1.data.decode('utf-8')
        self.assertIn("button-disabled", html_p1)
        self.assertIn("Previous", html_p1)
        self.assertNotIn("Next <i class=\"fas fa-chevron-right\"></i></span>", html_p1)
        self.assertIn("Next <i class=\"fas fa-chevron-right\"></i>", html_p1)

        response_p4 = self.client.get('/products?sort_by=name&sort_order=ASC&page=4&per_page=3')
        html_p4 = response_p4.data.decode('utf-8')
        self.assertNotIn("Previous</span>", html_p4)
        self.assertIn("Previous", html_p4)
        self.assertIn("button-disabled", html_p4)
        self.assertIn("Next", html_p4)

    def test_filter_sort_preservation_in_pagination(self):
        search_term_prod = ""
        category_prod = "Produce"
        per_page_prod = 2
        sort_by_prod = "name"
        sort_order_prod = "ASC"

        response_p1 = self.client.get(f'/products?search_term={search_term_prod}&category={category_prod}&sort_by={sort_by_prod}&sort_order={sort_order_prod}&page=1&per_page={per_page_prod}')
        html_p1 = response_p1.data.decode('utf-8')
        self.assertIn("Page 1 of 2", html_p1)
        
        self.assertIn('href="', html_p1)
        self.assertIn('category=Produce', html_p1.replace('&amp;', '&'))
        self.assertIn('sort_by=name', html_p1.replace('&amp;', '&'))
        self.assertIn('sort_order=ASC', html_p1.replace('&amp;', '&'))
        self.assertIn('page=2', html_p1.replace('&amp;', '&'))
        self.assertIn(f'per_page={per_page_prod}', html_p1.replace('&amp;', '&'))
        if not search_term_prod:
             self.assertNotIn(f'search_term={search_term_prod+"A"}', html_p1.replace('&amp;', '&'))
        if not category_prod:
             self.assertNotIn(f'category={category_prod+"A"}', html_p1.replace('&amp;', '&'))

    def test_clear_filters_functionality(self):
        response_filtered = self.client.get('/products?search_term=Apples&category=Produce&sort_by=name&sort_order=DESC')
        self.assertEqual(response_filtered.status_code, 200)
        html_filtered = response_filtered.data.decode('utf-8')
        
        clear_filters_url_expected = "/products"
        self.assertIn(f'href="{clear_filters_url_expected}"', html_filtered)
        
        response_cleared = self.client.get(clear_filters_url_expected)
        self.assertEqual(response_cleared.status_code, 200)
        html_cleared = response_cleared.data.decode('utf-8')

        self.assertIn('Apples', html_cleared)
        self.assertIn('Bananas', html_cleared)
        self.assertIn('Chicken Breast', html_cleared)
        self.assertIn('name="search_term" id="search_term" value=""', html_cleared)
        self.assertRegex(html_cleared, r'<select name="category"[^>]*>\s*<option value="" selected>\s*All Categories\s*</option>')
        self.assertRegex(html_cleared, r'<select name="purchase_location"[^>]*>\s*<option value="" selected>\s*All Locations\s*</option>')

# --- Tests for Excel Upload UoM Mismatch Flash Messages ---
# We need io, openpyxl for creating dummy excel files, and patch from unittest.mock
import io
import openpyxl
from unittest.mock import patch

class TestExcelUploadUoMMismatch(unittest.TestCase): # Create a new class for clarity

    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False # Disable CSRF for simpler test forms
        app.config['SECRET_KEY'] = 'test_secret_key_excel' # Ensure a secret key for flash messages
        app.config['SERVER_NAME'] = 'localhost.test.excel' # If SERVER_NAME is used by url_for

        # It's important to push an app context if your app uses it,
        # especially for things like url_for or accessing current_app.
        self.app_context = app.app_context()
        self.app_context.push()

        self.client = app.test_client()

        # Mock the manager instance used by the app for these tests
        # This avoids actual DB operations and lets us control `add_item_to_list` return values
        self.mock_manager = unittest.mock.MagicMock(spec=InventoryManager)

        # It's crucial that the app uses this mocked manager.
        # We'll patch 'app.manager' which is the global instance.
        # Store original and patch it
        self.original_app_manager = app.manager
        app.manager = self.mock_manager

    def tearDown(self):
        app.manager = self.original_app_manager # Restore original manager
        # Also restore recipe_mngr if it was patched, though it wasn't in this class
        self.app_context.pop()

    def _create_dummy_excel_file(self, data_rows):
        """Helper to create an in-memory Excel file with given data."""
        workbook = openpyxl.Workbook()
        sheet = workbook.active
        # Add header
        sheet.append(['Name', 'Quantity', 'Purchase Date', 'Expiry Days', 'Category', 'Unit of Measure'])
        for row in data_rows:
            sheet.append(row)

        excel_file_io = io.BytesIO()
        workbook.save(excel_file_io)
        excel_file_io.seek(0)
        return excel_file_io

    def test_upload_excel_uom_mismatch_triggers_flash(self):
        # Simulate one row with mismatch, one without
        dummy_excel_rows = [
            ['Apples', '5', '2023-01-01', 10, 'Produce', 'bags'], # Mismatch
            ['Bananas', '12', '2023-01-01', 5, 'Produce', 'kg']   # No mismatch (assume DB is kg)
        ]
        excel_file = self._create_dummy_excel_file(dummy_excel_rows)

        # Mock return values for add_item_to_list
        self.mock_manager.add_item_to_list.side_effect = [
            {'success': True, 'item_id': 1, 'product_id': 1, 'uom_mismatch': True,
             'original_product_name': 'Apples', 'excel_uom': 'bags', 'db_uom': 'kg'},
            {'success': True, 'item_id': 2, 'product_id': 2, 'uom_mismatch': False}
        ]
        # Mock get_product_by_name for the UoM check in app.py (needed for new product check)
        self.mock_manager.get_product_by_name.side_effect = [
            unittest.mock.MagicMock(return_value={'id': 1, 'unit_of_measure': 'kg'}), # For 'Apples'
            unittest.mock.MagicMock(return_value={'id': 2, 'unit_of_measure': 'kg'})  # For 'Bananas'
        ]


        with self.client: # Use client in a 'with' block to handle session_transaction context
            response = self.client.post('/inventory/upload_excel',
                                        data={'excel_file': (excel_file, 'test.xlsx')},
                                        content_type='multipart/form-data',
                                        follow_redirects=True) # Follow redirect to see flashes on target page

        self.assertEqual(response.status_code, 200) # Should redirect to current_inventory_view

        # Check flashed messages (need to access session directly, or use a helper if available)
        # For Flask < 2.3, direct session access is common in tests.
        # For Flask >= 2.3, response.flashes might be available if configured.
        # Assuming direct session access for now.
        flashed_messages = []
        with self.client.session_transaction() as session:
            flashed_messages = dict(session.get('_flashes', []))

        self.assertIn('warning', flashed_messages, "General UoM warning message category not found")
        self.assertIn("Some products had Unit of Measure mismatches", flashed_messages['warning'])

        self.assertIn('warning_detail', flashed_messages, "Detailed UoM warning message category not found")
        expected_detail_warning = "Warning: UoM for 'Apples' in Excel ('bags') differs from database ('kg'). Product's UoM was not updated."
        self.assertIn(expected_detail_warning, flashed_messages['warning_detail'])

    def test_upload_excel_no_uom_mismatch_no_flash(self):
        dummy_excel_rows = [
            ['Pears', '10', '2023-01-01', 7, 'Produce', 'kg']
        ]
        excel_file = self._create_dummy_excel_file(dummy_excel_rows)

        self.mock_manager.add_item_to_list.return_value = {
            'success': True, 'item_id': 3, 'product_id': 3, 'uom_mismatch': False
        }
        self.mock_manager.get_product_by_name.return_value = None # Simulate new product


        with self.client:
            response = self.client.post('/inventory/upload_excel',
                                 data={'excel_file': (excel_file, 'test.xlsx')},
                                 content_type='multipart/form-data',
                                 follow_redirects=True)
        self.assertEqual(response.status_code, 200)

        flashed_messages = []
        with self.client.session_transaction() as session:
            flashed_messages = dict(session.get('_flashes', []))

        # Ensure UoM specific warning categories are NOT present
        self.assertNotIn('warning', flashed_messages.keys()) # Check if 'warning' category related to UoM is absent
        self.assertNotIn('warning_detail', flashed_messages.keys())

        # General success message for item addition should be there
        self.assertIn('success', flashed_messages)
        self.assertIn("Successfully added 1 items from the Excel file.", flashed_messages['success'])


class TestRecipeProduction(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        app.config['SECRET_KEY'] = 'test_secret_key_recipe_prod'
        app.config['SERVER_NAME'] = 'localhost.test.recipeprod' # Unique server name

        self.app_context = app.app_context()
        self.app_context.push()
        self.client = app.test_client()

        # Use the actual managers from the app, but reconfigure their DB to be in-memory for tests
        self.original_manager_db = app.manager.db_filepath
        self.original_recipe_mngr_db = app.recipe_mngr.db_filepath

        app.manager.db_filepath = ":memory:"
        app.manager.conn = sqlite3.connect(":memory:") # New connection for manager
        app.manager.conn.row_factory = sqlite3.Row
        app.manager._initialize_db() # Re-initialize its own schema

        app.recipe_mngr.db_filepath = ":memory:"
        app.recipe_mngr.conn = app.manager.conn # Crucially, make them share the SAME in-memory DB connection
        app.recipe_mngr._initialize_db() # This should not conflict if schema is idempotent

        # --- Test Data Setup ---
        # 1. Create Products (Ingredients and Output)
        self.milk_prod = app.manager.create_product(name="Milk For Cheese", category="Dairy", unit_of_measure="liter", default_expiry_days=7)
        self.rennet_prod = app.manager.create_product(name="Rennet", category="Misc", unit_of_measure="tablet", default_expiry_days=365)
        self.cheese_output_prod = app.manager.create_product(name="Shredded Cheese", category="Dairy", unit_of_measure="kg", default_expiry_days=30)

        self.milk_prod_id = self.milk_prod['product_id']
        self.rennet_prod_id = self.rennet_prod['product_id']
        self.cheese_output_prod_id = self.cheese_output_prod['product_id']

        # 2. Add Recipe
        self.recipe_name = "Homemade Cheese"
        self.cheese_yield = 0.4 # e.g., 0.4 kg of cheese
        recipe_data = {
            "name": self.recipe_name,
            "description": "Simple homemade cheese",
            "instructions": "Mix milk and rennet, wait, press.",
            "ingredients": [
                {"item_name": "Milk For Cheese", "quantity_required": 2.0}, # 2 liters of milk
                {"item_name": "Rennet", "quantity_required": 1.0}        # 1 tablet of rennet
            ],
            "output_product_id": self.cheese_output_prod_id,
            "output_yield": self.cheese_yield
        }
        add_recipe_result = app.recipe_mngr.add_recipe(recipe_data)
        self.assertTrue(add_recipe_result.get('success'), f"Failed to add recipe for test: {add_recipe_result.get('message')}")
        self.recipe_id = add_recipe_result.get('recipe_id')

        # 3. Add Initial Stock for Ingredients
        app.manager.add_inventory_stock(product_id=self.milk_prod_id, quantity_str="10", purchase_date_str="2024-01-01") # 10 liters of milk
        app.manager.add_inventory_stock(product_id=self.rennet_prod_id, quantity_str="5", purchase_date_str="2024-01-01")   # 5 tablets of rennet
        # Output product (Shredded Cheese) starts at 0 stock implicitly, or we can add some. Let's start at 0.

    def tearDown(self):
        # Close the shared connection via one of the managers
        if app.manager.db_filepath == ":memory:" and app.manager.conn:
            app.manager.close_connection()

        # Restore original DB filepaths and clear conn for both managers
        app.manager.db_filepath = self.original_manager_db
        app.manager.conn = None
        app.recipe_mngr.db_filepath = self.original_recipe_mngr_db
        app.recipe_mngr.conn = None

        self.app_context.pop()

    def test_make_recipe_produces_output(self):
        num_batches = 2

        # Get initial quantities
        initial_milk_qty = app.manager.get_total_item_quantity(self.milk_prod_id)
        initial_rennet_qty = app.manager.get_total_item_quantity(self.rennet_prod_id)
        initial_cheese_qty = app.manager.get_total_item_quantity(self.cheese_output_prod_id)
        self.assertEqual(initial_cheese_qty, 0) # Assuming it starts at 0

        # Simulate making the recipe
        response = self.client.post(f'/recipes/{self.recipe_name}/make',
                                    data={'num_batches': str(num_batches)},
                                    follow_redirects=True)
        self.assertEqual(response.status_code, 200) # Should redirect to recipe detail page

        # Verify flashed messages
        flashed_messages = []
        with self.client.session_transaction() as session:
            flashes = session.get('_flashes', [])
            for category, message in flashes: # Convert to simple list of messages
                flashed_messages.append(message)

        self.assertTrue(any(f"{num_batches} batch(es) of '{self.recipe_name}' made! Ingredients consumed." in msg for msg in flashed_messages))
        expected_total_yield = self.cheese_yield * num_batches
        self.assertTrue(any(f"Produced {expected_total_yield} of 'Shredded Cheese' and added to inventory." in msg for msg in flashed_messages))

        # Verify ingredient consumption
        expected_milk_consumed = 2.0 * num_batches
        expected_rennet_consumed = 1.0 * num_batches

        final_milk_qty = app.manager.get_total_item_quantity(self.milk_prod_id)
        final_rennet_qty = app.manager.get_total_item_quantity(self.rennet_prod_id)

        self.assertAlmostEqual(final_milk_qty, initial_milk_qty - expected_milk_consumed)
        self.assertAlmostEqual(final_rennet_qty, initial_rennet_qty - expected_rennet_consumed)

        # Verify output product increase
        final_cheese_qty = app.manager.get_total_item_quantity(self.cheese_output_prod_id)
        self.assertAlmostEqual(final_cheese_qty, initial_cheese_qty + expected_total_yield)

    def test_make_recipe_no_output_product_defined(self):
        # Add a recipe without output product
        no_output_recipe_name = "Salad Without Output"
        app.recipe_mngr.add_recipe({
            "name": no_output_recipe_name, "ingredients": [{"item_name": "Milk For Cheese", "quantity_required": 0.1}],
            "output_product_id": None, "output_yield": None # Explicitly no output
        })
        # Ensure Milk For Cheese has stock
        app.manager.add_inventory_stock(product_id=self.milk_prod_id, quantity_str="1", purchase_date_str="2024-01-01")
        initial_milk_qty = app.manager.get_total_item_quantity(self.milk_prod_id)


        response = self.client.post(f'/recipes/{no_output_recipe_name}/make', data={'num_batches': '1'}, follow_redirects=True)
        self.assertEqual(response.status_code, 200)

        flashed_messages = []
        with self.client.session_transaction() as session:
            flashes = session.get('_flashes', [])
            for category, message in flashes:
                flashed_messages.append(message)

        self.assertTrue(any(f"1 batch(es) of '{no_output_recipe_name}' made! Ingredients consumed." in msg for msg in flashed_messages))
        # Ensure no production messages
        self.assertFalse(any("Produced" in msg for msg in flashed_messages))
        self.assertFalse(any("Error producing output" in msg for msg in flashed_messages))

        # Check milk was consumed
        final_milk_qty = app.manager.get_total_item_quantity(self.milk_prod_id)
        self.assertAlmostEqual(final_milk_qty, initial_milk_qty - 0.1)


if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
