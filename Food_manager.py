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
                # Current Inventory Table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS inventory_items (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        quantity TEXT NOT NULL, 
                        purchase_date TEXT NOT NULL,
                        expiry_date TEXT NOT NULL,
                        original_quantity_string TEXT 
                    )
                ''')
                # Historical (Consumed) Items Table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS historical_items (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        quantity_consumed_this_time REAL NOT NULL,
                        original_quantity_string TEXT,
                        purchase_date TEXT, 
                        expiry_date TEXT,
                        consumed_date TEXT NOT NULL
                    )
                ''')
                conn.commit()
        except sqlite3.Error as e:
            print(f"Database initialization error: {e}")
            # Depending on app design, might want to raise this or handle more gracefully

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

    def add_item_to_list(self, name, quantity_str, purchase_date_str, expiry_days):
        """Adds a new grocery item to the database."""
        try:
            purchase_dt = date.fromisoformat(purchase_date_str)
            expiry_dt = purchase_dt + timedelta(days=int(expiry_days))
        except (ValueError, TypeError) as e:
            print(f"Error processing date/expiry for adding item: {e}")
            return {"success": False, "message": f"Invalid date or expiry day format: {e}"}

        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO inventory_items 
                    (name, quantity, purchase_date, expiry_date, original_quantity_string) 
                    VALUES (?, ?, ?, ?, ?)
                ''', (name, str(quantity_str), purchase_dt.isoformat(), expiry_dt.isoformat(), str(quantity_str)))
                conn.commit()
            print(f"Added to DB: {name} (Expires: {expiry_dt.isoformat()})")
            return {"success": True, "message": f"Item '{name}' added successfully."}
        except sqlite3.Error as e:
            print(f"Database error adding item: {e}")
            return {"success": False, "message": f"Database error: {e}"}

    def get_current_inventory(self):
        """Retrieves all items from the current inventory, ordered by expiry date."""
        items = []
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT id, name, quantity, purchase_date, expiry_date, original_quantity_string 
                    FROM inventory_items 
                    ORDER BY expiry_date ASC
                ''')
                rows = cursor.fetchall()
                for row in rows:
                    item = dict(row) # Convert sqlite3.Row to dict
                    item['purchase_date'] = date.fromisoformat(item['purchase_date'])
                    item['expiry_date'] = date.fromisoformat(item['expiry_date'])
                    items.append(item)
        except sqlite3.Error as e:
            print(f"Database error fetching current inventory: {e}")
        return items

    def get_historical_inventory(self):
        """Retrieves all items from the historical inventory, ordered by consumed date."""
        items = []
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT id, name, quantity_consumed_this_time, original_quantity_string, 
                           purchase_date, expiry_date, consumed_date 
                    FROM historical_items 
                    ORDER BY consumed_date DESC
                ''')
                rows = cursor.fetchall()
                for row in rows:
                    item = dict(row)
                    if item['purchase_date']: item['purchase_date'] = date.fromisoformat(item['purchase_date'])
                    if item['expiry_date']: item['expiry_date'] = date.fromisoformat(item['expiry_date'])
                    item['consumed_date'] = date.fromisoformat(item['consumed_date'])
                    items.append(item)
        except sqlite3.Error as e:
            print(f"Database error fetching historical inventory: {e}")
        return items

    def get_total_item_quantity(self, item_name_to_find):
        """Calculates total quantity of a specific item in current inventory."""
        total_quantity = 0.0
        item_name_lower = item_name_to_find.lower()
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT quantity FROM inventory_items WHERE LOWER(name) = ?", (item_name_lower,))
                rows = cursor.fetchall()
                for row in rows:
                    total_quantity += self._parse_quantity_string(row['quantity'])
        except sqlite3.Error as e:
            print(f"Database error getting total item quantity for {item_name_to_find}: {e}")
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

        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                # Fetch all batches of the item, ordered by expiry_date to consume oldest first.
                cursor.execute('''
                    SELECT id, name, quantity, purchase_date, expiry_date, original_quantity_string 
                    FROM inventory_items 
                    WHERE LOWER(name) = ? 
                    ORDER BY expiry_date ASC
                ''', (item_name_to_consume.lower(),))
                items_in_stock = [dict(row) for row in cursor.fetchall()]

                if not items_in_stock:
                    return {"success": False, "message": f"Item '{item_name_to_consume}' not found."}

                for item_stock_dict in items_in_stock:
                    if quantity_remaining_to_consume <= 0:
                        break
                    
                    item_id = item_stock_dict['id']
                    current_original_qty_str = item_stock_dict['original_quantity_string'] # This is the original string when added
                    current_qty_str_in_db = item_stock_dict['quantity'] # This is current quantity string in DB
                    
                    # Use _parse_quantity_string for the current quantity in DB
                    numeric_qty_in_stock = self._parse_quantity_string(current_qty_str_in_db)

                    consumable_from_this_batch = min(quantity_remaining_to_consume, numeric_qty_in_stock)

                    if consumable_from_this_batch <= 0: # Should not happen if numeric_qty_in_stock > 0
                        continue

                    # Update inventory_items table
                    new_numeric_qty = numeric_qty_in_stock - consumable_from_this_batch
                    
                    # Determine new quantity string, attempting to preserve original unit label if present.
                    new_quantity_db_str = "0" # Default for fully consumed
                    if new_numeric_qty > 0:
                        original_parts = str(current_qty_str_in_db).split(maxsplit=1)
                        if len(original_parts) > 1: # If there was a unit part
                            # Check if the first part was indeed a number before, implies unit was second part
                            try:
                                float(original_parts[0]) # Check if original first part was number
                                unit_suffix = original_parts[1]
                                new_quantity_db_str = f"{new_numeric_qty:.2f} {unit_suffix}"
                            except ValueError: # Original first part was not a number (e.g. "a loaf")
                                # If original was "a loaf" and new_numeric_qty is 0.5, this might be tricky.
                                # For simplicity, if original was not like "X unit", just store the number.
                                new_quantity_db_str = str(new_numeric_qty) if new_numeric_qty % 1 else str(int(new_numeric_qty))
                        else: # Original quantity was just a number
                             new_quantity_db_str = str(new_numeric_qty) if new_numeric_qty % 1 else str(int(new_numeric_qty))
                    
                    # Update or delete the item batch in the inventory
                    if new_numeric_qty <= 0:
                        cursor.execute("DELETE FROM inventory_items WHERE id = ?", (item_id,))
                        log_messages.append(f"Fully consumed batch ID {item_id} of '{item_name_to_consume}'.")
                    else:
                        cursor.execute("UPDATE inventory_items SET quantity = ? WHERE id = ?", 
                                       (new_quantity_db_str, item_id))
                        log_messages.append(f"Partially consumed batch ID {item_id} of '{item_name_to_consume}'. New qty: {new_quantity_db_str}")
                    
                    # Log to historical_items
                    cursor.execute('''
                        INSERT INTO historical_items 
                        (name, quantity_consumed_this_time, original_quantity_string, 
                         purchase_date, expiry_date, consumed_date) 
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (item_stock_dict['name'], consumable_from_this_batch, current_original_qty_str,
                          item_stock_dict['purchase_date'], item_stock_dict['expiry_date'],
                          date.today().isoformat()))
                    
                    consumed_amount_total_overall += consumable_from_this_batch
                    quantity_remaining_to_consume -= consumable_from_this_batch
                
                conn.commit() # Commit all changes if loop completes

        except sqlite3.Error as e:
            # No explicit rollback needed with `with conn:` if an error occurs before commit.
            # If commit fails, changes are not persisted.
            print(f"Database error consuming item: {e}")
            return {"success": False, "message": f"Database error: {e}", "details": log_messages}

        final_message = f"Total consumed: {consumed_amount_total_overall:.2f} of {item_name_to_consume}."
        if quantity_remaining_to_consume > 0 and consumed_amount_total_overall > 0 :
            final_message += f" Could not consume the full requested amount. {quantity_remaining_to_consume:.2f} still pending."
        elif consumed_amount_total_overall == 0 and quantity_to_consume_float > 0:
             final_message = f"No quantity of '{item_name_to_consume}' could be consumed (possibly none in stock or issue with parsing quantity)."
        
        print(final_message) # For server logs
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

        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                # Sum quantity_consumed_this_time for the item within the lookback period.
                # Using LOWER(name) for case-insensitive matching.
                cursor.execute('''
                    SELECT SUM(quantity_consumed_this_time) as total_consumed
                    FROM historical_items 
                    WHERE LOWER(name) = ? AND consumed_date >= ? AND consumed_date <= ?
                ''', (item_name.lower(), lookback_start_dt.isoformat(), today.isoformat()))
                result_row = cursor.fetchone()
                if result_row and result_row['total_consumed'] is not None:
                    total_consumed_in_lookback = float(result_row['total_consumed'])
        except sqlite3.Error as e:
            print(f"Database error fetching historical data for demand projection: {e}")
            # Return a result indicating failure or partial data
            return {
                "item_name": item_name, "current_stock": self.get_total_item_quantity(item_name),
                "avg_daily_consumption": 0, "days_to_depletion": "Error fetching history",
                "projected_need": 0, "lookback_days": lookback_days, "projection_days": projection_days,
                "success": False, "message": f"DB error calculating historical consumption: {e}"
            }

        avg_daily_consumption = (total_consumed_in_lookback / lookback_days) if lookback_days > 0 else 0.0
        current_quantity_sum = self.get_total_item_quantity(item_name)
        
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
            "item_name": item_name, "current_stock": current_quantity_sum,
            "avg_daily_consumption": avg_daily_consumption, "days_to_depletion": days_to_depletion_str,
            "projected_need": projected_need, "lookback_days": lookback_days, "projection_days": projection_days,
            "success": True # Indicate successful projection calculation
        }
        # Print output for command-line use, Flask will use the return value
        print(f"\n--- Demand Projection for '{item_name}' (DB) ---")
        print(f"Lookback: {lookback_days} days, Projection: {projection_days} days")
        print(f"Total consumed (lookback): {total_consumed_in_lookback:.2f} units")
        print(f"Current stock: {current_quantity_sum:.2f} units")
        print(f"Avg daily consumption: {avg_daily_consumption:.2f} units/day")
        print(f"Est. days to depletion: {days_to_depletion_str}")
        print(f"Projected need (next {projection_days} days): {projected_need:.2f} units")
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
    
    manager.add_item_to_list(name="DB Apples", quantity_str="6 units", purchase_date_str=today_str, expiry_days=14)
    manager.add_item_to_list(name="DB Bananas", quantity_str="12", purchase_date_str=today_str, expiry_days=5)
    manager.add_item_to_list(name="DB Milk", quantity_str="1 gallon", purchase_date_str=today_str, expiry_days=7)
    
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
