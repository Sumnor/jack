import discord
from discord import app_commands
import os
import requests
from bs4 import BeautifulSoup
from settings.bot_instance import bot, wrap_as_prefix_command
from settings.initializer_functions.cached_users_initializer import cached_users, load_sheet_data, get_registration_sheet, supabase
from settings.settings_multi import get_member_role
from databases.graphql_requests import get_general_data

@bot.tree.command(name="register", description="Register your Nation ID")
@app_commands.describe(nation_id="Your Nation ID (numbers only, e.g., 365325)")
async def register(interaction: discord.Interaction, nation_id: str):
    await interaction.response.defer()
    user_id = interaction.user.id
    data = get_general_data(nation_id, None, API_KEY=os.getenv("API_KEY"))
    aa_name = data[2]
    user_data = cached_users.get(str(user_id))
    
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
    print(f"🔍 Checking duplicates in global registration")
    print(f"📊 Current users in global cache: {len(global_users)}")
    print(f"👤 User ID: {user_id}, Username: {user_discord_username}, Nation: {nation_id_str}")
    
    for uid, data in global_users.items():
        if user_discord_username not in ["sumnor", "sumnorintra"]:
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
        existing_discord = supabase.select('users', filters={'discord_id': user_id})
        if existing_discord:
            await interaction.followup.send(f"❌ This Discord ID ({user_id}) is already registered.")
            return
        
        existing_nation = supabase.select('users', filters={'nation_id': nation_id_str})
        if existing_nation:
            await interaction.followup.send(f"❌ This Nation ID ({nation_id_str}) is already registered.")
            return
        
        all_users = supabase.select('users')
        for user in all_users:
            if user.get('discord_username', '').lower() == user_discord_username:
                await interaction.followup.send(f"❌ This Discord username ({user_discord_username}) is already registered.")
                return
        
    except Exception as e:
        print(f"❌ Error checking duplicates in Supabase: {e}")
        await interaction.followup.send("❌ Database error while checking for duplicates. Please try again.")
        return
    
    try:
        sheet = get_registration_sheet(None)
        sheet.append_row([interaction.user.name, user_id, nation_id, aa_name])
        print(f"📝 Added registration for {interaction.user.name} (ID: {user_id}) to Supabase")
    except Exception as e:
        await interaction.followup.send(f"❌ Failed to write registration: {e}")
        return
    
    try:
        load_sheet_data()
        print(f"✅ Reloaded global cache after registration")
    except Exception as e:
        print(f"⚠️ Failed to reload cached data: {e}")

    await interaction.followup.send("✅ You're registered successfully!")

bot.command(name="register")(wrap_as_prefix_command(register.callback))