import asyncio
from typing import Dict, Optional
from settings.initializer_functions.resource_prices import ALL_RESOURCES
from offshore.offshore_utils.initialize import (
    pnw_api, CONFIG_OFFSHORE_AA_ID, CONFIG_DEPOSIT_NOTE,
    stored_white_keys, processed_transaction_ids, safekeep_db
)
from datetime import datetime, timezone


async def process_new_deposits():
    global processed_transaction_ids

    for guild_id, data in stored_white_keys.items():
        alliance_id = data['aa_id']
        white_key = data['key']
        offshore_id = CONFIG_OFFSHORE_AA_ID

        print(f"[INFO] Checking deposits for alliance {alliance_id} (guild {guild_id})")

        last_processed_date = await asyncio.to_thread(
            safekeep_db.get_last_processed_date,
            alliance_id,
            guild_id
        )
        from offshore.offshore_utils.initialize import pnw_api
        
        transactions = await asyncio.to_thread(
            pnw_api.get_recent_bank_transactions,
            alliance_id,
            CONFIG_DEPOSIT_NOTE
        )

        if not transactions:
            continue

        filtered_txns = []
        print(f"[DEBUG] Retrieved {len(transactions)} txns for alliance {alliance_id}")

        for txn in transactions[:5]:  # show only a few
            print(f"[DEBUG] TXN: id={txn.get('id')} note={txn.get('note')} date={txn.get('date')}")

        for txn in transactions:
            txn_id = txn.get("id")
            txn_date = txn.get("date")
            note = str(txn.get("note", "")).lower()

            if "jack safekeep" not in note:
                continue
            if txn_id in processed_transaction_ids:
                continue
            if last_processed_date and txn_date <= last_processed_date:
                continue

            filtered_txns.append(txn)

        if not filtered_txns:
            continue

        filtered_txns.sort(key=lambda t: t["date"])
        latest_date = filtered_txns[-1]["date"]

        for txn in filtered_txns:
            txn_id = txn.get("id")
            nation_id = txn.get("sender_id")
            sender_type = txn.get("sender_type")

            if sender_type != 1:
                continue

            deposited = {}
            for resource in ALL_RESOURCES:
                amount = float(txn.get(resource, 0))
                if amount > 0:
                    deposited[resource] = amount

            if not deposited:
                continue

            print(f"[INFO] Processing deposit from nation {nation_id}: {deposited}")
            success = await transfer_deposit_to_offshore(
                nation_id, alliance_id, guild_id, deposited
            )

            if success:
                await asyncio.to_thread(
                    safekeep_db.update_safekeep_balance,
                    None,
                    nation_id,
                    deposited,
                    subtract=False
                )

            processed_transaction_ids.add(txn_id)

        if filtered_txns:
            await asyncio.to_thread(
                safekeep_db.update_last_processed_date,
                alliance_id,
                guild_id,
                latest_date
            )


async def transfer_deposit_to_offshore(nation_id: int, alliance_id: int, guild_id: int, resources: Dict[str, float]) -> bool:
    alliance_white_key = None
    
    if guild_id in stored_white_keys:
        key_data = stored_white_keys[guild_id]
        stored_aa_id = key_data.get('aa_id')
        stored_key = key_data.get('key')
        
        if stored_aa_id == alliance_id:
            alliance_white_key = stored_key
        else:
            return False
    else:
        return False
    
    if not alliance_white_key:
        return False
    from offshore.offshore_utils.initialize import PnWAPI, CONFIG_OFFSHORE_AA_ID
    alliance_api = PnWAPI(alliance_white_key, alliance_white_key)
    try:
        success = await asyncio.to_thread(
            alliance_api.transfer_to_alliance,
            CONFIG_OFFSHORE_AA_ID,
            resources,
            f"Safekeep deposit from Nation {nation_id}"
        )
        
        if not success:
            return False
        
    except Exception as e:
        return False
    ebo_id = await asyncio.to_thread(
        safekeep_db.record_ebo_transaction,
        alliance_id,
        CONFIG_OFFSHORE_AA_ID,
        resources,
        f"Safekeep deposit - Nation {nation_id}",
        "System"
    )
    await asyncio.to_thread(
        safekeep_db.update_aa_sheet,
        alliance_id,
        guild_id,
        resources,
        operation="subtract"
    )
    
    await asyncio.to_thread(
        safekeep_db.update_aa_sheet,
        CONFIG_OFFSHORE_AA_ID,
        guild_id,
        resources,
        operation="add"
    )
    return True