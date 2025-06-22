import sys
import os
from datetime import date

# Add the parent directory to sys.path to allow imports from Food_manager
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

try:
    from Food_manager import InventoryManager
except ImportError:
    print("Error: Food_manager.py not found or not in Python path. Ensure it's in the same directory or sys.path is correctly set.")
    sys.exit(1)

def run_test():
    print("Starting test_add_item_excel_scenario.py...")

    # Use an in-memory database for this test for isolation
    manager = InventoryManager(db_filepath=":memory:")
    print("InventoryManager initialized with in-memory DB.")

    # 1. Ensure a test category exists
    test_category_name = "Test Category Excel Upload"
    category_id = None

    existing_cat = manager.get_category_by_name(test_category_name)
    if existing_cat:
        category_id = existing_cat['id']
        print(f"Category '{test_category_name}' already exists with ID: {category_id}.")
    else:
        add_cat_result = manager.add_category(test_category_name)
        if add_cat_result.get("success"):
            category_id = add_cat_result.get("category_id")
            print(f"Category '{test_category_name}' created with ID: {category_id}.")
        else:
            print(f"Failed to create category '{test_category_name}': {add_cat_result.get('message')}")
            manager.close_connection()
            return False

    assert category_id is not None, "Failed to get or create category ID."

    # 2. First call to add_item_to_list (simulating new product, new subcategory)
    print("\n--- First call to add_item_to_list ---")
    item_details_first_call = {
        "name": "Test Product New SubCat",
        "quantity_str": "1",
        "purchase_date_str": "2024-01-01",
        "expiry_days": 30,
        "category": test_category_name,  # Name of the category
        "subcategory": "Test New SubCategory", # New subcategory
        "unit_of_measure": "pcs",
        "par_level": 1.0,
        "max_holding_amount": 5.0,
        "purchase_location": "Test Store",
        "confirmed_action": None,
        "temp_category_id": None
    }

    first_call_result = manager.add_item_to_list(**item_details_first_call)
    print(f"First call result: {first_call_result}")

    assert first_call_result.get("action_required") == "confirm_new_subcategory", \
        f"AssertionError: Expected action_required='confirm_new_subcategory', got '{first_call_result.get('action_required')}'"
    print("Assertion: action_required='confirm_new_subcategory' - PASSED")

    assert first_call_result.get("confirmation_details", {}).get("category_id") == category_id, \
        f"AssertionError: Expected category_id in confirmation_details to be {category_id}, got '{first_call_result.get('confirmation_details', {}).get('category_id')}'"
    print(f"Assertion: confirmation_details.category_id == {category_id} - PASSED")

    product_data_from_first_call = first_call_result.get("product_data")
    temp_category_id_for_second_call = first_call_result.get("confirmation_details", {}).get("category_id")

    assert product_data_from_first_call is not None, "product_data not found in first call result"
    assert temp_category_id_for_second_call is not None, "temp_category_id not found in first call result confirmation_details"

    # 3. Second call to add_item_to_list (simulating user confirmation)
    print("\n--- Second call to add_item_to_list ---")

    # Prepare arguments for the second call by merging product_data with confirmed_action and temp_category_id
    # Ensure all expected keys from product_data are present.
    # The product_data should contain all original fields like name, quantity_str, etc.
    second_call_args = {
        **product_data_from_first_call, # Spread the dictionary
        "confirmed_action": "confirm_new_subcategory",
        "temp_category_id": temp_category_id_for_second_call
    }

    # Ensure all required keys are present, if not, take from item_details_first_call as a fallback
    # This is because product_data_for_confirmation might not contain all original fields
    # if the function exited early before populating it fully.
    # However, based on current Food_manager.py, product_data_for_confirmation IS populated.
    required_keys = ["name", "quantity_str", "purchase_date_str", "expiry_days", "category", "subcategory", "unit_of_measure", "par_level", "max_holding_amount", "purchase_location"]
    for key in required_keys:
        if key not in second_call_args:
             print(f"Warning: Key '{key}' not in product_data_from_first_call, using from initial item_details.")
             second_call_args[key] = item_details_first_call[key]


    second_call_result = manager.add_item_to_list(**second_call_args)
    print(f"Second call result: {second_call_result}")

    assert second_call_result.get("success") is True, \
        f"AssertionError: Expected success=True, got '{second_call_result.get('success')}' with message: {second_call_result.get('message')}"
    print("Assertion: success=True - PASSED")

    assert second_call_result.get("action_required") is None or not second_call_result.get("action_required"), \
        f"AssertionError: Expected action_required to be None or empty, got '{second_call_result.get('action_required')}'"
    print("Assertion: action_required is None or empty - PASSED")

    created_item_id = second_call_result.get("item_id")
    created_product_id = second_call_result.get("product_id")

    assert created_item_id is not None, "AssertionError: item_id is None in second call result"
    print("Assertion: item_id is not None - PASSED")
    assert created_product_id is not None, "AssertionError: product_id is None in second call result"
    print("Assertion: product_id is not None - PASSED")

    # 4. Verification
    print("\n--- Verification ---")
    # Verify subcategory
    retrieved_subcategory = manager.get_subcategory_by_name_and_category_id("Test New SubCategory", category_id)
    assert retrieved_subcategory is not None, "Verification FAILED: Subcategory 'Test New SubCategory' not found."
    assert retrieved_subcategory['name'] == "Test New SubCategory", "Verification FAILED: Subcategory name mismatch."
    print(f"Verification PASSED: Subcategory 'Test New SubCategory' (ID: {retrieved_subcategory['id']}) found under category ID {category_id}.")
    retrieved_subcategory_id = retrieved_subcategory['id']

    # Verify product
    retrieved_product = manager.get_product(created_product_id)
    assert retrieved_product is not None, f"Verification FAILED: Product with ID {created_product_id} not found."
    assert retrieved_product['name'] == "Test Product New SubCat", "Verification FAILED: Product name mismatch."
    assert retrieved_product['category_id'] == category_id, "Verification FAILED: Product category_id mismatch."
    assert retrieved_product['subcategory_id'] == retrieved_subcategory_id, "Verification FAILED: Product subcategory_id mismatch."
    print(f"Verification PASSED: Product 'Test Product New SubCat' (ID: {created_product_id}) found with correct category and subcategory links.")

    # Verify inventory item
    # Need to fetch inventory items for the product and check if one matches.
    # get_current_inventory can be too broad, get_inventory_batches_for_product is better.
    inventory_batches = manager.get_inventory_batches_for_product(created_product_id, limit=5) # Limit just in case
    found_inventory_item = False
    for batch in inventory_batches:
        if batch['id'] == created_item_id: # Check if the created item_id is in the list of batches for this product
            assert batch['original_quantity_string'] == "1", f"Verification FAILED: Inventory item quantity mismatch. Expected '1', got '{batch['original_quantity_string']}'"
            # Can add more checks like purchase_date if needed
            found_inventory_item = True
            break

    assert found_inventory_item, f"Verification FAILED: Inventory item with ID {created_item_id} for product ID {created_product_id} not found."
    print(f"Verification PASSED: Inventory item for 'Test Product New SubCat' (Batch ID: {created_item_id}) found with correct quantity.")

    print("\nAll tests and assertions PASSED.")
    return True

if __name__ == "__main__":
    success = False
    manager_instance = None # To ensure close_connection can be called
    try:
        # Create a dummy manager instance just for the finally block,
        # the real one is inside run_test()
        # This is a bit of a hack; ideally, the manager from run_test() would be accessible here.
        # For this script structure, it's simpler to just create one for closing if an error occurs early.
        if 'InventoryManager' in globals(): # Check if import was successful
             manager_instance = InventoryManager(db_filepath=":memory:") # Temporary for cleanup
        success = run_test()
    except AssertionError as e:
        print(f"\nTEST FAILED: {e}")
        success = False
    except Exception as e:
        print(f"\nAN UNEXPECTED ERROR OCCURRED: {e}")
        import traceback
        traceback.print_exc()
        success = False
    finally:
        if manager_instance:
            manager_instance.close_connection()
            print("Closed temporary DB connection in finally block.")
        # Note: The primary manager connection is closed within run_test() or if it fails there.
        # This structure might lead to double-closing if run_test() fails after its own manager init.
        # However, for sqlite in-memory, closing multiple times is generally safe.

        if success:
            print("Script completed successfully.")
            sys.exit(0)
        else:
            print("Script failed.")
            sys.exit(1)
