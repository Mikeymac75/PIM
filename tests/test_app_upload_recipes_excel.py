import os
import pytest
import openpyxl
from io import BytesIO
from flask import session, get_flashed_messages

# Assuming your Flask app instance is named 'app' in 'app.py'
# and InventoryManager, RecipeManager are accessible
from app import app, manager as global_manager, recipe_mngr as global_recipe_mngr
from RecipeManager import RecipeManager # Corrected import
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
    app.config['DATABASE_FILE_PATH'] = str(test_db_path) # Override DB path
    app.secret_key = 'test_secret_key' # Needed for session/flash messages

    # Use new instances of managers for test isolation, pointing to the test DB
    # This ensures that the global manager instances in app.py are not directly used by tests
    # if they hold state or connections that might interfere.
    # However, the app routes will use the global instances. We need to re-point them.

    # Store original managers
    original_manager = global_manager
    original_recipe_mngr = global_recipe_mngr

    # Create new managers for the test DB
    test_inventory_manager = InventoryManager(db_filepath=str(test_db_path))
    test_recipe_manager = RecipeManager(db_filepath=str(test_db_path))

    # Monkeypatch the global manager instances within the app context for this test client
    app.inventory_manager = test_inventory_manager
    app.recipe_manager = test_recipe_manager
    # Also need to update the references used by the routes in app.py
    # This is a bit tricky. A cleaner way might be to make managers configurable in app.py
    # For now, let's assume routes pick up these new instances if we patch app.manager and app.recipe_mngr
    # This depends on how `manager` and `recipe_mngr` are used within app.py routes.
    # Let's try to directly patch the module-level variables in app.py
    # This is generally not recommended but can work for testing.
    import app as main_app_module
    main_app_module.manager = test_inventory_manager
    main_app_module.recipe_mngr = test_recipe_manager


    with app.test_client() as client:
        with app.app_context(): # Ensures DB operations occur within app context
            # Initialize DB schema
            test_inventory_manager.init_db() # Creates tables if they don't exist
            test_recipe_manager.init_db()   # Creates tables if they don't exist

            # Pre-populate with some products
            products_to_add = [
                {'name': 'Flour', 'category_id': 1, 'subcategory_id': None, 'unit_of_measure': 'kg', 'default_expiry_days': 365, 'par_level': 1, 'max_holding_amount': 5},
                {'name': 'Sugar', 'category_id': 1, 'subcategory_id': None, 'unit_of_measure': 'kg', 'default_expiry_days': 730, 'par_level': 1, 'max_holding_amount': 3},
                {'name': 'Eggs', 'category_id': 2, 'subcategory_id': None, 'unit_of_measure': 'dozen', 'default_expiry_days': 28, 'par_level': 1, 'max_holding_amount': 2},
                {'name': 'Yeast', 'category_id': 1, 'subcategory_id': None, 'unit_of_measure': 'g', 'default_expiry_days': 180, 'par_level': 50, 'max_holding_amount': 100},
                {'name': 'Butter', 'category_id': 2, 'subcategory_id': None, 'unit_of_measure': 'lb', 'default_expiry_days': 60, 'par_level': 1, 'max_holding_amount': 2},
                {'name': 'Milk', 'category_id': 2, 'subcategory_id': None, 'unit_of_measure': 'L', 'default_expiry_days': 7, 'par_level': 1, 'max_holding_amount': 2},
                {'name': 'Vanilla Extract', 'category_id': 1, 'subcategory_id': None, 'unit_of_measure': 'mL', 'default_expiry_days': 730, 'par_level': 100, 'max_holding_amount': 250},
                {'name': 'Chocolate Chips', 'category_id': 1, 'subcategory_id': None, 'unit_of_measure': 'g', 'default_expiry_days': 365, 'par_level': 200, 'max_holding_amount': 500},
                # Products that can be recipe outputs
                {'name': 'Cake Mix', 'category_id': 3, 'subcategory_id': None, 'unit_of_measure': 'box', 'default_expiry_days': 365, 'par_level': 2, 'max_holding_amount': 5},
                {'name': 'Bread Loaf', 'category_id': 3, 'subcategory_id': None, 'unit_of_measure': 'loaf', 'default_expiry_days': 7, 'par_level': 1, 'max_holding_amount': 3},
                {'name': 'Cookies Batch', 'category_id': 3, 'subcategory_id': None, 'unit_of_measure': 'batch', 'default_expiry_days': 14, 'par_level': 1, 'max_holding_amount': 3},
            ]
            # Add categories first if your manager requires it
            test_inventory_manager.add_category("Baking Supplies") # id 1
            test_inventory_manager.add_category("Dairy & Refrigerated") # id 2
            test_inventory_manager.add_category("Finished Goods") # id 3

            for prod_data in products_to_add:
                test_inventory_manager.create_product(**prod_data)

        yield client # client, test_inventory_manager, test_recipe_manager

    # Teardown: Revert monkeypatch and remove test DB
    main_app_module.manager = original_manager
    main_app_module.recipe_mngr = original_recipe_mngr

    if os.path.exists(str(test_db_path)):
        os.remove(str(test_db_path))

