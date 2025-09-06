import discord
from discord import app_commands
import os
import requests
from bs4 import BeautifulSoup
import random
import pandas as pd
import datetime
import asyncio
from bot_instance import bot, YT_Key
from utils import cached_users, load_sheet_data, get_registration_sheet, get_client
from settings_multi import get_member_role
from graphql_requests import get_general_data

@bot.tree.command(name="register", description="Register your Nation ID")
@app_commands.describe(nation_id="Your Nation ID (numbers only, e.g., 365325)")
async def register(interaction: discord.Interaction, nation_id: str):
    await interaction.response.defer()
    user_id = interaction.user.id
    data = get_general_data(nation_id, None, API_KEY=os.getenv("API_KEY"))
    aa_name = data[2]
    user_data = cached_users.get(user_id)
    if user_data:
        await interaction.followup.send(
            "❌ You are already registered.", ephemeral=True
        )
        return
    MEMBER_ROLE = get_member_role(interaction)
    async def is_banker(interaction):
        return (
            any(role.name == MEMBER_ROLE for role in interaction.user.roles)
            or str(interaction.user.id) == "1148678095176474678"
        )

    if not await is_banker(interaction):
        await interaction.followup.send("❌ You need to be a Member to register yourself.")
        return

    if not nation_id.isdigit():
        await interaction.followup.send("❌ Please enter only the Nation ID number, not a link.")
        return
    url = f"https://politicsandwar.com/nation/id={nation_id}"
    try:
        response = requests.get(url)
        response.raise_for_status()
    except Exception:
        await interaction.followup.send("❌ Failed to fetch nation data. Try again later.")
        return

    soup = BeautifulSoup(response.text, 'html.parser')
    discord_label = soup.find(string="Discord Username:")
    if not discord_label:
        await interaction.followup.send("❌ Invalid Nation ID or no Discord username listed.")
        return

    try:
        nation_discord_username = discord_label.parent.find_next_sibling("td").text.strip().lower()
    except Exception:
        await interaction.followup.send("❌ Could not parse nation information.")
        return

    user_discord_username = interaction.user.name.strip().lower()
    user_id = str(interaction.user.id)
    nation_id_str = str(nation_id).strip()
    print(f"🔄 Force reloading global registration data")
    load_sheet_data()
    if user_discord_username != "sumnor":
        cleaned_nation_username = nation_discord_username.replace("#0", "")
        if cleaned_nation_username != user_discord_username:
            await interaction.followup.send(
                f"❌ Username mismatch.\nNation lists: `{nation_discord_username}`\nYour Discord: `{user_discord_username}`"
            )
            return
    global_users = cached_users
    print(f"🔍 Checking duplicates in global registration sheet")
    print(f"📊 Current users in global cache: {len(global_users)}")
    print(f"👤 User ID: {user_id}, Username: {user_discord_username}, Nation: {nation_id_str}")
    for uid, data in global_users.items():
        print(f"  - Cached: ID={uid}, Username={data.get('DiscordUsername')}, Nation={data.get('NationID')}")

    for uid, data in global_users.items():
        if user_discord_username != "sumnor":  # Sumnor can always register
            if uid == user_id:
                await interaction.followup.send(f"❌ This Discord ID ({user_id}) is already registered.")
                return
            if data.get('DiscordUsername', '').lower() == user_discord_username:
                await interaction.followup.send(f"❌ This Discord username ({user_discord_username}) is already registered.")
                return
            if data.get('NationID') == nation_id_str:
                await interaction.followup.send(f"❌ This Nation ID ({nation_id_str}) is already registered.")
                return
    try:
        dummy_guild_id = "I'm too lazy to remove it from get_registration_sheet so this is a dummy"
        sheet = get_registration_sheet(dummy_guild_id)
        sheet.append_row([interaction.user.name, user_id, nation_id, aa_name])
        print(f"📝 Added registration for {interaction.user.name} (ID: {user_id}) to global sheet")
    except Exception as e:
        await interaction.followup.send(f"❌ Failed to write registration: {e}")
        return
    try:
        load_sheet_data()
        print(f"✅ Reloaded global cache after registration")
    except Exception as e:
        print(f"⚠️ Failed to reload cached sheet data: {e}")

    await interaction.followup.send("✅ You're registered successfully!")

@bot.tree.command(name="register_server_aa", description="Register this server and create Google Sheets")
@app_commands.checks.has_permissions(administrator=True)
async def register_server_aa(interaction: discord.Interaction):
    await interaction.response.defer()
    guild = interaction.guild
    if guild is None:
        await interaction.followup.send("This command can only be used in a guild.", ephemeral=True)
        return

    server_id = str(guild.id)
    share_email = "savior@inbound-analogy-459312-i4.iam.gserviceaccount.com"
    sum_email = "rodipoltavskyi@gmail.com"

    try:
        client = get_client()

        alliance_title = f"{server_id}_AllianceNet"
        alliance_headers = [
            "TimeT", "TotalMoney", "Money", "Food", "Gasoline", "Munitions",
            "Steel", "Aluminum", "Bauxite", "Lead", "Iron", "Oil", "Coal", "Uranium"
        ]
        alliance_spreadsheet = client.create(alliance_title)
        alliance_ws = alliance_spreadsheet.get_worksheet(0)
        alliance_ws.update_title("Snapshot")
        alliance_ws.append_row(alliance_headers)
        alliance_spreadsheet.share(share_email, perm_type="user", role="writer")
        alliance_spreadsheet.share(sum_email, perm_type="user", role="writer")

        auto_title = f"{server_id}_AutoRequests"
        auto_headers = ["DiscordID", "NationID", "Coal", "Oil", "Bauxite", "Lead", "Iron", "TimePeriod", "LastRequested"]
        auto_spreadsheet = client.create(auto_title)
        auto_ws = auto_spreadsheet.get_worksheet(0)
        auto_ws.update_title("Requests")
        auto_ws.append_row(auto_headers)
        auto_spreadsheet.share(share_email, perm_type="user", role="writer")
        auto_spreadsheet.share(sum_email, perm_type="user", role="writer")

        await interaction.followup.send(
            f"✅ Created registration sheets for server **{guild.name}**:\n"
            f"- `{alliance_title}`\n"
            f"- `{auto_title}`"
        )

    except Exception as e:
        await interaction.followup.send(f"❌ Failed to create sheets: {e}", ephemeral=True)

