import discord
from discord import app_commands
import datetime
from typing import Optional
from settings.bot_instance import bot, wrap_as_prefix_command
from settings.initializer_functions.supabase_initializer import supabase

def get_warn_channel(guild_id):
    try:
        records = supabase.select('server_settings', filters={'server_id': str(guild_id), 'key': 'WARN_CHANNEL'})
        if records:
            return str(records[0].get('value', '')).strip()
        print(f"⚠️ WARN_CHANNEL not found for guild {guild_id}")
        return None
    except Exception as e:
        print(f"❌ Error fetching warn channel for guild {guild_id}: {e}")
        return None

def get_warroom_id(guild_id):
    try:
        records = supabase.select('server_settings', filters={'server_id': str(guild_id), 'key': 'WAR_ROOMS'})
        if records:
            return str(records[0].get('value', '')).strip()
        print(f"⚠️ WAR_ROOMS not found for guild {guild_id}")
        return None
    except Exception as e:
        print(f"❌ Error fetching warn channel for guild {guild_id}: {e}")
        return None

def get_grant_channel(guild_id):
    try:
        records = supabase.select('server_settings', filters={'server_id': str(guild_id), 'key': 'GRANT_REQUEST_CHANNEL_ID'})
        if records:
            return str(records[0].get('value', '')).strip()
        print(f"⚠️ GRANT_REQUEST_CHANNEL_ID not found for guild {guild_id}")
        return None
    except Exception as e:
        print(f"❌ Error fetching grant channel for guild {guild_id}: {e}")
        return None

def get_api_key_for_interaction(interaction: discord.Interaction):
    return get_settings_value("API_KEY", interaction.guild.id)

def get_quota_due(guild_id):
    return get_settings_value("QUOTA DUE", guild_id)

def get_quota_expiery(guild_id):
    return get_settings_value("QUOTA EXPIERY", guild_id)

def get_api_key_for_guild(guild_id: int):
    try:
        records = supabase.select('server_settings', filters={'server_id': str(guild_id), 'key': 'API_KEY'})
        if records:
            api_key = records[0].get('value', '').strip()
            print(api_key)
            return api_key
        print(f"⚠️ API_KEY not found for guild {guild_id}")
        return None
    except Exception as e:
        print(f"❌ Error fetching API key for guild {guild_id}: {e}")
        return None

def get_banking_role(interaction: discord.Interaction):
    return get_settings_value("BANKING_ROLE", interaction.guild.id)

def get_ia_gov_role(interaction: discord.Interaction):
    return get_settings_value("IA STAFF", interaction.guild.id)

def get_ia_head_role(interaction: discord.Interaction = None, guild_id: str = None):
    if interaction:
        return get_settings_value("IA HEAD", interaction.guild.id)
    else:
        return get_settings_value("IA HEAD", guild_id)

def get_gov_role(interaction: discord.Interaction):
    return get_settings_value("GOV_ROLE", interaction.guild.id)

def get_aa_name(interaction: discord.Interaction):
    return get_settings_value("AA_NAME", interaction.guild.id)

def get_aa_name_guild(guild_id):
    return get_settings_value("AA_NAME", guild_id)

def get_welcome_message(interaction: discord.Interaction):
    return get_settings_value("TICKET_MESSAGE", interaction.guild.id)

def get_ticket_category(interaction: discord.Interaction):
    return get_settings_value("TICKET_CATEGORY", interaction.guild.id)

def get_colour_bloc(interaction: discord.Interaction):
    return get_settings_value("COLOUR_BLOC", interaction.guild.id)

def get_member_role(interaction: discord.Interaction):
    return get_settings_value("MEMBER_ROLE", interaction.guild.id)

