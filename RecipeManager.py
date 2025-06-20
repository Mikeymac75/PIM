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
                        /* output_product_id INTEGER REFERENCES products(id) - Will be added via ALTER TABLE */
                        /* output_yield REAL - Will be added via ALTER TABLE */
                    )
                ''')

                # Check and add new columns to recipes table if they don't exist
                cursor.execute("PRAGMA table_info(recipes)")
                columns = [column[1] for column in cursor.fetchall()]

                if 'output_product_id' not in columns:
                    cursor.execute('ALTER TABLE recipes ADD COLUMN output_product_id INTEGER REFERENCES products(id)')
                    print("Column 'output_product_id' added to 'recipes' table.")

                if 'output_yield' not in columns:
                    cursor.execute('ALTER TABLE recipes ADD COLUMN output_yield REAL')
                    print("Column 'output_yield' added to 'recipes' table.")

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

    def add_recipe(self, recipe_data):
        """
        Adds a new recipe to the database.
        recipe_data is a dict containing name, description, instructions,
        ingredients (list of dicts), output_product_id (optional), and output_yield (optional).
        """
        if not recipe_data or 'name' not in recipe_data or 'ingredients' not in recipe_data:
            return {"success": False, "message": "Recipe name and ingredients are required."}

        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO recipes (name, description, instructions, output_product_id, output_yield)
                    VALUES (?, ?, ?, ?, ?)
                ''', (recipe_data['name'], recipe_data.get('description'), recipe_data.get('instructions'),
                      recipe_data.get('output_product_id'), recipe_data.get('output_yield')))
                recipe_id = cursor.lastrowid

                for ingredient in recipe_data['ingredients']:
                    if not ingredient.get('item_name'):
                        # Rollback or handle more gracefully if an ingredient is invalid
                        conn.rollback()
                        return {"success": False, "message": "Ingredient item_name is required."}
                    cursor.execute('''
                        INSERT INTO recipe_ingredients (recipe_id, item_name, quantity, notes)
                        VALUES (?, ?, ?, ?)
                    ''', (recipe_id, ingredient['item_name'], ingredient.get('quantity'), ingredient.get('notes')))

                conn.commit()
                return {"success": True, "message": "Recipe added successfully.", "recipe_id": recipe_id}
        except sqlite3.IntegrityError:
            return {"success": False, "message": f"Recipe name '{recipe_data['name']}' already exists."}
        except sqlite3.Error as e:
            return {"success": False, "message": f"Database error adding recipe: {e}"}

    def get_recipe_by_id(self, recipe_id):
        """Retrieves a complete recipe (details and ingredients) by its ID."""
        recipe = None
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT r.id, r.name, r.description, r.instructions, r.output_product_id, r.output_yield
                    FROM recipes r
                    WHERE r.id = ?
                ''', (recipe_id,))
                recipe_row = cursor.fetchone()

                if recipe_row:
                    recipe = dict(recipe_row)
                    cursor.execute('''
                        SELECT id, item_name, quantity, notes
                        FROM recipe_ingredients
                        WHERE recipe_id = ?
                    ''', (recipe_id,))
                    ingredients = [dict(row) for row in cursor.fetchall()]
                    recipe['ingredients'] = ingredients
        except sqlite3.Error as e:
            print(f"Database error getting recipe by ID {recipe_id}: {e}")
        return recipe

    def get_recipe_by_name(self, recipe_name):
        """Retrieves a complete recipe (details and ingredients) by its name."""
        recipe = None
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                # Using LOWER() for case-insensitive matching of recipe name
                cursor.execute('''
                    SELECT r.id, r.name, r.description, r.instructions, r.output_product_id, r.output_yield
                    FROM recipes r
                    WHERE LOWER(r.name) = LOWER(?)
                ''', (recipe_name,))
                recipe_row = cursor.fetchone()

                if recipe_row:
                    recipe = dict(recipe_row)
                    cursor.execute('''
                        SELECT id, item_name, quantity, notes
                        FROM recipe_ingredients
                        WHERE recipe_id = ?
                    ''', (recipe['id'],)) # Use the id from the fetched recipe_row
                    ingredients = [dict(row) for row in cursor.fetchall()]
                    recipe['ingredients'] = ingredients
        except sqlite3.Error as e:
            print(f"Database error getting recipe by name '{recipe_name}': {e}")
        return recipe

    def get_all_recipes(self, page=1, per_page=10, sort_by='name', sort_order='ASC'):
        """Retrieves all recipes with details and ingredients, with pagination and sorting."""
        recipes_list = []

        # Validate sort_by and sort_order
        valid_sort_columns = {'name', 'description'} # Add more if needed, like output_product_id
        sort_column = sort_by if sort_by in valid_sort_columns else 'name'
        sort_order_str = 'DESC' if sort_order.upper() == 'DESC' else 'ASC'

        offset = (page - 1) * per_page

        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                # Get paginated recipes
                query = f'''
                    SELECT r.id, r.name, r.description, r.instructions, r.output_product_id, r.output_yield
                    FROM recipes r
                    ORDER BY r.{sort_column} {sort_order_str}
                    LIMIT ? OFFSET ?
                '''
                cursor.execute(query, (per_page, offset))
                recipe_rows = cursor.fetchall()

                for recipe_row in recipe_rows:
                    recipe = dict(recipe_row)
                    # Fetch ingredients for each recipe
                    cursor.execute('''
                        SELECT id, item_name, quantity, notes
                        FROM recipe_ingredients
                        WHERE recipe_id = ?
                    ''', (recipe['id'],))
                    ingredients = [dict(ing_row) for ing_row in cursor.fetchall()]
                    recipe['ingredients'] = ingredients
                    recipes_list.append(recipe)
        except sqlite3.Error as e:
            print(f"Database error getting all recipes: {e}")
        return recipes_list

    def get_all_recipes_count(self):
        """Gets the total number of recipes."""
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) as count FROM recipes")
                result = cursor.fetchone()
                return result['count'] if result else 0
        except sqlite3.Error as e:
            print(f"Database error getting recipe count: {e}")
            return 0

    def update_recipe(self, recipe_id, recipe_data):
        """
        Updates an existing recipe.
        recipe_data can contain name, description, instructions, output_product_id, output_yield.
        Ingredients update is handled separately (e.g., by deleting old and adding new).
        """
        if not recipe_data:
            return {"success": False, "message": "No data provided for update."}

        fields_to_update = []
        params = []

        if 'name' in recipe_data:
            fields_to_update.append("name = ?")
            params.append(recipe_data['name'])
        if 'description' in recipe_data:
            fields_to_update.append("description = ?")
            params.append(recipe_data['description'])
        if 'instructions' in recipe_data:
            fields_to_update.append("instructions = ?")
            params.append(recipe_data['instructions'])
        if 'output_product_id' in recipe_data: # Can be None to clear it
            fields_to_update.append("output_product_id = ?")
            params.append(recipe_data['output_product_id'])
        if 'output_yield' in recipe_data: # Can be None to clear it
            fields_to_update.append("output_yield = ?")
            params.append(recipe_data['output_yield'])

        if not fields_to_update:
            return {"success": False, "message": "No valid fields to update for recipe details."}

        params.append(recipe_id)
        query = f"UPDATE recipes SET {', '.join(fields_to_update)} WHERE id = ?"

        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, tuple(params))
                # Ingredient updates would typically be:
                # 1. Delete existing ingredients for this recipe_id
                # 2. Insert new ingredients from recipe_data['ingredients'] if provided
                # This part is complex and depends on how UI handles ingredient editing.
                # For now, focusing on updating the recipe table itself.
                # If recipe_data includes 'ingredients', we can call a helper or implement here.
                if 'ingredients' in recipe_data:
                    # Delete old ingredients
                    cursor.execute("DELETE FROM recipe_ingredients WHERE recipe_id = ?", (recipe_id,))
                    # Add new ingredients
                    for ingredient in recipe_data['ingredients']:
                        if not ingredient.get('item_name'):
                            conn.rollback()
                            return {"success": False, "message": "Ingredient item_name is required for update."}
                        cursor.execute('''
                            INSERT INTO recipe_ingredients (recipe_id, item_name, quantity, notes)
                            VALUES (?, ?, ?, ?)
                        ''', (recipe_id, ingredient['item_name'], ingredient.get('quantity'), ingredient.get('notes')))

                conn.commit()
                if cursor.rowcount == 0 and not ('ingredients' in recipe_data and recipe_data['ingredients']):
                    # Check rowcount only if ingredients were not the only thing changed
                    # A bit complex logic here, if only ingredients changed, main table rowcount is 0
                    # A more robust check might be needed, or rely on get_recipe_by_id to confirm existence
                    # For now, if ingredients were updated, we assume success if no SQL error.
                    # If no core fields updated and no ingredients, it might mean recipe_id not found.
                    # This check is imperfect.
                    # A better way: Check if recipe exists before attempting update.
                    pass # Allow updates of only ingredients

                return {"success": True, "message": f"Recipe ID {recipe_id} updated successfully."}
        except sqlite3.IntegrityError as e: # e.g. unique constraint on name
            return {"success": False, "message": f"Error updating recipe (e.g., name conflict): {e}"}
        except sqlite3.Error as e:
            return {"success": False, "message": f"Database error updating recipe: {e}"}

    def delete_recipe(self, recipe_id):
        """Deletes a recipe and its associated ingredients."""
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                # First, delete associated ingredients
                cursor.execute("DELETE FROM recipe_ingredients WHERE recipe_id = ?", (recipe_id,))
                # Then, delete the recipe itself
                cursor.execute("DELETE FROM recipes WHERE id = ?", (recipe_id,))
                conn.commit()
                if cursor.rowcount == 0: # Check if the recipe deletion affected any row
                    return {"success": False, "message": f"Recipe with ID {recipe_id} not found."}
                return {"success": True, "message": f"Recipe ID {recipe_id} and its ingredients deleted successfully."}
        except sqlite3.Error as e:
            return {"success": False, "message": f"Database error deleting recipe: {e}"}

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
