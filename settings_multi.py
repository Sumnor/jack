import discord
from discord import app_commands
from typing import Optional
from bot_instance import bot
from utils import get_client

def get_warn_channel(guild_id):
    try:
        sheet = get_settings_sheet()
        rows = sheet.get_all_records()

        for row in rows:
            if str(row.get("server_id")) == str(guild_id) and row.get("key") == "WARN_CHANNEL":
                value = row.get("value")
                return str(value).strip() if value is not None else None

        print(f"⚠️ WARN_CHANNEL not found for guild {guild_id}")
        return None

    except Exception as e:
        print(f"❌ Error fetching warn channel for guild {guild_id}: {e}")
        return None

def get_grant_channel(guild_id):
    try:
        sheet = get_settings_sheet()
        rows = sheet.get_all_records()

        for row in rows:
            if str(row.get("server_id")) == str(guild_id) and row.get("key") == "GRANT_REQUEST_CHANNEL_ID":
                value = row.get("value")
                return str(value).strip() if value is not None else None

        print(f"⚠️ GRANT_REQUEST_CHANNEL_ID not found for guild {guild_id}")
        return None

    except Exception as e:
        print(f"❌ Error fetching grant channel for guild {guild_id}: {e}")
        return None

def get_dm_sheet():
    client = get_client()
    return client.open("DmsSentByGov").sheet1

def get_alliance_sheet(guild_id):
    client = get_client()
    return client.open(f"{guild_id}_AllianceNet").sheet1

def get_auto_requests_sheet(guild_id):
    client = get_client()
    return client.open(f"{guild_id}_AutoRequests").sheet1  

def get_api_key_for_interaction(interaction: discord.Interaction) -> str:
    return get_settings_value("API_KEY", interaction.guild.id)

def get_api_key_for_guild(guild_id: int) -> str | None:
    try:
        sheet = get_settings_sheet()
        rows = sheet.get_all_records()

        for row in rows:
            if str(row.get("server_id")) == str(guild_id) and row.get("key") == "API_KEY":
                print(row.get("value").strip())
                return row.get("value").strip()

        print(f"⚠️ API_KEY not found for guild {guild_id}")
        return None

    except Exception as e:
        print(f"❌ Error fetching API key for guild {guild_id}: {e}")
        return None

def get_banking_role(interaction: discord.Interaction):
    return get_settings_value("BANKING_ROLE", interaction.guild.id)

def get_gov_role(interaction: discord.Interaction):
    return get_settings_value("GOV_ROLE", interaction.guild.id)

def get_aa_name(interaction: discord.Interaction):
    return get_settings_value("AA_NAME", interaction.guild.id)

def get_welcome_message(interaction: discord.Interaction):
    return get_settings_value("TICKET_MESSAGE", interaction.guild.id)

def get_ticket_category(interaction: discord.Interaction):
    return get_settings_value("TICKET_CATEGORY", interaction.guild.id)

def get_colour_bloc(interaction: discord.Interaction):
    return get_settings_value("COLOUR_BLOC", interaction.guild.id)

def get_member_role(interaction: discord.Interaction):
    return get_settings_value("MEMBER_ROLE", interaction.guild.id)

def get_server_sheet():
    client = get_client()
    return client.open("BotServerSettings").sheet1  # Your sheet must have: server_id | api_key | lott_channel_ids
def save_server_settings(server_id, api_key=None, lott_ids=None):
    sheet = get_server_sheet()
    server_id = str(server_id)
    records = sheet.get_all_records()
    row_idx = None

    for i, row in enumerate(records):
        if str(row["server_id"]) == server_id:
            row_idx = i + 2
            break

    if row_idx:
        if api_key is not None:
            sheet.update_cell(row_idx, 2, api_key)
        if lott_ids is not None:
            sheet.update_cell(row_idx, 3, ",".join(lott_ids))
    else:
        sheet.append_row([server_id, api_key or "", ",".join(lott_ids) if lott_ids else ""])

def get_server_settings(server_id):
    sheet = get_server_sheet()
    server_id = str(server_id)
    records = sheet.get_all_records()
    for row in records:
        if str(row["server_id"]) == server_id:
            return {
                "api_key": row["api_key"],
                "lott_channel_ids": row["lott_channel_ids"].split(",") if row["lott_channel_ids"] else []
            }
    return {}

def get_settings_value(key: str, server_id: int) -> Optional[str]:
    sheet = get_settings_sheet()  # Make sure this returns the BotServerSettings sheet
    records = sheet.get_all_records()

    for row in records:
        if str(row["server_id"]) == str(server_id) and row["key"] == key:
            return row["value"]
    return None

def get_settings_sheet():
    client = get_client()
    sheet = client.open("BotServerSettings")
    try:
        return sheet.worksheet("Settings")
    except:
        return sheet.add_worksheet(title="Settings", rows="1000", cols="3")
def set_server_setting(server_id, key, value):
    sheet = get_settings_sheet()
    records = sheet.get_all_records()
    server_id = str(server_id)
    key = key.strip().upper()
    row_idx = None

    for i, row in enumerate(records):
        if str(row["server_id"]) == server_id and row["key"].strip().upper() == key:
            row_idx = i + 2
            break

    if row_idx:
        sheet.update_cell(row_idx, 3, str(value))
    else:
        sheet.append_row([server_id, key, value])

def get_server_setting(server_id, key):
    sheet = get_settings_sheet()
    server_id = str(server_id)
    key = key.strip().upper()
    records = sheet.get_all_records()
    for row in records:
        if str(row["server_id"]) == server_id and row["key"].strip().upper() == key:
            return row["value"]
    return None

def list_server_settings(server_id):
    sheet = get_settings_sheet()
    server_id = str(server_id)
    return [
        (row["key"], row["value"])
        for row in sheet.get_all_records()
        if str(row["server_id"]) == server_id
    ]


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

    gov_role_id = get_gov_role(interaction)  # Implemented elsewhere
    member = await guild.fetch_member(interaction.user.id)

    if gov_role_id is None:
        set_server_setting(guild_id, key.value, value)
        await interaction.followup.send(f"✅ {key.value} set to `{value}`.", ephemeral=True)
        return

    if not any(role.name == gov_role_id for role in member.roles):
        await interaction.followup.send("❌ You do not have permission to use this command. Only members with the GOV_ROLE can set settings.", ephemeral=True)
        return

    try:
        set_server_setting(guild_id, key.value, value)
        await interaction.followup.send(f"✅ `{key.value}` set to `{value}`.", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ Failed to set setting: {e}", ephemeral=True)

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