import requests
from settings.bot_instance import SUPABASE_URL_DATA, SUPABASE_KEY_DATA

class SupabaseClient:
    def __init__(self):
        self.base_url = SUPABASE_URL_DATA.rstrip('/')
        self.headers = {
            'apikey': SUPABASE_KEY_DATA,
            'Authorization': f'Bearer {SUPABASE_KEY_DATA}',
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

    def delete(self, table: str, filters: dict):
        params = {}
        for key, value in filters.items():
            params[key] = f"eq.{value}"
        return self._make_request('DELETE', table, params=params)
    
    def update(self, table: str, data: dict, filters: dict):
        params = {}
        for key, value in filters.items():
            params[key] = f"eq.{value}"
        endpoint = f"{table}?" + "&".join([f"{k}={v}" for k, v in params.items()])
        return self._make_request('PATCH', endpoint, data=data)

supabase = SupabaseClient()

def get_nations_data_sql_by_nation_id(nation_id: str):
  try:
      records = supabase.select('nations', filters={'id': str(nation_id)})
      if records and len(records) > 0:
          return records[0]
      return None
  except Exception as e:
      print(f"Error fetching nation data: {e}")
      return None
  
def get_alliances_data_sql_by_id(nation_id: str):
  try:
      records = supabase.select('alliances', filters={'id': str(nation_id)})
      if records and len(records) > 0:
          return records[0]
      return None
  except Exception as e:
      print(f"Error fetching nation data: {e}")
      return None
  
def get_nations_data_sql_by_nation_name(nation_name: str):
  try:
      records = supabase.select('nations', filters={'nation_name': str(nation_name)})
      if records and len(records) > 0:
          return records[0]
      return None
  except Exception as e:
      print(f"Error fetching nation data: {e}")
      return None
  
def get_alliances_data_sql_by_name(nation_name: str):
  try:
      records = supabase.select('alliances', filters={'name': str(nation_name)})
      if records and len(records) > 0:
          return records[0]
      return None
  except Exception as e:
      print(f"Error fetching nation data: {e}")
      return None

def get_wars_data_sql_by_nation_id(nation_id: str):
    try:
        nation_id = str(nation_id)
        wars_attacker = supabase.select('wars', filters={'attacker_id': nation_id}) or []
        wars_defender = supabase.select('wars', filters={'defender_id': nation_id}) or []
        all_wars = wars_attacker + wars_defender
        return all_wars

    except Exception as e:
        print(f"Error fetching war data: {e}")
        return []

def get_cities_data_sql_by_nation_id(nation_id: str):
  try:
      records = supabase.select('cities', filters={'nation_id': str(nation_id)})
      if records and len(records) > 0:
          return records
      return None
  except Exception as e:
      print(f"Error fetching nation data: {e}")
      return None
  
def get_trade_data_sql_by_everything(identifier: str, this_nation: str, pull: str):
    try:
      if pull == '/':
        records_sender = supabase.select('trade_records', filters={'sender_id': str(this_nation)})
        records_receiver = supabase.select('trade_records', filters={'receiver_id': str(this_nation)})
        if records_receiver == None and records_sender == None:
            nation_data = get_nations_data_sql_by_nation_name(this_nation)
            nation_id = nation_data.get('id')
            records_sender = supabase.select('trade_records', filters={'sender_id': str(nation_id)})
            records_receiver = supabase.select('trade_records', filters={'receiver_id': str(nation_id)})
        all_trade_records = records_sender + records_receiver
        return all_trade_records
      else:
        records_sender = supabase.select('trade_records', filters={'sender_id': str(this_nation), 'receiver_id': str(identifier)})
        records_receiver = supabase.select('trade_records', filters={'receiver_id': str(this_nation), 'sender_id': str(identifier)})
        if records_receiver == None and records_sender == None:
            nation_data = get_nations_data_sql_by_nation_name(this_nation)
            nation_id = nation_data.get('id')
            records_sender = supabase.select('trade_records', filters={'sender_id': str(nation_id), 'receiver_id': str(identifier)})
            records_receiver = supabase.select('trade_records', filters={'receiver_id': str(nation_id), 'sender_id': str(identifier)})
        all_trade_records = records_sender + records_receiver
        return all_trade_records
          
    except Exception as e:
      print(f"Error fetching nation data: {e}")
      return None
    
def get_bank_data_sql_by_everything(identifier: str, this_nation: str, pull: str):
    try:

      if pull == '/':
        records_sender = supabase.select('bank_records', filters={'sender_id': str(this_nation)}) or []
        records_receiver = supabase.select('bank_records', filters={'receiver_id': str(this_nation)}) or []
        
        if not records_receiver and not records_sender and not str(this_nation).isdigit():
            nation_data = get_nations_data_sql_by_nation_name(this_nation)
            nation_id = nation_data.get('id') if nation_data else None
            if nation_id:
                records_sender = supabase.select('bank_records', filters={'sender_id': str(nation_id)}) or []
                records_receiver = supabase.select('bank_records', filters={'receiver_id': str(nation_id)}) or []
        
        all_bank_records = records_sender + records_receiver
        return all_bank_records
      else:
        records_sender = supabase.select('bank_records', filters={'sender_id': str(this_nation), 'receiver_id': str(identifier)}) or []
        records_receiver = supabase.select('bank_records', filters={'receiver_id': str(this_nation), 'sender_id': str(identifier)}) or []
        
        if not records_receiver and not records_sender and not str(this_nation).isdigit():
            nation_data = get_nations_data_sql_by_nation_name(this_nation)
            nation_id = nation_data.get('id') if nation_data else None
            if nation_id:
                records_sender = supabase.select('bank_records', filters={'sender_id': str(nation_id), 'receiver_id': str(identifier)}) or []
                records_receiver = supabase.select('bank_records', filters={'receiver_id': str(nation_id), 'sender_id': str(identifier)}) or []

        all_bank_records = records_sender + records_receiver
        return all_bank_records
          
    except Exception as e:
      print(f"Error fetching bank data: {e}")
      return []
    
def get_nations_data_sql_by_alliance_id(id: str):
  try:
      records = supabase.select('nations', filters={'alliance_id': str(id)})
      if records and len(records) > 0:
          return records
      return None
  except Exception as e:
      print(f"Error fetching nation data: {e}")
      return None
def get_treaties_data_sql_by_alliance_id(id: str):
    try:
        records_sender = supabase.select('treaties', filters={'alliance1_id': str(id)})
        records_receiver = supabase.select('treaties', filters={'alliance2_id': str(id)})
        all_trade_records = records_sender + records_receiver
        return all_trade_records
    except Exception as e:
      print(f"Error fetching nation data: {e}")
      return None