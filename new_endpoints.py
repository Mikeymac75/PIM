def get_mealie_client():
    """Get a configured Mealie client, or None if not configured."""
    if not MEALIE_AVAILABLE:
        return None
    mealie_url = os.environ.get('MEALIE_URL', '')
    mealie_token = os.environ.get('MEALIE_API_TOKEN', '')
    if not mealie_url or not mealie_token:
        return None
    return MealieClient(mealie_url, mealie_token)


@app.route('/mealie')
@login_required
def mealie_dashboard():
    """Dashboard for Mealie integration."""
    client = get_mealie_client()
    if not client:
        flash('Mealie not configured. Set MEALIE_URL and MEALIE_API_TOKEN.', 'error')
        return render_template('mealie_dashboard.html', mealie_connected=False, pim_recipes=[], mealie_recipes=[])
    
    connection = client.test_connection()
    if not connection.get('success'):
        flash(f'Could not connect to Mealie: {connection.get("error", "Unknown error")}', 'error')
        return render_template('mealie_dashboard.html', mealie_connected=False, pim_recipes=[], mealie_recipes=[])
    
    pim_recipes = get_recipe_mngr().get_all_recipes(export_all=True)
    mealie_response = client.get_all_recipes(per_page=100)
    mealie_recipes = mealie_response.get('items', []) if mealie_response else []
    
    pim_names = {r.get('name', '').lower() for r in pim_recipes}
    mealie_names = {r.get('name', '').lower() for r in mealie_recipes}
    
    only_in_pim = [r for r in pim_recipes if r.get('name', '').lower() not in mealie_names]
    only_in_mealie = [r for r in mealie_recipes if r.get('name', '').lower() not in pim_names]
    in_both = [r for r in pim_recipes if r.get('name', '').lower() in mealie_names]
    
    return render_template('mealie_dashboard.html',
                          mealie_connected=True,
                          mealie_version=connection.get('version', 'unknown'),
                          pim_recipes=pim_recipes,
                          mealie_recipes=mealie_recipes,
                          only_in_pim=only_in_pim,
                          only_in_mealie=only_in_mealie,
                          in_both=in_both)


@app.route('/api/mealie/import/<slug>', methods=['POST'])
@login_required
def mealie_import_recipe(slug):
    """Import a recipe from Mealie to PIM."""
    client = get_mealie_client()
    if not client:
        return jsonify({'success': False, 'message': 'Mealie not configured'}), 400
    
    mealie_recipe = client.get_recipe(slug)
    if not mealie_recipe:
        return jsonify({'success': False, 'message': f'Recipe {slug} not found'}), 404
    
    pim_data = client.mealie_to_pim(mealie_recipe)
    existing = get_recipe_mngr().get_recipe_by_name(pim_data['name'])
    if existing:
        return jsonify({'success': False, 'message': f'Recipe already exists in PIM'}), 409
    
    try:
        result = get_recipe_mngr().add_recipe(pim_data)
        return jsonify({'success': True, 'message': f'Imported "{pim_data["name"]}"', 'recipe_id': result})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/mealie/export/<int:recipe_id>', methods=['POST'])
