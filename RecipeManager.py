import sqlite3
from datetime import date # Keep for potential future use

class RecipeManager:
    def __init__(self, db_filepath="inventory.db"): # Assuming it uses the same DB
        self.db_filepath = db_filepath
        self.conn = None  # For persistent in-memory connection
        if self.db_filepath == ":memory:":
            self.conn = sqlite3.connect(":memory:")
            self.conn.row_factory = sqlite3.Row
        self._initialize_db()

    def _get_db_connection(self):
        """Establishes and returns a database connection."""
        if self.conn and self.db_filepath == ":memory:":
            return self.conn
        conn = sqlite3.connect(self.db_filepath)
        conn.row_factory = sqlite3.Row
        return conn

    def close_connection(self):
        """Closes the persistent connection if it exists (mainly for in-memory DBs)."""
        if self.conn and self.db_filepath == ":memory:":
            self.conn.close()
            self.conn = None

    def _initialize_db(self):
        """Creates database tables for recipes if they don't already exist."""
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                # Recipes Table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS recipes (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL UNIQUE,
                        description TEXT,
                        instructions TEXT
                    )
                ''')
                # Recipe Ingredients Table
                # item_name links to product name in products table (implicitly)
                # quantity could be like "2 cups", "100 grams", etc.
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS recipe_ingredients (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        recipe_id INTEGER NOT NULL,
                        item_name TEXT NOT NULL,
                        quantity TEXT,
                        notes TEXT,
                        FOREIGN KEY (recipe_id) REFERENCES recipes (id)
                    )
                ''')
                conn.commit()
        except sqlite3.Error as e:
            # It's good practice to raise or log this error.
            # For now, printing to console.
            print(f"RecipeManager Database initialization error: {e}")
            # raise sqlite3.Error(f"RecipeManager Database initialization error: {e}")

    def get_recipes_for_product(self, product_name):
        """
        Finds all recipes that use a given product_name (item_name in recipe_ingredients).
        Returns a list of recipe dicts e.g., [{'id': 1, 'name': 'Pasta Carbonara'}].
        """
        recipes_found = []
        if not product_name:
            return recipes_found

        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                # First, find recipe_ids from recipe_ingredients that match the product_name
                # Using LOWER() for case-insensitive matching of item_name
                cursor.execute('''
                    SELECT DISTINCT ri.recipe_id, r.name
                    FROM recipe_ingredients ri
                    JOIN recipes r ON ri.recipe_id = r.id
                    WHERE LOWER(ri.item_name) = LOWER(?)
                    ORDER BY r.name ASC
                ''', (product_name,))

                rows = cursor.fetchall()
                for row in rows:
                    recipes_found.append({'id': row['recipe_id'], 'name': row['name']})
            return recipes_found
        except sqlite3.Error as e:
            print(f"Database error getting recipes for product '{product_name}': {e}")
            return [] # Return empty list on error

