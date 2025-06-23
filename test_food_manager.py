import unittest
import sqlite3
from Food_manager import InventoryManager
from datetime import date, timedelta
import unittest.mock

class TestInventoryManager(unittest.TestCase):
    def setUp(self):
        self.manager = InventoryManager(db_filepath=":memory:")
        cat_produce_result = self.manager.add_category("Produce")
        self.produce_cat_id = cat_produce_result['category_id']
        cat_meat_result = self.manager.add_category("Meat")
        self.meat_cat_id = cat_meat_result['category_id']
        cat_dairy_result = self.manager.add_category("Dairy")
        self.dairy_cat_id = cat_dairy_result['category_id']
        cat_bakery_result = self.manager.add_category("Bakery")
        self.bakery_cat_id = cat_bakery_result['category_id']

        subcat_fruit_result = self.manager.add_subcategory("Fruit", self.produce_cat_id)
        self.fruit_subcat_id = subcat_fruit_result['subcategory_id']
        subcat_poultry_result = self.manager.add_subcategory("Poultry", self.meat_cat_id)
        self.poultry_subcat_id = subcat_poultry_result['subcategory_id']
        subcat_milk_result = self.manager.add_subcategory("Milk Products", self.dairy_cat_id)
        self.milk_subcat_id = subcat_milk_result['subcategory_id']
        subcat_bread_result = self.manager.add_subcategory("Bread", self.bakery_cat_id)
        self.bread_subcat_id = subcat_bread_result['subcategory_id']
        subcat_veg_result = self.manager.add_subcategory("Vegetable", self.produce_cat_id)
        self.veg_subcat_id = subcat_veg_result['subcategory_id']

        self.products_data_def = [
            {'name': 'Apples', 'category_id': self.produce_cat_id, 'subcategory_id': self.fruit_subcat_id, 'unit_of_measure': 'kg', 'default_expiry_days': 10, 'par_level': 5.0},
            {'name': 'Bananas', 'category_id': self.produce_cat_id, 'subcategory_id': self.fruit_subcat_id, 'unit_of_measure': 'kg', 'default_expiry_days': 5, 'par_level': 2.0},
            {'name': 'Chicken Breast', 'category_id': self.meat_cat_id, 'subcategory_id': self.poultry_subcat_id, 'unit_of_measure': 'kg', 'default_expiry_days': 3, 'par_level': 1.0},
            {'name': 'Milk', 'category_id': self.dairy_cat_id, 'subcategory_id': self.milk_subcat_id, 'unit_of_measure': 'liter', 'default_expiry_days': 7, 'par_level': 2.0},
            {'name': 'Bread', 'category_id': self.bakery_cat_id, 'subcategory_id': self.bread_subcat_id, 'unit_of_measure': 'loaf', 'default_expiry_days': 4, 'par_level': 1.0},
            {'name': 'Carrots', 'category_id': self.produce_cat_id, 'subcategory_id': self.veg_subcat_id, 'unit_of_measure': 'kg', 'default_expiry_days': 10, 'par_level': 1.0},
        ]
        self.product_ids_setup = {}
        for p_data in self.products_data_def:
            create_result = self.manager.create_product(
                name=p_data['name'], category_id=p_data['category_id'],
                subcategory_id=p_data.get('subcategory_id'), unit_of_measure=p_data['unit_of_measure'],
                default_expiry_days=p_data['default_expiry_days'], par_level=p_data.get('par_level', 0),
                max_holding_amount=p_data.get('max_holding_amount', 0), purchase_location=p_data.get('purchase_location')
            )
            self.assertTrue(create_result.get("success"), f"Failed to create product {p_data['name']}: {create_result.get('message')}")
            if create_result.get("success"): self.product_ids_setup[p_data['name']] = create_result['product_id']

    def tearDown(self):
        if self.manager and hasattr(self.manager, 'conn') and self.manager.conn:
            self.manager.close_connection(); self.manager.conn = None

    def test_get_current_inventory_default_behavior(self):
        self.manager.log_purchase(self.product_ids_setup["Apples"], "2023-01-10", 5.0, 1.0)
        self.manager.log_purchase(self.product_ids_setup["Bananas"], "2023-01-09", 10.0, 0.5)
        self.manager.log_purchase(self.product_ids_setup["Milk"], "2023-01-11", 2.0, 3.0)
        inv = self.manager.get_current_inventory(sort_by='p.name', sort_order='ASC')
        self.assertEqual(len(inv), 3)
        self.assertEqual(inv[0]['product_name'], "Apples")

    def test_get_historical_inventory_default_behavior(self):
        pid = self.product_ids_setup["Apples"]
        self.manager.log_purchase(pid, "2023-01-01", 5.0, 1.0)
        with unittest.mock.patch('datetime.date') as md:
            md.today.return_value = date(2023,1,5); md.fromisoformat.side_effect = lambda s: date.fromisoformat(s); md.side_effect = lambda *a,**k: date(*a,**k) if a else date.today()
            self.manager.consume_item("Apples", 2.0)
        hist = self.manager.get_historical_inventory()
        self.assertEqual(len(hist), 1); self.assertEqual(hist[0]['product_display_name'], "Apples")

    def test_log_purchase_and_wac_single_batch(self):
        pid = self.product_ids_setup["Apples"]
        res = self.manager.log_purchase(pid, "2024-03-15", 10.0, 1.50, "Fruit Stand")
        self.assertTrue(res.get("success")); iid = res.get("inventory_item_id")
        with self.manager._get_db_connection() as conn:
            self.assertEqual(conn.execute("SELECT cost_per_unit FROM inventory_items WHERE id = ?", (iid,)).fetchone()['cost_per_unit'], 1.50)
        self.assertEqual(self.manager.get_weighted_average_cost(pid), 1.50)

    def test_wac_multiple_batches(self):
        pid = self.product_ids_setup["Bananas"]
        self.manager.log_purchase(pid, "2024-03-10", 10.0, 0.50); self.manager.log_purchase(pid, "2024-03-12", 20.0, 0.75)
        self.assertAlmostEqual(self.manager.get_weighted_average_cost(pid), (10*0.5 + 20*0.75)/30.0, places=5)

    def test_wac_no_inventory(self):
        self.assertEqual(self.manager.get_weighted_average_cost(self.product_ids_setup["Milk"]), 0.0)

    def test_wac_after_consumption(self):
        pid = self.product_ids_setup["Bread"]
        self.manager.log_purchase(pid, "2024-03-01", 5.0, 2.00); self.manager.log_purchase(pid, "2024-03-05", 5.0, 2.50)
        self.manager.consume_item("Bread", 6.0)
        self.assertAlmostEqual(self.manager.get_weighted_average_cost(pid), 2.50, places=2)

    def test_consume_item_logs_cost_of_goods_used(self):
        pid = self.product_ids_setup["Chicken Breast"]; name = "Chicken Breast"
        self.manager.log_purchase(pid, "2024-03-10", 2.0, 10.00); self.manager.log_purchase(pid, "2024-03-12", 3.0, 12.00)
        wac = (2*10 + 3*12)/5.0; qty = 1.5
        with unittest.mock.patch('datetime.date') as md:
            md.today.return_value = date(2024,3,15); md.fromisoformat.side_effect = lambda s: date.fromisoformat(s); md.side_effect = lambda *a,**k: date(*a,**k) if a else date.today()
            self.manager.consume_item(name, qty)
        with self.manager._get_db_connection() as conn:
            cogs = sum(h['cost_of_goods_used'] for h in conn.execute("SELECT cost_of_goods_used FROM historical_items WHERE product_id = ? AND consumed_date = ?", (pid, "2024-03-15")).fetchall())
            self.assertAlmostEqual(cogs, qty*wac, places=2)

    def test_get_average_daily_consumption_no_override(self):
        pid = self.product_ids_setup["Apples"]; today = date.today()
        with self.manager._get_db_connection() as conn:
            for i in range(30): conn.execute("INSERT INTO historical_items (product_id, name, quantity_consumed_this_time, consumed_date) VALUES (?,?,?,?)",(pid,"Apples",1.0,(today-timedelta(days=i+1)).isoformat()))
            conn.commit()
        self.assertAlmostEqual(self.manager._get_average_daily_consumption(pid,30),1.0,places=5)

    def test_get_average_daily_consumption_with_override(self):
        pid = self.product_ids_setup["Bananas"]
        self.manager.save_consumption_overrides([{'product_id':pid,'override_rate':0.75}])
        self.assertEqual(self.manager._get_average_daily_consumption(pid,30),0.75)

    def test_get_average_daily_consumption_no_history_no_override(self):
        self.assertEqual(self.manager._get_average_daily_consumption(self.product_ids_setup["Milk"],30),0.0)