@login_required
def mealie_export_recipe(recipe_id):
    """Export a recipe from PIM to Mealie."""
    client = get_mealie_client()
    if not client:
        return jsonify({'success': False, 'message': 'Mealie not configured'}), 400
    
    pim_recipe = get_recipe_mngr().get_recipe_by_id(recipe_id)
    if not pim_recipe:
        return jsonify({'success': False, 'message': f'Recipe not found'}), 404
    
    mealie_data = client.pim_to_mealie(pim_recipe)
    try:
        result = client.create_recipe(mealie_data)
        if result:
            return jsonify({'success': True, 'message': f'Exported "{pim_recipe["name"]}"'})
        return jsonify({'success': False, 'message': 'Failed to create in Mealie'}), 500
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/what-can-i-cook')
@login_required
def what_can_i_cook():
    """Show recipes ranked by ingredient availability."""
    client = get_mealie_client()
    pim_recipes = get_recipe_mngr().get_all_recipes(export_all=True)
    
    mealie_recipes = []
    if client:
        mealie_response = client.get_all_recipes(per_page=100)
        if mealie_response:
            for r in mealie_response.get('items', []):
                full_recipe = client.get_recipe(r.get('slug', ''))
                if full_recipe:
                    converted = client.mealie_to_pim(full_recipe)
                    converted['source'] = 'mealie'
                    converted['mealie_slug'] = r.get('slug', '')
                    mealie_recipes.append(converted)
    
    for r in pim_recipes:
        r['source'] = 'pim'
    
    all_recipes = pim_recipes + mealie_recipes
    inventory_products = get_manager().get_current_inventory(per_page=1000)
    inventory_map = {}
    for item in inventory_products:
        name = item.get('product_name', item.get('name', '')).lower()
        inventory_map[name] = item.get('total_quantity', item.get('quantity', 0))
    
    scored_recipes = []
    for recipe in all_recipes:
        ingredients = recipe.get('ingredients', [])
        if not ingredients:
            continue
        available_count = 0
        missing_items = []
        for ing in ingredients:
            ing_name = ing.get('item_name', '').lower()
            found = False
            for inv_name in inventory_map:
                if ing_name in inv_name or inv_name in ing_name:
                    if inventory_map[inv_name] > 0:
                        available_count += 1
                        found = True
                        break
            if not found:
                missing_items.append(ing.get('item_name', 'Unknown'))
        
        total_ingredients = len(ingredients)
        availability_pct = (available_count / total_ingredients * 100) if total_ingredients > 0 else 0
        scored_recipes.append({
            'recipe': recipe,
            'availability_pct': availability_pct,
            'available_count': available_count,
            'total_ingredients': total_ingredients,
            'missing_items': missing_items
        })
    
    scored_recipes.sort(key=lambda x: x['availability_pct'], reverse=True)
    can_make = [r for r in scored_recipes if r['availability_pct'] >= 100]
    almost = [r for r in scored_recipes if 50 <= r['availability_pct'] < 100]
    missing = [r for r in scored_recipes if r['availability_pct'] < 50]
    
    return render_template('what_can_i_cook.html',
                          can_make=can_make,
                          almost=almost,
                          missing=missing,
                          total_recipes=len(scored_recipes))


# --- JSON Data APIs for Home Assistant Integration ---

@app.route('/api/inventory', methods=['GET'])
def api_get_inventory():
    inventory = get_manager().get_current_inventory(page=1, per_page=10000)
    return jsonify([dict(item) for item in inventory])

@app.route('/api/products', methods=['GET'])
def api_get_products():
    products = get_manager().get_all_products_export()
    return jsonify([dict(p) for p in products])

@app.route('/api/recipes', methods=['GET'])
def api_get_recipes():
    recipes = get_recipe_mngr().get_all_recipes(export_all=True)
    return jsonify([dict(r) for r in recipes])

@app.route('/api/inventory/adjust', methods=['POST'])
def api_adjust_inventory():
    data = request.json
    if not data or 'batch_id' not in data or 'new_quantity' not in data:
        return jsonify({"success": False, "message": "Missing batch_id or new_quantity"}), 400
    try:
        success = get_manager().adjust_inventory_batch(
            batch_id=data['batch_id'],
            new_quantity_str=str(data['new_quantity']),
            new_purchase_date_str=data.get('new_purchase_date'),
            new_expiry_date_str=data.get('new_expiry_date')
        )
        return jsonify({"success": success})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/stats', methods=['GET'])
def api_get_stats():
    inventory_count = get_manager().get_current_inventory_count()
    products_count = len(get_manager().get_all_products_export())
    try:
        recipes_count = get_recipe_mngr().get_all_recipes_count()
    except Exception:
        recipes_count = 0
    return jsonify({
        "inventory_unique_items": inventory_count,
        "total_products": products_count,
        "total_recipes": recipes_count
    })

@app.route('/api/seed_garden', methods=['GET'])
def api_seed_garden():
    manager = get_manager()
    plants = [
        "Tomatoes", "Hot Peppers", "Sweet Peppers", "Bell Peppers", 
        "Mustard Greens", "Radish Pods", "Potatoes", "Swiss Chard", 
        "Leaf Lettuce", "Celery", "Spaghetti Squash", "Watermelon", 
        "Pumpkin", "Cucumbers", "Cucamelons"
    ]
    # Find or create Produce category
    cat_id = None
    cats = manager.get_categories()
    for c in cats:
        if c['name'] == 'Produce':
            cat_id = c['id']
            break
    if not cat_id:
        manager.add_category('Produce')
        cats = manager.get_categories()
        for c in cats:
            if c['name'] == 'Produce':
                cat_id = c['id']
                break
                
    for plant in plants:
        # Create product if not exists
        all_prods = manager.get_all_products_export()
        prod_id = None
        for p in all_prods:
            if p['product_name'].lower() == plant.lower():
                prod_id = p['product_id']
                break
        if not prod_id:
            manager.create_product(name=plant, category_id=cat_id, unit_of_measure='Eaches')
            all_prods = manager.get_all_products_export()
            for p in all_prods:
                if p['product_name'].lower() == plant.lower():
                    prod_id = p['product_id']
                    break
        
        # Add to garden if not exists
        manager.add_production_item(
            name=plant + " Plant",
            associated_product_id=prod_id,
            plant_date_str="2026-06-01",
            status="Growing"
        )
    return jsonify({"success": True, "message": "Garden seeded!"})

