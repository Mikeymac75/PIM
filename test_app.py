import unittest
import os
import sqlite3 # For direct DB verification
import openpyxl # For creating test Excel files
from datetime import date, timedelta, datetime
from io import BytesIO # For sending file data in POST request

# Import the Flask app instance and manager classes
from app import app # Import the app instance
from Food_manager import InventoryManager
from recipe_manager import RecipeManager

# --- Test File Paths ---
TEST_APP_DB_FILE = "test_app_main.db" 
TEST_APP_EXCEL_FILE = "test_upload.xlsx"


class BaseAppTest(unittest.TestCase):
    """Base class for App tests to handle common setup for Flask app and DB."""
    
    @classmethod
    def setUpClass(cls):
        app.config['TESTING'] = True
        app.config['SECRET_KEY'] = 'test_secret_key_for_app_tests'
        app.config['WTF_CSRF_ENABLED'] = False

        cls.original_app_inventory_manager = app.manager
        cls.original_app_recipe_manager = app.recipe_mngr

    @classmethod
    def tearDownClass(cls):
        app.manager = cls.original_app_inventory_manager
        app.recipe_mngr = cls.original_app_recipe_manager

    def setUp(self):
        self.client = app.test_client()
        self.test_db_fp = TEST_APP_DB_FILE
        self.test_excel_fp = TEST_APP_EXCEL_FILE

        if os.path.exists(self.test_db_fp):
            os.remove(self.test_db_fp)
        
        self.inventory_manager = InventoryManager(db_filepath=self.test_db_fp)
        self.recipe_manager = RecipeManager(db_filepath=self.test_db_fp) 

        app.manager = self.inventory_manager
        app.recipe_mngr = self.recipe_manager

        self.assertEqual(app.manager.db_filepath, self.test_db_fp)
        self.assertEqual(app.recipe_mngr.db_filepath, self.test_db_fp)

        self.today = date.today()
        self.today_str = self.today.isoformat()

    def _add_app_inventory_item(self, name, quantity_str, purchase_date_str, expiry_days,
                                category=None, subcategory=None, par_level=0, max_holding_amount=0,
                                purchase_location=None):
        """Helper to add items to inventory via app.manager for tests."""
        return app.manager.add_item_to_list(
            name, quantity_str, purchase_date_str, expiry_days,
            category, subcategory, par_level, max_holding_amount, purchase_location
        )

    def _add_app_historical_consumption(self, name, quantity_consumed, days_ago):
        """Helper to add historical consumption data via app.manager's DB."""
        consumed_date = (self.today - timedelta(days=days_ago)).isoformat()
        # Use app.manager's connection/cursor if possible, or direct like in food_manager tests
        conn = app.manager._get_db_connection() # Assuming manager has _get_db_connection
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO historical_items
            (name, quantity_consumed_this_time, original_quantity_string, purchase_date, expiry_date, consumed_date)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (name, quantity_consumed, "N/A", None, None, consumed_date))
        conn.commit()
        conn.close()

    def tearDown(self):
        if os.path.exists(self.test_db_fp):
            os.remove(self.test_db_fp)
        if os.path.exists(self.test_excel_fp):
            os.remove(self.test_excel_fp)

    def _get_db_connection(self):
        conn = sqlite3.connect(self.test_db_fp)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
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

    def _create_dummy_excel_file(self, data_rows_with_header):
        wb = openpyxl.Workbook()
        sheet = wb.active
        for row in data_rows_with_header: # First row should be header
            sheet.append(row)
        wb.save(self.test_excel_fp)
        return self.test_excel_fp


