# food_manager.py
import json
import csv # Added for CSV export
from datetime import date, timedelta

# Let's define what a grocery item looks like
def create_grocery_item(name, quantity, purchase_date, expiry_days):
    """Creates a dictionary to represent a grocery item."""
    # from datetime import date, timedelta # Moved to top
    purchase_dt_obj = date.fromisoformat(purchase_date) # Expects "YYYY-MM-DD"
    item = {
        "name": name,
        "quantity": quantity,
        "purchase_date": purchase_dt_obj,
        "expiry_date": purchase_dt_obj + timedelta(days=expiry_days)
    }
    return item

# This will be our list to store all grocery items - initialized by loading from file
# my_grocery_list = [] # Will be loaded

# --- File Persistence Functions ---
def save_inventory_to_file(filepath="inventory.json"):
    """Saves the current grocery list to a JSON file with dates as ISO strings."""
    global my_grocery_list
    list_to_save = []
    for item in my_grocery_list:
        list_to_save.append({
            "name": item["name"],
            "quantity": item["quantity"],
            "purchase_date": item["purchase_date"].isoformat(),
            "expiry_date": item["expiry_date"].isoformat()
        })
    try:
        with open(filepath, 'w') as f:
            json.dump(list_to_save, f, indent=4)
        # print(f"Inventory saved to {filepath}")
    except IOError as e:
        print(f"Error saving inventory to {filepath}: {e}")

def load_inventory_from_file(filepath="inventory.json"):
    """Loads the grocery list from a JSON file."""
    # from datetime import date # Moved to top
    try:
        with open(filepath, 'r') as f:
            loaded_list = json.load(f)
            # Convert date strings back to date objects
            for item in loaded_list:
                item['purchase_date'] = date.fromisoformat(item['purchase_date'])
                item['expiry_date'] = date.fromisoformat(item['expiry_date'])
            # print(f"Inventory loaded from {filepath}")
            return loaded_list
    except FileNotFoundError:
        # print(f"Inventory file {filepath} not found. Starting with an empty list.")
        return []
    except (IOError, json.JSONDecodeError) as e:
        print(f"Error loading inventory from {filepath}: {e}. Starting with an empty list.")
        return []

# Initialize the grocery list by loading from file
my_grocery_list = load_inventory_from_file()

# Initialize historical inventory
historical_inventory = [] # Will be loaded

# --- Historical Inventory Persistence Functions ---
def save_historical_inventory_to_file(filepath="historical_inventory.json"):
    """Saves the historical inventory list to a JSON file with dates as ISO strings."""
    global historical_inventory
    list_to_save = []
    for item in historical_inventory:
        item_copy = item.copy() # Avoid modifying the original item in memory
        item_copy['purchase_date'] = item['purchase_date'].isoformat()
        item_copy['expiry_date'] = item['expiry_date'].isoformat()
        if 'consumed_date' in item_copy and isinstance(item_copy['consumed_date'], date):
            item_copy['consumed_date'] = item_copy['consumed_date'].isoformat()
        list_to_save.append(item_copy)
    try:
        with open(filepath, 'w') as f:
            json.dump(list_to_save, f, indent=4)
        # print(f"Historical inventory saved to {filepath}")
    except IOError as e:
        print(f"Error saving historical inventory to {filepath}: {e}")

def load_historical_inventory_from_file(filepath="historical_inventory.json"):
    """Loads the historical inventory list from a JSON file."""
    try:
        with open(filepath, 'r') as f:
            loaded_list = json.load(f)
            for item in loaded_list:
                item['purchase_date'] = date.fromisoformat(item['purchase_date'])
                item['expiry_date'] = date.fromisoformat(item['expiry_date'])
                if 'consumed_date' in item:
                    item['consumed_date'] = date.fromisoformat(item['consumed_date'])
            # print(f"Historical inventory loaded from {filepath}")
            return loaded_list
    except FileNotFoundError:
        # print(f"Historical inventory file {filepath} not found. Starting with an empty list.")
        return []
    except (IOError, json.JSONDecodeError) as e:
        print(f"Error loading historical inventory from {filepath}: {e}. Starting with an empty list.")
        return []

