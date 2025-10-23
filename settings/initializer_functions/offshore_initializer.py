import asyncio
from datetime import datetime, timezone
from typing import Set

safekeep_commands = None
processed_transaction_ids: Set[str] = set()

async def check_jack_safekeep_deposits():
    global safekeep_commands, processed_transaction_ids
    
    if not safekeep_commands:
        print("[ERROR] safekeep_commands not initialized")
        return
    
    try:
        for guild_id, guild_data in safekeep_commands.stored_white_keys.items():
            aa_id = guild_data.get('aa_id')
            white_key = guild_data.get('key')
            
            if not aa_id or not white_key:
                continue
            
            # Fetch recent bank records with "Jack Safekeep" note
            records = safekeep_commands.pnw_api.get_bank_records(aa_id, "Jack Safekeep")
            
            for record in records:
                transaction_id = str(record.get('id'))
                
                # Skip if already processed
                if transaction_id in processed_transaction_ids:
                    continue
                
                # Check if it's a deposit (rtype=2 means alliance received)
                rtype = record.get('rtype')
                rid = record.get('rid')
                
                # Only process if this alliance received the deposit
                if rtype != 2 or rid != aa_id:
                    continue
                
                # Extract resources from the transaction
                resources = {}
                resource_fields = ['money', 'coal', 'oil', 'uranium', 'iron', 'bauxite', 
                                 'lead', 'gasoline', 'munitions', 'steel', 'aluminum', 'food']
                
                for res in resource_fields:
                    amount = record.get(res, 0)
                    if amount and amount > 0:
                        resources[res] = amount
                
                if not resources:
                    processed_transaction_ids.add(transaction_id)
                    continue
                
                # Execute auto-EBO to INTRA
                print(f"[INFO] Auto-EBO: Processing transaction {transaction_id} from AA {aa_id}")
                print(f"[INFO] Resources: {resources}")
                
                offshore_id = safekeep_commands.config['offshore_alliance_id']
                note = f"Auto-EBO: Jack Safekeep deposit (ID: {transaction_id})"
                
                success = await asyncio.to_thread(
                    safekeep_commands.pnw_api.transfer_to_alliance,
                    offshore_id,
                    resources,
                    white_key,
                    note
                )
                
                if success:
                    print(f"[SUCCESS] Auto-EBO completed for transaction {transaction_id}")
                    processed_transaction_ids.add(transaction_id)
                    
                    # Log to database
                    try:
                        log_data = {
                            'transaction_id': transaction_id,
                            'source_aa': aa_id,
                            'target_aa': offshore_id,
                            'resources': resources,
                            'note': note,
                            'processed_at': datetime.now(timezone.utc).isoformat()
                        }
                        safekeep_commands.safekeep_db._post('auto_ebo_logs', log_data)
                    except Exception as e:
                        print(f"[WARN] Failed to log auto-EBO: {e}")
                else:
                    print(f"[ERROR] Auto-EBO failed for transaction {transaction_id}")
        if len(processed_transaction_ids) > 1000:
            processed_transaction_ids.clear()
            print("[INFO] Cleared processed transaction cache")
    
    except Exception as e:
        print(f"[ERROR] Auto-EBO check failed: {e}")


async def auto_ebo_loop():
    """Main loop - runs every 15 minutes"""
    print("[INFO] Starting auto-EBO checker (15min interval)")
    
    while True:
        try:
            await check_jack_safekeep_deposits()
        except Exception as e:
            print(f"[ERROR] Auto-EBO loop error: {e}")
        await asyncio.sleep(900)


import asyncio
from datetime import datetime, timezone, timedelta
from typing import Set

safekeep_commands = None
processed_transaction_ids: Set[str] = set()


async def check_jack_safekeep_deposits():
    """Check for deposits with 'Jack Safekeep' note and auto-EBO them to INTRA"""
    global safekeep_commands, processed_transaction_ids
    
    if not safekeep_commands:
        print("[ERROR] safekeep_commands not initialized")
        return
    
    print("[INFO] Checking for Jack Safekeep deposits...")
    
    try:
        # Check each registered guild's alliance
        for guild_id, guild_data in safekeep_commands.stored_white_keys.items():
            aa_id = guild_data.get('aa_id')
            white_key = guild_data.get('key')
            
            if not aa_id or not white_key:
                continue
            
            # Fetch recent bank records with "Jack Safekeep" note
            records = safekeep_commands.pnw_api.get_bank_records(aa_id, "Jack Safekeep")
            
            for record in records:
                transaction_id = str(record.get('id'))
                
                # Skip if already processed
                if transaction_id in processed_transaction_ids:
                    continue
                
                # Check if it's a deposit (rtype=2 means alliance received)
                rtype = record.get('rtype')
                rid = record.get('rid')
                
                # Only process if this alliance received the deposit
                if rtype != 2 or rid != aa_id:
                    continue
                
                # Extract resources from the transaction
                resources = {}
                resource_fields = ['money', 'coal', 'oil', 'uranium', 'iron', 'bauxite', 
                                 'lead', 'gasoline', 'munitions', 'steel', 'aluminum', 'food']
                
                for res in resource_fields:
                    amount = record.get(res, 0)
                    if amount and amount > 0:
                        resources[res] = amount
                
                if not resources:
                    processed_transaction_ids.add(transaction_id)
                    continue
                
                # Execute auto-EBO to INTRA
                print(f"[INFO] Auto-EBO: Processing transaction {transaction_id} from AA {aa_id}")
                print(f"[INFO] Resources: {resources}")
                
                offshore_id = safekeep_commands.config['offshore_alliance_id']
                note = f"Auto-EBO: Jack Safekeep deposit (ID: {transaction_id})"
                
                success = await asyncio.to_thread(
                    safekeep_commands.pnw_api.transfer_to_alliance,
                    offshore_id,
                    resources,
                    white_key,
                    note
                )
                
                if success:
                    print(f"[SUCCESS] Auto-EBO completed for transaction {transaction_id}")
                    processed_transaction_ids.add(transaction_id)
                    
                    # Log to database
                    try:
                        log_data = {
                            'transaction_id': transaction_id,
                            'source_aa': aa_id,
                            'target_aa': offshore_id,
                            'resources': resources,
                            'note': note,
                            'processed_at': datetime.now(timezone.utc).isoformat()
                        }
                        safekeep_commands.safekeep_db._post('auto_ebo_logs', log_data)
                    except Exception as e:
                        print(f"[WARN] Failed to log auto-EBO: {e}")
                else:
                    print(f"[ERROR] Auto-EBO failed for transaction {transaction_id}")
        if len(processed_transaction_ids) > 1000:
            processed_transaction_ids.clear()
            print("[INFO] Cleared processed transaction cache")
    
    except Exception as e:
        print(f"[ERROR] Auto-EBO check failed: {e}")


async def auto_ebo_loop():
    """Main loop - runs every 15 minutes"""
    print("[INFO] Starting auto-EBO checker (15min interval)")
    
    while True:
        try:
            await check_jack_safekeep_deposits()
        except Exception as e:
            print(f"[ERROR] Auto-EBO loop error: {e}")
        await asyncio.sleep(900)


def start_auto_ebo_checker(safekeep_cmd_module):
    """Initialize and start the auto-EBO checker"""
    global safekeep_commands
    safekeep_commands = safekeep_cmd_module
    asyncio.create_task(auto_ebo_loop())
    print("[INFO] Auto-EBO checker started")