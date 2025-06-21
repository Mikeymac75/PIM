import sqlite3
import csv
from datetime import date, timedelta, datetime
import os # For the demo part

class InventoryManager:
    def __init__(self, db_filepath="inventory.db"):
        self.db_filepath = db_filepath
        self.conn = None  # For persistent in-memory connection
        if self.db_filepath == ":memory:":
            self.conn = sqlite3.connect(":memory:")
            self.conn.row_factory = sqlite3.Row
        self._initialize_db()
        # Garden produce is not part of this class for now
        # self.my_garden_produce = []

    def _get_db_connection(self):
        """Establishes and returns a database connection."""
        if self.conn and self.db_filepath == ":memory:":
            return self.conn
        # For file-based databases, create a new connection each time
        conn = sqlite3.connect(self.db_filepath)
        conn.row_factory = sqlite3.Row # Access columns by name
        return conn

    def close_connection(self):
        """Closes the persistent connection if it exists (mainly for in-memory DBs)."""
        if self.conn and self.db_filepath == ":memory:":
            self.conn.close()
            self.conn = None

    def _initialize_db(self):
        """Creates database tables if they don't already exist."""
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()

                # Products Table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS products (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL UNIQUE,
                        unit_of_measure TEXT NOT NULL,
                        default_expiry_days INTEGER NOT NULL,
                        par_level REAL DEFAULT 0,
                        max_holding_amount REAL DEFAULT 0,
                        purchase_location TEXT,
                        consumption_override_rate REAL DEFAULT NULL,
                        category_id INTEGER,
                        subcategory_id INTEGER,
                        FOREIGN KEY (category_id) REFERENCES categories (id),
                        FOREIGN KEY (subcategory_id) REFERENCES subcategories (id)
                    )
                ''')

                # Current Inventory Table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS inventory_items (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        product_id INTEGER,
                        name TEXT NOT NULL,
                        quantity TEXT NOT NULL, 
                        purchase_date TEXT NOT NULL,
                        expiry_date TEXT NOT NULL,
                        original_quantity_string TEXT,
                        FOREIGN KEY (product_id) REFERENCES products (id)
                    )
                ''')
                # Historical (Consumed) Items Table
                # No changes needed for historical_items table in this subtask
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS historical_items (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        product_id INTEGER,
                        name TEXT NOT NULL,
                        quantity_consumed_this_time REAL NOT NULL,
                        original_quantity_string TEXT,
                        purchase_date TEXT, 
                        expiry_date TEXT,
                        consumed_date TEXT NOT NULL,
                        FOREIGN KEY (product_id) REFERENCES products (id)
                    )
                ''')

                # Production Items Table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS production_items (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        associated_product_id INTEGER,
                        plant_date TEXT,
                        time_to_harvest_days INTEGER,
                        expected_harvest_period_days INTEGER,
                        expected_yield_total REAL,
                        status TEXT CHECK(status IN ('Growing', 'Harvesting', 'Finished')),
                        FOREIGN KEY (associated_product_id) REFERENCES products (id)
                    )
                ''')

                # Categories Table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS categories (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL UNIQUE
                    )
                ''')

                # Subcategories Table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS subcategories (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        category_id INTEGER NOT NULL,
                        FOREIGN KEY (category_id) REFERENCES categories (id),
                        UNIQUE (name, category_id)
                    )
                ''')
                conn.commit()
        except sqlite3.Error as e:
            raise sqlite3.Error(f"Database initialization error: {e}")
            # Depending on app design, might want to raise this or handle more gracefully

    def migrate_text_categories_to_ids(self):
        """
        Simulates migration of products with old text-based category/subcategory
        to new ID-based category_id/subcategory_id.
        This method is intended for demonstration and setup.
        """
        print("Starting migration of text categories to IDs...")
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()

                # --- a. Simulate Pre-existing Schema and Data ---
                try:
                    # Add old columns if they don't exist (for simulation)
                    # Note: In a real migration, these columns would already exist.
                    # This is to make the script runnable for demonstration even if DB is new.
                    cursor.execute("SELECT old_category_text FROM products LIMIT 1")
                except sqlite3.OperationalError: # Column doesn't exist
                    print("Simulating old schema: Adding old_category_text and old_subcategory_text columns...")
                    conn.executescript('''
                        ALTER TABLE products ADD COLUMN old_category_text TEXT;
                        ALTER TABLE products ADD COLUMN old_subcategory_text TEXT;
                    ''')
                    # Insert sample data only if we just added the columns (i.e., fresh simulation)
                    print("Inserting sample products with text categories for migration...")
                    sample_products = [
                        ("Apple", "pcs", 14, "Produce", "Fruit"),
                        ("Milk", "liter", 7, "Dairy", None),
                        ("Carrot", "kg", 21, "Produce", "Vegetable"),
                        ("Yogurt", "pcs", 10, "Dairy", "Cultured"),
                        ("Orange Juice", "liter", 7, "Beverages", None),
                        ("Banana", "pcs", 5, "Produce", "Fruit") # Another Produce/Fruit
                    ]
                    for p_name, uom, exp_days, cat_text, subcat_text in sample_products:
                        # Check if product already exists by name to avoid IntegrityError during simulation
                        cursor.execute("SELECT id FROM products WHERE name = ?", (p_name,))
                        if not cursor.fetchone():
                            cursor.execute("""
                                INSERT INTO products (name, unit_of_measure, default_expiry_days, old_category_text, old_subcategory_text, category_id, subcategory_id)
                                VALUES (?, ?, ?, ?, ?, NULL, NULL)
                            """, (p_name, uom, exp_days, cat_text, subcat_text))
                        else:
                            # If product exists, update its old text fields for migration simulation
                            cursor.execute("""
                                UPDATE products SET old_category_text = ?, old_subcategory_text = ?
                                WHERE name = ? AND category_id IS NULL
                            """, (cat_text, subcat_text, p_name))
                    conn.commit()
                    print("Sample data inserted/updated for old text categories.")

                # --- b. Extract Distinct Categories and Populate categories Table ---
                print("Populating 'categories' table from old_category_text...")
                cursor.execute("SELECT DISTINCT old_category_text FROM products WHERE old_category_text IS NOT NULL")
                distinct_categories = [row['old_category_text'] for row in cursor.fetchall()]

                for cat_name in distinct_categories:
                    add_cat_result = self.add_category(cat_name) # Uses existing method, handles duplicates
                    if add_cat_result['success']:
                        print(f"Category '{cat_name}' (ID: {add_cat_result.get('category_id')}) processed/ensured in categories table.")
                    elif "already exists" in add_cat_result.get('message',''):
                         print(f"Category '{cat_name}' already exists, skipping addition.")
                    else:
                        print(f"Warning: Could not add category '{cat_name}': {add_cat_result.get('message')}")
                conn.commit()

                # --- c. Extract Distinct Subcategories and Populate subcategories Table ---
                print("Populating 'subcategories' table...")
                cursor.execute("""
                    SELECT DISTINCT old_category_text, old_subcategory_text
                    FROM products
                    WHERE old_category_text IS NOT NULL AND old_subcategory_text IS NOT NULL
                """)
                distinct_subcategories = cursor.fetchall()

                for row in distinct_subcategories:
                    old_cat_text = row['old_category_text']
                    old_subcat_text = row['old_subcategory_text']

                    category_obj = self.get_category_by_name(old_cat_text)
                    if category_obj:
                        cat_id = category_obj['id']
                        add_subcat_result = self.add_subcategory(old_subcat_text, cat_id) # Handles duplicates
                        if add_subcat_result['success']:
                            print(f"Subcategory '{old_subcat_text}' (ID: {add_subcat_result.get('subcategory_id')}) under Category '{old_cat_text}' processed.")
                        elif "already exists" in add_subcat_result.get('message',''):
                            print(f"Subcategory '{old_subcat_text}' under '{old_cat_text}' already exists.")
                        else:
                             print(f"Warning: Could not add subcategory '{old_subcat_text}' for category '{old_cat_text}': {add_subcat_result.get('message')}")
                    else:
                        print(f"Warning: Category '{old_cat_text}' not found for subcategory '{old_subcat_text}'. Skipping subcategory.")
                conn.commit()

                # --- d. Update products Table with category_id and subcategory_id ---
                print("Updating 'products' table with category_id and subcategory_id...")
                cursor.execute("SELECT id, old_category_text, old_subcategory_text FROM products WHERE category_id IS NULL")
                products_to_update = cursor.fetchall()

                for product_row in products_to_update:
                    prod_id = product_row['id']
                    cat_id_to_set = None
                    sub_cat_id_to_set = None

                    if product_row['old_category_text']:
                        category_data = self.get_category_by_name(product_row['old_category_text'])
                        if category_data:
                            cat_id_to_set = category_data['id']
                            if product_row['old_subcategory_text']:
                                subcategory_data = self.get_subcategory_by_name_and_category_id(product_row['old_subcategory_text'], cat_id_to_set)
                                if subcategory_data:
                                    sub_cat_id_to_set = subcategory_data['id']
                                else:
                                    print(f"Warning: Subcategory '{product_row['old_subcategory_text']}' not found in DB for product ID {prod_id}. Subcategory ID will be NULL.")
                        else:
                            print(f"Warning: Category '{product_row['old_category_text']}' not found in DB for product ID {prod_id}. Category ID will be NULL.")

                    if cat_id_to_set is not None:
                        cursor.execute("""
                            UPDATE products SET category_id = ?, subcategory_id = ?
                            WHERE id = ?
                        """, (cat_id_to_set, sub_cat_id_to_set, prod_id))
                        print(f"Product ID {prod_id} updated with CategoryID: {cat_id_to_set}, SubcategoryID: {sub_cat_id_to_set}")
                conn.commit()

                # --- e. Simulate Dropping Old Columns ---
                # In a real scenario, backup before dropping.
                # SQLite's DROP COLUMN is only supported in version 3.35.0+
                # This might fail in older versions.
                print("Attempting to drop old text category columns (simulation)...")
                try:
                    conn.executescript('''
                        ALTER TABLE products DROP COLUMN old_category_text;
                        ALTER TABLE products DROP COLUMN old_subcategory_text;
                    ''')
                    print("Successfully dropped old_category_text and old_subcategory_text columns.")
                except sqlite3.OperationalError as e_drop:
                    print(f"Could not drop old columns (this is expected if SQLite version < 3.35.0 or columns already dropped): {e_drop}")

                conn.commit()
                return {"success": True, "message": "Migration of text categories to IDs completed."}

        except sqlite3.Error as e:
            return {"success": False, "message": f"Migration failed: {e}"}


    # --- Category and Subcategory Management Methods ---
    def add_category(self, name):
        """Adds a new category to the categories table."""
        if not name or not isinstance(name, str) or not name.strip():
            return {"success": False, "message": "Category name must be a non-empty string."}
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO categories (name) VALUES (?)", (name.strip(),))
                conn.commit()
                category_id = cursor.lastrowid
                return {"success": True, "message": f"Category '{name.strip()}' added successfully.", "category_id": category_id}
        except sqlite3.IntegrityError:
            return {"success": False, "message": f"Category name '{name.strip()}' already exists."}
        except sqlite3.Error as e:
            return {"success": False, "message": f"Database error adding category: {e}"}

    def add_subcategory(self, name, category_id):
        """Adds a new subcategory to the subcategories table."""
        if not name or not isinstance(name, str) or not name.strip():
            return {"success": False, "message": "Subcategory name must be a non-empty string."}
        if not isinstance(category_id, int):
             return {"success": False, "message": "Category ID must be an integer."}

        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                # Check if category_id exists
                cursor.execute("SELECT id FROM categories WHERE id = ?", (category_id,))
                if not cursor.fetchone():
                    return {"success": False, "message": f"Parent category with ID {category_id} not found."}

                cursor.execute("INSERT INTO subcategories (name, category_id) VALUES (?, ?)", (name.strip(), category_id))
                conn.commit()
                subcategory_id = cursor.lastrowid
                return {"success": True, "message": f"Subcategory '{name.strip()}' added successfully under category ID {category_id}.", "subcategory_id": subcategory_id}
        except sqlite3.IntegrityError:
            # This can be due to UNIQUE constraint on (name, category_id) or FOREIGN KEY constraint (though checked above)
            return {"success": False, "message": f"Subcategory '{name.strip()}' already exists for category ID {category_id}, or foreign key constraint failed."}
        except sqlite3.Error as e:
            return {"success": False, "message": f"Database error adding subcategory: {e}"}

    def get_all_categories_with_subcategories(self):
        """
        Retrieves all categories and their subcategories, ordered by name.
        """
        categories_list = []
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id, name FROM categories ORDER BY name ASC")
                categories_rows = cursor.fetchall()

                for cat_row in categories_rows:
                    category_dict = dict(cat_row)
                    category_dict['subcategories'] = []

                    cursor.execute("""
                        SELECT id, name, category_id
                        FROM subcategories
                        WHERE category_id = ?
                        ORDER BY name ASC
                    """, (cat_row['id'],))
                    subcategories_rows = cursor.fetchall()
                    for sub_row in subcategories_rows:
                        category_dict['subcategories'].append(dict(sub_row))
                    categories_list.append(category_dict)
            return categories_list
        except sqlite3.Error as e:
            print(f"Database error retrieving categories with subcategories: {e}")
            return [] # Return empty list on error

    def get_category_by_name(self, name):
        """Retrieves a category by its name (case-insensitive)."""
        if not name or not isinstance(name, str) or not name.strip():
            return None
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id, name FROM categories WHERE LOWER(name) = LOWER(?)", (name.strip(),))
                row = cursor.fetchone()
                return dict(row) if row else None
        except sqlite3.Error as e:
            print(f"Database error getting category by name '{name}': {e}")
            return None

    def get_subcategory_by_name_and_category_id(self, subcategory_name, category_id):
        """Retrieves a subcategory by its name and parent category_id (case-insensitive name)."""
        if not subcategory_name or not isinstance(subcategory_name, str) or not subcategory_name.strip() or not isinstance(category_id, int):
            return None
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, name, category_id
                    FROM subcategories
                    WHERE LOWER(name) = LOWER(?) AND category_id = ?
                """, (subcategory_name.strip(), category_id))
                row = cursor.fetchone()
                return dict(row) if row else None
        except sqlite3.Error as e:
            print(f"Database error getting subcategory by name '{subcategory_name}' and category_id {category_id}: {e}")
            return None

    def get_category_name_by_id(self, category_id):
        """Retrieves a category name by its ID."""
        if not isinstance(category_id, int):
            return None
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM categories WHERE id = ?", (category_id,))
                row = cursor.fetchone()
                return row['name'] if row else None
        except sqlite3.Error as e:
            print(f"Database error getting category name by ID {category_id}: {e}")
            return None

    # --- Production Item (Garden & Harvest) Methods ---
    def add_production_item(self, name, associated_product_id, plant_date_str,
                            time_to_harvest_days, expected_harvest_period_days,
                            expected_yield_total, status='Growing'):
        """Adds a new production item to the production_items table."""
        if not all([name, plant_date_str, time_to_harvest_days is not None,
                    expected_harvest_period_days is not None, expected_yield_total is not None]):
            return {"success": False, "message": "Missing required production item fields."}

        try:
            # Validate plant_date_str format
            date.fromisoformat(plant_date_str)
        except ValueError:
            return {"success": False, "message": "Invalid plant_date format. Use YYYY-MM-DD."}

        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO production_items
                    (name, associated_product_id, plant_date, time_to_harvest_days,
                    expected_harvest_period_days, expected_yield_total, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (name, associated_product_id, plant_date_str, time_to_harvest_days,
                      expected_harvest_period_days, expected_yield_total, status))
                conn.commit()
                item_id = cursor.lastrowid
                return {"success": True, "message": f"Production item '{name}' added successfully.", "item_id": item_id}
        except sqlite3.Error as e:
            return {"success": False, "message": f"Database error adding production item: {e}"}

    def get_production_item(self, item_id):
        """Retrieves a production item by its ID."""
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM production_items WHERE id = ?", (item_id,))
                row = cursor.fetchone()
                if row:
                    item = dict(row)
                    # Dynamically calculate status and yield for single item view as well
                    # This ensures consistency with get_all_production_items
                    # However, the core requirement was for get_all_production_items,
                    # so this is an enhancement. If not desired, remove calculation here.
                    try:
                        plant_dt = date.fromisoformat(item['plant_date'])
                        harvest_start_date = plant_dt + timedelta(days=item['time_to_harvest_days'])
                        harvest_end_date = harvest_start_date + timedelta(days=item['expected_harvest_period_days'])
                        current_dt = date.today()

                        if current_dt < harvest_start_date:
                            item['calculated_status'] = 'Growing'
                        elif harvest_start_date <= current_dt <= harvest_end_date:
                            item['calculated_status'] = 'Harvesting'
                        else:
                            item['calculated_status'] = 'Finished'

                        if item['expected_harvest_period_days'] > 0:
                            item['estimated_daily_yield'] = item['expected_yield_total'] / item['expected_harvest_period_days']
                        else:
                            item['estimated_daily_yield'] = 0
                    except (ValueError, TypeError) as e:
                        # Handle cases where date conversion or calculation might fail
                        item['calculated_status'] = item.get('status', 'Error calculating status') # Fallback to stored status
                        item['estimated_daily_yield'] = 'Error'
                        print(f"Error calculating dynamic fields for production item {item_id}: {e}")
                    return item
                return None
        except sqlite3.Error as e:
            print(f"Database error getting production item by ID {item_id}: {e}")
            return None

    def get_all_production_items(self, filters=None, sort_by='plant_date', sort_order='ASC',
                                 page=1, per_page=10):
        """Retrieves production items with filtering, sorting, pagination, and calculated fields."""
        items = []
        params = []

        query = "SELECT * FROM production_items"

        # Basic filtering (e.g., by status)
        where_clauses = []
        if filters and 'status' in filters:
            # Note: This filters by the *stored* status. Dynamic status is calculated later.
            # If filtering by dynamic status is needed, the query or post-processing becomes more complex.
            where_clauses.append("status = ?")
            params.append(filters['status'])

        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)

        # Sorting
        valid_sort_columns = {
            'name': 'name', 'plant_date': 'plant_date', 'status': 'status',
            'expected_yield_total': 'expected_yield_total'
            # Add more as needed
        }
        sort_column = valid_sort_columns.get(sort_by, 'plant_date')
        sort_order_upper = 'DESC' if sort_order.upper() == 'DESC' else 'ASC'
        query += f" ORDER BY {sort_column} {sort_order_upper}"

        # Pagination
        # If page or per_page is None, or if per_page is not a positive integer,
        # do not apply LIMIT and OFFSET, effectively fetching all products.
        if page is not None and per_page is not None and \
           isinstance(page, int) and isinstance(per_page, int) and \
           page > 0 and per_page > 0:
            offset = (page - 1) * per_page
            query += " LIMIT ? OFFSET ?"
            params.extend([per_page, offset])
        # No 'else' or 'elif' here: if conditions are not met, pagination is skipped.

        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, tuple(params))
                rows = cursor.fetchall()
                current_dt = date.today()
                for row_data in rows:
                    item = dict(row_data)
                    try:
                        plant_dt = date.fromisoformat(item['plant_date'])
                        # Ensure time_to_harvest_days and expected_harvest_period_days are not None
                        time_to_harvest = item['time_to_harvest_days'] if item['time_to_harvest_days'] is not None else 0
                        expected_period = item['expected_harvest_period_days'] if item['expected_harvest_period_days'] is not None else 0

                        harvest_start_date = plant_dt + timedelta(days=time_to_harvest)
                        harvest_end_date = harvest_start_date + timedelta(days=expected_period)

                        if current_dt < harvest_start_date:
                            item['calculated_status'] = 'Growing'
                        elif harvest_start_date <= current_dt <= harvest_end_date:
                            item['calculated_status'] = 'Harvesting'
                        else:
                            item['calculated_status'] = 'Finished'

                        if expected_period > 0 and item['expected_yield_total'] is not None:
                            item['estimated_daily_yield'] = item['expected_yield_total'] / expected_period
                        else:
                            item['estimated_daily_yield'] = 0

                    except (ValueError, TypeError, KeyError) as e:
                        item['calculated_status'] = item.get('status', 'Error') # Fallback to stored status or 'Error'
                        item['estimated_daily_yield'] = 'Error'
                        print(f"Error calculating dynamic fields for item ID {item.get('id')}: {e}")

                    items.append(item)
        except sqlite3.Error as e:
            print(f"Database error fetching all production items: {e}")
        return items

    def update_production_item(self, item_id, data):
        """Updates an existing production item."""
        if not data:
            return {"success": False, "message": "No data provided for update."}

        fields = []
        params = []
        for key, value in data.items():
            # Add more validation for column names if necessary
            if key in ['name', 'associated_product_id', 'plant_date',
                       'time_to_harvest_days', 'expected_harvest_period_days',
                       'expected_yield_total', 'status']:
                if key == 'plant_date':
                    try:
                        date.fromisoformat(value) # Validate date format
                    except ValueError:
                        return {"success": False, "message": f"Invalid plant_date format for {key}: {value}. Use YYYY-MM-DD."}
                fields.append(f"{key} = ?")
                params.append(value)

        if not fields:
            return {"success": False, "message": "No valid fields to update."}

        params.append(item_id)
        query = f"UPDATE production_items SET {', '.join(fields)} WHERE id = ?"

        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, tuple(params))
                conn.commit()
                if cursor.rowcount == 0:
                    return {"success": False, "message": f"Production item with ID {item_id} not found."}
                return {"success": True, "message": f"Production item ID {item_id} updated successfully."}
        except sqlite3.Error as e:
            return {"success": False, "message": f"Database error updating production item: {e}"}

    def record_harvest(self, production_item_id, actual_harvest_amount, harvest_date_str):
        """Records a harvest, adding it to inventory stock."""
        if actual_harvest_amount <= 0:
            return {"success": False, "message": "Actual harvest amount must be positive."}

        production_item = self.get_production_item(production_item_id)
        if not production_item:
            return {"success": False, "message": f"Production item with ID {production_item_id} not found."}

        associated_product_id = production_item.get('associated_product_id')
        if associated_product_id is None:
            return {"success": False, "message": f"Production item ID {production_item_id} does not have an associated product ID."}

        # Validate harvest_date_str format
        try:
            date.fromisoformat(harvest_date_str)
        except ValueError:
            return {"success": False, "message": "Invalid harvest_date format. Use YYYY-MM-DD."}

        # Call add_inventory_stock to add the harvested amount to general inventory
        # self.add_inventory_stock handles fetching product details (like default_expiry_days)
        # and creating the inventory_item record.
        stock_result = self.add_inventory_stock(
            product_id=associated_product_id,
            quantity_str=str(actual_harvest_amount), # add_inventory_stock expects a string
            purchase_date_str=harvest_date_str # Harvest date is treated as purchase date for inventory purposes
        )

        # Optionally, update production_item status or remaining yield here if needed in future.
        # For now, status updates are via update_production_item or dynamic calculation.

        return stock_result

    # --- Product Management Methods ---
    def create_product(self, name, category_id, subcategory_id, unit_of_measure, default_expiry_days,
                       par_level=0, max_holding_amount=0, purchase_location=None):
        """Inserts a new product into the products table."""
        # category_id is treated as required for now. subcategory_id is optional.
        if not all([name, unit_of_measure, default_expiry_days is not None, category_id is not None]):
            return {"success": False, "message": "Missing required product fields (name, category_id, unit_of_measure, default_expiry_days)."}
        if category_id is not None and not isinstance(category_id, int):
            return {"success": False, "message": "Category ID must be an integer."}
        if subcategory_id is not None and not isinstance(subcategory_id, int):
            return {"success": False, "message": "Subcategory ID must be an integer if provided."}

        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO products
                    (name, category_id, subcategory_id, unit_of_measure, default_expiry_days,
                     par_level, max_holding_amount, purchase_location)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (name, category_id, subcategory_id, unit_of_measure, default_expiry_days,
                      par_level, max_holding_amount, purchase_location))
                conn.commit()
                product_id = cursor.lastrowid
                return {"success": True, "message": f"Product '{name}' created successfully.", "product_id": product_id}
        except sqlite3.IntegrityError:
            return {"success": False, "message": f"Product name '{name}' already exists."}
        except sqlite3.Error as e:
            return {"success": False, "message": f"Database error creating product: {e}"}

    def get_product(self, product_id):
        """Retrieves a product by its ID, including category and subcategory names."""
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT
                        p.id, p.name, p.unit_of_measure, p.default_expiry_days,
                        p.par_level, p.max_holding_amount, p.purchase_location,
                        p.consumption_override_rate, p.category_id, p.subcategory_id,
                        c.name AS category_name,
                        s.name AS subcategory_name
                    FROM products p
                    LEFT JOIN categories c ON p.category_id = c.id
                    LEFT JOIN subcategories s ON p.subcategory_id = s.id
                    WHERE p.id = ?
                """, (product_id,))
                row = cursor.fetchone()
                return dict(row) if row else None
        except sqlite3.Error as e:
            print(f"Database error getting product by ID {product_id}: {e}")
            return None # Or raise error

    def get_product_details(self, product_id):
        """
        Retrieves a product by its ID, and enhances it with current on-hand inventory
        and the nearest expiry date from inventory_items.
        """
        product = self.get_product(product_id)
        if not product:
            return None

        # Calculate current_on_hand_inventory
        # self.get_total_item_quantity already handles product_id or name
        current_on_hand_inventory = self.get_total_item_quantity(product_id)
        product['current_on_hand_inventory'] = current_on_hand_inventory

        # Find nearest_expiry_date
        nearest_expiry_date_str = "N/A"
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT expiry_date
                    FROM inventory_items
                    WHERE product_id = ?
                    ORDER BY expiry_date ASC
                    LIMIT 1
                ''', (product_id,))
                row = cursor.fetchone()
                if row and row['expiry_date']:
                    nearest_expiry_date_str = row['expiry_date']
        except sqlite3.Error as e:
            print(f"Database error getting nearest expiry date for product ID {product_id}: {e}")
            # nearest_expiry_date_str remains "N/A" or could be set to an error indicator

        product['nearest_expiry_date'] = nearest_expiry_date_str
        return product

    def get_daily_consumption(self, product_id, days=30):
        """
        Retrieves daily consumption for a product over a specified number of days.
        - product_id: The ID of the product.
        - days: The number of past days to fetch data for.
        """
        consumption_data = []
        today = date.today()
        start_date = today - timedelta(days=days)
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT
                        strftime('%Y-%m-%d', consumed_date) as consumption_date,
                        SUM(quantity_consumed_this_time) as total_quantity_consumed
                    FROM historical_items
                    WHERE product_id = ? AND consumed_date >= ?
                    GROUP BY consumption_date
                    ORDER BY consumption_date ASC
                ''', (product_id, start_date.isoformat()))
                rows = cursor.fetchall()
                for row in rows:
                    consumption_data.append(dict(row))
        except sqlite3.Error as e:
            print(f"Database error getting daily consumption for product ID {product_id}: {e}")
            # Depending on requirements, could return empty list or raise error
        return consumption_data

    def get_monthly_consumption(self, product_id, months=12):
        """
        Retrieves monthly consumption for a product over a specified number of months.
        - product_id: The ID of the product.
        - months: The number of past months to fetch data for.
        """
        consumption_data = []
        # Calculate the first day of the month 'months' ago
        # This is a bit tricky to get precisely the Nth month back.
        # A simpler approach for SQL is to filter for dates >= the first day of that month.
        today = date.today()
        # Approximate start_date: go back (months * average_days_in_month)
        # A more robust way is to iterate back month by month or use date library functions
        # For SQL, we can use date functions if available and portable,
        # or filter for a wider range and then process in Python if needed.
        # Simplest for SQLite: calculate the date string for "N months ago"
        # and group by YYYY-MM.

        # Calculate the first day of the current month
        first_day_current_month = today.replace(day=1)

        # Iterate backwards to find the first day of the month N months ago
        target_month_date = first_day_current_month
        for _ in range(months -1): # Subtract 1 because current month counts as one of the 'months'
            # Move to the last day of the previous month
            target_month_date = (target_month_date - timedelta(days=1)).replace(day=1)

        start_month_iso = target_month_date.isoformat()

        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT
                        strftime('%Y-%m', consumed_date) as consumption_month,
                        SUM(quantity_consumed_this_time) as total_quantity_consumed
                    FROM historical_items
                    WHERE product_id = ? AND date(consumed_date) >= date(?)
                    GROUP BY consumption_month
                    ORDER BY consumption_month ASC
                ''', (product_id, start_month_iso))
                rows = cursor.fetchall()
                for row in rows:
                    consumption_data.append(dict(row))
        except sqlite3.Error as e:
            print(f"Database error getting monthly consumption for product ID {product_id}: {e}")
        return consumption_data

    def get_daily_inventory_history(self, product_id, days=30):
        """
        Retrieves the daily inventory quantity for a product over a specified number of past days.
        - product_id: The ID of the product.
        - days: The number of past days to fetch data for (defaults to 30).
        Returns a list of dictionaries: [{'inventory_date': 'YYYY-MM-DD', 'quantity_on_hand': float}]
        """
        if not isinstance(product_id, int):
            raise ValueError("product_id must be an integer.")
        if not isinstance(days, int) or days <= 0:
            raise ValueError("days must be a positive integer.")

        today = date.today()
        report_start_date = today - timedelta(days=days - 1)
        events = []

        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()

                # Fetch purchase events
                cursor.execute('''
                    SELECT purchase_date, original_quantity_string
                    FROM inventory_items
                    WHERE product_id = ?
                ''', (product_id,))
                for row in cursor.fetchall():
                    try:
                        event_date = date.fromisoformat(row['purchase_date'])
                        quantity = self._parse_quantity_string(row['original_quantity_string'])
                        if quantity > 0:
                            events.append({'date': event_date, 'change': quantity, 'type': 'purchase'})
                        else:
                            print(f"Warning: Skipping purchase event with non-positive quantity for product_id {product_id}: {row}")
                    except (ValueError, TypeError) as e:
                        print(f"Warning: Skipping purchase event due to invalid data for product_id {product_id}: {row} - Error: {e}")

                # Fetch consumption events
                cursor.execute('''
                    SELECT consumed_date, quantity_consumed_this_time
                    FROM historical_items
                    WHERE product_id = ?
                ''', (product_id,))
                for row in cursor.fetchall():
                    try:
                        event_date = date.fromisoformat(row['consumed_date'])
                        quantity = float(row['quantity_consumed_this_time'])
                        if quantity > 0:
                            events.append({'date': event_date, 'change': -quantity, 'type': 'consumption'})
                        else:
                            print(f"Warning: Skipping consumption event with non-positive quantity for product_id {product_id}: {row}")
                    except (ValueError, TypeError) as e:
                        print(f"Warning: Skipping consumption event due to invalid data for product_id {product_id}: {row} - Error: {e}")

        except sqlite3.Error as e:
            print(f"Database error retrieving inventory history for product ID {product_id}: {e}")
            return []

        # Sort events: by date, then by type (purchases first on same day)
        events.sort(key=lambda x: (x['date'], 0 if x['type'] == 'purchase' else 1))

        daily_inventory_data = []
        current_simulated_stock = 0.0
        event_idx = 0

        # Pre-window stock calculation: Accumulate stock changes before the report_start_date
        while event_idx < len(events) and events[event_idx]['date'] < report_start_date:
            current_simulated_stock += events[event_idx]['change']
            event_idx += 1

        # Simulate and record for the report window
        for i in range(days):
            current_report_day = report_start_date + timedelta(days=i)

            # Process events for the current_report_day
            while event_idx < len(events) and events[event_idx]['date'] == current_report_day:
                current_simulated_stock += events[event_idx]['change']
                event_idx += 1

            daily_inventory_data.append({
                'inventory_date': current_report_day.isoformat(),
                'quantity_on_hand': max(0, round(current_simulated_stock, 3))
            })

        return daily_inventory_data

    def get_product_by_name(self, name):
        """Retrieves a product by its name."""
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM products WHERE LOWER(name) = LOWER(?)", (name,))
                row = cursor.fetchone()
                return dict(row) if row else None
        except sqlite3.Error as e:
            print(f"Database error getting product by name '{name}': {e}")
            return None

    def get_all_products(self, search_term=None, category=None, purchase_location=None,
                         sort_by='name', sort_order='ASC', page=None, per_page=None):
        """
        Retrieves products from the products table with filtering, sorting, and pagination.
        - search_term: Filters by product name (case-insensitive).
        - category: Filters by category name (case-insensitive).
        - purchase_location: Filters by purchase location (case-insensitive).
        - sort_by: Column to sort by ('name', 'category', 'subcategory', 'purchase_location').
                   Defaults to 'name'. Invalid values also default to 'name'.
        - sort_order: 'ASC' or 'DESC'. Defaults to 'ASC'.
        - page: For pagination, the page number to retrieve. Defaults to 1.
        - per_page: For pagination, items per page. Defaults to 10.
        """
        items = []
        params = []

        # Base query
        query = """
            SELECT
                p.id, p.name, p.unit_of_measure, p.default_expiry_days,
                p.par_level, p.max_holding_amount, p.purchase_location,
                p.consumption_override_rate, p.category_id, p.subcategory_id,
                c.name AS category_name,
                s.name AS subcategory_name
            FROM products p
            LEFT JOIN categories c ON p.category_id = c.id
            LEFT JOIN subcategories s ON p.subcategory_id = s.id
        """

        # Filtering
        where_clauses = []
        if search_term:
            where_clauses.append("LOWER(p.name) LIKE ?")
            params.append(f"%{search_term.lower()}%")
        if category: # This now filters by category NAME from the joined 'categories' table
            where_clauses.append("LOWER(c.name) = ?")
            params.append(category.lower())
        if purchase_location:
            where_clauses.append("LOWER(p.purchase_location) = ?")
            params.append(purchase_location.lower())

        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)

        # Sorting
        valid_sort_columns = {
            'name': 'p.name',
            'category': 'c.name',
            'subcategory': 's.name',
            'purchase_location': 'p.purchase_location'
            # Add other p.columns if needed for sorting, e.g. p.default_expiry_days
        }
        # Default to 'p.name' if sort_by is invalid or not in valid_sort_columns
        sort_column = valid_sort_columns.get(sort_by.lower(), 'p.name')

        sort_order_upper = sort_order.upper()
        if sort_order_upper not in ['ASC', 'DESC']:
            sort_order_upper = 'ASC' # Default to 'ASC'

        query += f" ORDER BY {sort_column} {sort_order_upper}, p.id {sort_order_upper}" # Added p.id for stable sort

        # Pagination
        # If page or per_page is None, or if per_page is not a positive integer,
        # do not apply LIMIT and OFFSET, effectively fetching all products.
        if page is not None and per_page is not None and \
           isinstance(page, int) and isinstance(per_page, int) and \
           page > 0 and per_page > 0:
            offset = (page - 1) * per_page
            query += " LIMIT ? OFFSET ?"
            params.extend([per_page, offset])
        # No 'else' or 'elif' here: if conditions are not met, pagination is skipped.

        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, tuple(params))
                rows = cursor.fetchall()
                for row in rows:
                    items.append(dict(row))
        except sqlite3.Error as e:
            print(f"Database error fetching all products with filters: {e}")
        return items

    def get_product_count(self, search_term=None, category=None, purchase_location=None):
        """
        Gets the total number of products, filtered by search_term, category, and purchase_location.
        """
        params = []
        query = """
            SELECT COUNT(p.id) as count
            FROM products p
            LEFT JOIN categories c ON p.category_id = c.id
        """ # s (subcategories) is not needed for count if not filtering by subcategory name or id

        where_clauses = []
        if search_term:
            where_clauses.append("LOWER(p.name) LIKE ?") # Alias product table as p
            params.append(f"%{search_term.lower()}%")
        if category: # This now filters by category NAME from the joined 'categories' table
            where_clauses.append("LOWER(c.name) = ?") # Alias category table as c
            params.append(category.lower())
        if purchase_location:
            where_clauses.append("LOWER(p.purchase_location) = ?") # Alias product table as p
            params.append(purchase_location.lower())

        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)

        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, tuple(params))
                result = cursor.fetchone()
                return result['count'] if result else 0
        except sqlite3.Error as e:
            print(f"Database error getting product count: {e}")
            return 0

    def get_all_categories(self):
        """Retrieves all category names from the 'categories' table."""
        # This method now fetches from the dedicated 'categories' table.
        category_names = []
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM categories ORDER BY name ASC")
                rows = cursor.fetchall()
                for row in rows:
                    category_names.append(row['name'])
        except sqlite3.Error as e:
            print(f"Database error fetching all category names: {e}")
        return category_names

    def get_all_purchase_locations(self):
        """Retrieves all unique purchase location names from the products table."""
        locations = []
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT DISTINCT purchase_location FROM products WHERE purchase_location IS NOT NULL ORDER BY purchase_location ASC")
                rows = cursor.fetchall()
                for row in rows:
                    locations.append(row['purchase_location'])
        except sqlite3.Error as e:
            print(f"Database error fetching all purchase locations: {e}")
        return locations

    def get_products_for_projection_list(self, search_term=None, category=None, purchase_location=None,
                                         sort_by='name', sort_order='ASC', page=1, per_page=10):
        """
        Retrieves a paginated and filtered list of products for the demand projection page.
        This is similar to get_all_products but specifically for listing products
        for which projections will be calculated.
        """
        # This method is essentially a wrapper or identical to get_all_products.
        # Re-using get_all_products logic directly.
        return self.get_all_products(
            search_term=search_term,
            category=category,
            purchase_location=purchase_location,
            sort_by=sort_by,
            sort_order=sort_order,
            page=page,
            per_page=per_page
        )

    def get_products_for_projection_list_count(self, search_term=None, category=None, purchase_location=None):
        """
        Gets the total number of products for the projection list, filtered by product attributes.
        This is similar to get_product_count.
        """
        # This method is essentially a wrapper or identical to get_product_count.
        # Re-using get_product_count logic directly.
        return self.get_product_count(
            search_term=search_term,
            category=category,
            purchase_location=purchase_location
        )

    def update_product(self, product_id, name, category, subcategory, unit_of_measure,
                       default_expiry_days, par_level, max_holding_amount, purchase_location):
        """Updates an existing product in the products table."""
        if not all([name, unit_of_measure, default_expiry_days is not None]):
             return {"success": False, "message": "Missing required product fields for update."}
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE products SET
                    name = ?, category = ?, subcategory = ?, unit_of_measure = ?,
                    default_expiry_days = ?, par_level = ?, max_holding_amount = ?, purchase_location = ?
                    WHERE id = ?
                ''', (name, category, subcategory, unit_of_measure, default_expiry_days,
                      par_level, max_holding_amount, purchase_location, product_id))
                conn.commit()
                if cursor.rowcount == 0:
                    return {"success": False, "message": f"Product with ID {product_id} not found."}
                return {"success": True, "message": f"Product ID {product_id} updated successfully."}
        except sqlite3.IntegrityError:
            return {"success": False, "message": f"Product name '{name}' may already exist for another product."}
        except sqlite3.Error as e:
            return {"success": False, "message": f"Database error updating product: {e}"}

    def save_consumption_overrides(self, product_overrides: list):
        """
        Saves consumption override rates for products.
        - product_overrides: A list of dictionaries, where each dictionary is
                             {'product_id': int, 'override_rate': float_or_none_or_empty_str}.
        """
        if not isinstance(product_overrides, list):
            return {"success": False, "message": "Invalid input: product_overrides must be a list."}

        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                updates_made = 0
                errors_encountered = 0

                for override_item in product_overrides:
                    if not isinstance(override_item, dict) or \
                       'product_id' not in override_item or \
                       'override_rate' not in override_item:
                        print(f"Skipping invalid override item: {override_item}")
                        errors_encountered += 1
                        continue

                    product_id = override_item['product_id']
                    override_rate_input = override_item['override_rate']

                    final_override_rate = None # Default to NULL

                    if isinstance(override_rate_input, str):
                        if override_rate_input.strip() == "":
                            final_override_rate = None
                        else:
                            try:
                                final_override_rate = float(override_rate_input)
                            except ValueError:
                                print(f"Warning: Could not parse override_rate '{override_rate_input}' for product ID {product_id}. Setting to NULL.")
                                final_override_rate = None # Explicitly NULL if unparsable
                    elif isinstance(override_rate_input, (int, float)):
                        final_override_rate = float(override_rate_input)
                    # If override_rate_input is None, final_override_rate remains None (SQL NULL)

                    try:
                        cursor.execute('''
                            UPDATE products
                            SET consumption_override_rate = ?
                            WHERE id = ?
                        ''', (final_override_rate, product_id))
                        if cursor.rowcount > 0:
                            updates_made += 1
                        # No error if product_id not found, rowcount will be 0
                    except sqlite3.Error as e_item:
                        print(f"Error updating override for product ID {product_id}: {e_item}")
                        errors_encountered += 1

                conn.commit()

                message = f"Consumption overrides saved. {updates_made} products updated."
                if errors_encountered > 0:
                    message += f" {errors_encountered} items had errors."

                return {"success": errors_encountered == 0, "message": message, "updates_made": updates_made, "errors": errors_encountered}

        except sqlite3.Error as e:
            return {"success": False, "message": f"Database error saving consumption overrides: {e}"}

    def _parse_quantity_string(self, quantity_str):
        """Attempts to parse a quantity string (e.g., "2 lbs", "10 units", "1") into a float.
           Returns float if parsable, otherwise None or a specific handling.
           For simplicity, we'll try to extract the first numeric part.
           - If the string is "a loaf", "one piece", etc., it's treated as 1.0.
           - If the string is "2 lbs", "0.5 kg", it extracts 2.0 or 0.5.
           - If the string is just a number "10", it returns 10.0.
           - If unparseable or empty in a numeric context, returns 0.0.
        """
        if isinstance(quantity_str, (int, float)):
            return float(quantity_str)
        
        s_quantity_str = str(quantity_str).strip()
        if not s_quantity_str:
            return 0.0

        parts = s_quantity_str.split()
        try:
            # Try to convert the first part to a float
            return float(parts[0])
        except (ValueError, IndexError):
            # If the first part is not a number (e.g., "a loaf", "one unit")
            # and the string is not empty, consider it as 1.0.
            # This helps in contexts where such string quantities imply a single unit.
            if s_quantity_str: # Check if the original stripped string was non-empty
                return 1.0 
            return 0.0 # Default for completely unparseable or empty strings

    def add_inventory_stock(self, product_id, quantity_str, purchase_date_str):
        """Adds a new inventory item stock linked to a product."""
        product = self.get_product(product_id)
        if not product:
            return {"success": False, "message": f"Product with ID {product_id} not found."}

        try:
            purchase_dt = date.fromisoformat(purchase_date_str)
            expiry_dt = purchase_dt + timedelta(days=int(product['default_expiry_days']))
        except (ValueError, TypeError) as e:
            return {"success": False, "message": f"Invalid date or expiry day format for product {product['name']}: {e}"}

        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO inventory_items 
                    (product_id, name, quantity, purchase_date, expiry_date, original_quantity_string)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (product_id, product['name'], str(quantity_str), purchase_dt.isoformat(),
                      expiry_dt.isoformat(), str(quantity_str)))
                conn.commit()
                stock_item_id = cursor.lastrowid # Get the ID of the inserted item
            print(f"Added stock to DB: {product['name']} ({quantity_str}), Expires: {expiry_dt.isoformat()}")
            return {"success": True, "message": f"Stock for '{product['name']}' added successfully.", "stock_item_id": stock_item_id}
        except sqlite3.Error as e:
            print(f"Database error adding inventory stock: {e}")
            return {"success": False, "message": f"Database error: {e}"}

    # This method is called by the Excel upload in app.py
    # It now relies on product_id for linking, and creates product if not found.
    def add_item_to_list(self, name, quantity_str, purchase_date_str, expiry_days,
                         category=None, subcategory=None, par_level=0, max_holding_amount=0, # Text category/subcategory from Excel
                         purchase_location=None, unit_of_measure=None,
                         # The following are for handling pending actions from app.py
                         confirmed_action=None, temp_category_id=None):
        """
        Adds an item to inventory. Handles product creation, category/subcategory resolution,
        and potential user confirmation steps for new categories/subcategories.
        """
        product_data_for_confirmation = {
            "name": name, "quantity_str": quantity_str, "purchase_date_str": purchase_date_str,
            "expiry_days": expiry_days, "category": category, "subcategory": subcategory,
            "par_level": par_level, "max_holding_amount": max_holding_amount,
            "purchase_location": purchase_location, "unit_of_measure": unit_of_measure
        }

        product_info = self.get_product_by_name(name)
        product_id_to_use = None
        category_id_to_use = None
        subcategory_id_to_use = None
        action_required = None
        confirmation_details = {}
        warnings = []

        if product_info:
            product_id_to_use = product_info['id']
            category_id_to_use = product_info.get('category_id')
            subcategory_id_to_use = product_info.get('subcategory_id')
            print(f"Product '{name}' found with ID {product_id_to_use}. Using existing product.")

            if category and category_id_to_use:
                db_category_name = self.get_category_name_by_id(category_id_to_use)
                if db_category_name and db_category_name.lower() != category.strip().lower():
                    warnings.append(f"Category '{category.strip()}' in Excel for existing product '{name}' differs from DB category '{db_category_name}'. DB category retained.")

            if subcategory and subcategory_id_to_use:
                # Need to fetch subcategory name by its ID to compare
                # This assumes we have a method like get_subcategory_by_id(id) or can adapt get_subcategory_by_name_and_category_id
                # For now, let's assume a direct fetch or skip detailed name check for subcategory if complex
                # This part can be enhanced if a get_subcategory_by_id method is added.
                # For simplicity, we'll rely on IDs for existing products.
                pass # Placeholder for potential subcategory name mismatch warning

            if unit_of_measure and unit_of_measure.strip() and product_info.get('unit_of_measure') != unit_of_measure.strip():
                warnings.append(f"UoM for '{name}' in Excel ('{unit_of_measure.strip()}') differs from DB ('{product_info.get('unit_of_measure')}'). DB UoM retained.")

        else: # New Product
            if not category or not category.strip():
                return {"success": False, "message": f"Category name is missing in Excel for new product '{name}'. Product not added.", "warnings": warnings}

            excel_category_name = category.strip()

            if confirmed_action == "confirmed_new_category":
                # User confirmed, create the new category
                add_cat_result = self.add_category(excel_category_name)
                if not add_cat_result.get("success"):
                    return {"success": False, "message": f"Failed to create new category '{excel_category_name}': {add_cat_result.get('message')}", "warnings": warnings}
                category_id_to_use = add_cat_result['category_id']

                if subcategory and subcategory.strip():
                    excel_subcategory_name = subcategory.strip()
                    # User confirmed new category, now also create the new subcategory under it
                    add_subcat_result = self.add_subcategory(excel_subcategory_name, category_id_to_use)
                    if not add_subcat_result.get("success"):
                         return {"success": False, "message": f"Failed to create new subcategory '{excel_subcategory_name}' for new category '{excel_category_name}': {add_subcat_result.get('message')}", "warnings": warnings}
                    subcategory_id_to_use = add_subcat_result['subcategory_id']
                # Proceed to create product

            elif confirmed_action == "confirmed_new_subcategory" and temp_category_id is not None:
                category_id_to_use = temp_category_id # Use the ID of the existing category
                excel_subcategory_name = subcategory.strip() # Should be present if this action was triggered
                add_subcat_result = self.add_subcategory(excel_subcategory_name, category_id_to_use)
                if not add_subcat_result.get("success"):
                    return {"success": False, "message": f"Failed to create new subcategory '{excel_subcategory_name}': {add_subcat_result.get('message')}", "warnings": warnings}
                subcategory_id_to_use = add_subcat_result['subcategory_id']
                # Proceed to create product

            else: # Not a confirmed action, check existing categories/subcategories
                existing_category_obj = self.get_category_by_name(excel_category_name)
                if existing_category_obj:
                    category_id_to_use = existing_category_obj['id']
                    if subcategory and subcategory.strip():
                        excel_subcategory_name = subcategory.strip()
                        existing_subcategory_obj = self.get_subcategory_by_name_and_category_id(excel_subcategory_name, category_id_to_use)
                        if existing_subcategory_obj:
                            subcategory_id_to_use = existing_subcategory_obj['id']
                        else: # New subcategory for existing category
                            action_required = "confirm_new_subcategory"
                            confirmation_details = {
                                "category_id": category_id_to_use,
                                "category_name": existing_category_obj['name'],
                                "new_subcategory_name": excel_subcategory_name
                            }
                            return {"success": False, "action_required": action_required, "confirmation_details": confirmation_details, "product_data": product_data_for_confirmation, "warnings": warnings}
                    # Else (no subcategory provided or subcategory found), proceed to create product with existing category_id_to_use
                else: # New category
                    action_required = "confirm_new_category"
                    confirmation_details = {
                        "new_category_name": excel_category_name,
                        "new_subcategory_name": subcategory.strip() if subcategory else None
                    }
                    return {"success": False, "action_required": action_required, "confirmation_details": confirmation_details, "product_data": product_data_for_confirmation, "warnings": warnings}

            # Create the product if it's new and category/subcategory are resolved (either existed or confirmed & created)
            print(f"Attempting to create new product '{name}' with CategoryID: {category_id_to_use}, SubcategoryID: {subcategory_id_to_use}")
            if not unit_of_measure: # Unit of measure is mandatory for new products
                return {"success": False, "message": f"Unit of Measure is missing in Excel for new product '{name}'. Product not added.", "warnings": warnings}

            create_product_result = self.create_product(
                name=name,
                category_id=category_id_to_use,
                subcategory_id=subcategory_id_to_use,
                unit_of_measure=unit_of_measure,
                default_expiry_days=expiry_days,
                par_level=par_level,
                max_holding_amount=max_holding_amount,
                purchase_location=purchase_location
            )
            if create_product_result.get("success"):
                product_id_to_use = create_product_result.get("product_id")
                # product_info = self.get_product(product_id_to_use) # Not strictly needed here, product_id_to_use is enough
                print(f"Product '{name}' created successfully with ID {product_id_to_use}.")
            else:
                return {"success": False, "message": create_product_result.get("message", f"Failed to create product '{name}'."), "warnings": warnings}

        # --- Common logic for adding inventory item once product_id_to_use is determined ---
        if product_id_to_use is None:
             # This case should ideally be caught by earlier checks (e.g., product not found and action not confirmed)
            return {"success": False, "message": f"Could not determine product ID for '{name}'. Inventory item not added.", "warnings": warnings}

        try:
            purchase_dt = date.fromisoformat(purchase_date_str)
            # Use default_expiry_days from the product (either existing or newly created)
            # Need to fetch the product if it was just created to get its default_expiry_days
            # However, the expiry_days param is for THIS BATCH from Excel, not necessarily product default
            batch_expiry_dt = purchase_dt + timedelta(days=int(expiry_days))
        except (ValueError, TypeError) as e:
            return {"success": False, "message": f"Invalid purchase date '{purchase_date_str}' or expiry days '{expiry_days}' for item '{name}': {e}", "warnings": warnings}

        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO inventory_items
                    (product_id, name, quantity, purchase_date, expiry_date, original_quantity_string)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (product_id_to_use, name, str(quantity_str), purchase_dt.isoformat(),
                      batch_expiry_dt.isoformat(), str(quantity_str)))
                conn.commit()
                item_id = cursor.lastrowid
                print(f"Successfully added item '{name}' (Batch ID: {item_id}) to inventory. Expires: {batch_expiry_dt.isoformat()}")
                return {"success": True, "message": f"Item '{name}' added to inventory.", "item_id": item_id, "product_id": product_id_to_use, "warnings": warnings}
        except sqlite3.Error as e:
            return {"success": False, "message": f"Database error adding item '{name}' to inventory: {e}", "warnings": warnings}


    def get_current_inventory(self, search_term=None, category=None, purchase_location=None,
                              expiry_start_date=None, expiry_end_date=None,
                              sort_by='expiry_date', sort_order='ASC',
                              page=1, per_page=10):
        """
        Retrieves items from the current inventory, joined with product details,
        with filtering, sorting, and pagination.
        - search_term: Filters by product name (p.name).
        - category: Filters by product category (p.category).
        - purchase_location: Filters by product purchase location (p.purchase_location).
        - expiry_start_date: Filters for expiry_date >= this date.
        - expiry_end_date: Filters for expiry_date <= this date.
        - sort_by: Column to sort by ('product_name', 'category', 'purchase_location',
                   'expiry_date', 'purchase_date', 'quantity'). Defaults to 'expiry_date'.
        - sort_order: 'ASC' or 'DESC'. Defaults to 'ASC'.
        - page: For pagination.
        - per_page: For pagination.
        """
        items = []
        params = []

        base_query = """
            SELECT
                ii.id, ii.product_id, ii.quantity, ii.purchase_date, ii.expiry_date,
                ii.original_quantity_string,
                p.name AS product_name,
                p.unit_of_measure, p.par_level, p.max_holding_amount, p.purchase_location,
                c.name AS category_name,
                sc.name AS subcategory_name
            FROM inventory_items ii
            JOIN products p ON ii.product_id = p.id
            LEFT JOIN categories c ON p.category_id = c.id
            LEFT JOIN subcategories sc ON p.subcategory_id = sc.id
        """

        where_clauses = []
        if search_term:
            where_clauses.append("LOWER(p.name) LIKE ?")
            params.append(f"%{search_term.lower()}%")
        if category: # Filter by category NAME from joined 'categories' table
            where_clauses.append("LOWER(c.name) = ?")
            params.append(category.lower())
        if purchase_location:
            where_clauses.append("LOWER(p.purchase_location) = ?")
            params.append(purchase_location.lower())
        if expiry_start_date:
            where_clauses.append("ii.expiry_date >= ?")
            params.append(expiry_start_date)
        if expiry_end_date:
            where_clauses.append("ii.expiry_date <= ?")
            params.append(expiry_end_date)

        if where_clauses:
            base_query += " WHERE " + " AND ".join(where_clauses)

        # Sorting
        valid_sort_columns = {
            'product_name': 'p.name',
            'category_name': 'c.name', # Updated to sort by category_name
            'purchase_location': 'p.purchase_location',
            'expiry_date': 'ii.expiry_date',
            'purchase_date': 'ii.purchase_date',
            # Sorting by quantity can be tricky due to its string nature.
            # CAST to REAL might work for purely numeric strings.
            'quantity': 'CAST(ii.quantity AS REAL)'
        }
        sort_column = valid_sort_columns.get(sort_by.lower(), 'ii.expiry_date')

        sort_order_upper = sort_order.upper()
        if sort_order_upper not in ['ASC', 'DESC']:
            sort_order_upper = 'ASC'

        base_query += f" ORDER BY {sort_column} {sort_order_upper}, ii.id {sort_order_upper}" # Secondary sort for stability

        # Pagination
        if page is not None and per_page is not None and page > 0 and per_page > 0:
            offset = (page - 1) * per_page
            base_query += " LIMIT ? OFFSET ?"
            params.extend([per_page, offset])
        elif per_page is not None and per_page > 0:
            base_query += " LIMIT ?"
            params.append(per_page)

        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(base_query, tuple(params))
                rows = cursor.fetchall()
                for row in rows:
                    item = dict(row)
                    # Convert date strings to date objects
                    if item.get('purchase_date'):
                        item['purchase_date'] = date.fromisoformat(item['purchase_date'])
                    if item.get('expiry_date'):
                        item['expiry_date'] = date.fromisoformat(item['expiry_date'])
                    items.append(item)
        except sqlite3.Error as e:
            print(f"Database error fetching current inventory with filters: {e}")
        return items

    def get_current_inventory_count(self, search_term=None, category=None, purchase_location=None,
                                    expiry_start_date=None, expiry_end_date=None):
        """
        Gets the total count of current inventory items based on filters.
        """
        params = []
        query = """
            SELECT COUNT(ii.id) as count
            FROM inventory_items ii
            JOIN products p ON ii.product_id = p.id
            LEFT JOIN categories c ON p.category_id = c.id
        """

        where_clauses = []
        if search_term:
            where_clauses.append("LOWER(p.name) LIKE ?")
            params.append(f"%{search_term.lower()}%")
        if category: # Filter by category NAME
            where_clauses.append("LOWER(c.name) = ?")
            params.append(category.lower())
        if purchase_location:
            where_clauses.append("LOWER(p.purchase_location) = ?")
            params.append(purchase_location.lower())
        if expiry_start_date:
            where_clauses.append("ii.expiry_date >= ?")
            params.append(expiry_start_date)
        if expiry_end_date:
            where_clauses.append("ii.expiry_date <= ?")
            params.append(expiry_end_date)

        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)

        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, tuple(params))
                result = cursor.fetchone()
                return result['count'] if result else 0
        except sqlite3.Error as e:
            print(f"Database error getting current inventory count: {e}")
            return 0

    def get_current_inventory_categories(self):
        """Retrieves unique categories from products currently in inventory."""
        categories = []
        query = """
            SELECT DISTINCT c.name
            FROM inventory_items ii
            JOIN products p ON ii.product_id = p.id
            JOIN categories c ON p.category_id = c.id
            WHERE c.name IS NOT NULL
            ORDER BY c.name ASC
        """
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query)
                rows = cursor.fetchall()
                for row in rows:
                    categories.append(row['name']) # Select c.name
        except sqlite3.Error as e:
            print(f"Database error fetching current inventory categories: {e}")
        return categories

    def get_current_inventory_purchase_locations(self):
        """Retrieves unique purchase locations from products currently in inventory."""
        locations = []
        query = """
            SELECT DISTINCT p.purchase_location
            FROM products p
            JOIN inventory_items ii ON p.id = ii.product_id
            WHERE p.purchase_location IS NOT NULL
            ORDER BY p.purchase_location ASC
        """
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query)
                rows = cursor.fetchall()
                for row in rows:
                    locations.append(row['purchase_location'])
        except sqlite3.Error as e:
            print(f"Database error fetching current inventory purchase locations: {e}")
        return locations

    def get_inventory_batches_for_product(self, product_id, limit=None, order_by_purchase_desc=False, order_by_id_desc=False):
        """
        Retrieves specific inventory batches for a given product_id.
        Can be ordered by purchase_date descending or id descending, and limited.
        """
        items = []
        if not product_id: # Ensure product_id is not None or empty before query
            return items

        # Ensure product_id is an integer if it's coming from a form/URL
        try:
            valid_product_id = int(product_id)
        except ValueError:
            print(f"Invalid product_id format: {product_id}")
            return items # Or raise an error

        query = '''
            SELECT
                ii.id, ii.product_id, ii.quantity, ii.purchase_date, ii.expiry_date,
                ii.original_quantity_string,
                p.name AS product_name, p.category, p.subcategory, p.unit_of_measure
            FROM inventory_items ii
            JOIN products p ON ii.product_id = p.id
            WHERE ii.product_id = ?
        '''
        params = [valid_product_id]

        if order_by_id_desc:
            query += " ORDER BY ii.id DESC"
        elif order_by_purchase_desc:
            query += " ORDER BY ii.purchase_date DESC, ii.id DESC"
        else: # Default order (e.g., by expiry date as in get_current_inventory)
            query += " ORDER BY ii.expiry_date ASC, ii.id ASC"


        if limit is not None:
            query += " LIMIT ?"
            params.append(limit)

        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, tuple(params))
                rows = cursor.fetchall()
                for row in rows:
                    item = dict(row)
                    # Convert date strings to date objects
                    if item.get('purchase_date'):
                        item['purchase_date'] = date.fromisoformat(item['purchase_date'])
                    if item.get('expiry_date'):
                        item['expiry_date'] = date.fromisoformat(item['expiry_date'])
                    items.append(item)
        except sqlite3.Error as e:
            print(f"Database error fetching inventory batches for product ID {valid_product_id}: {e}")
        return items

    def get_shopping_list_items(self, store_filter=None, search_term=None):
        """
        Generates a shopping list based on current inventory, consumption rates,
        par levels, and purchase locations.
        """
        SOBEYS_FREQUENCY_WEEKS = 1
        COSTCO_FREQUENCY_WEEKS = 3
        shopping_list = []

        # get_current_inventory() now returns items with product details joined
        inventory_with_product_details = self.get_current_inventory()

        # We need a unique list of product_ids that are below par to avoid multiple projections for the same product
        # if it has multiple inventory batches.
        # However, par_level is per product, so we should iterate through products that have par levels.

        all_products = self.get_all_products()
        products_to_check = [p for p in all_products if p.get('par_level', 0) is not None and p.get('par_level', 0) > 0]

        for product in products_to_check:
            product_id = product['id']
            product_name = product['name']
            par_level = product.get('par_level', 0.0)
            purchase_location = product.get('purchase_location')
            unit_of_measure = product.get('unit_of_measure', 'units')

            # Skip if par_level is not set or not positive
            if par_level <= 0:
                continue

            projection_days_for_item = 0
            if purchase_location == 'Sobeys':
                projection_days_for_item = SOBEYS_FREQUENCY_WEEKS * 7
            elif purchase_location == 'Costco':
                projection_days_for_item = COSTCO_FREQUENCY_WEEKS * 7
            else:
                # If purchase location doesn't match known cycles, skip or use a default.
                # For now, skipping.
                continue

            # Use project_demand with product_id
            demand_projection = self.project_demand(product_id, lookback_days=30, projection_days=projection_days_for_item)

            if not demand_projection.get("success"):
                print(f"Skipping shopping list item for {product_name} due to projection error: {demand_projection.get('message')}")
                continue

            avg_daily_consumption = demand_projection.get('avg_daily_consumption', 0.0)
            # current_numeric_quantity is the total stock for this product_id
            current_numeric_quantity = self.get_total_item_quantity(product_id)

            target_stock_after_shopping = par_level + (avg_daily_consumption * projection_days_for_item)
            recommended_purchase_amount = target_stock_after_shopping - current_numeric_quantity
            recommended_purchase_amount = max(0, round(recommended_purchase_amount, 2))

            if recommended_purchase_amount > 0:
                # Find the earliest expiry date for this product from inventory for display (optional)
                earliest_expiry_date_str = "N/A"
                relevant_inventory_batches = [
                    item for item in inventory_with_product_details if item['product_id'] == product_id
                ]
                if relevant_inventory_batches:
                    earliest_expiry_date_str = min(item['expiry_date'] for item in relevant_inventory_batches).isoformat()

                # Current quantity display string (sum of original strings might be complex, so just use numeric total with unit)
                current_quantity_display = f"{current_numeric_quantity:.2f} {unit_of_measure}"


                shopping_list_item = {
                    'product_id': product_id,
                    'name': product_name, # This is product_name from products table
                    'current_quantity_display': current_quantity_display,
                    'current_numeric_quantity': current_numeric_quantity,
                    'unit_of_measure': unit_of_measure,
                    'purchase_location': purchase_location,
                    'earliest_expiry_date': earliest_expiry_date_str, # Informational
                    'recommended_purchase_amount': recommended_purchase_amount,
                    'par_level': par_level,
                    'days_to_next_shop': projection_days_for_item,
                    'avg_daily_consumption': round(avg_daily_consumption, 2)
                }
                shopping_list.append(shopping_list_item)

        # Filter logic (remains largely the same, but fields might have changed names slightly)
        if store_filter:
            shopping_list = [
                item for item in shopping_list
                if item['purchase_location'] and item['purchase_location'].lower() == store_filter.lower()
            ]

        if search_term:
            shopping_list = [
                item for item in shopping_list
                if search_term.lower() in item['name'].lower()
            ]

        return shopping_list

    def get_historical_inventory(self, search_term=None, category=None,
                                 consumed_start_date=None, consumed_end_date=None,
                                 sort_by='consumed_date', sort_order='DESC',
                                 page=1, per_page=10):
        """
        Retrieves items from historical inventory, joined with product details,
        with filtering, sorting, and pagination.
        - search_term: Filters by product name (p.name or hi.name).
        - category: Filters by product category (p.category).
        - consumed_start_date: Filters for hi.consumed_date >= this date.
        - consumed_end_date: Filters for hi.consumed_date <= this date.
        - sort_by: ('product_name', 'category', 'quantity_consumed', 'consumed_date').
        - sort_order: 'ASC' or 'DESC'.
        - page: For pagination.
        - per_page: For pagination.
        """
        items = []
        params = []

        base_query = """
            SELECT
                hi.id, hi.product_id,
                COALESCE(p.name, hi.name) AS product_display_name,
                hi.quantity_consumed_this_time, hi.original_quantity_string,
                hi.purchase_date, hi.expiry_date, hi.consumed_date,
                p.unit_of_measure,
                c.name AS category_name,
                sc.name AS subcategory_name
            FROM historical_items hi
            LEFT JOIN products p ON hi.product_id = p.id
            LEFT JOIN categories c ON p.category_id = c.id
            LEFT JOIN subcategories sc ON p.subcategory_id = sc.id
        """

        where_clauses = []
        if search_term:
            where_clauses.append("LOWER(COALESCE(p.name, hi.name)) LIKE ?")
            params.append(f"%{search_term.lower()}%")
        if category: # Filter by category NAME
            # This will only include items that have a linked product and category
            where_clauses.append("c.name IS NOT NULL AND LOWER(c.name) = ?")
            params.append(category.lower())
        if consumed_start_date:
            where_clauses.append("hi.consumed_date >= ?")
            params.append(consumed_start_date)
        if consumed_end_date:
            where_clauses.append("hi.consumed_date <= ?")
            params.append(consumed_end_date)

        if where_clauses:
            base_query += " WHERE " + " AND ".join(where_clauses)

        # Sorting
        valid_sort_columns = {
            'product_name': 'product_display_name',
            'category_name': 'c.name', # Updated to category_name
            'quantity_consumed': 'hi.quantity_consumed_this_time',
            'consumed_date': 'hi.consumed_date',
            'purchase_date': 'hi.purchase_date', # Added for completeness
            'expiry_date': 'hi.expiry_date'    # Added for completeness
        }
        sort_column = valid_sort_columns.get(sort_by.lower(), 'hi.consumed_date')

        sort_order_upper = sort_order.upper()
        if sort_order_upper not in ['ASC', 'DESC']:
            sort_order_upper = 'DESC' # Default for historical

        base_query += f" ORDER BY {sort_column} {sort_order_upper}, hi.id {sort_order_upper}"

        # Pagination
        if page is not None and per_page is not None and page > 0 and per_page > 0:
            offset = (page - 1) * per_page
            base_query += " LIMIT ? OFFSET ?"
            params.extend([per_page, offset])
        elif per_page is not None and per_page > 0:
            base_query += " LIMIT ?"
            params.append(per_page)

        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(base_query, tuple(params))
                rows = cursor.fetchall()
                for row_data in rows:
                    item = dict(row_data)
                    item['name'] = item['product_display_name'] # Ensure 'name' key is present for consistency
                    if item.get('purchase_date'):
                        item['purchase_date'] = date.fromisoformat(item['purchase_date'])
                    if item.get('expiry_date'):
                        item['expiry_date'] = date.fromisoformat(item['expiry_date'])
                    if item.get('consumed_date'): # Should always be present for historical
                        item['consumed_date'] = date.fromisoformat(item['consumed_date'])
                    items.append(item)
        except sqlite3.Error as e:
            print(f"Database error fetching historical inventory with filters: {e}")
        return items

    def get_historical_inventory_count(self, search_term=None, category=None,
                                       consumed_start_date=None, consumed_end_date=None):
        """
        Gets the total count of historical inventory items based on filters.
        """
        params = []
        query = """
            SELECT COUNT(hi.id) as count
            FROM historical_items hi
            LEFT JOIN products p ON hi.product_id = p.id
            LEFT JOIN categories c ON p.category_id = c.id
        """

        where_clauses = []
        if search_term:
            where_clauses.append("LOWER(COALESCE(p.name, hi.name)) LIKE ?")
            params.append(f"%{search_term.lower()}%")
        if category: # Filter by category NAME
            where_clauses.append("c.name IS NOT NULL AND LOWER(c.name) = ?")
            params.append(category.lower())
        if consumed_start_date:
            where_clauses.append("hi.consumed_date >= ?")
            params.append(consumed_start_date)
        if consumed_end_date:
            where_clauses.append("hi.consumed_date <= ?")
            params.append(consumed_end_date)

        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)

        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, tuple(params))
                result = cursor.fetchone()
                return result['count'] if result else 0
        except sqlite3.Error as e:
            print(f"Database error getting historical inventory count: {e}")
            return 0

    def get_historical_inventory_categories(self):
        """Retrieves unique categories from products recorded in historical inventory."""
        categories = []
        query = """
            SELECT DISTINCT c.name
            FROM historical_items hi
            JOIN products p ON hi.product_id = p.id
            JOIN categories c ON p.category_id = c.id
            WHERE c.name IS NOT NULL
            ORDER BY c.name ASC
        """
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query)
                rows = cursor.fetchall()
                for row in rows:
                    categories.append(row['name']) # Select c.name
        except sqlite3.Error as e:
            print(f"Database error fetching historical inventory categories: {e}")
        return categories

    def get_total_item_quantity(self, product_name_or_id):
        """Calculates total quantity of a specific item in current inventory, using product_id or name."""
        total_quantity = 0.0
        product_id = None

        if isinstance(product_name_or_id, int): # Assume it's an ID
            product_id = product_name_or_id
        elif isinstance(product_name_or_id, str): # Assume it's a name
            product = self.get_product_by_name(product_name_or_id)
            if product:
                product_id = product['id']
            else:
                print(f"Product '{product_name_or_id}' not found for quantity check.")
                return 0.0 # Product not found
        else:
            print(f"Invalid identifier type for get_total_item_quantity: {product_name_or_id}")
            return 0.0

        if product_id is None: # Handles case where name was given but not found
             return 0.0

        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT quantity FROM inventory_items WHERE product_id = ?", (product_id,))
                rows = cursor.fetchall()
                for row in rows:
                    total_quantity += self._parse_quantity_string(row['quantity'])
        except sqlite3.Error as e:
            print(f"Database error getting total item quantity for product ID {product_id}: {e}")
        return total_quantity

    def consume_item(self, item_name_to_consume, quantity_to_consume_float):
        """
        Consumes a specified quantity of an item from the inventory.
        - Fetches all batches of the item, ordered by expiry date (soonest first).
        - Iterates through batches, consuming the required quantity.
        - Updates item quantities in `inventory_items` table (or deletes if fully consumed).
        - Logs each consumption event (even partial from a batch) to `historical_items`.
        - Returns a dictionary with success status and detailed messages.
        """
        if quantity_to_consume_float <= 0:
            return {"success": False, "message": "Quantity to consume must be positive."}

        log_messages = []
        consumed_amount_total_overall = 0.0
        quantity_remaining_to_consume = float(quantity_to_consume_float)

        product_to_consume = self.get_product_by_name(item_name_to_consume)
        if not product_to_consume:
            return {"success": False, "message": f"Product '{item_name_to_consume}' not found in products table."}

        product_id_to_consume = product_to_consume['id']
        # Ensure product_name is the canonical name from the products table
        product_name_canonical = product_to_consume['name']

        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                # Fetch all batches of the item, ordered by expiry_date to consume oldest first.
                cursor.execute('''
                    SELECT id, product_id, name, quantity, purchase_date, expiry_date, original_quantity_string
                    FROM inventory_items 
                    WHERE product_id = ?
                    ORDER BY expiry_date ASC
                ''', (product_id_to_consume,))
                items_in_stock = [dict(row) for row in cursor.fetchall()]

                if not items_in_stock:
                    return {"success": False, "message": f"Item '{product_name_canonical}' not found in inventory."}

                for item_stock_dict in items_in_stock:
                    if quantity_remaining_to_consume <= 0:
                        break
                    
                    item_id = item_stock_dict['id']
                    current_original_qty_str = item_stock_dict['original_quantity_string']
                    current_qty_str_in_db = item_stock_dict['quantity']
                    
                    numeric_qty_in_stock = self._parse_quantity_string(current_qty_str_in_db)
                    consumable_from_this_batch = min(quantity_remaining_to_consume, numeric_qty_in_stock)

                    if consumable_from_this_batch <= 0:
                        continue

                    new_numeric_qty = numeric_qty_in_stock - consumable_from_this_batch
                    
                    new_quantity_db_str = "0" # Default if fully consumed
                    if new_numeric_qty > 0:
                        # Store floating-point numbers with decimals and integers without decimals
                        new_quantity_db_str = str(new_numeric_qty) if new_numeric_qty % 1 else str(int(new_numeric_qty))
                    
                    if new_numeric_qty <= 0:
                        cursor.execute("DELETE FROM inventory_items WHERE id = ?", (item_id,))
                        log_messages.append(f"Fully consumed batch ID {item_id} of '{product_name_canonical}'.")
                    else:
                        cursor.execute("UPDATE inventory_items SET quantity = ? WHERE id = ?", 
                                       (new_quantity_db_str, item_id))
                        log_messages.append(f"Partially consumed batch ID {item_id} of '{product_name_canonical}'. New qty: {new_quantity_db_str}")
                    
                    # Log to historical_items, now including product_id
                    cursor.execute('''
                        INSERT INTO historical_items 
                        (product_id, name, quantity_consumed_this_time, original_quantity_string,
                         purchase_date, expiry_date, consumed_date) 
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (product_id_to_consume, product_name_canonical, consumable_from_this_batch, current_original_qty_str,
                          item_stock_dict['purchase_date'], item_stock_dict['expiry_date'],
                          date.today().isoformat()))
                    
                    consumed_amount_total_overall += consumable_from_this_batch
                    quantity_remaining_to_consume -= consumable_from_this_batch
                
                conn.commit()

        except sqlite3.Error as e:
            print(f"Database error consuming item: {e}")
            return {"success": False, "message": f"Database error: {e}", "details": log_messages}

        final_message = f"Total consumed: {consumed_amount_total_overall:.2f} of {product_name_canonical}."
        if quantity_remaining_to_consume > 0 and consumed_amount_total_overall > 0 :
            final_message += f" Could not consume the full requested amount. {quantity_remaining_to_consume:.2f} still pending."
        elif consumed_amount_total_overall == 0 and quantity_to_consume_float > 0:
             final_message = f"No quantity of '{product_name_canonical}' could be consumed (possibly none in stock or issue with parsing quantity)."
        
        print(final_message)
        return {"success": consumed_amount_total_overall > 0, "message": final_message, "details": log_messages}

    def adjust_inventory_batch(self, batch_id, new_quantity_str, new_purchase_date_str=None, new_expiry_date_str=None, include_in_projections=False):
        """
        Adjusts the quantity, purchase date, or expiry date of a specific inventory batch.
        - batch_id: The ID of the inventory_item to adjust.
        - new_quantity_str: The new quantity for the batch (as a string).
        - new_purchase_date_str: Optional. New purchase date in 'YYYY-MM-DD' format.
        - new_expiry_date_str: Optional. New expiry date in 'YYYY-MM-DD' format.
        - include_in_projections: Boolean. If True, quantity changes affect historical consumption for projections.
        Logs changes to historical_items if quantity is changed AND include_in_projections is True.
        Deletes batch if new quantity is 0.
        Returns a dictionary with success status and message.
        """
        log_message_parts = []
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("SELECT * FROM inventory_items WHERE id = ?", (batch_id,))
                batch_row = cursor.fetchone()

                if not batch_row:
                    return {"success": False, "message": f"Inventory batch with ID {batch_id} not found."}

                current_batch = dict(batch_row)
                item_name = current_batch['name'] # Use name from DB for messages
                product_id = current_batch['product_id']
                current_quantity_numeric = self._parse_quantity_string(current_batch['quantity'])

                new_quantity_float = self._parse_quantity_string(new_quantity_str)
                if new_quantity_float < 0:
                    return {"success": False, "message": "Quantity cannot be negative."}

                quantity_diff = new_quantity_float - current_quantity_numeric
                final_quantity_db_str = str(new_quantity_str) # What will be stored if not deleting

                # Date handling (validate and prepare for update if provided)
                final_purchase_date_str = current_batch['purchase_date']
                final_expiry_date_str = current_batch['expiry_date']
                date_fields_to_update = {}

                if new_purchase_date_str and new_purchase_date_str != current_batch['purchase_date']:
                    try:
                        date.fromisoformat(new_purchase_date_str) # Validate
                        date_fields_to_update["purchase_date"] = new_purchase_date_str
                        final_purchase_date_str = new_purchase_date_str
                    except ValueError:
                        return {"success": False, "message": "Invalid new purchase date format. Use YYYY-MM-DD."}

                if new_expiry_date_str and new_expiry_date_str != current_batch['expiry_date']:
                    try:
                        date.fromisoformat(new_expiry_date_str) # Validate
                        date_fields_to_update["expiry_date"] = new_expiry_date_str
                        final_expiry_date_str = new_expiry_date_str
                    except ValueError:
                        return {"success": False, "message": "Invalid new expiry date format. Use YYYY-MM-DD."}

                # --- Database Operations ---
                if new_quantity_float == 0:
                    cursor.execute("DELETE FROM inventory_items WHERE id = ?", (batch_id,))
                    log_message_parts.append(f"Batch ID {batch_id} ('{item_name}') deleted (quantity set to 0).")
                    # If deleted, quantity_diff is based on current_quantity_numeric becoming 0.
                    # So quantity_diff will be -current_quantity_numeric
                    # This ensures the full amount is logged as "consumed" or "removed" if projections are included.
                    quantity_diff = -current_quantity_numeric
                else:
                    update_fields_sql = ["quantity = ?"]
                    update_values_sql = [final_quantity_db_str]
                    if "purchase_date" in date_fields_to_update:
                        update_fields_sql.append("purchase_date = ?")
                        update_values_sql.append(date_fields_to_update["purchase_date"])
                    if "expiry_date" in date_fields_to_update:
                        update_fields_sql.append("expiry_date = ?")
                        update_values_sql.append(date_fields_to_update["expiry_date"])

                    if update_fields_sql: # Only update if quantity or dates actually changed
                        update_values_sql.append(batch_id)
                        cursor.execute(f"UPDATE inventory_items SET {', '.join(update_fields_sql)} WHERE id = ?", tuple(update_values_sql))
                        log_message_parts.append(f"Batch ID {batch_id} ('{item_name}') updated.")
                    else: # No quantity change, no date change
                         if quantity_diff == 0 and not date_fields_to_update:
                             return {"success": True, "message": f"No changes detected for batch ID {batch_id} ('{item_name}')."}


                # Historical Logging based on include_in_projections flag
                if quantity_diff != 0: # Only log if quantity actually changed
                    if include_in_projections:
                        amount_for_history = -quantity_diff # Positive if decreased, negative if increased
                        cursor.execute('''
                            INSERT INTO historical_items
                            (product_id, name, quantity_consumed_this_time, original_quantity_string,
                             purchase_date, expiry_date, consumed_date)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        ''', (product_id, item_name, amount_for_history, current_batch['original_quantity_string'],
                              current_batch['purchase_date'], current_batch['expiry_date'], # Log original batch dates
                              date.today().isoformat()))
                        log_message_parts.append(f"Adjustment of {amount_for_history} units recorded for projections. Note: Batch ID {batch_id} quantity adjusted from {current_quantity_numeric} to {new_quantity_float}.")
                    else:
                        log_message_parts.append(f"Quantity updated without impacting projections history. Note: Batch ID {batch_id} quantity adjusted from {current_quantity_numeric} to {new_quantity_float}.")

                conn.commit()
                return {"success": True, "message": " ".join(log_message_parts)}

        except sqlite3.Error as e:
            print(f"Database error adjusting inventory batch ID {batch_id}: {e}")
            return {"success": False, "message": f"Database error: {e}"}
        except Exception as e: # Catch other potential errors like date parsing
            print(f"Error adjusting inventory batch ID {batch_id}: {e}")
            return {"success": False, "message": f"An unexpected error occurred: {e}"}

    def check_for_expiring_items(self, days_threshold=3):
        """Checks for items expiring within a certain number of days from DB."""
        today = date.today()
        threshold_date = (today + timedelta(days=days_threshold)).isoformat()
        expiring_items_list = []
        
        print(f"\n--- Items Expiring Soon (within {days_threshold} days or already expired) ---")
        found_expiring = False
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                # Select items expiring on or before the threshold date, or already expired (expiry_date < today)
                cursor.execute('''
                    SELECT name, quantity, purchase_date, expiry_date 
                    FROM inventory_items 
                    WHERE expiry_date <= ? 
                    ORDER BY expiry_date ASC
                ''', (threshold_date,))
                rows = cursor.fetchall()
                for row in rows:
                    item = dict(row)
                    item_expiry_date = date.fromisoformat(item['expiry_date'])
                    days_to_expiry = (item_expiry_date - today).days
                    
                    if days_to_expiry < 0:
                        print(f"- {item['name']} EXPIRED on {item['expiry_date']}!")
                    else:
                        print(f"- {item['name']} expires in {days_to_expiry} day(s) on {item['expiry_date']}")
                    
                    # Convert dates for the returned list
                    item['purchase_date'] = date.fromisoformat(item['purchase_date'])
                    item['expiry_date'] = item_expiry_date
                    expiring_items_list.append(item)
                    found_expiring = True
            if not found_expiring:
                print("No items expiring soon or already expired.")
        except sqlite3.Error as e:
            print(f"Database error checking expiring items: {e}")
        
        print("---------------------------------------\n")
        return expiring_items_list

    def get_inventory_concerns(self, product_id):
        """
        Analyzes a product's inventory and consumption to identify potential concerns.
        - product_id: The ID of the product to check.
        Returns a list of concern strings.
        """
        concerns = []
        today = date.today()

        product_details = self.get_product_details(product_id) # This now includes nearest_expiry_date
        if not product_details:
            concerns.append(f"Product with ID {product_id} not found.")
            return concerns

        current_stock = product_details.get('current_on_hand_inventory', 0)
        nearest_expiry_date_str = product_details.get('nearest_expiry_date', "N/A")

        # Get average daily consumption
        # Using projection_days=1 as we only need avg_daily_consumption here.
        # lookback_days can be standard e.g. 30 or configurable if needed.
        demand_projection = self.project_demand(product_id, lookback_days=30, projection_days=1)
        avg_daily_consumption = 0.0
        if demand_projection.get("success"):
            avg_daily_consumption = demand_projection.get('avg_daily_consumption', 0.0)
        else:
            # Add a concern if demand projection failed, as it's needed for some checks
            concerns.append(f"Could not retrieve consumption data for {product_details.get('name', 'this product')}: {demand_projection.get('message', 'Unknown error')}")


        # Concern 1: Low stock
        if avg_daily_consumption > 0:
            days_of_stock_left = current_stock / avg_daily_consumption
            # Using a threshold of 3 days for "low stock"
            if days_of_stock_left < 3:
                concerns.append(f"Will run out in the next {days_of_stock_left:.1f} days based on current consumption.")
        elif current_stock > 0: # Stock exists but no consumption
            # Concern 2: No significant usage
            concerns.append("No significant usage data available, but stock exists.")
        # If avg_daily_consumption is 0 and current_stock is 0, it's less of an immediate "concern" unless par levels are set.

        # Date parsing for expiry concerns
        nearest_expiry_date_obj = None
        if nearest_expiry_date_str != "N/A":
            try:
                nearest_expiry_date_obj = date.fromisoformat(nearest_expiry_date_str)
            except ValueError:
                concerns.append(f"Invalid nearest expiry date format found: {nearest_expiry_date_str}")


        if nearest_expiry_date_obj:
            days_until_expiry = (nearest_expiry_date_obj - today).days

            # Concern 3: Nearing expiry (e.g., within 7 days)
            # Let's use a threshold of 7 days for "expiring soon"
            EXPIRY_SOON_THRESHOLD_DAYS = 7
            if days_until_expiry <= EXPIRY_SOON_THRESHOLD_DAYS:
                if days_until_expiry < 0:
                     concerns.append(f"Item has batches already EXPIRED (Nearest expiry: {nearest_expiry_date_str}).")
                else:
                     concerns.append(f"Item has batches expiring soon (on {nearest_expiry_date_str}, in {days_until_expiry} days).")

            # Concern 4: Stock may expire before being fully used
            if avg_daily_consumption > 0 and current_stock > 0:
                # days_of_stock_left was calculated earlier for low stock check
                if days_of_stock_left > days_until_expiry and days_until_expiry >= 0: # only if not already expired
                    concerns.append(f"Stock ({current_stock} units, lasting {days_of_stock_left:.1f} days) may expire before being fully used (expires in {days_until_expiry} days on {nearest_expiry_date_str}).")
        elif current_stock > 0 and nearest_expiry_date_str == "N/A":
            # This case implies stock exists but no expiry date could be found, which might be a data issue.
            concerns.append("Stock exists but nearest expiry date is not available. Check inventory data.")

        return concerns

    def project_demand(self, product_name_or_id, lookback_days=30, projection_days=7):
        """
        Analyzes historical consumption and current stock to project future demand using DB.
        - Calculates average daily consumption based on historical data within a lookback period.
        - Checks current total stock of the item.
        - Estimates how long current stock will last and projects future need.
        """
        today = date.today()
        lookback_start_dt = today - timedelta(days=lookback_days)
        total_consumed_in_lookback = 0.0
        product_id = None
        product_name = None
        product_unit = "units" # Default unit

        if isinstance(product_name_or_id, int): # Assume it's an ID
            product_id = product_name_or_id
            product = self.get_product(product_id)
            if not product:
                return {"success": False, "message": f"Product with ID {product_id} not found."}
            product_name = product['name']
            product_unit = product.get('unit_of_measure', product_unit)
        elif isinstance(product_name_or_id, str): # Assume it's a name
            product = self.get_product_by_name(product_name_or_id)
            if not product:
                return {"success": False, "message": f"Product '{product_name_or_id}' not found."}
            product_id = product['id']
            product_name = product['name']
            product_unit = product.get('unit_of_measure', product_unit)
        else:
            return {"success": False, "message": "Invalid product identifier for projection."}

        avg_daily_consumption = 0.0
        consumption_rate_overridden = False
        if product.get('consumption_override_rate') is not None:
            try:
                avg_daily_consumption = float(product['consumption_override_rate'])
                consumption_rate_overridden = True
                print(f"Using consumption_override_rate: {avg_daily_consumption} for {product_name}")
            except ValueError:
                print(f"Warning: Could not parse consumption_override_rate '{product['consumption_override_rate']}' for {product_name}. Proceeding with historical calculation.")

        if not consumption_rate_overridden:
            try:
                with self._get_db_connection() as conn:
                    cursor = conn.cursor()
                cursor.execute('''
                    SELECT SUM(quantity_consumed_this_time) as total_consumed
                    FROM historical_items 
                    WHERE product_id = ? AND consumed_date >= ? AND consumed_date <= ?
                ''', (product_id, lookback_start_dt.isoformat(), today.isoformat()))
                result_row = cursor.fetchone()
                if result_row and result_row['total_consumed'] is not None:
                    total_consumed_in_lookback = float(result_row['total_consumed'])

                # Calculate avg_daily_consumption based on historical data if not overridden
                avg_daily_consumption = (total_consumed_in_lookback / lookback_days) if lookback_days > 0 else 0.0

            except sqlite3.Error as e:
                print(f"Database error fetching historical data for demand projection (Product ID: {product_id}): {e}")
                return {
                    "product_id": product_id, "product_name": product_name, "unit_of_measure": product_unit,
                    "consumption_override_rate": product.get('consumption_override_rate'),
                    "current_stock": self.get_total_item_quantity(product_id),
                    "avg_daily_consumption": 0, "days_to_depletion": "Error fetching history",
                    "projected_need": 0, "lookback_days": lookback_days, "projection_days": projection_days,
                    "success": False, "message": f"DB error calculating historical consumption: {e}"
                }
        # else: avg_daily_consumption is already set from override

        current_quantity_sum = self.get_total_item_quantity(product_id)
        
        days_to_depletion_str = "N/A"
        if avg_daily_consumption > 0:
            if current_quantity_sum > 0 :
                days_to_depletion = current_quantity_sum / avg_daily_consumption
                days_to_depletion_str = f"{days_to_depletion:.1f} days"
            else:
                days_to_depletion_str = "0 days (already out of stock)"
        elif current_quantity_sum > 0:
            days_to_depletion_str = "Stock will not deplete based on recent consumption."
        else:
            days_to_depletion_str = "N/A (out of stock, no consumption history)"
        
        projected_need = avg_daily_consumption * projection_days
        
        result = {
            "product_id": product_id, "product_name": product_name, "unit_of_measure": product_unit,
            "current_stock": current_quantity_sum,
            "avg_daily_consumption": avg_daily_consumption, "days_to_depletion": days_to_depletion_str,
            "projected_need": projected_need, "lookback_days": lookback_days, "projection_days": projection_days,
            "consumption_override_rate": product.get('consumption_override_rate'), # Ensure it's in the result
            "success": True
        }

        print(f"\n--- Demand Projection for '{product_name}' (ID: {product_id}) ---")
        print(f"Unit of Measure: {product_unit}")
        print(f"Lookback: {lookback_days} days, Projection: {projection_days} days")
        print(f"Total consumed (lookback): {total_consumed_in_lookback:.2f} {product_unit}")
        print(f"Current stock: {current_quantity_sum:.2f} {product_unit}")
        print(f"Avg daily consumption: {avg_daily_consumption:.2f} {product_unit}/day")
        print(f"Est. days to depletion: {days_to_depletion_str}")
        print(f"Projected need (next {projection_days} days): {projected_need:.2f} {product_unit}")
        print("-----------------------------------------\n")
        return result

    def export_data_to_csv(self, filename_prefix="inventory_export_db"):
        """Exports current and historical inventory, and projections to CSV files from DB."""
        def write_to_csv_internal(filename, data_dicts, fieldnames):
            try:
                with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    writer.writeheader()
                    for row_dict in data_dicts:
                        # Convert date objects to ISO strings for CSV if they are date objects
                        row_to_write = {k: (v.isoformat() if isinstance(v, date) else v) for k, v in row_dict.items()}
                        writer.writerow(row_to_write)
                print(f"Data successfully exported to '{filename}'.")
            except IOError as e: print(f"Error exporting data to '{filename}': {e}")
            except Exception as e: print(f"An unexpected error occurred during CSV export: {e}")

        current_inv_data = self.get_current_inventory()
        if current_inv_data:
            # Ensure all keys are present for DictWriter, even if some rows don't have them all
            # (though SQL SELECT should be consistent)
            current_fields = ["id", "name", "quantity", "purchase_date", "expiry_date", "original_quantity_string"]
            write_to_csv_internal(f"{filename_prefix}_current.csv", current_inv_data, current_fields)
        else: print("Current inventory empty. Skipping export.")

        historical_inv_data = self.get_historical_inventory()
        if historical_inv_data:
            hist_fields = ["id", "name", "quantity_consumed_this_time", "original_quantity_string", 
                           "purchase_date", "expiry_date", "consumed_date"]
            write_to_csv_internal(f"{filename_prefix}_historical.csv", historical_inv_data, hist_fields)
        else: print("Historical inventory empty. Skipping export.")

        unique_items = set(item['name'] for item in current_inv_data) | \
                       set(item['name'] for item in historical_inv_data)
        if unique_items:
            projections = [self.project_demand(name) for name in sorted(list(unique_items))]
            # Filter out projections that might have indicated an error during calculation
            successful_projections = [p for p in projections if p.get("success", True)]
            if successful_projections:
                # Get fieldnames from the first successful projection, excluding 'success' if it was added
                proj_fields = [key for key in successful_projections[0].keys() if key != 'success']
                write_to_csv_internal(f"{filename_prefix}_projections.csv", successful_projections, proj_fields)
            else:
                print("No successful projection data generated. Skipping export.")
        else:
            print("No items found to generate projections. Skipping projection export.")


# --- Standalone Garden Produce Functions (Not part of InventoryManager class) ---
# These functions remain as they were, operating on a global list,
# as they are not part of the core SQLite-backed InventoryManager.
my_garden_produce_list = [] 

def add_garden_produce(name, harvest_date_str, typical_shelf_life_days):
    """Adds produce harvested from the garden to a global list."""
    global my_garden_produce_list
    try:
        harvest_dt = date.fromisoformat(harvest_date_str)
        produce = {
            "name": name,
            "harvest_date": harvest_dt,
            "estimated_expiry": harvest_dt + timedelta(days=typical_shelf_life_days),
            "source": "garden"
        }
        my_garden_produce_list.append(produce)
        print(f"Logged garden produce: {produce['name']}")
    except ValueError:
        print(f"Error: Invalid date format for garden produce '{name}'. Please use YYYY-MM-DD.")

def display_garden_produce():
    """Prints all items in the garden produce list."""
    if not my_garden_produce_list:
        print("Your garden produce list is empty!")
        return
    print("\n--- Your Garden Produce ---")
    for item in my_garden_produce_list:
        print(f"- {item['name']}, Harvested: {item['harvest_date'].isoformat()}, Est. Expires: {item['estimated_expiry'].isoformat()}")
    print("---------------------------\n")


if __name__ == "__main__":
    DB_FILE = "food_manager_dev.db" # Use a dev-specific DB for demo
    print(f"Welcome to your SQLite Food Manager! Using database: {DB_FILE}")
    print("Note: For a fresh demo, delete the database file before running.")
    
    manager = InventoryManager(db_filepath=DB_FILE)

    # --- Section 1: Initial State ---
    print("\n--- Section 1: Initial Inventory State ---")
    current_items_main = manager.get_current_inventory()
    if not current_items_main: print("Current inventory is empty.")
    else: 
        for item in current_items_main: print(f"- {item['name']} ({item['quantity']})")
    
    historical_items_main = manager.get_historical_inventory()
    if not historical_items_main: print("Historical inventory is empty.")
    else: 
        for item in historical_items_main: print(f"- HIST: {item['name']} ({item['quantity_consumed_this_time']}) on {item['consumed_date']}")


    # --- Section 2: Adding Items ---
    print("\n--- Section 2: Adding New Grocery Items ---")
    today_str = date.today().isoformat()
    
    manager.add_item_to_list(name="DB Apples", quantity_str="6 units", purchase_date_str=today_str, expiry_days=14,
                             category="Produce", subcategory="Fruit", par_level=5, max_holding_amount=20)
    manager.add_item_to_list(name="DB Bananas", quantity_str="12", purchase_date_str=today_str, expiry_days=5,
                             category="Produce", subcategory="Fruit") # Using defaults for par/max
    manager.add_item_to_list(name="DB Milk", quantity_str="1 gallon", purchase_date_str=today_str, expiry_days=7,
                             category="Dairy", par_level=1, max_holding_amount=2)
    
    print("\n--- Current inventory after additions: ---")
    for item in manager.get_current_inventory(): print(f"- {item['name']} ({item['quantity']})")

    # --- Section 3: Checking for Expiring Items ---
    print("\n--- Section 3: Checking for Expiring Items ---")
    manager.check_for_expiring_items(days_threshold=6)

    # --- Section 4: Consuming Items ---
    print("\n--- Section 4: Consuming Items ---")
    print("Consuming 2 DB Apples...")
    manager.consume_item("DB Apples", 2.0)
    print("Consuming 12 DB Bananas...")
    manager.consume_item("DB Bananas", 12.0)
    
    print("\n--- Current inventory after consumption: ---")
    for item in manager.get_current_inventory(): print(f"- {item['name']} ({item['quantity']})")
    print("\n--- Historical inventory after consumption: ---")
    for item in manager.get_historical_inventory(): print(f"- HIST: {item['name']} ({item['quantity_consumed_this_time']}) on {item['consumed_date']}")

    # --- Section 5: Demand Projection ---
    print("\n--- Section 5: Demand Projection ---")
    manager.project_demand("DB Apples")
    manager.project_demand("DB Milk")

    # --- Section 6: Exporting Data ---
    print("\n--- Section 6: Exporting All Data to CSV ---")
    manager.export_data_to_csv(filename_prefix="food_manager_db_demo_export")
    print(f"Data export process finished for DB demo.")

    print("\n\n--- Food Manager (SQLite DB) Demonstration Complete ---")
    print(f"Database file '{DB_FILE}' contains the data.")

    # Run migration if needed (idempotent parts are handled inside the method)
    print("\n--- Running Data Migration (if applicable) ---")
    migration_result = manager.migrate_text_categories_to_ids()
    if migration_result: # Check if not None
        print(migration_result.get("message", "Migration status unknown."))
    print("--- Migration Attempt Finished ---")

    # Note: To truly reset, delete DB_FILE before running again.
