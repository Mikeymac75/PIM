import unittest
import os
import sqlite3
from flask import session # Added session import
from app import app, manager as app_manager
from Food_manager import InventoryManager
import io
import openpyxl
from unittest.mock import patch, MagicMock # Ensured MagicMock is imported
from datetime import date


class TestAppProductList(unittest.TestCase):

    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        app.config['SECRET_KEY'] = 'test_secret_key'
        # app.config['SERVER_NAME'] = 'localhost.test' # Usually not needed for test_client

        self.app_context = app.app_context()
        self.app_context.push()
        self.client = app.test_client()

        # Ensure manager uses a fresh in-memory DB for each test
        app_manager.db_filepath = ":memory:"
        # Explicitly close any existing connection
        if hasattr(app_manager, 'conn') and app_manager.conn:
            try:
                app_manager.close_connection()
            except Exception as e:
                print(f"Error closing existing connection in setUp: {e}")

        app_manager.conn = sqlite3.connect(":memory:")
        app_manager.conn.row_factory = sqlite3.Row
        app_manager._initialize_db() # Re-initialize schema

        # Create categories and subcategories
        self.cat_produce = app_manager.add_category("Produce")
        self.cat_meat = app_manager.add_category("Meat")
        self.cat_dairy = app_manager.add_category("Dairy")
        self.cat_bakery = app_manager.add_category("Bakery")

        self.produce_cat_id = self.cat_produce['category_id']
        self.meat_cat_id = self.cat_meat['category_id']
        self.dairy_cat_id = self.cat_dairy['category_id']
        self.bakery_cat_id = self.cat_bakery['category_id']

        self.subcat_fruit = app_manager.add_subcategory("Fruit", self.produce_cat_id)
        self.subcat_veg = app_manager.add_subcategory("Vegetable", self.produce_cat_id)
        self.subcat_poultry = app_manager.add_subcategory("Poultry", self.meat_cat_id)
        self.subcat_fish = app_manager.add_subcategory("Fish", self.meat_cat_id)
        self.subcat_milk_prod = app_manager.add_subcategory("Milk Products", self.dairy_cat_id)
        self.subcat_bread_loaves = app_manager.add_subcategory("Bread", self.bakery_cat_id) # Renamed from self.subcat_bread

        self.fruit_subcat_id = self.subcat_fruit['subcategory_id']
        self.veg_subcat_id = self.subcat_veg['subcategory_id']
        self.poultry_subcat_id = self.subcat_poultry['subcategory_id']
        self.fish_subcat_id = self.subcat_fish['subcategory_id']
        self.milk_subcat_id = self.subcat_milk_prod['subcategory_id']
        self.bread_loaves_subcat_id = self.subcat_bread_loaves['subcategory_id']


        self.products_setup_data = [
            {'name': 'Apples', 'category_id': self.produce_cat_id, 'subcategory_id': self.fruit_subcat_id, 'unit_of_measure': 'kg', 'default_expiry_days': 10, 'purchase_location': 'Store A'},
            {'name': 'Bananas', 'category_id': self.produce_cat_id, 'subcategory_id': self.fruit_subcat_id, 'unit_of_measure': 'kg', 'default_expiry_days': 5, 'purchase_location': 'Store B'},
            {'name': 'Chicken Breast', 'category_id': self.meat_cat_id, 'subcategory_id': self.poultry_subcat_id, 'unit_of_measure': 'kg', 'default_expiry_days': 3, 'purchase_location': 'Store A'},
            {'name': 'Milk', 'category_id': self.dairy_cat_id, 'subcategory_id': self.milk_subcat_id, 'unit_of_measure': 'liter', 'default_expiry_days': 7, 'purchase_location': 'Store C'},
            {'name': 'Bread', 'category_id': self.bakery_cat_id, 'subcategory_id': self.bread_loaves_subcat_id, 'unit_of_measure': 'loaf', 'default_expiry_days': 4, 'purchase_location': 'Store B'},
            {'name': 'Organic Apples', 'category_id': self.produce_cat_id, 'subcategory_id': self.fruit_subcat_id, 'unit_of_measure': 'kg', 'default_expiry_days': 12, 'purchase_location': 'Store D'},
            {'name': 'Salmon Fillet', 'category_id': self.meat_cat_id, 'subcategory_id': self.fish_subcat_id, 'unit_of_measure': 'kg', 'default_expiry_days': 2, 'purchase_location': 'Store A'},
            {'name': 'Yogurt', 'category_id': self.dairy_cat_id, 'subcategory_id': self.milk_subcat_id, 'unit_of_measure': 'kg', 'default_expiry_days': 14, 'purchase_location': 'Store C'},
            {'name': 'Carrots', 'category_id': self.produce_cat_id, 'subcategory_id': self.veg_subcat_id, 'unit_of_measure': 'kg', 'default_expiry_days': 10, 'purchase_location': 'Store B'},
            {'name': 'Whole Wheat Bread', 'category_id': self.bakery_cat_id, 'subcategory_id': self.bread_loaves_subcat_id, 'unit_of_measure': 'loaf', 'default_expiry_days': 5, 'purchase_location': 'Store D'},
        ]
        
        for p_data in self.products_setup_data:
            # Ensure all necessary fields for create_product are present
            app_manager.create_product(
                name=p_data['name'],
                category_id=p_data['category_id'],
                subcategory_id=p_data.get('subcategory_id'), # Handles optional subcategory
                unit_of_measure=p_data['unit_of_measure'],
                default_expiry_days=p_data['default_expiry_days'],
                par_level=p_data.get('par_level', 0), # Add default if not in data
                max_holding_amount=p_data.get('max_holding_amount', 0), # Add default
                purchase_location=p_data.get('purchase_location')
            )

    def tearDown(self):
        if app_manager.db_filepath == ":memory:" and hasattr(app_manager, 'conn') and app_manager.conn:
            app_manager.close_connection()
            app_manager.conn = None # Ensure connection is reset for next test's setUp
        
        # app_manager.db_filepath = self.original_db_filepath # This line might cause issues if original_db_filepath is not set or if app_manager is not meant to be restored this way in all test classes.
                                                            # For in-memory, ensuring connection is closed and reset is key.
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
        self.assertIn('name="category"', html_content) # This will be category name
        self.assertIn('name="purchase_location"', html_content)
        self.assertIn('type="submit"', html_content)
        self.assertIn('href="/products"', html_content) # Clear filters link

    def test_filter_by_search_term(self):
        response = self.client.get('/products?search_term=Apples')
        self.assertEqual(response.status_code, 200)
        html_content = response.data.decode('utf-8')
        self.assertIn('Apples', html_content)
        self.assertIn('Organic Apples', html_content)
        self.assertNotIn('Bananas', html_content)

    def test_filter_by_category_name(self): # Updated test to reflect filtering by category name
        response = self.client.get('/products?category=Meat')
        self.assertEqual(response.status_code, 200)
        html_content = response.data.decode('utf-8')
        self.assertIn('Chicken Breast', html_content) # Belongs to Meat
        self.assertIn('Salmon Fillet', html_content)  # Belongs to Meat
        self.assertNotIn('Apples', html_content)      # Belongs to Produce

    def test_filter_by_purchase_location(self):
        response = self.client.get('/products?purchase_location=Store A')
        self.assertEqual(response.status_code, 200)
        html_content = response.data.decode('utf-8')
        self.assertIn('Apples', html_content)
        self.assertIn('Chicken Breast', html_content)
        self.assertIn('Salmon Fillet', html_content)
        self.assertNotIn('Bananas', html_content)

    def test_sorting_by_name(self):
        response_asc = self.client.get('/products?sort_by=name&sort_order=ASC&per_page=10')
        html_asc = response_asc.data.decode('utf-8')
        positions = {}
        sorted_names = sorted([p['name'] for p in self.products_setup_data])
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

    def test_sorting_by_category_name(self): # Updated for category_name
        response_asc = self.client.get('/products?sort_by=category&sort_order=ASC&per_page=10')
        html_asc = response_asc.data.decode('utf-8')
        # This test is more complex as it requires knowing the order of category names for the displayed products
        # A simpler check might be to ensure the first few items adhere to expected category order
        self.assertLess(html_asc.find("Bakery"), html_asc.find("Dairy")) # Bakery < Dairy
        self.assertLess(html_asc.find("Dairy"), html_asc.find("Meat"))   # Dairy < Meat
        self.assertLess(html_asc.find("Meat"), html_asc.find("Produce")) # Meat < Produce

    def test_pagination(self):
        response_p1 = self.client.get('/products?sort_by=name&sort_order=ASC&page=1&per_page=3')
        html_p1 = response_p1.data.decode('utf-8')
        sorted_names = sorted([p['name'] for p in self.products_setup_data])
        self.assertIn(sorted_names[0], html_p1)
        self.assertIn(sorted_names[1], html_p1)
        self.assertIn(sorted_names[2], html_p1)
        self.assertNotIn(sorted_names[3], html_p1)
        self.assertIn("Page 1 of 4", html_p1)

    # Basic test for product creation page
    def test_create_product_page_loads(self):
        response = self.client.get('/products/create')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Create New Product", response.data)
        self.assertIn(b"Category:</label>", response.data) # Check for new dropdown label

    def test_create_product_post_success(self):
        data = {
            'name': 'New Test Product 123',
            'category_id': str(self.produce_cat_id),
            'subcategory_id': str(self.fruit_subcat_id),
            'unit_of_measure': 'piece',
            'default_expiry_days': '10',
            'par_level': '5',
            'max_holding_amount': '20',
            'purchase_location': 'Test Store'
        }
        response = self.client.post('/products/create', data=data, follow_redirects=True)
        self.assertEqual(response.status_code, 200) # Should redirect to product list
        self.assertIn(b"Product 'New Test Product 123' created successfully.", response.data)
        
        # Verify product in DB (optional, but good)
        product = app_manager.get_product_by_name('New Test Product 123')
        self.assertIsNotNone(product)
        self.assertEqual(product['category_id'], self.produce_cat_id)
        self.assertEqual(product['subcategory_id'], self.fruit_subcat_id)

    def test_create_product_post_missing_required_id(self):
        data = { # Missing category_id
            'name': 'New Test Product 456',
            'subcategory_id': str(self.fruit_subcat_id),
            'unit_of_measure': 'piece',
            'default_expiry_days': '10',
        }
        response = self.client.post('/products/create', data=data, follow_redirects=True)
        self.assertEqual(response.status_code, 200) # Stays on create page
        self.assertIn(b"Category is required.", response.data)


    def test_edit_product_page_loads_and_data_prepopulation(self):
        product_to_edit_id = self.product_ids_setup['Apples']
        response = self.client.get(f'/products/{product_to_edit_id}/edit')
        self.assertEqual(response.status_code, 200)
        html_content = response.data.decode('utf-8')
        self.assertIn(b"Edit Product: Apples", response.data)
        self.assertIn(f'value="{self.produce_cat_id}" selected', html_content)
        # JavaScript will handle subcategory pre-selection, so it's harder to check directly in HTML
        # We can check if the necessary data for JS is present
        self.assertIn(f'const currentProductCategoryId = "{self.produce_cat_id}";', html_content)
        self.assertIn(f'const currentProductSubcategoryId = "{self.fruit_subcat_id}";', html_content)


    def test_edit_product_post_success(self):
        product_to_edit_id = self.product_ids_setup['Apples']
        updated_data = {
            'name': 'Granny Smith Apples',
            'category_id': str(self.produce_cat_id),
            'subcategory_id': str(self.veg_subcat_id), # Changed to Vegetable
            'unit_of_measure': 'bag',
            'default_expiry_days': '12',
            'par_level': '6',
            'max_holding_amount': '22',
            'purchase_location': 'Organic Market'
        }
        response = self.client.post(f'/products/{product_to_edit_id}/edit', data=updated_data, follow_redirects=True)
        self.assertEqual(response.status_code, 200) # Redirects to product list
        self.assertIn(b"Product ID " + str(product_to_edit_id).encode() + b" updated successfully.", response.data)

        # Verify update in DB
        product = app_manager.get_product(product_to_edit_id)
        self.assertEqual(product['name'], 'Granny Smith Apples')
        self.assertEqual(product['category_id'], self.produce_cat_id)
        self.assertEqual(product['subcategory_id'], self.veg_subcat_id)
        self.assertEqual(product['unit_of_measure'], 'bag')