historical_inventory = load_historical_inventory_from_file()


# --- Core Functions for your App ---

def add_item_to_list(name, quantity, purchase_date_str, expiry_days):
    """Adds a new grocery item to our list and saves the list."""
    # create_grocery_item now returns items with date objects
    new_item = create_grocery_item(name, quantity, purchase_date_str, expiry_days)
    my_grocery_list.append(new_item)
    save_inventory_to_file() # Save after adding
    print(f"Added: {new_item['name']} (Expires: {new_item['expiry_date'].isoformat()})")


def display_all_items():
    """Prints all items in the grocery list."""
    if not my_grocery_list:
        print("Your grocery list is empty!")
        return
    print("\n--- Your Grocery List ---")
    for item in my_grocery_list:
        print(f"- {item['name']} ({item['quantity']}), Purchased: {item['purchase_date'].isoformat()}, Expires: {item['expiry_date'].isoformat()}")
    print("-------------------------\n")

def check_for_expiring_items(days_threshold=3):
    """Checks for items expiring within a certain number of days."""
    # from datetime import date, timedelta # Moved to top
    today = date.today()
    upcoming_expiry_items = []

    print(f"\n--- Items Expiring Soon (within {days_threshold} days) ---")
    found_expiring = False
    for item in my_grocery_list:
        days_to_expiry = (item['expiry_date'] - today).days
        if 0 <= days_to_expiry <= days_threshold:
            print(f"- {item['name']} expires in {days_to_expiry} day(s) on {item['expiry_date'].isoformat()}")
            upcoming_expiry_items.append(item)
            found_expiring = True
        elif days_to_expiry < 0:
            print(f"- {item['name']} EXPIRED on {item['expiry_date'].isoformat()}!")
            upcoming_expiry_items.append(item) # You might want to handle expired items differently
            found_expiring = True
            
    if not found_expiring:
        print("No items expiring soon or already expired.")
    print("---------------------------------------\n")
    return upcoming_expiry_items

# --- Placeholder for Garden Integration ---
my_garden_produce = []

def add_garden_produce(name, harvest_date_str, typical_shelf_life_days):
    """Adds produce harvested from the garden."""
    # Similar to grocery items, but source is 'garden'
    # This is a simplified example
    from datetime import date, timedelta
    produce = {
        "name": name,
        "harvest_date": date.fromisoformat(harvest_date_str),
        "estimated_expiry": date.fromisoformat(harvest_date_str) + timedelta(days=typical_shelf_life_days),
        "source": "garden"
    }
    my_garden_produce.append(produce)
    print(f"Logged garden produce: {produce['name']}")

# --- Example Usage (How you might interact with these functions) ---
if __name__ == "__main__":
    print("Welcome to your Simple Food Manager!")

    # Adding some grocery items
    add_item_to_list(name="Milk", quantity="1 gallon", purchase_date_str="2025-05-20", expiry_days=7)
    add_item_to_list(name="Eggs", quantity="1 dozen", purchase_date_str="2025-05-22", expiry_days=21)
    add_item_to_list(name="Bread", quantity="1 loaf", purchase_date_str="2025-05-23", expiry_days=5) # This will expire soon
    add_item_to_list(name="Chicken Breast", quantity="2 lbs", purchase_date_str="2025-05-18", expiry_days=3) # This might be expired or close

    # Adding some garden produce
    add_garden_produce(name="Tomatoes", harvest_date_str="2025-05-21", typical_shelf_life_days=7)

    # Displaying the items
    display_all_items()

    # Checking for expiring items
    check_for_expiring_items(days_threshold=3)

    # --- What's next? ---
    # - Creating a user interface (web or mobile)
    # - Adding recipe suggestions based on available ingredients
    # - More detailed garden tracking
    # - User accounts if multiple people use it

