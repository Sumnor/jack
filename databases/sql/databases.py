import requests
import time
from discord.ext import tasks
from datetime import datetime, timezone
import json
from settings.bot_instance import SUPABASE_URL, SUPABASE_KEY
from settings.initializer_functions.resource_prices import ALL_RESOURCES
from typing import Dict, Optional, List, Tuple
import json

supabase_url = SUPABASE_URL
supabase_key = SUPABASE_KEY

class Database:
    def __init__(self, supabase_url: str, supabase_key: str):
        self.url = supabase_url.rstrip('/')
        self.key = supabase_key
        self.headers = {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation"
        }
    
    def _get(self, endpoint: str, params: Dict = None):
        url = f"{self.url}/{endpoint}"
        if params:
            query = "&".join([f"{k}={v}" for k, v in params.items()])
            url += f"?{query}"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json()
    
    def _post(self, endpoint: str, data: Dict):
        url = f"{self.url}/{endpoint}"
        response = requests.post(url, headers=self.headers, json=data)
        response.raise_for_status()
        return response.json()
    
    def _patch(self, endpoint: str, data: Dict):
        url = f"{self.url}/{endpoint}"
        response = requests.patch(url, headers=self.headers, json=data)
        response.raise_for_status()
        return response.json()
    
    def _delete(self, endpoint: str):
        url = f"{self.url}/{endpoint}"
        response = requests.delete(url, headers=self.headers)
        response.raise_for_status()
        return response.json()

TABLE_NAME = "materials"
ALERTS_TABLE = "alerts"
MATERIALS = ["food","uranium","iron","coal","bauxite","oil","lead","steel","aluminum","munitions","gasoline"]

def execute_query(query, params=None):
    try:
        if "INSERT INTO predictions" in query and params:
            material, target_date, predicted_price, confidence_score, model_used = params
            
            target_date_str = target_date.isoformat() if hasattr(target_date, 'isoformat') else str(target_date)
            
            payload = {
                "material": material,
                "target_date": target_date_str,
                "predicted_price": float(predicted_price),
                "confidence_score": float(confidence_score),
                "model_used": model_used
            }
            
            url = f"{SUPABASE_URL}/predictions"
            headers = {
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Content-Type": "application/json",
                "Prefer": "return=minimal"
            }
            
            response = requests.post(url, headers=headers, json=payload)
            response.raise_for_status()
            return True
            
        return False
    except Exception as e:
        print(f"Execute query error: {e}")
        return False

def fetch_query(query, params=None):
    try:
        if "SELECT" in query and "FROM predictions" in query and params:
            material, days_limit = params
            
            url = f"{SUPABASE_URL}/predictions?select=target_date,predicted_price,confidence_score&material=eq.{material}&target_date=gte.{datetime.now(timezone.utc).date().isoformat()}&order=target_date&limit={days_limit}"
            
            headers = {
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}"
            }
            
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            
            return [(row['target_date'], row['predicted_price'], row['confidence_score']) for row in data]
            
        return None
    except Exception as e:
        print(f"Fetch query error: {e}")
        return None

def fetch_column(table_name, column_name, limit=100):
    url = f"{SUPABASE_URL}/{table_name}?select={column_name}&limit={limit}"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}"
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    data = response.json()

    return [row[column_name] for row in data]

def fetch_columns(table_name, column_name, last_n=None):
    url = f"{SUPABASE_URL}/{table_name}?select={column_name}&order=timestamp.desc"
    if last_n:
        url += f"&limit={last_n}"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}"
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    data = response.json()
    

    values = [row[column_name] for row in reversed(data)]
    return values

def fetch_columnss(table_name, column_name, last_n=None, with_timestamps=False):
    select_fields = f"{column_name}"
    if with_timestamps:
        select_fields += ",timestamp"

    url = f"{SUPABASE_URL}/{table_name}?select={select_fields}&order=timestamp.desc"
    if last_n:
        url += f"&limit={last_n}"

    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}"
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    data = response.json()

    if with_timestamps:
        values = [row[column_name] for row in data]
        timestamps = [row["timestamp"] for row in data]
        return values[::-1], timestamps[::-1]
    else:
        return [row[column_name] for row in data][::-1]


