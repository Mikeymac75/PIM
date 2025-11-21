#!/usr/bin/with-contenv bashio

echo "Starting Mac's PIM App..."

# 1. Read configuration from Home Assistant Options
USERS_JSON=$(bashio::config 'users')
SECRET=$(bashio::config 'secret_key')

# Convert JSON list to comma-separated string for app.py
PIM_USERS_STRING=$(echo "$USERS_JSON" | jq -r 'join(",")')

# 2. Export Environment Variables for the Flask App
export PIM_USERS="$PIM_USERS_STRING"
export FLASK_SECRET_KEY="$SECRET"
export DATABASE_FILE_PATH="/data/food_app.db"

# 3. Start the App using Gunicorn for stability
# Binding to 0.0.0.0:8080 as required by config.yaml
gunicorn --bind 0.0.0.0:8080 app:app
