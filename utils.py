import os
import requests
from typing import Optional, Dict, List
from datetime import datetime, timezone, timedelta
import asyncio


SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

class SupabaseClient:
    def __init__(self):
        self.base_url = SUPABASE_URL.rstrip('/')
        self.headers = {
            'apikey': SUPABASE_KEY,
            'Authorization': f'Bearer {SUPABASE_KEY}',
            'Content-Type': 'application/json',
            'Prefer': 'return=representation'
        }
    
    def _make_request(self, method: str, endpoint: str, data: dict = None, params: dict = None):
        url = f"{self.base_url}/{endpoint}"
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=self.headers, params=params)
            elif method == 'POST':
                response = requests.post(url, headers=self.headers, json=data)
            elif method == 'PATCH':
                response = requests.patch(url, headers=self.headers, json=data)
            elif method == 'DELETE':
                response = requests.delete(url, headers=self.headers, params=params)
            
            response.raise_for_status()
            return response.json() if response.text else None
            
        except requests.exceptions.RequestException as e:
            print(f"Supabase API error: {e}")
            if hasattr(e.response, 'text'):
                print(f"Response: {e.response.text}")
            raise
    
    def select(self, table: str, columns: str = "*", filters: dict = None):
        params = {"select": columns}
        if filters:
            for key, value in filters.items():
                params[key] = f"eq.{value}"
        return self._make_request('GET', table, params=params)
    
    def insert(self, table: str, data: dict):
        return self._make_request('POST', table, data=data)
    
    def update(self, table: str, data: dict, filters: dict):
        params = {}
        for key, value in filters.items():
            params[key] = f"eq.{value}"
        endpoint = f"{table}?" + "&".join([f"{k}={v}" for k, v in params.items()])
        return self._make_request('PATCH', endpoint, data=data)

supabase = SupabaseClient()

def get_prices():
    API_KEY = os.getenv("API_KEY")
    if not API_KEY:
        raise ValueError("API key not found for this guild.")

    GRAPHQL_URL = f"https://api.politicsandwar.com/graphql?api_key={API_KEY}"
    prices_query = """
    {
      top_trade_info {
        resources {
          resource
          average_price
        }
      }
    }
    """
    try:
        response = requests.post(
            GRAPHQL_URL,
            json={"query": prices_query},
            headers={"Content-Type": "application/json"}
        )
        return response.json()
    except Exception as e:
        print(f"Error fetching resource prices: {e}")
        raise

cached_users = {}
cached_registrations = []
cached_conflicts = []
cached_conflict_data = []

async def daily_refresh_loop():
    while True:
        now = datetime.now(timezone.utc)
        next_midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        wait_seconds = (next_midnight - now).total_seconds()
        await asyncio.sleep(wait_seconds)
        print("🔄 Refreshing all cached sheet data at UTC midnight...")
        load_registration_data()

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

active_war_rooms: Dict[str, Dict] = {}


async def load_active_war_rooms():
    """Populate active_war_rooms from Supabase"""
    global active_war_rooms
    try:
        records = supabase.select("war_rooms")  # depends on your supabase wrapper
        active_war_rooms = {}

        for record in records:
            war_id = str(record.get("war_id", "")).strip()
            if not war_id:
                continue

            active_war_rooms[war_id] = {
                "channel_id": str(record.get("channel_id", "")).strip(),
                "participants": record.get("participants", {}),
                "guild_id": str(record.get("guild_id", "")).strip(),
                "enemy_id": str(record.get("enemy_id", "")).strip(),
                "main_embed_id": record.get("main_embed_id"),
                "total_losses": record.get("total_losses") or {
                    'att_soldiers': 0, 'att_tanks': 0, 'att_aircraft': 0, 'att_ships': 0,
                    'def_soldiers': 0, 'def_tanks': 0, 'def_aircraft': 0, 'def_ships': 0
                },
                "last_action": record.get("last_action") or {},
                "peace_offered": record.get("peace_offered", False),
            }

        print(f"✅ Loaded {len(active_war_rooms)} active war rooms from Supabase.")

    except Exception as e:
        print(f"❌ Error loading war rooms from database: {e}")

