import unittest
import os
import sqlite3 # For direct DB verification
import openpyxl # For creating test Excel files
from datetime import date, timedelta, datetime

# Import the Flask app instance and manager classes
from app import app # Import the app instance
# We will monkeypatch app.manager and app.recipe_mngr
from Food_manager import InventoryManager
from recipe_manager import RecipeManager

# --- Test File Paths ---
# Single DB for all app tests, reflecting shared DB in app.py
TEST_APP_DB_FILE = "test_app_main.db" 
TEST_APP_EXCEL_FILE = "test_upload.xlsx"


class BaseAppTest(unittest.TestCase):
    """Base class for App tests to handle common setup for Flask app and DB."""
    
    @classmethod
    def setUpClass(cls):
        app.config['TESTING'] = True
        app.config['SECRET_KEY'] = 'test_secret_key_for_app_tests'
        app.config['WTF_CSRF_ENABLED'] = False # Disable CSRF for testing forms

        # Store original managers from app.py context if needed for restoration
        # but since we re-assign in setUp for each test class instance, this might be redundant
        # if test classes don't overlap their execution in a way that this matters.
        # For safety, it's good practice if there's any doubt.
        cls.original_app_inventory_manager = app.manager
        cls.original_app_recipe_manager = app.recipe_mngr

    @classmethod
    def tearDownClass(cls):
        # Restore original managers if they were changed at class level
        app.manager = cls.original_app_inventory_manager
        app.recipe_mngr = cls.original_app_recipe_manager

    def setUp(self):
        self.client = app.test_client()
        self.test_db_fp = TEST_APP_DB_FILE
        self.test_excel_fp = TEST_APP_EXCEL_FILE

        # Ensure a clean database for each test method
        if os.path.exists(self.test_db_fp):
            os.remove(self.test_db_fp)
        
        # Create new manager instances for each test, using the shared test DB
        # This ensures that _initialize_db() is called for both, creating all tables
        self.inventory_manager = InventoryManager(db_filepath=self.test_db_fp)
        self.recipe_manager = RecipeManager(db_filepath=self.test_db_fp) # Uses the same DB

        # Monkeypatch the global manager instances in the app module
        app.manager = self.inventory_manager
        app.recipe_mngr = self.recipe_manager

        # Verify monkeypatching by checking the db_filepath attribute
        self.assertEqual(app.manager.db_filepath, self.test_db_fp)
        self.assertEqual(app.recipe_mngr.db_filepath, self.test_db_fp)


    def tearDown(self):
        if os.path.exists(self.test_db_fp):
            os.remove(self.test_db_fp)
        if os.path.exists(self.test_excel_fp): # Excel file is created by some tests
            os.remove(self.test_excel_fp)

    # --- Helper Methods for DB Interaction ---
    def _get_db_connection(self):
        conn = sqlite3.connect(self.test_db_fp)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;") # Important for recipe tests
        return conn

    def _get_inventory_item_from_db(self, name):
        with self._get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM inventory_items WHERE name = ?", (name,))
            return cursor.fetchone()

    def _get_all_inventory_items_from_db(self):
        with self._get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM inventory_items")
            return cursor.fetchall()
            
    def _get_historical_item_count_from_db(self, name=None):
        with self._get_db_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT COUNT(*) as count FROM historical_items"
            params = []
            if name:
                query += " WHERE name = ?"
                params.append(name)
            cursor.execute(query, params)
            return cursor.fetchone()['count']

    def _get_recipe_from_db(self, name):
        with self._get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM recipes WHERE name = ?", (name,))
            recipe_row = cursor.fetchone()
            if recipe_row:
                recipe_dict = dict(recipe_row)
                cursor.execute("SELECT * FROM recipe_ingredients WHERE recipe_id = ?", (recipe_dict['id'],))
                recipe_dict['ingredients'] = [dict(ing_row) for ing_row in cursor.fetchall()]
                return recipe_dict
            return None
            
    def _get_all_recipes_from_db(self):
        recipes = []
        with self._get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, name, description FROM recipes")
            recipe_rows = cursor.fetchall()
            for r_row in recipe_rows:
                recipe_dict = dict(r_row)
                cursor.execute("SELECT item_name, quantity_required FROM recipe_ingredients WHERE recipe_id = ?", (recipe_dict['id'],))
                recipe_dict['ingredients'] = [dict(ing_row) for ing_row in cursor.fetchall()]
                recipes.append(recipe_dict)
        return recipes


    # --- Helper for Excel ---
    def _create_dummy_excel_file(self, data_rows):
        wb = openpyxl.Workbook()
        sheet = wb.active
        header = ["Name", "Quantity", "Purchase Date", "Expiry Days"]
        sheet.append(header)
        for row in data_rows:
            sheet.append(row)
        wb.save(self.test_excel_fp)
        return self.test_excel_fp


