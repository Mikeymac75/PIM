import os
import pytest
import openpyxl
from io import BytesIO
from flask import session, get_flashed_messages

# Assuming your Flask app instance is named 'app' in 'app.py'
# and InventoryManager, RecipeManager are accessible
from app import app # Only import app instance
import app as main_app_module # Import the module itself for monkeypatching
from RecipeManager import RecipeManager
from Food_manager import InventoryManager

# Database path for testing
TEST_DB_NAME = "test_food_app_recipes_upload.db"

@pytest.fixture
def test_db_path(tmp_path):
    """Provides a temporary database path for tests."""
    return tmp_path / TEST_DB_NAME

@pytest.fixture
def client(test_db_path):
    """Configures the Flask app for testing and sets up a test client."""
    app.config['TESTING'] = True
    # Explicitly set the database path in the global app config so get_db() uses it
    app.config['DATABASE_FILE_PATH'] = str(test_db_path)
    app.secret_key = 'test_secret_key'
    app.config['LOGIN_DISABLED'] = True

    # Setup initial data manually using a separate manager instance on the test DB
    test_inventory_manager = InventoryManager(db_filepath=str(test_db_path))

    with app.app_context():
        # Tables should be created by app startup (or we ensure they exist)
        # Since we just pointed app to a new DB path, the tables might not exist if app was already initialized
        # So we force table creation via the test_inventory_manager which calls _initialize_db in init

        products_to_add = [
            {'name': 'Flour', 'category_id': 1, 'subcategory_id': None, 'unit_of_measure': 'kg', 'default_expiry_days': 365, 'par_level': 1, 'max_holding_amount': 5},
            {'name': 'Sugar', 'category_id': 1, 'subcategory_id': None, 'unit_of_measure': 'kg', 'default_expiry_days': 730, 'par_level': 1, 'max_holding_amount': 3},
            {'name': 'Eggs', 'category_id': 2, 'subcategory_id': None, 'unit_of_measure': 'dozen', 'default_expiry_days': 28, 'par_level': 1, 'max_holding_amount': 2},
            {'name': 'Yeast', 'category_id': 1, 'subcategory_id': None, 'unit_of_measure': 'g', 'default_expiry_days': 180, 'par_level': 50, 'max_holding_amount': 100},
            {'name': 'Butter', 'category_id': 2, 'subcategory_id': None, 'unit_of_measure': 'lb', 'default_expiry_days': 60, 'par_level': 1, 'max_holding_amount': 2},
            {'name': 'Milk', 'category_id': 2, 'subcategory_id': None, 'unit_of_measure': 'L', 'default_expiry_days': 7, 'par_level': 1, 'max_holding_amount': 2},
            {'name': 'Vanilla Extract', 'category_id': 1, 'subcategory_id': None, 'unit_of_measure': 'mL', 'default_expiry_days': 730, 'par_level': 100, 'max_holding_amount': 250},
            {'name': 'Chocolate Chips', 'category_id': 1, 'subcategory_id': None, 'unit_of_measure': 'g', 'default_expiry_days': 365, 'par_level': 200, 'max_holding_amount': 500},
            {'name': 'Cake Mix', 'category_id': 3, 'subcategory_id': None, 'unit_of_measure': 'box', 'default_expiry_days': 365, 'par_level': 2, 'max_holding_amount': 5},
            {'name': 'Bread Loaf', 'category_id': 3, 'subcategory_id': None, 'unit_of_measure': 'loaf', 'default_expiry_days': 7, 'par_level': 1, 'max_holding_amount': 3},
            {'name': 'Cookies Batch', 'category_id': 3, 'subcategory_id': None, 'unit_of_measure': 'batch', 'default_expiry_days': 14, 'par_level': 1, 'max_holding_amount': 3},
        ]
        test_inventory_manager.add_category("Baking Supplies")
        test_inventory_manager.add_category("Dairy & Refrigerated")
        test_inventory_manager.add_category("Finished Goods")
        for prod_data in products_to_add:
            test_inventory_manager.create_product(**prod_data)

    with app.test_client() as client:
        yield client

    if os.path.exists(str(test_db_path)):
        os.remove(str(test_db_path))