# --- Display Historical Inventory Function ---
def display_historical_inventory():
    """Prints all items in the historical inventory list."""
    global historical_inventory
    if not historical_inventory:
        print("Historical inventory is empty.")
        return
    
    print("\n--- Historical Inventory ---")
    for item in historical_inventory:
        consumed_qty_display = item.get('quantity_consumed_this_time', item.get('quantity', 'N/A'))
        # Ensure the quantity displayed is reasonably formatted if it's numeric
        if isinstance(consumed_qty_display, float):
            consumed_qty_display = f"{consumed_qty_display:.2f}"
        
        # Format other details for clarity
        purchase_date_str = item['purchase_date'].isoformat() if isinstance(item['purchase_date'], date) else str(item['purchase_date'])
        expiry_date_str = item['expiry_date'].isoformat() if isinstance(item['expiry_date'], date) else str(item['expiry_date'])
        consumed_date_str = item['consumed_date'].isoformat() if isinstance(item['consumed_date'], date) else str(item['consumed_date'])
        original_qty_str = item.get('original_quantity_string', '')
        if original_qty_str: # If it was like "1 loaf"
             details = f"(Original: {original_qty_str}, Consumed Qty: {consumed_qty_display})"
        else: # If it was a numeric quantity
             details = f"(Consumed Qty: {consumed_qty_display})"

        print(f"- {item['name']} {details}, Purchased: {purchase_date_str}, Expired: {expiry_date_str}, Consumed: {consumed_date_str}")
    print("--------------------------\n")

# --- CSV Export Function ---
def export_data_to_csv(filename_prefix="inventory_export"):
    """Exports current inventory, historical inventory, and demand projections to CSV files."""
    global my_grocery_list
    global historical_inventory

    # Helper function to write list of dicts to CSV
    def write_to_csv(filename, data, fieldnames):
        try:
            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                for row_dict in data:
                    # Create a shallow copy to modify for export (e.g., date formatting)
                    row_to_write = row_dict.copy()
                    # Convert date objects to ISO strings for CSV
                    for key, value in row_to_write.items():
                        if isinstance(value, date):
                            row_to_write[key] = value.isoformat()
                    writer.writerow(row_to_write)
            print(f"Data successfully exported to '{filename}'.")
        except IOError as e:
            print(f"Error exporting data to '{filename}': {e}")
        except Exception as e: # Catch any other unexpected errors during writing
            print(f"An unexpected error occurred while writing to '{filename}': {e}")

    # 1. Export current inventory (my_grocery_list)
    if my_grocery_list:
        current_inventory_filename = f"{filename_prefix}_current.csv"
        # Define fieldnames based on typical keys, ensuring all are present
        current_fieldnames = ["name", "quantity", "purchase_date", "expiry_date"]
        # Check if all items have these keys, or gather all unique keys
        # For simplicity, using a fixed set. A more dynamic way would be to inspect all items.
        write_to_csv(current_inventory_filename, my_grocery_list, current_fieldnames)
    else:
        print("Current inventory is empty. Skipping export for current inventory.")

    # 2. Export historical inventory
    if historical_inventory:
        historical_inventory_filename = f"{filename_prefix}_historical.csv"
        # Define fieldnames, including all potential keys from historical items
        historical_fieldnames = [
            "name", "quantity", "purchase_date", "expiry_date", 
            "consumed_date", "quantity_consumed_this_time", "original_quantity_string"
        ]
        # Note: 'quantity' in historical might represent remaining qty if not fully consumed,
        # or original qty. 'quantity_consumed_this_time' is more specific for consumption.
        # 'original_quantity_string' might be optional.
        # A more robust way to get fieldnames is to inspect all dicts for all keys:
        # all_keys = set()
        # for item in historical_inventory:
        # all_keys.update(item.keys())
        # historical_fieldnames = sorted(list(all_keys))
        write_to_csv(historical_inventory_filename, historical_inventory, historical_fieldnames)
    else:
        print("Historical inventory is empty. Skipping export for historical inventory.")
        
    # 3. Export Demand Projections
    projections_data = []
    unique_item_names = set()
    for item in my_grocery_list:
        unique_item_names.add(item['name'])
    for item in historical_inventory:
        unique_item_names.add(item['name'])

    if unique_item_names:
        for item_name in sorted(list(unique_item_names)):
            # Suppress print output from project_demand during CSV export
            # by temporarily redirecting stdout if necessary, or by modifying project_demand
            # For now, we'll allow project_demand to print, then we print export status.
            projection = project_demand(item_name) # Uses default lookback/projection days
            if projection: # project_demand returns a dict
                projections_data.append(projection)
        
        if projections_data:
            projections_filename = f"{filename_prefix}_projections.csv"
            # Fieldnames from the keys of the first projection dictionary
            projection_fieldnames = list(projections_data[0].keys())
            write_to_csv(projections_filename, projections_data, projection_fieldnames)
        else:
            print("No projection data generated. Skipping export for demand projections.")
    else:
        print("No items found in current or historical inventory to generate projections. Skipping export.")


