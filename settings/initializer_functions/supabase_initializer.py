import os
import requests
from typing import Dict, List

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

supabase = SupabaseClient()