from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
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
    # Retrieve filter and sort parameters from request.args
    search_term = request.args.get('search_term', '').strip()
    selected_category = request.args.get('category', '').strip()
    selected_purchase_location = request.args.get('purchase_location', '').strip()
    expiry_start_date = request.args.get('expiry_start_date', '').strip()
    expiry_end_date = request.args.get('expiry_end_date', '').strip()

    filter_is_below_par_str = request.args.get('filter_is_below_par', 'false').strip().lower()
    filter_is_below_par = filter_is_below_par_str == 'true'

    sort_by = request.args.get('sort_by', 'expiry_date').strip()
    sort_order = request.args.get('sort_order', 'ASC').strip().upper()
    if sort_order not in ['ASC', 'DESC']:
        sort_order = 'ASC'

    try:
        page = int(request.args.get('page', 1))
        if page < 1: page = 1
    except ValueError:
        page = 1

    try:
        per_page = int(request.args.get('per_page', 20)) # Default 20 items per page
        if per_page < 1: per_page = 1
    except ValueError:
        per_page = 20

    # Fetch data from manager using SQL-filterable parameters
    inventory_items_raw = manager.get_current_inventory(
        search_term=search_term if search_term else None,
        category=selected_category if selected_category else None,
        purchase_location=selected_purchase_location if selected_purchase_location else None,
        expiry_start_date=expiry_start_date if expiry_start_date else None,
        expiry_end_date=expiry_end_date if expiry_end_date else None,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        per_page=per_page
    )

    total_items = manager.get_current_inventory_count(
        search_term=search_term if search_term else None,
        category=selected_category if selected_category else None,
        purchase_location=selected_purchase_location if selected_purchase_location else None,
        expiry_start_date=expiry_start_date if expiry_start_date else None,
        expiry_end_date=expiry_end_date if expiry_end_date else None
    )

    # Process items and apply is_below_par filter if requested
    processed_inventory_items = []
    for item_dict in inventory_items_raw:
        item_processed = dict(item_dict)
        numeric_quantity = manager._parse_quantity_string(item_processed['quantity'])
        par_level = item_processed.get('par_level', 0.0)
        if par_level is None: par_level = 0.0
        else: par_level = float(par_level)
        
        item_processed['is_below_par'] = (numeric_quantity < par_level and par_level > 0)

        if filter_is_below_par:
            if item_processed['is_below_par']:
                processed_inventory_items.append(item_processed)
        else:
            processed_inventory_items.append(item_processed)

    # Pagination calculation (uses total_items from DB before Python-level 'is_below_par' filtering)
    total_pages = (total_items + per_page - 1) // per_page if per_page > 0 else 1
    if page > total_pages and total_pages > 0: # Adjust page if it's out of bounds after filtering
        page = total_pages
        # Re-fetching might be needed if is_below_par drastically changed item count for the page
        # For this iteration, we accept the limitation that a page might show fewer items
        # if is_below_par is filtered in Python.

    # Fetch filter options
    categories_options = manager.get_current_inventory_categories()
    purchase_locations_options = manager.get_current_inventory_purchase_locations()

    today = date.today()
    return render_template(
        'current_inventory.html',
        items=processed_inventory_items,
        today=today,
        timedelta=timedelta,
        current_page=page,
        total_pages=total_pages,
        per_page=per_page,
        search_term=search_term,
        selected_category=selected_category,
        selected_purchase_location=selected_purchase_location,
        expiry_start_date=expiry_start_date,
        expiry_end_date=expiry_end_date,
        filter_is_below_par=filter_is_below_par, # Pass the boolean
        sort_by=sort_by,
        sort_order=sort_order,
        categories=categories_options,
        purchase_locations=purchase_locations_options
    )

@app.route('/inventory/historical')
def historical_inventory_view():
    # Retrieve filter and sort parameters
    search_term = request.args.get('search_term', '').strip()
    selected_category = request.args.get('category', '').strip()
    consumed_start_date = request.args.get('consumed_start_date', '').strip()
    consumed_end_date = request.args.get('consumed_end_date', '').strip()

    sort_by = request.args.get('sort_by', 'consumed_date').strip()
    sort_order = request.args.get('sort_order', 'DESC').strip().upper()
    if sort_order not in ['ASC', 'DESC']:
        sort_order = 'DESC'

    try:
        page = int(request.args.get('page', 1))
        if page < 1: page = 1
    except ValueError:
        page = 1

    try:
        per_page = int(request.args.get('per_page', 20))
        if per_page < 1: per_page = 1
    except ValueError:
        per_page = 20

    # Fetch data from manager
    historical_items = manager.get_historical_inventory(
        search_term=search_term if search_term else None,
        category=selected_category if selected_category else None,
        consumed_start_date=consumed_start_date if consumed_start_date else None,
        consumed_end_date=consumed_end_date if consumed_end_date else None,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        per_page=per_page
    )

    total_items = manager.get_historical_inventory_count(
        search_term=search_term if search_term else None,
        category=selected_category if selected_category else None,
        consumed_start_date=consumed_start_date if consumed_start_date else None,
        consumed_end_date=consumed_end_date if consumed_end_date else None
    )

    total_pages = (total_items + per_page - 1) // per_page if per_page > 0 else 1

    # Adjust page if out of bounds (e.g., after filters change total item count)
    if page > total_pages and total_pages > 0:
        page = total_pages
        # Re-fetch for the new valid page
        historical_items = manager.get_historical_inventory(
            search_term=search_term if search_term else None,
            category=selected_category if selected_category else None,
            consumed_start_date=consumed_start_date if consumed_start_date else None,
            consumed_end_date=consumed_end_date if consumed_end_date else None,
            sort_by=sort_by,
            sort_order=sort_order,
            page=page,
            per_page=per_page
        )

    # Fetch filter options
    categories_options = manager.get_historical_inventory_categories()

    return render_template(
        'historical_inventory.html',
        items=historical_items,
        current_page=page,
        total_pages=total_pages,
        per_page=per_page,
        search_term=search_term,
        selected_category=selected_category,
        consumed_start_date=consumed_start_date,
        consumed_end_date=consumed_end_date,
        sort_by=sort_by,
        sort_order=sort_order,
        categories=categories_options
    )