# --- Demand Projection Function ---
def project_demand(item_name, lookback_days=30, projection_days=7):
    """
    Analyzes historical consumption and current stock to project future demand for an item.
    """
    global my_grocery_list
    global historical_inventory
    # Ensure date and timedelta are available (already imported at top level)

    today = date.today()
    lookback_start_date = today - timedelta(days=lookback_days)

    # 1. Analyze Historical Consumption
    total_consumed_in_lookback = 0.0
    relevant_historical_items = [
        item for item in historical_inventory
        if item['name'].lower() == item_name.lower() and
           item.get('consumed_date') and # Ensure consumed_date exists
           item['consumed_date'] >= lookback_start_date and
           item['consumed_date'] <= today # Ensure it's not in the future, just in case
    ]

    for item in relevant_historical_items:
        # Use 'quantity_consumed_this_time' as this represents the actual amount consumed.
        # Fallback to 'quantity' if 'quantity_consumed_this_time' is not present for some reason,
        # though it should be from the consume_item logic.
        consumed_qty = item.get('quantity_consumed_this_time', item.get('quantity', 0))
        
        # Ensure consumed_qty is numeric
        if isinstance(consumed_qty, (int, float)):
            total_consumed_in_lookback += float(consumed_qty)
        elif isinstance(consumed_qty, str): # Try to parse if string
            try:
                total_consumed_in_lookback += float(consumed_qty.split()[0])
            except (ValueError, IndexError):
                # If string is not parsable as a number (e.g. "a loaf" became 0 in consume_item)
                # or if quantity_consumed_this_time was set to 1.0 for such items.
                # The 'quantity_consumed_this_time' field should ideally be numeric.
                # If it was '1 loaf' and recorded as 1.0, that's fine.
                # If it was something else non-numeric, it might add 0 here.
                # This depends on how 'quantity_consumed_this_time' was set for non-parsed quantities.
                # The current consume_item sets it to 1.0 for "a loaf", which is good.
                pass # Or print a warning: print(f"Warning: Could not parse historical quantity for {item_name}")


    avg_daily_consumption = 0
    if lookback_days > 0: # Avoid division by zero if lookback_days is 0
        avg_daily_consumption = total_consumed_in_lookback / lookback_days
    else: # if lookback_days is 0, no basis for avg consumption
        avg_daily_consumption = 0


    # 2. Check Current Stock
    current_quantity_sum = 0.0
    for item in my_grocery_list:
        if item['name'].lower() == item_name.lower():
            qty = item['quantity']
            if isinstance(qty, (int, float)):
                current_quantity_sum += float(qty)
            elif isinstance(qty, str):
                try:
                    current_quantity_sum += float(qty.split()[0])
                except (ValueError, IndexError):
                    # For strings like "1 loaf" or "a piece", assume 1 unit.
                    # This matches the behavior in consume_item for unparseable initial quantities.
                    current_quantity_sum += 1.0


    # 3. Estimate Depletion and Future Need
    days_to_depletion_str = "N/A"
    if avg_daily_consumption > 0:
        if current_quantity_sum > 0 :
            days_to_depletion = current_quantity_sum / avg_daily_consumption
            days_to_depletion_str = f"{days_to_depletion:.1f} days"
        else:
            days_to_depletion_str = "0 days (already out of stock)"
            
    elif current_quantity_sum > 0:
        days_to_depletion_str = "Stock will not deplete based on recent consumption."
    else: # No stock and no consumption
        days_to_depletion_str = "N/A (out of stock, no consumption history)"


    projected_need = avg_daily_consumption * projection_days

    # 4. Output
    print(f"\n--- Demand Projection for '{item_name}' ---")
    print(f"Lookback period: {lookback_days} days")
    print(f"Projection period: {projection_days} days")
    print(f"\nTotal '{item_name}' consumed in last {lookback_days} days: {total_consumed_in_lookback:.2f} units")
    print(f"Current stock: {current_quantity_sum:.2f} units")
    print(f"Average daily consumption (last {lookback_days} days): {avg_daily_consumption:.2f} units/day")
    print(f"\nEstimated days until current stock depletes: {days_to_depletion_str}")
    print(f"Projected need for the next {projection_days} days: {projected_need:.2f} units")
    print("-----------------------------------------\n")

    return {
        "item_name": item_name,
        "current_stock": current_quantity_sum,
        "avg_daily_consumption": avg_daily_consumption,
        "days_to_depletion": days_to_depletion_str, # Return the string for consistency in reporting
        "projected_need": projected_need,
        "lookback_days": lookback_days,
        "projection_days": projection_days
    }