class TestAppInventoryRoutes(BaseAppTest):
    def test_home_page(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Welcome to Your Food Inventory Manager!", response.data)

    def test_current_inventory_view_empty(self):
        response = self.client.get('/inventory/current')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Current inventory is empty.", response.data)

    def test_current_inventory_view_with_items_and_new_fields(self):
        app.manager.add_item_to_list("Test Apple", "5", "2023-01-01", 10, "Produce", "Fruit", 2.0, 10.0)
        response = self.client.get('/inventory/current')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Test Apple", response.data)
        self.assertIn(b"Produce", response.data)
        self.assertIn(b"Fruit", response.data)
        self.assertIn(b"2.00", response.data) # Par Level
        self.assertIn(b"10.00", response.data) # Max Holding

    def test_current_inventory_par_level_highlighting(self):
        app.manager.add_item_to_list("Low Milk", "1", "2023-10-01", 7, par_level=2.0)
        app.manager.add_item_to_list("OK Eggs", "12", "2023-10-01", 21, par_level=12.0)
        app.manager.add_item_to_list("Surplus Bread", "5", "2023-10-01", 5, par_level=2.0)
        app.manager.add_item_to_list("No Par Item", "10", "2023-10-01", 30, par_level=0)

        response = self.client.get('/inventory/current')
        self.assertEqual(response.status_code, 200)
        
        # More robust check for highlighting: find the row and check its class
        # This requires knowing the structure of your HTML or using a parser
        # For simplicity, we'll check if the "Low Milk" item data appears within a row that has the class
        # This is not perfect but better than just checking for class presence anywhere.
        # A proper solution would use an HTML parser like BeautifulSoup.
        data_str = response.data.decode('utf-8')
        self.assertRegex(data_str, r'<tr class=".*?below-par-level.*?".*?>.*?Low Milk.*?</tr>', "Low Milk row should have below-par-level class.")
        self.assertNotRegex(data_str, r'<tr class=".*?below-par-level.*?".*?>.*?OK Eggs.*?</tr>', "OK Eggs row should not have below-par-level class.")
        self.assertNotRegex(data_str, r'<tr class=".*?below-par-level.*?".*?>.*?Surplus Bread.*?</tr>', "Surplus Bread row should not have below-par-level class.")
        self.assertNotRegex(data_str, r'<tr class=".*?below-par-level.*?".*?>.*?No Par Item.*?</tr>', "No Par Item row should not have below-par-level class.")


    def test_add_item_post_success_with_all_fields(self):
        with self.client:
            response = self.client.post('/inventory/add', data={
                'name': 'Test Cherry', 'quantity': '100g',
                'purchase_date': '2023-10-01', 'expiry_days': '5',
                'category': 'Fruit', 'subcategory': 'Stone Fruit',
                'par_level': '2.5', 'max_holding_amount': '5.0',
                'purchase_location': 'Sobeys' # New field
            }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Item 'Test Cherry' added successfully!", response.data)
        item_in_db = self._get_inventory_item_from_db('Test Cherry')
        self.assertIsNotNone(item_in_db)
        self.assertEqual(item_in_db['category'], 'Fruit')
        self.assertEqual(item_in_db['par_level'], 2.5)
        self.assertEqual(item_in_db['purchase_location'], 'Sobeys') # Verify new field

    def test_add_item_post_success_optional_fields_empty(self):
        with self.client:
            response = self.client.post('/inventory/add', data={
                'name': 'Test Dates', 'quantity': '1 box',
                'purchase_date': '2023-11-01', 'expiry_days': '30',
                'category': '', 'subcategory': '', 'par_level': '', 'max_holding_amount': '',
                'purchase_location': '' # Empty purchase location
            }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        item_in_db = self._get_inventory_item_from_db('Test Dates')
        self.assertIsNotNone(item_in_db)
        self.assertIsNone(item_in_db['category'])
        self.assertEqual(item_in_db['par_level'], 0.0)
        self.assertIsNone(item_in_db['purchase_location']) # Should be None if empty

    def test_add_item_post_validation_error_new_fields(self):
        with self.client:
            response_par = self.client.post('/inventory/add', data={
                'name': 'Test Item', 'quantity': '10', 'purchase_date': '2023-01-01', 'expiry_days': '10',
                'par_level': 'abc'
            })
            self.assertEqual(response_par.status_code, 200)
            self.assertIn(b"Par level must be a valid number.", response_par.data)

            response_max = self.client.post('/inventory/add', data={
                'name': 'Test Item 2', 'quantity': '5', 'purchase_date': '2023-01-01', 'expiry_days': '10',
                'max_holding_amount': '-5'
            })
            self.assertEqual(response_max.status_code, 200)
            self.assertIn(b"Max holding amount must be a non-negative number.", response_max.data)

            # Test invalid purchase_location
            response_loc = self.client.post('/inventory/add', data={
                'name': 'Test Item 3', 'quantity': '2', 'purchase_date': '2023-01-01', 'expiry_days': '3',
                'purchase_location': 'Walmart'
            })
            self.assertEqual(response_loc.status_code, 200) # Should re-render the form
            self.assertIn(b"Invalid purchase location. If provided, must be one of: Sobeys, Costco.", response_loc.data)

        self.assertIsNone(self._get_inventory_item_from_db('Test Item'))
        self.assertIsNone(self._get_inventory_item_from_db('Test Item 3'))


    def test_upload_excel_post_success_with_new_fields(self):
        excel_header = ["Name", "Quantity", "Purchase Date", "Expiry Days", "Category", "Subcategory", "Par Level", "Max Holding Amount", "Purchase Location"]
        excel_data_rows = [
            excel_header,
            ["Apples", "10 units", "2023-10-01", 7, "Produce", "Fruit", 5, 20, "Sobeys"],
            ["Bananas", 12, datetime(2023,10,5), 5, "Produce", "Fruit", 6, 24.5, "Costco"],
            ["Milk", "1 gallon", "2023-10-10", 10, "Dairy", "", 1, "", ""], # Empty subcategory, empty max, empty location
            ["Bread", "1 loaf", "2023-10-12", 5, "Bakery", "", 2, 4, "Sobeys"],
        ]
        excel_file_path = self._create_dummy_excel_file(excel_data_rows)
        with open(excel_file_path, 'rb') as fp:
            with self.client:
                response = self.client.post('/inventory/upload_excel',
                                           data={'excel_file': (fp, os.path.basename(excel_file_path))},
                                           content_type='multipart/form-data',
                                           follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Successfully added 4 items from the Excel file.", response.data)
        apples = self._get_inventory_item_from_db("Apples")
        self.assertEqual(apples['category'], "Produce")
        self.assertEqual(apples['par_level'], 5.0)
        self.assertEqual(apples['purchase_location'], "Sobeys")
        bananas = self._get_inventory_item_from_db("Bananas")
        self.assertEqual(bananas['purchase_location'], "Costco")
        milk = self._get_inventory_item_from_db("Milk")
        self.assertIsNone(milk['subcategory'])
        self.assertEqual(milk['max_holding_amount'], 0.0) # Default for empty string
        self.assertIsNone(milk['purchase_location'])


    def test_upload_excel_post_bad_data_in_new_fields(self):
        excel_header = ["Name", "Quantity", "Purchase Date", "Expiry Days", "Category", "Subcategory", "Par Level", "Max Holding Amount", "Purchase Location"]
        excel_data_rows = [
            excel_header,
            ["Good Apples", "5", "2023-10-01", 7, "Produce", "Fruit", 2, 10, "Sobeys"],
            ["Bad Par Grapes", "20", "2023-10-10", 14, "Produce", "Fruit", "abc", 20, "Costco"],
            ["Negative Max Watermelon", "1", "2023-10-11", 20, "Produce", "Fruit", 1, -5, "Sobeys"],
            ["Invalid Location Oranges", "3", "2023-10-12", 10, "Produce", "Fruit", 2, 5, "UnknownStore"],
        ]
        excel_file_path = self._create_dummy_excel_file(excel_data_rows)
        with open(excel_file_path, 'rb') as fp:
            with self.client:
                response = self.client.post('/inventory/upload_excel',
                                           data={'excel_file': (fp, os.path.basename(excel_file_path))},
                                           content_type='multipart/form-data',
                                           follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Successfully added 1 items from the Excel file.", response.data) # Only Good Apples
        self.assertIn(b"3 rows had errors. See details below:", response.data)
        self.assertIn(b"Row 3 ('Bad Par Grapes'): Invalid Par Level 'abc'. Must be a number.", response.data)
        self.assertIn(b"Row 4 ('Negative Max Watermelon'): Max Holding Amount must be non-negative.", response.data)
        self.assertIn(b"Row 5 ('Invalid Location Oranges'): Invalid Purchase Location 'UnknownStore'", response.data)
        self.assertEqual(len(self._get_all_inventory_items_from_db()), 1)

    # --- Tests for new consume_item_view functionality ---
    def test_consume_item_post_item_success(self): # Renamed from test_consume_item_post_success_partial
        app.manager.add_item_to_list("Test Beans", "2 cans", "2023-03-03", 365)
        with self.client:
            response = self.client.post('/inventory/consume', data={
                'consumption_type': 'item',
                'item_name': 'Test Beans',
                'quantity_consumed': '1'
            }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Total consumed: 1.00 of Test Beans.", response.data)
        item_in_db = self._get_inventory_item_from_db('Test Beans')
        self.assertIsNotNone(item_in_db)
        self.assertEqual(item_in_db['quantity'], "1.00 cans")
        self.assertEqual(self._get_historical_item_count_from_db("Test Beans"), 1)

    def test_consume_item_post_recipe_success(self):
        # Setup recipe
        app.recipe_mngr.add_recipe({
            "name": "Simple Snack", 
            "ingredients": [
                {"item_name": "Cracker", "quantity_required": 2.0},
                {"item_name": "Cheese Slice", "quantity_required": 1.0}
            ]
        })
        # Setup inventory
        app.manager.add_item_to_list("Cracker", "10 units", "2023-10-01", 30)
        app.manager.add_item_to_list("Cheese Slice", "5 units", "2023-10-01", 15)

        with self.client:
            response = self.client.post('/inventory/consume', data={
                'consumption_type': 'recipe',
                'recipe_name_to_consume': 'Simple Snack'
            }, follow_redirects=True)
        
        self.assertEqual(response.status_code, 200) # Should redirect to current inventory
        self.assertIn(b"Recipe 'Simple Snack' made successfully! Ingredients have been consumed.", response.data)
        
        cracker = self._get_inventory_item_from_db("Cracker")
        cheese = self._get_inventory_item_from_db("Cheese Slice")
        self.assertAlmostEqual(app.manager._parse_quantity_string(cracker['quantity']), 8.0) # 10 - 2
        self.assertAlmostEqual(app.manager._parse_quantity_string(cheese['quantity']), 4.0)   # 5 - 1
        self.assertEqual(self._get_historical_item_count_from_db("Cracker"), 1)
        self.assertEqual(self._get_historical_item_count_from_db("Cheese Slice"), 1)

    def test_consume_item_post_recipe_insufficient_ingredients(self):
        app.recipe_mngr.add_recipe({
            "name": "Big Meal", 
            "ingredients": [{"item_name": "Steak", "quantity_required": 1.0}]
        })
        app.manager.add_item_to_list("Steak", "0.5 lbs", "2023-10-01", 5) # Not enough

        with self.client:
            response = self.client.post('/inventory/consume', data={
                'consumption_type': 'recipe',
                'recipe_name_to_consume': 'Big Meal'
            }, follow_redirects=True) # Redirects to consume_item_view or current_inventory
        
        self.assertEqual(response.status_code, 200) 
        self.assertIn(b"Cannot make 'Big Meal'. Not enough ingredients currently available.", response.data)
        steak = self._get_inventory_item_from_db("Steak")
        self.assertAlmostEqual(app.manager._parse_quantity_string(steak['quantity']), 0.5) # Unchanged
        self.assertEqual(self._get_historical_item_count_from_db(), 0)

    def test_consume_item_post_invalid_type_or_missing_data(self):
        with self.client:
            # Invalid consumption_type
            response = self.client.post('/inventory/consume', data={'consumption_type': 'wrong_type'}, follow_redirects=True)
            self.assertEqual(response.status_code, 200) # Re-renders consume_item.html
            self.assertIn(b"Invalid consumption type specified.", response.data)

            # Type 'item' but missing item_name
            response = self.client.post('/inventory/consume', data={'consumption_type': 'item', 'quantity_consumed': '1'}, follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            self.assertIn(b"Item name is required for item consumption.", response.data)

            # Type 'recipe' but missing recipe_name
            response = self.client.post('/inventory/consume', data={'consumption_type': 'recipe'}, follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            self.assertIn(b"Recipe name is required for recipe consumption.", response.data)

    # --- Tests for /shopping_list route ---
    def test_shopping_list_route_get_empty(self):
        response = self.client.get('/shopping_list')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"No items on your shopping list", response.data)

    def test_shopping_list_route_with_items(self):
        # Add items that should appear on the list
        # Sobeys item
        self._add_app_inventory_item("Milk", "1 L", self.today_str, 7, par_level=2, purchase_location="Sobeys")
        for i in range(1, 8): self._add_app_historical_consumption("Milk", 1, i) # Consume 1L daily for 7 days
        # Costco item
        self._add_app_inventory_item("Paper Towels", "2 rolls", self.today_str, 100, par_level=6, purchase_location="Costco")
        for i in range(1, 4): self._add_app_historical_consumption("Paper Towels", 1, i*7) # Consume 1 roll weekly for 3 weeks

        response = self.client.get('/shopping_list')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Milk", response.data)
        self.assertIn(b"Paper Towels", response.data)
        self.assertIn(b"Product Name", response.data) # Header
        self.assertIn(b"Recommended Purchase Amount", response.data) # Header

    def test_shopping_list_route_filter_sobeys(self):
        self._add_app_inventory_item("Sobeys Milk", "1 L", self.today_str, 7, par_level=2, purchase_location="Sobeys")
        for i in range(1, 8): self._add_app_historical_consumption("Sobeys Milk", 1, i)
        self._add_app_inventory_item("Costco Paper", "2 rolls", self.today_str, 100, par_level=6, purchase_location="Costco")
        for i in range(1, 4): self._add_app_historical_consumption("Costco Paper", 1, i*7)

        response = self.client.get('/shopping_list?store=Sobeys')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Sobeys Milk", response.data)
        self.assertNotIn(b"Costco Paper", response.data)

    def test_shopping_list_route_filter_costco(self):
        self._add_app_inventory_item("Sobeys Milk", "1 L", self.today_str, 7, par_level=2, purchase_location="Sobeys")
        for i in range(1, 8): self._add_app_historical_consumption("Sobeys Milk", 1, i)
        self._add_app_inventory_item("Costco Paper", "2 rolls", self.today_str, 100, par_level=6, purchase_location="Costco")
        for i in range(1, 4): self._add_app_historical_consumption("Costco Paper", 1, i*7)

        response = self.client.get('/shopping_list?store=Costco')
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(b"Sobeys Milk", response.data)
        self.assertIn(b"Costco Paper", response.data)

    def test_shopping_list_route_search(self):
        self._add_app_inventory_item("Organic Apples", "1 unit", self.today_str, 7, par_level=2, purchase_location="Sobeys")
        self._add_app_historical_consumption("Organic Apples", 7, 1)
        self._add_app_inventory_item("Apple Juice", "1 bottle", self.today_str, 21, par_level=2, purchase_location="Costco")
        self._add_app_historical_consumption("Apple Juice", 21, 1)

        response = self.client.get('/shopping_list?search=Apple')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Organic Apples", response.data)
        self.assertIn(b"Apple Juice", response.data)

        response = self.client.get('/shopping_list?search=Organic')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Organic Apples", response.data)
        self.assertNotIn(b"Apple Juice", response.data)

    def test_shopping_list_route_search_and_store_filter(self):
        self._add_app_inventory_item("Organic Apples", "1 unit", self.today_str, 7, par_level=2, purchase_location="Sobeys")
        self._add_app_historical_consumption("Organic Apples", 7, 1)
        self._add_app_inventory_item("Apple Juice", "1 bottle", self.today_str, 21, par_level=2, purchase_location="Costco")
        self._add_app_historical_consumption("Apple Juice", 21, 1)
        self._add_app_inventory_item("Sobeys Apple Pie", "1", self.today_str, 7, par_level=2, purchase_location="Sobeys")
        self._add_app_historical_consumption("Sobeys Apple Pie", 7,1)


        response = self.client.get('/shopping_list?store=Sobeys&search=Apple')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Organic Apples", response.data)
        self.assertIn(b"Sobeys Apple Pie", response.data)
        self.assertNotIn(b"Apple Juice", response.data)


class TestAppRecipeRoutes(BaseAppTest): # Inherits from BaseAppTest
    # (Recipe route tests remain largely the same as they don't directly interact with these new inventory fields,
    #  but they will benefit from the shared BaseAppTest setup)
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
        self.assertIn(b"Needed:", response.data) 

    def test_add_recipe_post_success(self):
        with self.client:
            response = self.client.post('/recipes/add', data={
                'recipe_name': 'Omelette', 'description': 'Basic omelette.',
                'ingredient_1_name': 'Eggs', 'ingredient_1_quantity': '2',
                'ingredient_2_name': 'Milk', 'ingredient_2_quantity': '0.1'
            }, follow_redirects=True)
        self.assertEqual(response.status_code, 200) 
        self.assertIn(b"Recipe 'Omelette' added successfully!", response.data)
        recipe_in_db = self._get_recipe_from_db("Omelette")
        self.assertIsNotNone(recipe_in_db)
        self.assertEqual(len(recipe_in_db['ingredients']), 2)

    def test_make_recipe_post_success(self):
        app.recipe_mngr.add_recipe({"name": "Toast", "ingredients": [{"item_name": "Bread", "quantity_required": 2.0}]})
        app.manager.add_item_to_list("Bread", "10 slices", "2023-10-01", 7)
        
        with self.client:
            response = self.client.post('/recipes/Toast/make', follow_redirects=True)
        self.assertEqual(response.status_code, 200) 
        self.assertIn(b"Recipe 'Toast' made successfully!", response.data)
        bread_item = self._get_inventory_item_from_db("Bread")
        self.assertIsNotNone(bread_item)
        self.assertEqual(bread_item['quantity'], "8.00 slices") 
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
        self.assertEqual(flakes_item['quantity'], "50g") 
        self.assertEqual(self._get_historical_item_count_from_db(), 0)

if __name__ == '__main__':
    unittest.main(verbosity=2)
