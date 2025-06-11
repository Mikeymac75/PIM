import sqlite3
import csv
from datetime import date, timedelta, datetime
import os # For the demo part

class InventoryManager:
    def __init__(self, db_filepath="inventory.db"):
        self.db_filepath = db_filepath
        self._initialize_db()
        # Garden produce is not part of this class for now
        # self.my_garden_produce = [] 

    def _get_db_connection(self):
        """Establishes and returns a database connection."""
        conn = sqlite3.connect(self.db_filepath)
        conn.row_factory = sqlite3.Row # Access columns by name
        return conn

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
                        category TEXT,
                        subcategory TEXT,
                        unit_of_measure TEXT NOT NULL,
                        default_expiry_days INTEGER NOT NULL,
                        par_level REAL DEFAULT 0,
                        max_holding_amount REAL DEFAULT 0,
                        purchase_location TEXT
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
                conn.commit()
        except sqlite3.Error as e:
            raise sqlite3.Error(f"Database initialization error: {e}")
            # Depending on app design, might want to raise this or handle more gracefully

    # --- Product Management Methods ---
    def create_product(self, name, category, subcategory, unit_of_measure, default_expiry_days,
                       par_level=0, max_holding_amount=0, purchase_location=None):
        """Inserts a new product into the products table."""
        if not all([name, unit_of_measure, default_expiry_days is not None]): # category, subcategory can be None
            return {"success": False, "message": "Missing required product fields (name, unit_of_measure, default_expiry_days)."}

        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO products
                    (name, category, subcategory, unit_of_measure, default_expiry_days,
                     par_level, max_holding_amount, purchase_location)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (name, category, subcategory, unit_of_measure, default_expiry_days,
                      par_level, max_holding_amount, purchase_location))
                conn.commit()
                product_id = cursor.lastrowid
                return {"success": True, "message": f"Product '{name}' created successfully.", "product_id": product_id}
        except sqlite3.IntegrityError:
            return {"success": False, "message": f"Product name '{name}' already exists."}
        except sqlite3.Error as e:
            return {"success": False, "message": f"Database error creating product: {e}"}

    def get_product(self, product_id):
        """Retrieves a product by its ID."""
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM products WHERE id = ?", (product_id,))
                row = cursor.fetchone()
                return dict(row) if row else None
        except sqlite3.Error as e:
            print(f"Database error getting product by ID {product_id}: {e}")
            return None # Or raise error

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

    def get_all_products(self):
        """Retrieves all products from the products table, ordered by name."""
        items = []
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM products ORDER BY name ASC")
                rows = cursor.fetchall()
                for row in rows:
                    items.append(dict(row))
        except sqlite3.Error as e:
            print(f"Database error fetching all products: {e}")
        return items

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
            print(f"Added stock to DB: {product['name']} ({quantity_str}), Expires: {expiry_dt.isoformat()}")
            return {"success": True, "message": f"Stock for '{product['name']}' added successfully."}
        except sqlite3.Error as e:
            print(f"Database error adding inventory stock: {e}")
            return {"success": False, "message": f"Database error: {e}"}

    def get_current_inventory(self):
        """Retrieves all items from the current inventory, joined with product details, ordered by expiry date."""
        items = []
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                # Joined query to include product details
                cursor.execute('''
                    SELECT
                        ii.id, ii.product_id, ii.quantity, ii.purchase_date, ii.expiry_date,
                        ii.original_quantity_string,
                        p.name AS product_name, p.category, p.subcategory, p.unit_of_measure,
                        p.par_level, p.max_holding_amount, p.purchase_location
                    FROM inventory_items ii
                    JOIN products p ON ii.product_id = p.id
                    ORDER BY ii.expiry_date ASC
                ''')
                rows = cursor.fetchall()
                for row in rows:
                    item = dict(row)
                    item['purchase_date'] = date.fromisoformat(item['purchase_date'])
                    item['expiry_date'] = date.fromisoformat(item['expiry_date'])
                    items.append(item)
        except sqlite3.Error as e:
            print(f"Database error fetching current inventory: {e}")
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

    def get_historical_inventory(self):
        """Retrieves all items from the historical inventory, ordered by consumed date."""
        items = []
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                # Joined query to include product details, if product_id is not null
                # Using LEFT JOIN in case some historical items don't have a product_id (legacy data)
                # or if a product was deleted.
                cursor.execute('''
                    SELECT
                        hi.id, hi.product_id, hi.name AS historical_item_name,
                        hi.quantity_consumed_this_time, hi.original_quantity_string,
                        hi.purchase_date, hi.expiry_date, hi.consumed_date,
                        p.name AS product_name, p.category, p.subcategory, p.unit_of_measure
                    FROM historical_items hi
                    LEFT JOIN products p ON hi.product_id = p.id
                    ORDER BY hi.consumed_date DESC
                ''')
                rows = cursor.fetchall()
                for row in rows:
                    item = dict(row)
                    # Use product_name from products table if available, otherwise use historical_item_name
                    item['name'] = item['product_name'] if item['product_name'] else item['historical_item_name']
                    if item['purchase_date']: item['purchase_date'] = date.fromisoformat(item['purchase_date'])
                    if item['expiry_date']: item['expiry_date'] = date.fromisoformat(item['expiry_date'])
                    item['consumed_date'] = date.fromisoformat(item['consumed_date'])
                    items.append(item)
        except sqlite3.Error as e:
            print(f"Database error fetching historical inventory: {e}")
        return items

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
                    
                    new_quantity_db_str = "0"
                    if new_numeric_qty > 0:
                        original_parts = str(current_qty_str_in_db).split(maxsplit=1)
                        if len(original_parts) > 1:
                            try:
                                float(original_parts[0])
                                unit_suffix = original_parts[1]
                                new_quantity_db_str = f"{new_numeric_qty:.2f} {unit_suffix}"
                            except ValueError:
                                new_quantity_db_str = str(new_numeric_qty) if new_numeric_qty % 1 else str(int(new_numeric_qty))
                        else:
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

    def project_demand(self, item_name, lookback_days=30, projection_days=7):
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
        except sqlite3.Error as e:
            print(f"Database error fetching historical data for demand projection (Product ID: {product_id}): {e}")
            return {
                "product_id": product_id, "product_name": product_name, "unit_of_measure": product_unit,
                "current_stock": self.get_total_item_quantity(product_id),
                "avg_daily_consumption": 0, "days_to_depletion": "Error fetching history",
                "projected_need": 0, "lookback_days": lookback_days, "projection_days": projection_days,
                "success": False, "message": f"DB error calculating historical consumption: {e}"
            }

        avg_daily_consumption = (total_consumed_in_lookback / lookback_days) if lookback_days > 0 else 0.0
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
    # Note: To truly reset, delete DB_FILE before running again.