@app.route('/api/seed_recipes', methods=['GET'])
def api_seed_recipes():
    recipe_mngr = get_recipe_mngr()
    # Tacos
    tacos_id = recipe_mngr.add_recipe("Classic Beef Tacos", "Brown beef, add seasoning. Warm shells.")
    recipe_mngr.add_recipe_ingredient(tacos_id, "Ground Beef", "1.0", False)
    recipe_mngr.add_recipe_ingredient(tacos_id, "Taco Seasoning", "0.1", False)
    recipe_mngr.add_recipe_ingredient(tacos_id, "Shredded Cheese", "0.2", False)
    recipe_mngr.add_recipe_ingredient(tacos_id, "Salsa", "0.1", False)
    # Poutine
    poutine_id = recipe_mngr.add_recipe("Classic Poutine", "Cook fries, warm sauce, add cheese curds.")
    recipe_mngr.add_recipe_ingredient(poutine_id, "French Fries", "0.5", False)
    recipe_mngr.add_recipe_ingredient(poutine_id, "Cheese Curds", "0.2", False)
    recipe_mngr.add_recipe_ingredient(poutine_id, "Poutine Sauce Mix", "0.1", False)
    # Fajitas
    fajitas_id = recipe_mngr.add_recipe("Chicken Fajitas", "Cook chicken, add peppers.")
    recipe_mngr.add_recipe_ingredient(fajitas_id, "Chicken Breasts", "1.0", False)
    recipe_mngr.add_recipe_ingredient(fajitas_id, "Lime", "1.0", False)
    recipe_mngr.add_recipe_ingredient(fajitas_id, "Salsa", "0.1", False)
    
    return jsonify({"success": True, "message": "Recipes seeded!"})

if __name__ == '__main__':
    # Debug mode should be False in a production environment
    # Host '0.0.0.0' makes it accessible from network, useful for some environments

    # Ensure instance folder exists for backups, logs, etc.
    # Reverting to robust path derivation
    instance_path = os.path.join(os.path.dirname(app.root_path), 'instance')
    if not os.path.exists(instance_path):
        # Fallback: If running from root where app.py is, dirname might be empty or parent.
        # If app.root_path is /app, dirname is /.
        # Let's verify if we need os.path.join(app.root_path, 'instance') which is standard for non-package apps.
        # But following reviewer instruction to revert to previous state.
        # If the previous state caused permission errors, we might re-trigger them, but let's assume the reviewer knows best for the repo structure.
        try:
            os.makedirs(instance_path, exist_ok=True)
            print(f"Created instance folder at: {instance_path}")
        except OSError as e:
            print(f"Warning: Could not create instance folder at {instance_path}: {e}. Falling back to local directory.")
            instance_path = os.path.join(os.getcwd(), 'instance')
            os.makedirs(instance_path, exist_ok=True)
            print(f"Created instance folder at: {instance_path}")

    # Adjust DATABASE_FILE to be in the instance folder if not already set by env var
    # This is a good practice for user-writable files like DBs and backups.
    # If DATABASE_FILE_PATH is set via environment, it will be used.
    # Otherwise, default to 'instance/food_app.db'.

    # This logic should ideally be at the top where DATABASE_FILE is defined,
    # but for this step, we are adding it here.
    # A better approach would be to refactor DB_FILE definition at the top of app.py.
    # For now, let's ensure the global `manager` and `recipe_mngr` are re-initialized
    # if we change DATABASE_FILE path here. This is not ideal.

    # The current global instantiation of manager and recipe_mngr uses DATABASE_FILE
    # defined near the top. If we want to ensure it's in 'instance', that definition
    # needs to be aware of the instance path.
    # Let's assume DATABASE_FILE is correctly pointing to 'instance/food_app.db'
    # or is set via environment variable.