# --- Tests for Excel Upload Confirmation Flow ---
class TestExcelUploadConfirmation(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        app.config['SECRET_KEY'] = 'excel_test_secret'
        self.app_context = app.app_context()
        self.app_context.push()
        self.client = app.test_client()

        app_manager.db_filepath = ":memory:"
        if hasattr(app_manager, 'conn') and app_manager.conn:
            try: app_manager.close_connection()
            except: pass
        app_manager.conn = sqlite3.connect(":memory:")
        app_manager.conn.row_factory = sqlite3.Row
        app_manager._initialize_db()

        # Pre-add some categories/subcategories for testing different scenarios
        self.cat_existing_id = app_manager.add_category("Existing Category")['category_id']
        self.subcat_existing_id = app_manager.add_subcategory("Existing Subcategory", self.cat_existing_id)['subcategory_id']

    def tearDown(self):
        if app_manager.db_filepath == ":memory:" and hasattr(app_manager, 'conn') and app_manager.conn:
            app_manager.close_connection()
            app_manager.conn = None
        self.app_context.pop()

    def _create_excel_file(self, data_rows):
        workbook = openpyxl.Workbook()
        sheet = workbook.active
        sheet.append(['Name', 'Quantity', 'Purchase Date', 'Expiry Days', 'Category', 'Subcategory', 'Unit of Measure'])
        for row in data_rows:
            sheet.append(row)
        excel_io = io.BytesIO()
        workbook.save(excel_io)
        excel_io.seek(0)
        return excel_io

    def test_excel_upload_all_existing_cat_subcat(self):
        excel_data = [
            ['Product A', '10', '2024-01-01', 5, 'Existing Category', 'Existing Subcategory', 'pcs']
        ]
        excel_file = self._create_excel_file(excel_data)
        response = self.client.post('/inventory/upload_excel',
                                    data={'excel_file': (excel_file, 'test.xlsx')},
                                    follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Successfully processed and added 1 items", response.data)
        with self.client.session_transaction() as sess:
            self.assertFalse(sess.get('items_pending_confirmation'))

    def test_excel_upload_new_category_triggers_confirmation(self):
        excel_data = [
            ['Product B', '5', '2024-01-02', 7, 'Totally New Category', 'Some Sub', 'kg']
        ]
        excel_file = self._create_excel_file(excel_data)
        response = self.client.post('/inventory/upload_excel',
                                    data={'excel_file': (excel_file, 'test.xlsx')}) # No follow_redirects initially
        self.assertEqual(response.status_code, 302) # Should redirect to GET /inventory/upload_excel
        with self.client.session_transaction() as sess:
            self.assertTrue(sess.get('items_pending_confirmation'))
            self.assertEqual(len(sess['items_pending_confirmation']), 1)
            pending_item = sess['items_pending_confirmation'][0]
            self.assertEqual(pending_item['action_required'], 'confirm_new_category')
            self.assertEqual(pending_item['confirmation_details']['new_category_name'], 'Totally New Category')

        # Check the content of the page it redirects to
        response_get = self.client.get(response.location)
        self.assertIn(b"Items Requiring Confirmation", response_get.data)
        self.assertIn(b"Totally New Category", response_get.data)

    def test_excel_upload_new_subcategory_triggers_confirmation(self):
        excel_data = [
            ['Product C', '3', '2024-01-03', 10, 'Existing Category', 'Brand New Subcategory', 'ltr']
        ]
        excel_file = self._create_excel_file(excel_data)
        response = self.client.post('/inventory/upload_excel',
                                    data={'excel_file': (excel_file, 'test.xlsx')})
        self.assertEqual(response.status_code, 302)
        with self.client.session_transaction() as sess:
            self.assertTrue(sess.get('items_pending_confirmation'))
            pending_item = sess['items_pending_confirmation'][0]
            self.assertEqual(pending_item['action_required'], 'confirm_new_subcategory')
            self.assertEqual(pending_item['confirmation_details']['category_name'], 'Existing Category')
            self.assertEqual(pending_item['confirmation_details']['new_subcategory_name'], 'Brand New Subcategory')

        response_get = self.client.get(response.location)
        self.assertIn(b"Items Requiring Confirmation", response_get.data)
        self.assertIn(b"Brand New Subcategory", response_get.data)

    def test_confirm_excel_uploads_flow(self):
        # Simulate items pending confirmation in session
        pending_items_data = [
            {
                "product_data": {'name': 'Product D', 'quantity_str': '2', 'purchase_date_str': '2024-01-04', 'expiry_days': 12, 'category': 'Confirm New Cat', 'subcategory': 'Confirm New Sub', 'unit_of_measure': 'pcs', 'par_level':0, 'max_holding_amount':0, 'purchase_location': None},
                "confirmation_details": {'new_category_name': 'Confirm New Cat', 'new_subcategory_name': 'Confirm New Sub'},
                "action_required": "confirm_new_category",
                "row_idx": 2
            },
            {
                "product_data": {'name': 'Product E', 'quantity_str': '7', 'purchase_date_str': '2024-01-05', 'expiry_days': 15, 'category': 'Existing Category', 'subcategory': 'Confirm Another Sub', 'unit_of_measure': 'pcs', 'par_level':0, 'max_holding_amount':0, 'purchase_location': None},
                "confirmation_details": {'category_id': self.cat_existing_id, 'category_name': 'Existing Category', 'new_subcategory_name': 'Confirm Another Sub'},
                "action_required": "confirm_new_subcategory",
                "row_idx": 3
            }
        ]
        with self.client.session_transaction() as sess:
            sess['items_pending_confirmation'] = pending_items_data
            sess['upload_warnings'] = ["Initial warning for Product D"]

        response = self.client.post('/confirm_excel_uploads', follow_redirects=True)
        self.assertEqual(response.status_code, 200) # Redirects to current_inventory
        self.assertIn(b"Successfully processed and added 2 confirmed items.", response.data)
        self.assertTrue(any("Initial warning for Product D" in msg.decode() for msg in response.data.split(b'<li class="warning_detail">') if b'</li>' in msg))


        # Verify creations
        prod_d = app_manager.get_product_by_name("Product D")
        self.assertIsNotNone(prod_d)
        self.assertEqual(prod_d['category_name'], 'Confirm New Cat')
        self.assertEqual(prod_d['subcategory_name'], 'Confirm New Sub')

        prod_e = app_manager.get_product_by_name("Product E")
        self.assertIsNotNone(prod_e)
        self.assertEqual(prod_e['category_name'], 'Existing Category')
        self.assertEqual(prod_e['subcategory_name'], 'Confirm Another Sub')

        with self.client.session_transaction() as sess: # Check session is cleared
            self.assertFalse(sess.get('items_pending_confirmation'))
            self.assertFalse(sess.get('upload_warnings')) # Should also be cleared after successful confirmation and display

# (TestRecipeProduction class and its setUp/tearDown can remain as is, but its product creation calls need update)
class TestRecipeProduction(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        app.config['SECRET_KEY'] = 'test_secret_key_recipe_prod'
        # app.config['SERVER_NAME'] = 'localhost.test.recipeprod'

        self.app_context = app.app_context()
        self.app_context.push()
        self.client = app.test_client()

        self.original_manager_db = app.manager.db_filepath
        self.original_recipe_mngr_db = app.recipe_mngr.db_filepath

        app.manager.db_filepath = ":memory:"
        if hasattr(app_manager, 'conn') and app_manager.conn:
            try: app_manager.close_connection()
            except: pass
        app.manager.conn = sqlite3.connect(":memory:")
        app.manager.conn.row_factory = sqlite3.Row
        app_manager._initialize_db()

        app.recipe_mngr.db_filepath = ":memory:"
        app.recipe_mngr.conn = app.manager.conn
        app.recipe_mngr._initialize_db()

        # Create Categories needed for products in this test class
        self.dairy_cat_id = app.manager.add_category("Dairy")['category_id']
        self.misc_cat_id = app.manager.add_category("Misc")['category_id']

        # Create Products using new signature
        self.milk_prod = app.manager.create_product(name="Milk For Cheese", category_id=self.dairy_cat_id, subcategory_id=None, unit_of_measure="liter", default_expiry_days=7)
        self.rennet_prod = app.manager.create_product(name="Rennet", category_id=self.misc_cat_id, subcategory_id=None, unit_of_measure="tablet", default_expiry_days=365)
        self.cheese_output_prod = app.manager.create_product(name="Shredded Cheese", category_id=self.dairy_cat_id, subcategory_id=None, unit_of_measure="kg", default_expiry_days=30)

        self.milk_prod_id = self.milk_prod['product_id']
        self.rennet_prod_id = self.rennet_prod['product_id']
        self.cheese_output_prod_id = self.cheese_output_prod['product_id']

        self.recipe_name = "Homemade Cheese"
        self.cheese_yield = 0.4
        recipe_data = {
            "name": self.recipe_name, "description": "Simple homemade cheese",
            "instructions": "Mix milk and rennet, wait, press.",
            "ingredients": [
                {"item_name": "Milk For Cheese", "quantity_required": 2.0},
                {"item_name": "Rennet", "quantity_required": 1.0} ],
            "output_product_id": self.cheese_output_prod_id, "output_yield": self.cheese_yield
        }
        add_recipe_result = app.recipe_mngr.add_recipe(recipe_data)
        self.assertTrue(add_recipe_result.get('success'), f"Failed to add recipe for test: {add_recipe_result.get('message')}")
        self.recipe_id = add_recipe_result.get('recipe_id')

        app.manager.add_inventory_stock(product_id=self.milk_prod_id, quantity_str="10", purchase_date_str="2024-01-01")
        app.manager.add_inventory_stock(product_id=self.rennet_prod_id, quantity_str="5", purchase_date_str="2024-01-01")

    def tearDown(self):
        if app.manager.db_filepath == ":memory:" and hasattr(app_manager, 'conn') and app.manager.conn:
            app.manager.close_connection()
            app.manager.conn = None

        app.manager.db_filepath = self.original_manager_db
        app.recipe_mngr.db_filepath = self.original_recipe_mngr_db
        app.recipe_mngr.conn = None

        self.app_context.pop()

    def test_make_recipe_produces_output(self):
        num_batches = 2
        initial_milk_qty = app.manager.get_total_item_quantity(self.milk_prod_id)
        initial_rennet_qty = app.manager.get_total_item_quantity(self.rennet_prod_id)
        initial_cheese_qty = app.manager.get_total_item_quantity(self.cheese_output_prod_id)
        self.assertEqual(initial_cheese_qty, 0)

        response = self.client.post(f'/recipes/{self.recipe_name}/make',
                                    data={'num_batches': str(num_batches)},
                                    follow_redirects=True)
        self.assertEqual(response.status_code, 200)

        flashed_messages = []
        with self.client.session_transaction() as session_data: # Use different var name
            flashes = session_data.get('_flashes', [])
            for category, message in flashes:
                flashed_messages.append(message)

        self.assertTrue(any(f"{num_batches} batch(es) of '{self.recipe_name}' made! Ingredients consumed." in msg for msg in flashed_messages))
        expected_total_yield = self.cheese_yield * num_batches
        self.assertTrue(any(f"Produced {expected_total_yield} of 'Shredded Cheese' and added to inventory." in msg for msg in flashed_messages))

        expected_milk_consumed = 2.0 * num_batches
        expected_rennet_consumed = 1.0 * num_batches
        final_milk_qty = app.manager.get_total_item_quantity(self.milk_prod_id)
        final_rennet_qty = app.manager.get_total_item_quantity(self.rennet_prod_id)
        self.assertAlmostEqual(final_milk_qty, initial_milk_qty - expected_milk_consumed)
        self.assertAlmostEqual(final_rennet_qty, initial_rennet_qty - expected_rennet_consumed)

        final_cheese_qty = app.manager.get_total_item_quantity(self.cheese_output_prod_id)
        self.assertAlmostEqual(final_cheese_qty, initial_cheese_qty + expected_total_yield)

    def test_make_recipe_no_output_product_defined(self):
        no_output_recipe_name = "Salad Without Output"
        # Ensure category for "Milk for Cheese" (Dairy) exists for recipe ingredient product lookup
        milk_for_cheese_prod = app.manager.get_product_by_name("Milk For Cheese")
        self.assertIsNotNone(milk_for_cheese_prod, "Milk For Cheese product not found during recipe test setup")

        app.recipe_mngr.add_recipe({
            "name": no_output_recipe_name, "ingredients": [{"item_name": "Milk For Cheese", "quantity_required": 0.1}],
            "output_product_id": None, "output_yield": None
        })
        app.manager.add_inventory_stock(product_id=self.milk_prod_id, quantity_str="1", purchase_date_str="2024-01-01")
        initial_milk_qty = app.manager.get_total_item_quantity(self.milk_prod_id)

        response = self.client.post(f'/recipes/{no_output_recipe_name}/make', data={'num_batches': '1'}, follow_redirects=True)
        self.assertEqual(response.status_code, 200)

        flashed_messages = []
        with self.client.session_transaction() as session_data:
            flashes = session_data.get('_flashes', [])
            for category, message in flashes:
                flashed_messages.append(message)

        self.assertTrue(any(f"1 batch(es) of '{no_output_recipe_name}' made! Ingredients consumed." in msg for msg in flashed_messages))
        self.assertFalse(any("Produced" in msg for msg in flashed_messages))
        self.assertFalse(any("Error producing output" in msg for msg in flashed_messages))

        final_milk_qty = app.manager.get_total_item_quantity(self.milk_prod_id)
        self.assertAlmostEqual(final_milk_qty, initial_milk_qty - 0.1)


if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
