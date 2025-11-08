from datetime import datetime, timezone
from typing import Optional, Dict, List, Set
import requests
from settings.bot_instance import WHITEKEY, BOT_KEY
from databases.sql.databases import SafekeepDB, MaterialsDB
from settings.settings_multi import get_api_key_for_interaction
from settings.initializer_functions.resource_prices import ALL_RESOURCES
from databases.sql.data_puller import get_bank_data_sql_by_everything

CONFIG_OFFSHORE_AA_ID = 14207
CONFIG_DEPOSIT_NOTE = "Jack Safekeep"

config = None
safekeep_db = None
materials_db = None
pnw_api = None
stored_white_keys = {}
processed_transaction_ids: Set[int] = set()
warned_nations: Dict[int, str] = {}
try:
    from settings.initializer_functions.cached_users_initializer import cached_users
except ImportError:
    cached_users = {}

class PnWAPI:
    def __init__(self, api_key: str, bot_key: str):
        self.api_key = api_key
        self.bot_key = bot_key

    def get_whitekey_for_aa(self, aa_id: int) -> str:
        for key_info in stored_white_keys.values():
            if key_info.get("aa_id") == aa_id:
                return key_info["key"]

        raise ValueError(f"No WHITEKEY found for AA ID {aa_id}")
    
    def execute_query(self, query: str, account_api_key: str = None) -> Optional[Dict]:
        API_URL = f"https://api.politicsandwar.com/graphql?api_key={account_api_key}"
        if account_api_key is None:
            account_api_key = WHITEKEY

        headers = {
            "Content-Type": "application/json",
            "X-Bot-Key": BOT_KEY,
            "X-Api-Key": WHITEKEY
        }

        try:
            response = requests.post(API_URL, json={"query": query}, headers=headers, timeout=30)

            if response.status_code == 401:
                print(f"[ERROR] Unauthorized - X-Api-Key: {account_api_key[:4]}..., X-Bot-Key: {BOT_KEY[:4]}...")
                print("Response text:", response.text)
                return None

            if not response.ok:
                print(f"[ERROR] HTTP {response.status_code}: {response.text}")
                return None

            data = response.json()

            if "errors" in data:
                print(f"[ERROR] GraphQL errors: {data}")
                return None

            return data

        except requests.Timeout:
            print("[ERROR] Request timeout")
            return None
        except Exception as e:
            print(f"[ERROR] Exception during API call: {e}")
            import traceback
            traceback.print_exc()
            return None

        
    def get_alliance_info(self, alliance_id: int) -> Optional[Dict]:
        aa_id = None
        for key_info in stored_white_keys.values():
            if key_info.get("aa_id"):
                aa_id = key_info["aa_id"]
                break

        if aa_id is None:
            print(f"[ERROR] No WHITEKEY/AA found for alliance {alliance_id}")
            return None

        try:
            whitekey = self.get_whitekey_for_aa(aa_id)
        except ValueError as e:
            print(f"[ERROR] {e}")
            return None

        query = f"""
        {{
        alliances(id: {alliance_id}, first: 1) {{
            data {{
            id
            name
            money
            coal
            oil
            uranium
            iron
            bauxite
            lead
            gasoline
            munitions
            steel
            aluminum
            food
            }}
        }}
        }}
        """

        result = self.execute_query(query=query, account_api_key=whitekey)
        if result and result.get("data", {}).get("alliances", {}).get("data"):
            alliances = result["data"]["alliances"]["data"]
            return alliances[0] if alliances else None

        return None

    
    def get_nation_info(self, nation_id: int, interaction) -> Optional[Dict]:
        api_key = get_api_key_for_interaction(interaction)
        query = f"""
        {{
          nations(id: {nation_id}, first: 1) {{
            data {{
              id
              nation_name
              leader_name
              alliance_id
              alliance {{
                id
                name
              }}
            }}
          }}
        }}
        """
        
        result = self.execute_query(query, api_key)
        if result and result.get("data", {}).get("nations", {}).get("data"):
            nations = result["data"]["nations"]["data"]
            return nations[0] if nations else None
        return None
    
    def withdraw_to_nation(self, nation_id: int, resources: Dict[str, float], note: str = "Discord withdrawal") -> bool:
        valid_resources = [
            "money", "coal", "oil", "uranium", "iron", "bauxite",
            "lead", "gasoline", "munitions", "steel", "aluminum", "food"
        ]
        resource_params = [f"{res}: {resources.get(res, 0)}" for res in valid_resources]
        if note:
            resource_params.append(f'note: "{note}"')

        resource_string = ",\n".join(resource_params)

        mutation = f"""
        mutation {{
        bankWithdraw(
            receiver: "{nation_id}",
            receiver_type: 1,
            {resource_string}
        ) {{
            id
            date
            note
        }}
        }}
        """

        result = self.execute_query(query=mutation, account_api_key=WHITEKEY)
        return result is not None


    def transfer_to_alliance(self, target_alliance_id: int, resources: Dict[str, float], note: str = "EBO Transfer") -> bool:
        resource_params = [f"{res}: {resources.get(res, 0)}" for res in ALL_RESOURCES]
        resource_string = ", ".join(resource_params)

        mutation = f"""
        mutation {{
        bankWithdraw(
            receiver: "{target_alliance_id}",
            receiver_type: 2,
            {resource_string},
            note: "{note}"
        ) {{
            id
            date
            note
        }}
        }}
        """
        result = self.execute_query(query=mutation, account_api_key=self.api_key)
        return result is not None

    def get_recent_bank_transactions(self, alliance_id: int, note: str, limit: int = 100) -> Optional[List[Dict]]:
        records = get_bank_data_sql_by_everything('', str(alliance_id), '/')
        return records if records else None