def create_excel_file_bytes(header_row, data_rows):
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.append(header_row)
    for row_data in data_rows:
        sheet.append(row_data)
    excel_file_bytes = BytesIO()
    workbook.save(excel_file_bytes)
    excel_file_bytes.seek(0)
    return excel_file_bytes

def test_upload_recipes_excel_get_page(client):
    response = client.get('/upload_recipes_excel')
    assert response.status_code == 200
    assert b"Upload Recipes from Excel" in response.data

def test_upload_no_file_selected(client):
    response = client.post('/upload_recipes_excel', data={}, content_type='multipart/form-data')
    assert response.status_code == 302
    flashes = get_flashed_messages(with_categories=True)
    assert any('No file part in the request.' in message for category, message in flashes if category == 'error')

def test_upload_empty_filename(client):
    data = {'excel_file': (BytesIO(b""), '')}
    response = client.post('/upload_recipes_excel', data=data, content_type='multipart/form-data')
    assert response.status_code == 302
    flashes = get_flashed_messages(with_categories=True)
    assert any('No selected file.' in message for category, message in flashes if category == 'error')

def test_upload_invalid_file_type(client):
    data = {'excel_file': (BytesIO(b"text"), 'test.txt')}
    response = client.post('/upload_recipes_excel', data=data, content_type='multipart/form-data')
    assert response.status_code == 302
    flashes = get_flashed_messages(with_categories=True)
    assert any('Invalid file type. Please upload an .xlsx file.' in message for category, message in flashes if category == 'error')

def test_upload_corrupted_excel_file(client):
    data = {'excel_file': (BytesIO(b"corrupted"), 'fake.xlsx')}
    response = client.post('/upload_recipes_excel', data=data, content_type='multipart/form-data')
    assert response.status_code == 302
    flashes = get_flashed_messages(with_categories=True)
    assert any("corrupted" in message.lower() and ("excel" in message.lower() or "file could not be opened" in message.lower()) for category, message in flashes if category == 'error'), f"Flashes: {flashes}"

def test_upload_recipes_successful_simple(client):
    # Verify using a fresh manager connected to the test DB
    test_recipe_manager = RecipeManager(db_filepath=app.config['DATABASE_FILE_PATH'])
    header = ["Recipe Name", "Ingredient 1 Name", "Ingredient 1 Quantity"]
    data = [["Test Bread", "Flour", "500g"]]
    excel_bytes = create_excel_file_bytes(header, data)
    response = client.post('/upload_recipes_excel', data={'excel_file': (excel_bytes, 'simple.xlsx')})
    assert response.status_code == 302
    flashes = get_flashed_messages(with_categories=True)
    assert any('Successfully added 1 recipes' in message for cat, message in flashes if cat == 'success')
    recipes = test_recipe_manager.get_all_recipes()
    assert len(recipes) == 1
    assert recipes[0]['name'] == "Test Bread"

def test_upload_recipes_successful_with_all_fields(client):
    test_recipe_manager = RecipeManager(db_filepath=app.config['DATABASE_FILE_PATH'])
    test_inventory_manager = InventoryManager(db_filepath=app.config['DATABASE_FILE_PATH'])
    header = ["Recipe Name", "Description", "Instructions", "Output Product Name", "Output Yield",
              "Ingredient 1 Name", "Ingredient 1 Quantity", "Ingredient 1 Notes"]
    data = [["Deluxe Cake", "Yummy", "Mix bake", "Cake Mix", "1", "Flour", "250", "Sifted"]]
    excel_bytes = create_excel_file_bytes(header, data)
    response = client.post('/upload_recipes_excel', data={'excel_file': (excel_bytes, 'deluxe.xlsx')})
    assert response.status_code == 302
    flashes = get_flashed_messages(with_categories=True)
    assert any('Successfully added 1 recipes' in message for cat, message in flashes if cat == 'success')
    recipe = test_recipe_manager.get_recipe_by_name("Deluxe Cake")
    assert recipe is not None
    assert recipe['description'] == "Yummy"
    output_product = test_inventory_manager.get_product_by_name("Cake Mix")
    assert recipe['output_product_id'] == output_product['id']
    assert recipe['output_yield'] == 1.0

