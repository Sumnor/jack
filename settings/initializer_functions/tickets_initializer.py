from typing import Optional
from settings.initializer_functions.supabase_initializer import supabase

def get_ticket_sheet():
    class TicketSheetWrapper:
        def get_all_records(self):
            try:
                records = supabase.select('ticket_configs')
                formatted = []
                for record in records:
                    formatted.append({
                        'message_id': record.get('message_id', ''),
                        'message': record.get('message', ''),
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

def get_ticket_config(message_id: int) -> Optional[dict]:
    try:
        records = supabase.select('ticket_configs', filters={'message_id': str(message_id)})
        if records:
            row = records[0]
            return {
                'message': row.get("message", ""),
                'category_id': int(row["category_id"]) if row.get("category_id") else None
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
            'embed_description': embed_description,
            'category_id': category_id,
            'verify': embed_title
        }
        supabase.insert('ticket_configs', data)
        print("✅ Ticket config saved to Supabase")
    except Exception as e:
        print(f"❌ Failed to save ticket config: {e}")