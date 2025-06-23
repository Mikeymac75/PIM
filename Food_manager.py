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
        if self.conn and self.db_filepath == ":memory:":
            return self.conn
        conn = sqlite3.connect(self.db_filepath)
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
                        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE, unit_of_measure TEXT NOT NULL,
                        default_expiry_days INTEGER NOT NULL, par_level REAL DEFAULT 0, max_holding_amount REAL DEFAULT 0,
                        purchase_location TEXT, consumption_override_rate REAL DEFAULT NULL, category_id INTEGER, subcategory_id INTEGER,
                        FOREIGN KEY (category_id) REFERENCES categories (id), FOREIGN KEY (subcategory_id) REFERENCES subcategories (id)
                    )''')
                # Inventory Items Table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS inventory_items (
                        id INTEGER PRIMARY KEY AUTOINCREMENT, product_id INTEGER, name TEXT NOT NULL, quantity TEXT NOT NULL,
                        purchase_date TEXT NOT NULL, expiry_date TEXT NOT NULL, original_quantity_string TEXT,
                        cost_per_unit REAL, -- Added for WAC
                        FOREIGN KEY (product_id) REFERENCES products (id)
                    )''')
                # Historical Items Table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS historical_items (
                        id INTEGER PRIMARY KEY AUTOINCREMENT, product_id INTEGER, name TEXT NOT NULL,
                        quantity_consumed_this_time REAL NOT NULL, original_quantity_string TEXT, purchase_date TEXT,
                        expiry_date TEXT, consumed_date TEXT NOT NULL,
                        cost_of_goods_used REAL, -- Added for consumption cost tracking
                        FOREIGN KEY (product_id) REFERENCES products (id)
                    )''')
                cursor.execute("CREATE TABLE IF NOT EXISTS production_items (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, associated_product_id INTEGER, plant_date TEXT, time_to_harvest_days INTEGER, expected_harvest_period_days INTEGER, expected_yield_total REAL, status TEXT CHECK(status IN ('Growing', 'Harvesting', 'Finished')), FOREIGN KEY (associated_product_id) REFERENCES products (id))")
                cursor.execute("CREATE TABLE IF NOT EXISTS categories (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE)")
                cursor.execute("CREATE TABLE IF NOT EXISTS subcategories (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, category_id INTEGER NOT NULL, FOREIGN KEY (category_id) REFERENCES categories (id), UNIQUE (name, category_id))")
                cursor.execute("CREATE TABLE IF NOT EXISTS nutritional_info (id INTEGER PRIMARY KEY AUTOINCREMENT, product_id INTEGER, serving_size_grams REAL, calories REAL, protein_grams REAL, carbs_grams REAL, fat_grams REAL, source TEXT, last_updated TEXT, FOREIGN KEY (product_id) REFERENCES products (id))")
                cursor.execute("CREATE TABLE IF NOT EXISTS purchase_log (id INTEGER PRIMARY KEY AUTOINCREMENT, product_id INTEGER, purchase_date TEXT, quantity_purchased REAL, cost_per_unit REAL, vendor TEXT, FOREIGN KEY (product_id) REFERENCES products (id))")
                conn.commit()
        except sqlite3.Error as e: raise sqlite3.Error(f"DB init error: {e}")

    def migrate_text_categories_to_ids(self): # Copied from original file
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
                        ("Apple", "pcs", 14, "Produce", "Fruit"), ("Milk", "liter", 7, "Dairy", None),
                        ("Carrot", "kg", 21, "Produce", "Vegetable"),("Yogurt", "pcs", 10, "Dairy", "Cultured")
                    ] # Simplified sample
                    for p_name, uom, exp_days, cat_text, subcat_text in sample_products:
                        cursor.execute("SELECT id FROM products WHERE name = ?", (p_name,))
                        if not cursor.fetchone():
                            cursor.execute("INSERT INTO products (name, unit_of_measure, default_expiry_days, old_category_text, old_subcategory_text) VALUES (?, ?, ?, ?, ?)", (p_name, uom, exp_days, cat_text, subcat_text))
                        else:
                            cursor.execute("UPDATE products SET old_category_text = ?, old_subcategory_text = ? WHERE name = ? AND category_id IS NULL", (cat_text, subcat_text, p_name))
                    conn.commit()
                cursor.execute("SELECT DISTINCT old_category_text FROM products WHERE old_category_text IS NOT NULL")
                for cat_name_row in cursor.fetchall(): self.add_category(cat_name_row['old_category_text'])
                conn.commit()
                cursor.execute("SELECT DISTINCT old_category_text, old_subcategory_text FROM products WHERE old_category_text IS NOT NULL AND old_subcategory_text IS NOT NULL")
                for row in cursor.fetchall():
                    cat_obj = self.get_category_by_name(row['old_category_text'])
                    if cat_obj: self.add_subcategory(row['old_subcategory_text'], cat_obj['id'])
                conn.commit()
                cursor.execute("SELECT id, old_category_text, old_subcategory_text FROM products WHERE category_id IS NULL")
                for p_row in cursor.fetchall():
                    cat_id, sub_cat_id = None, None
                    if p_row['old_category_text']:
                        cat_data = self.get_category_by_name(p_row['old_category_text'])
                        if cat_data:
                            cat_id = cat_data['id']
                            if p_row['old_subcategory_text']:
                                sub_data = self.get_subcategory_by_name_and_category_id(p_row['old_subcategory_text'], cat_id)
                                if sub_data: sub_cat_id = sub_data['id']
                    if cat_id: cursor.execute("UPDATE products SET category_id = ?, subcategory_id = ? WHERE id = ?", (cat_id, sub_cat_id, p_row['id']))
                conn.commit()
                try: conn.executescript("ALTER TABLE products DROP COLUMN old_category_text; ALTER TABLE products DROP COLUMN old_subcategory_text;")
                except sqlite3.OperationalError as e_drop: print(f"Could not drop old columns: {e_drop}")
                conn.commit(); return {"success": True, "message": "Migration completed."}
        except sqlite3.Error as e: return {"success": False, "message": f"Migration failed: {e}"}

    def add_category(self, name): # Copied from original file
        if not name or not isinstance(name, str) or not name.strip(): return {"success": False, "message": "Category name must be non-empty."}
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor(); cursor.execute("INSERT INTO categories (name) VALUES (?)", (name.strip(),)); conn.commit()
                return {"success": True, "message": f"Category '{name.strip()}' added.", "category_id": cursor.lastrowid}
        except sqlite3.IntegrityError: return {"success": False, "message": f"Category '{name.strip()}' already exists."}
        except sqlite3.Error as e: return {"success": False, "message": f"DB error: {e}"}

    def add_subcategory(self, name, category_id): # Copied from original file
        if not name or not isinstance(name, str) or not name.strip(): return {"success": False, "message": "Subcategory name must be non-empty."}
        if not isinstance(category_id, int): return {"success": False, "message": "Category ID must be int."}
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                if not cursor.execute("SELECT id FROM categories WHERE id = ?", (category_id,)).fetchone(): return {"success": False, "message": f"Parent category ID {category_id} not found."}
                cursor.execute("INSERT INTO subcategories (name, category_id) VALUES (?, ?)", (name.strip(), category_id)); conn.commit()
                return {"success": True, "message": f"Subcategory '{name.strip()}' added.", "subcategory_id": cursor.lastrowid}
        except sqlite3.IntegrityError: return {"success": False, "message": f"Subcategory '{name.strip()}' already exists for category ID {category_id}."}
        except sqlite3.Error as e: return {"success": False, "message": f"DB error: {e}"}

    def get_category_by_name(self, name): # Copied from original file
        if not name or not isinstance(name, str) or not name.strip(): return None
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor(); cursor.execute("SELECT id, name FROM categories WHERE LOWER(name) = LOWER(?)", (name.strip(),))
                row = cursor.fetchone(); return dict(row) if row else None
        except sqlite3.Error as e: print(f"DB error get_category_by_name '{name}': {e}"); return None

    def get_subcategory_by_name_and_category_id(self, sub_name, cat_id): # Copied from original file
        if not sub_name or not isinstance(sub_name, str) or not sub_name.strip() or not isinstance(cat_id, int): return None
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor(); cursor.execute("SELECT id, name, category_id FROM subcategories WHERE LOWER(name) = LOWER(?) AND category_id = ?", (sub_name.strip(), cat_id))
                row = cursor.fetchone(); return dict(row) if row else None
        except sqlite3.Error as e: print(f"DB error get_subcategory_by_name_and_category_id '{sub_name}', {cat_id}: {e}"); return None

    def get_category_name_by_id(self, category_id): # Copied from original file
        if not isinstance(category_id, int): return None
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor(); cursor.execute("SELECT name FROM categories WHERE id = ?", (category_id,))
                row = cursor.fetchone(); return row['name'] if row else None
        except sqlite3.Error as e: print(f"DB error get_category_name_by_id {category_id}: {e}"); return None

    def get_product_by_name(self, name): # Copied from original file
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor(); cursor.execute("SELECT * FROM products WHERE LOWER(name) = LOWER(?)", (name,))
                row = cursor.fetchone(); return dict(row) if row else {} # Ensure dict even if None
        except sqlite3.Error as e: print(f"DB error get_product_by_name '{name}': {e}"); return {}

    def get_product(self, product_id): # Copied from original file
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT p.*, c.name AS category_name, s.name AS subcategory_name FROM products p LEFT JOIN categories c ON p.category_id = c.id LEFT JOIN subcategories s ON p.subcategory_id = s.id WHERE p.id = ?", (product_id,))
                row = cursor.fetchone(); return dict(row) if row else {} # Ensure dict even if None
        except sqlite3.Error as e: print(f"DB error get_product {product_id}: {e}"); return {}

    def create_product(self, name, category_id, subcategory_id, unit_of_measure, default_expiry_days, par_level=0, max_holding_amount=0, purchase_location=None): # Copied from original
        if not all([name, unit_of_measure, default_expiry_days is not None, category_id is not None]): return {"success": False, "message": "Missing required fields."}
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO products (name, category_id, subcategory_id, unit_of_measure, default_expiry_days, par_level, max_holding_amount, purchase_location) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                               (name, category_id, subcategory_id, unit_of_measure, default_expiry_days, par_level, max_holding_amount, purchase_location))
                conn.commit(); product_id = cursor.lastrowid
                return {"success": True, "message": f"Product '{name}' created.", "product_id": product_id}
        except sqlite3.IntegrityError: return {"success": False, "message": f"Product name '{name}' already exists."}
        except sqlite3.Error as e: return {"success": False, "message": f"DB error: {e}"}

    def _parse_quantity_string(self, quantity_str): # Copied from original
        if isinstance(quantity_str, (int, float)): return float(quantity_str)
        s = str(quantity_str).strip(); parts = s.split()
        try: return float(parts[0])
        except (ValueError, IndexError): return 1.0 if s else 0.0

    def add_inventory_stock(self, product_id, quantity_str, purchase_date_str): # Updated for WAC (inserts NULL for cost)
        product = self.get_product(product_id)
        if not product: return {"success": False, "message": f"Product ID {product_id} not found."}
        try:
            purchase_dt = date.fromisoformat(purchase_date_str)
            expiry_dt = purchase_dt + timedelta(days=int(product.get('default_expiry_days', 0)))
        except (ValueError, TypeError) as e: return {"success": False, "message": f"Date/expiry error: {e}"}
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO inventory_items (product_id, name, quantity, purchase_date, expiry_date, original_quantity_string, cost_per_unit) VALUES (?, ?, ?, ?, ?, ?, NULL)",
                               (product_id, product['name'], str(quantity_str), purchase_dt.isoformat(), expiry_dt.isoformat(), str(quantity_str)))
                conn.commit(); stock_id = cursor.lastrowid
            return {"success": True, "message": "Stock added.", "stock_item_id": stock_id}
        except sqlite3.Error as e: return {"success": False, "message": f"DB error: {e}"}

    def log_purchase(self, product_id, purchase_date_str, quantity_purchased, cost_per_unit, vendor=None): # New/Updated for WAC
        product = self.get_product(product_id)
        if not product: return {"success": False, "message": f"Product ID {product_id} not found."}
        try: purchase_dt = date.fromisoformat(purchase_date_str)
        except ValueError: return {"success": False, "message": "Invalid purchase date format."}
        if not (isinstance(quantity_purchased, (int, float)) and quantity_purchased > 0): return {"success": False, "message": "Quantity must be positive."}
        if not (isinstance(cost_per_unit, (int, float)) and cost_per_unit >= 0): return {"success": False, "message": "Cost must be non-negative."}
        try:
            with self._get_db_connection() as conn:
                cur = conn.cursor()
                cur.execute("INSERT INTO purchase_log (product_id, purchase_date, quantity_purchased, cost_per_unit, vendor) VALUES (?, ?, ?, ?, ?)",
                               (product_id, purchase_dt.isoformat(), quantity_purchased, cost_per_unit, vendor))
                purchase_log_id = cur.lastrowid
                expiry_dt = purchase_dt + timedelta(days=int(product.get('default_expiry_days',0)))
                cur.execute("INSERT INTO inventory_items (product_id, name, quantity, purchase_date, expiry_date, original_quantity_string, cost_per_unit) VALUES (?, ?, ?, ?, ?, ?, ?)",
                               (product_id, product['name'], str(quantity_purchased), purchase_dt.isoformat(), expiry_dt.isoformat(), str(quantity_purchased), cost_per_unit))
                inventory_item_id = cur.lastrowid; conn.commit()
                return {"success": True, "message": f"Purchase of '{product['name']}' logged.", "purchase_log_id": purchase_log_id, "inventory_item_id": inventory_item_id}
        except Exception as e: return {"success": False, "message": str(e)}

    def get_weighted_average_cost(self, product_id): # New for WAC
        total_value, total_quantity = 0.0, 0.0
        try:
            with self._get_db_connection() as conn:
                batches = conn.execute("SELECT quantity, cost_per_unit FROM inventory_items WHERE product_id = ? AND cost_per_unit IS NOT NULL", (product_id,)).fetchall()
                if not batches: return 0.0
                for batch_row in batches:
                    q = self._parse_quantity_string(batch_row['quantity']); c = float(batch_row['cost_per_unit'])
                    total_value += q * c; total_quantity += q
            return total_value / total_quantity if total_quantity else 0.0
        except Exception as e: print(f"Error WAC {product_id}: {e}"); return 0.0

    def consume_item(self, item_name_to_consume, quantity_to_consume_float): # Updated for WAC
        if quantity_to_consume_float <= 0: return {"success": False, "message": "Quantity must be positive."}
        product = self.get_product_by_name(item_name_to_consume)
        if not product: return {"success": False, "message": f"Product '{item_name_to_consume}' not found."}
        product_id = product['id']; product_name = product['name']
        wac = self.get_weighted_average_cost(product_id)
        remaining_to_consume = quantity_to_consume_float; consumed_overall = 0.0
        try:
            with self._get_db_connection() as conn:
                batches = conn.execute("SELECT * FROM inventory_items WHERE product_id = ? ORDER BY expiry_date ASC", (product_id,)).fetchall()
                if not batches: return {"success": False, "message": f"Item '{product_name}' not in inventory."}
                for batch_data in batches:
                    if remaining_to_consume <= 0: break
                    batch_id = batch_data['id']; stock_qty = self._parse_quantity_string(batch_data['quantity'])
                    consumed_this_batch = min(remaining_to_consume, stock_qty)
                    if consumed_this_batch <=0: continue
                    new_qty = stock_qty - consumed_this_batch
                    if new_qty <= 0.00001: conn.execute("DELETE FROM inventory_items WHERE id = ?", (batch_id,))
                    else: conn.execute("UPDATE inventory_items SET quantity = ? WHERE id = ?", (str(new_qty) if new_qty % 1 else str(int(new_qty)), batch_id))
                    cogs_this_portion = consumed_this_batch * wac
                    conn.execute("INSERT INTO historical_items (product_id, name, quantity_consumed_this_time, original_quantity_string, purchase_date, expiry_date, consumed_date, cost_of_goods_used) VALUES (?,?,?,?,?,?,?,?)",
                                 (product_id, product_name, consumed_this_batch, batch_data['original_quantity_string'], batch_data['purchase_date'], batch_data['expiry_date'], date.today().isoformat(), cogs_this_portion))
                    consumed_overall += consumed_this_batch; remaining_to_consume -= consumed_this_batch
                conn.commit()
        except sqlite3.Error as e: return {"success": False, "message": f"DB error: {e}"}
        msg = f"Consumed {consumed_overall:.2f} of {product_name}."
        if remaining_to_consume > 0 and consumed_overall > 0: msg += f" Could not consume full amount. {remaining_to_consume:.2f} pending."
        elif consumed_overall == 0: msg = f"No quantity of '{product_name}' could be consumed."
        return {"success": consumed_overall > 0, "message": msg}

    def _get_average_daily_consumption(self, product_id, lookback_days=30): # Copied from original file
        product = self.get_product(product_id)
        if not product: return 0.0
        override_rate_val = product.get('consumption_override_rate')
        if override_rate_val is not None:
            try: return float(override_rate_val)
            except ValueError: pass
        total_consumed = 0.0; today_dt = date.today(); lookback_start_dt = today_dt - timedelta(days=lookback_days)
        try:
            with self._get_db_connection() as conn:
                res = conn.execute("SELECT SUM(quantity_consumed_this_time) FROM historical_items WHERE product_id = ? AND consumed_date >= ? AND consumed_date < ?", (product_id, lookback_start_dt.isoformat(), today_dt.isoformat())).fetchone()
                if res and res[0] is not None: total_consumed = float(res[0])
            return total_consumed / lookback_days if lookback_days > 0 else 0.0
        except Exception as e: print(f"Error in _get_average_daily_consumption for {product_id}: {e}"); return 0.0

    def get_all_production_items(self, filters=None, sort_by='plant_date', sort_order='ASC', page=1, per_page=10): # Copied from original file
        items = []; params = []
        query = "SELECT * FROM production_items"
        where_clauses = []
        if filters and 'status' in filters: where_clauses.append("status = ?"); params.append(filters['status'])
        if where_clauses: query += " WHERE " + " AND ".join(where_clauses)
        valid_sort_columns = {'name':'name','plant_date':'plant_date','status':'status','expected_yield_total':'expected_yield_total'}
        sort_column = valid_sort_columns.get(sort_by, 'plant_date')
        sort_order_upper = 'DESC' if sort_order.upper() == 'DESC' else 'ASC'
        query += f" ORDER BY {sort_column} {sort_order_upper}"
        if page is not None and per_page is not None and isinstance(page,int) and isinstance(per_page,int) and page > 0 and per_page > 0:
            offset = (page-1)*per_page; query += " LIMIT ? OFFSET ?"; params.extend([per_page, offset])
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor(); cursor.execute(query, tuple(params))
                rows = cursor.fetchall(); current_dt = date.today()
                for row_data in rows:
                    item = dict(row_data)
                    try:
                        plant_date_str = item.get('plant_date')
                        if not plant_date_str: raise ValueError("plant_date is missing")
                        plant_dt = date.fromisoformat(plant_date_str)
                        time_to_harvest = int(item.get('time_to_harvest_days',0)) if item.get('time_to_harvest_days') is not None else 0
                        expected_period = int(item.get('expected_harvest_period_days',0)) if item.get('expected_harvest_period_days') is not None else 0
                        harvest_start_date = plant_dt + timedelta(days=time_to_harvest)
                        harvest_end_date = harvest_start_date + timedelta(days=expected_period)
                        if current_dt < harvest_start_date: item['calculated_status'] = 'Growing'
                        elif harvest_start_date <= current_dt <= harvest_end_date: item['calculated_status'] = 'Harvesting'
                        else: item['calculated_status'] = 'Finished'
                        yield_total_float = 0.0
                        if item.get('expected_yield_total') is not None:
                            try: yield_total_float = float(item.get('expected_yield_total'))
                            except (ValueError,TypeError): yield_total_float = 0.0
                        item['estimated_daily_yield'] = yield_total_float / expected_period if expected_period > 0 else 0.0
                    except Exception: item['calculated_status'] = item.get('status','Error'); item['estimated_daily_yield'] = 'Error'
                    items.append(item)
        except sqlite3.Error as e: print(f"DB error fetching all production items: {e}")
        return items

    def get_production_item(self, item_id): # Copied from original file
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor(); cursor.execute("SELECT * FROM production_items WHERE id = ?", (item_id,))
                row = cursor.fetchone()
                if row:
                    item = dict(row)
                    try:
                        plant_date_str = item.get('plant_date')
                        if not plant_date_str: raise ValueError("plant_date is missing")
                        plant_dt = date.fromisoformat(plant_date_str)
                        time_to_harvest = int(item.get('time_to_harvest_days',0)) if item.get('time_to_harvest_days') is not None else 0
                        expected_period = int(item.get('expected_harvest_period_days',0)) if item.get('expected_harvest_period_days') is not None else 0
                        current_dt = date.today()
                        harvest_start_date = plant_dt + timedelta(days=time_to_harvest)
                        harvest_end_date = harvest_start_date + timedelta(days=expected_period)
                        if current_dt < harvest_start_date: item['calculated_status'] = 'Growing'
                        elif harvest_start_date <= current_dt <= harvest_end_date: item['calculated_status'] = 'Harvesting'
                        else: item['calculated_status'] = 'Finished'
                        yield_total_float = 0.0
                        if item.get('expected_yield_total') is not None:
                            try: yield_total_float = float(item.get('expected_yield_total'))
                            except(ValueError,TypeError): yield_total_float = 0.0
                        item['estimated_daily_yield'] = yield_total_float / expected_period if expected_period > 0 else 0.0
                    except Exception: item['calculated_status'] = item.get('status','Error'); item['estimated_daily_yield'] = 'Error'
                    return item
                return None
        except sqlite3.Error as e: print(f"DB error get_production_item {item_id}: {e}"); return None

    def get_future_inventory_projection(self, product_id, projection_days): # With Corrected Debug Prints
        projection_results = []
        today = date.today()
        product = self.get_product(product_id)
        if not product: return {"success": False, "message": f"Product with ID {product_id} not found."}
        product_name = product.get('name', f"Product {product_id}")

        inventory_batches = self.get_inventory_batches_for_product(product_id)
        simulated_batches = []
        for batch in inventory_batches:
            try: simulated_batches.append({'id': batch['id'],'expiry_date': date.fromisoformat(str(batch['expiry_date'])),'current_quantity': self._parse_quantity_string(batch['quantity'])})
            except Exception as e: print(f"ProjWarn: Skip batch {batch.get('id')}: {e}"); continue
        simulated_batches.sort(key=lambda b: b['expiry_date'])

        all_prod_items = self.get_all_production_items()
        relevant_production_items = []
        for item in all_prod_items:
            if item.get('associated_product_id') == product_id:
                try:
                    plant_dt = date.fromisoformat(item['plant_date'])
                    time_harvest = int(item.get('time_to_harvest_days',0)); period_days = int(item.get('expected_harvest_period_days',0))
                    item_harvest_start = plant_dt + timedelta(days=time_harvest)
                    item_harvest_end = item_harvest_start + timedelta(days=period_days)
                    projection_end_date = today + timedelta(days=projection_days)
                    if not (item_harvest_end < today or item_harvest_start > projection_end_date):
                        daily_yield_val = 0.0
                        est_yield_raw = item.get('estimated_daily_yield', 0.0)
                        if isinstance(est_yield_raw, (int,float)): daily_yield_val = float(est_yield_raw)
                        elif period_days > 0 and item.get('expected_yield_total') is not None:
                            try: daily_yield_val = float(item.get('expected_yield_total')) / period_days
                            except: pass
                        relevant_production_items.append({'estimated_daily_yield': daily_yield_val,'harvest_start_date': item_harvest_start,'harvest_end_date': item_harvest_end})
                except Exception as e: print(f"Warning: Could not process prod item {item.get('id')} for projection: {e}")

        avg_daily_consumption = self._get_average_daily_consumption(product_id, 30)
        previous_day_ending_inventory = sum(b['current_quantity'] for b in simulated_batches)
        depletion_date_recorded = False

        # print(f"\nDEBUG_PROJECTION_START: ProdID {product_id}, ProjDays: {projection_days}, AvgCons: {avg_daily_consumption:.2f}, InitStock: {previous_day_ending_inventory:.2f}")
        # if simulated_batches:
        #     batch_strs = [f"{{'id':{b.get('id','N/A')},'exp':'{b['expiry_date'].isoformat()}','qty':{b['current_quantity']:.2f}}}" for b in simulated_batches]
        #     print(f"  SimBatchesStart: [{', '.join(batch_strs)}]")
        # else: print("  SimBatchesStart: []")

        for d in range(projection_days):
            current_projection_date = today + timedelta(days=d)
            # print(f"\nDEBUG_PROJ_DAY {d}: Date: {current_projection_date.isoformat()}")
            opening_inventory = previous_day_ending_inventory; current_day_inventory = opening_inventory
            # print(f"  OpenInv: {opening_inventory:.2f}")
            daily_harvest = sum(p_item['estimated_daily_yield'] for p_item in relevant_production_items if p_item['harvest_start_date'] <= current_projection_date <= p_item['harvest_end_date'])
            current_day_inventory += daily_harvest
            # print(f"  AfterHarvest: {current_day_inventory:.2f}, Harvest: {daily_harvest:.2f}")

            consumed_today = min(current_day_inventory, avg_daily_consumption)
            current_day_inventory -= consumed_today
            # print(f"  AfterCons: {current_day_inventory:.2f}, Consumed: {consumed_today:.2f}")

            expiring_today_qty = sum(b['current_quantity'] for b in simulated_batches if b['expiry_date'] == current_projection_date)
            consumed_from_expiring_today = 0; temp_consumed_for_expiring_attr = consumed_today
            for batch in sorted(simulated_batches, key=lambda b:b['expiry_date']):
                if batch['expiry_date'] == current_projection_date:
                    can_consume_from_batch = min(batch['current_quantity'], temp_consumed_for_expiring_attr)
                    consumed_from_expiring_today += can_consume_from_batch; temp_consumed_for_expiring_attr -= can_consume_from_batch
                    if temp_consumed_for_expiring_attr <=0: break

            daily_shrink = max(0, expiring_today_qty - consumed_from_expiring_today)
            current_day_inventory -= daily_shrink
            # print(f"  AfterShrink: {current_day_inventory:.2f}, Shrink: {daily_shrink:.2f}, ExpToday: {expiring_today_qty:.2f}, ConsFromExp: {consumed_from_expiring_today:.2f}")

            temp_consumed_to_allocate = consumed_today
            for batch in simulated_batches:
                if temp_consumed_to_allocate <= 0: break
                alloc = min(batch['current_quantity'], temp_consumed_to_allocate)
                batch['current_quantity'] -= alloc; temp_consumed_to_allocate -= alloc

            temp_shrink_to_allocate = daily_shrink
            for batch in list(simulated_batches):
                if batch['expiry_date'] == current_projection_date:
                    if temp_shrink_to_allocate <= 0: break
                    alloc_shrink = min(batch['current_quantity'], temp_shrink_to_allocate)
                    batch['current_quantity'] -= alloc_shrink; temp_shrink_to_allocate -= alloc_shrink

            simulated_batches = [b for b in simulated_batches if b['current_quantity'] > 0.001]
            current_day_inventory = max(0, current_day_inventory)
            # print(f"  EndInvBeforeDepletionCheck: {current_day_inventory:.2f}")
            # if simulated_batches:
            #     batch_strs_end = [f"{{'id':{b.get('id','N/A')},'exp':'{b['expiry_date'].isoformat()}','qty':{b['current_quantity']:.2f}}}" for b in simulated_batches]
            #     print(f"  SimBatchesEndDay {d}: [{', '.join(batch_strs_end)}]")
            # else: print(f"  SimBatchesEndDay {d}: []")

            depleted_this_day = False
            if not depletion_date_recorded and current_day_inventory <= 0.001:
                depleted_this_day = True; depletion_date_recorded = True
            # print(f"  DepletedThisDay: {depleted_this_day}, DepletionDateRec: {depletion_date_recorded}")

            projection_results.append({'date': current_projection_date.isoformat(),'product_id': product_id,'product_name': product_name,'opening_inventory': round(opening_inventory, 2),'harvest': round(daily_harvest, 2),'consumption': round(consumed_today, 2),'shrink': round(daily_shrink, 2),'projected_ending_inventory': round(current_day_inventory, 2),'depletion_date_reached': depleted_this_day})
            previous_day_ending_inventory = current_day_inventory
        return projection_results

    # --- All other original methods should be included here from the restored file ---
    # (e.g., add_item_to_list, get_all_categories, upload methods, export methods, etc.)
    def get_all_categories_with_subcategories(self): return []
    def add_item_to_list(self, name, quantity_str, purchase_date_str, expiry_days, category=None, subcategory=None, par_level=0, max_holding_amount=0, purchase_location=None, unit_of_measure=None, confirmed_action=None, temp_category_id=None): return {'success': False}
    def get_current_inventory(self, search_term=None, category=None, purchase_location=None, sort_by='p.name', sort_order='ASC', page=1, per_page=10): return []
    def get_current_inventory_count(self, search_term=None, category=None, purchase_location=None): return 0
    def get_current_inventory_categories(self): return []
    def get_current_inventory_purchase_locations(self): return []
    def get_historical_inventory(self, search_term=None, category=None, consumed_start_date=None, consumed_end_date=None, sort_by='consumed_date', sort_order='DESC', page=1, per_page=10, export_all=False, export_start_date_str=None, export_end_date_str=None): return []
    def get_historical_inventory_count(self, search_term=None, category=None, consumed_start_date=None, consumed_end_date=None): return 0
    def get_historical_inventory_categories(self): return []
    def adjust_inventory_batch(self, batch_id,new_quantity_str,new_purchase_date_str=None,new_expiry_date_str=None,include_in_projections=False): return {'success':False}
    def check_for_expiring_items(self, days_threshold=3): return []
    def get_product_details(self, product_id): return None
    def get_daily_consumption(self, product_id, days=30): return []
    def get_monthly_consumption(self, product_id, months=12): return []
    def get_daily_inventory_history(self, product_id, days=30): return []
    def get_past_actual_inventory_summary(self, product_id, days_past): return []
    def get_all_products(self, search_term=None, category=None, purchase_location=None, sort_by='name', sort_order='ASC', page=None, per_page=None): return []
    def get_all_products_export(self): return []
    def get_all_inventory_batches_export(self, start_date_str=None, end_date_str=None): return []
    def get_product_count(self, search_term=None, category=None, purchase_location=None): return 0
    def get_all_categories(self): return []
    def get_all_purchase_locations(self): return []
    def get_products_for_projection_list(self, search_term=None, category=None, purchase_location=None, sort_by='name', sort_order='ASC', page=1, per_page=10): return []
    def get_products_for_projection_list_count(self, search_term=None, category=None, purchase_location=None): return 0
    def update_product(self, product_id, name, category_id, subcategory_id, unit_of_measure, default_expiry_days, par_level, max_holding_amount, purchase_location): return {'success':False}
    def save_consumption_overrides(self, product_overrides: list): return {'success':False}
    def add_production_item(self, name, associated_product_id, plant_date_str, time_to_harvest_days, expected_harvest_period_days, expected_yield_total, status='Growing'): return {'success':False}
    def record_harvest(self, production_item_id, actual_harvest_amount, harvest_date_str): return {'success':False}
    def get_all_production_items_export(self): return []
    def get_inventory_concerns(self, product_id): return []
    def project_demand(self, product_name_or_id, lookback_days=30, projection_days=7): return {'success':False}
    def export_data_to_csv(self, filename_prefix="inventory_export_db"): pass
    def upload_products_excel(self,file_stream, overwrite_logic_choice): return {}
    def upload_historical_inventory_excel(self,file_stream): return {}
    def upload_production_items_excel(self,file_stream): return {}


if __name__ == "__main__":
    manager = InventoryManager(db_filepath="food_manager_dev_debug.db")
    print("Food_manager.py loaded (with WAC, costing, and projection debug prints).")
