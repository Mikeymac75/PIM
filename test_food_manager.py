import unittest
import os
import sqlite3 # Added for SQLite testing
import csv # Still needed for CSV export tests
from datetime import date, timedelta

# Import the refactored manager classes
from Food_manager import InventoryManager
from recipe_manager import RecipeManager

# --- Test File Paths for CSV exports (still relevant) ---
TEST_CSV_PREFIX = "test_export_food_manager"
TEST_CURRENT_CSV = f"{TEST_CSV_PREFIX}_current.csv"
TEST_HISTORICAL_CSV = f"{TEST_CSV_PREFIX}_historical.csv"
TEST_PROJECTIONS_CSV = f"{TEST_CSV_PREFIX}_projections.csv"

class TestInventoryManager(unittest.TestCase): # Renamed from TestFoodManager
    def setUp(self):
        self.test_db_file = 'test_inventory_manager.db'
        if os.path.exists(self.test_db_file):
            os.remove(self.test_db_file)
        
        self.manager = InventoryManager(db_filepath=self.test_db_file)
        # _initialize_db is called in InventoryManager's __init__
        
        # Clean up CSV files that might be created by some tests
        self.cleanup_csv_files()

    def tearDown(self):
        if os.path.exists(self.test_db_file):
            os.remove(self.test_db_file)
        self.cleanup_csv_files()

    def cleanup_csv_files(self):
        files_to_delete = [TEST_CURRENT_CSV, TEST_HISTORICAL_CSV, TEST_PROJECTIONS_CSV]
        for f_path in files_to_delete:
            if os.path.exists(f_path):
                os.remove(f_path)

    def _get_db_connection(self):
        conn = sqlite3.connect(self.test_db_file)
        conn.row_factory = sqlite3.Row
        return conn

    def test_add_item_to_list_db(self):
        result = self.manager.add_item_to_list("DB Apples", "10 units", "2023-01-01", 7)
        self.assertTrue(result.get("success"))
        
        with self._get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM inventory_items WHERE name = ?", ("DB Apples",))
            row = cursor.fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row['name'], "DB Apples")
            self.assertEqual(row['quantity'], "10 units")
            self.assertEqual(row['purchase_date'], "2023-01-01")
            self.assertEqual(row['expiry_date'], "2023-01-08")
            self.assertEqual(row['original_quantity_string'], "10 units")
            # Check default values for new fields
            self.assertIsNone(row['category']) # Default from add_item_to_list if not provided
            self.assertIsNone(row['subcategory'])
            self.assertEqual(row['par_level'], 0)
            self.assertEqual(row['max_holding_amount'], 0)

        # Test adding with new fields
        result_full = self.manager.add_item_to_list(
            "DB Pears", "5 kg", "2023-02-01", 10,
            category="Produce", subcategory="Fruit", par_level=2.0, max_holding_amount=10.0
        )
        self.assertTrue(result_full.get("success"))
        with self._get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM inventory_items WHERE name = ?", ("DB Pears",))
            row_full = cursor.fetchone()
            self.assertIsNotNone(row_full)
            self.assertEqual(row_full['category'], "Produce")
            self.assertEqual(row_full['subcategory'], "Fruit")
            self.assertEqual(row_full['par_level'], 2.0)
            self.assertEqual(row_full['max_holding_amount'], 10.0)


    def test_get_current_inventory_db(self):
        self.manager.add_item_to_list("Item1", "1", "2023-01-01", 5, "Cat1", "Sub1", 1, 5)
        self.manager.add_item_to_list("Item2", "2", "2023-01-03", 2) # Defaults for new fields
        
        items = self.manager.get_current_inventory()
        self.assertEqual(len(items), 2)
        
        # Item2 expires sooner
        self.assertEqual(items[0]['name'], "Item2") 
        self.assertIsNone(items[0]['category']) # Default
        self.assertEqual(items[0]['par_level'], 0) # Default

        self.assertEqual(items[1]['name'], "Item1")
        self.assertEqual(items[1]['category'], "Cat1")
        self.assertEqual(items[1]['subcategory'], "Sub1")
        self.assertEqual(items[1]['par_level'], 1)
        self.assertEqual(items[1]['max_holding_amount'], 5)
        self.assertIsInstance(items[0]['purchase_date'], date)

    def test_get_total_item_quantity_db(self):
        self.manager.add_item_to_list("Milk", "1 gallon", "2023-01-01", 7)
        self.manager.add_item_to_list("Milk", "0.5 gallon", "2023-01-05", 7)
        self.manager.add_item_to_list("Juice", "2 liters", "2023-01-03", 10)
        
        # "1 gallon" parses to 1.0, "0.5 gallon" to 0.5
        self.assertAlmostEqual(self.manager.get_total_item_quantity("Milk"), 1.5)
        self.assertAlmostEqual(self.manager.get_total_item_quantity("Juice"), 2.0)
        self.assertAlmostEqual(self.manager.get_total_item_quantity("NonExistent"), 0.0)

    def test_consume_item_full_db(self):
        add_result = self.manager.add_item_to_list("DB Eggs", "12 units", "2023-01-01", 21)
        self.assertTrue(add_result.get("success"))
        
        consume_result = self.manager.consume_item("DB Eggs", 12.0)
        self.assertTrue(consume_result.get("success"))
        
        current_items = self.manager.get_current_inventory()
        self.assertEqual(len(current_items), 0)
        
        historical_items = self.manager.get_historical_inventory()
        self.assertEqual(len(historical_items), 1)
        self.assertEqual(historical_items[0]['name'], "DB Eggs")
        self.assertEqual(historical_items[0]['quantity_consumed_this_time'], 12.0)
        self.assertEqual(historical_items[0]['consumed_date'], date.today())
        self.assertEqual(historical_items[0]['original_quantity_string'], "12 units")

    def test_consume_item_partial_db(self):
        self.manager.add_item_to_list("DB Flour", "2 kg", "2023-02-01", 365)
        consume_result = self.manager.consume_item("DB Flour", 0.5)
        self.assertTrue(consume_result.get("success"))

        current_items = self.manager.get_current_inventory()
        self.assertEqual(len(current_items), 1)
        # The _parse_quantity_string and consume_item logic for string quantities can be tricky.
        # If "2 kg" -> 2.0, then 2.0 - 0.5 = 1.5. The string representation becomes "1.5 kg".
        self.assertEqual(current_items[0]['name'], "DB Flour")
        self.assertEqual(current_items[0]['quantity'], "1.50 kg") # Based on current consume_item string logic
        
        historical_items = self.manager.get_historical_inventory()
        self.assertEqual(len(historical_items), 1)
        self.assertEqual(historical_items[0]['quantity_consumed_this_time'], 0.5)

    def test_check_for_expiring_items_db(self):
        today_str = date.today().isoformat()
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        in_2_days = (date.today() + timedelta(days=2)).isoformat()
        in_5_days = (date.today() + timedelta(days=5)).isoformat()

        self.manager.add_item_to_list("Expired Bread", "1 loaf", yesterday, 0) # Expired yesterday
        self.manager.add_item_to_list("Fresh Milk", "1 gallon", today_str, 2)  # Expires in 2 days
        self.manager.add_item_to_list("Yogurt", "6 pack", today_str, 5)      # Expires in 5 days

        expiring_soon = self.manager.check_for_expiring_items(days_threshold=3) # Expired or expiring in <=3 days
        
        self.assertEqual(len(expiring_soon), 2)
        expiring_names = [item['name'] for item in expiring_soon]
        self.assertIn("Expired Bread", expiring_names)
        self.assertIn("Fresh Milk", expiring_names)
        self.assertNotIn("Yogurt", expiring_names)

    def test_project_demand_db(self):
        # Add current stock
        self.manager.add_item_to_list("DB Cereal", "500g", date.today().isoformat(), 30)
        
        # Add historical consumption for DB Cereal
        with self._get_db_connection() as conn:
            cursor = conn.cursor()
            for i in range(5): # Consumed 50g, 5 times over the last 10 days
                consumed_date = (date.today() - timedelta(days=i*2)).isoformat()
                cursor.execute('''
                    INSERT INTO historical_items 
                    (name, quantity_consumed_this_time, consumed_date, original_quantity_string, purchase_date, expiry_date) 
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', ("DB Cereal", 50.0, consumed_date, "500g", "2023-01-01", "2023-12-31")) # Dummy P/E dates
            conn.commit()

        projection = self.manager.project_demand("DB Cereal", lookback_days=10, projection_days=7)
        
        # Total consumed in last 10 days = 5 * 50g = 250g
        # Avg daily = 250 / 10 = 25g/day
        # Current stock = 500g (from "500g" string)
        # Days to depletion = 500 / 25 = 20 days
        # Projected need for 7 days = 25 * 7 = 175g
        self.assertAlmostEqual(projection["avg_daily_consumption"], 25.0)
        self.assertAlmostEqual(projection["current_stock"], 500.0) # _parse_quantity_string("500g") -> 500.0
        self.assertTrue("20.0 days" in projection["days_to_depletion"])
        self.assertAlmostEqual(projection["projected_need"], 175.0)

    def test_export_data_to_csv_db(self):
        self.manager.add_item_to_list("DB Oranges", "5 units", "2023-02-01", 10)
        # Add a historical item directly for simplicity in this test
        with self._get_db_connection() as conn:
            conn.execute('''
                INSERT INTO historical_items (name, quantity_consumed_this_time, consumed_date, original_quantity_string) 
                VALUES (?, ?, ?, ?)
            ''', ("DB Juice", 1.0, date.today().isoformat(), "1 liter"))
            conn.commit()

        self.manager.export_data_to_csv(filename_prefix=TEST_CSV_PREFIX)

        self.assertTrue(os.path.exists(TEST_CURRENT_CSV))
        self.assertTrue(os.path.exists(TEST_HISTORICAL_CSV))
        self.assertTrue(os.path.exists(TEST_PROJECTIONS_CSV)) # For Oranges and Juice

        with open(TEST_CURRENT_CSV, 'r', newline='') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["name"], "DB Oranges")

# --- Tests for RecipeManager (SQLite) ---
TEST_RECIPES_DB_FILE = "test_recipe_manager.db"

class TestRecipeManager(unittest.TestCase):
    def setUp(self):
        self.test_db_file = TEST_RECIPES_DB_FILE
        if os.path.exists(self.test_db_file):
            os.remove(self.test_db_file)
        self.recipe_mngr = RecipeManager(db_filepath=self.test_db_file)
        # _initialize_db called in RecipeManager's __init__

    def tearDown(self):
        if os.path.exists(self.test_db_file):
            os.remove(self.test_db_file)

    def _get_db_connection(self): # Helper for recipe tests
        conn = sqlite3.connect(self.test_db_file)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def test_add_recipe_db(self):
        recipe_data = {
            "name": "DB Test Pasta",
            "description": "A simple DB test pasta.",
            "ingredients": [{"item_name": "DB Pasta", "quantity_required": 100.0}]
        }
        result = self.recipe_mngr.add_recipe(recipe_data)
        self.assertTrue(result["success"], result.get("message"))
        
        with self._get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM recipes WHERE name = ?", ("DB Test Pasta",))
            recipe_row = cursor.fetchone()
            self.assertIsNotNone(recipe_row)
            self.assertEqual(recipe_row['description'], "A simple DB test pasta.")
            
            cursor.execute("SELECT * FROM recipe_ingredients WHERE recipe_id = ?", (recipe_row['id'],))
            ing_row = cursor.fetchone()
            self.assertIsNotNone(ing_row)
            self.assertEqual(ing_row['item_name'], "DB Pasta")
            self.assertEqual(ing_row['quantity_required'], 100.0)

    def test_add_recipe_duplicate_name_db(self):
        recipe_data = {"name": "DB Duplicate Recipe", "ingredients": [{"item_name": "Item1", "quantity_required": 1.0}]}
        self.recipe_mngr.add_recipe(recipe_data)
        result = self.recipe_mngr.add_recipe(recipe_data)
        self.assertFalse(result["success"])
        self.assertTrue("already exists" in result["message"])

    def test_get_all_recipes_db(self):
        self.recipe_mngr.add_recipe({"name": "DB Recipe 1", "ingredients": [{"item_name": "Ing1", "quantity_required": 1.0}]})
        self.recipe_mngr.add_recipe({"name": "DB Recipe 2", "ingredients": [{"item_name": "Ing2", "quantity_required": 2.0}]})
        recipes = self.recipe_mngr.get_all_recipes()
        self.assertEqual(len(recipes), 2)
        self.assertEqual(recipes[0]['name'], "DB Recipe 1") # Default order is by name ASC

    def test_get_recipe_by_name_db(self):
        self.recipe_mngr.add_recipe({"name": "DB Specific Recipe", "description":"Desc", "ingredients": [{"item_name": "IngX", "quantity_required": 3.0}]})
        recipe = self.recipe_mngr.get_recipe_by_name("DB Specific Recipe")
        self.assertIsNotNone(recipe)
        self.assertEqual(recipe['description'], "Desc")
        self.assertEqual(len(recipe['ingredients']), 1)
        self.assertEqual(recipe['ingredients'][0]['item_name'], "IngX")

    def test_delete_recipe_db(self):
        self.recipe_mngr.add_recipe({"name": "DB ToDelete", "ingredients": []})
        recipe_id = self.recipe_mngr.get_recipe_by_name("DB ToDelete")['id'] # Get id for checking ingredients
        
        # Add a dummy ingredient to test cascade delete
        with self._get_db_connection() as conn:
            conn.execute("INSERT INTO recipe_ingredients (recipe_id, item_name, quantity_required) VALUES (?,?,?)",
                         (recipe_id, "DummyIng", 1.0))
            conn.commit()

        result = self.recipe_mngr.delete_recipe("DB ToDelete")
        self.assertTrue(result["success"])
        self.assertIsNone(self.recipe_mngr.get_recipe_by_name("DB ToDelete"))
        
        # Verify ingredients were cascade deleted
        with self._get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM recipe_ingredients WHERE recipe_id = ?", (recipe_id,))
            self.assertIsNone(cursor.fetchone())

    def test_update_recipe_db(self):
        self.recipe_mngr.add_recipe({"name": "DB Original", "description": "Orig Desc", "ingredients": [{"item_name": "OldIng", "quantity_required": 1.0}]})
        update_data = {
            "name": "DB Updated", 
            "description": "New Desc", 
            "ingredients": [{"item_name": "NewIng", "quantity_required": 2.0}, {"item_name": "AnotherIng", "quantity_required": 3.0}]
        }
        result = self.recipe_mngr.update_recipe("DB Original", update_data)
        self.assertTrue(result["success"])
        
        updated = self.recipe_mngr.get_recipe_by_name("DB Updated")
        self.assertIsNotNone(updated)
        self.assertEqual(updated['description'], "New Desc")
        self.assertEqual(len(updated['ingredients']), 2)
        self.assertEqual(updated['ingredients'][0]['item_name'], "NewIng")
        
        self.assertIsNone(self.recipe_mngr.get_recipe_by_name("DB Original")) # Check old name is gone

if __name__ == '__main__':
    unittest.main(verbosity=2)
