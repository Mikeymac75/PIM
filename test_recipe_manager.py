import unittest
import sqlite3
from RecipeManager import RecipeManager

class TestRecipeManager(unittest.TestCase):

    def setUp(self):
        """Set up an in-memory SQLite database for each test."""
        # We need InventoryManager to create products for output_product_id
        # Since they share the DB path, initializing InventoryManager first ensures tables are set up.
        # However, RecipeManager's _initialize_db also tries to create tables if not exist.
        # For testing, it's cleaner to manage the DB connection explicitly if needed,
        # but RecipeManager(":memory:") should work fine.
        # Let's ensure products table exists by a direct call or relying on its init.
        # For these tests, we'll assume products table can be populated by RecipeManager's _get_db_connection
        # for simplicity if we need to insert dummy products directly.
        # A better approach for interdependent managers would be a shared TestDBManager or fixture.

        self.db_filepath = ":memory:"
        self.recipe_mngr = RecipeManager(db_filepath=self.db_filepath)

        # Manually add some products for testing output_product_id
        # This requires access to the same DB connection and cursor.
        conn = sqlite3.connect(self.db_filepath)
        cursor = conn.cursor()
        # Ensure products table exists (it should due to RecipeManager's _initialize_db calling InventoryManager's schema parts)
        # Or, more directly, ensure products table creation if not relying on InventoryManager's full init.
        # For this test, we rely on the schema being initialized by RecipeManager,
        # which should include products table if InventoryManager parts were correctly added to its init.
        # Let's assume `products` table is available.
        try:
            cursor.execute("INSERT INTO products (name, category, unit_of_measure, default_expiry_days) VALUES (?, ?, ?, ?)",
                           ("Tomato Puree", "Canned Goods", "grams", 365))
            self.product1_id = cursor.lastrowid
            cursor.execute("INSERT INTO products (name, category, unit_of_measure, default_expiry_days) VALUES (?, ?, ?, ?)",
                           ("Pizza Dough", "Bakery", "ball", 3))
            self.product2_id = cursor.lastrowid
            conn.commit()
        except sqlite3.Error as e:
            # This might happen if products table isn't created by RecipeManager's init path.
            # This indicates a potential issue in how _initialize_db is shared or structured if it fails.
            # For now, we'll proceed assuming it works or these tests will reveal the problem.
            print(f"Error setting up products for recipe tests: {e} - check DB initialization in RecipeManager")
            pass # Allow tests to proceed and potentially fail if product IDs are crucial and missing
        finally:
            conn.close()


    def test_add_and_get_recipe(self):
        """Test adding a recipe and retrieving it by name."""
        recipe_data = {
            "name": "Test Pasta",
            "description": "A simple test pasta recipe.",
            "ingredients": [
                {"item_name": "Pasta", "quantity_required": 200.0}, # Assuming quantity_required based on previous app.py
                {"item_name": "Tomato Sauce", "quantity_required": 1.0}
            ],
            "output_product_id": self.product1_id,
            "output_yield": 500.0
        }
        add_result = self.recipe_mngr.add_recipe(recipe_data)
        self.assertTrue(add_result['success'], msg=add_result.get("message"))
        recipe_id = add_result['recipe_id']

        # Get by ID
        retrieved_recipe_by_id = self.recipe_mngr.get_recipe_by_id(recipe_id)
        self.assertIsNotNone(retrieved_recipe_by_id)
        self.assertEqual(retrieved_recipe_by_id['name'], "Test Pasta")
        self.assertEqual(retrieved_recipe_by_id['description'], "A simple test pasta recipe.")
        self.assertEqual(len(retrieved_recipe_by_id['ingredients']), 2)
        self.assertEqual(retrieved_recipe_by_id['ingredients'][0]['item_name'], "Pasta")
        # Assuming 'quantity_required' is the key stored for ingredients based on manager logic
        self.assertEqual(float(retrieved_recipe_by_id['ingredients'][0]['quantity']), 200.0)
        self.assertEqual(retrieved_recipe_by_id['output_product_id'], self.product1_id)
        self.assertEqual(retrieved_recipe_by_id['output_yield'], 500.0)

        # Get by Name
        retrieved_recipe_by_name = self.recipe_mngr.get_recipe_by_name("Test Pasta")
        self.assertIsNotNone(retrieved_recipe_by_name)
        self.assertEqual(retrieved_recipe_by_name['name'], "Test Pasta")
        self.assertEqual(retrieved_recipe_by_name['output_product_id'], self.product1_id)
        self.assertEqual(retrieved_recipe_by_name['output_yield'], 500.0)


    def test_add_recipe_no_output(self):
        """Test adding a recipe without production output."""
        recipe_data = {
            "name": "Simple Salad",
            "description": "No direct output product.",
            "ingredients": [{"item_name": "Lettuce", "quantity_required": 1.0}]
            # No output_product_id or output_yield
        }
        add_result = self.recipe_mngr.add_recipe(recipe_data)
        self.assertTrue(add_result['success'], msg=add_result.get("message"))

        retrieved_recipe = self.recipe_mngr.get_recipe_by_name("Simple Salad")
        self.assertIsNotNone(retrieved_recipe)
        self.assertIsNone(retrieved_recipe['output_product_id'])
        self.assertIsNone(retrieved_recipe['output_yield'])


    def test_add_recipe_duplicate_name(self):
        """Test adding a recipe with a name that already exists."""
        recipe_data = {"name": "Unique Recipe", "ingredients": [{"item_name": "Thing", "quantity_required": 1}]}
        self.recipe_mngr.add_recipe(recipe_data)

        duplicate_recipe_data = {"name": "Unique Recipe", "description": "Another description", "ingredients": []}
        add_result = self.recipe_mngr.add_recipe(duplicate_recipe_data)
        self.assertFalse(add_result['success'])
        self.assertIn("already exists", add_result['message'])

    def test_get_all_recipes(self):
        """Test retrieving all added recipes."""
        self.recipe_mngr.add_recipe({"name": "Recipe One", "ingredients": []})
        self.recipe_mngr.add_recipe({"name": "Recipe Two", "ingredients": []})

        all_recipes = self.recipe_mngr.get_all_recipes(page=None, per_page=None) # Fetch all
        self.assertEqual(len(all_recipes), 2)
        recipe_names = [r['name'] for r in all_recipes]
        self.assertIn("Recipe One", recipe_names)
        self.assertIn("Recipe Two", recipe_names)
        # Check if output fields are present (should be None if not set)
        self.assertIsNone(all_recipes[0].get('output_product_id'))
        self.assertIsNone(all_recipes[0].get('output_yield'))


    def test_update_recipe_with_output(self):
        """Test updating an existing recipe's details, ingredients, and output."""
        original_data = {
            "name": "Old Recipe",
            "description": "Old description",
            "ingredients": [{"item_name": "Old Item", "quantity_required": 1.0}]
            # No output initially
        }
        add_result = self.recipe_mngr.add_recipe(original_data)
        self.assertTrue(add_result['success'])
        recipe_id = add_result['recipe_id']


        updated_data = {
            "name": "New Recipe Name",
            "description": "New description",
            "ingredients": [
                {"item_name": "New Item A", "quantity_required": 2.5},
                {"item_name": "New Item B", "quantity_required": 0.5}
            ],
            "output_product_id": self.product2_id, # Basil
            "output_yield": 2.0
        }
        # update_recipe in RecipeManager uses recipe_id as first arg
        update_result = self.recipe_mngr.update_recipe(recipe_id, updated_data)
        self.assertTrue(update_result['success'], msg=update_result.get("message"))

        retrieved_recipe = self.recipe_mngr.get_recipe_by_id(recipe_id)
        self.assertIsNotNone(retrieved_recipe)
        self.assertEqual(retrieved_recipe['name'], "New Recipe Name")
        self.assertEqual(retrieved_recipe['description'], "New description")
        self.assertEqual(len(retrieved_recipe['ingredients']), 2)
        self.assertEqual(retrieved_recipe['ingredients'][0]['item_name'], "New Item A")
        self.assertEqual(retrieved_recipe['output_product_id'], self.product2_id)
        self.assertEqual(retrieved_recipe['output_yield'], 2.0)

        # Test updating to remove output
        update_remove_output_data = {
            "output_product_id": None,
            "output_yield": None
        }
        update_result_remove = self.recipe_mngr.update_recipe(recipe_id, update_remove_output_data)
        self.assertTrue(update_result_remove['success'])
        retrieved_no_output = self.recipe_mngr.get_recipe_by_id(recipe_id)
        self.assertIsNone(retrieved_no_output['output_product_id'])
        self.assertIsNone(retrieved_no_output['output_yield'])


    def test_update_recipe_non_existent(self):
        """Test updating a recipe that does not exist."""
        update_data = {"name": "Non Existent Updated", "ingredients": []}
        # Assuming update_recipe takes recipe_id (int) not name
        update_result = self.recipe_mngr.update_recipe(999, update_data) # Use a non-existent ID
        self.assertFalse(update_result['success'])
        # Message might vary, e.g. "Recipe ID 999 not found" or generic update error
        # For now, just check success is False. If rowcount is checked, "not found" is good.
        # self.assertIn("not found", update_result['message']) # This depends on update_recipe's error message detail


    def test_delete_recipe(self):
        """Test deleting a recipe."""
        recipe_data = {"name": "To Be Deleted", "ingredients": []}
        self.recipe_mngr.add_recipe(recipe_data)

        # Ensure it's there
        self.assertIsNotNone(self.recipe_mngr.get_recipe_by_name("To Be Deleted"))

        delete_result = self.recipe_mngr.delete_recipe("To Be Deleted")
        self.assertTrue(delete_result['success'], msg=delete_result.get("message"))

        # Ensure it's gone
        self.assertIsNone(self.recipe_mngr.get_recipe_by_name("To Be Deleted"))

    def test_delete_recipe_non_existent(self):
        """Test deleting a recipe that does not exist."""
        delete_result = self.recipe_mngr.delete_recipe("I Do Not Exist")
        self.assertFalse(delete_result['success'])
        self.assertIn("not found", delete_result['message'])

    def test_add_recipe_invalid_data(self):
        """Test adding a recipe with invalid data types or missing fields."""
        # Missing name
        res_missing_name = self.recipe_mngr.add_recipe({"description": "no name", "ingredients": []})
        self.assertFalse(res_missing_name['success'])
        self.assertIn("name is required", res_missing_name['message'].lower())

        # Ingredients not a list
        res_ing_not_list = self.recipe_mngr.add_recipe({"name": "Test", "ingredients": "not a list"})
        self.assertFalse(res_ing_not_list['success'])
        self.assertIn("ingredients must be a list", res_ing_not_list['message'].lower())

        # Ingredient item with invalid format (not a dict)
        res_ing_item_bad = self.recipe_mngr.add_recipe({"name": "Test", "ingredients": ["not a dict"]})
        self.assertFalse(res_ing_item_bad['success'])
        self.assertIn("invalid format", res_ing_item_bad['message'].lower())

        # Ingredient item with missing name
        res_ing_name_missing = self.recipe_mngr.add_recipe({"name": "Test", "ingredients": [{"quantity_required": 1}]})
        self.assertFalse(res_ing_name_missing['success'])
        self.assertIn("name missing", res_ing_name_missing['message'].lower())

        # Ingredient item with invalid quantity
        res_ing_qty_invalid = self.recipe_mngr.add_recipe({"name": "Test", "ingredients": [{"item_name": "X", "quantity_required": "abc"}]})
        self.assertFalse(res_ing_qty_invalid['success'])
        self.assertIn("qty invalid", res_ing_qty_invalid['message'].lower())

        # Ingredient item with non-positive quantity
        res_ing_qty_non_pos = self.recipe_mngr.add_recipe({"name": "Test", "ingredients": [{"item_name": "Y", "quantity_required": 0}]})
        self.assertFalse(res_ing_qty_non_pos['success'])
        self.assertIn("qty must be > 0", res_ing_qty_non_pos['message'].lower())


    def tearDown(self):
        """Clean up resources, if any."""
        pass

if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