class TestProductionItems(unittest.TestCase):
    def setUp(self):
        self.manager = InventoryManager(db_filepath=":memory:")
        self.cat_id = self.manager.add_category("Produce")['category_id']
        self.prod_tomato_id = self.manager.create_product(name="Tomatoes", category_id=self.cat_id, subcategory_id=None, unit_of_measure="kg", default_expiry_days=7)['product_id']

    def tearDown(self): self.manager.close_connection()

    @unittest.mock.patch('datetime.date')
    def test_get_production_item_dynamic_status_and_yield_corrected_mock(self, mock_date_class):
        mock_date_class.today = unittest.mock.MagicMock()
        mock_date_class.fromisoformat.side_effect = date.fromisoformat
        mock_date_class.side_effect = lambda *args,**kwargs: date(*args,**kwargs) if args else date.today()

        plant_dt = date(2024,1,1)
        res = self.manager.add_production_item(name="DynPlant", associated_product_id=self.prod_tomato_id, plant_date_str=plant_dt.isoformat(),time_to_harvest_days=30,expected_harvest_period_days=15, expected_yield_total=3.0)
        item_id = res["item_id"]
        mock_date_class.today.return_value = date(2024,1,15)
        item = self.manager.get_production_item(item_id)
        self.assertEqual(item['calculated_status'], "Growing")
        self.assertAlmostEqual(item['estimated_daily_yield'], 0.2)

    @unittest.mock.patch('datetime.date')
    def test_get_all_production_items_dynamic_behavior(self, mock_date_class):
        mock_date_class.today = unittest.mock.MagicMock()
        mock_date_class.fromisoformat.side_effect = date.fromisoformat
        mock_date_class.side_effect = lambda *args,**kwargs: date(*args,**kwargs) if args else date.today()

        plant_dt = date(2024,1,1)
        self.manager.add_production_item(name="AllDynPlant",associated_product_id=self.prod_tomato_id,plant_date_str=plant_dt.isoformat(),time_to_harvest_days=30,expected_harvest_period_days=15,expected_yield_total=3.0,status="Growing")
        mock_date_class.today.return_value = date(2024,1,15)
        items = self.manager.get_all_production_items()
        self.assertEqual(items[0]['calculated_status'], "Growing")
        self.assertAlmostEqual(items[0]['estimated_daily_yield'], 0.2)

