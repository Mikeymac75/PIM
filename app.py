from flask import Flask, render_template, request, redirect, url_for, flash
from Food_manager import InventoryManager
from recipe_manager import RecipeManager
from datetime import date, datetime, timedelta # Added timedelta
import openpyxl # For reading Excel files
import os # For accessing environment variables

app = Flask(__name__)
# Configure secret key: Use an environment variable for production, with a fallback for development.
# IMPORTANT: For production, set the FLASK_SECRET_KEY environment variable to a strong, random value.
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'a_default_fallback_secret_key')
# Define allowed extensions for file upload
ALLOWED_EXTENSIONS = {'xlsx'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Define the shared database file path
# Use an environment variable for the database path, with a default for development.
# IMPORTANT: For production or specific setups, set DATABASE_FILE_PATH environment variable.
DATABASE_FILE = os.environ.get('DATABASE_FILE_PATH', 'food_app.db')

# Instantiate Managers globally, using the shared database file
# The manager classes themselves will handle DB initialization (table creation IF NOT EXISTS)
manager = InventoryManager(db_filepath=DATABASE_FILE)
recipe_mngr = RecipeManager(db_filepath=DATABASE_FILE)

# --- Helper Functions ---
def _get_unique_item_names(include_historical=False):
    """
    Helper to get sorted unique item names from the products table.
    The `include_historical` parameter is less relevant now as we fetch from a definitive product list.
    """
    # manager.get_all_products() returns a list of product dictionaries
    all_products = manager.get_all_products()
    # Assuming each product dict has a 'name' key
    unique_names = set(product['name'] for product in all_products if 'name' in product)
    return sorted(list(unique_names))

# --- Flask Routes ---
@app.route('/')
def home():
    return render_template('home.html')

@app.route('/inventory/current')
def current_inventory_view():
    inventory_items_raw = manager.get_current_inventory()
    processed_inventory_items = []
    for item_dict in inventory_items_raw: # manager.get_current_inventory() returns list of dicts
        # Ensure item_dict is a mutable dictionary if it's not already (e.g. if it was a sqlite3.Row)
        item_processed = dict(item_dict) 
        
        # Parse current quantity string to a number for comparison
        # The _parse_quantity_string method is in InventoryManager
        numeric_quantity = manager._parse_quantity_string(item_processed['quantity'])
        
        par_level = item_processed.get('par_level', 0.0) # Default to 0.0 if not present
        if par_level is None: # Handle cases where par_level might be None from DB (though schema defaults to 0)
            par_level = 0.0
        else:
            par_level = float(par_level)

        item_processed['is_below_par'] = (numeric_quantity < par_level and par_level > 0)
        processed_inventory_items.append(item_processed)

    today = date.today() # Get current date
    return render_template('current_inventory.html', items=processed_inventory_items, today=today, timedelta=timedelta)

@app.route('/inventory/historical')
def historical_inventory_view():
    historical_items = manager.get_historical_inventory()
    return render_template('historical_inventory.html', items=historical_items)

@app.route('/inventory/consume', methods=['GET', 'POST'])
def consume_item_view():
    item_names = _get_unique_item_names() # Use new helper, default is include_historical=False

    if request.method == 'POST':
        item_name = request.form.get('item_name')
        quantity_consumed_str = request.form.get('quantity_consumed')

        errors = []
        if not item_name:
            errors.append("Item name is required.")
        
        numeric_quantity_consumed = None # Initialize to None
        if not quantity_consumed_str:
            errors.append("Quantity to consume is required.")
        else:
            try:
                numeric_quantity_consumed = float(quantity_consumed_str) # Allow for float quantities
                if numeric_quantity_consumed <= 0:
                    errors.append("Quantity to consume must be a positive number (greater than zero).")
            except ValueError:
                errors.append("Quantity to consume must be a valid number.")

        if errors:
            for error in errors:
                flash(error, 'error')
            return render_template('consume_item.html', item_names=item_names, form_data=request.form)

        # If validation passes
        try:
            # consume_item in InventoryManager returns a dict like:
            # {"success": True/False, "message": "details..."}
            result = manager.consume_item(item_name, numeric_quantity_consumed)
            
            if result.get("success"):
                flash(result.get("message", f"Consumption of '{item_name}' processed."), 'success')
                # Optionally, show details if any:
                # for detail_msg in result.get("details", []):
                # flash(detail_msg, 'info')
            else:
                flash(result.get("message", f"Could not consume '{item_name}'."), 'error')
            
            # Redirect to current inventory to see changes, or back to consume page
            return redirect(url_for('current_inventory_view')) 
            # Or: return redirect(url_for('consume_item_view'))
            
        except Exception as e:
            flash(f"An unexpected error occurred while consuming item: {e}", 'error')
            return render_template('consume_item.html', item_names=item_names, form_data=request.form)

    # For GET request
    return render_template('consume_item.html', item_names=item_names, form_data={})

@app.route('/inventory/upload_excel', methods=['GET', 'POST'])
def upload_excel_view():
    if request.method == 'POST':
        if 'excel_file' not in request.files:
            flash('No file part in the request.', 'error')
            return redirect(request.url)
        
        file = request.files['excel_file']
        if file.filename == '':
            flash('No selected file.', 'error')
            return redirect(request.url)

        if file and allowed_file(file.filename):
            try:
                workbook = openpyxl.load_workbook(file)
                sheet = workbook.active # Get the first active sheet

                # Determine header row and map columns
                # Assuming first row is header
                header_row_values = [cell.value for cell in sheet[1]]
                # Create a mapping from lowercased header name to its column index
                header_map = {str(h).strip().lower(): idx for idx, h in enumerate(header_row_values) if h}

                required_headers = ['name', 'quantity', 'purchase date', 'expiry days']
                missing_headers = [req_h for req_h in required_headers if req_h not in header_map]
                if missing_headers:
                    flash(f"Missing required columns in Excel: {', '.join(missing_headers)}. Please check headers.", 'error')
                    return redirect(request.url)

                name_col = header_map['name']
                qty_col = header_map['quantity']
                pdate_col = header_map['purchase date']
                expdays_col = header_map['expiry days']
                
                # Optional columns, get their index if they exist, otherwise None
                category_col = header_map.get('category') 
                subcategory_col = header_map.get('subcategory')
                par_level_col = header_map.get('par level')
                max_holding_col = header_map.get('max holding amount')
                purchase_location_col = header_map.get('purchase location') # New
                
                items_added_count = 0
                error_messages = []

                for row_idx, row in enumerate(sheet.iter_rows(min_row=2, values_only=True), start=2):
                    # Stop if first cell of row is empty (common way to detect end of data)
                    # Ensure the row has enough columns to prevent IndexError if a row is shorter than header
                    if len(row) <= max(name_col, qty_col, pdate_col, expdays_col):
                        error_messages.append(f"Row {row_idx}: Skipped due to insufficient columns.")
                        continue

                    name = str(row[name_col]).strip() if row[name_col] is not None else None
                    quantity = str(row[qty_col]).strip() if row[qty_col] is not None else None
                    purchase_date_val = row[pdate_col] # Handled by type checks later
                    expiry_days_val = row[expdays_col] # Handled by type checks later

                    # Extract optional fields, defaulting to None if column doesn't exist or cell is empty
                    category = str(row[category_col]).strip() if category_col is not None and row[category_col] is not None else None
                    subcategory = str(row[subcategory_col]).strip() if subcategory_col is not None and row[subcategory_col] is not None else None
                    par_level_val = row[par_level_col] if par_level_col is not None and row[par_level_col] is not None else "0" # Default to "0" if cell empty/col missing
                    max_holding_val = row[max_holding_col] if max_holding_col is not None and row[max_holding_col] is not None else "0" # Default to "0"
                    purchase_location_val = str(row[purchase_location_col]).strip() if purchase_location_col is not None and row[purchase_location_col] is not None else None # New

                    # Skip row if essential 'name' field is missing
                    if not name:
                        # Check if any other relevant cell in the row has data to avoid skipping genuinely sparse rows
                        # vs. completely blank rows often found at the end of sheets.
                        other_cells_have_data = any(
                            row[col_idx] for col_idx in [qty_col, pdate_col, expdays_col, 
                                                         category_col, subcategory_col, par_level_col, max_holding_col, purchase_location_col]
                            if col_idx is not None and len(row) > col_idx and row[col_idx] is not None
                        )
                        if other_cells_have_data:
                            error_messages.append(f"Row {row_idx}: Name is missing but other data present. Skipped.")
                        # If all relevant cells are effectively empty, it's likely an empty row, so just continue
                        elif not any(row[col_idx] for col_idx in [name_col, qty_col, pdate_col, expdays_col, 
                                                                category_col, subcategory_col, par_level_col, max_holding_col, purchase_location_col]
                                     if col_idx is not None and len(row) > col_idx and row[col_idx] is not None):
                            continue
                        else: # Name missing, other fields might be empty too, but log it
                             error_messages.append(f"Row {row_idx}: Name is missing. Skipped.")
                        continue
                    
                    row_errors = []
                    # Validate required fields
                    if quantity is None or quantity == "": row_errors.append("Quantity is missing.") # Quantity is text, can be "0"
                    if purchase_date_val is None: row_errors.append("Purchase Date is missing.")
                    if expiry_days_val is None: row_errors.append("Expiry Days is missing.")

                    purchase_date_str = None
                    if isinstance(purchase_date_val, datetime):
                        purchase_date_str = purchase_date_val.strftime('%Y-%m-%d')
                    elif isinstance(purchase_date_val, str):
                        try:
                            date.fromisoformat(purchase_date_val) # Validate format
                            purchase_date_str = purchase_date_val
                        except ValueError:
                            row_errors.append(f"Invalid Purchase Date format '{purchase_date_val}'. Use YYYY-MM-DD.")
                    elif purchase_date_val is not None: 
                         row_errors.append(f"Purchase Date '{purchase_date_val}' is not in YYYY-MM-DD text or Excel date format.")

                    expiry_days_int = None # Will hold successfully parsed int
                    if isinstance(expiry_days_val, (int, float)):
                        expiry_days_int = int(expiry_days_val)
                        if expiry_days_int < 0:
                            row_errors.append("Expiry Days must be a non-negative number.")
                            expiry_days_int = None # Reset if invalid
                    elif isinstance(expiry_days_val, str) and expiry_days_val.strip().lstrip('-').isdigit(): # Handle numbers as strings, allow negative for initial check
                        expiry_days_int = int(expiry_days_val.strip())
                        if expiry_days_int < 0:
                             row_errors.append("Expiry Days must be a non-negative number.")
                             expiry_days_int = None # Reset if invalid
                    elif expiry_days_val is not None: # If not None and not int/float/parsable string
                        row_errors.append(f"Expiry Days '{expiry_days_val}' must be a valid whole number.")

                    # Validate optional numeric fields: par_level, max_holding_amount
                    par_level_float = None
                    try:
                        par_level_val_cleaned = str(par_level_val).strip() if par_level_val is not None else "0"
                        par_level_float = float(par_level_val_cleaned)
                        if par_level_float < 0:
                            row_errors.append("Par Level must be a non-negative number.")
                            par_level_float = None # Reset if invalid
                    except (ValueError, TypeError):
                        row_errors.append(f"Invalid Par Level '{par_level_val}'. Must be a valid number.")

                    max_holding_float = None
                    try:
                        max_holding_val_cleaned = str(max_holding_val).strip() if max_holding_val is not None else "0"
                        max_holding_float = float(max_holding_val_cleaned)
                        if max_holding_float < 0:
                            row_errors.append("Max Holding Amount must be a non-negative number.")
                            max_holding_float = None # Reset if invalid
                    except (ValueError, TypeError):
                        row_errors.append(f"Invalid Max Holding Amount '{max_holding_val}'. Must be a valid number.")

                    # Validate purchase_location_val (optional, but if provided, must be one of the allowed values)
                    purchase_location_to_pass = None
                    if purchase_location_val:
                        allowed_locations = ['Sobeys', 'Costco']
                        if purchase_location_val in allowed_locations:
                            purchase_location_to_pass = purchase_location_val
                        else:
                            row_errors.append(f"Invalid Purchase Location '{purchase_location_val}'. If provided, must be one of: {', '.join(allowed_locations)}.")
                    
                    if row_errors: 
                        error_messages.append(f"Row {row_idx} ('{name}'): " + "; ".join(row_errors))
                        continue 

                    # If all validations pass for this row, attempt to add to inventory
                    try:
                        manager.add_item_to_list(
                            name=str(name), 
                            quantity_str=str(quantity), 
                            purchase_date_str=purchase_date_str, 
                            expiry_days=expiry_days_int,
                            category=category if category else None, # Pass None if empty string
                            subcategory=subcategory if subcategory else None,
                            par_level=par_level_float,
                            max_holding_amount=max_holding_float,
                            purchase_location=purchase_location_to_pass # New
                        )
                        items_added_count += 1
                    except Exception as e: # Catch errors from manager.add_item_to_list
                        error_messages.append(f"Row {row_idx} ('{name}'): Error adding to inventory - {str(e)}")
                
                # Flash summary
                if items_added_count > 0:
                    flash(f"Successfully added {items_added_count} items from the Excel file.", 'success')
                if error_messages:
                    flash(f"{len(error_messages)} rows had errors. See details below:", 'error')
                    for err_msg in error_messages[:5]: # Show first 5 errors
                        flash(err_msg, 'detail_error') # Use a different category if you want specific styling
                if items_added_count == 0 and not error_messages:
                     flash("No items were found or added from the file. The file might be empty or data starts after row 2.", 'info')

                return redirect(url_for('current_inventory_view'))

            except Exception as e:
                flash(f"An error occurred while processing the Excel file: {e}", 'error')
                return redirect(request.url)
        else:
            flash('Invalid file type. Please upload an .xlsx file.', 'error')
            return redirect(request.url)

    return render_template('upload_excel.html')

@app.route('/recipes/add', methods=['GET', 'POST'])
def add_recipe_view():
    form_data_to_repopulate = {} # For GET or if POST fails and re-renders
    if request.method == 'POST':
        recipe_name = request.form.get('recipe_name', '').strip()
        description = request.form.get('description', '').strip()
        
        # Process ingredients
        ingredients = []
        form_errors = [] # Collect form validation errors before calling manager
        for i in range(1, 11): # Max 10 ingredients from form (updated from 6 to 11 for range)
            ing_name = request.form.get(f'ingredient_{i}_name', '').strip()
            ing_qty_str = request.form.get(f'ingredient_{i}_quantity', '').strip()

            if ing_name and ing_qty_str: # Process if both name and quantity are provided
                try:
                    ing_qty = float(ing_qty_str)
                    if ing_qty <= 0:
                        form_errors.append(f"Ingredient '{ing_name}': Quantity must be a positive number (greater than zero).")
                    else:
                        ingredients.append({'item_name': ing_name, 'quantity_required': ing_qty})
                except ValueError:
                    form_errors.append(f"Ingredient '{ing_name}': Invalid quantity '{ing_qty_str}'. Must be a valid number.")
            elif ing_name and not ing_qty_str: # Name provided but not quantity
                form_errors.append(f"Ingredient '{ing_name}': Quantity is missing.")
            # If only quantity or neither is provided, it's skipped (considered an empty ingredient slot)
        
        if not recipe_name:
            form_errors.append("Recipe name is required.")
        
        # Optional: Enforce at least one ingredient if desired
        # if not ingredients and any(request.form.get(f'ingredient_{i}_name') for i in range(1,6)):
        #      form_errors.append("At least one valid ingredient (name and positive quantity) is required if ingredients are attempted.")

        if form_errors:
            for error in form_errors:
                flash(error, 'error')
            form_data_to_repopulate = request.form # Repopulate with all original attempt
            return render_template('add_recipe.html', form_data=form_data_to_repopulate)

        # Data for RecipeManager (already validated for basic format by above logic)
        recipe_data = {
            "name": recipe_name,
            "description": description,
            "ingredients": ingredients
        }
        
        result = recipe_mngr.add_recipe(recipe_data)
        
        if result.get("success"):
            flash(result['message'], 'success')
            return redirect(url_for('add_recipe_view')) # Redirect back to add form (or future list page)
        else:
            flash(result['message'], 'error')
            # Repopulate form with the data that was attempted
            form_data_to_repopulate = {
                'recipe_name': recipe_name,
                'description': description
            }
            for i, ing in enumerate(ingredients, 1):
                form_data_to_repopulate[f'ingredient_{i}_name'] = ing['item_name']
                form_data_to_repopulate[f'ingredient_{i}_quantity'] = ing['quantity_required']
            # Also add back any originally submitted (but potentially incomplete) ingredient fields
            for i in range(1, 11): # Ensure all 10 potential fields are repopulated
                if not form_data_to_repopulate.get(f'ingredient_{i}_name'):
                     form_data_to_repopulate[f'ingredient_{i}_name'] = request.form.get(f'ingredient_{i}_name', '')
                if not form_data_to_repopulate.get(f'ingredient_{i}_quantity'):
                     form_data_to_repopulate[f'ingredient_{i}_quantity'] = request.form.get(f'ingredient_{i}_quantity', '')
            
            return render_template('add_recipe.html', form_data=form_data_to_repopulate)

    return render_template('add_recipe.html', form_data=form_data_to_repopulate)

@app.route('/recipes')
def recipes_list_view():
    all_recipes = recipe_mngr.get_all_recipes()
    # Sort recipes by name for consistent display order
    sorted_recipes = sorted(all_recipes, key=lambda r: r['name'].lower())
    return render_template('recipes_list.html', recipes=sorted_recipes)

@app.route('/recipes/<path:recipe_name>') # Using path for flexibility with names
def recipe_detail_view(recipe_name):
    recipe = recipe_mngr.get_recipe_by_name(recipe_name)

    if not recipe:
        flash(f"Recipe '{recipe_name}' not found.", 'error')
        return redirect(url_for('recipes_list_view'))

    ingredients_status = []
    recipe_makeable = True # Assume true until an insufficient ingredient is found

    if recipe.get('ingredients'):
        for ing in recipe['ingredients']:
            item_name = ing['item_name']
            required_qty = float(ing['quantity_required'])
            
            # Use the new helper method from InventoryManager
            available_qty = manager.get_total_item_quantity(item_name)
            
            remaining_qty = available_qty - required_qty
            sufficient = remaining_qty >= 0

            if not sufficient:
                recipe_makeable = False # Mark recipe as not makeable

            # Fetch product details to get unit_of_measure
            product_details = manager.get_product_by_name(item_name)
            product_unit_of_measure = 'units' # Default unit
            if product_details and product_details.get('unit_of_measure'):
                product_unit_of_measure = product_details['unit_of_measure']

            ingredients_status.append({
                'name': item_name,
                'required': required_qty,
                'available': available_qty,
                'remaining': remaining_qty,
                'sufficient': sufficient,
                'needed_more': -remaining_qty if not sufficient else 0,
                'unit_of_measure': product_unit_of_measure
            })
    else: # Recipe has no ingredients listed
        recipe_makeable = True # Technically makeable if no ingredients are needed

    return render_template('recipe_detail.html', 
                           recipe=recipe, 
                           ingredients_status=ingredients_status, 
                           recipe_makeable=recipe_makeable)

# Placeholder for Make Recipe POST route - to be implemented in a later subtask
@app.route('/recipes/<path:recipe_name>/make', methods=['POST'])
def make_recipe_view(recipe_name):
    # This is where the logic to "make" the recipe would go.
    # For now, just flash a message and redirect.
    # Actual implementation would consume ingredients from inventory.
    
    # Re-check if makeable before attempting to make, as inventory might have changed.
    recipe = recipe_mngr.get_recipe_by_name(recipe_name)
    if not recipe:
        flash(f"Recipe '{recipe_name}' not found.", 'error')
        return redirect(url_for('recipes_list_view'))

    recipe_makeable_now = True
    if recipe.get('ingredients'):
        for ing_spec in recipe['ingredients']:
            available = manager.get_total_item_quantity(ing_spec['item_name'])
            if available < float(ing_spec['quantity_required']):
                recipe_makeable_now = False
                break
    
    if not recipe_makeable_now:
        flash(f"Cannot make '{recipe_name}'. Not enough ingredients currently available.", 'error')
        return redirect(url_for('recipe_detail_view', recipe_name=recipe_name))

    # Actual implementation to consume ingredients from inventory.
    all_consumed_successfully = True
    consumption_error_messages = []

    if recipe.get('ingredients'):
        for ingredient in recipe['ingredients']:
            item_name = ingredient['item_name']
            required_qty = float(ingredient['quantity_required'])
            
            # consume_item returns a dict: {"success": bool, "message": str, "details": list}
            consumption_result = manager.consume_item(item_name, required_qty)
            
            if not consumption_result.get("success"):
                all_consumed_successfully = False
                # Accumulate error messages if specific items fail, though prior check should prevent this.
                # This handles unexpected issues during consumption.
                consumption_error_messages.append(
                    f"Failed to consume {required_qty} of '{item_name}'. "
                    f"Reason: {consumption_result.get('message', 'Unknown error.')}"
                )
                # If one ingredient fails, we might want to stop and not consume further,
                # or attempt to consume all and report individual failures.
                # For now, let's stop on first critical failure.
                # A more advanced system might try to "roll back" previous consumptions if one fails mid-way.
                break 
    
    if all_consumed_successfully and not consumption_error_messages:
        flash(f"Recipe '{recipe.name}' made successfully! Ingredients have been consumed.", 'success')
    else:
        # If loop was broken due to consumption failure after availability check (should be rare)
        flash(f"Error making recipe '{recipe.name}'. Some ingredients could not be consumed:", 'error')
        for err_msg in consumption_error_messages:
            flash(err_msg, 'error')
        # It's also possible recipe_makeable_now was false and we already flashed that.
        # This block mainly handles errors *during* the consumption loop.

    return redirect(url_for('recipe_detail_view', recipe_name=recipe_name))


@app.route('/inventory/projections')
def projections_view():
    unique_item_names_for_proj = _get_unique_item_names(include_historical=True) # Use new helper

    projection_results_list = []
    if unique_item_names_for_proj:
        for item_name in unique_item_names_for_proj:
            # project_demand in InventoryManager now prints to console AND returns dict.
            # Flask app will use the returned dict.
            projection_data = manager.project_demand(item_name) # Uses default lookback/projection days
            if projection_data and projection_data.get("success", True): # Check for success if manager might return that
                if 'product_name' in projection_data:
                    projection_data['item_name'] = projection_data.pop('product_name')
                projection_results_list.append(projection_data)
            elif projection_data and not projection_data.get("success", True):
                flash(f"Could not generate projection for {item_name}: {projection_data.get('message', 'Unknown error')}", "error")
    
    return render_template('projections.html', projections=projection_results_list)

@app.route('/shopping_list')
def shopping_list_view():
    store_filter = request.args.get('store', '').strip()
    search_term = request.args.get('search', '').strip()

    # Get shopping list items from the manager
    # The manager.get_shopping_list_items method should handle None or empty strings for filters
    shopping_list_items = manager.get_shopping_list_items(
        store_filter=store_filter if store_filter else None,
        search_term=search_term if search_term else None
    )

    # Pass the items and current filter values to the template
    return render_template('shopping_list.html',
                           items=shopping_list_items,
                           current_store_filter=store_filter,
                           current_search_term=search_term)

# --- Product Management Routes ---
@app.route('/products', methods=['GET'])
def list_products_view():
    products = manager.get_all_products()
    return render_template('list_products.html', products=products)

@app.route('/products/create', methods=['GET', 'POST'])
def create_product_view():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        category = request.form.get('category', '').strip()
        subcategory = request.form.get('subcategory', '').strip()
        unit_of_measure = request.form.get('unit_of_measure', '').strip()
        default_expiry_days_str = request.form.get('default_expiry_days', '').strip()
        par_level_str = request.form.get('par_level', '0').strip()
        max_holding_amount_str = request.form.get('max_holding_amount', '0').strip()
        purchase_location = request.form.get('purchase_location', '').strip()

        errors = []
        if not name: errors.append("Product name is required.")
        if not unit_of_measure: errors.append("Unit of measure is required.")
        if not default_expiry_days_str: errors.append("Default expiry days are required.")

        default_expiry_days = None
        try:
            default_expiry_days = int(default_expiry_days_str)
            if default_expiry_days < 0:
                errors.append("Default expiry days must be a non-negative number.")
        except ValueError:
            if default_expiry_days_str: # Error only if it's not empty but invalid
                 errors.append("Default expiry days must be a valid whole number.")

        par_level = 0.0
        try:
            par_level = float(par_level_str)
            if par_level < 0:
                errors.append("Par level must be a non-negative number.")
        except ValueError:
            if par_level_str and par_level_str != '0': # Error if not empty, not '0', but invalid
                errors.append("Par level must be a valid number.")

        max_holding_amount = 0.0
        try:
            max_holding_amount = float(max_holding_amount_str)
            if max_holding_amount < 0:
                errors.append("Max holding amount must be a non-negative number.")
        except ValueError:
            if max_holding_amount_str and max_holding_amount_str != '0':
                errors.append("Max holding amount must be a valid number.")

        # Optional: Validate purchase_location against a predefined list if necessary
        # For now, allowing free text based on Food_manager.py structure

        if errors:
            for error in errors:
                flash(error, 'error')
            return render_template('create_product.html', form_data=request.form)

        result = manager.create_product(
            name=name,
            category=category if category else None,
            subcategory=subcategory if subcategory else None,
            unit_of_measure=unit_of_measure,
            default_expiry_days=default_expiry_days,
            par_level=par_level,
            max_holding_amount=max_holding_amount,
            purchase_location=purchase_location if purchase_location else None
        )

        if result.get("success"):
            flash(result['message'], 'success')
            return redirect(url_for('list_products_view'))
        else:
            flash(result.get("message", "An error occurred creating the product."), 'error')
            return render_template('create_product.html', form_data=request.form)

    return render_template('create_product.html', form_data={})

@app.route('/products/<int:product_id>/edit', methods=['GET', 'POST'])
def edit_product_view(product_id):
    product = manager.get_product(product_id)
    if not product:
        flash(f"Product with ID {product_id} not found.", 'error')
        return redirect(url_for('list_products_view'))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        category = request.form.get('category', '').strip()
        subcategory = request.form.get('subcategory', '').strip()
        unit_of_measure = request.form.get('unit_of_measure', '').strip()
        default_expiry_days_str = request.form.get('default_expiry_days', '').strip()
        par_level_str = request.form.get('par_level', '0').strip()
        max_holding_amount_str = request.form.get('max_holding_amount', '0').strip()
        purchase_location = request.form.get('purchase_location', '').strip()

        errors = []
        if not name: errors.append("Product name is required.")
        if not unit_of_measure: errors.append("Unit of measure is required.")
        if not default_expiry_days_str: errors.append("Default expiry days are required.")

        default_expiry_days = None
        try:
            default_expiry_days = int(default_expiry_days_str)
            if default_expiry_days < 0:
                errors.append("Default expiry days must be a non-negative number.")
        except ValueError:
            if default_expiry_days_str:
                 errors.append("Default expiry days must be a valid whole number.")

        par_level = 0.0
        try:
            par_level = float(par_level_str)
            if par_level < 0:
                errors.append("Par level must be a non-negative number.")
        except ValueError:
            if par_level_str and par_level_str != '0':
                errors.append("Par level must be a valid number.")

        max_holding_amount = 0.0
        try:
            max_holding_amount = float(max_holding_amount_str)
            if max_holding_amount < 0:
                errors.append("Max holding amount must be a non-negative number.")
        except ValueError:
            if max_holding_amount_str and max_holding_amount_str != '0':
                errors.append("Max holding amount must be a valid number.")

        if errors:
            for error in errors:
                flash(error, 'error')
            # Pass current form data back to template, merge with original product data for safety
            form_data = request.form.to_dict()
            product_data_for_template = {**product, **form_data} # Form data overrides product data if keys clash
            return render_template('edit_product.html', product=product_data_for_template)

        result = manager.update_product(
            product_id=product_id,
            name=name,
            category=category if category else None,
            subcategory=subcategory if subcategory else None,
            unit_of_measure=unit_of_measure,
            default_expiry_days=default_expiry_days,
            par_level=par_level,
            max_holding_amount=max_holding_amount,
            purchase_location=purchase_location if purchase_location else None
        )

        if result.get("success"):
            flash(result['message'], 'success')
            return redirect(url_for('list_products_view'))
        else:
            flash(result.get("message", f"An error occurred updating product ID {product_id}."), 'error')
            form_data = request.form.to_dict()
            product_data_for_template = {**product, **form_data}
            return render_template('edit_product.html', product=product_data_for_template)

    # GET request: pass the fetched product data to the template
    return render_template('edit_product.html', product=product)

# --- Inventory Management Routes ---
@app.route('/inventory/add_stock', methods=['GET', 'POST'])
def add_inventory_stock_view():
    if request.method == 'POST':
        product_id_str = request.form.get('product_id')
        quantity_added = request.form.get('quantity_added', '').strip()
        purchase_date_str = request.form.get('purchase_date', '').strip()

        errors = []
        if not product_id_str:
            errors.append("Product selection is required.")

        product_id = None
        if product_id_str:
            try:
                product_id = int(product_id_str)
            except ValueError:
                errors.append("Invalid product ID.")

        if not quantity_added: # Basic check, manager._parse_quantity_string will do more
            errors.append("Quantity added is required.")
        else:
            try:
                # Validate that quantity_added is a number
                float(quantity_added)
                # Check if quantity is positive using manager's parser
                # This part remains, as _parse_quantity_string might handle units in the future
                # and it also ensures the string is appropriate for DB storage if it includes units.
                # For now, it expects a string that can be converted to float.
                parsed_qty = manager._parse_quantity_string(quantity_added)
                if parsed_qty <= 0:
                    errors.append("Quantity added must be a positive amount.")
            except ValueError:
                errors.append("Quantity added must be a number.")

        if not purchase_date_str:
            purchase_date_str = date.today().isoformat() # Default to today
        else:
            try:
                date.fromisoformat(purchase_date_str) # Validate format
            except ValueError:
                errors.append("Invalid purchase date format. Please use YYYY-MM-DD.")

        if errors:
            for error in errors:
                flash(error, 'error')
            # Repopulate products for dropdown
            products_for_dropdown = manager.get_all_products()
            return render_template('add_inventory.html', products=products_for_dropdown, form_data=request.form)

        # If validation passes
        result = manager.add_inventory_stock(
            product_id=product_id,
            quantity_str=quantity_added,
            purchase_date_str=purchase_date_str
        )

        if result.get("success"):
            flash(result['message'], 'success')
            return redirect(url_for('current_inventory_view'))
        else:
            flash(result.get("message", "An error occurred adding inventory stock."), 'error')
            products_for_dropdown = manager.get_all_products() # Repopulate products
            return render_template('add_inventory.html', products=products_for_dropdown, form_data=request.form)

    # GET request
    products_for_dropdown = manager.get_all_products()
    # Default purchase date to today for GET request pre-fill
    return render_template('add_inventory.html', products=products_for_dropdown, form_data={'purchase_date': date.today().isoformat()})

@app.route('/inventory/edit', methods=['GET', 'POST'])
def edit_inventory_view():
    products_for_dropdown = manager.get_all_products()
    selected_product_id = request.args.get('product_id')
    inventory_batches = []
    selected_product_name = None

    if selected_product_id:
        try:
            # Fetch current and last 3 lines (total 4), ordered by id descending
            # to get the most recently added batches.
            inventory_batches = manager.get_inventory_batches_for_product(
                product_id=int(selected_product_id),
                limit=4,
                order_by_id_desc=True
            )
            # The method returns them in DESC order of ID (most recent first).
            # The template iterates as is (most recent first). If oldest of these 4 should be first,
            # they would need to be reversed here: inventory_batches.reverse()

            selected_product = manager.get_product(int(selected_product_id))
            if selected_product:
                selected_product_name = selected_product['name']
        except ValueError: # Handles error from int(selected_product_id)
            flash("Invalid product ID format provided.", "error")
            selected_product_id = None # Reset to avoid further errors
            inventory_batches = [] # Ensure it's an empty list
            # selected_product_name remains None or its previous state

    if request.method == 'POST':
        include_in_projections = request.form.get('include_in_projections') == 'true'

        # selected_product_id is needed for the redirect, try to get it from form if hidden field added,
        # or from the original GET param if still in context.
        # For safety, it's better if product_id is part of the form submission.
        # Let's assume 'product_id' (the one for the dropdown) is also submitted,
        # or we re-fetch/validate it if necessary.
        # The current HTML form doesn't explicitly submit the overall 'product_id' for the page,
        # only 'product_id' for the dropdown selection (which causes a GET).
        # The `selected_product_id` variable should be available from the GET part of the view if the page reloads.
        # For the redirect:
        page_product_id_for_redirect = request.form.get('product_id_for_redirect') # Assuming we add this hidden field

        # Iterate through form data to find batch adjustments
        i = 0
        while True:
            batch_id_str = request.form.get(f'batch_id_{i}')
            if batch_id_str is None:
                break # No more batches in the form

            new_quantity_str = request.form.get(f'quantity_{i}')
            new_purchase_date_str = request.form.get(f'purchase_date_{i}')
            new_expiry_date_str = request.form.get(f'expiry_date_{i}')

            if not batch_id_str: # Should not happen if form is structured correctly
                i += 1
                continue

            try:
                batch_id = int(batch_id_str)
                # Call the manager method
                # NOTE: The `include_in_projections` variable is captured but not yet passed to `adjust_inventory_batch`.
                # This will be addressed if `adjust_inventory_batch` is updated to use it.
                result = manager.adjust_inventory_batch(
                    batch_id=batch_id,
                    new_quantity_str=new_quantity_str,
                    new_purchase_date_str=new_purchase_date_str,
                    new_expiry_date_str=new_expiry_date_str,
                    include_in_projections=include_in_projections # Ensure this is passed
                )

                if result.get("success"):
                    flash(result["message"], 'success')
                else:
                    flash(f"Error for batch ID {batch_id}: {result.get('message', 'Unknown error.')}", 'error')

            except ValueError:
                flash(f"Invalid Batch ID format: {batch_id_str}", "error")
            except Exception as e: # Catch any other unexpected errors during adjustment
                flash(f"An unexpected error occurred processing batch ID {batch_id_str}: {e}", "error")

            i += 1

        # If page_product_id_for_redirect was not available, try selected_product_id from GET context
        redirect_product_id = page_product_id_for_redirect if page_product_id_for_redirect else selected_product_id

        if redirect_product_id:
            return redirect(url_for('edit_inventory_view', product_id=redirect_product_id))
        else:
            # If no product_id is known (e.g., if form submission was manipulated or state lost)
            # redirect to the plain edit page or current inventory.
            flash("No product context for redirect, returning to general edit page.", "warning")
            return redirect(url_for('edit_inventory_view'))

    return render_template('edit_inventory.html',
                           products=products_for_dropdown,
                           selected_product_id=selected_product_id,
                           selected_product_name=selected_product_name,
                           inventory_batches=inventory_batches)


if __name__ == '__main__':
    # Debug mode should be False in a production environment
    # Host '0.0.0.0' makes it accessible from network, useful for some environments
    app.run(host='0.0.0.0', port=8080, debug=True)
