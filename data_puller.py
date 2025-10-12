import discord
import os
import requests
from typing import Optional, Dict, List
from datetime import datetime, timezone, timedelta
import asyncio
from bot_instance import SUPABASE_URL_DATA, SUPABASE_KEY_DATA

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

def get_wars_data_sql_by_nation_id(nation_id: str):
    try:
        nation_id = str(nation_id)
        wars_attacker = supabase.select('wars', filters={'attacker_id': nation_id}) or []
        wars_defender = supabase.select('wars', filters={'defender_id': nation_id}) or []
        if wars_attacker and wars_defender != None:
          all_wars = wars_attacker + wars_defender
          return all_wars
        return None

    except Exception as e:
        print(f"Error fetching war data: {e}")
        return []

def get_cities_data_sql_by_nation_id(nation_id: str):
  try:
      records = supabase.select('cities', filters={'nation_id': str(nation_id)})
      if records and len(records) > 0:
          return records[0]
      return None
  except Exception as e:
      print(f"Error fetching nation data: {e}")
      return None




  
  