@bot.tree.command(name=f"bot_info_and_invite", description="Get the Info and invite for me")
async def bot_info(interaction: discord.Interaction):
    now = datetime.datetime.now()
    unix_timestamp = int(now.timestamp())
    Status = os.getenv("STATUS", "ERROR")
    messages = (
    "- Name: Jack\n"
    "- Discriminator: #8205\n"
    "- User ID: ```1367997847978377247```\n"
    f"- Current Date: <t:{unix_timestamp}:d>\n"
    f"- Command Called: <t:{unix_timestamp}:R>\n"
    f"- STATUS: {Status}\n"
    "- Bugs Dashboard: [Jack's Dashboard](https://jack-support.streamlit.app)\n"
    "- Help Server: [Jack Support](https://discord.gg/qqtb3kccjv)\n"
    "- Script: [Github](https://github.com/Sumnor/jack/tree/main)\n"
    "- Invite: [Jack](https://discord.com/oauth2/authorize?client_id=1367997847978377247&permissions=201444368&scope=bot%20applications.commands)"
)
    embed = discord.Embed(
        title="BOT INFO",
        colour=discord.Colour.brand_green(),
        description=messages
    )

    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="run_check", description="Manual update of members")
async def run_check_slash(interaction: discord.Interaction):
    await interaction.response.defer()
    guild_id = str(interaction.guild.id)

    try:
        sheet = get_registration_sheet(guild_id)
        records = sheet.get_all_records()
        df = pd.DataFrame(records)
        df.columns = [col.strip() for col in df.columns]

        if "NationID" not in df.columns:
            await interaction.followup.send("❌ 'NationID' column missing in the sheet.")
            return

        for index, row in df.iterrows():
            nation_id = row.get("NationID")
            if not nation_id:
                continue

            result = get_general_data(nation_id, interaction)
            if result is None or len(result) < 7:
                print(f"Failed to retrieve data for nation {nation_id}")
                continue

            _, _, alliance_name, _, _, _, last_active, *_ = result
            cell_range = f"D{index + 2}"
            sheet.update_acell(cell_range, alliance_name)
            print(f"Updated nation {nation_id} with AA: {alliance_name}")
            await asyncio.sleep(3)  # 50 per minute ~= 1.2 seconds delay

        await interaction.followup.send("Manual member update completed.")

    except Exception as e:
        await interaction.followup.send(f"Error during manual update: {e}")


@bot.tree.command(name="warn_maint", description="Notify users of bot maintenance (Dev only)")
async def warn_maint(interaction: discord.Interaction, time: str):
    await interaction.response.defer()
    user_id = str(interaction.user.id)

    if user_id != "1148678095176474678":
        await interaction.followup.send("You don't have the required permission level", ephemeral=True)
        return

    try:
        
        CHANNEL_ID = "UC_ID-A3YnSQXCwyIcCs9QFw"

        
        search_url = 'https://www.googleapis.com/youtube/v3/search'
        search_params = {
            'part': 'snippet',
            'channelId': CHANNEL_ID,
            'maxResults': 50,
            'order': 'date',
            'type': 'video',
            'key': YT_Key
        }
        search_response = requests.get(search_url, params=search_params)
        video_ids = [item['id']['videoId'] for item in search_response.json().get('items', []) if item['id'].get('videoId')]

        
        videos_url = 'https://www.googleapis.com/youtube/v3/videos'
        videos_params = {
            'part': 'contentDetails',
            'id': ','.join(video_ids),
            'key': YT_Key
        }
        videos_response = requests.get(videos_url, params=videos_params)
        shorts = [
            f"https://www.youtube.com/shorts/{item['id']}"
            for item in videos_response.json().get('items', [])
            if parse_duration(item['contentDetails']['duration']) <= 60
        ]

        
        chosen_vid = random.choice(shorts) if shorts else "https://www.youtube.com"

        
        msg = (
            f"⚠️ **Bot Maintenance Notice** ⚠️\n\n"
            f"🔧 The bot will be undergoing maintenance **until {time} (UTC +2)**.\n"
            f"❌ Please **do not** accept, deny, or copy grant codes during this time.\n"
            f"🛑 Also avoid using any of the bot's commands.\n\n"
            f"We’ll be back soon! Sorry for any inconvenience this may cause.\n"
            f"If you have questions, please ping @Sumnor.\n"
            f"P.S.: If you're bored, watch this: {chosen_vid}"
        )
        await interaction.followup.send(msg)

    except Exception as e:
        await interaction.followup.send(f"❌ Failed to send maintenance warning: `{e}`")

def parse_duration(duration):
    duration = duration.replace('PT', '')
    hours, minutes, seconds = 0, 0, 0

    if 'H' in duration:
        hours, duration = duration.split('H')
        hours = int(hours)

    if 'M' in duration:
        minutes, duration = duration.split('M')
        minutes = int(minutes)

    if 'S' in duration:
        seconds = int(duration.replace('S', ''))

    return hours * 3600 + minutes * 60 + seconds
