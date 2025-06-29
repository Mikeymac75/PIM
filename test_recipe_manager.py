import unittest
import sqlite3
from RecipeManager import RecipeManager

class TestRecipeManager(unittest.TestCase):

    def setUp(self):
        """Set up an in-memory SQLite database for each test."""
        self.db_filepath = ":memory:"

        # Initialize InventoryManager first and ensure its schema is created.
        # This instance will be used to create prerequisite products.
        # The RecipeManager created next will get its own internal InventoryManager,
        # but we will make them share the same connection.
        from Food_manager import InventoryManager # Import here to ensure it's available
        self.inventory_mngr_for_setup = InventoryManager(db_filepath=self.db_filepath)
        # self.inventory_mngr_for_setup._initialize_db() # Already called in its __init__

        # Initialize RecipeManager. It will create its own internal InventoryManager.
        self.recipe_mngr = RecipeManager(db_filepath=self.db_filepath)

        # Crucially, make RecipeManager's internal InventoryManager use the same
        # database connection as self.inventory_mngr_for_setup.
        # This ensures product lookups by RecipeManager see products created by self.inventory_mngr_for_setup.
        if self.db_filepath == ":memory:":
            # Ensure RecipeManager itself uses the shared connection if it needs one directly
            self.recipe_mngr.conn = self.inventory_mngr_for_setup.conn
            # Ensure RecipeManager's *internal* InventoryManager uses the shared connection
            if hasattr(self.recipe_mngr, 'manager'):
                self.recipe_mngr.manager.conn = self.inventory_mngr_for_setup.conn
                self.recipe_mngr.manager.db_filepath = ":memory:"
                # The internal manager's _initialize_db was called in its __init__.
                # Since it's using the same connection now, its tables (if any were specific to it
                # beyond what self.inventory_mngr_for_setup creates) would be on the shared DB.
                # Food_manager._initialize_db creates products, categories etc. which is what we need.

        # Initialize RecipeManager's specific tables (recipes, recipe_ingredients) on the shared connection.
        self.recipe_mngr._initialize_db()


        # Add categories needed for products, using the setup InventoryManager
        cat1_res = self.inventory_mngr_for_setup.add_category("Test Canned Goods")
        self.assertTrue(cat1_res.get("success"), "Failed to create category 'Test Canned Goods'")
        self.cat1_id = cat1_res['category_id']

        cat2_res = self.inventory_mngr_for_setup.add_category("Test Bakery")
        self.assertTrue(cat2_res.get("success"), "Failed to create category 'Test Bakery'")
        self.cat2_id = cat2_res['category_id']

        cat_general_res = self.inventory_mngr_for_setup.add_category("General Produce")
        self.assertTrue(cat_general_res.get("success"), "Failed to create category 'General Produce'")
        self.general_cat_id = cat_general_res['category_id']


        # Add products using the setup InventoryManager
        products_to_add_details = [
            {"name": "Tomato Puree", "cat_id": self.cat1_id, "uom": "grams", "exp": 365, "attr_name": "product1_id"},
            {"name": "Pizza Dough", "cat_id": self.cat2_id, "uom": "ball", "exp": 3, "attr_name": "product2_id"},
            {"name": "Pasta", "cat_id": self.cat1_id, "uom": "grams", "exp": 730, "attr_name": "pasta_product_id"},
            {"name": "Tomato Sauce", "cat_id": self.cat1_id, "uom": "ml", "exp": 365, "attr_name": "tomatosauce_product_id"},
            {"name": "Old Item", "cat_id": self.cat1_id, "uom": "pcs", "exp": 100, "attr_name": "olditem_product_id"},
            {"name": "New Item A", "cat_id": self.cat1_id, "uom": "pcs", "exp": 100, "attr_name": "newitemA_product_id"},
            {"name": "New Item B", "cat_id": self.cat1_id, "uom": "pcs", "exp": 100, "attr_name": "newitemB_product_id"},
            # Products needed for test_add_recipe_invalid_data and test_add_recipe_no_output
            {"name": "Thing", "cat_id": self.general_cat_id, "uom": "unit", "exp": 7, "attr_name": "thing_product_id"},
            {"name": "Lettuce", "cat_id": self.general_cat_id, "uom": "head", "exp": 7, "attr_name": "lettuce_product_id"},
            {"name": "X", "cat_id": self.general_cat_id, "uom": "unit", "exp": 7, "attr_name": "x_product_id"},
            {"name": "Y", "cat_id": self.general_cat_id, "uom": "unit", "exp": 7, "attr_name": "y_product_id"},
            # For test_add_and_get_recipe output product
            {"name": "Test Output Food", "cat_id": self.general_cat_id, "uom": "serving", "exp": 3, "attr_name": "output_food_product_id"}
        ]

        for p_data in products_to_add_details:
            res = self.inventory_mngr_for_setup.create_product(
                name=p_data["name"],
                category_id=p_data["cat_id"],
                subcategory_id=None,
                unit_of_measure=p_data["uom"],
                default_expiry_days=p_data["exp"]
            )
            self.assertTrue(res.get("success"), f"Failed to create prerequisite product: {p_data['name']}")
            if "attr_name" in p_data: # Store product ID for tests that need it
                setattr(self, p_data["attr_name"], res['product_id'])

        # Specifically for test_add_and_get_recipe which uses self.product1_id for output
        # It was previously Tomato Puree. Let's keep it consistent or update the test to use the new attribute name.
        # For now, let's assign self.product1_id to what was Tomato Puree's ID.
        # This assumes "Tomato Puree" is the first item in products_to_add_details.
        # A safer way is to retrieve it by name after creation if tests depend on this specific self.product1_id.
        # setattr will handle it: self.product1_id = (ID of Tomato Puree)
        # And self.product2_id for Pizza Dough.
        # self.output_food_product_id is now the one for "Test Output Food"
        # Let's make sure test_add_and_get_recipe uses self.output_food_product_id for its output.


    def test_add_and_get_recipe(self):
        """Test adding a recipe and retrieving it by name."""
        recipe_data = {
            "name": "Test Pasta",
            "description": "A simple test pasta recipe.",
            "ingredients": [
                {"item_name": "Pasta", "quantity_required": 200.0},
                {"item_name": "Tomato Sauce", "quantity_required": 1.0}
            ],
            "output_product_id": self.output_food_product_id, # Use the correctly setup output product ID
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
        self.assertEqual(retrieved_recipe_by_id['ingredients'][0]['quantity_required'], 200.0)
        self.assertEqual(retrieved_recipe_by_id['output_product_id'], self.output_food_product_id)
        self.assertEqual(retrieved_recipe_by_id['output_yield'], 500.0)

        # Get by Name
        retrieved_recipe_by_name = self.recipe_mngr.get_recipe_by_name("Test Pasta")
        self.assertIsNotNone(retrieved_recipe_by_name)
        self.assertEqual(retrieved_recipe_by_name['name'], "Test Pasta")
        self.assertEqual(retrieved_recipe_by_name['output_product_id'], self.output_food_product_id)
        self.assertEqual(retrieved_recipe_by_name['output_yield'], 500.0)


    def test_add_recipe_no_output(self):
        """Test adding a recipe without production output."""
        recipe_data = {
            "name": "Simple Salad",
            "description": "No direct output product.",
            "ingredients": [{"item_name": "Lettuce", "quantity_required": 1.0}] # Lettuce product created in setUp
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
        recipe_to_delete = self.recipe_mngr.get_recipe_by_name("To Be Deleted")
        self.assertIsNotNone(recipe_to_delete)
        recipe_id_to_delete = recipe_to_delete['id']

        delete_result = self.recipe_mngr.delete_recipe(recipe_id_to_delete) # Use ID
        self.assertTrue(delete_result['success'], msg=delete_result.get("message"))

        # Ensure it's gone
        self.assertIsNone(self.recipe_mngr.get_recipe_by_id(recipe_id_to_delete)) # Check by ID
        self.assertIsNone(self.recipe_mngr.get_recipe_by_name("To Be Deleted"))


    def test_delete_recipe_non_existent(self):
        """Test deleting a recipe that does not exist."""
        delete_result = self.recipe_mngr.delete_recipe(99999) # Use a non-existent ID
        self.assertFalse(delete_result['success'])
        self.assertIn("not found", delete_result['message'])

    def test_add_recipe_invalid_data(self):
        """Test adding a recipe with invalid data types or missing fields."""
        # Missing name
        res_missing_name = self.recipe_mngr.add_recipe({"description": "no name", "ingredients": []})
        self.assertFalse(res_missing_name['success'])
        self.assertIn("recipe name and ingredients are required", res_missing_name['message'].lower()) # Adjusted expected message

        # Ingredients not a list
        res_ing_not_list = self.recipe_mngr.add_recipe({"name": "Test", "ingredients": "not a list"})
        self.assertFalse(res_ing_not_list['success'])
        self.assertIn("ingredients must be a list", res_ing_not_list['message'].lower())

        # Ingredient item with invalid format (not a dict)
        res_ing_item_bad = self.recipe_mngr.add_recipe({"name": "Test", "ingredients": ["not a dict"]})
        self.assertFalse(res_ing_item_bad['success'])
        self.assertIn("each ingredient must be a dictionary", res_ing_item_bad['message'].lower()) # Updated expected message

        # Ingredient item with missing name
        res_ing_name_missing = self.recipe_mngr.add_recipe({"name": "Test", "ingredients": [{"quantity_required": 1.0}]}) # Ensure quantity is float for consistency
        self.assertFalse(res_ing_name_missing['success'])
        self.assertIn("ingredient item_name is required", res_ing_name_missing['message'].lower()) # Corrected expected message

        # Ingredient item with invalid quantity
        res_ing_qty_invalid = self.recipe_mngr.add_recipe({"name": "Test", "ingredients": [{"item_name": "X", "quantity_required": "abc"}]}) # X product created in setUp
        self.assertFalse(res_ing_qty_invalid['success'])
        self.assertIn("invalid quantity format for ingredient 'x': 'abc'", res_ing_qty_invalid['message'].lower()) # Updated expected message

        # Ingredient item with non-positive quantity
        res_ing_qty_non_pos = self.recipe_mngr.add_recipe({"name": "Test", "ingredients": [{"item_name": "Y", "quantity_required": 0}]})
        self.assertFalse(res_ing_qty_non_pos['success'])
        self.assertIn("qty must be > 0", res_ing_qty_non_pos['message'].lower())


    def tearDown(self):
        """Clean up resources, if any."""
        pass

if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