def create_excel_file_bytes(header_row, data_rows):
    """
    Creates an in-memory Excel (.xlsx) file.
    :param header_row: List of strings for the header.
    :param data_rows: List of lists, where each inner list is a row of data.
    :return: BytesIO object containing the Excel file bytes.
    """
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.append(header_row)
    for row_data in data_rows:
        sheet.append(row_data)

    excel_file_bytes = BytesIO()
    workbook.save(excel_file_bytes)
    excel_file_bytes.seek(0) # Rewind to the beginning of the stream
    return excel_file_bytes

# --- Test Cases Stubs ---

def test_upload_recipes_excel_get_page(client):
    """Test GET request to the upload page."""
    response = client.get('/upload_recipes_excel')
    assert response.status_code == 200
    assert b"Upload Recipes from Excel" in response.data
    assert b"Instructions for Excel File Format (Recipes):" in response.data

def test_upload_no_file_selected(client):
    """Test submitting the form with no file selected."""
    response = client.post('/upload_recipes_excel', data={}, content_type='multipart/form-data')
    assert response.status_code == 302 # Redirect expected
    assert response.location == '/upload_recipes_excel' # Redirects back to self
    with client.session_transaction() as sess:
        flashes = sess.get('_flashes', [])
    assert any('No file part in the request.' in message[1] for message in flashes)

def test_upload_empty_filename(client):
    """Test submitting the form with an empty filename (e.g., file input not actually used)."""
    data = {
        'excel_file': (BytesIO(b""), '') # Empty filename
    }
    response = client.post('/upload_recipes_excel', data=data, content_type='multipart/form-data')
    assert response.status_code == 302
    assert response.location == '/upload_recipes_excel'
    with client.session_transaction() as sess:
        flashes = sess.get('_flashes', [])
    assert any('No selected file.' in message[1] for message in flashes)


def test_upload_invalid_file_type(client):
    """Test uploading a file with an invalid extension (e.g., .txt)."""
    data = {
        'excel_file': (BytesIO(b"This is a test text file."), 'test.txt')
    }
    response = client.post('/upload_recipes_excel', data=data, content_type='multipart/form-data')
    assert response.status_code == 302
    assert response.location == '/upload_recipes_excel'
    with client.session_transaction() as sess:
        flashes = sess.get('_flashes', [])
    assert any('Invalid file type. Please upload an .xlsx file.' in message[1] for message in flashes)

def test_upload_corrupted_excel_file(client):
    """Test uploading a file that is not a valid Excel .xlsx file but has .xlsx extension."""
    data = {
        'excel_file': (BytesIO(b"This is not a real excel file content."), 'fake.xlsx')
    }
    response = client.post('/upload_recipes_excel', data=data, content_type='multipart/form-data')
    assert response.status_code == 302 # Should redirect back to the upload page
    assert response.location == '/upload_recipes_excel'
    with client.session_transaction() as sess:
        flashes = sess.get('_flashes', [])
    # Check for the specific flash message from the `openpyxl.utils.exceptions.InvalidFileException` catch
    assert any('The uploaded file is not a valid Excel (.xlsx) file or is corrupted.' in message[1] for message in flashes)