def fetch_latest_price(material):
    data = fetch_columns(TABLE_NAME, material, last_n=1)
    return data[-1] if data else None

headers = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}

def get_alerts_for_user(discord_id: int):
    url = f"{SUPABASE_URL}/{ALERTS_TABLE}?discord_id=eq.{discord_id}"
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    data = resp.json()
    if data:
        return data[0]
    else:

        payload = {"discord_id": discord_id}
        resp = requests.post(f"{SUPABASE_URL}/{ALERTS_TABLE}", headers=headers, json=payload)
        resp.raise_for_status()
        return resp.json()[0]

def update_alert(discord_id: int, material: str, mode: int):
    url = f"{SUPABASE_URL}/{ALERTS_TABLE}?discord_id=eq.{discord_id}"
    payload = {material: mode, "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    resp = requests.patch(url, headers=headers, json=payload)
    resp.raise_for_status()
    return resp.json()

def get_all_alerts():
    url = f"{SUPABASE_URL}/{ALERTS_TABLE}"
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    return resp.json()


async def send_alert(user, message):
    try:
        await user.send(message)
    except:
        pass

def setup_alerts_task(bot, table_name="materials"):

    @tasks.loop(minutes=1)
    async def check_alerts():
        rows = get_all_alerts()
        for row in rows:
            user = bot.get_user(row["discord_id"])
            if not user:
                continue
            for mat in MATERIALS:
                mode = row.get(mat, 0)
                if mode == 0:
                    continue
                latest_price = fetch_latest_price(table_name, mat)
                if latest_price is None:
                    continue
                values = fetch_columns(table_name, mat, last_n=30)
                avg = sum(values) / len(values) if values else 0
                if avg == 0:
                    continue
                if mode in (1,3) and latest_price > avg*1.2:
                    await send_alert(user, f"⚠️ {mat.capitalize()} {latest_price} is above +20% ({avg*1.2:.2f})")
                if mode in (2,3) and latest_price < avg*0.8:
                    await send_alert(user, f"⚠️ {mat.capitalize()} {latest_price} is below -20% ({avg*0.8:.2f})")

    check_alerts.start()
    return check_alerts

def fetch_latest_model(material):
    url = f"{SUPABASE_URL}/model_parameters?select=*&material=eq.{material}&order=timestamp.desc&limit=1"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}"
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    data = response.json()
    if not data:
        return None
    row = data[0]
    intercept = float(row["intercept"])
    coefficients = json.loads(row["coefficients"])
    features = json.loads(row["features"])
    return intercept, coefficients, features


from datetime import datetime, timezone
from typing import Optional, Dict, List
import requests


class Database:
    def __init__(self, supabase_url: str, supabase_key: str):
        self.base_url = supabase_url.rstrip('/')
        self.headers = {
            'apikey': supabase_key,
            'Authorization': f'Bearer {supabase_key}',
            'Content-Type': 'application/json',
            'Prefer': 'return=representation'
        }
    
    def _get(self, endpoint: str):
        url = f"{self.base_url}/{endpoint}"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json()
    
    def _post(self, table: str, data: dict):
        url = f"{self.base_url}/{table}"
        response = requests.post(url, headers=self.headers, json=data)
        response.raise_for_status()
        return response.json()
    
    def _patch(self, endpoint: str, data: dict):
        url = f"{self.base_url}/{endpoint}"
        response = requests.patch(url, headers=self.headers, json=data)
        response.raise_for_status()
        return response.json()
    
    def _delete(self, endpoint: str):
        url = f"{self.base_url}/{endpoint}"
        response = requests.delete(url, headers=self.headers)
        response.raise_for_status()
        return response.json()
    
    def _upsert(self, table: str, data: dict, conflict_columns: str = None):
        url = f"{self.base_url}/{table}"
        headers = self.headers.copy()
        if conflict_columns:
            headers['Prefer'] = f'resolution=merge-duplicates,return=representation'
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        return response.json()