def test_upload_recipes_missing_recipe_name(client):
    test_recipe_manager = RecipeManager(db_filepath=app.config['DATABASE_FILE_PATH'])
    header = ["Recipe Name", "Ingredient 1 Name", "Ingredient 1 Quantity"]
    data = [["", "Flour", "100g"]]
    excel_bytes = create_excel_file_bytes(header, data)
    response = client.post('/upload_recipes_excel', data={'excel_file': (excel_bytes, 'missing_name.xlsx')})
    assert response.status_code == 302
    flashes = get_flashed_messages(with_categories=True)
    expected_warning_message = "Row 2: Recipe Name is missing but other data present. Skipped."
    expected_general_warning = "1 warnings encountered:"
    assert any(expected_warning_message in msg for cat, msg in flashes if cat == 'warning_detail')
    assert any(expected_general_warning in msg for cat, msg in flashes if cat == 'warning')
    assert len(test_recipe_manager.get_all_recipes()) == 0

def test_upload_recipes_output_product_not_found(client):
    header = ["Recipe Name", "Output Product Name", "Output Yield"]
    data = [["Mystery Cake", "NonExistent Cake", "1"]]
    excel_bytes = create_excel_file_bytes(header, data)
    response = client.post('/upload_recipes_excel', data={'excel_file': (excel_bytes, 'bad_output.xlsx')})
    assert response.status_code == 302
    flashes = get_flashed_messages(with_categories=True)
    assert any("Output Product Name 'NonExistent Cake' not found" in message for cat, message in flashes if cat == 'error_detail')

def test_upload_recipes_output_yield_missing(client):
    header = ["Recipe Name", "Output Product Name", "Output Yield"]
    data = [["Productive Recipe", "Cake Mix", ""]]
    excel_bytes = create_excel_file_bytes(header, data)
    response = client.post('/upload_recipes_excel', data={'excel_file': (excel_bytes, 'missing_yield.xlsx')})
    flashes = get_flashed_messages(with_categories=True)
    assert any("Output Yield is required when Output Product Name is provided" in message for cat, message in flashes if cat == 'error_detail')

def test_upload_recipes_ingredient_name_not_found(client):
    header = ["Recipe Name", "Ingredient 1 Name", "Ingredient 1 Quantity"]
    data = [["Mystery Ing Bread", "Unobtainium", "100"]]
    excel_bytes = create_excel_file_bytes(header, data)
    response = client.post('/upload_recipes_excel', data={'excel_file': (excel_bytes, 'bad_ing.xlsx')})
    flashes = get_flashed_messages(with_categories=True)
    assert any("Failed to add recipe - Ingredient 'Unobtainium' not found" in message for cat, message in flashes if cat == 'error_detail')

def test_upload_recipes_ingredient_quantity_missing(client):
    header = ["Recipe Name", "Ingredient 1 Name", "Ingredient 1 Quantity"]
    data = [["Flour Only", "Flour", ""]]
    excel_bytes = create_excel_file_bytes(header, data)
    response = client.post('/upload_recipes_excel', data={'excel_file': (excel_bytes, 'missing_qty.xlsx')})
    flashes = get_flashed_messages(with_categories=True)
    assert any("Ingredient 1 Quantity is required for 'Flour'" in message for cat, message in flashes if cat == 'error_detail')