def test_upload_recipes_successful_simple(client):
    """Test uploading a valid Excel file with one simple recipe."""
    # Access the test-specific recipe manager via app context if needed for assertions
    # For route testing, the patched global one (main_app_module.recipe_mngr) is used by the route
    test_recipe_manager = main_app_module.recipe_mngr

    header = ["Recipe Name", "Ingredient 1 Name", "Ingredient 1 Quantity"]
    data = [
        ["Test Bread", "Flour", "500g"] # 'Flour' product exists
    ]
    excel_bytes = create_excel_file_bytes(header, data)

    response = client.post('/upload_recipes_excel', data={'excel_file': (excel_bytes, 'simple_recipe.xlsx')})

    assert response.status_code == 302
    assert response.location == '/recipes' # Assuming redirect to recipes_list_view

    with client.session_transaction() as sess:
        flashes = sess.get('_flashes', [])
    assert any('Successfully added 1 recipes' in message[1] for message in flashes)

    # Verify recipe in DB
    recipes = test_recipe_manager.get_all_recipes()
    assert len(recipes) == 1
    assert recipes[0]['name'] == "Test Bread"
    assert len(recipes[0]['ingredients']) == 1
    assert recipes[0]['ingredients'][0]['item_name'] == "Flour"
    # The route converts quantity to float before calling recipe_mngr.add_recipe
    assert recipes[0]['ingredients'][0]['quantity_required'] == 500.0

def test_upload_recipes_successful_with_all_fields(client):
    """Test uploading a recipe with all fields populated."""
    test_recipe_manager = main_app_module.recipe_mngr
    test_inventory_manager = main_app_module.manager

    header = [
        "Recipe Name", "Description", "Instructions",
        "Output Product Name", "Output Yield",
        "Ingredient 1 Name", "Ingredient 1 Quantity", "Ingredient 1 Notes",
        "Ingredient 2 Name", "Ingredient 2 Quantity", "Ingredient 2 Notes"
    ]
    data = [
        ["Deluxe Cake", "A yummy cake", "Mix and bake.", "Cake Mix", "1",
         "Flour", "250", "Sifted",
         "Sugar", "150", "Fine"]
    ]
    excel_bytes = create_excel_file_bytes(header, data)

    response = client.post('/upload_recipes_excel', data={'excel_file': (excel_bytes, 'deluxe_cake.xlsx')})

    assert response.status_code == 302
    assert response.location == '/recipes'
    with client.session_transaction() as sess:
        flashes = sess.get('_flashes', [])
    assert any('Successfully added 1 recipes' in message[1] for message in flashes)

    recipes = test_recipe_manager.get_all_recipes()
    assert len(recipes) == 1
    recipe = recipes[0]
    assert recipe['name'] == "Deluxe Cake"
    assert recipe['description'] == "A yummy cake"
    assert recipe['instructions'] == "Mix and bake."

    output_product = test_inventory_manager.get_product_by_name("Cake Mix")
    assert recipe['output_product_id'] == output_product['id']
    assert recipe['output_yield'] == 1.0

    assert len(recipe['ingredients']) == 2
    assert recipe['ingredients'][0]['item_name'] == "Flour"
    assert recipe['ingredients'][0]['quantity_required'] == 250.0
    assert recipe['ingredients'][0]['notes'] == "Sifted"
    assert recipe['ingredients'][1]['item_name'] == "Sugar"
    assert recipe['ingredients'][1]['quantity_required'] == 150.0
    assert recipe['ingredients'][1]['notes'] == "Fine"

