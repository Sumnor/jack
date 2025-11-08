import os
import requests
from typing import Dict

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

from typing import Dict, Tuple

ALL_RESOURCES = [
    "money", "coal", "oil", "uranium", "iron", "bauxite", "lead",
    "gasoline", "munitions", "steel", "aluminum", "food"
]

RESOURCE_EMOJIS = {
    "money": "💰",
    "coal": "⚫",
    "oil": "🛢️",
    "uranium": "☢️",
    "iron": "⚙️",
    "bauxite": "🟤",
    "lead": "🔗",
    "gasoline": "⛽",
    "munitions": "💣",
    "steel": "🔩",
    "aluminum": "🥈",
    "food": "🍞"
}

def format_number(num):
    if num >= 1_000_000_000:
        return f"{num/1_000_000_000:.1f}B"
    elif num >= 1_000_000:
        return f"{num/1_000_000:.1f}M"
    elif num >= 1_000:
        return f"{num/1_000:.1f}K"
    else:
        return f"{num:.0f}"

def parse_resources(args: str, default_note: str = "Discord withdrawal") -> Tuple[Dict[str, float], str]:
    resources_requested = {}
    note = default_note
    
    if not args:
        return resources_requested, note
    
    parts = args.split()
    for part in parts:
        if '=' in part:
            key, value = part.split('=', 1)
            key = key.lower().strip()
            
            if key == 'note':
                note = value.strip('"\'')
            elif key in ALL_RESOURCES:
                try:
                    amount = float(value)
                    if amount > 0:
                        resources_requested[key] = amount
                except ValueError:
                    pass
    
    return resources_requested, note