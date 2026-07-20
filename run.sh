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

# 3b. API token for Home Assistant / automation clients (optional)
if bashio::config.exists 'api_token' && bashio::config.has_value 'api_token'; then
    export PIM_API_TOKEN=$(bashio::config 'api_token')
    echo "API token configured for automation clients"
fi

# 3c. Automatic daily database backups into /share so external backup
# systems (e.g. PBS) sweep them up with their normal schedule.
export PIM_BACKUP_DIR="/share/pim_backups"
if bashio::config.exists 'backup_hour' && bashio::config.has_value 'backup_hour'; then
    export PIM_BACKUP_HOUR=$(bashio::config 'backup_hour')
fi
if bashio::config.exists 'backup_keep' && bashio::config.has_value 'backup_keep'; then
    export PIM_BACKUP_KEEP=$(bashio::config 'backup_keep')
fi

echo "PIM configured, starting gunicorn..."

# 4. Start the App using Gunicorn
exec gunicorn --bind 0.0.0.0:8080 --access-logfile - --error-logfile - app:app