def test_upload_recipes_missing_recipe_name(client):
    """Test a row with a missing Recipe Name."""
    test_recipe_manager = main_app_module.recipe_mngr
    header = ["Recipe Name", "Ingredient 1 Name", "Ingredient 1 Quantity"]
    data = [
        ["", "Flour", "100g"] # Missing recipe name
    ]
    excel_bytes = create_excel_file_bytes(header, data)
    response = client.post('/upload_recipes_excel', data={'excel_file': (excel_bytes, 'missing_name.xlsx')})

    assert response.status_code == 302
    assert response.location == '/recipes' # Still redirects to list view

    with client.session_transaction() as sess:
        flashes = sess.get('_flashes', [])
    # The current code skips rows with missing recipe names if other data is also missing,
    # or logs an error if other data is present.
    # If other data is present, it would be:
    # assert any("Recipe Name is missing but other data present. Skipped." in message[1] for message in flashes if message[0] == 'error_detail')
    # If the row is treated as blank and skipped silently:
    assert any("No new recipes were found or added" in message[1] for message in flashes if message[0] == 'info')

    recipes = test_recipe_manager.get_all_recipes()
    assert len(recipes) == 0


def test_upload_recipes_output_product_not_found(client):
    """Test recipe with an output product name that does not exist."""
    test_recipe_manager = main_app_module.recipe_mngr
    header = ["Recipe Name", "Output Product Name", "Output Yield"]
    data = [
        ["Mystery Cake", "NonExistent Cake", "1"]
    ]
    excel_bytes = create_excel_file_bytes(header, data)
    response = client.post('/upload_recipes_excel', data={'excel_file': (excel_bytes, 'bad_output.xlsx')})

    assert response.status_code == 302
    assert response.location == '/recipes'
    with client.session_transaction() as sess:
        flashes = sess.get('_flashes', [])
    assert any("Output Product Name 'NonExistent Cake' not found" in message[1] for message in flashes if message[0] == 'error_detail')

    recipes = test_recipe_manager.get_all_recipes()
    assert len(recipes) == 0

def test_upload_recipes_output_yield_missing(client):
    """Test recipe with Output Product Name but missing Output Yield."""
    test_recipe_manager = main_app_module.recipe_mngr
    header = ["Recipe Name", "Output Product Name", "Output Yield"]
    data = [
        ["Productive Recipe", "Cake Mix", ""] # Output Yield is blank
    ]
    excel_bytes = create_excel_file_bytes(header, data)
    response = client.post('/upload_recipes_excel', data={'excel_file': (excel_bytes, 'missing_yield.xlsx')})

    assert response.status_code == 302
    assert response.location == '/recipes'
    with client.session_transaction() as sess:
        flashes = sess.get('_flashes', [])
    assert any("Output Yield is required when Output Product Name is provided" in message[1] for message in flashes if message[0] == 'error_detail')

    recipes = test_recipe_manager.get_all_recipes()
    assert len(recipes) == 0


def test_upload_recipes_ingredient_name_not_found(client):
    """
    Test recipe with an ingredient name that does not exist.
    The current app.py code for upload_recipes_excel_view does NOT validate ingredient existence itself,
    it relies on recipe_mngr.add_recipe to handle it.
    Let's assume recipe_mngr.add_recipe would fail or skip this ingredient.
    The test should reflect how recipe_mngr.add_recipe actually behaves.
    If add_recipe fails the whole recipe, then no recipe is added.
    If add_recipe allows recipes with unknown ingredients (e.g. by creating them on the fly or ignoring them),
    this test needs to be adjusted.
    Based on `RecipeManager.add_recipe`, it tries to get product_id by name. If not found, it errors.
    """
    test_recipe_manager = main_app_module.recipe_mngr
    header = ["Recipe Name", "Ingredient 1 Name", "Ingredient 1 Quantity"]
    data = [
        ["Mystery Ingredient Bread", "Unobtainium Flour", "100"]
    ]
    excel_bytes = create_excel_file_bytes(header, data)
    response = client.post('/upload_recipes_excel', data={'excel_file': (excel_bytes, 'bad_ingredient.xlsx')})

    assert response.status_code == 302
    assert response.location == '/recipes'
    with client.session_transaction() as sess:
        flashes = sess.get('_flashes', [])
    # The error comes from recipe_mngr.add_recipe
    assert any("Failed to add recipe - Ingredient 'Unobtainium Flour' not found" in message[1] for message in flashes if message[0] == 'error_detail')

    recipes = test_recipe_manager.get_all_recipes()
    assert len(recipes) == 0