def test_upload_recipes_multiple_recipes_mixed_validity(client):
    test_recipe_manager = RecipeManager(db_filepath=app.config['DATABASE_FILE_PATH'])
    header_fixed = ["Recipe Name", "Ingredient 1 Name", "Ingredient 1 Quantity", "Description"]
    data = [["Valid Bread", "Flour", "500", "Good"],
            ["Invalid Qty", "Sugar", "", "Bad"],
            ["Valid Cookies", "Eggs", "2", "Nice"],
            ["Invalid Ing", "Unobtainium", "1", "Fail"]]
    excel_bytes_fixed = create_excel_file_bytes(header_fixed, data)

    response = client.post('/upload_recipes_excel', data={'excel_file': (excel_bytes_fixed, 'mixed.xlsx')})
    flashes = get_flashed_messages(with_categories=True)
    assert any('Successfully added 2 recipes' in message for cat, message in flashes if cat == 'success')
    assert any("Ingredient 1 Quantity is required for 'Sugar'" in message for cat, message in flashes if cat == 'error_detail')
    assert any("Failed to add recipe - Ingredient 'Unobtainium' not found" in message for cat, message in flashes if cat == 'error_detail')
    recipes = test_recipe_manager.get_all_recipes()
    recipe_names = {r['name'] for r in recipes}
    assert "Valid Bread" in recipe_names
    assert "Valid Cookies" in recipe_names
    assert len(recipes) == 2

def test_upload_recipes_excel_missing_mandatory_header(client):
    header = ["Description", "Ingredient 1 Name", "Ingredient 1 Quantity"]
    data = [["Desc", "Flour", "100g"]]
    excel_bytes = create_excel_file_bytes(header, data)
    response = client.post('/upload_recipes_excel', data={'excel_file': (excel_bytes, 'missing_hdr.xlsx')})
    flashes = get_flashed_messages(with_categories=True)
    assert any("Missing required column in Excel: 'Recipe Name'" in message for cat, message in flashes if cat == 'error')

def test_upload_recipes_excel_empty_file(client):
    header = ["Recipe Name", "Ingredient 1 Name", "Ingredient 1 Quantity"]
    excel_bytes = create_excel_file_bytes(header, [])
    response = client.post('/upload_recipes_excel', data={'excel_file': (excel_bytes, 'empty.xlsx')})
    flashes = get_flashed_messages(with_categories=True)
    assert any("No new recipes were found or added" in message for cat, message in flashes if cat == 'info')

def test_upload_recipes_with_optional_fields_blank(client):
    test_recipe_manager = RecipeManager(db_filepath=app.config['DATABASE_FILE_PATH'])
    header = ["Recipe Name", "Description", "Instructions", "Output Product Name", "Output Yield",
              "Ingredient 1 Name", "Ingredient 1 Quantity", "Ingredient 1 Notes"]
    data = [["Minimal Recipe", "", "", "", "", "Flour", "100", ""]]
    excel_bytes = create_excel_file_bytes(header, data)
    response = client.post('/upload_recipes_excel', data={'excel_file': (excel_bytes, 'minimal.xlsx')})
    flashes = get_flashed_messages(with_categories=True)
    assert any("Successfully added 1 recipes" in message for cat, message in flashes if cat == 'success')
    recipe = test_recipe_manager.get_recipe_by_name("Minimal Recipe")
    assert recipe['description'] == ""
    assert recipe['instructions'] == ""

