import unittest
from Food_manager import InventoryManager
from datetime import date, timedelta

class TestConsumptionProjection(unittest.TestCase):

    def setUp(self):
        self.manager = InventoryManager(db_filepath=":memory:")
        # Ensure tables are created
        self.manager._initialize_db()

        # Add Chicken Breasts product
        product_result = self.manager.create_product(
            name="Chicken Breasts",
            category_id=1, # Assuming a category 'TestCategory' with ID 1 exists or is created
            subcategory_id=None,
            unit_of_measure="Bag of 2",
            default_expiry_days=7,
            par_level=5,
            max_holding_amount=10,
            purchase_location="TestStore"
        )
        if not product_result["success"]:
             # Need to create category first if it's required and doesn't exist
            cat_result = self.manager.add_category("TestCategory")
            if not cat_result["success"] and "already exists" not in cat_result.get("message", ""):
                raise Exception(f"Failed to create category for test setup: {cat_result.get('message')}")

            # Try creating product again if category was the issue
            product_result = self.manager.create_product(
                name="Chicken Breasts",
                category_id=cat_result.get("category_id", 1), # Use ID from result or default
                subcategory_id=None,
                unit_of_measure="Bag of 2",
                default_expiry_days=7,
                par_level=5,
                max_holding_amount=10,
                purchase_location="TestStore"
            )
            if not product_result["success"]:
                 raise Exception(f"Failed to create product for test setup: {product_result.get('message')}")

        self.product_id = product_result["product_id"]
        self.product_name = "Chicken Breasts"

    def tearDown(self):
        self.manager.close_connection()

    def simulate_historical_consumption(self, product_id, product_name, days_ago, quantity):
        consumed_date = date.today() - timedelta(days=days_ago)
        # Minimal data for historical_items for this test
        with self.manager._get_db_connection() as conn:
            conn.cursor().execute("""
                INSERT INTO historical_items
                (product_id, name, quantity_consumed_this_time, consumed_date, purchase_date, expiry_date)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (product_id, product_name, quantity, consumed_date.isoformat(), consumed_date.isoformat(), consumed_date.isoformat()))
            conn.commit()

    def test_consumption_updates_projection(self):
        # 1. Log initial purchase
        purchase_date = date.today().isoformat()
        log_purchase_result = self.manager.log_purchase(
            product_id=self.product_id,
            purchase_date_str=purchase_date,
            quantity_purchased_float=10.0,
            cost_per_unit_float=5.0,
            vendor_str="TestVendor"
        )
        self.assertTrue(log_purchase_result["success"], f"Log purchase failed: {log_purchase_result.get('message')}")

        # 2. Simulate some historical consumption *before* today
        self.simulate_historical_consumption(self.product_id, self.product_name, days_ago=1, quantity=1.0) # 1 unit yesterday
        self.simulate_historical_consumption(self.product_id, self.product_name, days_ago=2, quantity=1.0) # 1 unit two days ago
        # Total historical before today (within 30 days) = 2 units

        lookback = 30

        # 3. Get initial projection
        initial_projection = self.manager.project_demand(self.product_id, lookback_days=lookback, projection_days=7)
        self.assertTrue(initial_projection["success"], f"Initial projection failed: {initial_projection.get('message')}")

        initial_avg_daily_consumption = initial_projection["avg_daily_consumption"]
        # Expected: (1+1) / 30 = 2 / 30 = 0.0666...
        self.assertAlmostEqual(initial_avg_daily_consumption, 2.0 / lookback, places=4)

        # Total consumed (lookback, estimated) = avg_daily_consumption * lookback_days
        initial_total_consumed_estimated = initial_avg_daily_consumption * lookback
        self.assertAlmostEqual(initial_total_consumed_estimated, 2.0, places=4)
        initial_current_stock = initial_projection["current_stock"]
        self.assertAlmostEqual(initial_current_stock, 10.0, places=4) # From the purchase

        # 4. Consume item today
        consumption_today_qty = 2.0
        consume_result = self.manager.consume_item(self.product_name, consumption_today_qty)
        self.assertTrue(consume_result["success"], f"Consume item failed: {consume_result.get('message')}")

        # 5. Get projection again
        updated_projection = self.manager.project_demand(self.product_id, lookback_days=lookback, projection_days=7)
        self.assertTrue(updated_projection["success"], f"Updated projection failed: {updated_projection.get('message')}")

        updated_avg_daily_consumption = updated_projection["avg_daily_consumption"]
        # Expected new total consumed: 1 (yesterday) + 1 (day before) + 2 (today) = 4 units
        # Expected new avg: 4 / 30 = 0.1333...
        expected_new_avg = 4.0 / lookback
        self.assertAlmostEqual(updated_avg_daily_consumption, expected_new_avg, places=4,
                               msg=f"Avg daily consumption did not update as expected. Got {updated_avg_daily_consumption}, expected {expected_new_avg}")

        # Total consumed (lookback, estimated) should now reflect today's consumption
        updated_total_consumed_estimated = updated_avg_daily_consumption * lookback
        self.assertAlmostEqual(updated_total_consumed_estimated, 4.0, places=4,
                               msg=f"Total consumed estimated did not update. Got {updated_total_consumed_estimated}, expected 4.0")

        updated_current_stock = updated_projection["current_stock"]
        self.assertAlmostEqual(updated_current_stock, 10.0 - consumption_today_qty, places=4)


if __name__ == '__main__':
    unittest.main()