def test_upload_recipes_ingredient_quantity_missing(client):
    """Test recipe with an ingredient name but missing quantity."""
    test_recipe_manager = main_app_module.recipe_mngr
    header = ["Recipe Name", "Ingredient 1 Name", "Ingredient 1 Quantity"]
    data = [
        ["Flour Only Bread", "Flour", ""] # Quantity is blank
    ]
    excel_bytes = create_excel_file_bytes(header, data)
    response = client.post('/upload_recipes_excel', data={'excel_file': (excel_bytes, 'missing_qty.xlsx')})

    assert response.status_code == 302
    assert response.location == '/recipes'
    with client.session_transaction() as sess:
        flashes = sess.get('_flashes', [])
    assert any("Ingredient 1 Quantity is required for 'Flour'" in message[1] for message in flashes if message[0] == 'error_detail')

    recipes = test_recipe_manager.get_all_recipes()
    assert len(recipes) == 0

def test_upload_recipes_multiple_recipes_mixed_validity(client):
    """Test uploading multiple recipes, some valid, some not."""
    test_recipe_manager = main_app_module.recipe_mngr
    header = ["Recipe Name", "Ingredient 1 Name", "Ingredient 1 Quantity", "Description"]
    data = [
        ["Valid Bread", "Flour", "500", "Good bread"],
        ["Invalid Bread Bad Qty", "Sugar", "", "Missing Qty"], # Invalid: Missing quantity
        ["Valid Cookies", "Chocolate Chips", "100", "Yummy cookies"],
        ["Invalid Bread Bad Ing", "NonExistentItem", "10", "Bad Ingredient"] # Invalid: Ingredient not found
    ]
    excel_bytes = create_excel_file_bytes(header, data)
    response = client.post('/upload_recipes_excel', data={'excel_file': (excel_bytes, 'mixed.xlsx')})

    assert response.status_code == 302
    assert response.location == '/recipes'

    with client.session_transaction() as sess:
        flashes = sess.get('_flashes', [])

    # Check overall success message for the valid ones
    assert any("Successfully added 2 recipes" in message[1] for message in flashes if message[0] == 'success')

    # Check error messages for invalid ones
    assert any("Ingredient 1 Quantity is required for 'Sugar'" in message[1] for message in flashes if message[0] == 'error_detail')
    assert any("Failed to add recipe - Ingredient 'NonExistentItem' not found" in message[1] for message in flashes if message[0] == 'error_detail')

    recipes = test_recipe_manager.get_all_recipes()
    assert len(recipes) == 2
    recipe_names = {r['name'] for r in recipes}
    assert "Valid Bread" in recipe_names
    assert "Valid Cookies" in recipe_names
    assert "Invalid Bread Bad Qty" not in recipe_names
    assert "Invalid Bread Bad Ing" not in recipe_names

def test_upload_recipes_excel_missing_mandatory_header(client):
    """Test uploading an Excel file missing a mandatory header like 'Recipe Name'."""
    # Here, 'Recipe Name' is missing.
    header = ["Description", "Ingredient 1 Name", "Ingredient 1 Quantity"]
    data = [
        ["Some desc", "Flour", "100g"]
    ]
    excel_bytes = create_excel_file_bytes(header, data)
    response = client.post('/upload_recipes_excel', data={'excel_file': (excel_bytes, 'missing_header.xlsx')})

    assert response.status_code == 302 # Redirects back to upload page
    assert response.location == '/upload_recipes_excel'

    with client.session_transaction() as sess:
        flashes = sess.get('_flashes', [])
    assert any("Missing required column in Excel: 'Recipe Name'" in message[1] for message in flashes if message[0] == 'error')

