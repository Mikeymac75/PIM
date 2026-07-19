#!/command/with-contenv bashio

echo "Starting Mac's PIM App..."

# 1. Read configuration from Home Assistant Options
if bashio::config.exists 'users'; then
    USERS_JSON=$(bashio::config 'users')
    PIM_USERS_STRING=$(echo "$USERS_JSON" | jq -r 'if type == "array" then join(",") else . end' 2>/dev/null || echo "$USERS_JSON")
else
    PIM_USERS_STRING="admin:password"
fi

if bashio::config.exists 'secret_key'; then
    SECRET=$(bashio::config 'secret_key')
else
    SECRET="default_secret_key"
fi

# 2. Export Environment Variables for the Flask App
export PIM_USERS="$PIM_USERS_STRING"
export FLASK_SECRET_KEY="$SECRET"
export DATABASE_FILE_PATH="/data/food_app.db"
export PYTHONUNBUFFERED=1
export FLASK_ENABLE_ADMIN_ROUTES=true

# 3. Mealie Integration (optional)
if bashio::config.exists 'mealie_url' && bashio::config.has_value 'mealie_url'; then
    export MEALIE_URL=$(bashio::config 'mealie_url')
    echo "Mealie URL configured: $MEALIE_URL"
fi
if bashio::config.exists 'mealie_api_token' && bashio::config.has_value 'mealie_api_token'; then
    export MEALIE_API_TOKEN=$(bashio::config 'mealie_api_token')
    echo "Mealie API token configured"
fi

echo "PIM configured, starting gunicorn..."

# 4. Start the App using Gunicorn
exec gunicorn --bind 0.0.0.0:8080 --access-logfile - --error-logfile - app:app