def test_upload_recipes_numeric_conversion_errors(client):
    header = ["Recipe Name", "Output Product Name", "Output Yield", "Ingredient 1 Name", "Ingredient 1 Quantity"]
    data = [["Bad Yield", "Cake Mix", "abc", "Flour", "100"],
            ["Negative Yield", "Cake Mix", "-5", "Flour", "100"],
            ["Bad Ing Qty", "Cake Mix", "1", "Flour", "xyz"],
            ["Negative Ing Qty", "Cake Mix", "1", "Flour", "-2"]] # This will cause "Invalid Ingredient ... Quantity format '-2'"
    excel_bytes = create_excel_file_bytes(header, data)
    response = client.post('/upload_recipes_excel', data={'excel_file': (excel_bytes, 'num_errors.xlsx')})
    flashes = get_flashed_messages(with_categories=True)
    assert any("Invalid Output Yield 'abc'" in message for cat, message in flashes if cat == 'error_detail')
    assert any("Output Yield must be a positive number" in message for cat, message in flashes if cat == 'error_detail')
    assert any("Invalid Ingredient 1 Quantity format 'xyz' for 'Flour'. Expected format like '100' or '100g'." in message for cat, message in flashes if cat == 'error_detail')
    # Corrected assertion for the "-2" quantity case:
    assert any("Invalid Ingredient 1 Quantity format '-2' for 'Flour'. Expected format like '100' or '100g'." in message for cat, message in flashes if cat == 'error_detail')
    assert any("4 rows/recipes had errors" in message for cat, message in flashes if cat == 'error')

def test_upload_recipes_max_ingredients(client):
    test_recipe_manager = RecipeManager(db_filepath=app.config['DATABASE_FILE_PATH'])
    header = ["Recipe Name"]
    ingredients_data = []
    for i in range(1, 16):
        header.extend([f"Ingredient {i} Name", f"Ingredient {i} Quantity", f"Ingredient {i} Notes"])
        product_name = ['Flour', 'Sugar', 'Eggs', 'Yeast', 'Butter', 'Milk', 'Vanilla Extract',
                        'Chocolate Chips', 'Flour', 'Sugar', 'Eggs', 'Yeast', 'Butter', 'Milk', 'Vanilla Extract'][i-1]
        ingredients_data.extend([product_name, str(i * 10), f"Note {i}"])
    data_row = ["Max Ing Recipe"] + ingredients_data
    excel_bytes = create_excel_file_bytes(header, [data_row])
    response = client.post('/upload_recipes_excel', data={'excel_file': (excel_bytes, 'max_ing.xlsx')})
    flashes = get_flashed_messages(with_categories=True)
    assert any("Successfully added 1 recipes" in message for cat, message in flashes if cat == 'success')
    recipe = test_recipe_manager.get_recipe_by_name("Max Ing Recipe")
    assert len(recipe['ingredients']) == 15

def test_upload_recipes_yield_without_output_product_warning(client):
    header_fixed = ["Recipe Name", "Output Product Name", "Output Yield", "Ingredient 1 Name", "Ingredient 1 Quantity"]
    data_fixed = [["YieldNoProd", "", "5.0", "Flour", "100"]]
    excel_bytes = create_excel_file_bytes(header_fixed, data_fixed)
    response = client.post('/upload_recipes_excel', data={'excel_file': (excel_bytes, 'yield_no_prod.xlsx')})
    flashes = get_flashed_messages(with_categories=True)
    assert any("Output Yield '5.0' provided without an Output Product Name. Yield will be ignored." in message for cat, message in flashes if cat == 'warning_detail')
    assert any("Successfully added 1 recipes" in message for cat, message in flashes if cat == 'success')

def test_upload_recipes_ingredient_quantity_without_name_error(client):
    test_recipe_manager = RecipeManager(db_filepath=app.config['DATABASE_FILE_PATH'])
    header = ["Recipe Name", "Ingredient 1 Name", "Ingredient 1 Quantity"]
    data = [["QtyNoName", "", "100"]]
    excel_bytes = create_excel_file_bytes(header, data)
    response = client.post('/upload_recipes_excel', data={'excel_file': (excel_bytes, 'qty_no_name.xlsx')})
    flashes = get_flashed_messages(with_categories=True)
    assert any("Ingredient 1 Name is missing but Quantity '100' was provided." in message for cat, message in flashes if cat == 'error_detail')
    assert len(test_recipe_manager.get_all_recipes()) == 0