@app.route('/inventory/consume', methods=['GET', 'POST'])
def consume_item_view():
    item_names = _get_unique_item_names() # Use new helper, default is include_historical=False
    all_recipes = recipe_mngr.get_all_recipes() # Fetch recipes once for the view

    if request.method == 'POST':
        consumption_type = request.form.get('consumption_type', 'item') # Default to 'item'

        if consumption_type == 'recipe':
            recipe_name_to_consume = request.form.get('recipe_name_to_consume')
            if not recipe_name_to_consume:
                flash("Please select a recipe to consume.", 'error')
                # item_names and all_recipes are already fetched
                return render_template('consume_item.html', item_names=item_names, recipes=all_recipes, form_data=request.form)
            else:
                # Redirect to the make_recipe_view, which handles the actual consumption
                return redirect(url_for('make_recipe_view', recipe_name=recipe_name_to_consume))
        
        # Else, it's an 'item' consumption (existing logic)
        else: # consumption_type == 'item'
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
                    if numeric_quantity_consumed <= 0: # This check is now in FoodManager, but good to have here too for early feedback
                        errors.append("Quantity to consume must be a positive number (greater than zero).")
                except ValueError:
                    errors.append("Quantity to consume must be a valid number.")

            if errors:
                for error in errors:
                    flash(error, 'error')
                # item_names and all_recipes are already fetched
                return render_template('consume_item.html', item_names=item_names, recipes=all_recipes, form_data=request.form)

            # If validation passes for item consumption
            try:
                result = manager.consume_item(item_name, numeric_quantity_consumed)

                if result.get("success"):
                    flash(result.get("message", f"Consumption of '{item_name}' processed."), 'success')
                else:
                    flash(result.get("message", f"Could not consume '{item_name}'."), 'error')

                return redirect(url_for('current_inventory_view'))

            except Exception as e:
                flash(f"An unexpected error occurred while consuming item: {e}", 'error')
                # item_names and all_recipes are already fetched
                return render_template('consume_item.html', item_names=item_names, recipes=all_recipes, form_data=request.form)

    # For GET request (all_recipes already fetched)
    return render_template('consume_item.html', item_names=item_names, recipes=all_recipes, form_data={})

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
                unit_of_measure_col = header_map.get('unit of measure') # New
                
                items_added_count = 0
                error_messages = []
                uom_mismatch_warnings = [] # Initialize list for UoM warnings

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
                    unit_of_measure_val = str(row[unit_of_measure_col]).strip() if unit_of_measure_col is not None and row[unit_of_measure_col] is not None else None # New

                    # Skip row if essential 'name' field is missing
                    if not name:
                        # Check if any other relevant cell in the row has data to avoid skipping genuinely sparse rows
                        # vs. completely blank rows often found at the end of sheets.
                        other_cells_have_data = any(
                            row[col_idx] for col_idx in [qty_col, pdate_col, expdays_col,
                                                         category_col, subcategory_col, par_level_col, max_holding_col, purchase_location_col, unit_of_measure_col]
                            if col_idx is not None and len(row) > col_idx and row[col_idx] is not None
                        )
                        if other_cells_have_data:
                            error_messages.append(f"Row {row_idx}: Name is missing but other data present. Skipped.")
                        # If all relevant cells are effectively empty, it's likely an empty row, so just continue
                        elif not any(row[col_idx] for col_idx in [name_col, qty_col, pdate_col, expdays_col,
                                                                category_col, subcategory_col, par_level_col, max_holding_col, purchase_location_col, unit_of_measure_col]
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
                    
                    # Conditional requirement for unit_of_measure
                    product_exists = manager.get_product_by_name(name)
                    if not product_exists and not unit_of_measure_val:
                        row_errors.append("Unit of Measure is required for new products.")

                    if row_errors: 
                        error_messages.append(f"Row {row_idx} ('{name}'): " + "; ".join(row_errors))
                        continue 

                    # If all validations pass for this row, attempt to add to inventory
                    try:
                        result = manager.add_item_to_list( # Capture the result
                            name=str(name), 
                            quantity_str=str(quantity), 
                            purchase_date_str=purchase_date_str, 
                            expiry_days=expiry_days_int,
                            category=category if category else None, # Pass None if empty string
                            subcategory=subcategory if subcategory else None,
                            par_level=par_level_float,
                            max_holding_amount=max_holding_float,
                            purchase_location=purchase_location_to_pass, # New
                            unit_of_measure=unit_of_measure_val # New
                        )
                        items_added_count += 1

                        # Check for UoM mismatch
                        if result.get('uom_mismatch'):
                            warning_msg = (f"Warning: UoM for '{result.get('original_product_name')}' "
                                           f"in Excel ('{result.get('excel_uom')}') differs from "
                                           f"database ('{result.get('db_uom')}'). "
                                           "Product's UoM was not updated.")
                            uom_mismatch_warnings.append(warning_msg)

                    except Exception as e: # Catch errors from manager.add_item_to_list
                        error_messages.append(f"Row {row_idx} ('{name}'): Error adding to inventory - {str(e)}")
                
                # Flash summary for items added
                if items_added_count > 0:
                    flash(f"Successfully added {items_added_count} items from the Excel file.", 'success')

                # Flash UoM mismatch warnings
                if uom_mismatch_warnings:
                    flash("Some products had Unit of Measure mismatches (UoM in Excel differs from DB; DB UoM was kept):", 'warning')
                    for warning in uom_mismatch_warnings:
                        flash(warning, 'warning_detail') # Use a distinct category for individual warnings if needed

                # Flash errors for rows that failed
                if error_messages:
                    flash(f"{len(error_messages)} rows had errors and were not processed. See details below:", 'error')
                    for err_msg in error_messages[:5]: # Show first 5 errors
                        flash(err_msg, 'error_detail') # Use a distinct category for individual errors

                if items_added_count == 0 and not error_messages and not uom_mismatch_warnings:
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
    all_db_products = manager.get_all_products(page=None, per_page=None) # For "Output Product" dropdown

    if request.method == 'POST':
        recipe_name = request.form.get('recipe_name', '').strip()
        description = request.form.get('description', '').strip()
        output_product_id_str = request.form.get('output_product_id')
        output_yield_str = request.form.get('output_yield')
        
        ingredients = []
        form_errors = []
        for i in range(1, 11):
            ing_name = request.form.get(f'ingredient_{i}_name', '').strip()
            ing_qty_str = request.form.get(f'ingredient_{i}_quantity', '').strip()
            # notes are optional, not used in current RecipeManager.add_recipe for ingredient quantity_required
            # ing_notes = request.form.get(f'ingredient_{i}_notes', '').strip()

            if ing_name and ing_qty_str:
                try:
                    # The RecipeManager expects 'quantity_required' for the value,
                    # but the form might use 'quantity' for simplicity.
                    # Let's assume RecipeManager expects 'quantity' as string or 'quantity_required' as float.
                    # Based on current RecipeManager, it expects 'quantity' as a string.
                    # No, `add_recipe` in RecipeManager processes `quantity_required` from this form.
                    # The form should submit `quantity_required` or the route should adapt.
                    # The current `add_recipe_view` (before this change) uses `quantity_required`.
                    # Let's stick to `quantity_required` for clarity with the manager.
                    # The template might name it `ingredient_X_quantity` for user display.
                    ing_qty_float = float(ing_qty_str)
                    if ing_qty_float <= 0:
                        form_errors.append(f"Ingredient '{ing_name}': Quantity must be a positive number.")
                    else:
                        # ingredients.append({'item_name': ing_name, 'quantity': ing_qty_str, 'notes': ing_notes})
                        # Corrected to use 'quantity_required' as expected by manager logic in add_recipe
                         ingredients.append({'item_name': ing_name, 'quantity_required': ing_qty_float})
                except ValueError:
                    form_errors.append(f"Ingredient '{ing_name}': Invalid quantity '{ing_qty_str}'. Must be a valid number.")
            elif ing_name and not ing_qty_str:
                form_errors.append(f"Ingredient '{ing_name}': Quantity is missing.")
        
        if not recipe_name:
            form_errors.append("Recipe name is required.")

        output_product_id = None
        if output_product_id_str and output_product_id_str != "None" and output_product_id_str != "":
            try:
                output_product_id = int(output_product_id_str)
            except ValueError:
                form_errors.append("Invalid Output Product ID.")
        
        output_yield = None
        if output_yield_str:
            try:
                output_yield = float(output_yield_str)
                if output_yield <= 0 and output_product_id is not None: # Yield must be positive if an output product is set
                     form_errors.append("Output Yield must be positive if an Output Product is selected.")
                elif output_yield < 0 and output_product_id is None: # Allow zero yield if no product, but not negative
                    form_errors.append("Output Yield cannot be negative.")
            except ValueError:
                form_errors.append("Invalid Output Yield. Must be a number.")

        if output_product_id is not None and output_yield is None:
            form_errors.append("Output Yield is required if an Output Product is selected.")


        if form_errors:
            for error in form_errors:
                flash(error, 'error')
            form_data_to_repopulate = request.form
            return render_template('add_recipe.html', form_data=form_data_to_repopulate, products=all_db_products)

        recipe_data = {
            "name": recipe_name,
            "description": description,
            "instructions": request.form.get('instructions', '').strip(), # Added instructions
            "ingredients": ingredients, # This should be list of dicts with item_name, quantity_required
            "output_product_id": output_product_id,
            "output_yield": output_yield
        }
        
        # recipe_mngr.add_recipe was updated to handle output_product_id and output_yield
        result = recipe_mngr.add_recipe(recipe_data)
        
        if result.get("success"):
            flash(result['message'], 'success')
            return redirect(url_for('recipes_list_view'))
        else:
            flash(result['message'], 'error')
            form_data_to_repopulate = request.form
            return render_template('add_recipe.html', form_data=form_data_to_repopulate, products=all_db_products)

    return render_template('add_recipe.html', form_data=form_data_to_repopulate, products=all_db_products)

@app.route('/recipes/<int:recipe_id>/edit', methods=['GET', 'POST'])
def edit_recipe_view(recipe_id):
    recipe = recipe_mngr.get_recipe_by_id(recipe_id) # Should now include output_product_id and output_yield

    if not recipe:
        flash(f"Recipe with ID {recipe_id} not found.", 'error')
        return redirect(url_for('recipes_list_view'))

    all_db_products = manager.get_all_products(page=None, per_page=None)

    if request.method == 'POST':
        recipe_name = request.form.get('recipe_name', '').strip()
        description = request.form.get('description', '').strip()
        instructions = request.form.get('instructions', '').strip()
        output_product_id_str = request.form.get('output_product_id')
        output_yield_str = request.form.get('output_yield')

        ingredients = []
        form_errors = []

        for i in range(1, 11):
            ing_name = request.form.get(f'ingredient_{i}_name', '').strip()
            ing_qty_str = request.form.get(f'ingredient_{i}_quantity', '').strip()
            # ing_notes = request.form.get(f'ingredient_{i}_notes', '').strip()

            if ing_name and ing_qty_str:
                try:
                    ing_qty_float = float(ing_qty_str)
                    if ing_qty_float <= 0:
                        form_errors.append(f"Ingredient '{ing_name}': Quantity must be a positive number.")
                    else:
                        # ingredients.append({'item_name': ing_name, 'quantity': ing_qty_str, 'notes': ing_notes})
                        # Corrected to use 'quantity_required'
                        ingredients.append({'item_name': ing_name, 'quantity_required': ing_qty_float})
                except ValueError:
                    form_errors.append(f"Ingredient '{ing_name}': Invalid quantity '{ing_qty_str}'.")
            elif ing_name and not ing_qty_str:
                form_errors.append(f"Ingredient '{ing_name}': Quantity is missing.")

        if not recipe_name:
            form_errors.append("Recipe name is required.")

        output_product_id = None
        if output_product_id_str and output_product_id_str != "None" and output_product_id_str != "":
            try:
                output_product_id = int(output_product_id_str)
            except ValueError:
                form_errors.append("Invalid Output Product ID.")

        output_yield = None
        if output_yield_str:
            try:
                output_yield = float(output_yield_str)
                if output_yield <= 0 and output_product_id is not None:
                     form_errors.append("Output Yield must be positive if an Output Product is selected.")
                elif output_yield < 0 and output_product_id is None:
                    form_errors.append("Output Yield cannot be negative.")
            except ValueError:
                form_errors.append("Invalid Output Yield. Must be a number.")

        if output_product_id is not None and output_yield is None : # Check if yield is missing when product id is present
             # Check if original recipe also had product_id but no yield, or if this is a new assignment
            if not (recipe.get('output_product_id') == output_product_id and recipe.get('output_yield') is None):
                 form_errors.append("Output Yield is required if an Output Product is selected.")


        if form_errors:
            for error in form_errors:
                flash(error, 'error')

            form_data_repopulate = request.form.to_dict()
            # Ensure the original recipe ID is part of the data for template if needed
            form_data_repopulate['id'] = recipe_id
            # Merge with original recipe for fields not directly in form or to show original if form field empty
            # For example, the ingredients list in `recipe` is structured, request.form is flat.
            # The template `edit_recipe.html` will need to intelligently use `form_data_repopulate` primarily,
            # and fall back to `recipe` for things like existing ingredients if not resubmitted.
            # This is tricky. A simple approach: template uses `form_data.get('field', recipe.field)`.
            return render_template('edit_recipe.html', recipe=recipe, products=all_db_products, form_data=form_data_repopulate)

        updated_recipe_data = {
            "name": recipe_name,
            "description": description,
            "instructions": instructions,
            "ingredients": ingredients, # This should be list of dicts with item_name, quantity_required
            "output_product_id": output_product_id,
            "output_yield": output_yield
        }

        result = recipe_mngr.update_recipe(recipe_id, updated_recipe_data)

        if result.get("success"):
            flash(result.get('message', "Recipe updated successfully!"), 'success')
            return redirect(url_for('recipe_detail_view', recipe_name=updated_recipe_data['name']))
        else:
            flash(result.get('message', "Failed to update recipe."), 'error')
            form_data_repopulate = request.form.to_dict()
            form_data_repopulate['id'] = recipe_id
            return render_template('edit_recipe.html', recipe=recipe, products=all_db_products, form_data=form_data_repopulate)

    # GET request:
    # The 'recipe' dict (fetched earlier) is used to pre-fill the form.
    # Ensure template can handle `output_product_id` and `output_yield` being None for older recipes.
    return render_template('edit_recipe.html', recipe=recipe, products=all_db_products, form_data={})

@app.route('/recipes')
def recipes_list_view():
    all_recipes = recipe_mngr.get_all_recipes()
    # Sort recipes by name for consistent display order
    sorted_recipes = sorted(all_recipes, key=lambda r: r['name'].lower())
    return render_template('recipes_list.html', recipes=sorted_recipes)

@app.route('/recipes/id/<int:recipe_id>')
def recipe_detail_view_by_id(recipe_id):
    recipe = recipe_mngr.get_recipe_by_id(recipe_id)
    if not recipe:
        flash(f"Recipe with ID {recipe_id} not found.", 'error')
        return redirect(url_for('recipes_list_view'))
    # Since other parts of the app might link by name, we redirect to the name-based URL
    # to maintain consistency and allow `make_recipe_view` to work as is.
    # This also simplifies if the name changes; links using ID will find the new name.
    return redirect(url_for('recipe_detail_view', recipe_name=recipe['name']))

@app.route('/recipes/name/<path:recipe_name>') # Using path for flexibility with names
def recipe_detail_view(recipe_name):
    # This function now serves as the canonical URL for recipe details by name.
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
            ingredient_product_id = None # Default to None
            if product_details:
                if product_details.get('unit_of_measure'):
                    product_unit_of_measure = product_details['unit_of_measure']
                if product_details.get('id'):
                    ingredient_product_id = product_details['id']

            ingredients_status.append({
                'name': item_name,
                'product_id': ingredient_product_id, # Add product_id here
                'required': required_qty,
                'available': available_qty,
                'remaining': remaining_qty,
                'sufficient': sufficient,
                'needed_more': -remaining_qty if not sufficient else 0,
                'unit_of_measure': product_unit_of_measure,
            })
    else: # Recipe has no ingredients listed
        recipe_makeable = True # Technically makeable if no ingredients are needed

    return render_template('recipe_detail.html', 
                           recipe=recipe, 
                           ingredients_status=ingredients_status, 
                           recipe_makeable=recipe_makeable)

# Placeholder for Make Recipe POST route - to be implemented in a later subtask
@app.route('/recipes/<path:recipe_name>/make', methods=['GET', 'POST'])
def make_recipe_view(recipe_name):
    # This is where the logic to "make" the recipe would go.
    # For now, just flash a message and redirect.
    # Actual implementation would consume ingredients from inventory.
    
    # Re-check if makeable before attempting to make, as inventory might have changed.
    recipe = recipe_mngr.get_recipe_by_name(recipe_name) # This now includes output_product_id and output_yield
    app.logger.info(f"Recipe fetched for making: {recipe}") # Log the entire recipe object
    if not recipe:
        flash(f"Recipe '{recipe_name}' not found.", 'error')
        return redirect(url_for('recipes_list_view'))

    num_batches_str = request.form.get('num_batches', '1').strip()
    try:
        num_batches = int(num_batches_str)
        if num_batches <= 0:
            flash("Number of batches must be a positive integer.", 'error')
            return redirect(url_for('recipe_detail_view', recipe_name=recipe_name))
    except ValueError:
        flash("Invalid number of batches specified.", 'error')
        return redirect(url_for('recipe_detail_view', recipe_name=recipe_name))

    # Check ingredient availability for the total quantity needed
    recipe_makeable_now = True
    if recipe.get('ingredients'):
        for ing_spec in recipe['ingredients']:
            total_required_qty = float(ing_spec['quantity_required']) * num_batches
            available = manager.get_total_item_quantity(ing_spec['item_name'])
            if available < total_required_qty:
                recipe_makeable_now = False
                flash(f"Not enough '{ing_spec['item_name']}'. Needed: {total_required_qty}, Available: {available}.", 'warning')
                # break # Optional: break on first insufficient ingredient or list all
    
    if not recipe_makeable_now:
        flash(f"Cannot make {num_batches} batch(es) of '{recipe_name}'. Not enough ingredients.", 'error')
        return redirect(url_for('recipe_detail_view', recipe_name=recipe_name))

    # Consume ingredients
    all_consumed_successfully = True
    consumption_error_messages = []
    if recipe.get('ingredients'):
        for ingredient in recipe['ingredients']:
            item_name = ingredient['item_name']
            qty_per_batch = float(ingredient['quantity_required'])
            total_qty_to_consume = qty_per_batch * num_batches
            
            consumption_result = manager.consume_item(item_name, total_qty_to_consume)
            
            if not consumption_result.get("success"):
                all_consumed_successfully = False
                consumption_error_messages.append(
                    f"Failed to consume {total_qty_to_consume} of '{item_name}'. "
                    f"Reason: {consumption_result.get('message', 'Unknown error.')}"
                )
                break 
    
    if all_consumed_successfully and not consumption_error_messages:
        flash(f"{num_batches} batch(es) of '{recipe['name']}' made! Ingredients consumed.", 'success')

        output_product_id = recipe.get('output_product_id')
        output_yield_per_batch_from_recipe = recipe.get('output_yield') # Renamed
        app.logger.info(f"Attempting production: output_product_id={output_product_id}, output_yield_per_batch_from_recipe={output_yield_per_batch_from_recipe}")

        output_yield_per_batch_float = None
        if output_yield_per_batch_from_recipe is not None:
            try:
                output_yield_per_batch_float = float(output_yield_per_batch_from_recipe)
            except ValueError:
                app.logger.error(f"Invalid output_yield format ('{output_yield_per_batch_from_recipe}') in recipe ID {recipe.get('id')}. Cannot produce output.")
                # The flash message for this case will be handled by the broader try-except block below if production fails

        if output_product_id and output_yield_per_batch_float is not None:
            try:
                if output_yield_per_batch_float > 0:
                    total_output_yield = output_yield_per_batch_float * num_batches
                    app.logger.info(f"Calculated total_output_yield: {total_output_yield} for product_id: {output_product_id}")
                    # Ensure purchase_date_str is defined for add_inventory_stock
                    purchase_date_str = date.today().isoformat()
                    production_result = manager.add_inventory_stock(
                        product_id=output_product_id,
                        quantity_str=str(total_output_yield),
                        purchase_date_str=purchase_date_str
                    )
                    app.logger.info(f"Result of add_inventory_stock: {production_result}")
                    if production_result.get("success"):
                        output_product_details = manager.get_product(output_product_id)
                        output_product_name = output_product_details.get('name', f"ID {output_product_id}") if output_product_details else f"ID {output_product_id}"
                        flash(f"Produced {total_output_yield} of '{output_product_name}' and added to inventory.", 'success')
                    else:
                        flash(f"Error producing output for recipe: {production_result.get('message', 'Unknown error')}", 'error')
                elif output_yield_per_batch_float == 0 : # Yield is zero, no production needed
                    pass # Do nothing if yield is zero
                else: # Negative yield, should be caught by validation ideally
                    flash(f"Recipe has a non-positive output yield ({output_yield_per_batch_float}). No output produced.", 'warning')

            except ValueError:
                flash(f"Invalid output_yield format ('{output_yield_per_batch}') in recipe. Cannot produce output.", 'error')
            except Exception as e: # Catch-all for other errors during production
                flash(f"An unexpected error occurred during output production: {e}", 'error')

        elif output_product_id and output_yield_per_batch is None:
             flash(f"Recipe '{recipe['name']}' has an output product ID but missing output yield. No output produced.", 'warning')
        # If no output_product_id, it's a recipe that doesn't produce a direct inventory item.

    else:
        flash(f"Error making recipe '{recipe['name']}'. Some ingredients could not be consumed:", 'error')
        for err_msg in consumption_error_messages:
            flash(err_msg, 'error_detail') # Use a more specific category for display

    return redirect(url_for('recipe_detail_view', recipe_name=recipe_name))


@app.route('/inventory/projections')
def projections_view():
    # Retrieve filter, sort, and pagination parameters for the product list
    search_term = request.args.get('search_term', '').strip()
    selected_category = request.args.get('category', '').strip()
    selected_purchase_location = request.args.get('purchase_location', '').strip()

    sort_by = request.args.get('sort_by', 'name').strip() # Default sort for product list
    sort_order = request.args.get('sort_order', 'ASC').strip().upper()
    if sort_order not in ['ASC', 'DESC']:
        sort_order = 'ASC'

    try:
        page = int(request.args.get('page', 1))
        if page < 1: page = 1
    except ValueError:
        page = 1

    try:
        per_page = int(request.args.get('per_page', 10)) # Default 10 products per page for projections
        if per_page < 1: per_page = 1
    except ValueError:
        per_page = 10

    # Fetch total count of products for pagination of the product list
    total_products_for_list = manager.get_products_for_projection_list_count(
        search_term=search_term if search_term else None,
        category=selected_category if selected_category else None,
        purchase_location=selected_purchase_location if selected_purchase_location else None
    )

    total_pages = (total_products_for_list + per_page - 1) // per_page if per_page > 0 else 1

    # Adjust page if out of bounds
    original_page = page
    if page > total_pages and total_pages > 0:
        page = total_pages
    elif page == 0 and total_pages > 0: # Should not happen if page default is 1 and min is 1
        page = 1


    # Fetch the paginated list of products
    products_on_page = manager.get_products_for_projection_list(
        search_term=search_term if search_term else None,
        category=selected_category if selected_category else None,
        purchase_location=selected_purchase_location if selected_purchase_location else None,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        per_page=per_page
    )

    projection_results_list = []
    if products_on_page:
        for product_dict in products_on_page:
            # Using product ID for project_demand is more robust
            projection_data = manager.project_demand(product_dict['id'])
            if projection_data: # project_demand returns a dict, might include success status
                 # Ensure item_name is consistently set from product_name for template
                if 'product_name' in projection_data and 'item_name' not in projection_data:
                     projection_data['item_name'] = projection_data['product_name']
                projection_results_list.append(projection_data)
            # Optionally, flash a message if a specific projection failed
            # elif projection_data and not projection_data.get("success", True):
            #     flash(f"Could not generate projection for {product_dict['name']}: {projection_data.get('message', 'Unknown error')}", "error")


    # Fetch filter options for product attributes
    categories_options = manager.get_all_categories() # Reusing existing method for product categories
    purchase_locations_options = manager.get_all_purchase_locations() # Reusing existing method

    return render_template(
        'projections.html',
        projections=projection_results_list,
        current_page=page,
        total_pages=total_pages,
        per_page=per_page,
        search_term=search_term,
        selected_category=selected_category,
        selected_purchase_location=selected_purchase_location,
        sort_by=sort_by,
        sort_order=sort_order,
        categories=categories_options,
        purchase_locations=purchase_locations_options
        # lookback_days and projection_days can be added if they become configurable
    )

@app.route('/projections/save_overrides', methods=['POST'])
def save_overrides_view():
    if request.method == 'POST':
        overrides_to_save = []
        for key, value in request.form.items():
            if key.startswith('overrides['):
                try:
                    # Extract product_id from 'overrides[<product_id>]'
                    start_index = key.find('[') + 1
                    end_index = key.find(']')
                    product_id_str = key[start_index:end_index]
                    product_id = int(product_id_str)

                    # Value is the override rate string
                    # Empty string will be handled by manager as None/NULL
                    rate_str = value.strip()

                    overrides_to_save.append({
                        'product_id': product_id,
                        'override_rate': rate_str if rate_str else None
                    })
                except (ValueError, IndexError) as e:
                    flash(f"Error parsing override data for key {key}: {e}", 'error')
                    # Continue to process other valid entries

        if not overrides_to_save and not request.form:
             flash("No override data submitted.", 'info')
        elif overrides_to_save:
            result = manager.save_consumption_overrides(overrides_to_save)
            if result.get("success"):
                flash(result.get("message", "Consumption overrides saved successfully."), 'success')
            else:
                flash(result.get("message", "Failed to save consumption overrides."), 'error')
        elif not overrides_to_save and request.form: # request.form was not empty, but parsing failed for all
            flash("Submitted override data was not in the expected format.", "error")


    return redirect(url_for('projections_view'))

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

# --- Garden & Harvest Routes ---
@app.route('/garden', methods=['GET'])
def garden_list_view():
    # Basic implementation: Get all items, sort by plant_date by default
    sort_by = request.args.get('sort_by', 'plant_date')
    sort_order = request.args.get('sort_order', 'ASC').upper()
    status_filter = request.args.get('status_filter', '').strip()

    # Pagination
    try:
        page = int(request.args.get('page', 1))
        if page < 1: page = 1
    except ValueError:
        page = 1

    try:
        per_page = int(request.args.get('per_page', 10)) # Default 10 items per page
        if per_page < 1: per_page = 10
    except ValueError:
        per_page = 10

    filters = {}
    if status_filter:
        # This filters by the *stored* status.
        # For dynamic status filtering, logic would need to be in Python after fetching all items,
        # or a more complex SQL query if dynamic status could be expressed in SQL.
        filters['status'] = status_filter

    # The get_all_production_items method should handle pagination and sorting.
    # It also calculates dynamic status and yield.
    # For now, total count for pagination is not implemented for production_items, so pass None for page/per_page
    # to fetch all and then manually paginate if needed, or add count method to manager.
    # For simplicity in this step, fetching all. Pagination can be added fully later.
    all_items_raw = manager.get_all_production_items(
        filters=filters if filters else None,
        sort_by=sort_by,
        sort_order=sort_order,
        page=None, # Fetch all for now
        per_page=None # Fetch all for now
    )

    # Manual pagination for now
    total_items = len(all_items_raw)
    total_pages = (total_items + per_page - 1) // per_page if per_page > 0 else 1
    if page > total_pages and total_pages > 0: page = total_pages

    start_index = (page - 1) * per_page
    end_index = start_index + per_page
    paginated_items = all_items_raw[start_index:end_index]

    return render_template('garden_list.html',
                           items=paginated_items,
                           sort_by=sort_by,
                           sort_order=sort_order,
                           status_filter=status_filter,
                           all_status_options=['Growing', 'Harvesting', 'Finished'], # For filter dropdown
                           current_page=page,
                           total_pages=total_pages,
                           per_page=per_page)

@app.route('/garden/add', methods=['GET', 'POST'])
def add_production_item_view():
    all_db_products = manager.get_all_products(page=None, per_page=None) # Get all products for dropdown

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        associated_product_id_str = request.form.get('associated_product_id')
        plant_date_str = request.form.get('plant_date')
        time_to_harvest_days_str = request.form.get('time_to_harvest_days')
        expected_harvest_period_days_str = request.form.get('expected_harvest_period_days')
        expected_yield_total_str = request.form.get('expected_yield_total')
        status = request.form.get('status', 'Growing').strip()

        errors = []
        if not name: errors.append("Item name is required.")
        if not plant_date_str: errors.append("Plant date is required.")
        else:
            try:
                date.fromisoformat(plant_date_str)
            except ValueError:
                errors.append("Invalid plant date format. Use YYYY-MM-DD.")

        associated_product_id = None
        if associated_product_id_str and associated_product_id_str != "None" and associated_product_id_str != "": # Handle "None" string from dropdown
            try:
                associated_product_id = int(associated_product_id_str)
            except ValueError:
                errors.append("Invalid associated product ID.")

        time_to_harvest_days = None
        if time_to_harvest_days_str:
            try:
                time_to_harvest_days = int(time_to_harvest_days_str)
                if time_to_harvest_days < 0: errors.append("Time to harvest must be non-negative.")
            except ValueError:
                errors.append("Time to harvest must be a whole number.")
        else: errors.append("Time to harvest is required.")

        expected_harvest_period_days = None
        if expected_harvest_period_days_str:
            try:
                expected_harvest_period_days = int(expected_harvest_period_days_str)
                if expected_harvest_period_days <= 0: errors.append("Expected harvest period must be positive.")
            except ValueError:
                errors.append("Expected harvest period must be a whole number.")
        else: errors.append("Expected harvest period is required.")

        expected_yield_total = None
        if expected_yield_total_str:
            try:
                expected_yield_total = float(expected_yield_total_str)
                if expected_yield_total < 0: errors.append("Expected yield must be non-negative.")
            except ValueError:
                errors.append("Expected yield must be a valid number.")
        else: errors.append("Expected total yield is required.")

        if status not in ['Growing', 'Harvesting', 'Finished']:
            errors.append("Invalid status selected.")

        if errors:
            for error in errors:
                flash(error, 'error')
            return render_template('garden_edit.html', item=request.form, products=all_db_products, form_action_label='Add', current_page='garden_add')

        result = manager.add_production_item(
            name=name,
            associated_product_id=associated_product_id, # This can be None
            plant_date_str=plant_date_str,
            time_to_harvest_days=time_to_harvest_days,
            expected_harvest_period_days=expected_harvest_period_days,
            expected_yield_total=expected_yield_total,
            status=status
        )

        if result.get("success"):
            flash(result['message'], 'success')
            return redirect(url_for('garden_list_view'))
        else:
            flash(result.get("message", "An error occurred adding the production item."), 'error')
            return render_template('garden_edit.html', item=request.form, products=all_db_products, form_action_label='Add', current_page='garden_add')

    return render_template('garden_edit.html', item={}, products=all_db_products, form_action_label='Add', current_page='garden_add')

@app.route('/garden/<int:item_id>/edit', methods=['GET', 'POST'])
def edit_production_item_view(item_id):
    production_item = manager.get_production_item(item_id) # This should already return a dict
    if not production_item:
        flash(f"Production item with ID {item_id} not found.", 'error')
        return redirect(url_for('garden_list_view'))

    all_db_products = manager.get_all_products(page=None, per_page=None)

    if request.method == 'POST':
        # Create a mutable copy of the form data for modification
        data_to_update = request.form.to_dict()

        errors = []
        if not data_to_update.get('name', '').strip(): errors.append("Item name is required.")

        plant_date_str = data_to_update.get('plant_date')
        if not plant_date_str: errors.append("Plant date is required.")
        else:
            try:
                date.fromisoformat(plant_date_str)
            except ValueError:
                errors.append("Invalid plant date format. Use YYYY-MM-DD.")

        assoc_prod_id_str = data_to_update.get('associated_product_id')
        if assoc_prod_id_str and assoc_prod_id_str != "None" and assoc_prod_id_str != "":
            try:
                data_to_update['associated_product_id'] = int(assoc_prod_id_str)
            except ValueError:
                errors.append("Invalid associated product ID.")
        else:
            data_to_update['associated_product_id'] = None # Ensure it's None if empty or "None"

        time_harvest_str = data_to_update.get('time_to_harvest_days')
        if time_harvest_str:
            try:
                data_to_update['time_to_harvest_days'] = int(time_harvest_str)
                if data_to_update['time_to_harvest_days'] < 0: errors.append("Time to harvest must be non-negative.")
            except ValueError:
                errors.append("Time to harvest must be a whole number.")
        else: errors.append("Time to harvest is required.")

        exp_harvest_period_str = data_to_update.get('expected_harvest_period_days')
        if exp_harvest_period_str:
            try:
                data_to_update['expected_harvest_period_days'] = int(exp_harvest_period_str)
                if data_to_update['expected_harvest_period_days'] <= 0: errors.append("Expected harvest period must be positive.")
            except ValueError:
                errors.append("Expected harvest period must be a whole number.")
        else: errors.append("Expected harvest period is required.")

        exp_yield_total_str = data_to_update.get('expected_yield_total')
        if exp_yield_total_str:
            try:
                data_to_update['expected_yield_total'] = float(exp_yield_total_str)
                if data_to_update['expected_yield_total'] < 0: errors.append("Expected yield must be non-negative.")
            except ValueError:
                errors.append("Expected yield must be a valid number.")
        else: errors.append("Expected total yield is required.")

        status_str = data_to_update.get('status', '').strip()
        if status_str not in ['Growing', 'Harvesting', 'Finished']:
            errors.append("Invalid status selected.")
            data_to_update['status'] = production_item['status'] # Fallback
        else:
            data_to_update['status'] = status_str


        if errors:
            for error in errors:
                flash(error, 'error')
            # Repopulate with submitted data, ensuring original item ID is preserved.
            # Merge `production_item` (original) with `data_to_update` (submitted form data).
            # Submitted form data should take precedence for fields that were edited.
            form_data_repopulate = {**production_item, **data_to_update}
            return render_template('garden_edit.html', item=form_data_repopulate, products=all_db_products, form_action_label='Edit', current_page='garden_edit')

        # Remove fields from data_to_update that are not part of the production_items table schema
        # or are not meant to be updated directly this way (e.g., calculated fields if they were in form)
        # For now, assuming all keys in data_to_update (after cleaning) are valid for update_production_item

        result = manager.update_production_item(item_id, data_to_update)
        if result.get("success"):
            flash(result['message'], 'success')
            return redirect(url_for('garden_list_view'))
        else:
            flash(result.get("message", "An error occurred updating the production item."), 'error')
            form_data_repopulate = {**production_item, **data_to_update} # Repopulate with submitted data
            return render_template('garden_edit.html', item=form_data_repopulate, products=all_db_products, form_action_label='Edit', current_page='garden_edit')

    # GET request: Convert production_item (which is a dict) to a compatible structure if needed,
    # or ensure template handles dict directly.
    return render_template('garden_edit.html', item=production_item, products=all_db_products, form_action_label='Edit', current_page='garden_edit')

@app.route('/garden/<int:item_id>/harvest', methods=['POST'])
def record_harvest_view(item_id):
    actual_harvest_amount_str = request.form.get('actual_harvest_amount')
    harvest_date_str = request.form.get('harvest_date', date.today().isoformat()) # Default to today

    errors = []
    actual_harvest_amount = None
    if actual_harvest_amount_str:
        try:
            actual_harvest_amount = float(actual_harvest_amount_str)
            if actual_harvest_amount <= 0:
                errors.append("Actual harvest amount must be positive.")
        except ValueError:
            errors.append("Actual harvest amount must be a valid number.")
    else:
        errors.append("Actual harvest amount is required.")

    if not harvest_date_str:
        errors.append("Harvest date is required.")
    else:
        try:
            date.fromisoformat(harvest_date_str)
        except ValueError:
            errors.append("Invalid harvest date format. Use YYYY-MM-DD.")

    if errors:
        for error in errors:
            flash(error, 'error')
    else:
        result = manager.record_harvest(
            production_item_id=item_id,
            actual_harvest_amount=actual_harvest_amount,
            harvest_date_str=harvest_date_str
        )
        if result.get("success"):
            flash(result.get("message", "Harvest recorded successfully and stock added to inventory."), 'success')
        else:
            flash(result.get("message", "Failed to record harvest."), 'error')

    return redirect(url_for('garden_list_view'))

# --- Product Management Routes ---
@app.route('/products', methods=['GET'])
def list_products_view():
    # Retrieve filter parameters
    search_term = request.args.get('search_term', '').strip()
    category = request.args.get('category', '').strip()
    purchase_location = request.args.get('purchase_location', '').strip()

    # Retrieve sorting parameters
    sort_by = request.args.get('sort_by', 'name').strip()
    sort_order = request.args.get('sort_order', 'ASC').strip().upper()
    if sort_order not in ['ASC', 'DESC']:
        sort_order = 'ASC'

    # Retrieve pagination parameters
    try:
        page = int(request.args.get('page', 1))
        if page < 1: page = 1
    except ValueError:
        page = 1

    try:
        per_page = int(request.args.get('per_page', 20))
        if per_page < 1: per_page = 1
    except ValueError:
        per_page = 20

    # Get products with filtering, sorting, and pagination
    products = manager.get_all_products(
        search_term=search_term if search_term else None,
        category=category if category else None,
        purchase_location=purchase_location if purchase_location else None,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        per_page=per_page
    )

    # Get total product count for pagination
    total_products = manager.get_product_count(
        search_term=search_term if search_term else None,
        category=category if category else None,
        purchase_location=purchase_location if purchase_location else None
    )

    total_pages = (total_products + per_page - 1) // per_page if per_page > 0 else 1
    if page > total_pages and total_pages > 0 : # If current page is beyond total pages (e.g. after filters change)
        page = total_pages # Go to last valid page
        # Re-fetch products for the new valid page
        products = manager.get_all_products(
            search_term=search_term if search_term else None,
            category=category if category else None,
            purchase_location=purchase_location if purchase_location else None,
            sort_by=sort_by,
            sort_order=sort_order,
            page=page,
            per_page=per_page
        )


    # Get filter options
    all_categories = manager.get_all_categories()
    all_purchase_locations = manager.get_all_purchase_locations()

    return render_template(
        'list_products.html',
        products=products,
        current_page=page,
        total_pages=total_pages,
        per_page=per_page,
        search_term=search_term,
        selected_category=category,
        selected_purchase_location=purchase_location,
        sort_by=sort_by,
        sort_order=sort_order,
        categories=all_categories,
        purchase_locations=all_purchase_locations
    )

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

        if not quantity_added:
            errors.append("Quantity added is required.")
        else:
            try:
                # Attempt to parse and validate the quantity.
                # manager._parse_quantity_string should handle basic conversion.
                parsed_qty = manager._parse_quantity_string(quantity_added) # This might raise ValueError if not a number
                if parsed_qty <= 0:
                    errors.append("Quantity added must be a positive amount.")
            except ValueError:
                # This catches errors if quantity_added is not a valid number string
                errors.append("Quantity added must be a valid number.")

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

@app.route('/product_modal_details/<int:product_id>', methods=['GET'])
def product_modal_details(product_id):
    product_details = manager.get_product_details(product_id)

    if not product_details:
        return jsonify({"error": "Product not found"}), 404

    # get_daily_consumption defaults to 30 days
    daily_consumption = manager.get_daily_consumption(product_id)
    # get_monthly_consumption defaults to 12 months
    monthly_consumption = manager.get_monthly_consumption(product_id)
    # Get daily inventory history (defaults to 30 days)
    daily_inventory_history = manager.get_daily_inventory_history(product_id)

    # Ensure all date/datetime objects are converted to ISO format strings for JSON serialization
    # For product_details, this depends on its structure. Assuming it's a dict from DB Row.
    # For consumption data, the manager methods already format dates as strings.

    # --- New data for modal ---
    recipes_containing_product = []
    if product_details.get('name'):
        recipes_containing_product = recipe_mngr.get_recipes_for_product(product_details['name'])

    inventory_concerns = manager.get_inventory_concerns(product_id)

    # Calculate shopping_list_amount_today
    shopping_list_amount_today = 0.0 # Default to 0
    SOBEYS_FREQUENCY_WEEKS = 1
    COSTCO_FREQUENCY_WEEKS = 3

    par_level = product_details.get('par_level', 0.0)
    if par_level is None: par_level = 0.0 # Ensure float if None
    else: par_level = float(par_level)

    purchase_location = product_details.get('purchase_location')
    current_on_hand_inventory = product_details.get('current_on_hand_inventory', 0.0)

    projection_days_for_item = 0
    if purchase_location == 'Sobeys':
        projection_days_for_item = SOBEYS_FREQUENCY_WEEKS * 7
    elif purchase_location == 'Costco':
        projection_days_for_item = COSTCO_FREQUENCY_WEEKS * 7

    if par_level > 0 and projection_days_for_item > 0:
        demand_projection = manager.project_demand(
            product_id,
            lookback_days=30, # Standard lookback
            projection_days=projection_days_for_item
        )
        avg_daily_consumption = 0.0
        if demand_projection.get("success"):
            avg_daily_consumption = demand_projection.get('avg_daily_consumption', 0.0)

        target_stock_after_shopping = par_level + (avg_daily_consumption * projection_days_for_item)
        recommended_purchase_amount = target_stock_after_shopping - current_on_hand_inventory
        shopping_list_amount_today = max(0, round(recommended_purchase_amount, 2))

    return jsonify({
        "product_details": product_details,
        "daily_consumption": daily_consumption,
        "monthly_consumption": monthly_consumption,
        "daily_inventory_history": daily_inventory_history,
        "recipes_containing_product": recipes_containing_product,
        "inventory_concerns": inventory_concerns,
        "shopping_list_amount_today": shopping_list_amount_today,
        # unit_of_measure, current_on_hand_inventory, nearest_expiry_date are already in product_details
    })

if __name__ == '__main__':
    # Debug mode should be False in a production environment
    # Host '0.0.0.0' makes it accessible from network, useful for some environments
    app.run(host='0.0.0.0', port=8080, debug=False, use_reloader=False)