def get_auto_requests_sheet(guild_id):
    """Returns a wrapper class that mimics sheet functionality but uses Supabase"""
    class AutoRequestsWrapper:
        def __init__(self, guild_id):
            self.guild_id = str(guild_id)
        
        async def get_all_values(self):
            try:
                records = supabase.select('auto_requests', filters={'guild_id': self.guild_id})
                if not records:
                    return [["DiscordID", "NationID", "Coal", "Oil", "Bauxite", "Lead", "Iron", "Food", "Uranium", "TimePeriod", "LastRequested"]]
                headers = ["DiscordID", "NationID", "Coal", "Oil", "Bauxite", "Lead", "Iron", "Food", "Uranium", "TimePeriod", "LastRequested"]
                rows = [headers]
                
                for record in records:
                    row = [
                        record.get('discord_id', ''),
                        record.get('nation_id', ''),
                        str(record.get('coal', 0)),
                        str(record.get('oil', 0)),
                        str(record.get('bauxite', 0)),
                        str(record.get('lead', 0)),
                        str(record.get('iron', 0)),
                        str(record.get('food', 0)),
                        str(record.get('uranium', 0)),
                        str(record.get('time_period', 1)),
                        record.get('last_requested', '')
                    ]
                    rows.append(row)
                
                return rows
            except Exception as e:
                print(f"❌ Error getting auto requests: {e}")
                return [["DiscordID", "NationID", "Coal", "Oil", "Bauxite", "Lead", "Iron", "Food", "Uranium", "TimePeriod", "LastRequested"]]
        
        def get_all_records(self):
            try:
                records = supabase.select('auto_requests', filters={'guild_id': self.guild_id})
                formatted_records = []
                for record in records:
                    formatted_records.append({
                        'DiscordID': record.get('discord_id', ''),
                        'NationID': record.get('nation_id', ''),
                        'Coal': record.get('coal', 0),
                        'Oil': record.get('oil', 0),
                        'Bauxite': record.get('bauxite', 0),
                        'Lead': record.get('lead', 0),
                        'Iron': record.get('iron', 0),
                        'Food': record.get('food', 0),
                        'Uranium': record.get('uranium', 0),
                        'TimePeriod': record.get('time_period', 1),
                        'LastRequested': record.get('last_requested', '')
                    })
                return formatted_records
            except Exception as e:
                print(f"❌ Error getting auto requests records: {e}")
                return []
        
        def append_row(self, row_data):
            try:
                if len(row_data) >= 11:
                    data = {
                        'guild_id': self.guild_id,
                        'discord_id': row_data[0],
                        'nation_id': row_data[1],
                        'coal': int(float(row_data[2]) if row_data[2] else 0),
                        'oil': int(float(row_data[3]) if row_data[3] else 0),
                        'bauxite': int(float(row_data[4]) if row_data[4] else 0),
                        'lead': int(float(row_data[5]) if row_data[5] else 0),
                        'iron': int(float(row_data[6]) if row_data[6] else 0),
                        'food': int(float(row_data[7]) if row_data[7] else 0),
                        'uranium': int(float(row_data[8]) if row_data[8] else 0),
                        'time_period': int(float(row_data[9]) if row_data[9] else 1),
                        'last_requested': row_data[10] if len(row_data) > 10 else ''
                    }
                    supabase.insert('auto_requests', data)
                    print(f"✅ Added auto request: {data}")
            except Exception as e:
                print(f"❌ Failed to append auto request row: {e}")
        
        def update_cell(self, row_index, col_index, value):
            try:
                records = supabase.select('auto_requests', filters={'guild_id': self.guild_id})
                if records and len(records) >= (row_index - 1):
                    record = records[row_index - 2]  # Adjust for 0-based indexing
                    record_id = record.get('id')
                    col_map = {
                        1: 'discord_id',
                        2: 'nation_id', 
                        3: 'coal',
                        4: 'oil',
                        5: 'bauxite',
                        6: 'lead',
                        7: 'iron',
                        8: 'food',
                        9: 'uranium',
                        10: 'time_period',
                        11: 'last_requested'
                    }
                    
                    field_name = col_map.get(col_index)
                    if field_name:
                        supabase.update('auto_requests', {field_name: value}, {'id': record_id})
            except Exception as e:
                print(f"❌ Failed to update auto request cell: {e}")

        def delete_rows(self, row_index):
            try:
                records = supabase.select('auto_requests', filters={'guild_id': self.guild_id})
                if records and len(records) >= (row_index - 1):
                    record = records[row_index - 2]  # Adjust for 0-based indexing
                    record_id = record.get('id')
                    supabase._make_request('DELETE', f'auto_requests?id=eq.{record_id}')
            except Exception as e:
                print(f"❌ Failed to delete auto request row: {e}")
    
    return AutoRequestsWrapper(guild_id)

