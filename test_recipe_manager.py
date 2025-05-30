import unittest
import sqlite3
from recipe_manager import RecipeManager

class TestRecipeManager(unittest.TestCase):

    def setUp(self):
        """Set up an in-memory SQLite database for each test."""
        self.recipe_mngr = RecipeManager(db_filepath=":memory:")

    def test_add_and_get_recipe(self):
        """Test adding a recipe and retrieving it by name."""
        recipe_data = {
            "name": "Test Pasta",
            "description": "A simple test pasta recipe.",
            "ingredients": [
                {"item_name": "Pasta", "quantity_required": 200.0},
                {"item_name": "Tomato Sauce", "quantity_required": 1.0}
            ]
        }
        add_result = self.recipe_mngr.add_recipe(recipe_data)
        self.assertTrue(add_result['success'], msg=add_result.get("message"))

        retrieved_recipe = self.recipe_mngr.get_recipe_by_name("Test Pasta")
        self.assertIsNotNone(retrieved_recipe)
        self.assertEqual(retrieved_recipe['name'], "Test Pasta")
        self.assertEqual(retrieved_recipe['description'], "A simple test pasta recipe.")
        self.assertEqual(len(retrieved_recipe['ingredients']), 2)
        self.assertEqual(retrieved_recipe['ingredients'][0]['item_name'], "Pasta")
        self.assertEqual(retrieved_recipe['ingredients'][0]['quantity_required'], 200.0)

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

        all_recipes = self.recipe_mngr.get_all_recipes()
        self.assertEqual(len(all_recipes), 2)
        recipe_names = [r['name'] for r in all_recipes]
        self.assertIn("Recipe One", recipe_names)
        self.assertIn("Recipe Two", recipe_names)

    def test_update_recipe(self):
        """Test updating an existing recipe's details and ingredients."""
        original_data = {
            "name": "Old Recipe",
            "description": "Old description",
            "ingredients": [{"item_name": "Old Item", "quantity_required": 1.0}]
        }
        self.recipe_mngr.add_recipe(original_data)

        updated_data = {
            "name": "New Recipe Name", # Name change
            "description": "New description",
            "ingredients": [
                {"item_name": "New Item A", "quantity_required": 2.5},
                {"item_name": "New Item B", "quantity_required": 0.5}
            ]
        }
        update_result = self.recipe_mngr.update_recipe("Old Recipe", updated_data)
        self.assertTrue(update_result['success'], msg=update_result.get("message"))

        # Verify old name doesn't exist
        self.assertIsNone(self.recipe_mngr.get_recipe_by_name("Old Recipe"))

        # Verify new recipe details
        retrieved_recipe = self.recipe_mngr.get_recipe_by_name("New Recipe Name")
        self.assertIsNotNone(retrieved_recipe)
        self.assertEqual(retrieved_recipe['description'], "New description")
        self.assertEqual(len(retrieved_recipe['ingredients']), 2)
        self.assertEqual(retrieved_recipe['ingredients'][0]['item_name'], "New Item A")

    def test_update_recipe_non_existent(self):
        """Test updating a recipe that does not exist."""
        update_data = {"name": "Non Existent Updated", "ingredients": []}
        update_result = self.recipe_mngr.update_recipe("Non Existent Original", update_data)
        self.assertFalse(update_result['success'])
        self.assertIn("not found", update_result['message'])


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
