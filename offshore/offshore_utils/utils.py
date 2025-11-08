from datetime import datetime, timezone
from typing import Optional, Dict
from offshore.offshore_utils.initialize import safekeep_db,stored_white_keys

def save_warning_to_db(nation_id: int, original_aa_id: int) -> bool:
    try:
        data = {
            'nation_id': nation_id,
            'warned_at': datetime.now(timezone.utc).isoformat(),
            'original_aa_id': original_aa_id
        }
        
        existing = safekeep_db._get(f"safekeep_warnings?nation_id=eq.{nation_id}")
        if existing:
            safekeep_db._patch(f"safekeep_warnings?nation_id=eq.{nation_id}", data)
        else:
            safekeep_db._post("safekeep_warnings", data)
        
        return True
    except Exception as e:
        print(f"[ERROR] Failed to save warning: {e}")
        return False


def save_white_key_to_db(guild_id: int, white_key: str, aa_id: int, stored_by: str) -> bool:
    try:
        existing = safekeep_db._get(f"guild_white_keys?guild_id=eq.{guild_id}")
        
        data = {
            'guild_id': guild_id,
            'white_key': white_key,
            'aa_id': aa_id,
            'stored_by': stored_by,
            'stored_at': datetime.now(timezone.utc).isoformat()
        }
        
        if existing:
            safekeep_db._patch(f"guild_white_keys?guild_id=eq.{guild_id}", data)
        else:
            safekeep_db._post("guild_white_keys", data)
        
        return True
    except Exception as e:
        print(f"[ERROR] Failed to save white key: {e}")
        return False


def get_aa_id_from_guild(guild_id: int) -> Optional[int]:
    guild_data = stored_white_keys.get(guild_id)
    return guild_data.get('aa_id') if guild_data else None


def get_white_key_from_guild(guild_id: int) -> Optional[str]:
    guild_data = stored_white_keys.get(guild_id)
    return guild_data.get('key') if guild_data else None


def get_safekeep_by_nation_id(nation_id: int) -> Optional[Dict]:
    try:
        result = safekeep_db._get(f"safekeep?nation_id=eq.{nation_id}")
        return result[0] if result else None
    except Exception as e:
        return None