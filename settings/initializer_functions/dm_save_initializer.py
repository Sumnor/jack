from datetime import datetime, timezone
from settings.initializer_functions.supabase_initializer import supabase

def save_dm_to_sheet(sender_name: str, recipient_name: str, message: str):
    try:
        data = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'sender': sender_name,
            'recipient': recipient_name,
            'message': message
        }
        supabase.insert('dm_logs', data)
        print("✅ DM logged to Supabase")
    except Exception as e:
        print(f"❌ Failed to save DM log: {e}")

def get_dm_sheet():
    class DMSheetWrapper:
        def append_row(self, row_data):
            if len(row_data) >= 3:
                save_dm_to_sheet(row_data[1], row_data[2], row_data[3])
        
        def row_values(self, row_num):
            return ["Timestamp", "Sender", "Recipient", "Message"]
    
    return DMSheetWrapper()