import sqlite3
import os # For the demo part
import json # Only for the demo part's print statements

class RecipeManager:
    def __init__(self, db_filepath="inventory.db"): # Changed default to inventory.db for consistency
        self.db_filepath = db_filepath
        self._initialize_db()

    def _get_db_connection(self):
        """Establishes and returns a database connection, enabling foreign keys."""
        conn = sqlite3.connect(self.db_filepath)
        conn.row_factory = sqlite3.Row # Access columns by name
        conn.execute("PRAGMA foreign_keys = ON;") # Crucial for ON DELETE CASCADE
        return conn

    def _initialize_db(self):
        """Creates database tables for recipes if they don't already exist."""
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS recipes (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL UNIQUE COLLATE NOCASE,
                        description TEXT
                    )
                ''')
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS recipe_ingredients (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        recipe_id INTEGER NOT NULL,
                        item_name TEXT NOT NULL,
                        quantity_required REAL NOT NULL,
                        FOREIGN KEY (recipe_id) REFERENCES recipes(id) ON DELETE CASCADE
                    )
                ''')
                conn.commit()
        except sqlite3.Error as e:
            raise sqlite3.Error(f"Recipe DB initialization error: {e}")
            # Consider raising this or handling more gracefully in a real app

    def add_recipe(self, recipe_data):
        """
        Adds a new recipe to the database, including its name, description, and ingredients.
        Validates input data, checks for duplicate recipe names (case-insensitive).
        Ingredients are stored in a separate table linked by recipe_id.
        Operations are performed within a transaction.
        """
        if not isinstance(recipe_data, dict):
            return {"success": False, "message": "Invalid recipe data format."}

        name = recipe_data.get("name")
        description = recipe_data.get("description", "")
        ingredients_list = recipe_data.get("ingredients")

        if not name or not isinstance(name, str) or not name.strip():
            return {"success": False, "message": "Recipe name is required."}
        name = name.strip()

        if not isinstance(ingredients_list, list): # Allow empty list for recipes with no ingredients
            return {"success": False, "message": "Ingredients must be a list (can be empty)."}

        valid_ingredients_data = []
        for idx, ing in enumerate(ingredients_list):
            if not isinstance(ing, dict): return {"success": False, "message": f"Ing. {idx+1} invalid format."}
            item_name = ing.get("item_name")
            qty_req_str = ing.get("quantity_required")
            if not item_name or not isinstance(item_name, str) or not item_name.strip():
                return {"success": False, "message": f"Ing. {idx+1} name missing."}
            try:
                qty_req_float = float(qty_req_str)
                if qty_req_float <= 0: return {"success": False, "message": f"Ing. '{item_name}' qty must be > 0."}
                valid_ingredients_data.append({"item_name": item_name.strip(), "quantity_required": qty_req_float})
            except (ValueError, TypeError):
                return {"success": False, "message": f"Ing. '{item_name}' qty invalid."}
        
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                # Check for existing recipe name (case-insensitive due to COLLATE NOCASE on schema)
                cursor.execute("SELECT id FROM recipes WHERE name = ?", (name,))
                if cursor.fetchone():
                    return {"success": False, "message": f"Recipe name '{name}' already exists."}

                cursor.execute("INSERT INTO recipes (name, description) VALUES (?, ?)", 
                               (name, description.strip() if isinstance(description, str) else ""))
                recipe_id = cursor.lastrowid
                
                if recipe_id:
                    for ing_data in valid_ingredients_data:
                        cursor.execute('''
                            INSERT INTO recipe_ingredients (recipe_id, item_name, quantity_required) 
                            VALUES (?, ?, ?)
                        ''', (recipe_id, ing_data["item_name"], ing_data["quantity_required"]))
                    conn.commit()
                    return {"success": True, "message": f"Recipe '{name}' added successfully."}
                else:
                    # This case should ideally not happen if INSERT was successful without error
                    conn.rollback() # Should be automatic with 'with conn:' on error
                    return {"success": False, "message": "Failed to get recipe ID after insert."}
        except sqlite3.IntegrityError: # Handles UNIQUE constraint for name specifically
             conn.rollback()
             return {"success": False, "message": f"Recipe name '{name}' already exists (DB constraint)."}
        except sqlite3.Error as e:
            print(f"Database error adding recipe: {e}")
            return {"success": False, "message": f"Database error: {e}"}

    def get_all_recipes(self):
        """
        Retrieves all recipes with their ingredients from the database.
        Optimized to reduce N+1 queries:
        1. Fetches all recipes.
        2. Fetches all ingredients.
        3. Maps ingredients to their respective recipes in Python.
        """
        recipes_dict = {} # Use a dictionary for quick lookup by recipe_id
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                
                # 1. Fetch all recipes
                cursor.execute("SELECT id, name, description FROM recipes ORDER BY name ASC")
                recipe_rows = cursor.fetchall()
                for row in recipe_rows:
                    recipes_dict[row['id']] = {
                        "id": row['id'], 
                        "name": row['name'], 
                        "description": row['description'], 
                        "ingredients": []
                    }
                
                # 2. Fetch all ingredients if there are recipes
                if recipes_dict:
                    cursor.execute("SELECT recipe_id, item_name, quantity_required FROM recipe_ingredients")
                    ingredient_rows = cursor.fetchall()
                    
                    # 3. Map ingredients to recipes
                    for ing_row in ingredient_rows:
                        recipe_id = ing_row['recipe_id']
                        if recipe_id in recipes_dict:
                            recipes_dict[recipe_id]['ingredients'].append({
                                "item_name": ing_row['item_name'],
                                "quantity_required": ing_row['quantity_required']
                            })
            return list(recipes_dict.values())
        except sqlite3.Error as e:
            print(f"Database error fetching all recipes: {e}")
            return []

    def get_recipe_by_name(self, recipe_name):
        """
        Gets a specific recipe by its name (case-insensitive) along with its ingredients.
        Uses the schema's COLLATE NOCASE for case-insensitive name matching.
        """
        if not recipe_name or not isinstance(recipe_name, str): return None
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                # Fetch the recipe by name
                cursor.execute("SELECT id, name, description FROM recipes WHERE name = ?", (recipe_name,))
                recipe_row = cursor.fetchone()
                
                if recipe_row:
                    recipe_data = dict(recipe_row)
                    recipe_data["ingredients"] = []
                    
                    # Fetch its ingredients
                    cursor.execute('''
                        SELECT item_name, quantity_required 
                        FROM recipe_ingredients 
                        WHERE recipe_id = ?
                    ''', (recipe_data['id'],))
                    ingredient_rows = cursor.fetchall()
                    for ing_row in ingredient_rows:
                        recipe_data["ingredients"].append(dict(ing_row))
                    return recipe_data
                else:
                    return None # Recipe not found
        except sqlite3.Error as e:
            print(f"Database error fetching recipe by name '{recipe_name}': {e}")
            return None

    def get_recipe_by_id(self, recipe_id):
        """
        Gets a specific recipe by its ID along with its ingredients.
        """
        if not isinstance(recipe_id, int):
            # Or handle as appropriate, e.g., raise ValueError or return None
            print(f"Invalid recipe_id type: {type(recipe_id)}. Must be int.")
            return None
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id, name, description FROM recipes WHERE id = ?", (recipe_id,))
                recipe_row = cursor.fetchone()

                if recipe_row:
                    recipe_data = dict(recipe_row)
                    recipe_data["ingredients"] = []

                    cursor.execute('''
                        SELECT item_name, quantity_required
                        FROM recipe_ingredients
                        WHERE recipe_id = ?
                    ''', (recipe_id,)) # Use recipe_id directly
                    ingredient_rows = cursor.fetchall()
                    for ing_row in ingredient_rows:
                        recipe_data["ingredients"].append(dict(ing_row))
                    return recipe_data
                else:
                    return None # Recipe not found
        except sqlite3.Error as e:
            print(f"Database error fetching recipe by ID '{recipe_id}': {e}")
            return None

    def get_recipes_for_product(self, product_name_to_find):
        """
        Retrieves a list of recipes that contain the given product name.
        - product_name_to_find: The name of the product (string) to search for in recipe ingredients.
        Returns a list of recipe dictionaries (e.g., [{'id': 1, 'name': 'Recipe Name'}]),
        or an empty list if no recipes contain the product or an error occurs.
        """
        if not product_name_to_find or not isinstance(product_name_to_find, str):
            print("Invalid product name provided to get_recipes_for_product.")
            return []

        recipes_found = []
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                # Find recipe_ids that contain the product_name (case-insensitive)
                # Ensure item_name in recipe_ingredients is compared case-insensitively
                cursor.execute("""
                    SELECT DISTINCT ri.recipe_id, r.name
                    FROM recipe_ingredients ri
                    JOIN recipes r ON ri.recipe_id = r.id
                    WHERE LOWER(ri.item_name) = LOWER(?)
                """, (product_name_to_find,))

                rows = cursor.fetchall()
                for row in rows:
                    recipes_found.append({"id": row['recipe_id'], "name": row['name']})
            return recipes_found
        except sqlite3.Error as e:
            print(f"Database error in get_recipes_for_product for '{product_name_to_find}': {e}")
            return []
        except Exception as e:
            print(f"An unexpected error occurred in get_recipes_for_product for '{product_name_to_find}': {e}")
            return []

    def update_recipe(self, recipe_id, updated_recipe_data):
        """
        Updates an existing recipe identified by its ID.
        - Validates new data (name, description, ingredients).
        - Fetches original recipe name for messages and conflict check context.
        - If name is changed, checks for conflicts against other recipes.
        - Updates recipe details and replaces all its ingredients in the database.
        - Operations are performed within a transaction.
        """
        if not isinstance(recipe_id, int):
            return {"success": False, "message": "Recipe ID must be an integer."}
        if not isinstance(updated_recipe_data, dict):
            return {"success": False, "message": "Updated recipe data invalid."}

        new_name = updated_recipe_data.get("name", "").strip()
        new_description = updated_recipe_data.get("description", "")
        new_ingredients_list = updated_recipe_data.get("ingredients")

        if not new_name: return {"success": False, "message": "Updated recipe name required."}
        if not isinstance(new_ingredients_list, list): return {"success": False, "message": "Updated ingredients must be a list."}

        valid_new_ingredients_data = []
        for idx, ing in enumerate(new_ingredients_list):
            if not isinstance(ing, dict): return {"success": False, "message": f"Updated ing. {idx+1} invalid format."}
            item_name = ing.get("item_name")
            qty_req_str = ing.get("quantity_required")
            if not item_name or not isinstance(item_name, str) or not item_name.strip():
                return {"success": False, "message": f"Updated ing. {idx+1} name missing."}
            try:
                qty_req_float = float(qty_req_str)
                if qty_req_float <= 0: return {"success": False, "message": f"Updated ing. '{item_name}' qty must be > 0."}
                valid_new_ingredients_data.append({"item_name": item_name.strip(), "quantity_required": qty_req_float})
            except (ValueError, TypeError):
                return {"success": False, "message": f"Updated ing. '{item_name}' qty invalid."}

        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()

                # Fetch original recipe name for messages and comparison
                cursor.execute("SELECT name FROM recipes WHERE id = ?", (recipe_id,))
                recipe_record = cursor.fetchone()
                if not recipe_record:
                    return {"success": False, "message": f"Recipe with ID {recipe_id} not found."}
                original_recipe_name = recipe_record['name']

                # If name is being changed, check for conflict with other recipes
                # Using lower() for case-insensitive comparison, consistent with schema's COLLATE NOCASE for uniqueness
                if new_name.lower() != original_recipe_name.lower():
                    cursor.execute("SELECT id FROM recipes WHERE name = ? AND id != ?", (new_name, recipe_id))
                    if cursor.fetchone():
                        return {"success": False, "message": f"New recipe name '{new_name}' already exists for another recipe."}
                
                cursor.execute("UPDATE recipes SET name = ?, description = ? WHERE id = ?",
                               (new_name, new_description.strip() if isinstance(new_description, str) else "", recipe_id))
                
                cursor.execute("DELETE FROM recipe_ingredients WHERE recipe_id = ?", (recipe_id,))
                for ing_data in valid_new_ingredients_data:
                    cursor.execute('''
                        INSERT INTO recipe_ingredients (recipe_id, item_name, quantity_required) 
                        VALUES (?, ?, ?)
                    ''', (recipe_id, ing_data["item_name"], ing_data["quantity_required"]))
                
                conn.commit()
                return {"success": True, "message": f"Recipe '{original_recipe_name}' (ID: {recipe_id}) updated successfully to '{new_name}'."}
        except sqlite3.IntegrityError: # Handles UNIQUE constraint for new_name if it still conflicts
            conn.rollback()
            # This message assumes the conflict is with the new_name, which is the most likely IntegrityError here.
            return {"success": False, "message": f"Database error: New recipe name '{new_name}' may already exist or another integrity constraint violated."}
        except sqlite3.Error as e:
            # Log the specific error for debugging, but return a generic message to the user.
            print(f"Database error updating recipe ID {recipe_id}: {e}") # Keep for server logs
            return {"success": False, "message": f"An unexpected database error occurred while updating the recipe."} # User-facing

    def delete_recipe(self, recipe_name): # TODO: Consider changing this to delete_recipe_by_id for consistency
        """
        Deletes a recipe from the database by its name (case-insensitive).
        Relies on 'ON DELETE CASCADE' foreign key constraint to also delete associated ingredients.
        """
        if not recipe_name or not isinstance(recipe_name, str):
            return {"success": False, "message": "Recipe name invalid for deletion."}
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                # Find the recipe by name first to get its ID for deletion
                # This maintains the current public interface but uses ID for actual deletion logic if preferred.
                # However, direct deletion by name is also fine if name is UNIQUE.
                cursor.execute("SELECT id FROM recipes WHERE name = ?", (recipe_name,))
                recipe_row = cursor.fetchone()
                if not recipe_row:
                    return {"success": False, "message": f"Recipe '{recipe_name}' not found."}
                
                recipe_id_to_delete = recipe_row['id']

                # Foreign key ON DELETE CASCADE handles recipe_ingredients table
                # Deleting by ID is generally safer if names could somehow be non-unique despite constraints
                # or if the internal preference is to operate by ID.
                cursor.execute("DELETE FROM recipes WHERE id = ?", (recipe_id_to_delete,))
                conn.commit()
                
                if cursor.rowcount > 0: # Check if a row was actually deleted
                    return {"success": True, "message": f"Recipe '{recipe_name}' (ID: {recipe_id_to_delete}) deleted successfully."}
                else:
                    # This case implies the recipe was found by name, but then not deleted by ID.
                    # Highly unlikely if the ID is correct and transaction is atomic.
                    return {"success": False, "message": f"Recipe '{recipe_name}' found but not deleted. Unknown error."}

        except sqlite3.Error as e:
            print(f"Database error deleting recipe '{recipe_name}': {e}") # Server log
            return {"success": False, "message": "An unexpected database error occurred while deleting the recipe."} # User-facing

    def delete_recipe_by_id(self, recipe_id):
        """
        Deletes a recipe from the database by its ID.
        Relies on 'ON DELETE CASCADE' foreign key constraint to also delete associated ingredients.
        """
        if not isinstance(recipe_id, int):
            return {"success": False, "message": "Recipe ID must be an integer for deletion."}
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()

                # Optional: Fetch name for message before deleting
                cursor.execute("SELECT name FROM recipes WHERE id = ?", (recipe_id,))
                recipe_row = cursor.fetchone()
                original_recipe_name = recipe_row['name'] if recipe_row else f"ID {recipe_id}"

                # Foreign key ON DELETE CASCADE should handle recipe_ingredients table
                cursor.execute("DELETE FROM recipes WHERE id = ?", (recipe_id,))
                conn.commit()

                if cursor.rowcount > 0: # Check if a row was actually deleted
                    return {"success": True, "message": f"Recipe '{original_recipe_name}' (ID: {recipe_id}) deleted successfully."}
                else:
                    return {"success": False, "message": f"Recipe with ID {recipe_id} not found or already deleted."}
        except sqlite3.Error as e:
            print(f"Database error deleting recipe ID {recipe_id}: {e}") # Server log
            return {"success": False, "message": "An unexpected database error occurred while deleting the recipe."} # User-facing


