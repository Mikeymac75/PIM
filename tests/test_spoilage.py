
import unittest
from datetime import date, timedelta
from Food_manager import InventoryManager

class TestSpoilageReport(unittest.TestCase):
    def setUp(self):
        # Use in-memory DB for testing
        self.manager = InventoryManager(":memory:")

        # Setup Categories
        self.manager.add_category("TestCategory")
        cat_id = self.manager.get_category_by_name("TestCategory")['id']

        # Setup Products
        # 1. Expired Product
        self.manager.create_product("Expired Milk", cat_id, None, "liters", 14)
        # 2. Waste Risk Product (High stock, low consumption)
        self.manager.create_product("Bulk Yogurt", cat_id, None, "tubs", 30)
        # 3. Safe Product (Expiring soon but will be eaten)
        self.manager.create_product("Canned Beans", cat_id, None, "cans", 365)

        self.expired_id = self.manager.get_product_by_name("Expired Milk")['id']
        self.waste_id = self.manager.get_product_by_name("Bulk Yogurt")['id']
        self.safe_id = self.manager.get_product_by_name("Canned Beans")['id']

    def tearDown(self):
        self.manager.close_connection()

    def test_expired_status(self):
        # Add stock that expired yesterday
        today = date.today()
        purchase_date = (today - timedelta(days=20)).isoformat() # Expired 6 days ago (default 14)
        self.manager.add_inventory_stock(self.expired_id, "2", purchase_date)

        report = self.manager.get_spoilage_report()
        expired_items = [x for x in report if x['status'] == "EXPIRED"]

        self.assertTrue(len(expired_items) > 0)
        self.assertEqual(expired_items[0]['name'], "Expired Milk")
        self.assertTrue("Expired" in expired_items[0]['reason'])

    def test_waste_risk_status(self):
        # Setup: Need stock to consume from first
        today = date.today()
        # Add plenty of stock initially so we can consume
        self.manager.add_inventory_stock(self.waste_id, "200", today.isoformat())

        # Create consumption history: 1 tub per day for past 30 days
        for i in range(30):
            d = (today - timedelta(days=i)).isoformat()
            self.manager.consume_item("Bulk Yogurt", 1.0, consumed_date_str=d)

        # Current State:
        # Initial Stock 200. Consumed 30. Remaining 170.
        # Rate = 1.0/day (30 consumed / 30 days).
        # Days of Stock Left = 170 / 1 = 170 days.
        # Expiry (default 30 days) is from 'today' (since we used today as purchase date above).
        # Expiry Date = today + 30. Days until expiry = 30.
        # 170 (stock days) > 30 (expiry days) -> Waste Risk.

        report = self.manager.get_spoilage_report()
        waste_items = [x for x in report if x['name'] == "Bulk Yogurt"]

        self.assertTrue(len(waste_items) > 0)
        self.assertEqual(waste_items[0]['status'], "Projected Waste")
        self.assertTrue("Stock lasts" in waste_items[0]['reason'])

    def test_expiring_soon_status(self):
        # Goal: Stock that expires in 5 days, but we eat it fast enough so it's NOT "Projected Waste".
        today = date.today()

        # Step 1: Add 30 dummy cans to establish consumption history
        self.manager.add_inventory_stock(self.safe_id, "30", today.isoformat())

        # Step 2: Consume 29. (Rate ~1/day, Remaining 1).
        for i in range(29):
             d = (today - timedelta(days=i)).isoformat()
             self.manager.consume_item("Canned Beans", 1.0, consumed_date_str=d)

        # Step 3: Add 1 can expiring in 5 days
        # Purchase date = today - (365 - 5) = today - 360
        purchase_date = (today - timedelta(days=360)).isoformat()
        self.manager.add_inventory_stock(self.safe_id, "1", purchase_date)

        # Current State:
        # Total Stock = 1 (dummy) + 1 (new) = 2.
        # Consumption Rate = 29/30 ~= 0.97/day.
        # Days of Stock Left = 2 / 0.97 = 2.06 days.
        # New Item Expiry = 5 days.
        # Logic Check:
        # 2.06 (Stock Days) > 5 (Expiry Days)? False. -> Not "Projected Waste".
        # 5 <= 7? True. -> "Expiring Soon".

        report = self.manager.get_spoilage_report()
        soon_items = [x for x in report if x['name'] == "Canned Beans" and x['days_until_expiry'] <= 5]

        self.assertTrue(len(soon_items) > 0, "Expected 'Canned Beans' in report")
        self.assertEqual(soon_items[0]['status'], "Expiring Soon")
        self.assertEqual(soon_items[0]['severity_score'], 1)

if __name__ == '__main__':
    unittest.main()
