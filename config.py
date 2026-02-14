import os

# Render environment variables
BOT_TOKEN = os.environ.get('BOT_TOKEN')
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable is not set!")

# Admin IDs (space separated string -> list)
admin_ids_str = os.environ.get('ADMIN_IDS', '')
ADMIN_IDS = [int(id.strip()) for id in admin_ids_str.split(',') if id.strip()]