class TestAppInventoryRoutes(BaseAppTest): # Inherits from BaseAppTest
    # --- Test GET Routes (Inventory) ---
    def test_home_page(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Welcome to Your Food Inventory Manager!", response.data)

    def test_current_inventory_view_empty(self):
        response = self.client.get('/inventory/current')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Current inventory is empty.", response.data)

    def test_current_inventory_view_with_items(self):
        app.manager.add_item_to_list("Test Apple", "5", "2023-01-01", 10)
        response = self.client.get('/inventory/current')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Test Apple", response.data)

    # ... (other GET tests for historical, projections, add, consume, upload pages remain similar)

    # --- Test POST Routes (Inventory) ---
    def test_add_item_post_success(self):
        with self.client:
            response = self.client.post('/inventory/add', data={
                'name': 'Test Cherry', 'quantity': '100g',
                'purchase_date': '2023-10-01', 'expiry_days': '5'
            }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Item 'Test Cherry' added successfully!", response.data)
        
        item_in_db = self._get_inventory_item_from_db('Test Cherry')
        self.assertIsNotNone(item_in_db)
        self.assertEqual(item_in_db['quantity'], '100g')

    def test_add_item_post_validation_error(self):
        with self.client:
            response = self.client.post('/inventory/add', data={'name': ''})
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Item name is required.", response.data)
        self.assertIsNone(self._get_inventory_item_from_db('')) # Check DB

    def test_consume_item_post_success_partial(self):
        app.manager.add_item_to_list("Test Beans", "2 cans", "2023-03-03", 365)
        with self.client:
            response = self.client.post('/inventory/consume', data={
                'item_name': 'Test Beans', 'quantity_consumed': '1'
            }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Total consumed: 1.00 of Test Beans.", response.data) # Message from consume_item
        
        item_in_db = self._get_inventory_item_from_db('Test Beans')
        self.assertIsNotNone(item_in_db)
        # Assuming "2 cans" parsed to 2.0, consumed 1.0, new string is "1.00 cans"
        self.assertEqual(item_in_db['quantity'], "1.00 cans") 
        self.assertEqual(self._get_historical_item_count_from_db("Test Beans"), 1)


    def test_consume_item_post_full_consumption(self):
        app.manager.add_item_to_list("Test Soda", "6 units", "2023-04-01", 180)
        with self.client:
            response = self.client.post('/inventory/consume', data={
                'item_name': 'Test Soda', 'quantity_consumed': '6'
            }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Total consumed: 6.00 of Test Soda.", response.data)
        self.assertIsNone(self._get_inventory_item_from_db('Test Soda'))
        self.assertEqual(self._get_historical_item_count_from_db("Test Soda"), 1)

    def test_upload_excel_post_success(self):
        excel_data = [["Apples", "10 units", "2023-10-01", 7], ["Bananas", 12, datetime(2023,10,5), 5]]
        excel_file_path = self._create_dummy_excel_file(excel_data)
        with open(excel_file_path, 'rb') as fp:
            with self.client:
                response = self.client.post('/inventory/upload_excel',
                                           data={'excel_file': (fp, os.path.basename(excel_file_path))},
                                           follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Successfully added 2 items from the Excel file.", response.data)
        self.assertIsNotNone(self._get_inventory_item_from_db("Apples"))
        self.assertIsNotNone(self._get_inventory_item_from_db("Bananas"))


class TestAppRecipeRoutes(BaseAppTest): # Inherits from BaseAppTest
    # --- Test GET Routes (Recipes) ---
    def test_add_recipe_view_get(self):
        response = self.client.get('/recipes/add')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Add New Recipe", response.data)

    def test_recipes_list_view_empty(self):
        response = self.client.get('/recipes')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"No recipes found.", response.data)

    def test_recipes_list_view_with_recipes(self):
        app.recipe_mngr.add_recipe({"name": "Pasta Bake", "ingredients": []})
        response = self.client.get('/recipes')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Pasta Bake", response.data)

    def test_recipe_detail_view_get_exists(self):
        app.recipe_mngr.add_recipe({"name": "Salad", "description": "A salad", "ingredients": [{"item_name": "Lettuce", "quantity_required": 100.0}]})
        app.manager.add_item_to_list("Lettuce", "50g", "2023-01-01", 7) # Not enough
        response = self.client.get('/recipes/Salad')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Salad", response.data)
        self.assertIn(b"Needed:", response.data) # For Lettuce

    # --- Test POST Routes (Recipes) ---
    def test_add_recipe_post_success(self):
        with self.client:
            response = self.client.post('/recipes/add', data={
                'recipe_name': 'Omelette', 'description': 'Basic omelette.',
                'ingredient_1_name': 'Eggs', 'ingredient_1_quantity': '2',
                'ingredient_2_name': 'Milk', 'ingredient_2_quantity': '0.1'
            }, follow_redirects=True)
        self.assertEqual(response.status_code, 200) # Redirects to add_recipe_view
        self.assertIn(b"Recipe 'Omelette' added successfully!", response.data)
        recipe_in_db = self._get_recipe_from_db("Omelette")
        self.assertIsNotNone(recipe_in_db)
        self.assertEqual(len(recipe_in_db['ingredients']), 2)

    def test_make_recipe_post_success(self):
        app.recipe_mngr.add_recipe({"name": "Toast", "ingredients": [{"item_name": "Bread", "quantity_required": 2.0}]})
        app.manager.add_item_to_list("Bread", "10 slices", "2023-10-01", 7)
        
        with self.client:
            response = self.client.post('/recipes/Toast/make', follow_redirects=True)
        self.assertEqual(response.status_code, 200) # Redirects to recipe detail
        self.assertIn(b"Recipe 'Toast' made successfully!", response.data)
        
        bread_item = self._get_inventory_item_from_db("Bread")
        self.assertIsNotNone(bread_item)
        # Initial "10 slices" -> 10.0. Consumed 2.0. Remaining 8.0. Stored as "8.0 slices" by current logic
        self.assertEqual(bread_item['quantity'], "8.0 slices") 
        self.assertEqual(self._get_historical_item_count_from_db("Bread"), 1)


    def test_make_recipe_post_insufficient_ingredients(self):
        app.recipe_mngr.add_recipe({"name": "Cereal", "ingredients": [{"item_name": "Flakes", "quantity_required": 100.0}]})
        app.manager.add_item_to_list("Flakes", "50g", "2023-10-01", 30)

        with self.client:
            response = self.client.post('/recipes/Cereal/make', follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Cannot make 'Cereal'. Not enough ingredients currently available.", response.data)
        
        flakes_item = self._get_inventory_item_from_db("Flakes")
        self.assertIsNotNone(flakes_item)
        self.assertEqual(flakes_item['quantity'], "50g") # Unchanged
        self.assertEqual(self._get_historical_item_count_from_db(), 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
