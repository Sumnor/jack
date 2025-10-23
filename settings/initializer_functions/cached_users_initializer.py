from typing import Dict
from datetime import datetime, timezone, timedelta
import asyncio
from settings.initializer_functions.supabase_initializer import supabase, SupabaseRegistrationSheet

cached_users = {}
cached_registrations = []
cached_conflicts = []
cached_conflict_data = []

def load_sheet_data():
    try:
        latest_data = load_registration_data()
        cached_users.clear()
        cached_users.update(latest_data)
        print("✅ cached_users updated:", len(cached_users), "users")
    except Exception as e:
        print(f"❌ Failed to load sheet data: {e}")
        import traceback
        print(traceback.format_exc())

def load_registration_data() -> Dict[str, Dict]:
    try:
        records = supabase.select('users')
        user_map = {}
        for record in records:
            discord_id = str(record.get('discord_id', '')).strip()
            discord_username = str(record.get('discord_username', '')).strip().lower()
            nation_id = str(record.get('nation_id', '')).strip()
            aa = str(record.get('aa', '')).strip()
            
            if discord_id and discord_username and nation_id:
                user_map[discord_id] = {
                    'DiscordUsername': discord_username,
                    'NationID': nation_id,
                    'AA': aa
                }
        
        print(f"✅ Loaded {len(user_map)} users from Supabase.")
        return user_map
        
    except Exception as e:
        print(f"❌ Failed to load registration data: {e}")
        import traceback
        print(traceback.format_exc())
        return {}
    
async def daily_refresh_loop():
    while True:
        now = datetime.now(timezone.utc)
        next_midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        wait_seconds = (next_midnight - now).total_seconds()
        await asyncio.sleep(wait_seconds)
        print("🔄 Refreshing all cached sheet data at UTC midnight...")
        load_registration_data()

def get_registration_sheet(guild_id: str = None) -> SupabaseRegistrationSheet:
    return SupabaseRegistrationSheet()