def test_upload_recipes_excel_empty_file(client):
    """Test uploading an empty Excel file (only headers, no data rows)."""
    test_recipe_manager = main_app_module.recipe_mngr
    header = ["Recipe Name", "Ingredient 1 Name", "Ingredient 1 Quantity"]
    data = [] # No data rows
    excel_bytes = create_excel_file_bytes(header, data)

    response = client.post('/upload_recipes_excel', data={'excel_file': (excel_bytes, 'empty_data.xlsx')})

    assert response.status_code == 302
    assert response.location == '/recipes'

    with client.session_transaction() as sess:
        flashes = sess.get('_flashes', [])
    assert any("No new recipes were found or added from the file." in message[1] for message in flashes if message[0] == 'info')

    recipes = test_recipe_manager.get_all_recipes()
    assert len(recipes) == 0

def test_upload_recipes_with_optional_fields_blank(client):
    """Test a recipe where optional fields like description, instructions, notes are blank."""
    test_recipe_manager = main_app_module.recipe_mngr
    header = [
        "Recipe Name", "Description", "Instructions",
        "Output Product Name", "Output Yield",
        "Ingredient 1 Name", "Ingredient 1 Quantity", "Ingredient 1 Notes"
    ]
    # Description, Instructions, Output Product Name, Output Yield, Ingredient 1 Notes are blank
    data = [
        ["Minimal Recipe", "", "", "", "", "Flour", "100", ""]
    ]
    excel_bytes = create_excel_file_bytes(header, data)
    response = client.post('/upload_recipes_excel', data={'excel_file': (excel_bytes, 'minimal.xlsx')})

    assert response.status_code == 302
    assert response.location == '/recipes'
    with client.session_transaction() as sess:
        flashes = sess.get('_flashes', [])
    assert any("Successfully added 1 recipes" in message[1] for message in flashes if message[0] == 'success')

    recipes = test_recipe_manager.get_all_recipes()
    assert len(recipes) == 1
    recipe = recipes[0]
    assert recipe['name'] == "Minimal Recipe"
    assert recipe['description'] == ""
    assert recipe['instructions'] == ""
    assert recipe['output_product_id'] is None
    assert recipe['output_yield'] is None
    assert len(recipe['ingredients']) == 1
    assert recipe['ingredients'][0]['item_name'] == "Flour"
    assert recipe['ingredients'][0]['quantity_required'] == 100.0
    assert recipe['ingredients'][0]['notes'] == ""

def test_upload_recipes_numeric_conversion_errors(client):
    """Test various numeric conversion errors for yield and ingredient quantity."""
    test_recipe_manager = main_app_module.recipe_mngr
    header = ["Recipe Name", "Output Product Name", "Output Yield", "Ingredient 1 Name", "Ingredient 1 Quantity"]
    data = [
        ["Bad Yield", "Cake Mix", "abc", "Flour", "100"],      # Non-numeric yield
        ["Negative Yield", "Cake Mix", "-5", "Flour", "100"], # Negative yield
        ["Bad Ing Qty", "Cake Mix", "1", "Flour", "xyz"],    # Non-numeric ingredient quantity
        ["Negative Ing Qty", "Cake Mix", "1", "Flour", "-2"], # Negative ingredient quantity
    ]
    excel_bytes = create_excel_file_bytes(header, data)
    response = client.post('/upload_recipes_excel', data={'excel_file': (excel_bytes, 'numeric_errors.xlsx')})

    assert response.status_code == 302
    assert response.location == '/recipes'
    with client.session_transaction() as sess:
        flashes = sess.get('_flashes', [])

    assert any("Invalid Output Yield 'abc'" in message[1] for message in flashes if message[0] == 'error_detail')
    assert any("Output Yield must be a positive number" in message[1] for message in flashes if message[0] == 'error_detail') # For "-5"
    assert any("Invalid Ingredient 1 Quantity 'xyz'" in message[1] for message in flashes if message[0] == 'error_detail')
    assert any("Ingredient 1 Quantity for 'Flour' must be positive" in message[1] for message in flashes if message[0] == 'error_detail') # For "-2"

    # Should also have a general error count message
    assert any("4 rows/recipes had errors" in message[1] for message in flashes if message[0] == 'error')

    recipes = test_recipe_manager.get_all_recipes()
    assert len(recipes) == 0

