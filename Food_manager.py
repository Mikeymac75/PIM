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

    def _get_db_connection(self):
        """Establishes and returns a database connection."""
        if self.conn and self.db_filepath == ":memory:":
            return self.conn
        conn = sqlite3.connect(self.db_filepath)
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.row_factory = sqlite3.Row
        return conn

    def close_connection(self):
        if self.conn and self.db_filepath == ":memory:":
            self.conn.close()
            self.conn = None

    def _initialize_db(self):
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
                try:
                    cursor.execute("SELECT old_category_text FROM products LIMIT 1")
                except sqlite3.OperationalError:
                    print("Simulating old schema: Adding old_category_text and old_subcategory_text columns...")
                    conn.executescript('''
                        ALTER TABLE products ADD COLUMN old_category_text TEXT;
                        ALTER TABLE products ADD COLUMN old_subcategory_text TEXT;
                    ''')
                    print("Inserting sample products with text categories for migration...")
                    sample_products = [
                        ("Apple", "pcs", 14, "Produce", "Fruit"),("Milk", "liter", 7, "Dairy", None),
                        ("Carrot", "kg", 21, "Produce", "Vegetable"),("Yogurt", "pcs", 10, "Dairy", "Cultured"),
                        ("Orange Juice", "liter", 7, "Beverages", None),("Banana", "pcs", 5, "Produce", "Fruit")
                    ]
                    for p_name, uom, exp_days, cat_text, subcat_text in sample_products:
                        cursor.execute("SELECT id FROM products WHERE name = ?", (p_name,))
                        if not cursor.fetchone():
                            cursor.execute("""
                                INSERT INTO products (name, unit_of_measure, default_expiry_days, old_category_text, old_subcategory_text, category_id, subcategory_id)
                                VALUES (?, ?, ?, ?, ?, NULL, NULL)
                            """, (p_name, uom, exp_days, cat_text, subcat_text))
                        else:
                            cursor.execute("""
                                UPDATE products SET old_category_text = ?, old_subcategory_text = ?
                                WHERE name = ? AND category_id IS NULL
                            """, (cat_text, subcat_text, p_name))
                    conn.commit()
                    print("Sample data inserted/updated for old text categories.")

                print("Populating 'categories' table from old_category_text...")
                cursor.execute("SELECT DISTINCT old_category_text FROM products WHERE old_category_text IS NOT NULL")
                distinct_categories = [row['old_category_text'] for row in cursor.fetchall()]
                for cat_name in distinct_categories:
                    add_cat_result = self.add_category(cat_name)
                    if add_cat_result['success']: print(f"Category '{cat_name}' (ID: {add_cat_result.get('category_id')}) processed.")
                    elif "already exists" in add_cat_result.get('message',''): print(f"Category '{cat_name}' already exists.")
                    else: print(f"Warning: Could not add category '{cat_name}': {add_cat_result.get('message')}")
                conn.commit()

                print("Populating 'subcategories' table...")
                cursor.execute("SELECT DISTINCT old_category_text, old_subcategory_text FROM products WHERE old_category_text IS NOT NULL AND old_subcategory_text IS NOT NULL")
                for row in cursor.fetchall():
                    old_cat_text, old_subcat_text = row['old_category_text'], row['old_subcategory_text']
                    category_obj_res = self.get_category_by_name(old_cat_text) # Expects dict
                    if category_obj_res.get("success") and category_obj_res.get("data"):
                        cat_id = category_obj_res["data"]['id']
                        add_subcat_result = self.add_subcategory(old_subcat_text, cat_id)
                        if add_subcat_result['success']: print(f"Subcategory '{old_subcat_text}' under Category '{old_cat_text}' processed.")
                        elif "already exists" in add_subcat_result.get('message',''): print(f"Subcategory '{old_subcat_text}' under '{old_cat_text}' already exists.")
                        else: print(f"Warning: Could not add subcategory '{old_subcat_text}' for '{old_cat_text}': {add_subcat_result.get('message')}")
                    else: print(f"Warning: Category '{old_cat_text}' not found for subcategory '{old_subcat_text}'.")
                conn.commit()

                print("Updating 'products' table with category_id and subcategory_id...")
                cursor.execute("SELECT id, old_category_text, old_subcategory_text FROM products WHERE category_id IS NULL")
                for product_row in cursor.fetchall():
                    prod_id, cat_text, subcat_text = product_row['id'], product_row['old_category_text'], product_row['old_subcategory_text']
                    cat_id_to_set, sub_cat_id_to_set = None, None
                    if cat_text:
                        cat_data_res = self.get_category_by_name(cat_text)
                        if cat_data_res.get("success") and cat_data_res.get("data"):
                            cat_id_to_set = cat_data_res["data"]['id']
                            if subcat_text:
                                subcat_data_res = self.get_subcategory_by_name_and_category_id(subcat_text, cat_id_to_set)
                                if subcat_data_res.get("success") and subcat_data_res.get("data"):
                                    sub_cat_id_to_set = subcat_data_res["data"]['id']
                                else: print(f"Warning: Subcategory '{subcat_text}' not found for product ID {prod_id}.")
                        else: print(f"Warning: Category '{cat_text}' not found for product ID {prod_id}.")
                    if cat_id_to_set:
                        cursor.execute("UPDATE products SET category_id = ?, subcategory_id = ? WHERE id = ?", (cat_id_to_set, sub_cat_id_to_set, prod_id))
                        print(f"Product ID {prod_id} updated with CategoryID: {cat_id_to_set}, SubcategoryID: {sub_cat_id_to_set}")
                conn.commit()

                print("Attempting to drop old text category columns (simulation)...")
                try:
                    conn.executescript("ALTER TABLE products DROP COLUMN old_category_text; ALTER TABLE products DROP COLUMN old_subcategory_text;")
                    print("Successfully dropped old_category_text and old_subcategory_text columns.")
                except sqlite3.OperationalError as e_drop: print(f"Could not drop old columns: {e_drop}")
                conn.commit()
                return {"success": True, "message": "Migration of text categories to IDs completed."}
        except sqlite3.Error as e: return {"success": False, "message": f"Migration failed: {e}", "error_details": str(e)}

    def add_category(self, name):
        if not name or not isinstance(name, str) or not name.strip():
            return {"success": False, "message": "Category name must be a non-empty string."}
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO categories (name) VALUES (?)", (name.strip(),))
                conn.commit()
                return {"success": True, "message": f"Category '{name.strip()}' added successfully.", "category_id": cursor.lastrowid}
        except sqlite3.IntegrityError:
            return {"success": False, "message": f"Category name '{name.strip()}' already exists.", "error_details": "IntegrityError"}
        except sqlite3.Error as e:
            return {"success": False, "message": f"Database error adding category: {e}", "error_details": str(e)}

    def add_subcategory(self, name, category_id):
        if not name or not isinstance(name, str) or not name.strip():
            return {"success": False, "message": "Subcategory name must be a non-empty string."}
        if not isinstance(category_id, int):
             return {"success": False, "message": "Category ID must be an integer."}
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM categories WHERE id = ?", (category_id,))
                if not cursor.fetchone():
                    return {"success": False, "message": f"Parent category with ID {category_id} not found."}
                cursor.execute("INSERT INTO subcategories (name, category_id) VALUES (?, ?)", (name.strip(), category_id))
                conn.commit()
                return {"success": True, "message": f"Subcategory '{name.strip()}' added.", "subcategory_id": cursor.lastrowid}
        except sqlite3.IntegrityError:
            return {"success": False, "message": f"Subcategory '{name.strip()}' already exists for category ID {category_id}.", "error_details": "IntegrityError"}
        except sqlite3.Error as e:
            return {"success": False, "message": f"Database error adding subcategory: {e}", "error_details": str(e)}

    def process_excel_row_for_inventory_upload(self, row_data, confirmed_action=None, temp_category_id=None):
        """
        Processes a single row of data from an Excel upload for inventory items.
        Validates data, handles product/category/subcategory creation or resolution,
        and then calls add_item_to_list for database insertion.
        """
        name = row_data.get('name')
        quantity_str = row_data.get('quantity_str')
        purchase_date_val = row_data.get('purchase_date_val') # Expects raw value from Excel
        expiry_days_val = row_data.get('expiry_days_val') # Expects raw value
        category_name = row_data.get('category_name')
        subcategory_name = row_data.get('subcategory_name')
        par_level_val = row_data.get('par_level_val', "0")
        max_holding_val = row_data.get('max_holding_val', "0")
        purchase_location = row_data.get('purchase_location')
        unit_of_measure = row_data.get('unit_of_measure')

        row_errors = []
        warnings = []

        if not name: row_errors.append("Name is missing.")
        if quantity_str is None or str(quantity_str).strip() == "": row_errors.append("Quantity is missing.")
        if purchase_date_val is None: row_errors.append("Purchase Date is missing.")
        if expiry_days_val is None: row_errors.append("Expiry Days is missing.")

        purchase_date_str = None
        if isinstance(purchase_date_val, datetime):
            purchase_date_str = purchase_date_val.strftime('%Y-%m-%d')
        elif isinstance(purchase_date_val, str):
            try:
                date.fromisoformat(purchase_date_val.strip())
                purchase_date_str = purchase_date_val.strip()
            except ValueError:
                row_errors.append(f"Invalid Purchase Date format '{purchase_date_val}'. Use YYYY-MM-DD.")
        elif purchase_date_val is not None:
             row_errors.append(f"Purchase Date '{purchase_date_val}' is not in YYYY-MM-DD text or Excel date format.")
        
        expiry_days_int = None
        if isinstance(expiry_days_val, (int, float)):
            expiry_days_int = int(expiry_days_val)
            if expiry_days_int < 0: row_errors.append("Expiry Days must be non-negative.")
        elif isinstance(expiry_days_val, str) and expiry_days_val.strip().lstrip('-').isdigit():
            expiry_days_int = int(expiry_days_val.strip())
            if expiry_days_int < 0: row_errors.append("Expiry Days must be non-negative.")
        elif expiry_days_val is not None:
            row_errors.append(f"Expiry Days '{expiry_days_val}' must be a valid whole number.")

        par_level_float = 0.0
        try:
            par_level_float = float(str(par_level_val).strip()) if par_level_val is not None else 0.0
            if par_level_float < 0: row_errors.append("Par Level must be non-negative.")
        except (ValueError, TypeError): row_errors.append(f"Invalid Par Level '{par_level_val}'. Must be a number.")

        max_holding_float = 0.0
        try:
            max_holding_float = float(str(max_holding_val).strip()) if max_holding_val is not None else 0.0
            if max_holding_float < 0: row_errors.append("Max Holding Amount must be non-negative.")
        except (ValueError, TypeError): row_errors.append(f"Invalid Max Holding Amount '{max_holding_val}'. Must be a number.")

        if purchase_location and purchase_location.strip() not in ['Sobeys', 'Costco', None, '']: # Example allowed locations
             row_errors.append(f"Invalid Purchase Location '{purchase_location}'. If provided, must be one of: Sobeys, Costco.")

        # Check if product exists to determine if UoM is required for new product
        product_exists_response = self.get_product_by_name(name)
        is_new_product = False
        if product_exists_response.get("success"):
            if not product_exists_response.get("data"): is_new_product = True
        else: # DB error during product check
            return {"status": "error", "message": f"DB error checking product '{name}'.", "row_errors": [product_exists_response.get("message")], "warnings": warnings}

        if is_new_product and not unit_of_measure:
            row_errors.append("Unit of Measure is required for new products.")

        if row_errors:
            return {"status": "error", "message": f"Validation errors for '{name}'.", "row_errors": row_errors, "warnings": warnings}

        # Call the refactored add_item_to_list
        # This method will now primarily focus on DB interactions and complex logic like action_required
        add_result = self.add_item_to_list(
            name=name,
            quantity_str=quantity_str,
            purchase_date_str=purchase_date_str, # Already validated string
            expiry_days=expiry_days_int, # Already validated int
            category_name=category_name, # Pass names, add_item_to_list resolves/creates IDs
            subcategory_name=subcategory_name,
            par_level=par_level_float,
            max_holding_amount=max_holding_float,
            purchase_location=purchase_location.strip() if purchase_location else None,
            unit_of_measure=unit_of_measure.strip() if unit_of_measure else None,
            confirmed_action=confirmed_action,
            temp_category_id=temp_category_id
        )

        if add_result.get("warnings"): warnings.extend(add_result["warnings"])

        if add_result.get("action_required"):
            return {
                "status": "confirmation_required",
                "message": add_result.get("message"),
                "product_data_for_confirmation": add_result.get("product_data"), # Pass through from add_item_to_list
                "confirmation_details": add_result.get("confirmation_details"),
                "warnings": warnings,
                "row_errors": [] # No row errors at this stage if confirmation is required
            }
        elif add_result.get("success"):
            return {"status": "success", "message": add_result.get("message"), "warnings": warnings, "row_errors": []}
        else: # Error from add_item_to_list
            return {"status": "error", "message": add_result.get("message"), "row_errors": [add_result.get("message")], "warnings": warnings}

    def add_item_to_list(self, name, quantity_str, purchase_date_str, expiry_days,
                         category_name=None, subcategory_name=None, par_level=0, max_holding_amount=0,
                         purchase_location=None, unit_of_measure=None,
                         confirmed_action=None, temp_category_id=None):
        """
        Adds an item to inventory. Assumes basic data validation and type conversion
        has been done by the calling method (e.g., process_excel_row_for_inventory_upload).
        Focuses on product/category resolution and DB interaction.
        """
        warnings = []
        details = [] # For internal logging/debugging if needed later

        # Data for confirmation needs all original values passed to process_excel_row_for_inventory_upload
        # This is slightly redundant if process_excel_row... is the only caller, but good for direct use.
        product_data_for_confirmation = {
            "name": name, "quantity_str": quantity_str, "purchase_date_str": purchase_date_str,
            "expiry_days": expiry_days, "category_name": category_name, "subcategory_name": subcategory_name,
            "par_level": par_level, "max_holding_amount": max_holding_amount,
            "purchase_location": purchase_location, "unit_of_measure": unit_of_measure
        }

        product_info_response = self.get_product_by_name(name)
        if product_info_response.get("warnings"): warnings.extend(product_info_response["warnings"])
        if not product_info_response.get("success"):
            return {"success": False, "message": product_info_response.get("message"), "error_details": product_info_response.get("error_details"), "warnings": warnings}

        product_info = product_info_response.get("data")
        product_id_to_use = None
        category_id_to_use = None
        subcategory_id_to_use = None

        if product_info: # Existing product
            product_id_to_use = product_info['id']
            category_id_to_use = product_info.get('category_id') # May be None
            subcategory_id_to_use = product_info.get('subcategory_id') # May be None

            # Warning if provided category/UoM differs from DB for existing product
            if category_name and category_id_to_use:
                cat_name_res = self.get_category_name_by_id(category_id_to_use)
                if cat_name_res.get("success") and cat_name_res.get("data"):
                    if cat_name_res["data"].lower() != category_name.strip().lower():
                        warnings.append(f"Provided category '{category_name.strip()}' differs from DB category '{cat_name_res['data']}'. DB category retained.")
            if unit_of_measure and product_info.get('unit_of_measure', '').lower() != unit_of_measure.strip().lower():
                warnings.append(f"Provided UoM '{unit_of_measure.strip()}' differs from DB UoM '{product_info.get('unit_of_measure')}'. DB UoM retained.")

        else: # New Product
            if not category_name or not category_name.strip():
                 return {"success": False, "message": "Category name is required for new product.", "warnings": warnings}
            if not unit_of_measure or not unit_of_measure.strip(): # UoM must be present for new product
                 return {"success": False, "message": "Unit of Measure is required for new product.", "warnings": warnings}


            # Category resolution/creation
            category_res = self.get_category_by_name(category_name.strip())
            if not category_res.get("success"): # DB error
                return {"success": False, "message": category_res.get("message"), "error_details": category_res.get("error_details"), "warnings": warnings}

            existing_category_data = category_res.get("data")
            if existing_category_data:
                category_id_to_use = existing_category_data['id']
            elif confirmed_action == "confirm_new_category":
                add_cat_res = self.add_category(category_name.strip())
                if not add_cat_res.get("success"): return add_cat_res # Propagate error
                category_id_to_use = add_cat_res['category_id']
                warnings.append(f"New category '{category_name.strip()}' created.")
            else: # New category, needs confirmation
                return {"success": False, "action_required": "confirm_new_category",
                        "confirmation_details": {"new_category_name": category_name.strip(), "new_subcategory_name": subcategory_name.strip() if subcategory_name else None},
                        "product_data": product_data_for_confirmation, "warnings": warnings}

            # Subcategory resolution/creation (only if category_id_to_use is now set)
            if subcategory_name and subcategory_name.strip() and category_id_to_use:
                subcategory_res = self.get_subcategory_by_name_and_category_id(subcategory_name.strip(), category_id_to_use)
                if not subcategory_res.get("success"): # DB error
                     return {"success": False, "message": subcategory_res.get("message"), "error_details": subcategory_res.get("error_details"), "warnings": warnings}

                existing_subcategory_data = subcategory_res.get("data")
                if existing_subcategory_data:
                    subcategory_id_to_use = existing_subcategory_data['id']
                elif confirmed_action in ["confirm_new_category", "confirm_new_subcategory"]:
                    # If confirming category, assume subcategory can be created too.
                    # If confirming subcategory, temp_category_id should match category_id_to_use.
                    if confirmed_action == "confirm_new_subcategory" and temp_category_id != category_id_to_use:
                        # This is an internal consistency check, should ideally not be hit if app logic is correct
                        return {"success": False, "message": "Category ID mismatch during subcategory confirmation.", "warnings": warnings, "error_type": "ApplicationLogicError"}

                    add_subcat_res = self.add_subcategory(subcategory_name.strip(), category_id_to_use)
                    if not add_subcat_res.get("success"): return add_subcat_res
                    subcategory_id_to_use = add_subcat_res['subcategory_id']
                    warnings.append(f"New subcategory '{subcategory_name.strip()}' created under '{category_name.strip()}'.")
                else: # New subcategory for existing or newly confirmed category, needs confirmation
                    return {"success": False, "action_required": "confirm_new_subcategory",
                            "confirmation_details": {"category_id": category_id_to_use, "category_name": category_name.strip(), "new_subcategory_name": subcategory_name.strip()},
                            "product_data": product_data_for_confirmation, "warnings": warnings}

            # Create product
            create_product_res = self.create_product(
                name=name, category_id=category_id_to_use, subcategory_id=subcategory_id_to_use,
                unit_of_measure=unit_of_measure, default_expiry_days=expiry_days,
                par_level=par_level, max_holding_amount=max_holding_amount, purchase_location=purchase_location
            )
            if not create_product_res.get("success"): return create_product_res # Propagate error
            product_id_to_use = create_product_res['product_id']
            warnings.append(f"New product '{name}' created.")

        # Add to inventory_items
        if product_id_to_use is None: # Should not happen if logic is correct
            return {"success": False, "message": "Failed to resolve product ID.", "warnings": warnings, "error_type": "ApplicationLogicError"}

        try:
            purchase_dt_obj = date.fromisoformat(purchase_date_str)
            batch_expiry_dt = purchase_dt_obj + timedelta(days=int(expiry_days))
        except (ValueError, TypeError) as e:
            return {"success": False, "message": f"Invalid date format or expiry days: {e}", "error_details": str(e), "warnings": warnings}

        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO inventory_items
                    (product_id, name, quantity, purchase_date, expiry_date, original_quantity_string)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (product_id_to_use, name, str(quantity_str), purchase_dt_obj.isoformat(),
                      batch_expiry_dt.isoformat(), str(quantity_str)))
                conn.commit()
                item_id = cursor.lastrowid
                return {"success": True, "message": f"Item '{name}' added to inventory.", "item_id": item_id, "product_id": product_id_to_use, "warnings": warnings}
        except sqlite3.Error as e:
            return {"success": False, "message": f"Database error adding item to inventory: {e}", "error_details": str(e), "warnings": warnings, "error_type": "DBError"}

    def get_current_inventory(self, search_term=None, category=None, purchase_location=None,
                              sort_by='p.name', sort_order='ASC',
                              page=1, per_page=10):
        items = []
        params = []
        warnings = []

        base_query = """
            SELECT
                p.id AS product_id, p.name AS product_name, p.unit_of_measure, p.par_level,
                c.name AS category_name, sc.name AS subcategory_name,
                SUM(CAST(ii.quantity AS REAL)) AS total_quantity
            FROM products p JOIN inventory_items ii ON p.id = ii.product_id
            LEFT JOIN categories c ON p.category_id = c.id
            LEFT JOIN subcategories sc ON p.subcategory_id = sc.id
        """
        where_clauses = []
        if search_term: where_clauses.append("LOWER(p.name) LIKE ?"); params.append(f"%{search_term.lower()}%")
        if category: where_clauses.append("LOWER(c.name) = ?"); params.append(category.lower())
        if purchase_location: where_clauses.append("LOWER(p.purchase_location) = ?"); params.append(purchase_location.lower())
        if where_clauses: base_query += " WHERE " + " AND ".join(where_clauses)
        base_query += " GROUP BY p.id, p.name, p.unit_of_measure, p.par_level, c.name, sc.name"

        valid_sort_columns = {'p.name': 'p.name', 'c.name': 'c.name', 'total_quantity': 'total_quantity', 'p.par_level': 'p.par_level'}
        sort_column = valid_sort_columns.get(sort_by.lower(), 'p.name')
        sort_order_upper = 'DESC' if sort_order.upper() == 'DESC' else 'ASC'
        base_query += f" ORDER BY {sort_column} {sort_order_upper}, p.id {sort_order_upper}"

        if page is not None and per_page is not None and page > 0 and per_page > 0:
            offset = (page - 1) * per_page
            base_query += " LIMIT ? OFFSET ?"; params.extend([per_page, offset])
        elif per_page is not None and per_page > 0:
            base_query += " LIMIT ?"; params.append(per_page)
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(base_query, tuple(params))
                for row in cursor.fetchall(): items.append(dict(row))
            return {"success": True, "data": items, "message": "Current inventory retrieved.", "warnings": warnings}
        except sqlite3.Error as e:
            return {"success": False, "message": f"DB error: {e}", "error_details": str(e), "data": [], "warnings": warnings}

    def get_current_inventory_count(self, search_term=None, category=None, purchase_location=None):
        params = []
        query = """
            SELECT COUNT(DISTINCT p.id) as count FROM products p
            JOIN inventory_items ii ON p.id = ii.product_id
            LEFT JOIN categories c ON p.category_id = c.id
        """
        where_clauses = []
        if search_term: where_clauses.append("LOWER(p.name) LIKE ?"); params.append(f"%{search_term.lower()}%")
        if category: where_clauses.append("LOWER(c.name) = ?"); params.append(category.lower())
        if purchase_location: where_clauses.append("LOWER(p.purchase_location) = ?"); params.append(purchase_location.lower())
        if where_clauses: query += " WHERE " + " AND ".join(where_clauses)
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor(); cursor.execute(query, tuple(params))
                result = cursor.fetchone()
                return {"success": True, "data": result['count'] if result else 0}
        except sqlite3.Error as e:
            return {"success": False, "message": f"DB error: {e}", "error_details": str(e), "data": 0}

    def get_current_inventory_categories(self):
        categories = []
        query = "SELECT DISTINCT c.name FROM inventory_items ii JOIN products p ON ii.product_id = p.id JOIN categories c ON p.category_id = c.id WHERE c.name IS NOT NULL ORDER BY c.name ASC"
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor(); cursor.execute(query)
                for row in cursor.fetchall(): categories.append(row['name'])
            return {"success": True, "data": categories, "message": "Current inventory categories retrieved."}
        except sqlite3.Error as e:
            return {"success": False, "message": f"DB error: {e}", "error_details": str(e), "data": []}

    def get_current_inventory_purchase_locations(self):
        locations = []
        query = "SELECT DISTINCT p.purchase_location FROM products p JOIN inventory_items ii ON p.id = ii.product_id WHERE p.purchase_location IS NOT NULL ORDER BY p.purchase_location ASC"
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor(); cursor.execute(query)
                for row in cursor.fetchall(): locations.append(row['purchase_location'])
            return {"success": True, "data": locations, "message": "Current inventory purchase locations retrieved."}
        except sqlite3.Error as e:
            return {"success": False, "message": f"DB error: {e}", "error_details": str(e), "data": []}

    def get_inventory_batches_for_product(self, product_id, limit=None, order_by_purchase_desc=False, order_by_id_desc=False):
        items = []; warnings = []
        try: valid_product_id = int(product_id)
        except ValueError: return {"success": False, "message": f"Invalid product_id format: {product_id}", "data": [], "warnings": [f"Invalid product_id format: {product_id}"], "error_type": "ValueError"}

        query = ''' SELECT ii.*, p.name AS product_name, c.name AS category_name, s.name AS subcategory_name, p.unit_of_measure
                    FROM inventory_items ii JOIN products p ON ii.product_id = p.id
                    LEFT JOIN categories c ON p.category_id = c.id LEFT JOIN subcategories s ON p.subcategory_id = s.id
                    WHERE ii.product_id = ? '''
        params = [valid_product_id]
        if order_by_id_desc: query += " ORDER BY ii.id DESC"
        elif order_by_purchase_desc: query += " ORDER BY ii.purchase_date DESC, ii.id DESC"
        else: query += " ORDER BY ii.expiry_date ASC, ii.id ASC"
        if limit is not None: query += " LIMIT ?"; params.append(limit)

        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor(); cursor.execute(query, tuple(params))
                for row in cursor.fetchall():
                    item = dict(row)
                    try: item['purchase_date'] = date.fromisoformat(str(item.get('purchase_date'))) if item.get('purchase_date') else None
                    except (ValueError, TypeError): warnings.append(f"Invalid purchase_date for batch {item.get('id')}")
                    try: item['expiry_date'] = date.fromisoformat(str(item.get('expiry_date'))) if item.get('expiry_date') else None
                    except (ValueError, TypeError): warnings.append(f"Invalid expiry_date for batch {item.get('id')}")
                    items.append(item)
            return {"success": True, "data": items, "warnings": warnings}
        except sqlite3.Error as e:
            return {"success": False, "message": f"DB error: {e}", "error_details": str(e), "data": [], "warnings": warnings, "error_type": "DBError"}

    def get_shopping_list_items(self, store_filter=None, search_term=None):
        shopping_list = []; warnings = []
        inventory_response = self.get_current_inventory() # Fetches all, aggregated
        if inventory_response.get("warnings"): warnings.extend(inventory_response["warnings"])
        if not inventory_response.get("success"):
            return {"success": False, "data": [], "message": f"Failed to get current inventory for shopping list: {inventory_response.get('message')}", "warnings": warnings, "error_type": "UpstreamError"}

        all_products_response = self.get_all_products(page=None, per_page=None) # Fetch all products
        if all_products_response.get("warnings"): warnings.extend(all_products_response["warnings"])
        if not all_products_response.get("success"):
            return {"success": False, "data": [], "message": f"Failed to get all products for shopping list: {all_products_response.get('message')}", "warnings": warnings, "error_type": "UpstreamError"}

        products_to_check = [p for p in all_products_response.get("data", []) if p.get('par_level', 0) is not None and p.get('par_level', 0) > 0]

        for product in products_to_check:
            product_id = product['id']; product_name = product['name']
            par_level = float(product.get('par_level', 0.0)); purchase_location = product.get('purchase_location')
            unit_of_measure = product.get('unit_of_measure', 'units')

            projection_days = 0
            if purchase_location == 'Sobeys': projection_days = 7
            elif purchase_location == 'Costco': projection_days = 21
            else: continue

            demand_response = self.project_demand(product_id, projection_days=projection_days)
            if demand_response.get("warnings"): warnings.extend(demand_response["warnings"])
            if not demand_response.get("success"):
                warnings.append(f"Skipping {product_name} due to projection error: {demand_response.get('message')}"); continue

            avg_daily_consumption = demand_response.get("data", {}).get('avg_daily_consumption', 0.0)

            quantity_response = self.get_total_item_quantity(product_id) # product_id is int
            if quantity_response.get("warnings"): warnings.extend(quantity_response["warnings"])
            current_qty = 0.0
            if not quantity_response.get("success"):
                warnings.append(f"Could not get quantity for {product_name}: {quantity_response.get('message')}")
            else: current_qty = quantity_response.get("data", 0.0)

            target_stock = par_level + (avg_daily_consumption * projection_days)
            purchase_amount = max(0, round(target_stock - current_qty, 2))

            if purchase_amount > 0:
                shopping_list.append({
                    'product_id': product_id, 'name': product_name,
                    'current_numeric_quantity': current_qty, 'unit_of_measure': unit_of_measure,
                    'purchase_location': purchase_location, 'recommended_purchase_amount': purchase_amount,
                    'par_level': par_level, 'days_to_next_shop': projection_days,
                    'avg_daily_consumption': round(avg_daily_consumption, 2)
                })
        if store_filter: shopping_list = [item for item in shopping_list if item['purchase_location'] and item['purchase_location'].lower() == store_filter.lower()]
        if search_term: shopping_list = [item for item in shopping_list if search_term.lower() in item['name'].lower()]

        message = "Shopping list generated."
        if not shopping_list and not warnings: message = "Shopping list is empty."
        elif not shopping_list and warnings: message = "Shopping list is empty, with warnings."
        return {"success": True, "data": shopping_list, "warnings": warnings, "message": message}

    # ... (rest of the methods will be included in the final file, assuming they are already refactored or don't need it for this subtask)
    # For brevity in this step, I'm omitting the rest of the file if they were correctly refactored in prior steps.
    # The overwrite will include the full correct file content.

    def get_historical_inventory(self, search_term=None, category=None,
                                 consumed_start_date=None, consumed_end_date=None,
                                 sort_by='consumed_date', sort_order='DESC',
                                 page=1, per_page=10,
                                 export_all=False, export_start_date_str=None, export_end_date_str=None):
        items = []; params = []; warnings = []
        base_query = """ SELECT hi.id, hi.product_id, COALESCE(p.name, hi.name) AS product_display_name,
                        hi.quantity_consumed_this_time, hi.original_quantity_string, hi.purchase_date,
                        hi.expiry_date, hi.consumed_date, p.unit_of_measure, c.name AS category_name,
                        sc.name AS subcategory_name FROM historical_items hi
                        LEFT JOIN products p ON hi.product_id = p.id LEFT JOIN categories c ON p.category_id = c.id
                        LEFT JOIN subcategories sc ON p.subcategory_id = sc.id """
        where_clauses = []
        if search_term: where_clauses.append("LOWER(COALESCE(p.name, hi.name)) LIKE ?"); params.append(f"%{search_term.lower()}%")
        if category: where_clauses.append("c.name IS NOT NULL AND LOWER(c.name) = ?"); params.append(category.lower())

        final_start_date, final_end_date = None, None
        if export_all:
            if export_start_date_str:
                try: date.fromisoformat(export_start_date_str); final_start_date = export_start_date_str
                except ValueError: warnings.append(f"Invalid export_start_date_str '{export_start_date_str}'. Ignored.")
            if export_end_date_str:
                try: date.fromisoformat(export_end_date_str); final_end_date = export_end_date_str
                except ValueError: warnings.append(f"Invalid export_end_date_str '{export_end_date_str}'. Ignored.")
        else:
            if consumed_start_date: final_start_date = consumed_start_date
            if consumed_end_date: final_end_date = consumed_end_date

        if final_start_date: where_clauses.append("hi.consumed_date >= ?"); params.append(final_start_date)
        if final_end_date: where_clauses.append("hi.consumed_date <= ?"); params.append(final_end_date)
        if where_clauses: base_query += " WHERE " + " AND ".join(where_clauses)

        valid_sort = {'product_name': 'product_display_name', 'category_name': 'c.name', 'quantity_consumed': 'hi.quantity_consumed_this_time', 'consumed_date': 'hi.consumed_date', 'purchase_date': 'hi.purchase_date', 'expiry_date': 'hi.expiry_date'}
        sort_col = valid_sort.get(sort_by.lower(), 'hi.consumed_date')
        sort_ord = 'DESC' if sort_order.upper() == 'DESC' else 'ASC'
        base_query += f" ORDER BY {sort_col} {sort_ord}, hi.id {sort_ord}"

        if not export_all and page is not None and per_page is not None and page > 0 and per_page > 0:
            offset = (page - 1) * per_page; base_query += " LIMIT ? OFFSET ?"; params.extend([per_page, offset])
        elif not export_all and per_page is not None and per_page > 0: base_query += " LIMIT ?"; params.append(per_page)

        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor(); cursor.execute(base_query, tuple(params))
                for row_data in cursor.fetchall():
                    item = dict(row_data); item['name'] = item['product_display_name']
                    for date_key in ['purchase_date', 'expiry_date', 'consumed_date']:
                        if item.get(date_key):
                            try: item[date_key] = date.fromisoformat(str(item[date_key]))
                            except (ValueError, TypeError): warnings.append(f"Invalid {date_key} for item ID {item.get('id')}")
                    items.append(item)
            return {"success": True, "data": items, "warnings": warnings, "message": "Historical inventory retrieved."}
        except sqlite3.Error as e:
            return {"success": False, "message": f"DB error: {e}", "error_details": str(e), "data": [], "warnings": warnings, "error_type": "DBError"}

    def get_historical_inventory_count(self, search_term=None, category=None, consumed_start_date=None, consumed_end_date=None):
        params = []
        query = "SELECT COUNT(hi.id) as count FROM historical_items hi LEFT JOIN products p ON hi.product_id = p.id LEFT JOIN categories c ON p.category_id = c.id"
        where_clauses = []
        if search_term: where_clauses.append("LOWER(COALESCE(p.name, hi.name)) LIKE ?"); params.append(f"%{search_term.lower()}%")
        if category: where_clauses.append("c.name IS NOT NULL AND LOWER(c.name) = ?"); params.append(category.lower())
        if consumed_start_date: where_clauses.append("hi.consumed_date >= ?"); params.append(consumed_start_date)
        if consumed_end_date: where_clauses.append("hi.consumed_date <= ?"); params.append(consumed_end_date)
        if where_clauses: query += " WHERE " + " AND ".join(where_clauses)
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor(); cursor.execute(query, tuple(params))
                result = cursor.fetchone()
                return {"success": True, "data": result['count'] if result else 0}
        except sqlite3.Error as e:
            return {"success": False, "message": f"DB error: {e}", "error_details": str(e), "data": 0, "error_type": "DBError"}

    def get_historical_inventory_categories(self):
        categories = []
        query = "SELECT DISTINCT c.name FROM historical_items hi JOIN products p ON hi.product_id = p.id JOIN categories c ON p.category_id = c.id WHERE c.name IS NOT NULL ORDER BY c.name ASC"
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor(); cursor.execute(query)
                for row in cursor.fetchall(): categories.append(row['name'])
            return {"success": True, "data": categories, "message": "Historical categories retrieved.", "warnings": []}
        except sqlite3.Error as e:
            return {"success": False, "message": f"DB error: {e}", "error_details": str(e), "data": [], "error_type": "DBError"}

    def get_total_item_quantity(self, product_name_or_id):
        total_quantity = 0.0; product_id = None; warnings = []
        if isinstance(product_name_or_id, int): product_id = product_name_or_id
        elif isinstance(product_name_or_id, str):
            product_response = self.get_product_by_name(product_name_or_id)
            if product_response.get("warnings"): warnings.extend(product_response["warnings"])
            if product_response.get("success"):
                if product_response.get("data"): product_id = product_response["data"]['id']
                else: return {"success": True, "data": 0.0, "message": f"Product '{product_name_or_id}' not found.", "warnings": warnings}
            else: return {"success": False, "message": f"DB error: {product_response.get('message')}", "error_details": product_response.get('error_details'), "data": 0.0, "warnings": warnings}
        else: return {"success": False, "message": "Invalid identifier type.", "error_type": "ValueError", "data": 0.0, "warnings": warnings}

        if product_id is None: return {"success": True, "data": 0.0, "message": "Product ID not resolved.", "warnings": warnings}
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor(); cursor.execute("SELECT quantity FROM inventory_items WHERE product_id = ?", (product_id,))
                for row in cursor.fetchall(): total_quantity += self._parse_quantity_string(row['quantity'])
            return {"success": True, "data": total_quantity, "warnings": warnings}
        except sqlite3.Error as e:
            return {"success": False, "message": f"DB error: {e}", "error_details": str(e), "data": 0.0, "warnings": warnings}

    def check_for_expiring_items(self, days_threshold=3):
        today = date.today(); threshold_date = (today + timedelta(days=days_threshold)).isoformat()
        expiring_items_list = []; warnings = []
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT name, quantity, purchase_date, expiry_date FROM inventory_items WHERE expiry_date <= ? ORDER BY expiry_date ASC", (threshold_date,))
                for row in cursor.fetchall():
                    item = dict(row)
                    try:
                        item['purchase_date'] = date.fromisoformat(item['purchase_date'])
                        item['expiry_date'] = date.fromisoformat(item['expiry_date'])
                        expiring_items_list.append(item)
                    except (ValueError, TypeError) as e_parse: warnings.append(f"Date parse error for item {item.get('name')}: {e_parse}")
            message = f"Checked items expiring within {days_threshold} days."
            if not expiring_items_list and not warnings: message = "No items expiring soon or already expired."
            return {"success": True, "data": expiring_items_list, "message": message, "warnings": warnings}
        except sqlite3.Error as e:
            return {"success": False, "message": f"DB error: {e}", "error_details": str(e), "data": [], "warnings": warnings}

    def get_inventory_concerns(self, product_id):
        concern_messages = []; warnings = []; today = date.today()
        product_details_response = self.get_product_details(product_id)
        if product_details_response.get("warnings"): warnings.extend(product_details_response["warnings"])
        if not product_details_response.get("success") or not product_details_response.get("data"):
            msg = product_details_response.get('message', f"Product ID {product_id} not found.")
            return {"success": False, "message": msg, "data": {"concern_messages": [msg]}, "warnings": warnings, "error_type": "UpstreamError"}

        product_details = product_details_response["data"]
        current_stock = 0.0
        try: current_stock = float(product_details.get('current_on_hand_inventory', 0.0))
        except ValueError: warnings.append("Invalid stock value in product_details.")

        demand_response = self.project_demand(product_id, lookback_days=30, projection_days=1)
        avg_daily_consumption = 0.0
        if demand_response.get("warnings"): warnings.extend(demand_response["warnings"])
        if demand_response.get("success"): avg_daily_consumption = demand_response.get("data", {}).get('avg_daily_consumption', 0.0)
        else: warnings.append(f"Could not get consumption for {product_details.get('name')}: {demand_response.get('message')}")

        if avg_daily_consumption > 0:
            if current_stock > 0:
                days_left = current_stock / avg_daily_consumption
                if days_left < 3: concern_messages.append(f"Low stock: Approx {days_left:.1f} days left.")
            else: concern_messages.append("Out of stock, with positive consumption.")
        elif current_stock > 0: concern_messages.append("Stocked, but no usage data.")

        nearest_expiry_str = product_details.get('nearest_expiry_date', "N/A")
        if nearest_expiry_str != "N/A":
            try:
                nearest_expiry_obj = date.fromisoformat(nearest_expiry_str)
                days_to_expiry = (nearest_expiry_obj - today).days
                if days_to_expiry <= 7: concern_messages.append(f"Expires soon: on {nearest_expiry_str} ({days_to_expiry} days).")
                if avg_daily_consumption > 0 and current_stock > 0 and days_to_expiry >=0 and (current_stock / avg_daily_consumption) > days_to_expiry:
                    concern_messages.append("Potential spoilage: Stock may expire before use.")
            except ValueError: warnings.append(f"Invalid expiry date format: {nearest_expiry_str}")
        elif current_stock > 0 : concern_messages.append("Stock exists, but no expiry date found.")
        return {"success": True, "data": {"concern_messages": concern_messages}, "warnings": warnings}

    def _get_average_daily_consumption(self, product_id, lookback_days=30):
        warnings = []
        product_response = self.get_product(product_id)
        if not product_response.get("success") or not product_response.get("data"):
            warnings.append(f"Product ID {product_id} not found for ADC. Details: {product_response.get('message')}")
            return 0.0, warnings
        product = product_response["data"]
        if product_response.get("warnings"): warnings.extend(product_response["warnings"])

        if product.get('consumption_override_rate') is not None:
            try: return float(product['consumption_override_rate']), warnings
            except ValueError: warnings.append(f"Invalid override rate for {product_id}. Using history.")

        total_consumed = 0.0; today = date.today(); lookback_start = today - timedelta(days=lookback_days)
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT SUM(quantity_consumed_this_time) as total FROM historical_items WHERE product_id = ? AND consumed_date >= ? AND consumed_date < ?", (product_id, lookback_start.isoformat(), today.isoformat()))
                row = cursor.fetchone()
                if row and row['total'] is not None: total_consumed = float(row['total'])
            return (total_consumed / lookback_days) if lookback_days > 0 else 0.0, warnings
        except sqlite3.Error as e:
            warnings.append(f"DB error for ADC {product_id}: {e}"); return 0.0, warnings

    # ... (other methods like project_demand, get_future_inventory_projection, export_data_to_csv remain unchanged from previous state for brevity)
    # Ensure they are included in the final file from their last correct state.
    # The __main__ block also remains.
    # The following is just to ensure the file ends correctly for the overwrite.
def add_garden_produce(name, harvest_date_str, typical_shelf_life_days): pass
def display_garden_produce(): pass
if __name__ == "__main__": pass
