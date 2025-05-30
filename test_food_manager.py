import unittest
import sqlite3
from datetime import date, timedelta
from Food_manager import InventoryManager

class TestInventoryManager(unittest.TestCase):

    def setUp(self):
        """Set up an in-memory SQLite database for each test."""
        self.manager = InventoryManager(db_filepath=":memory:")
        # Helper to add items directly for testing setup if needed
        self.today_str = date.today().isoformat()

    def test_add_and_get_item(self):
        """Test adding an item and retrieving it."""
        self.manager.add_item_to_list("Test Apple", "5 units", self.today_str, 7, category="Fruit")
        inventory = self.manager.get_current_inventory()
        self.assertEqual(len(inventory), 1)
        item = inventory[0]
        self.assertEqual(item['name'], "Test Apple")
        self.assertEqual(item['quantity'], "5 units") # Stored as string
        self.assertEqual(item['purchase_date'], date.today())
        self.assertEqual(item['expiry_date'], date.today() + timedelta(days=7))
        self.assertEqual(item['category'], "Fruit")

    def test_consume_item_partial(self):
        """Test consuming part of an item."""
        self.manager.add_item_to_list("Test Banana", "10 units", self.today_str, 5)
        result = self.manager.consume_item("Test Banana", 3.0)
        self.assertTrue(result['success'])

        inventory = self.manager.get_current_inventory()
        self.assertEqual(len(inventory), 1)
        item = inventory[0]
        self.assertEqual(item['name'], "Test Banana")
        # Assuming consume_item updates quantity to a string representation of the float
        self.assertEqual(item['quantity'], "7.0 units")

        historical_items = self.manager.get_historical_inventory()
        self.assertEqual(len(historical_items), 1)
        consumed_item_record = historical_items[0]
        self.assertEqual(consumed_item_record['name'], "Test Banana")
        self.assertEqual(consumed_item_record['quantity_consumed_this_time'], 3.0)


    def test_consume_item_full(self):
        """Test consuming an entire item."""
        self.manager.add_item_to_list("Test Orange", "2 units", self.today_str, 3)
        result = self.manager.consume_item("Test Orange", 2.0)
        self.assertTrue(result['success'])
        
        inventory = self.manager.get_current_inventory()
        self.assertEqual(len(inventory), 0) # Item should be gone

        historical_items = self.manager.get_historical_inventory()
        self.assertEqual(len(historical_items), 1)
        consumed_item_record = historical_items[0]
        self.assertEqual(consumed_item_record['name'], "Test Orange")
        self.assertEqual(consumed_item_record['quantity_consumed_this_time'], 2.0)


    def test_get_total_item_quantity(self):
        """Test getting total quantity of an item with multiple batches."""
        self.manager.add_item_to_list("Test Grapes", "100 g", self.today_str, 7)
        self.manager.add_item_to_list("Test Grapes", "150 g", self.today_str, 7) # Another batch
        
        total_quantity = self.manager.get_total_item_quantity("Test Grapes")
        # _parse_quantity_string extracts numeric part: 100.0 + 150.0
        self.assertEqual(total_quantity, 250.0)

    def test_check_for_expiring_items(self):
        """Test identifying expiring and expired items."""
        self.manager.add_item_to_list("Expiring Soon Milk", "1L", self.today_str, 2) # Expires in 2 days
        self.manager.add_item_to_list("Expired Bread", "1 loaf", (date.today() - timedelta(days=5)).isoformat(), 1) # Expired 4 days ago
        self.manager.add_item_to_list("Fresh Juice", "2L", self.today_str, 10) # Not expiring soon
        
        # Check for items expiring within 3 days
        expiring_items = self.manager.check_for_expiring_items(days_threshold=3)
        
        expiring_names = [item['name'] for item in expiring_items]
        self.assertIn("Expiring Soon Milk", expiring_names)
        self.assertIn("Expired Bread", expiring_names)
        self.assertNotIn("Fresh Juice", expiring_names)
        self.assertEqual(len(expiring_items), 2)

    def test_project_demand(self):
        """Test demand projection based on historical consumption and current stock."""
        # Setup: Add some stock
        self.manager.add_item_to_list("Test Projector Item", "20 units", self.today_str, 30)

        # Simulate historical consumption
        # To do this directly, we'd need a method to add to historical_items or consume items over time
        # For simplicity, let's assume consume_item correctly logs to historical_items.
        # Consume 5 units today, 5 units yesterday, 5 units the day before for "Test Projector Item"
        # This requires careful date manipulation if we want to simulate past consumption accurately.
        # Let's add some items and consume them to populate historical data.

        # Add and consume item to create history for "Test Projector Item"
        # This is a bit indirect. A dedicated method to seed historical data would be cleaner for tests.
        # Let's assume for this test the historical data is pre-populated or added via consume_item calls.

        # We need to add an item, then consume it multiple times to create history.
        # The current `consume_item` uses `date.today()`. For more robust historical testing,
        # we might need to adjust how `consumed_date` is set or allow it as a parameter.
        # For now, we'll rely on the current `consume_item` behavior.

        # Add item with enough quantity to be consumed over several "days" (simulated by calls)
        self.manager.add_item_to_list("Historical Item", "100 units", self.today_str, 60)

        # Simulate consumption for "Historical Item" to test projection
        # Day 1 consumption: 5 units
        self.manager.consume_item("Historical Item", 5.0)
        # Day 2 consumption: 5 units (simulated - in reality, date changes or we'd need to mock date)
        # To properly test historical consumption over different dates, we would need to:
        # 1. Allow `consume_item` to take a `consumed_date_override` parameter, OR
        # 2. Manually insert into `historical_items` table with past dates.
        # Option 2 is cleaner for testing specific historical scenarios.

        conn = self.manager._get_db_connection()
        cursor = conn.cursor()
        # Manually insert some historical data for "Test Projector Item"
        # These consumptions happened in the past
        past_date_1 = (date.today() - timedelta(days=1)).isoformat()
        past_date_5 = (date.today() - timedelta(days=5)).isoformat()
        past_date_10 = (date.today() - timedelta(days=10)).isoformat()

        cursor.execute("INSERT INTO historical_items (name, quantity_consumed_this_time, consumed_date) VALUES (?, ?, ?)",
                       ("Test Projector Item", 10.0, past_date_1))
        cursor.execute("INSERT INTO historical_items (name, quantity_consumed_this_time, consumed_date) VALUES (?, ?, ?)",
                       ("Test Projector Item", 10.0, past_date_5))
        cursor.execute("INSERT INTO historical_items (name, quantity_consumed_this_time, consumed_date) VALUES (?, ?, ?)",
                       ("Test Projector Item", 10.0, past_date_10))
        conn.commit()
        conn.close()

        # Current stock of "Test Projector Item" is 20 units.
        # Historical consumption over last 30 days: 30 units (10 * 3)
        # Avg daily consumption = 30 / 30 = 1 unit/day
        projection = self.manager.project_demand("Test Projector Item", lookback_days=30, projection_days=7)

        self.assertTrue(projection['success'])
        self.assertEqual(projection['item_name'], "Test Projector Item")
        self.assertEqual(projection['current_stock'], 20.0) # From add_item_to_list
        self.assertAlmostEqual(projection['avg_daily_consumption'], 1.0) # 30 units / 30 days
        self.assertEqual(projection['projected_need'], 7.0) # 1.0 units/day * 7 days

    def test_add_item_invalid_date_format(self):
        """Test adding item with invalid date format."""
        result = self.manager.add_item_to_list("Invalid Date Item", "1", "2023/01/01", 5) # Wrong format
        self.assertFalse(result['success'])
        self.assertIn("Invalid date", result['message'])

    def test_consume_item_not_found(self):
        """Test consuming an item that is not in inventory."""
        result = self.manager.consume_item("NonExistent Item", 1.0)
        self.assertFalse(result['success'])
        self.assertIn("not found", result['message'])

    def tearDown(self):
        """Clean up resources, if any (though in-memory DB is auto-cleaned)."""
        # For in-memory DB, connection closure might not be strictly necessary here
        # as it's per-test, but good practice if it were a file-based DB.
        pass

if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