def test_upload_recipes_max_ingredients(client):
    """Test uploading a recipe with the maximum number of ingredients (15)."""
    test_recipe_manager = main_app_module.recipe_mngr
    header = ["Recipe Name"]
    ingredients_data = []
    for i in range(1, 16):
        header.extend([f"Ingredient {i} Name", f"Ingredient {i} Quantity", f"Ingredient {i} Notes"])
        # Use existing products for ingredients to ensure validity
        product_name = ['Flour', 'Sugar', 'Eggs', 'Yeast', 'Butter', 'Milk', 'Vanilla Extract',
                        'Chocolate Chips', 'Flour', 'Sugar', 'Eggs', 'Yeast', 'Butter', 'Milk', 'Vanilla Extract'][i-1]
        ingredients_data.extend([product_name, str(i * 10), f"Note for ing {i}"])

    data_row = ["Max Ingredient Recipe"] + ingredients_data
    excel_bytes = create_excel_file_bytes(header, [data_row])

    response = client.post('/upload_recipes_excel', data={'excel_file': (excel_bytes, 'max_ingredients.xlsx')})

    assert response.status_code == 302
    assert response.location == '/recipes'
    with client.session_transaction() as sess:
        flashes = sess.get('_flashes', [])
    assert any("Successfully added 1 recipes" in message[1] for message in flashes if message[0] == 'success')

    recipes = test_recipe_manager.get_all_recipes()
    assert len(recipes) == 1
    assert recipes[0]['name'] == "Max Ingredient Recipe"
    assert len(recipes[0]['ingredients']) == 15
    for i in range(15):
        assert recipes[0]['ingredients'][i]['quantity_required'] == float((i + 1) * 10)
        assert recipes[0]['ingredients'][i]['notes'] == f"Note for ing {i+1}"

def test_upload_recipes_yield_without_output_product_warning(client):
    """Test that a warning is flashed if Output Yield is provided without Output Product Name."""
    test_recipe_manager = main_app_module.recipe_mngr
    header = ["Recipe Name", "Output Product Name", "Output Yield", "Ingredient 1 Name", "Ingredient 1 Quantity"]
    data = [
        ["YieldNoProd", "", "5.0", "Flour", "100"] # Output Product Name is blank, Yield has value
    ]
    excel_bytes = create_excel_file_bytes(header, data)
    response = client.post('/upload_recipes_excel', data={'excel_file': (excel_bytes, 'yield_no_prod.xlsx')})

    assert response.status_code == 302
    assert response.location == '/recipes'
    with client.session_transaction() as sess:
        flashes = sess.get('_flashes', [])

    assert any("Output Yield '5.0' provided without an Output Product Name. Yield will be ignored." in message[1] for message in flashes if message[0] == 'warning_detail')
    assert any("Successfully added 1 recipes" in message[1] for message in flashes if message[0] == 'success') # Recipe should still be added

    recipes = test_recipe_manager.get_all_recipes()
    assert len(recipes) == 1
    assert recipes[0]['name'] == "YieldNoProd"
    assert recipes[0]['output_product_id'] is None
    assert recipes[0]['output_yield'] is None # Yield ignored

def test_upload_recipes_ingredient_quantity_without_name_error(client):
    """Test that an error is flashed if Ingredient Quantity is provided without Ingredient Name."""
    test_recipe_manager = main_app_module.recipe_mngr
    header = ["Recipe Name", "Ingredient 1 Name", "Ingredient 1 Quantity"]
    data = [
        ["QtyNoName", "", "100"] # Ingredient Name is blank, Quantity has value
    ]
    excel_bytes = create_excel_file_bytes(header, data)
    response = client.post('/upload_recipes_excel', data={'excel_file': (excel_bytes, 'qty_no_name.xlsx')})

    assert response.status_code == 302
    assert response.location == '/recipes'
    with client.session_transaction() as sess:
        flashes = sess.get('_flashes', [])

    assert any("Ingredient 1 Name is missing but Quantity '100' was provided." in message[1] for message in flashes if message[0] == 'error_detail')

    recipes = test_recipe_manager.get_all_recipes()
    assert len(recipes) == 0 # Recipe should not be added due to this error
