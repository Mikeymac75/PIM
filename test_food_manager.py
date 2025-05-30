import unittest
import sqlite3
from datetime import date, timedelta
from Food_manager import InventoryManager

class TestInventoryManager(unittest.TestCase):

    def setUp(self):
        """Set up an in-memory SQLite database for each test."""
        self.manager = InventoryManager(db_filepath=":memory:")
        self.today = date.today()
        self.today_str = self.today.isoformat()

    def _add_inventory_item(self, name, quantity_str, purchase_date_str, expiry_days,
                            category=None, subcategory=None, par_level=0, max_holding_amount=0,
                            purchase_location=None):
        """Helper to add items to inventory for tests."""
        return self.manager.add_item_to_list(
            name, quantity_str, purchase_date_str, expiry_days,
            category, subcategory, par_level, max_holding_amount, purchase_location
        )

    def _add_historical_consumption(self, name, quantity_consumed, days_ago):
        """Helper to add historical consumption data for an item."""
        consumed_date = (self.today - timedelta(days=days_ago)).isoformat()
        conn = self.manager._get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO historical_items
            (name, quantity_consumed_this_time, original_quantity_string, purchase_date, expiry_date, consumed_date)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (name, quantity_consumed, "N/A", None, None, consumed_date))
        conn.commit()
        conn.close()

    def test_add_and_get_item(self):
        """Test adding an item and retrieving it, including purchase_location."""
        self._add_inventory_item("Test Apple", "5 units", self.today_str, 7, category="Fruit", purchase_location="Sobeys")
        inventory = self.manager.get_current_inventory()
        self.assertEqual(len(inventory), 1)
        item = inventory[0]
        self.assertEqual(item['name'], "Test Apple")
        self.assertEqual(item['quantity'], "5 units") # Stored as string
        self.assertEqual(item['purchase_date'], self.today)
        self.assertEqual(item['expiry_date'], self.today + timedelta(days=7))
        self.assertEqual(item['category'], "Fruit")
        self.assertEqual(item['purchase_location'], "Sobeys")

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
        # Option 2 is cleaner for testing specific historical scenarios. (Implemented with helper _add_historical_consumption)

        # Manually insert some historical data for "Test Projector Item"
        self._add_historical_consumption("Test Projector Item", 10.0, days_ago=1)
        self._add_historical_consumption("Test Projector Item", 10.0, days_ago=5)
        self._add_historical_consumption("Test Projector Item", 10.0, days_ago=10)

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

    # --- Tests for get_shopping_list_items ---

    def test_get_shopping_list_empty_inventory(self):
        self.assertEqual(self.manager.get_shopping_list_items(), [])

    def test_get_shopping_list_no_qualifying_items(self):
        # Item with high stock compared to par and zero consumption
        self._add_inventory_item("Apples", "20 units", self.today_str, 14, par_level=5, purchase_location="Sobeys")
        # Item with par level 0
        self._add_inventory_item("Oranges", "5 units", self.today_str, 10, par_level=0, purchase_location="Sobeys")
        self._add_historical_consumption("Oranges", 1, 1) # Some consumption

        self.assertEqual(self.manager.get_shopping_list_items(), [])

    def test_get_shopping_list_sobeys_item_needed(self):
        item_name = "Milk"
        self._add_inventory_item(item_name, "1 L", self.today_str, 7, par_level=2, purchase_location="Sobeys")
        # Consumed 0.5L daily for past 10 days = 5L total / 30 days lookback = avg 0.166 L/day
        # More direct: consumed 7L in last 7 days = 1L/day
        for i in range(1, 8): # 7 days of consumption
            self._add_historical_consumption(item_name, 1, i)

        # Current stock: 1L. Par: 2L. Avg daily consumption: 1L/day.
        # Sobeys shop is in 7 days.
        # Projected consumption in 7 days: 1 * 7 = 7L.
        # Stock at next Sobeys shop: 1 - 7 = -6L.
        # Target stock after Sobeys shop = Par (2) + Consumption for next cycle (7) = 9L.
        # Recommended purchase = Target (9) - Current (1) = 8L.

        shopping_list = self.manager.get_shopping_list_items()
        self.assertEqual(len(shopping_list), 1)
        item = shopping_list[0]
        self.assertEqual(item['name'], item_name)
        self.assertEqual(item['purchase_location'], "Sobeys")
        self.assertAlmostEqual(item['recommended_purchase_amount'], 8.0)
        self.assertEqual(item['par_level'], 2)
        self.assertEqual(item['days_to_next_shop'], 7) # Sobeys frequency

    def test_get_shopping_list_costco_item_needed(self):
        item_name = "Paper Towels"
        self._add_inventory_item(item_name, "2 rolls", self.today_str, 100, par_level=6, purchase_location="Costco")
        # Consumed 1 roll every 7 days for the past 28 days = 4 rolls total / 30 day lookback = avg 0.133 rolls/day
        # Let's simplify: 3 rolls consumed over 30 days. Avg daily = 0.1
        self._add_historical_consumption(item_name, 1, 5)
        self._add_historical_consumption(item_name, 1, 15)
        self._add_historical_consumption(item_name, 1, 25)

        # Current stock: 2 rolls. Par: 6 rolls. Avg daily consumption: 0.1 rolls/day.
        # Costco shop is in 21 days.
        # Projected consumption in 21 days: 0.1 * 21 = 2.1 rolls.
        # Stock at next Costco shop: 2 - 2.1 = -0.1 rolls.
        # Target stock after Costco shop = Par (6) + Consumption for next cycle (2.1) = 8.1 rolls.
        # Recommended purchase = Target (8.1) - Current (2) = 6.1 rolls.

        shopping_list = self.manager.get_shopping_list_items()
        self.assertEqual(len(shopping_list), 1)
        item = shopping_list[0]
        self.assertEqual(item['name'], item_name)
        self.assertEqual(item['purchase_location'], "Costco")
        self.assertAlmostEqual(item['recommended_purchase_amount'], 6.1)
        self.assertEqual(item['par_level'], 6)
        self.assertEqual(item['days_to_next_shop'], 21) # Costco frequency

    def test_get_shopping_list_mixed_items_no_filter(self):
        # Sobeys item
        self._add_inventory_item("Sobeys Item", "1 unit", self.today_str, 7, par_level=2, purchase_location="Sobeys")
        self._add_historical_consumption("Sobeys Item", 1, 1) # Avg daily 1/30, need more to trigger
        self._add_historical_consumption("Sobeys Item", 7, 3) # Avg daily (1+7)/30 = 0.26. Need 7*0.26 = 1.82 for next cycle. Par 2. Rec should be >0

        # Costco item
        self._add_inventory_item("Costco Item", "1 unit", self.today_str, 21, par_level=2, purchase_location="Costco")
        self._add_historical_consumption("Costco Item", 21, 5) # Avg daily 21/30 = 0.7. Need 21*0.7 = 14.7 for next cycle. Par 2. Rec should be >0

        shopping_list = self.manager.get_shopping_list_items()
        self.assertEqual(len(shopping_list), 2)
        self.assertTrue(any(it['name'] == "Sobeys Item" for it in shopping_list))
        self.assertTrue(any(it['name'] == "Costco Item" for it in shopping_list))

    def test_get_shopping_list_filter_by_sobeys(self):
        self._add_inventory_item("Sobeys Apples", "1 unit", self.today_str, 7, par_level=2, purchase_location="Sobeys")
        self._add_historical_consumption("Sobeys Apples", 7, 1) # Qualifies
        self._add_inventory_item("Costco Oranges", "1 unit", self.today_str, 21, par_level=2, purchase_location="Costco")
        self._add_historical_consumption("Costco Oranges", 21, 1) # Qualifies

        shopping_list = self.manager.get_shopping_list_items(store_filter="Sobeys")
        self.assertEqual(len(shopping_list), 1)
        self.assertEqual(shopping_list[0]['name'], "Sobeys Apples")

    def test_get_shopping_list_filter_by_costco(self):
        self._add_inventory_item("Sobeys Apples", "1 unit", self.today_str, 7, par_level=2, purchase_location="Sobeys")
        self._add_historical_consumption("Sobeys Apples", 7, 1)
        self._add_inventory_item("Costco Oranges", "1 unit", self.today_str, 21, par_level=2, purchase_location="Costco")
        self._add_historical_consumption("Costco Oranges", 21, 1)

        shopping_list = self.manager.get_shopping_list_items(store_filter="Costco")
        self.assertEqual(len(shopping_list), 1)
        self.assertEqual(shopping_list[0]['name'], "Costco Oranges")

    def test_get_shopping_list_search_term(self):
        self._add_inventory_item("Organic Apples", "1 unit", self.today_str, 7, par_level=2, purchase_location="Sobeys")
        self._add_historical_consumption("Organic Apples", 7, 1)
        self._add_inventory_item("Apple Pie", "1 unit", self.today_str, 7, par_level=2, purchase_location="Sobeys")
        self._add_historical_consumption("Apple Pie", 7, 1)
        self._add_inventory_item("Orange Juice", "1 unit", self.today_str, 7, par_level=2, purchase_location="Sobeys")
        self._add_historical_consumption("Orange Juice", 7, 1)

        shopping_list_apple = self.manager.get_shopping_list_items(search_term="Apple")
        self.assertEqual(len(shopping_list_apple), 2)
        self.assertTrue(any(it['name'] == "Organic Apples" for it in shopping_list_apple))
        self.assertTrue(any(it['name'] == "Apple Pie" for it in shopping_list_apple))

        shopping_list_pie = self.manager.get_shopping_list_items(search_term="Pie")
        self.assertEqual(len(shopping_list_pie), 1)
        self.assertEqual(shopping_list_pie[0]['name'], "Apple Pie")

        shopping_list_organic_apples = self.manager.get_shopping_list_items(search_term="Organic Apples")
        self.assertEqual(len(shopping_list_organic_apples), 1)
        self.assertEqual(shopping_list_organic_apples[0]['name'], "Organic Apples")


    def test_get_shopping_list_item_no_purchase_location(self):
        self._add_inventory_item("Mystery Item", "1 unit", self.today_str, 7, par_level=2, purchase_location=None)
        self._add_historical_consumption("Mystery Item", 7, 1) # Would qualify if it had a location
        self.assertEqual(self.manager.get_shopping_list_items(), [])

    def test_get_shopping_list_item_zero_par_level(self):
        self._add_inventory_item("Zero Par Item", "1 unit", self.today_str, 7, par_level=0, purchase_location="Sobeys")
        self._add_historical_consumption("Zero Par Item", 7, 1) # Would qualify if par > 0
        self.assertEqual(self.manager.get_shopping_list_items(), [])

    def test_get_shopping_list_item_none_par_level(self):
        # Test case where par_level might be None in DB (though schema defaults to 0)
        # Add item with par_level explicitly set to None if DB allows (our add method defaults it)
        conn = self.manager._get_db_connection()
        cursor = conn.cursor()
        item_name = "None Par Item"
        cursor.execute('''
            INSERT INTO inventory_items (name, quantity, purchase_date, expiry_date, par_level, purchase_location)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (item_name, "1 unit", self.today_str, (self.today + timedelta(days=7)).isoformat(), None, "Sobeys"))
        conn.commit()
        conn.close()
        self._add_historical_consumption(item_name, 7, 1)
        self.assertEqual(self.manager.get_shopping_list_items(), [])


    def test_get_shopping_list_recommendation_logic(self):
        item_name = "Test Item Reco"
        current_stock = 5
        par_level = 3
        daily_consumption_rate = 1
        purchase_location = "Sobeys" # 7-day cycle

        self._add_inventory_item(item_name, f"{current_stock} units", self.today_str, 30,
                                 par_level=par_level, purchase_location=purchase_location)

        # Simulate daily consumption for 30 days to establish avg rate
        for i in range(1, 31): # days ago
            self._add_historical_consumption(item_name, daily_consumption_rate, i)

        # Expected calculation:
        # Avg Daily Consumption should be very close to daily_consumption_rate (1)
        # Projection days for Sobeys = 7 days
        # Projected consumption until next shop = avg_daily_consumption * 7
        #   (approx. 1 * 7 = 7 units)
        # Stock at next shop = current_stock - projected_consumption_until_next_shop
        #   (approx. 5 - 7 = -2 units)
        # Target stock after shopping = par_level + projected_consumption_until_next_shop
        #   (approx. 3 + 7 = 10 units)
        # Recommended purchase amount = target_stock_after_shopping - current_stock
        #   (approx. 10 - 5 = 5 units)

        shopping_list = self.manager.get_shopping_list_items()
        self.assertEqual(len(shopping_list), 1)
        item = shopping_list[0]
        self.assertEqual(item['name'], item_name)
        # Verify avg daily consumption from projection_demand method
        # total consumed = 30 * 1 = 30. avg = 30/30 = 1.
        self.assertAlmostEqual(item['avg_daily_consumption'], daily_consumption_rate, places=2)

        expected_proj_consumption = daily_consumption_rate * 7 # Sobeys cycle
        expected_target_stock = par_level + expected_proj_consumption
        expected_reco = expected_target_stock - current_stock

        self.assertAlmostEqual(item['recommended_purchase_amount'], expected_reco, places=2)

if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