# Example Usage (can be removed or commented out later)
if __name__ == '__main__':
    print("RecipeManager Demo")
    # Use an in-memory database for this example for simplicity
    recipe_manager = RecipeManager(db_filepath=":memory:")

    # Setup: Create some dummy recipes and ingredients
    try:
        with recipe_manager._get_db_connection() as conn:
            cursor = conn.cursor()
            # Add recipes
            cursor.execute("INSERT INTO recipes (name, description, instructions) VALUES (?, ?, ?)",
                           ("Spaghetti Aglio e Olio", "Classic garlic and oil pasta", "Cook spaghetti. Saute garlic in oil. Combine."))
            recipe_id_aglio = cursor.lastrowid

            cursor.execute("INSERT INTO recipes (name, description, instructions) VALUES (?, ?, ?)",
                           ("Tomato Soup", "Simple tomato soup", "Blend tomatoes. Simmer with spices."))
            recipe_id_soup = cursor.lastrowid

            cursor.execute("INSERT INTO recipes (name, description, instructions) VALUES (?, ?, ?)",
                           ("Garlic Bread", "Crusty bread with garlic butter", "Spread garlic butter on bread. Bake."))
            recipe_id_garlic_bread = cursor.lastrowid

            # Add ingredients
            # Aglio e Olio ingredients
            cursor.execute("INSERT INTO recipe_ingredients (recipe_id, item_name, quantity) VALUES (?, ?, ?)",
                           (recipe_id_aglio, "Spaghetti", "200g"))
            cursor.execute("INSERT INTO recipe_ingredients (recipe_id, item_name, quantity) VALUES (?, ?, ?)",
                           (recipe_id_aglio, "Garlic", "3 cloves"))
            cursor.execute("INSERT INTO recipe_ingredients (recipe_id, item_name, quantity) VALUES (?, ?, ?)",
                           (recipe_id_aglio, "Olive Oil", "4 tbsp"))

            # Tomato Soup ingredients
            cursor.execute("INSERT INTO recipe_ingredients (recipe_id, item_name, quantity) VALUES (?, ?, ?)",
                           (recipe_id_soup, "Tomatoes", "500g"))
            cursor.execute("INSERT INTO recipe_ingredients (recipe_id, item_name, quantity) VALUES (?, ?, ?)",
                           (recipe_id_soup, "Garlic", "1 clove")) # Garlic also in soup
            cursor.execute("INSERT INTO recipe_ingredients (recipe_id, item_name, quantity) VALUES (?, ?, ?)",
                           (recipe_id_soup, "Vegetable Broth", "2 cups"))

            # Garlic Bread ingredients
            cursor.execute("INSERT INTO recipe_ingredients (recipe_id, item_name, quantity) VALUES (?, ?, ?)",
                           (recipe_id_garlic_bread, "Baguette", "1"))
            cursor.execute("INSERT INTO recipe_ingredients (recipe_id, item_name, quantity) VALUES (?, ?, ?)",
                           (recipe_id_garlic_bread, "Garlic", "2 cloves"))
            cursor.execute("INSERT INTO recipe_ingredients (recipe_id, item_name, quantity) VALUES (?, ?, ?)",
                           (recipe_id_garlic_bread, "Butter", "50g"))
            conn.commit()
            print("Dummy recipes and ingredients added.")
    except sqlite3.Error as e:
        print(f"Error setting up demo data: {e}")

    # Test get_recipes_for_product
    print("\n--- Testing get_recipes_for_product ---")

    product_to_test = "Garlic"
    recipes_with_garlic = recipe_manager.get_recipes_for_product(product_to_test)
    print(f"Recipes containing '{product_to_test}': {recipes_with_garlic}")
    # Expected: [{'id': recipe_id_aglio, 'name': 'Spaghetti Aglio e Olio'}, {'id': recipe_id_soup, 'name': 'Tomato Soup'}, {'id': recipe_id_garlic_bread, 'name': 'Garlic Bread'}] (IDs will vary)

    product_to_test_2 = "Tomatoes"
    recipes_with_tomatoes = recipe_manager.get_recipes_for_product(product_to_test_2)
    print(f"Recipes containing '{product_to_test_2}': {recipes_with_tomatoes}")
    # Expected: [{'id': recipe_id_soup, 'name': 'Tomato Soup'}]

    product_to_test_3 = "NonExistentProduct"
    recipes_with_nonexistent = recipe_manager.get_recipes_for_product(product_to_test_3)
    print(f"Recipes containing '{product_to_test_3}': {recipes_with_nonexistent}")
    # Expected: []

    product_to_test_4 = "spaghetti" # Test case insensitivity
    recipes_with_spaghetti_lower = recipe_manager.get_recipes_for_product(product_to_test_4)
    print(f"Recipes containing '{product_to_test_4}' (lowercase): {recipes_with_spaghetti_lower}")
    # Expected: [{'id': recipe_id_aglio, 'name': 'Spaghetti Aglio e Olio'}]


    recipe_manager.close_connection()
    print("\nRecipeManager Demo Complete.")
