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
            print(f"Recipe DB initialization error: {e}")
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

    def update_recipe(self, original_recipe_name, updated_recipe_data):
        """
        Updates an existing recipe.
        - Finds recipe by its original name.
        - Validates new data (name, description, ingredients).
        - If name is changed, checks for conflicts.
        - Updates recipe details and replaces all its ingredients in the database.
        - Operations are performed within a transaction.
        """
        if not original_recipe_name or not isinstance(original_recipe_name, str):
            return {"success": False, "message": "Original recipe name invalid."}
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
                cursor.execute("SELECT id FROM recipes WHERE name = ?", (original_recipe_name,))
                recipe_row = cursor.fetchone()
                if not recipe_row:
                    return {"success": False, "message": f"Recipe '{original_recipe_name}' not found."}
                recipe_id = recipe_row['id']

                # If name is being changed, check for conflict
                if new_name.lower() != original_recipe_name.lower():
                    cursor.execute("SELECT id FROM recipes WHERE name = ? AND id != ?", (new_name, recipe_id))
                    if cursor.fetchone():
                        return {"success": False, "message": f"New recipe name '{new_name}' already exists."}
                
                cursor.execute("UPDATE recipes SET name = ?, description = ? WHERE id = ?",
                               (new_name, new_description.strip() if isinstance(new_description, str) else "", recipe_id))
                
                cursor.execute("DELETE FROM recipe_ingredients WHERE recipe_id = ?", (recipe_id,))
                for ing_data in valid_new_ingredients_data:
                    cursor.execute('''
                        INSERT INTO recipe_ingredients (recipe_id, item_name, quantity_required) 
                        VALUES (?, ?, ?)
                    ''', (recipe_id, ing_data["item_name"], ing_data["quantity_required"]))
                
                conn.commit()
                return {"success": True, "message": f"Recipe '{original_recipe_name}' updated successfully to '{new_name}'."}
        except sqlite3.IntegrityError: # Handles UNIQUE constraint for new_name if it still conflicts
            conn.rollback()
            return {"success": False, "message": f"New recipe name '{new_name}' already exists (DB constraint)."}
        except sqlite3.Error as e:
            print(f"Database error updating recipe: {e}")
            return {"success": False, "message": f"Database error updating recipe: {e}"}

    def delete_recipe(self, recipe_name):
        """
        Deletes a recipe from the database by its name (case-insensitive).
        Relies on 'ON DELETE CASCADE' foreign key constraint to also delete associated ingredients.
        """
        if not recipe_name or not isinstance(recipe_name, str):
            return {"success": False, "message": "Recipe name invalid for deletion."}
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM recipes WHERE name = ?", (recipe_name,))
                recipe_row = cursor.fetchone()
                if not recipe_row:
                    return {"success": False, "message": f"Recipe '{recipe_name}' not found."}
                
                recipe_id = recipe_row['id']
                # Foreign key ON DELETE CASCADE should handle recipe_ingredients table
                cursor.execute("DELETE FROM recipes WHERE id = ?", (recipe_id,))
                conn.commit()
                
                if cursor.rowcount > 0: # Check if a row was actually deleted
                    return {"success": True, "message": f"Recipe '{recipe_name}' deleted successfully."}
                else:
                    # This case means the recipe was found, but delete affected 0 rows, which is odd.
                    # Might indicate a race condition or issue if name check and delete are not atomic enough
                    # without proper transaction isolation (though SQLite SERIALIZABLE should handle this).
                    # For simplicity, if it was found and then not deleted, it's an issue.
                    return {"success": False, "message": f"Recipe '{recipe_name}' found but not deleted. Unknown error."}

        except sqlite3.Error as e:
            print(f"Database error deleting recipe '{recipe_name}': {e}")
            return {"success": False, "message": f"Database error: {e}"}


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
    recipes_to_add = [
        {"name": "Pasta Carbonara", "description": "Classic Italian pasta.", 
         "ingredients": [{"item_name": "Spaghetti", "quantity_required": 200}, {"item_name": "Eggs", "quantity_required": 2}]},
        {"name": "Omelette", "description": "Simple egg omelette.", 
         "ingredients": [{"item_name": "Eggs", "quantity_required": 3}, {"item_name": "Milk", "quantity_required": 0.05}]},
        {"name": "Salad", "description": "Basic green salad.", "ingredients": []} # Recipe with no ingredients
    ]
    for r_data in recipes_to_add:
        res = recipe_manager.add_recipe(r_data)
        print(f"Add '{r_data['name']}': {res['message']}")

    # Add duplicate
    res_dup = recipe_manager.add_recipe({"name": "Omelette", "ingredients": []})
    print(f"Add duplicate 'Omelette': {res_dup['message']}")
    
    # Add invalid
    res_inv = recipe_manager.add_recipe({"name": "Invalid Recipe", "ingredients": [{"item_name": "Test", "quantity_required": "bad"}]})
    print(f"Add invalid recipe data: {res_inv['message']}")

    # Get all recipes
    print("\nAll recipes after additions:")
    for r in recipe_manager.get_all_recipes():
        print(f"  - {r['name']}: {r['description']} (Ingredients: {len(r['ingredients'])})")

    # Get one recipe
    print("\nGet 'Pasta Carbonara':")
    pasta = recipe_manager.get_recipe_by_name("Pasta Carbonara")
    if pasta: print(f"  Found: {pasta['name']}, Ingredients: {pasta['ingredients']}")
    else: print("  'Pasta Carbonara' not found.")

    # Update recipe
    update_data = {"name": "Pasta Carbonara Deluxe", "description": "Deluxe Carbonara", 
                   "ingredients": [{"item_name": "Spaghetti", "quantity_required": 250}, 
                                   {"item_name": "Pancetta", "quantity_required": 100},
                                   {"item_name": "Eggs", "quantity_required": 3}]}
    res_update = recipe_manager.update_recipe("Pasta Carbonara", update_data)
    print(f"\nUpdate 'Pasta Carbonara': {res_update['message']}")
    
    updated_pasta = recipe_manager.get_recipe_by_name("Pasta Carbonara Deluxe")
    if updated_pasta: print(f"  Updated to: {updated_pasta['name']}, New ingredients: {updated_pasta['ingredients']}")

    # Delete recipe
    res_delete = recipe_manager.delete_recipe("Omelette")
    print(f"\nDelete 'Omelette': {res_delete['message']}")
    
    res_delete_fail = recipe_manager.delete_recipe("Omelette") # Try deleting again
    print(f"Delete 'Omelette' again: {res_delete_fail['message']}")


    print("\nFinal list of recipes:")
    for r in recipe_manager.get_all_recipes():
        print(f"  - {r['name']}")
        
    print(f"\nDemo complete. Database is in '{DB_RECIPE_FILE}'.")
    # To keep the DB file after demo:
    # if os.path.exists(DB_RECIPE_FILE):
    #     print(f"Database file '{DB_RECIPE_FILE}' was created/updated.")
    # else:
    #     print(f"Database file '{DB_RECIPE_FILE}' was not created as expected.")