class TestFutureInventoryProjection(unittest.TestCase):
    def setUp(self):
        self.manager = InventoryManager(db_filepath=":memory:")
        self.cat_id = self.manager.add_category("FutureProj")['category_id']
        self.apple_id = self.manager.create_product(name="TestApples",category_id=self.cat_id,subcategory_id=None,unit_of_measure="pcs",default_expiry_days=10)['product_id']
        self.orange_id = self.manager.create_product(name="TestOranges",category_id=self.cat_id,subcategory_id=None,unit_of_measure="pcs",default_expiry_days=10)['product_id']
        self.manager.save_consumption_overrides([{'product_id':self.orange_id,'override_rate':0.5}])
        self.grapes_id = self.manager.create_product(name="TestGrapes",category_id=self.cat_id,subcategory_id=None,unit_of_measure="bunch",default_expiry_days=5)['product_id']

    def tearDown(self): self.manager.close_connection()

    def _add_hist_cons(self, pid, start_days_ago, end_days_ago, qty_day):
        today = date.today()
        with self.manager._get_db_connection() as conn:
            for i in range(start_days_ago, end_days_ago + 1):
                conn.execute("INSERT INTO historical_items (product_id,name,quantity_consumed_this_time,consumed_date) VALUES (?,?,?,?)",
                             (pid,f"Hist{pid}",qty_day,(today-timedelta(days=i)).isoformat()))
            conn.commit()

    def _assert_proj_struct(self, proj, days):
        self.assertEqual(len(proj), days, "Projection list length mismatch")
        for item in proj: self.assertIn('date', item)

    def test_projection_simple_consumption(self):
        self.manager.log_purchase(self.apple_id,date.today().isoformat(),10.0,1.0)
        self._add_hist_cons(self.apple_id,1,30,1.0)
        proj = self.manager.get_future_inventory_projection(self.apple_id,15)
        self._assert_proj_struct(proj,15)
        if not (proj and len(proj) > 9): self.fail("Projection too short")
        self.assertAlmostEqual(proj[0]['consumption'],1.0,places=1)
        self.assertAlmostEqual(proj[9]['projected_ending_inventory'],0.0,places=1)
        self.assertTrue(proj[9]['depletion_date_reached'])

    def test_projection_with_spoilage(self):
        self.manager.log_purchase(self.apple_id,date.today().isoformat(),5.0,1.0)
        self._add_hist_cons(self.apple_id,1,30,0.2)
        proj = self.manager.get_future_inventory_projection(self.apple_id,15)
        self._assert_proj_struct(proj,15)
        if not (proj and len(proj) > 9): self.fail("Projection too short")
        # Expected: 5 initial. 0.2 cons/day. Expires day 10 (index 9).
        # Start of day 9 (10th day): 5 - (0.2 * 9) = 3.2
        # Consumed on day 9: 0.2. Remaining before spoilage: 3.0
        # All 3.0 spoil.
        self.assertAlmostEqual(proj[9]['shrink'],3.0,places=1, msg=f"Shrink D9: {proj[9]['shrink']}")
        self.assertAlmostEqual(proj[9]['projected_ending_inventory'],0.0,places=1)
        self.assertTrue(proj[9]['depletion_date_reached'])

if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