async def delete_war_room_from_db(war_id: str):
    """Delete a war room from Supabase"""
    try:
        response = supabase.table("war_rooms").delete().eq("war_id", str(war_id).strip()).execute()

        if hasattr(response, "error") and response.error:
            print(f"❌ Error deleting war room {war_id}: {response.error}")
        else:
            print(f"🗑️ Deleted war room {war_id} from database")

    except Exception as e:
        print(f"❌ Error deleting war room {war_id} from database: {e}")

        
async def save_war_room_to_db(war_id: str, war_room_data: Dict):
    """Save or update a war room in Supabase"""
    try:
        # Shape matches what load_active_war_rooms expects
        data = {
            "war_id": str(war_id).strip(),
            "guild_id": str(war_room_data.get("guild_id", "")).strip(),
            "channel_id": str(war_room_data.get("channel_id", "")).strip(),
            "participants": war_room_data.get("participants", {}),
            "enemy_id": str(war_room_data.get("enemy_id", "")).strip(),
            "main_embed_id": war_room_data.get("main_embed_id"),
            "total_losses": war_room_data.get("total_losses") or {
                'att_soldiers': 0, 'att_tanks': 0, 'att_aircraft': 0, 'att_ships': 0,
                'def_soldiers': 0, 'def_tanks': 0, 'def_aircraft': 0, 'def_ships': 0
            },
            "last_action": war_room_data.get("last_action") or {},
            "peace_offered": war_room_data.get("peace_offered", False),
        }

        # Upsert via Supabase client (same style as load)
        response = supabase.table("war_rooms").upsert(data).execute()

        if hasattr(response, "error") and response.error:
            print(f"❌ Error saving war room {war_id}: {response.error}")
        else:
            print(f"💾 Saved war room {war_id} to database")

    except Exception as e:
        print(f"❌ Error saving war room {war_id} to database: {e}")

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

class SupabaseRegistrationSheet:
    def get_all_records(self) -> List[Dict]:
        try:
            records = supabase.select('users')
            formatted_records = []
            for record in records:
                formatted_records.append({
                    'DiscordUsername': record.get('discord_username', ''),
                    'DiscordID': record.get('discord_id', ''),
                    'NationID': record.get('nation_id', ''),
                    'AA': record.get('aa', '')
                })
            return formatted_records
        except Exception as e:
            print(f"❌ Failed to get all records: {e}")
            return []
    
    def append_row(self, row_data: List):
        try:
            if len(row_data) >= 3:
                data = {
                    'discord_username': row_data[0],
                    'discord_id': str(row_data[1]),
                    'nation_id': str(row_data[2]),
                    'aa': row_data[3] if len(row_data) > 3 else ''
                }
                result = supabase.insert('users', data)
                print(f"✅ Added registration: {data}")
                return result
            else:
                raise ValueError("Row data must contain at least 3 elements")
        except Exception as e:
            print(f"❌ Failed to append row: {e}")
            raise
    
    def update_acell(self, cell_range: str, value: str):
        try:
            records = self.get_all_records()
            if records:
                last_record = records[-1]
                nation_id = last_record['NationID']
                supabase.update('users', {'aa': value}, {'nation_id': nation_id})
                print(f"✅ Updated AA for nation {nation_id}: {value}")
        except Exception as e:
            print(f"❌ Failed to update cell: {e}")

def get_registration_sheet(guild_id: str = None) -> SupabaseRegistrationSheet:
    return SupabaseRegistrationSheet()

