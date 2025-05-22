# food_manager.py

# Let's define what a grocery item looks like
def create_grocery_item(name, quantity, purchase_date, expiry_days):
    """Creates a dictionary to represent a grocery item."""
    from datetime import date, timedelta
    item = {
        "name": name,
        "quantity": quantity,
        "purchase_date": date.fromisoformat(purchase_date), # Expects "YYYY-MM-DD"
        "expiry_date": date.fromisoformat(purchase_date) + timedelta(days=expiry_days)
    }
    return item

# This will be our list to store all grocery items
my_grocery_list = []

# --- Core Functions for your App ---

def add_item_to_list(name, quantity, purchase_date_str, expiry_days):
    """Adds a new grocery item to our list."""
    new_item = create_grocery_item(name, quantity, purchase_date_str, expiry_days)
    my_grocery_list.append(new_item)
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
    from datetime import date, timedelta
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
    # - Saving and loading data to a file (so it persists between runs)
    # - Creating a user interface (web or mobile)
    # - Adding recipe suggestions based on available ingredients
    # - More detailed garden tracking
    # - User accounts if multiple people use it