# --- Consumption Function ---
def consume_item(item_name_to_consume, quantity_to_consume):
    """Consumes a specified quantity of an item from the grocery list.
    Consumes from items expiring soonest first.
    Moves fully consumed items to historical inventory."""
    global my_grocery_list
    global historical_inventory

    # Ensure quantity_to_consume is a number
    if not isinstance(quantity_to_consume, (int, float)):
        print("Error: Quantity to consume must be a number.")
        return
    if quantity_to_consume <= 0:
        print("Error: Quantity to consume must be positive.")
        return

    # Find all instances of the item, sorted by expiry date (soonest first)
    matching_items_indices = [
        i for i, item in enumerate(my_grocery_list)
        if item['name'].lower() == item_name_to_consume.lower()
    ]

    if not matching_items_indices:
        print(f"Item '{item_name_to_consume}' not found in current inventory.")
        return

    # Sort these items by expiry date (soonest first)
    # We get the actual items with their original indices to modify/remove them later
    # Sorting based on the actual item's expiry_date
    sorted_matching_items_with_indices = sorted(
        [(i, my_grocery_list[i]) for i in matching_items_indices],
        key=lambda x: x[1]['expiry_date']
    )

    consumed_amount_total = 0
    quantity_remaining_to_consume = quantity_to_consume

    items_to_remove_indices = [] # Store original indices of items fully consumed

    for original_idx, item_instance in sorted_matching_items_with_indices:
        if quantity_remaining_to_consume <= 0:
            break # Consumed enough

        item_quantity_val = 0
        can_parse_quantity = False

        # Try to parse quantity
        if isinstance(item_instance['quantity'], (int, float)):
            item_quantity_val = item_instance['quantity']
            can_parse_quantity = True
        elif isinstance(item_instance['quantity'], str):
            try:
                # Attempt to parse leading number, e.g., "2 lbs" -> 2
                item_quantity_val = float(item_instance['quantity'].split()[0])
                can_parse_quantity = True
            except ValueError:
                # If parsing fails, treat as a single unit if it's a non-numeric string like "a loaf"
                item_quantity_val = 1 # Assume 1 unit if not parsable
                # We can only consume this whole unit
                if quantity_remaining_to_consume >= 1:
                     pass # We can consume this unit
                else: # Cannot consume part of an unparsable unit
                    print(f"Cannot partially consume '{item_instance['name']}' with quantity '{item_instance['quantity']}'. Skipping this batch.")
                    continue


        if not can_parse_quantity and quantity_remaining_to_consume < 1: # Cannot consume part of this unparsable unit
             print(f"Cannot partially consume '{item_instance['name']}' with quantity '{item_instance['quantity']}' when less than 1 unit is requested. Skipping this batch.")
             continue

        consumable_from_this_item = min(quantity_remaining_to_consume, item_quantity_val)

        if can_parse_quantity:
            item_instance['quantity'] -= consumable_from_this_item
        else: # Unparsable string quantity, we consume the whole unit
             if quantity_remaining_to_consume >=1:
                 item_instance['quantity'] = 0 # Consumed the unit
             else: # Should not happen due to earlier check, but as safeguard
                 continue


        consumed_amount_total += consumable_from_this_item
        quantity_remaining_to_consume -= consumable_from_this_item
        
        print(f"Consumed {consumable_from_this_item} of '{item_instance['name']}' (exp: {item_instance['expiry_date'].isoformat()}). Remaining in this batch: {item_instance['quantity']}")

        if item_instance['quantity'] <= 0:
            consumed_item_copy = item_instance.copy()
            consumed_item_copy['consumed_date'] = date.today() # Store as date object
            consumed_item_copy['quantity_consumed_this_time'] = consumable_from_this_item # Could be useful
            if not can_parse_quantity: # If it was "a loaf", record it as 1 consumed
                 consumed_item_copy['original_quantity_string'] = item_instance['quantity'] # Preserve original string
                 consumed_item_copy['quantity_consumed_this_time'] = 1.0 # We consumed 1 unit

            historical_inventory.append(consumed_item_copy)
            items_to_remove_indices.append(original_idx)
            print(f"Fully consumed '{item_instance['name']}' (exp: {item_instance['expiry_date'].isoformat()}). Moved to historical inventory.")

    # Remove fully consumed items from my_grocery_list (in reverse order of index to avoid shifting issues)
    for idx in sorted(items_to_remove_indices, reverse=True):
        my_grocery_list.pop(idx)

    if consumed_amount_total > 0:
        save_inventory_to_file()
        save_historical_inventory_to_file()
    
    if quantity_remaining_to_consume > 0 and consumed_amount_total > 0 :
        print(f"Could not consume the full requested amount. {quantity_remaining_to_consume} of '{item_name_to_consume}' still pending (possibly due to insufficient stock or unparsable quantities).")
    elif consumed_amount_total == 0 and quantity_to_consume >0 :
         # This case can happen if all matching items had unparsable quantities and quantity_to_consume was < 1 for each
        print(f"No quantity of '{item_name_to_consume}' could be consumed with the requested amount of {quantity_to_consume}.")


