import os
import gspread
import requests
from oauth2client.service_account import ServiceAccountCredentials
import json
from typing import Optional
from datetime import datetime, timezone, timedelta
import asyncio
from bot_instance import bot

def get_credentials():
    creds_str = os.environ.get("GOOGLE_CREDENTIALS")
    if not creds_str:
        raise RuntimeError("GOOGLE_CREDENTIALS not found in environment.")
    try:
        creds_json = json.loads(creds_str)
        return creds_json
    except Exception as e:
        raise RuntimeError(f"Failed to load GOOGLE_CREDENTIALS: {e}")

def get_client():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(get_credentials(), scope)
    client = gspread.authorize(creds)
    return client

from settings_multi import get_dm_sheet, get_alliance_sheet

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

def get_sheet_s(sheet_name: str):
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(get_credentials(), scope)
    client = gspread.authorize(creds)
    return client.open(sheet_name).sheet1

def get_registration_sheet(guild_id):
    client = get_client()
    sheet_name = f"Registrations"
    
    try:
        spreadsheet = client.open(sheet_name)
        sheet = spreadsheet.sheet1
        
        return sheet
    except gspread.SpreadsheetNotFound:
        print(f"❌ Sheet '{sheet_name}' not found.")
        '''try:
            spreadsheet = client.create(sheet_name)
            sheet = spreadsheet.sheet1
            sheet.update('A1:C1', [['DiscordUsername', 'DiscordID', 'NationID']])
            print(f"✅ Created new sheet: '{sheet_name}'")
            print(f"🔄 Auto-migrating data from main 'Registrations' sheet...")
            migrate_data_to_guild_sheet(guild_id)
            
            return sheet
        except Exception as create_error:
            print(f"❌ Failed to create sheet '{sheet_name}': {create_error}")
            raise'''
    except Exception as e:
        print(f"❌ Unexpected error opening sheet '{sheet_name}': {e}")
        raise

cached_users = {}
cached_registrations = {}
cached_conflicts = []
cached_conflict_data = []

from datetime import datetime, timezone
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
        load_registration_data()
        
        if not hasattr(bot, '_refresh_loops'):
            bot._refresh_loops = set()
        if 'global' not in bot._refresh_loops:
            bot.loop.create_task(daily_refresh_loop())
            bot._refresh_loops.add('global')
                
    except Exception as e:
        print(f"❌ Failed to load sheet data: {e}")
        import traceback
        print(traceback.format_exc())
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")

def load_registration_data():
    global cached_users, cached_registrations

    guild_id = "I'm too lazy to remove it from get_registration_sheet so this is a"

    try:
        sheet = get_registration_sheet(guild_id)
        print(f"📄 Sheet object: {sheet}")
        print(f"📘 Sheet title: {sheet.title}")

        records = sheet.get_all_records()
        print(f"📥 Records fetched: {len(records)}")

        user_map = {}

        for record in records:
            discord_id = str(record.get('DiscordID', '')).strip()
            discord_username = str(record.get('DiscordUsername', '')).strip().lower()
            nation_id = str(record.get('NationID', '')).strip()
            aa = str(record.get('AA', '')).strip()  # Add AA field

            if discord_id and discord_username and nation_id:
                user_map[discord_id] = {
                    'DiscordUsername': discord_username,
                    'NationID': nation_id,
                    'AA': aa  # Include AA in the user data
                }
        cached_users = user_map
        print(cached_users)
        cached_registrations = records

        print(f"✅ Loaded {len(user_map)} users from registration sheet.")

    except Exception as e:
        print(f"❌ Failed to load registration sheet data: {e}")
        import traceback
        print(traceback.format_exc())

def save_to_alliance_net(data_row, guild_id):
    try:
        sheet = get_alliance_sheet(guild_id)
        sheet.append_row(data_row)
        print("✅ Data saved to Alliance Net")
    except Exception as e:
        print(f"❌ Failed to save to Alliance Net: {e}")

def save_dm_to_sheet(sender_name, recipient_name, message):
    sheet = get_dm_sheet()
    headers = sheet.row_values(1)  
    data = {
        "Timestamp": datetime.now(timezone.utc).isoformat(),
        "Sender": sender_name,
        "Recipient": recipient_name,
        "Message": message
    }

    
    row = [data.get(header, "") for header in headers]
    sheet.append_row(row)

def get_ticket_config(message_id: int) -> Optional[dict]:
    sheet = get_ticket_sheet()
    records = sheet.get_all_records()
    
    for row in records:
        if str(row["message_id"]) == str(message_id):
            return {
                'embed_description': row["message"],  # This is the embed description
                'category_id': int(row["category"]) if row["category"] else None
            }
    return None

def get_verify_conf(message_id: int) -> Optional[dict]:
    sheet = get_ticket_sheet()
    records = sheet.get_all_records()

    for row in records:
        if str(row["message_id"]) == str(message_id):
            return {
                'verify': row.get("register", "🎟️ Support Ticket")  # Using register field for title
            }
    return None

def save_ticket_config(message_id: int, embed_description: str, category_id: int, embed_title: str):
    sheet = get_ticket_sheet()
    sheet.append_row([str(message_id), embed_description, str(category_id), embed_title])

def get_ticket_sheet():
    client = get_client()
    sheet = client.open("Tickets")
    try:
        return sheet.worksheet("Tickets")
    except:
        return sheet.add_worksheet(title="Tickets", rows="1000", cols="3")