def initialize(bot_config: dict, supabase_url: str, supabase_key: str, api_key: str, bot_key: str):
    global safekeep_db, materials_db, pnw_api, config
    config = bot_config
    safekeep_db = SafekeepDB(supabase_url, supabase_key)
    materials_db = MaterialsDB(supabase_url, supabase_key)
    pnw_api = PnWAPI(api_key, bot_key)
    
    load_white_keys_from_db()
    load_warned_nations_from_db()
    _update_imported_globals({
        'pnw_api': pnw_api,
        'safekeep_db': safekeep_db,
        'materials_db': materials_db,
        'config': config,
    })


def _update_imported_globals(new_values: dict):
    import sys
    this_module = sys.modules[__name__]
    for mod in list(sys.modules.values()):
        if not mod or not hasattr(mod, "__dict__"):
            continue
        for name, value in new_values.items():
            if name in mod.__dict__ and mod.__dict__[name] is None:
                mod.__dict__[name] = value


def load_white_keys_from_db():
    global stored_white_keys
    try:
        guild_keys = safekeep_db._get("guild_white_keys?select=*")
        for record in guild_keys:
            guild_id = record.get('guild_id')
            white_key = record.get('white_key')
            aa_id = record.get('aa_id')
            if guild_id and white_key:
                stored_white_keys[int(guild_id)] = {
                    'key': white_key,
                    'aa_id': aa_id,
                    'stored_by': record.get('stored_by', 'System'),
                    'stored_at': record.get('stored_at', datetime.now(timezone.utc).isoformat())
                }
        print(f"[INFO] Loaded {len(stored_white_keys)} white keys from database")
    except Exception as e:
        print(f"[ERROR] Failed to load white keys: {e}")


def load_warned_nations_from_db():
    global warned_nations
    try:
        warned = safekeep_db._get("safekeep_warnings?select=*")
        for record in warned:
            nation_id = record.get('nation_id')
            warned_at = record.get('warned_at')
            if nation_id and warned_at:
                warned_nations[nation_id] = warned_at
        print(f"[INFO] Loaded {len(warned_nations)} warned nations from database")
    except Exception as e:
        print(f"[INFO] No warnings table found or empty: {e}")