def get_settings_value(key: str, server_id: int):
    try:
        records = supabase.select('server_settings', filters={'server_id': str(server_id), 'key': key})
        if records:
            return records[0].get('value')
        return None
    except Exception as e:
        print(f"❌ Error getting setting {key} for server {server_id}: {e}")
        return None
    
def get_settings_updated_at(key: str, server_id: int):
    try:
        records = supabase.select('server_settings', filters={'server_id': str(server_id), 'key': key})
        if records:
            updated_at = records[0].get('updated_at')
            if updated_at:
                if isinstance(updated_at, str):
                    updated_at = datetime.datetime.fromisoformat(updated_at.replace('Z', '+00:00'))
                if updated_at.tzinfo is None:
                    updated_at = updated_at.replace(tzinfo=datetime.timezone.utc)
                return updated_at
        return None
    except Exception as e:
        print(f"❌ Error getting updated_at for {key} in server {server_id}: {e}")
        return None
    
import datetime
import math

def get_quota_due_date(guild_id: int):
    try:
        from settings.settings_multi import get_settings_updated_at, get_quota_expiery
        quota_days = get_quota_due(guild_id)
        print(f"DAYS: {quota_days}")
        try:
            quota_days = int(quota_days)
        except (TypeError, ValueError):
            quota_days = 7

        print(f"DAYS AFTER INTIFY: {quota_days}")
        updated_at = get_settings_updated_at('QUOTA DUE', guild_id)
        print(updated_at)
        now = datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc)
        print(now)

        if not updated_at:
            return now + datetime.timedelta(days=quota_days)

        if isinstance(updated_at, str):
            updated_at = datetime.datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
        if updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=datetime.timezone.utc)

        due_date = updated_at + datetime.timedelta(days=quota_days)
        return due_date
    except Exception:
        return datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc) + datetime.timedelta(days=7)


def get_quota_days_remaining(guild_id: int):
    try:
        from settings.settings_multi import get_settings_updated_at, get_quota_expiery
        quota_days = get_quota_due(guild_id)
        try:
            quota_days = int(quota_days)
        except (TypeError, ValueError):
            quota_days = 7

        updated_at = get_settings_updated_at('QUOTA DUE', guild_id)
        now = datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc)

        if not updated_at:
            return quota_days

        if isinstance(updated_at, str):
            updated_at = datetime.datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
        if updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=datetime.timezone.utc)

        seconds_passed = (now - updated_at).total_seconds()
        days_passed = math.floor(seconds_passed / 86400)
        days_remaining = quota_days - days_passed

        return max(0, days_remaining)
    except Exception:
        return 7


def set_server_setting(server_id, key, value):
    try:
        server_id = str(server_id)
        key = key.strip().upper()
        print(key)
        existing = supabase.select('server_settings', filters={'server_id': server_id, 'key': key})
        
        if existing:
            supabase.update(
                'server_settings',
                {
                    'value': str(value),
                    'updated_at': datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc).isoformat()
                },
                {'server_id': server_id, 'key': key}
            )
        else:
            data = {
                'server_id': server_id,
                'key': key,
                'value': str(value)
            }
            supabase.insert('server_settings', data)
    except Exception as e:
        print(f"❌ Failed to set server setting: {e}")

def get_server_setting(server_id, key):
    try:
        server_id = str(server_id)
        key = key.strip().upper()
        records = supabase.select('server_settings', filters={'server_id': server_id, 'key': key})
        if records:
            return records[0].get('value')
        return None
    except Exception as e:
        print(f"❌ Error getting server setting: {e}")
        return None

def list_server_settings(server_id):
    try:
        server_id = str(server_id)
        records = supabase.select('server_settings', filters={'server_id': server_id})
        return [(record['key'], record['value']) for record in records]
    except Exception as e:
        print(f"❌ Error listing server settings: {e}")
        return []