class SafekeepDB(Database):
    def __init__(self, supabase_url: str, supabase_key: str):
        super().__init__(supabase_url, supabase_key)
        self.table = "safekeep"
        self.aa_table = "alliance_accounts"
        self.intra_safekeep_table = "intra_safekeep"
        self.intra_db_table = "intra_database"
    
    def get_safekeep_by_discord_id(self, discord_id: str) -> Optional[Dict]:
        try:
            data = self._get(f"{self.table}?discord_id=eq.{discord_id}&select=*")
            if not data:
                return None
            
            record = data[0]
            deposit_date = record.get('deposit_date')
            if deposit_date:
                deposit_dt = datetime.fromisoformat(deposit_date.replace('Z', '+00:00'))
                if deposit_dt.date() > datetime.now(timezone.utc).date():
                    return None
            
            return record
        except Exception as e:
            print(f"Error fetching safekeep for {discord_id}: {e}")
            return None
    
    def get_safekeep_by_nation_id(self, nation_id: int) -> Optional[Dict]:
        try:
            data = self._get(f"{self.table}?nation_id=eq.{nation_id}&select=*")
            return data[0] if data else None
        except Exception as e:
            print(f"Error fetching safekeep for nation {nation_id}: {e}")
            return None
    
    def get_all_safekeep_for_aa(self, aa_id: int) -> List[Dict]:
        try:
            current_date = datetime.now(timezone.utc).date().isoformat()
            data = self._get(f"{self.table}?alliance_id=eq.{aa_id}&deposit_date=lte.{current_date}&select=*")
            return data
        except Exception as e:
            print(f"Error fetching safekeep for AA {aa_id}: {e}")
            return []
    
    def update_safekeep_balance(self, discord_id: str = None, nation_id: int = None, 
                               resources: Dict = None, subtract: bool = True) -> bool:
        try:
            if discord_id:
                current = self.get_safekeep_by_discord_id(discord_id)
                filter_param = f"discord_id=eq.{discord_id}"
            elif nation_id:
                current = self.get_safekeep_by_nation_id(nation_id)
                filter_param = f"nation_id=eq.{nation_id}"
            else:
                print("[ERROR] Either discord_id or nation_id must be provided")
                return False
            
            if not current:
                print(f"[ERROR] No safekeep record found for {'discord ' + str(discord_id) if discord_id else 'nation ' + str(nation_id)}")
                return False
            
            new_balance = {}
            for res, amt in resources.items():
                if amt > 0:
                    old_val = current.get(res, 0) or 0
                    if subtract:
                        new_val = max(old_val - amt, 0)
                    else:
                        new_val = old_val + amt
                    new_balance[res] = new_val
            
            if not new_balance:
                print("[ERROR] No resources to update")
                return False
            
            new_balance['updated_at'] = datetime.now(timezone.utc).isoformat()
            self._patch(f"{self.table}?{filter_param}", new_balance)
            return True
        except Exception as e:
            print(f"Error updating safekeep balance: {e}")
            return False
    
    def record_ebo_transaction(self, alliance_id: int, target_alliance_id: int, 
                               resources: Dict[str, float], note: str, 
                               executed_by: str, bank_record_id: int = None) -> int:
        try:
            data = {
                'alliance_id': alliance_id,
                'target_alliance_id': target_alliance_id,
                'resources': resources,
                'note': note,
                'executed_by': executed_by,
                'bank_record_id': bank_record_id,
                'remaining_resources': resources.copy()  
            }
            
            result = self._post('ebo_transactions', data)
            if result and len(result) > 0:
                ebo_id = result[0]['id']
                print(f"[INFO] Recorded EBO #{ebo_id} for AA {alliance_id}")
                return ebo_id
            return None
        except Exception as e:
            print(f"[ERROR] Failed to record EBO transaction: {e}")
            return None
    
    def get_recent_ebos(self, alliance_id: int, guild_id: int, hours: int = 24) -> List[Dict]:
        try:
            from datetime import datetime, timedelta, timezone
            cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
            
            result = self._get(
                f"ebo_transactions?alliance_id=eq.{alliance_id}"
                f"&executed_at=gte.{cutoff}"
                f"&order=executed_at.desc"
            )
            
            available_ebos = []
            for ebo in result:
                remaining = ebo.get('remaining_resources', {})
                if any(v > 0 for v in remaining.values()):
                    available_ebos.append(ebo)
            
            return available_ebos
        except Exception as e:
            print(f"[ERROR] Failed to get recent EBOs: {e}")
            return []
    
    def deduct_from_ebo(self, ebo_id: int, resources: Dict[str, float]) -> bool:
        try:
            ebo = self._get(f"ebo_transactions?id=eq.{ebo_id}")
            if not ebo or len(ebo) == 0:
                return False
            
            remaining = ebo[0].get('remaining_resources', {})
            
            for resource, amount in resources.items():
                if resource in remaining:
                    remaining[resource] = max(0, remaining[resource] - amount)
            
            update_data = {'remaining_resources': remaining}
            self._patch(f"ebo_transactions?id=eq.{ebo_id}", update_data)
            
            print(f"[INFO] Deducted from EBO #{ebo_id}: {resources}")
            return True
        except Exception as e:
            print(f"[ERROR] Failed to deduct from EBO: {e}")
            return False
    
    def get_or_create_aa_sheet(self, alliance_id: int, guild_id: int) -> Dict:
        try:
            result = self._get(f"aa_sheets?alliance_id=eq.{alliance_id}&guild_id=eq.{guild_id}")
            
            if result and len(result) > 0:
                return result[0]
            
            data = {
                'alliance_id': alliance_id,
                'money': 0, 'coal': 0, 'oil': 0, 'uranium': 0,
                'iron': 0, 'bauxite': 0, 'lead': 0, 'gasoline': 0,
                'munitions': 0, 'steel': 0, 'aluminum': 0, 'food': 0, 'guild_id': guild_id
            }
            
            result = self._post('aa_sheets', data)
            print(f"[INFO] Created AA sheet for alliance {alliance_id}")
            return result[0] if result else None
        except Exception as e:
            print(f"[ERROR] Failed to get/create AA sheet: {e}")
            return None
    
    def update_aa_sheet(self, alliance_id: int, guild_id: int, resources: Dict[str, float], 
                        operation: str = 'add') -> bool:
        try:
            sheet = self.get_or_create_aa_sheet(alliance_id, guild_id)
            if not sheet:
                return False
            
            updated = {}
            for resource, amount in resources.items():
                if resource in ALL_RESOURCES:
                    current = float(sheet.get(resource, 0))
                    if operation == 'add':
                        updated[resource] = current + amount
                    elif operation == 'subtract':
                        updated[resource] = max(0, current - amount)
            
            self._patch(f"aa_sheets?alliance_id=eq.{alliance_id}&guild_id=eq.{guild_id}", updated)
            print(f"[INFO] Updated AA sheet for alliance {alliance_id}: {operation} {resources}")
            return True
        except Exception as e:
            print(f"[ERROR] Failed to update AA sheet: {e}")
            return False
    
    def update_member_aa(self, discord_id: str, nation_id: int, new_aa_id: int) -> bool:
        try:
            data = {
                "alliance_id": new_aa_id,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
            self._patch(f"{self.table}?discord_id=eq.{discord_id}", data)
            return True
        except Exception as e:
            print(f"Error updating AA for {discord_id}: {e}")
            return False
    
    def remove_member_from_aa(self, discord_id: str) -> bool:
        try:
            self._delete(f"{self.table}?discord_id=eq.{discord_id}")
            return True
        except Exception as e:
            print(f"Error removing member {discord_id}: {e}")
            return False
        
    def get_last_processed_date(self, alliance_id: int, guild_id: int = None) -> Optional[str]:
        try:
            result = self._get(f"aa_sheets?alliance_id=eq.{alliance_id}&select=last_processed_date")
            if result and len(result) > 0:
                return result[0].get("last_processed_date")
            return None
        except Exception as e:
            print(f"[ERROR] Could not fetch last processed date: {e}")
            return None


    def update_last_processed_date(self, alliance_id: int, guild_id: int, date_str: str) -> None:
        try:
            self._patch(f"aa_sheets?alliance_id=eq.{alliance_id}",
                        {"last_processed_date": date_str})
            print(f"[INFO] Updated last processed date for AA {alliance_id} to {date_str}")
        except Exception as e:
            print(f"[ERROR] Could not update last processed date: {e}")


    
    def get_safekeep_by_guild_id(self, guild_id: str) -> Optional[Dict]:
        try:
            data = self._get(f"{self.aa_table}?id=eq.{guild_id}&select=*")
            if not data:
                return None
            
            record = data[0]
            deposit_date = record.get('deposit_date')
            if deposit_date:
                deposit_dt = datetime.fromisoformat(deposit_date.replace('Z', '+00:00'))
                if deposit_dt.date() > datetime.now(timezone.utc).date():
                    return None
            
            return record
        except Exception as e:
            print(f"Error fetching safekeep for {guild_id}: {e}")
            return None
    
    def create_safekeep_account(self, discord_id: str, nation_id: int, alliance_id: int, 
                                resources: Dict, deposit_date: str = None) -> Optional[Dict]:
        try:
            if not deposit_date:
                deposit_date = datetime.now(timezone.utc).date().isoformat()
            
            account_data = {
                "discord_id": discord_id,
                "nation_id": nation_id,
                "alliance_id": alliance_id,
                "deposit_date": deposit_date,
                "created_at": datetime.now(timezone.utc).isoformat(),
                **resources
            }
            
            return self._post(self.table, account_data)[0]
        except Exception as e:
            print(f"Error creating safekeep account for {discord_id}: {e}")
            return None

class MaterialsDB(Database):
    def __init__(self, supabase_url: str, supabase_key: str):
        super().__init__(supabase_url, supabase_key)
        self.table = "materials"
        self.alerts_table = "alerts"
    
    def fetch_latest_price(self, material: str) -> Optional[float]:
        try:
            data = self._get(f"{self.table}?select={material}&order=timestamp.desc&limit=1")
            return data[0][material] if data else None
        except Exception as e:
            print(f"Error fetching latest price for {material}: {e}")
            return None
    
    def fetch_price_history(self, material: str, limit: int = 30) -> List[float]:
        try:
            data = self._get(f"{self.table}?select={material}&order=timestamp.desc&limit={limit}")
            return [row[material] for row in reversed(data)]
        except Exception as e:
            print(f"Error fetching price history for {material}: {e}")
            return []
    
    def get_alerts_for_user(self, discord_id: int) -> Dict:
        try:
            data = self._get(f"{self.alerts_table}?discord_id=eq.{discord_id}")
            if data:
                return data[0]
            
            new_alert = {"discord_id": discord_id}
            return self._post(self.alerts_table, new_alert)[0]
        except Exception as e:
            print(f"Error getting alerts for {discord_id}: {e}")
            return {}
    
    def update_alert(self, discord_id: int, material: str, mode: int) -> bool:
        try:
            data = {
                material: mode,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
            self._patch(f"{self.alerts_table}?discord_id=eq.{discord_id}", data)
            return True
        except Exception as e:
            print(f"Error updating alert for {discord_id}: {e}")
            return False
    
    def get_all_alerts(self) -> List[Dict]:
        try:
            return self._get(self.alerts_table)
        except Exception as e:
            print(f"Error fetching all alerts: {e}")
            return []