def save_to_alliance_net(data_row: List, guild_id: str):
    try:
        if len(data_row) >= 14:
            data = {
                'guild_id': guild_id,
                'time_t': data_row[0] if data_row[0] else datetime.now(timezone.utc).isoformat(),
                'total_money': int(data_row[1]) if data_row[1] else 0,
                'money': int(data_row[2]) if data_row[2] else 0,
                'food': int(data_row[3]) if data_row[3] else 0,
                'gasoline': int(data_row[4]) if data_row[4] else 0,
                'munitions': int(data_row[5]) if data_row[5] else 0,
                'steel': int(data_row[6]) if data_row[6] else 0,
                'aluminum': int(data_row[7]) if data_row[7] else 0,
                'bauxite': int(data_row[8]) if data_row[8] else 0,
                'lead': int(data_row[9]) if data_row[9] else 0,
                'iron': int(data_row[10]) if data_row[10] else 0,
                'oil': int(data_row[11]) if data_row[11] else 0,
                'coal': int(data_row[12]) if data_row[12] else 0,
                'uranium': int(data_row[13]) if data_row[13] else 0
            }
            supabase.insert('alliance_snapshots', data)
            print("✅ Data saved to Alliance Net")
        else:
            raise ValueError("Data row must contain at least 14 elements")
    except Exception as e:
        print(f"❌ Failed to save to Alliance Net: {e}")

def save_dm_to_sheet(sender_name: str, recipient_name: str, message: str):
    try:
        data = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'sender': sender_name,
            'recipient': recipient_name,
            'message': message
        }
        supabase.insert('dm_logs', data)
        print("✅ DM logged to Supabase")
    except Exception as e:
        print(f"❌ Failed to save DM log: {e}")

def get_ticket_config(message_id: int) -> Optional[dict]:
    try:
        records = supabase.select('ticket_configs', filters={'message_id': str(message_id)})
        if records:
            row = records[0]
            return {
                'message': row.get("message", ""),
                'category': int(row["category_id"]) if row.get("category_id") else None
            }
        return None
    except Exception as e:
        print(f"❌ Failed to get ticket config: {e}")
        return None

def get_verify_conf(message_id: int) -> Optional[dict]:
    try:
        records = supabase.select('ticket_configs', filters={'message_id': str(message_id)})
        if records:
            row = records[0]
            return {
                'verify': row.get("register", "🎟️ Support Ticket")
            }
        return None
    except Exception as e:
        print(f"❌ Failed to get verify config: {e}")
        return None

def save_ticket_config(message_id: int, embed_description: str, category_id: int, embed_title: str):
    try:
        data = {
            'message_id': str(message_id),
            'message': embed_description,
            'category_id': category_id,
            'register': embed_title
        }
        supabase.insert('ticket_configs', data)
        print("✅ Ticket config saved to Supabase")
    except Exception as e:
        print(f"❌ Failed to save ticket config: {e}")


def get_alliance_sheet(guild_id):
    class AllianceSheetWrapper:
        def __init__(self, guild_id):
            self.guild_id = guild_id
        
        def append_row(self, row_data):
            save_to_alliance_net(row_data, self.guild_id)
    
    return AllianceSheetWrapper(guild_id)

def get_dm_sheet():
    class DMSheetWrapper:
        def append_row(self, row_data):
            if len(row_data) >= 3:
                save_dm_to_sheet(row_data[1], row_data[2], row_data[3])
        
        def row_values(self, row_num):
            return ["Timestamp", "Sender", "Recipient", "Message"]
    
    return DMSheetWrapper()

def get_ticket_sheet():
    class TicketSheetWrapper:
        def get_all_records(self):
            try:
                records = supabase.select('ticket_configs')
                formatted = []
                for record in records:
                    formatted.append({
                        'message_id': record.get('message_id', ''),
                        'message': record.get('embed_description', ''),
                        'category': record.get('category_id', ''),
                        'register': record.get('register', '🎟️ Support Ticket')
                    })
                return formatted
            except Exception as e:
                print(f"❌ Failed to get ticket records: {e}")
                return []
        
        def append_row(self, row_data):
            if len(row_data) >= 4:
                save_ticket_config(int(row_data[0]), row_data[1], int(row_data[2]), row_data[3])
    
    return TicketSheetWrapper()