SETTING_CHOICES = [
    app_commands.Choice(name="GRANT_REQUEST_CHANNEL_ID(optional)", value="GRANT_REQUEST_CHANNEL_ID"),
    app_commands.Choice(name="WARN_CHANNEL(optional)", value="WARN_CHANNEL"),
    app_commands.Choice(name="GOV_ROLE", value="GOV_ROLE"),
    app_commands.Choice(name="API_KEY", value="API_KEY"),
    app_commands.Choice(name="LOGS(optional)", value="LOGS"),
    app_commands.Choice(name="MEMBER_ROLE", value="MEMBER_ROLE"),
    app_commands.Choice(name="COLOUR_BLOC", value="COLOUR_BLOC"),
    app_commands.Choice(name="AA_NAME", value="AA_NAME"),
    app_commands.Choice(name="BANKING_ROLE", value="BANKING_ROLE"),
]

@bot.tree.command(name="set_setting", description="Set a server setting (e.g. GRANT_REQUEST_CHANNEL_ID).")
@app_commands.describe(key="The setting key", value="The value to store")
@app_commands.choices(key=SETTING_CHOICES)
async def set_setting(interaction: discord.Interaction, key: app_commands.Choice[str], value: str):
    await interaction.response.defer(ephemeral=True)
    raw_value = value.strip()
    if raw_value.startswith("<@&") and raw_value.endswith(">"):
        role_id = int(raw_value.replace("<@&", "").replace(">", ""))
        role = interaction.guild.get_role(role_id)
        if role:
            value = role.name
        else:
            await interaction.followup.send(f"❌ Could not find role with ID `{role_id}`.", ephemeral=True)
            return
    elif raw_value.startswith("<#") and raw_value.endswith(">"):
        value = raw_value.replace("<#", "").replace(">", "")

    guild = interaction.guild
    guild_id = interaction.guild_id
    if guild is None or guild_id is None:
        await interaction.followup.send("❌ This command can only be used in a server.", ephemeral=True)
        return

    gov_role_id = get_gov_role(interaction)
    member = await guild.fetch_member(interaction.user.id)
    key_value = key.value if hasattr(key, "value") else key
    key_value = key_value.strip().lower()

    if gov_role_id is None:
        set_server_setting(guild_id, key_value, value)
        await interaction.followup.send(f"✅ {key_value} set to `{value}`.", ephemeral=True)
        return

    if not any(role.name == gov_role_id for role in member.roles):
        await interaction.followup.send("❌ You do not have permission to use this command. Only members with the GOV_ROLE can set settings.", ephemeral=True)
        return

    try:
        set_server_setting(guild_id, key_value, value)
        await interaction.followup.send(f"✅ `{key_value}` set to `{value}`.", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ Failed to set setting: {e}", ephemeral=True)

bot.command(name="set_setting")(wrap_as_prefix_command(set_setting.callback))

@bot.tree.command(name="get_setting", description="Get a server setting.")
@app_commands.describe(key="The setting key to retrieve")
async def get_setting(interaction: discord.Interaction, key: str):
    await interaction.response.defer()
    if key.lower() == "api_key":
        return await interaction.followup.send("❌ To get the API Key please contact <@1148678095176474678>")
    server_id = interaction.guild_id
    value = get_server_setting(server_id, key)
    if value is not None:
        await interaction.followup.send(f"🔍 `{key}`: `{value}`", ephemeral=True)
    else:
        await interaction.followup.send(f"❌ `{key}` not found for this server.", ephemeral=True)

bot.command(name="get_setting")(wrap_as_prefix_command(get_setting.callback))

@bot.tree.command(name="list_settings", description="List all settings for this server.")
async def list_settings(interaction: discord.Interaction):
    await interaction.response.defer()
    server_id = interaction.guild_id
    settings = list_server_settings(server_id)

    if not settings:
        await interaction.followup.send("No settings found for this server.", ephemeral=True)
    else:
        filtered = [(k, v) for k, v in settings if k.upper() != "API_KEY"]
        msg = "\n".join(f"- `{k}` = `{v}`" for k, v in filtered)
        await interaction.followup.send(f"🔧 Settings:\n{msg}", ephemeral=True)

bot.command(name="list_settings")(wrap_as_prefix_command(list_settings.callback))