if __name__ == "__main__":
    # The script loads data from inventory.json and historical_inventory.json upon starting.
    # For a fresh demonstration, delete these JSON files before running.
    print("Welcome to your Simple Food Manager!")
    print("Note: Data is loaded from inventory.json and historical_inventory.json if they exist.")
    print("For a completely fresh run, please delete these files beforehand.")

    # --- Section 1: Initial State ---
    print("\n\n--- Section 1: Initial Inventory State ---")
    display_all_items()
    display_historical_inventory() # Using the new display function

    # --- Section 2: Adding Items ---
    print("\n\n--- Section 2: Adding New Grocery Items ---")
    # Get today's date for dynamic purchase dates
    today_str = date.today().isoformat()
    day_plus_2 = (date.today() + timedelta(days=2)).isoformat()
    day_plus_5 = (date.today() + timedelta(days=5)).isoformat()
    day_plus_10 = (date.today() + timedelta(days=10)).isoformat()

    add_item_to_list(name="Apples", quantity=6, purchase_date_str=today_str, expiry_days=14)
    add_item_to_list(name="Bananas", quantity=12, purchase_date_str=today_str, expiry_days=5) # Will expire relatively soon
    add_item_to_list(name="Yogurt", quantity="6 pack", purchase_date_str=day_plus_2, expiry_days=10)
    add_item_to_list(name="Cheese", quantity="200g", purchase_date_str=today_str, expiry_days=30)
    # Adding an item that might already exist if script run multiple times (or from previous state)
    add_item_to_list(name="Milk", quantity=1, purchase_date_str=day_plus_5, expiry_days=7) # e.g. "1 gallon"
    
    # Adding garden produce
    print("\n--- Adding Garden Produce ---")
    add_garden_produce(name="Homegrown Tomatoes", harvest_date_str=today_str, typical_shelf_life_days=7)
    add_garden_produce(name="Homegrown Lettuce", harvest_date_str=day_plus_2, typical_shelf_life_days=5)

    # Display current inventory after additions
    display_all_items()

    # --- Section 3: Checking for Expiring Items ---
    print("\n\n--- Section 3: Checking for Expiring Items ---")
    check_for_expiring_items(days_threshold=6) # Check for items expiring in the next 6 days

    # --- Section 4: Consuming Items ---
    print("\n\n--- Section 4: Consuming Items ---")
    # 1. Partial consumption
    print("\n--- Attempting partial consumption of 'Apples' (consume 2 of 6) ---")
    consume_item("Apples", 2)
    display_all_items()

    # 2. Full consumption of one batch
    print("\n--- Attempting full consumption of 'Bananas' (consume 12) ---")
    consume_item("Bananas", 12) # Assuming 12 were added
    display_all_items()
    display_historical_inventory()

    # 3. Consume an item with string quantity like "1 loaf"
    print("\n--- Adding and consuming 'Artisan Bread' (quantity '1 loaf') ---")
    add_item_to_list(name="Artisan Bread", quantity="1 loaf", purchase_date_str=today_str, expiry_days=3)
    display_all_items()
    consume_item("Artisan Bread", 1) # Consume the whole loaf
    display_all_items()
    display_historical_inventory()

    # 4. Attempt to consume an item that doesn't exist
    print("\n--- Attempting to consume a non-existent item ('Kiwis') ---")
    consume_item("Kiwis", 5)

    # 5. Attempt to consume more than available (e.g. Cheese)
    print("\n--- Attempting to consume more 'Cheese' than available (e.g., consume 500g when 200g exists) ---")
    consume_item("Cheese", 500) # Assuming '200g' was added, this will partially consume.
                                 # If '200g' is parsed as 200, and we consume 500, it will consume all and report.
    display_all_items()
    display_historical_inventory()
    
    # 6. Consume the remaining cheese to move it to historical
    print("\n--- Consuming remaining 'Cheese' ---")
    # Need to check current quantity of cheese to consume it all
    # For demo, let's assume it was "200g" and we consumed 500, so it's gone.
    # If it was parsed as 1 unit, let's consume that.
    # This part is tricky without querying current state directly in main.
    # Let's try consuming a specific amount that *should* clear any remaining "Cheese" based on above.
    # The consume_item function handles parsing "200g" as 200.
    # So if 200g was added, and 500 was attempted, it should be gone.
    # Let's add more cheese and consume it fully.
    add_item_to_list(name="Cheddar Cheese", quantity="300g", purchase_date_str=today_str, expiry_days=20)
    consume_item("Cheddar Cheese", 300)
    display_all_items()
    display_historical_inventory()


    # --- Section 5: Demand Projection ---
    print("\n\n--- Section 5: Demand Projection ---")
    # Item with potential history (Apples, Bananas, Cheese, Milk)
    print("\n--- Projecting demand for 'Apples' (lookback 30 days, project 7 days) ---")
    project_demand("Apples", lookback_days=30, projection_days=7)
    
    print("\n--- Projecting demand for 'Milk' (lookback 60 days, project 14 days) ---")
    project_demand("Milk", lookback_days=60, projection_days=14)

    # Item with no history (unless run multiple times with same data and it was consumed)
    print("\n--- Projecting demand for 'Olive Oil' (lookback 30 days, project 7 days) ---")
    project_demand("Olive Oil", lookback_days=30, projection_days=7) # Likely no history

    # --- Section 6: Exporting Data ---
    print("\n\n--- Section 6: Exporting All Data to CSV ---")
    export_data_to_csv(filename_prefix="food_manager_demo_export")
    print(f"Data export process finished. Check for files starting with 'food_manager_demo_export_'.")

    print("\n\n--- Food Manager Demonstration Complete ---")
    # --- What's next? ---
    # - Creating a user interface (web or mobile)
    # - Adding recipe suggestions based on available ingredients
    # - More detailed garden tracking
    # - User accounts if multiple people use it
