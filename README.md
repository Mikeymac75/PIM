# Food Inventory and Recipe Management System

## Overview

This web application provides a comprehensive solution for managing food inventory, recipes, and meal planning. It helps users track their current stock, log purchases, consume items, manage recipes, generate shopping lists based on needs, and project future inventory levels. The system also supports data import and export using Excel for easy management.

## Features

*   **Inventory Management:**
    *   Track current inventory with details like purchase date, expiry, quantity, and cost.
    *   View historical inventory consumption.
    *   Manage inventory by individual batches.
    *   Log purchases and add new items to stock.
    *   Consume items individually or as part of a recipe.
    *   Upload inventory items via Excel.
*   **Recipe Management:**
    *   Create, edit, and delete recipes with ingredients, instructions, and output yields.
    *   View recipe details, including required ingredients and current availability.
    *   "Make" recipes, automatically deducting ingredients from inventory and optionally adding produced items back to stock.
    *   Upload recipes via Excel.
*   **Product Management:**
    *   Define products with associated categories, units of measure, par levels, and default expiry.
    *   Manage product categories and subcategories.
    *   Upload product definitions via Excel.
*   **Shopping & Planning:**
    *   Generate a list of products needed based on current stock, par levels, and projected consumption.
    *   Maintain a user-specific shopping list.
    *   Log purchases directly from the shopping list.
    *   Export shopping list to Excel.
*   **Projections & Analysis:**
    *   Project future inventory demand based on historical consumption.
    *   Override automated consumption rates for specific products.
    *   View product details including consumption trends, inventory history, and future projections in a modal.
*   **Garden/Production Tracking:**
    *   Manage items grown or produced (e.g., garden produce).
    *   Track planting dates, harvest times, expected yields, and actual harvests.
    *   Record harvests, automatically adding the yield to inventory.
    *   Upload production items via Excel.
*   **Data Management:**
    *   Export various data tables (products, inventory batches, historical consumption, recipes, etc.) to Excel.
    *   Upload historical consumption data.
    *   (Admin) Backup and restore the application database (requires enabling admin routes).

## Tech Stack

*   **Backend:** Python, Flask
*   **Database:** SQLite (default)
*   **Excel Handling:** openpyxl
*   **Frontend:** HTML, CSS, JavaScript (via Flask templates)

## Prerequisites

*   Python 3.7+
*   pip (Python package installer)

## Installation

1.  **Clone the repository:**
    ```bash
    git clone <repository-url>
    cd <repository-directory>
    ```

2.  **Create and activate a virtual environment (recommended):**
    ```bash
    python -m venv venv
    # On Windows
    venv\\Scripts\\activate
    # On macOS/Linux
    source venv/bin/activate
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

## Configuration

The application can be configured using environment variables. You can set these directly in your shell or use a `.env` file (by installing `python-dotenv` and adding `from dotenv import load_dotenv; load_dotenv()` at the beginning of `app.py`).

*   **`FLASK_SECRET_KEY` (Required for sessions):**
    A strong, random key for session management.
    Example generation:
    ```python
    import os
    os.urandom(24).hex()
    ```
    Set it in your environment:
    ```bash
    export FLASK_SECRET_KEY='your_generated_secret_key'
    ```

*   **`DATABASE_FILE_PATH` (Optional):**
    Specifies the path to the SQLite database file.
    Defaults to `food_app.db` in the `instance` directory (e.g., `instance/food_app.db`). The `instance` folder will be created in the same directory as `app.py` if it doesn't exist.
    Example:
    ```bash
    export DATABASE_FILE_PATH='/path/to/your/food_data.db'
    ```

*   **`FLASK_ENABLE_ADMIN_ROUTES` (Optional):**
    Set to `true` to enable admin routes for database backup and restore.
    Example:
    ```bash
    export FLASK_ENABLE_ADMIN_ROUTES='true'
    ```

## Running the Application

1.  **Ensure environment variables are set (especially `FLASK_SECRET_KEY`).**

2.  **Run the Flask application:**
    ```bash
    python app.py
    ```

3.  **Access the application:**
    Open your web browser and go to `http://localhost:8080` (or `http://0.0.0.0:8080`).

## File Structure (Simplified)

```
.
├── app.py                   # Main Flask application, routes
├── Food_manager.py          # Handles inventory, product, and data logic
├── RecipeManager.py         # Handles recipe logic
├── requirements.txt         # Python dependencies
├── instance/                # Created automatically for database, backups
│   └── food_app.db          # Default SQLite database file
│   └── backups/             # Default backup location (if admin routes used)
├── static/                  # CSS, JavaScript files
│   ├── style.css
│   └── js/
│       └── product_modal.js
├── templates/               # HTML templates
├── tests/                   # Pytest tests
└── README.md                # This file
```

## Usage

Navigate the application using the links in the header/navigation bar. Key sections include:

*   **Home:** Main dashboard.
*   **Inventory & Usage Links:** Access current inventory, historical data, log purchases, consume items, etc.
*   **Recipe Links:** Add, view, and manage recipes.
*   **Products Links:** Manage product definitions, categories, and perform Excel uploads/exports for products.
*   **Garden:** Track home-grown or produced items.
*   **Shopping Lists:** View products needed and manage your shopping list.
*   **Projections:** View inventory projections.
*   **Data Export:** Export various data tables.
*   **Admin (if enabled):** Backup and Restore database.

Excel uploads generally expect specific column headers. Refer to the respective upload pages or sample data if available for correct formats.

## Contributing

Contributions are welcome! Please feel free to open an issue to discuss potential changes or submit a pull request. (Further guidelines may be added in the future).

## License

This project is currently unlicensed. (Or specify a license if one is chosen, e.g., MIT License).
