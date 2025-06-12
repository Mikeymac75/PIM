import unittest
import os
import sqlite3
from app import app, manager as app_manager
from Food_manager import InventoryManager

class TestAppProductList(unittest.TestCase):

    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        app.config['SECRET_KEY'] = 'test_secret_key'
        app.config['SERVER_NAME'] = 'localhost.test'

        self.app_context = app.app_context()
        self.app_context.push()

        self.client = app.test_client()

        self.original_db_filepath = app_manager.db_filepath
        app_manager.db_filepath = ":memory:"
        app_manager.conn = sqlite3.connect(":memory:")
        app_manager.conn.row_factory = sqlite3.Row
        app_manager._initialize_db()

        self.products_data = [
            {'id': 1, 'name': 'Apples', 'category': 'Produce', 'subcategory': 'Fruit', 'unit_of_measure': 'kg', 'default_expiry_days': 10, 'purchase_location': 'Store A'},
            {'id': 2, 'name': 'Bananas', 'category': 'Produce', 'subcategory': 'Fruit', 'unit_of_measure': 'kg', 'default_expiry_days': 5, 'purchase_location': 'Store B'},
            {'id': 3, 'name': 'Chicken Breast', 'category': 'Meat', 'subcategory': 'Poultry', 'unit_of_measure': 'kg', 'default_expiry_days': 3, 'purchase_location': 'Store A'},
            {'id': 4, 'name': 'Milk', 'category': 'Dairy', 'subcategory': 'Milk Products', 'unit_of_measure': 'liter', 'default_expiry_days': 7, 'purchase_location': 'Store C'},
            {'id': 5, 'name': 'Bread', 'category': 'Bakery', 'subcategory': 'Bread', 'unit_of_measure': 'loaf', 'default_expiry_days': 4, 'purchase_location': 'Store B'},
            {'id': 6, 'name': 'Organic Apples', 'category': 'Produce', 'subcategory': 'Fruit', 'unit_of_measure': 'kg', 'default_expiry_days': 12, 'purchase_location': 'Store D'},
            {'id': 7, 'name': 'Salmon Fillet', 'category': 'Meat', 'subcategory': 'Fish', 'unit_of_measure': 'kg', 'default_expiry_days': 2, 'purchase_location': 'Store A'},
            {'id': 8, 'name': 'Yogurt', 'category': 'Dairy', 'subcategory': 'Milk Products', 'unit_of_measure': 'kg', 'default_expiry_days': 14, 'purchase_location': 'Store C'},
            {'id': 9, 'name': 'Carrots', 'category': 'Produce', 'subcategory': 'Vegetable', 'unit_of_measure': 'kg', 'default_expiry_days': 10, 'purchase_location': 'Store B'},
            {'id': 10, 'name': 'Whole Wheat Bread', 'category': 'Bakery', 'subcategory': 'Bread', 'unit_of_measure': 'loaf', 'default_expiry_days': 5, 'purchase_location': 'Store D'},
        ]
        
        for p_data in self.products_data:
            app_manager.create_product(
                name=p_data['name'],
                category=p_data.get('category'),
                subcategory=p_data.get('subcategory'),
                unit_of_measure=p_data['unit_of_measure'],
                default_expiry_days=p_data['default_expiry_days'],
                purchase_location=p_data.get('purchase_location')
            )

    def tearDown(self):
        if app_manager.db_filepath == ":memory:" and app_manager.conn:
            app_manager.close_connection()
        
        app_manager.db_filepath = self.original_db_filepath
        app_manager.conn = None
        # app_manager._initialize_db() # Commented out

        self.app_context.pop()

    def test_products_page_loads(self):
        response = self.client.get('/products')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Product List", response.data)

    def test_filter_bar_elements_present(self):
        response = self.client.get('/products')
        self.assertEqual(response.status_code, 200)
        html_content = response.data.decode('utf-8')

        self.assertIn('name="search_term"', html_content)
        self.assertIn('name="category"', html_content)
        self.assertIn('name="purchase_location"', html_content)
        self.assertIn('type="submit"', html_content)
        self.assertIn('href="/products"', html_content)

    def test_filter_by_search_term(self):
        response = self.client.get('/products?search_term=Apples')
        self.assertEqual(response.status_code, 200)
        html_content = response.data.decode('utf-8')
        self.assertIn('Apples', html_content)
        self.assertIn('Organic Apples', html_content)
        self.assertNotIn('Bananas', html_content)
        # Pagination string "Page 1 of 1" is not shown if total_pages <= 1

    def test_filter_by_category(self):
        response = self.client.get('/products?category=Meat')
        self.assertEqual(response.status_code, 200)
        html_content = response.data.decode('utf-8')
        self.assertIn('Chicken Breast', html_content)
        self.assertIn('Salmon Fillet', html_content)
        self.assertNotIn('Apples', html_content)
        # Pagination string "Page 1 of 1" is not shown if total_pages <= 1

    def test_filter_by_purchase_location(self):
        response = self.client.get('/products?purchase_location=Store A')
        self.assertEqual(response.status_code, 200)
        html_content = response.data.decode('utf-8')
        self.assertIn('Apples', html_content)
        self.assertIn('Chicken Breast', html_content)
        self.assertIn('Salmon Fillet', html_content)
        self.assertNotIn('Bananas', html_content)
        # Pagination string "Page 1 of 1" is not shown if total_pages <= 1

    def test_sorting_by_name(self):
        response_asc = self.client.get('/products?sort_by=name&sort_order=ASC&per_page=10')
        html_asc = response_asc.data.decode('utf-8')
        positions = {}
        sorted_names = sorted([p['name'] for p in self.products_data])
        for name in sorted_names:
            positions[name] = html_asc.find(name)
        if len(sorted_names) >=3:
             self.assertTrue(positions[sorted_names[0]] < positions[sorted_names[1]] < positions[sorted_names[2]])

        response_desc = self.client.get('/products?sort_by=name&sort_order=DESC&per_page=10')
        html_desc = response_desc.data.decode('utf-8')
        positions_desc = {}
        for name in sorted_names:
            positions_desc[name] = html_desc.find(name)
        if len(sorted_names) >= 3:
            self.assertTrue(positions_desc[sorted_names[-1]] < positions_desc[sorted_names[-2]] < positions_desc[sorted_names[-3]])

    def test_pagination(self):
        response_p1 = self.client.get('/products?sort_by=name&sort_order=ASC&page=1&per_page=3')
        html_p1 = response_p1.data.decode('utf-8')
        sorted_names = sorted([p['name'] for p in self.products_data])
        self.assertIn(sorted_names[0], html_p1)
        self.assertIn(sorted_names[1], html_p1)
        self.assertIn(sorted_names[2], html_p1)
        self.assertNotIn(sorted_names[3], html_p1)
        self.assertIn("Page 1 of 4", html_p1)

        response_p2 = self.client.get('/products?sort_by=name&sort_order=ASC&page=2&per_page=3')
        html_p2 = response_p2.data.decode('utf-8')
        self.assertNotIn(sorted_names[2], html_p2)
        self.assertIn(sorted_names[3], html_p2)
        self.assertIn(sorted_names[4], html_p2)
        self.assertIn(sorted_names[5], html_p2)
        self.assertNotIn(sorted_names[6], html_p2)
        self.assertIn("Page 2 of 4", html_p2)

    def test_pagination_controls(self):
        response_p1 = self.client.get('/products?sort_by=name&sort_order=ASC&page=1&per_page=3')
        html_p1 = response_p1.data.decode('utf-8')
        self.assertIn("button-disabled", html_p1)
        self.assertIn("Previous", html_p1)
        self.assertNotIn("Next <i class=\"fas fa-chevron-right\"></i></span>", html_p1)
        self.assertIn("Next <i class=\"fas fa-chevron-right\"></i>", html_p1)

        response_p4 = self.client.get('/products?sort_by=name&sort_order=ASC&page=4&per_page=3')
        html_p4 = response_p4.data.decode('utf-8')
        self.assertNotIn("Previous</span>", html_p4)
        self.assertIn("Previous", html_p4)
        self.assertIn("button-disabled", html_p4)
        self.assertIn("Next", html_p4)

    def test_filter_sort_preservation_in_pagination(self):
        search_term_prod = ""
        category_prod = "Produce"
        per_page_prod = 2
        sort_by_prod = "name"
        sort_order_prod = "ASC"

        response_p1 = self.client.get(f'/products?search_term={search_term_prod}&category={category_prod}&sort_by={sort_by_prod}&sort_order={sort_order_prod}&page=1&per_page={per_page_prod}')
        html_p1 = response_p1.data.decode('utf-8')
        self.assertIn("Page 1 of 2", html_p1)
        
        self.assertIn('href="', html_p1)
        self.assertIn('category=Produce', html_p1.replace('&amp;', '&'))
        self.assertIn('sort_by=name', html_p1.replace('&amp;', '&'))
        self.assertIn('sort_order=ASC', html_p1.replace('&amp;', '&'))
        self.assertIn('page=2', html_p1.replace('&amp;', '&'))
        self.assertIn(f'per_page={per_page_prod}', html_p1.replace('&amp;', '&'))
        if not search_term_prod:
             self.assertNotIn(f'search_term={search_term_prod+"A"}', html_p1.replace('&amp;', '&'))
        if not category_prod:
             self.assertNotIn(f'category={category_prod+"A"}', html_p1.replace('&amp;', '&'))

    def test_clear_filters_functionality(self):
        response_filtered = self.client.get('/products?search_term=Apples&category=Produce&sort_by=name&sort_order=DESC')
        self.assertEqual(response_filtered.status_code, 200)
        html_filtered = response_filtered.data.decode('utf-8')
        
        clear_filters_url_expected = "/products"
        self.assertIn(f'href="{clear_filters_url_expected}"', html_filtered)
        
        response_cleared = self.client.get(clear_filters_url_expected)
        self.assertEqual(response_cleared.status_code, 200)
        html_cleared = response_cleared.data.decode('utf-8')

        self.assertIn('Apples', html_cleared)
        self.assertIn('Bananas', html_cleared)
        self.assertIn('Chicken Breast', html_cleared)
        self.assertIn('name="search_term" id="search_term" value=""', html_cleared)
        self.assertRegex(html_cleared, r'<select name="category"[^>]*>\s*<option value="" selected>\s*All Categories\s*</option>')
        self.assertRegex(html_cleared, r'<select name="purchase_location"[^>]*>\s*<option value="" selected>\s*All Locations\s*</option>')

if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
