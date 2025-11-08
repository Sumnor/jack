import discord
from settings.initializer_functions.cached_users_initializer import cached_users
from databases.sql.data_puller import (
    get_alliances_data_sql_by_id, 
    get_nations_data_sql_by_nation_id, 
    get_nations_data_sql_by_nation_name, 
    get_alliances_data_sql_by_name
)

def identifier(interaction, who, user_id):
    if not who:
        who = user_id

    data = None
    nation_id = None
    discord_id = None
    sub_operation = None
    requested_id = None

    if who.startswith("<@") and who.endswith(">"):
        sub_operation = 'by_uid'
        requested_id = str(who.replace("<@", "").replace(">", "").replace("!", "")).strip()

    elif who.startswith("https://politicsandwar.com/nation/id="):
        sub_operation = 'nation_id'
        requested_id = str(who.replace("https://politicsandwar.com/nation/id=", ""))
    
    # Numeric input
    elif who.isnumeric():
        requested_id = str(who).strip()
        
        # Discord IDs are typically 17-19 digits
        if len(who) > 15:
            sub_operation = 'by_uid'
        else:
            # Try nation ID first
            data = get_nations_data_sql_by_nation_id(who)
            if data:
                sub_operation = 'nation_id'
                nation_id = requested_id
            else:
                # Try alliance ID
                data = get_alliances_data_sql_by_id(who)
                if data:
                    sub_operation = 'aa_id'
                    nation_id = requested_id  # Store ID even for alliances
                else:
                    return "Error", "❌ Invalid ID - no nation or alliance found with that ID.", None, None
    
    # Text input (nation name, alliance name, or username)
    else:
        requested_id = str(who).strip()
        
        # Try nation name first
        data = get_nations_data_sql_by_nation_name(requested_id)
        if data:
            sub_operation = 'by_nation_name'
            nation_id = str(data.get("id"))
        else:
            # Try alliance name
            data = get_alliances_data_sql_by_name(requested_id)
            if data:
                sub_operation = 'by_alliance_name'
                nation_id = str(data.get("id"))  # Store alliance ID
            else:
                # Try Discord username from cache
                sub_operation = 'by_name/username'

    # --- Resolve based on operation type ---
    
    # Discord UID lookup
    if sub_operation == 'by_uid':
        user_data = cached_users.get(requested_id)
        if not user_data:
            return "Error", "❌ This user is not registered in the system.", None, None
        
        nation_id = str(user_data.get("NationID", "")).strip()
        discord_id = requested_id
        
        if not nation_id:
            return "Error", "❌ User is registered but has no nation ID linked.", None, None
        
        # Fetch nation data for consistency
        data = get_nations_data_sql_by_nation_id(nation_id)
    
    # Nation ID lookup
    elif sub_operation == 'nation_id':
        # Find Discord ID from cached users
        discord_id = next(
            (
                discord_uid for discord_uid, user in cached_users.items()
                if str(user.get("NationID", "")).strip() == requested_id
            ),
            None
        )
    
    # Username lookup (fallback for text that didn't match nation/alliance)
    elif sub_operation == 'by_name/username':
        # Search cached users for matching username or nation ID
        found = next(
            (
                (discord_uid, user.get("NationID"))
                for discord_uid, user in cached_users.items()
                if str(user.get("DiscordUsername", "").lower()).strip() == requested_id.lower()
            ),
            (None, None)
        )
        
        discord_id, nation_id = found
        
        if not nation_id:
            return "Error", f"❌ Could not find user, nation, or alliance matching '{requested_id}'.", None, None
        
        nation_id = str(nation_id)
        data = get_nations_data_sql_by_nation_id(nation_id)
        
        if data:
            sub_operation = 'nation_id'
    
    # Nation name lookup
    elif sub_operation == 'by_nation_name':
        # Find Discord ID from cached users
        discord_id = next(
            (
                discord_uid for discord_uid, user in cached_users.items()
                if str(user.get("NationID", "")).strip() == nation_id
            ),
            None
        )
    
    # Alliance lookups (aa_id or by_alliance_name)
    # data is already set, nation_id contains alliance ID
    
    # Final validation
    if not nation_id and not data:
        return "Error", "❌ Unable to resolve the provided identifier.", None, None
    
    return nation_id, discord_id, data, sub_operation