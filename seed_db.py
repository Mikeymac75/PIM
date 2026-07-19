import sqlite3
import datetime

db_path = r'\\homeassistant\addons\pim\food_app.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

def insert_category(name):
    cursor.execute("INSERT OR IGNORE INTO categories (name) VALUES (?)", (name,))
    cursor.execute("SELECT id FROM categories WHERE name = ?", (name,))
    return cursor.fetchone()[0]

def insert_product(name, unit, expiry, par, max_hold, cat_id):
    cursor.execute("""
        INSERT OR IGNORE INTO products (name, unit_of_measure, default_expiry_days, par_level, max_holding_amount, category_id)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (name, unit, expiry, par, max_hold, cat_id))
    cursor.execute("SELECT id FROM products WHERE name = ?", (name,))
    return cursor.fetchone()[0]

def insert_inventory(product_id, name, qty, purchase_date, expiry_date):
    cursor.execute("""
        INSERT INTO inventory_items (product_id, name, quantity, purchase_date, expiry_date, original_quantity_string)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (product_id, name, qty, purchase_date, expiry_date, str(qty)))

# Categories
cat_meat = insert_category("Meat & Poultry")
cat_produce = insert_category("Produce")
cat_spices = insert_category("Spices & Seasonings")
cat_kits = insert_category("Meal Kits")

# Products
p_ground_beef = insert_product("Ground Beef", "lbs", 5, 2.0, 5.0, cat_meat)
p_chicken_breast = insert_product("Chicken Breast", "lbs", 4, 3.0, 6.0, cat_meat)
p_chicken_thighs = insert_product("Boneless Thighs", "lbs", 4, 2.0, 4.0, cat_meat)
p_limes = insert_product("Limes", "each", 14, 5.0, 10.0, cat_produce)
p_taco_kit = insert_product("Taco Kit", "box", 180, 2.0, 5.0, cat_kits)
p_cayenne = insert_product("Cayenne Pepper", "oz", 365, 1.0, 2.0, cat_spices)
p_seasoning = insert_product("Seasoning Blends", "oz", 365, 2.0, 5.0, cat_spices)

# Fake Inventory
today = datetime.date.today()
today_str = today.strftime("%Y-%m-%d")

# Ground Beef
insert_inventory(p_ground_beef, "Ground Beef", "2.5", today_str, (today + datetime.timedelta(days=5)).strftime("%Y-%m-%d"))
# Chicken Breast
insert_inventory(p_chicken_breast, "Chicken Breast", "1.5", today_str, (today + datetime.timedelta(days=4)).strftime("%Y-%m-%d"))
# Boneless Thighs
insert_inventory(p_chicken_thighs, "Boneless Thighs", "2.0", today_str, (today + datetime.timedelta(days=4)).strftime("%Y-%m-%d"))
# Limes
insert_inventory(p_limes, "Limes", "6", today_str, (today + datetime.timedelta(days=14)).strftime("%Y-%m-%d"))
# Taco Kits
insert_inventory(p_taco_kit, "Taco Kit", "2", today_str, (today + datetime.timedelta(days=180)).strftime("%Y-%m-%d"))
# Cayenne
insert_inventory(p_cayenne, "Cayenne Pepper", "1", today_str, (today + datetime.timedelta(days=365)).strftime("%Y-%m-%d"))
# Seasoning
insert_inventory(p_seasoning, "Seasoning Blends", "3", today_str, (today + datetime.timedelta(days=365)).strftime("%Y-%m-%d"))

conn.commit()
conn.close()
print("Database seeded successfully with custom data!")