if __name__ == '__main__':
    DB_RECIPE_FILE = "recipes_dev.db"
    print(f"Recipe Manager (SQLite) Demo using DB: {DB_RECIPE_FILE}")
    print("Note: For a fresh demo, delete the database file before running.")

    # Clean up DB at start of demo if it exists
    if os.path.exists(DB_RECIPE_FILE):
        os.remove(DB_RECIPE_FILE)
    
    recipe_manager = RecipeManager(db_filepath=DB_RECIPE_FILE)

    print(f"Initial recipes: {json.dumps(recipe_manager.get_all_recipes(), indent=2)}")

    # Add recipes
    recipe1_data = {"name": "Pasta Carbonara", "description": "Classic Italian pasta.",
                    "ingredients": [{"item_name": "Spaghetti", "quantity_required": 200}, {"item_name": "Eggs", "quantity_required": 2}]}
    recipe2_data = {"name": "Omelette", "description": "Simple egg omelette.",
                    "ingredients": [{"item_name": "Eggs", "quantity_required": 3}, {"item_name": "Milk", "quantity_required": 0.05}]}
    recipe3_data = {"name": "Salad", "description": "Basic green salad.", "ingredients": []}

    res1 = recipe_manager.add_recipe(recipe1_data)
    print(f"Add '{recipe1_data['name']}': {res1['message']}")
    pasta_id = recipe_manager.get_recipe_by_name("Pasta Carbonara")['id'] if res1['success'] else None

    res2 = recipe_manager.add_recipe(recipe2_data)
    print(f"Add '{recipe2_data['name']}': {res2['message']}")
    omelette_id = recipe_manager.get_recipe_by_name("Omelette")['id'] if res2['success'] else None

    res3 = recipe_manager.add_recipe(recipe3_data)
    print(f"Add '{recipe3_data['name']}': {res3['message']}")
    salad_id = recipe_manager.get_recipe_by_name("Salad")['id'] if res3['success'] else None


    # Add duplicate
    res_dup = recipe_manager.add_recipe({"name": "Omelette", "ingredients": []})
    print(f"Add duplicate 'Omelette': {res_dup['message']}")
    
    # Add invalid
    res_inv = recipe_manager.add_recipe({"name": "Invalid Recipe", "ingredients": [{"item_name": "Test", "quantity_required": "bad"}]})
    print(f"Add invalid recipe data: {res_inv['message']}")

    # Get all recipes
    print("\nAll recipes after additions:")
    all_recipes = recipe_manager.get_all_recipes()
    for r in all_recipes:
        print(f"  - ID: {r['id']}, Name: {r['name']}: {r['description']} (Ingredients: {len(r['ingredients'])})")

    # Get one recipe by ID
    if pasta_id:
        print(f"\nGet recipe by ID: {pasta_id}")
        pasta_by_id = recipe_manager.get_recipe_by_id(pasta_id)
        if pasta_by_id: print(f"  Found: {pasta_by_id['name']}, Ingredients: {pasta_by_id['ingredients']}")
        else: print(f"  Recipe with ID {pasta_id} not found.")

    # Update recipe by ID
    if pasta_id:
        update_data = {"name": "Pasta Carbonara Deluxe", "description": "Deluxe Carbonara with Pancetta",
                       "ingredients": [{"item_name": "Spaghetti", "quantity_required": 250},
                                       {"item_name": "Pancetta", "quantity_required": 100},
                                       {"item_name": "Organic Eggs", "quantity_required": 3}]}
        res_update = recipe_manager.update_recipe(pasta_id, update_data)
        print(f"\nUpdate recipe ID {pasta_id} ('Pasta Carbonara'): {res_update['message']}")

        updated_pasta = recipe_manager.get_recipe_by_id(pasta_id)
        if updated_pasta: print(f"  Updated to: {updated_pasta['name']}, New ingredients: {updated_pasta['ingredients']}")

    # Attempt to update with conflicting name
    if pasta_id and omelette_id: # Ensure both exist
        conflict_update_data = {"name": "Omelette", "description": "Trying to steal Omelette's name", "ingredients": []}
        res_conflict_update = recipe_manager.update_recipe(pasta_id, conflict_update_data)
        print(f"\nAttempt to update Pasta ID {pasta_id} to name 'Omelette': {res_conflict_update['message']}")


    # Delete recipe by ID
    if omelette_id:
        res_delete_by_id = recipe_manager.delete_recipe_by_id(omelette_id)
        print(f"\nDelete recipe 'Omelette' by ID ({omelette_id}): {res_delete_by_id['message']}")
    
    # Try deleting again by ID
    if omelette_id:
        res_delete_by_id_fail = recipe_manager.delete_recipe_by_id(omelette_id)
        print(f"Delete recipe ID {omelette_id} again: {res_delete_by_id_fail['message']}")


    print("\nFinal list of recipes:")
    for r in recipe_manager.get_all_recipes():
        print(f"  - ID: {r['id']}, Name: {r['name']}")
        
    print(f"\nDemo complete. Database is in '{DB_RECIPE_FILE}'.")
    # To keep the DB file after demo:
    # if os.path.exists(DB_RECIPE_FILE):
    #     print(f"Database file '{DB_RECIPE_FILE}' was created/updated.")
    # else:
    #     print(f"Database file '{DB_RECIPE_FILE}' was not created as expected.")
