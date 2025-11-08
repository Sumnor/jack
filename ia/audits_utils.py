from datetime import datetime
from databases.sql.data_puller import supabase
from dotenv import load_dotenv
load_dotenv()

def upsert_audit(guild_id: int, nation_id: str, nation_name: str):
    data = {
        "guild_id": str(guild_id),
        "nation_id": str(nation_id),
        "nation_name": nation_name,
        "wc_audit": False,
        "build_audit": False,
        "tax_audit": False,
        "updated_at": datetime.utcnow().isoformat()
    }
    try:
        # Check if exists
        existing = supabase.select("audits", filters={"guild_id": str(guild_id), "nation_id": str(nation_id)})
        if existing:
            # Update existing
            supabase.update(
                "audits",
                {"nation_name": nation_name, "updated_at": datetime.utcnow().isoformat()},
                {"guild_id": str(guild_id), "nation_id": str(nation_id)}
            )
        else:
            # Insert new
            supabase.insert("audits", data)
        return True
    except Exception as e:
        print(f"Error upserting audit: {e}")
        return False

def bulk_upsert_audits(guild_id: int, nations: list):
    success_count = 0
    failed_count = 0
    
    for nation in nations:
        nation_id = str(nation.get('id'))
        nation_name = nation.get('nation_name', 'Unknown')
        
        if upsert_audit(guild_id, nation_id, nation_name):
            success_count += 1
        else:
            failed_count += 1
    
    return success_count, failed_count

def get_audits(guild_id: int):
    try:
        records = supabase.select("audits", filters={"guild_id": str(guild_id)})
        return records or []
    except Exception as e:
        print(f"Error fetching audits: {e}")
        return []

def delete_audit(guild_id: int, nation_id: str):
    try:
        supabase.delete("audits", {"guild_id": str(guild_id), "nation_id": str(nation_id)})
        return True
    except Exception as e:
        print(f"Error deleting audit: {e}")
        return False

def toggle_audit(guild_id: int, nation_id: str, field: str, auditor: str):
    valid_fields = ["wc_audit", "build_audit", "tax_audit"]
    if field not in valid_fields:
        raise ValueError("Invalid audit field")

    try:
        audits = supabase.select("audits", filters={"guild_id": str(guild_id), "nation_id": str(nation_id)})
        if not audits:
            raise ValueError("Audit not found. Run /audits_setup first.")

        current = audits[0]
        if field == "wc_audit":
            auditor_field = "wc_auditor"
        elif field == "build_audit":
            auditor_field = "build_auditor"
        else:
            auditor_field = "tax_auditor"
        new_val = not current.get(field, False)
        timestamp_field = f"{field}_updated_at"

        supabase.update(
            "audits",
            {field: new_val, timestamp_field: datetime.utcnow().isoformat(), auditor_field: auditor},
            {"guild_id": str(guild_id), "nation_id": str(nation_id)}
        )

        updated = supabase.select("audits", filters={"guild_id": str(guild_id), "nation_id": str(nation_id)})
        return updated[0] if updated else current
    except Exception as e:
        print(f"Error toggling audit: {e}")
        raise