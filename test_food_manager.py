import unittest
import sqlite3
from Food_manager import InventoryManager # Assuming Food_manager.py is in the same directory or accessible in PYTHONPATH

class TestInventoryManager(unittest.TestCase):
    def setUp(self):
        """Set up a temporary in-memory database and populate it with test data."""
        self.manager = InventoryManager(db_filepath=":memory:")
        # self.manager._initialize_db() # Should be called by constructor

        # Populate with diverse product data
        self.products_data = [
            {'name': 'Apples', 'category': 'Produce', 'subcategory': 'Fruit', 'unit_of_measure': 'kg', 'default_expiry_days': 10, 'purchase_location': 'Store A'},
            {'name': 'Bananas', 'category': 'Produce', 'subcategory': 'Fruit', 'unit_of_measure': 'kg', 'default_expiry_days': 5, 'purchase_location': 'Store B'},
            {'name': 'Chicken Breast', 'category': 'Meat', 'subcategory': 'Poultry', 'unit_of_measure': 'kg', 'default_expiry_days': 3, 'purchase_location': 'Store A'},
            {'name': 'Milk', 'category': 'Dairy', 'subcategory': 'Milk Products', 'unit_of_measure': 'liter', 'default_expiry_days': 7, 'purchase_location': 'Store C'},
            {'name': 'Bread', 'category': 'Bakery', 'subcategory': 'Bread', 'unit_of_measure': 'loaf', 'default_expiry_days': 4, 'purchase_location': 'Store B'},
            {'name': 'Organic Apples', 'category': 'Produce', 'subcategory': 'Fruit', 'unit_of_measure': 'kg', 'default_expiry_days': 12, 'purchase_location': 'Store D'},
            {'name': 'Salmon Fillet', 'category': 'Meat', 'subcategory': 'Fish', 'unit_of_measure': 'kg', 'default_expiry_days': 2, 'purchase_location': 'Store A'},
            {'name': 'Yogurt', 'category': 'Dairy', 'subcategory': 'Milk Products', 'unit_of_measure': 'kg', 'default_expiry_days': 14, 'purchase_location': 'Store C'},
            {'name': 'Carrots', 'category': 'Produce', 'subcategory': 'Vegetable', 'unit_of_measure': 'kg', 'default_expiry_days': 10, 'purchase_location': 'Store B'},
            {'name': 'Whole Wheat Bread', 'category': 'Bakery', 'subcategory': 'Bread', 'unit_of_measure': 'loaf', 'default_expiry_days': 5, 'purchase_location': 'Store D'},
        ]

        for p_data in self.products_data:
            self.manager.create_product(
                name=p_data['name'],
                category=p_data.get('category'),
                subcategory=p_data.get('subcategory'),
                unit_of_measure=p_data['unit_of_measure'],
                default_expiry_days=p_data['default_expiry_days'],
                purchase_location=p_data.get('purchase_location')
            )

    def tearDown(self):
        """Close the database connection."""
        # For an in-memory database, connection closure might not be strictly necessary
        # as it's discarded, but good practice if it were a file.
        self.manager.close_connection()

    # --- Test cases for get_all_products ---

    def test_get_all_products_basic(self):
        products = self.manager.get_all_products(page=1, per_page=len(self.products_data)) # Ensure all are fetched
        self.assertEqual(len(products), len(self.products_data))
        # Check if names match (order might vary by default)
        fetched_names = sorted([p['name'] for p in products])
        expected_names = sorted([p['name'] for p in self.products_data])
        self.assertListEqual(fetched_names, expected_names)

    def test_get_all_products_search_term(self):
        products = self.manager.get_all_products(search_term='Apples')
        self.assertEqual(len(products), 2) # Apples, Organic Apples
        self.assertTrue(all('apple' in p['name'].lower() for p in products))

        products_organic = self.manager.get_all_products(search_term='Organic Apples')
        self.assertEqual(len(products_organic), 1)
        self.assertEqual(products_organic[0]['name'], 'Organic Apples')

        products_no_match = self.manager.get_all_products(search_term='NonExistent')
        self.assertEqual(len(products_no_match), 0)

    def test_get_all_products_category(self):
        products = self.manager.get_all_products(category='Produce')
        self.assertEqual(len(products), 4) # Apples, Bananas, Organic Apples, Carrots
        self.assertTrue(all(p['category'] == 'Produce' for p in products))

        products_meat = self.manager.get_all_products(category='Meat')
        self.assertEqual(len(products_meat), 2) # Chicken Breast, Salmon Fillet
        self.assertTrue(all(p['category'] == 'Meat' for p in products_meat))

        products_no_match = self.manager.get_all_products(category='NonExistentCategory')
        self.assertEqual(len(products_no_match), 0)
        
    def test_get_all_products_purchase_location(self):
        products = self.manager.get_all_products(purchase_location='Store A')
        self.assertEqual(len(products), 3) # Apples, Chicken Breast, Salmon Fillet
        self.assertTrue(all(p['purchase_location'] == 'Store A' for p in products))

        products_store_d = self.manager.get_all_products(purchase_location='Store D')
        self.assertEqual(len(products_store_d), 2) # Organic Apples, Whole Wheat Bread
        self.assertTrue(all(p['purchase_location'] == 'Store D' for p in products_store_d))
        
        products_no_match = self.manager.get_all_products(purchase_location='NonExistentStore')
        self.assertEqual(len(products_no_match), 0)

    def test_get_all_products_combined_filters(self):
        products = self.manager.get_all_products(search_term='Apples', category='Produce')
        self.assertEqual(len(products), 2) # Apples, Organic Apples
        self.assertTrue(all('apple' in p['name'].lower() and p['category'] == 'Produce' for p in products))

        products_meat_store_a = self.manager.get_all_products(category='Meat', purchase_location='Store A')
        self.assertEqual(len(products_meat_store_a), 2) # Chicken, Salmon
        self.assertTrue(all(p['category'] == 'Meat' and p['purchase_location'] == 'Store A' for p in products_meat_store_a))

    def test_get_all_products_sort_by_name(self):
        products_asc = self.manager.get_all_products(sort_by='name', sort_order='ASC', page=1, per_page=len(self.products_data))
        self.assertEqual([p['name'] for p in products_asc], sorted([p['name'] for p in self.products_data]))

        products_desc = self.manager.get_all_products(sort_by='name', sort_order='DESC', page=1, per_page=len(self.products_data))
        self.assertEqual([p['name'] for p in products_desc], sorted([p['name'] for p in self.products_data], reverse=True))

    def test_get_all_products_sort_by_category(self):
        products_asc = self.manager.get_all_products(sort_by='category', sort_order='ASC', page=1, per_page=len(self.products_data))
        # Python's sort is stable, so secondary sort by name (default from DB or previous sort) might influence exact order for same categories
        # We only care that categories are grouped and ordered correctly.
        categories_asc = [p['category'] for p in products_asc]
        self.assertEqual(categories_asc, sorted(categories_asc)) # Check if categories are in ascending order

        products_desc = self.manager.get_all_products(sort_by='category', sort_order='DESC', page=1, per_page=len(self.products_data))
        categories_desc = [p['category'] for p in products_desc]
        self.assertEqual(categories_desc, sorted(categories_desc, reverse=True))

    def test_get_all_products_sort_by_subcategory(self):
        products_asc = self.manager.get_all_products(sort_by='subcategory', sort_order='ASC', page=1, per_page=len(self.products_data))
        subcategories_asc = [p['subcategory'] for p in products_asc]
        self.assertEqual(subcategories_asc, sorted(subcategories_asc))

        products_desc = self.manager.get_all_products(sort_by='subcategory', sort_order='DESC', page=1, per_page=len(self.products_data))
        subcategories_desc = [p['subcategory'] for p in products_desc]
        self.assertEqual(subcategories_desc, sorted(subcategories_desc, reverse=True))

    def test_get_all_products_sort_by_purchase_location(self):
        # Filter out None locations for consistent sorting comparison if any exist in test data
        expected_locations = sorted([p['purchase_location'] for p in self.products_data if p['purchase_location'] is not None])
        
        products_asc = self.manager.get_all_products(sort_by='purchase_location', sort_order='ASC', page=1, per_page=len(self.products_data))
        locations_asc = [p['purchase_location'] for p in products_asc if p['purchase_location'] is not None] # Filter None for comparison
        # The exact order of all items can be complex due to how SQL handles NULLs in ORDER BY.
        # We are primarily interested that non-NULL values are sorted.
        # A more robust test would be to check that the sequence of non-null locations is sorted.
        is_sorted_asc = all(locations_asc[i] <= locations_asc[i+1] for i in range(len(locations_asc)-1))
        self.assertTrue(is_sorted_asc, "Purchase locations are not sorted ASC")


        products_desc = self.manager.get_all_products(sort_by='purchase_location', sort_order='DESC', page=1, per_page=len(self.products_data))
        locations_desc = [p['purchase_location'] for p in products_desc if p['purchase_location'] is not None]
        is_sorted_desc = all(locations_desc[i] >= locations_desc[i+1] for i in range(len(locations_desc)-1))
        self.assertTrue(is_sorted_desc, "Purchase locations are not sorted DESC")


    def test_get_all_products_pagination(self):
        all_product_names_sorted = sorted([p['name'] for p in self.products_data])

        # Page 1, 3 per page
        products_p1 = self.manager.get_all_products(sort_by='name', sort_order='ASC', page=1, per_page=3)
        self.assertEqual(len(products_p1), 3)
        self.assertEqual([p['name'] for p in products_p1], all_product_names_sorted[0:3])

        # Page 2, 3 per page
        products_p2 = self.manager.get_all_products(sort_by='name', sort_order='ASC', page=2, per_page=3)
        self.assertEqual(len(products_p2), 3)
        self.assertEqual([p['name'] for p in products_p2], all_product_names_sorted[3:6])

        # Last page (e.g., page 4 if 10 items, 3 per page)
        total_items = len(self.products_data)
        per_page = 3
        last_page_count = total_items % per_page if total_items % per_page != 0 else per_page
        last_page_num = (total_items + per_page - 1) // per_page
        
        products_last_page = self.manager.get_all_products(sort_by='name', sort_order='ASC', page=last_page_num, per_page=per_page)
        self.assertEqual(len(products_last_page), last_page_count)
        self.assertEqual([p['name'] for p in products_last_page], all_product_names_sorted[(last_page_num-1)*per_page:])

        # Page beyond available items
        products_empty = self.manager.get_all_products(sort_by='name', sort_order='ASC', page=last_page_num + 1, per_page=per_page)
        self.assertEqual(len(products_empty), 0)

    def test_get_all_products_invalid_sort_by(self):
        # Should default to sorting by name ASC
        products = self.manager.get_all_products(sort_by='invalid_column', sort_order='ASC', page=1, per_page=len(self.products_data))
        self.assertEqual([p['name'] for p in products], sorted([p['name'] for p in self.products_data]))

        products_desc = self.manager.get_all_products(sort_by='invalid_column', sort_order='DESC', page=1, per_page=len(self.products_data))
        # Defaulting to 'name' means sort_order should still be respected if it's valid
        self.assertEqual([p['name'] for p in products_desc], sorted([p['name'] for p in self.products_data], reverse=True))


    # --- Test cases for get_product_count ---
    def test_get_product_count_no_filters(self):
        count = self.manager.get_product_count()
        self.assertEqual(count, len(self.products_data))

    def test_get_product_count_search_term(self):
        count = self.manager.get_product_count(search_term='Apples')
        self.assertEqual(count, 2) # Apples, Organic Apples
        count_bread = self.manager.get_product_count(search_term='Bread')
        self.assertEqual(count_bread, 2) # Bread, Whole Wheat Bread

    def test_get_product_count_category(self):
        count = self.manager.get_product_count(category='Produce')
        self.assertEqual(count, 4)
        count_dairy = self.manager.get_product_count(category='Dairy')
        self.assertEqual(count_dairy, 2)

    def test_get_product_count_purchase_location(self):
        count = self.manager.get_product_count(purchase_location='Store A')
        self.assertEqual(count, 3)
        count_store_c = self.manager.get_product_count(purchase_location='Store C')
        self.assertEqual(count_store_c, 2)

    def test_get_product_count_combined_filters(self):
        count = self.manager.get_product_count(search_term='Bread', category='Bakery')
        self.assertEqual(count, 2)
        count_produce_store_b = self.manager.get_product_count(category='Produce', purchase_location='Store B')
        self.assertEqual(count_produce_store_b, 2) # Bananas, Carrots

    # --- Test cases for get_all_categories and get_all_purchase_locations ---
    def test_get_all_categories(self):
        categories = self.manager.get_all_categories()
        expected_categories = sorted(list(set(p['category'] for p in self.products_data if p.get('category'))))
        self.assertListEqual(categories, expected_categories)

    def test_get_all_purchase_locations(self):
        locations = self.manager.get_all_purchase_locations()
        expected_locations = sorted(list(set(p['purchase_location'] for p in self.products_data if p.get('purchase_location'))))
        self.assertListEqual(locations, expected_locations)

if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)

# Example of how to run this:
# Assuming this file is test_food_manager.py and Food_manager.py is in the same directory
# python -m unittest test_food_manager.py
