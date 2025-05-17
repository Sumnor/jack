import discord
import json
import math
import pandas as pd
from pandas import json_normalize
from discord import app_commands, Interaction, ButtonStyle
from discord import app_commands
from discord.ext import commands
import requests
from dotenv import load_dotenv
from bs4 import BeautifulSoup
from discord.ui import View, Modal, TextInput, button
from discord.ui import Button, View
import random
import os
import json
import re
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import discord
from discord import app_commands, Interaction


load_dotenv("cred.env")
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="/", intents=intents)
bot_key = os.getenv("bot_key")
API_KEY = os.getenv("API_KEY")
YT_Key = os.getenv("YT_Key")
commandscalled = {"_global": 0}

UNIT_PRICES = {
    "soldiers": 5,
    "tanks": 60,
    "aircraft": 4000,
    "ships": 50000,
    "missiles": 150000,
    "nuclear": 1750000
}

BANK_PERMISSION_TYPE = "Nation Deposit to Bank"

class MessageView(View):
    def __init__(self, description_text):
        super().__init__()
        self.description_text = description_text

    @discord.ui.button(label="Generate Message", style=discord.ButtonStyle.green, custom_id="gm_message_button")
    async def copy_message_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer()
        await interaction.followup.send(
            f"COPY THE FOLLOWING:\n"
            "Go to the #💰︱essential-grants channel and request this with the /request_grant command:\n\n"
            f"{self.description_text}\n\nOr use the `/warchest` command.",
            ephemeral=True
        )


class BlueGuy(discord.ui.View):
    def __init__(self, category=None, data=None):
        super().__init__(timeout=None)
        self.category = category
        self.data = data or {}

    @discord.ui.button(label="Request Grant", style=discord.ButtonStyle.green, custom_id="req_money_needed")
    async def send_request(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()

        embed = discord.Embed(title="Request Grant", color=discord.Color.green())

        reason = "Unknown Request"
        materials = {}
        nation_name = self.data.get("nation_name", "?")
        nation_id = self.data.get("nation_id", "unknown")

        # Set up Reason and Materials
        if self.category == "infra":
            from_level = self.data.get("from", "?")
            to_level = self.data.get("infra", "?")
            cities = self.data.get("ct_count", "?")
            reason = f"Upgrade infrastructure from {from_level} to {to_level} in {cities} cities"
            materials = {"Money": self.data.get("total_cost", 0)}

        elif self.category == "city":
            from_cities = self.data.get("from", "?")
            to_cities = self.data.get("city_num", "?")
            ct_num = to_cities - from_cities
            reason = f"Buy {ct_num} new cities"
            materials = {"Money": self.data.get("total_cost", 0)}

        elif self.category == "project":
            project_name = self.data.get("project_name", "?")
            reason = f"Build project: {project_name}"
            materials = self.data.get("materials", {})

        # Start embed description
        description_lines = [f"**Nation:** {nation_name} (`{nation_id}`)", "**Request:**"]
        if materials:
            for name, amount in materials.items():
                description_lines.append(f"{name}: {amount:,.0f}")
        else:
            description_lines.append("None")

        description_lines.append(f"\n**Requested by:** {interaction.user.mention}")
        embed.description = "\n".join(description_lines)

        # Reason field
        embed.add_field(name="Reason", value=reason, inline=False)

        # Footer
        image_url = "https://i.ibb.co/qJygzr7/Leonardo-Phoenix-A-dazzling-star-emits-white-to-bluish-light-s-2.jpg"
        embed.set_footer(text="Brought to you by Darkstar", icon_url=image_url)

        await interaction.message.edit(embed=embed, view=GrantView())



class GrantView(View):
    def __init__(self):
        super().__init__(timeout=None)

    async def is_government_member(self, interaction):
        return (
            any(role.name == "Banker" for role in interaction.user.roles)
            or str(interaction.user.id) == "1148678095176474678"
        )

    @button(label="✅ Sent", style=discord.ButtonStyle.green, custom_id="grant_approve")
    async def approve_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.is_government_member(interaction):
            try:
                await interaction.response.send_message("❌ You need the 'Banker' role to approve grant requests.", ephemeral=True)
            except discord.NotFound:
                pass  # interaction might have expired
            return

        try:
            embed = interaction.message.embeds[0]
            embed.color = discord.Color.green()
            embed.description += f"\n**Status:** ✅ **GRANT SENT**"

            image_url = "https://i.ibb.co/qJygzr7/Leonardo-Phoenix-A-dazzling-star-emits-white-to-bluish-light-s-2.jpg"
            embed.set_footer(text="Brought to you by Darkstar", icon_url=image_url)

            await interaction.message.edit(embed=embed, view=None)

            lines = embed.description.splitlines()
            user_mention = "@someone"
            for line in lines:
                if line.startswith("**Requested by:**"):
                    user_mention = line.split("**Requested by:**")[1].strip()
                    break

            try:
                await interaction.followup.send(f"✅ Grant request has been approved and sent! {user_mention}", ephemeral=False)
            except discord.NotFound:
                # Fallback if followup webhook is expired
                await interaction.channel.send(f"✅ Grant request has been approved and sent! {user_mention}")

        except Exception as e:
            try:
                await interaction.followup.send(f"❌ Error: `{e}`", ephemeral=True)
            except discord.NotFound:
                await interaction.channel.send(f"❌ Error (no followup): `{e}`")


    @button(label="🕒 Delay", style=discord.ButtonStyle.primary, custom_id="grant_delay")
    async def delay_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.is_government_member(interaction):
            await interaction.followup.send("❌ You need the 'Banker' role to delay grant requests.", ephemeral=True)
            return

        try:
            embed = interaction.message.embeds[0]
            embed.color = discord.Color.orange()
            embed.description += f"\n**Status:** 🕒 **DELAYED**"
            image_url = "https://i.ibb.co/qJygzr7/Leonardo-Phoenix-A-dazzling-star-emits-white-to-bluish-light-s-2.jpg"
            embed.set_footer(text=f"Brought to you by Darkstar", icon_url=image_url)

            new_view = GrantView()
            new_view.remove_item(new_view.children[1]) 

            await interaction.message.edit(embed=embed, view=new_view)
            await interaction.message.pin()
            await interaction.response.send_message("✅ Grant delayed and message pinned.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Error: `{e}`", ephemeral=True)

    @button(label="❌ Deny", style=discord.ButtonStyle.red, custom_id="grant_denied")
    async def deny_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.is_government_member(interaction):
            await interaction.response.send_message("❌ You need the 'Banker' role to deny grant requests.", ephemeral=True)
            return
        try:
            embed = interaction.message.embeds[0]
            embed.color = discord.Color.red()
            embed.description += f"\n**Status:** ❌ **GRANT DENIED**"
            image_url = "https://i.ibb.co/qJygzr7/Leonardo-Phoenix-A-dazzling-star-emits-white-to-bluish-light-s-2.jpg"
            embed.set_footer(text=f"Brought to you by Darkstar", icon_url=image_url)
            await interaction.message.edit(embed=embed, view=None)
        except Exception as e:
            await interaction.response.send_message(f"❌ Error: `{e}`", ephemeral=True)

    @button(label="Copy Command", style=discord.ButtonStyle.blurple, custom_id="copied")
    async def copy_command(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.is_government_member(interaction):
            await interaction.response.send_message("❌ You need the 'Banker' role to approve grant requests.", ephemeral=True)
            return

        try:
            embed = interaction.message.embeds[0]
            lines = embed.description.splitlines()

            nation_line = next((line for line in lines if line.startswith("**Nation:**")), None)
            nation_id = nation_line.split("(`")[1].strip("`)") if nation_line else "unknown"

            try:
                request_start = lines.index("**Request:**") + 1
            except ValueError:
                await interaction.response.send_message("❌ Could not find '**Request:**' in embed.", ephemeral=True)
                return

            try:
                reason_index = next(i for i, line in enumerate(lines) if line.startswith("**Reason:**"))
            except StopIteration:
                reason_index = len(lines)

            request_lines = lines[request_start:reason_index]

            abbr_map = {
                "Money": "-$",
                "Gasoline": "-g",
                "Munitions": "-m",
                "Steel": "-s",
                "Aluminum": "-a",
                "Food": "-f",
                "Oil": "-o",
                "Uranium": "-u",
                "Lead": "-l",
                "Iron": "-I",
                "Bauxite": "-b"
            }

            command_parts = [f"$tfo -t https://politicsandwar.com/nation/id={nation_id}"]
            for line in request_lines:
                if ":" not in line:
                    continue
                key, val = [x.strip() for x in line.split(":", 1)]
                if key not in abbr_map:
                    continue
                val = val.replace(".", "").replace(",", "").strip()
                try:
                    num = int(val)
                    command_parts.append(f"{abbr_map[key]} {num}")
                except ValueError:
                    continue

            await interaction.response.send_message(f"***TARS COMMAND: {' '.join(command_parts)}***", ephemeral=True)

        except Exception as e:
            await interaction.response.send_message(f"❌ Error parsing embed: `{e}`", ephemeral=True)




def get_military_o(nation_id):
    session = requests.Session()
    url = f"https://politicsandwar.com/nation/id={nation_id}"
    response = session.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')

    def extract_stat(label_text):
        label = soup.find(string=lambda s: s and label_text in s)
        if not label or not label.parent:
            return "❌ Not Found"
        td = label.parent.find_next_sibling("td")
        if not td:
            return "❌ Missing Data"
        return "".join(t for t in td.find_all(string=True, recursive=False)).strip()

    def get_first_value(value):
        return value.split()[0]

    nation_name = extract_stat("Nation Name:")
    nation_leader = extract_stat("Leader Name:")
    nation_rank = extract_stat("Nation Rank:")
    nation_score = extract_stat("Nation Score:")
    war_policy = extract_stat("War Policy:")
    soldiers = get_first_value(extract_stat("Soldiers:"))
    tanks = get_first_value(extract_stat("Tanks:"))
    aircraft = get_first_value(extract_stat("Aircraft:"))
    ships = get_first_value(extract_stat("Ships:"))
    spies = get_first_value(extract_stat("Spies:"))
    missiles = get_first_value(extract_stat("Missiles:"))
    nuclear = get_first_value(extract_stat("Nuclear Weapons:"))

    return nation_name, nation_leader, nation_rank, nation_score, war_policy, soldiers, tanks, aircraft, ships, spies, missiles, nuclear

def graphql_request(nation_id):
    GRAPHQL_URL = f"https://api.politicsandwar.com/graphql?api_key={API_KEY}"

    query = f"""
    {{
      nations(id: [{nation_id}]) {{
        data {{
          id
          nation_name
          leader_name
          last_active
          alliance_id
          alliance_position
          alliance {{ name }}
          color
          warpolicy
          dompolicy
          continent
          num_cities
          score
          population
          vmode
          beigeturns
          soldiers
          tanks
          aircraft
          ships
          missiles
          nukes
          espionage_available
          spies
          money
          coal
          oil
          uranium
          iron
          bauxite
          lead
          gasoline
          munitions
          steel
          aluminum
          food
        }}
      }}
    }}
    """

    try:
        response = requests.post(
            GRAPHQL_URL,
            json={"query": query},
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
        json_data = response.json()

        if "errors" in json_data:
            print("GraphQL Errors:", json_data["errors"])
            return None

        nations_data = json_data.get("data", {}).get("nations", {}).get("data", [])
        if not nations_data:
            print("No nation data found.")
            return None

        df = pd.json_normalize(nations_data)
        return df

    except requests.RequestException as e:
        print(f"HTTP Error during GraphQL request: {e}")
        return None
    except (KeyError, TypeError, json.JSONDecodeError) as e:
        print(f"Parsing Error: {e}")
        return None


def get_resources(nation_id):
    df = graphql_request(nation_id)
    if df is not None:
        try:
            row = df[df["id"] == nation_id].iloc[0]
            
            return (
                row.get("nation_name", ""),
                row.get("num_cities", 0),
                row.get("food", 0),
                row.get("money", 0),
                row.get("gasoline", 0),
                row.get("munitions", 0),
                row.get("steel", 0),
                row.get("aluminum", 0)
            )
        except IndexError:
            return None


def get_military(nation_id):
    df = graphql_request(nation_id)
    if df is not None:
        try:
            row = df[df["id"] == nation_id].iloc[0]
            
            return (
                row.get("nation_name", ""),
                row.get("leader_name", ""),
                row.get("score", 0),
                row.get("warpolicy"),
                row.get("soldiers", 0),
                row.get("tanks", 0),
                row.get("aircraft", 0),
                row.get("ships", 0),
                row.get("spies", 0),
                row.get("missiles", 0),
                row.get("nukes", 0)
            )
        except IndexError:
            return None



def calculation(name, a, b, policy, war_type):
    unit_price = UNIT_PRICES.get(name, 0)
    c = a - b

    if b == 0:
        res = 100 if a > 0 else 50
    elif a == 0:
        res = 0
    elif c == 0:
        res = 100
    elif a > b:
        res = min(100, (c / b) * 100)
    else:
        res = 0

    if war_type == "Raid":
        res *= 1.25
    elif war_type == "Attrition":
        res *= 1.0

    if policy == "Pirate":
        res *= 1.4
    elif policy == "Attrition":
        res *= 1.1

    res = min(res, 100)

    opponent_value = b * unit_price
    win_value = (res / 100) * opponent_value
    fail_percent = 100 - res
    loss_value = (fail_percent / 100) * (a * unit_price)

    return {
        "success_chance": round(res, 2),
        "win_value": round(win_value, 2),
        "loss_value": round(loss_value, 2)
    }

def get_sheet():
    import json
    from oauth2client.service_account import ServiceAccountCredentials
    import gspread
    import os

    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_json_str = os.environ.get("GOOGLE_CREDENTIALS")
    if not creds_json_str:
        raise RuntimeError("Environment variable 'GOOGLE_CREDENTIALS' not found.")
    
    # Debug print (remove in production)
    print("Raw GOOGLE_CREDENTIALS:", creds_json_str[:100], "...")  # Show start of string

    try:
        # If creds_json_str is a JSON string, parse it to dict
        if isinstance(creds_json_str, str):
            creds_json = json.loads(creds_json_str)
        else:
            creds_json = creds_json_str
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Failed to parse GOOGLE_CREDENTIALS as JSON: {e}")

    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_json, scope)
    client = gspread.authorize(creds)
    sheet = client.open("Registrations").sheet1
    return sheet


cached_sheet_data = []  # global cache for sheet data

def load_sheet_data():
    global cached_users
    try:
        sheet = get_sheet()
        records = sheet.get_all_records()
        
        cached_users = {
            record['DiscordID']: {
                'DiscordUsername': record['DiscordUsername'],
                'NationID': record['NationID']
            }
            for record in records
        }
        
        print("Sheet data loaded/refreshed")
        print(cached_users)
    except Exception as e:
        print(f"Failed to load sheet data: {e}")

@bot.event
async def on_ready():
    if not hasattr(bot, "persistent_views_added"):
        bot.add_view(GrantView())
        bot.persistent_views_added = True
    load_sheet_data()  # load data once at startup
    await bot.tree.sync()
    print(f'Logged in as {bot.user}')


@bot.tree.command(name="register", description="Register your Nation ID")
@app_commands.describe(nation_id="Your Nation ID (numbers only, e.g., 365325)")
async def register(interaction: discord.Interaction, nation_id: str):
    await interaction.response.defer()

    if not nation_id.isdigit():
        await interaction.followup.send("❌ Please enter only the Nation ID number, not a link.")
        return

    url = f"https://politicsandwar.com/nation/id={nation_id}"
    session = requests.Session()
    response = session.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')

    discord_label = soup.find(string="Discord Username:")
    if not discord_label:
        await interaction.followup.send("❌ Invalid Nation ID or the nation has no Discord username listed.")
        return

    try:
        nation_discord_username = discord_label.parent.find_next_sibling("td").text.strip()
    except Exception:
        await interaction.followup.send("❌ Could not parse nation information.")
        return

    user_discord_username = str(interaction.user.name).strip()
    user_id = str(interaction.user.id)

    if nation_discord_username != user_discord_username:
        await interaction.followup.send(
            f"❌ Username mismatch.\nNation lists: `{nation_discord_username}`\nYour Discord: `{user_discord_username}`"
        )
        return

    try:
        sheet = get_sheet()
    except Exception as e:
        await interaction.followup.send(f"❌ Failed to access registration sheet: {e}")
        return

    # Use the cached data to check registrations
    global cached_sheet_data
    cached_data = cached_sheet_data

    user_discord_username_lower = user_discord_username.lower()
    nation_id_str = str(nation_id)

    for row in cached_data:
        discord_name = str(row.get("DiscordUsername", "")).strip().lower()
        discord_id = str(row.get("DiscordID", "")).strip()
        registered_nation_id = str(row.get("NationID", "")).strip()

        if user_discord_username_lower == discord_name:
            await interaction.followup.send("❌ This Discord username is already registered.")
            return

        if user_id == discord_id:
            await interaction.followup.send("❌ This Discord ID is already registered.")
            return

        if nation_id_str == registered_nation_id:
            await interaction.followup.send("❌ This Nation ID is already registered.")
            return

    try:
        sheet.append_row([user_discord_username, user_id, nation_id])
    except Exception as e:
        await interaction.followup.send(f"❌ Failed to write registration: {e}")
        return

    # Refresh cache after successful registration
    load_sheet_data()

    await interaction.followup.send("✅ You're registered successfully!")


'''@bot.tree.command(name="register_manual", description="Manually register a nation with a given Discord username (no validation)")
@app_commands.describe(
    nation_id="Nation ID number (e.g., 365325)",
    discord_username="Exact Discord username to register"
)
async def register_manual(interaction: discord.Interaction, nation_id: str, discord_username: str):
    await interaction.response.defer()

    if not str(interaction.user.id) == "1148678095176474678":
        await interaction.followup.send("Not a public command")
        return

    if not nation_id.isdigit():
        await interaction.followup.send("❌ Please enter only the Nation ID number, not a link.")
        return

    try:
        with open("Alliance.json", "r") as f:
            data = json.load(f)
    except FileNotFoundError:
        data = {}

    if discord_username in data:
        await interaction.followup.send("❌ This Discord username is already registered.")
        return

    data[discord_username] = {
        "Name": discord_username,
        "NationID": nation_id
    }

    with open("Alliance.json", "w") as f:
        json.dump(data, f, indent=4)

    await interaction.followup.send("✅ Registered successfully (manually, no validation).")
'''


@bot.tree.command(name="battle_sim", description="simulate a battle")
async def simulation(interaction: discord.Interaction, nation_id: str, war_type: str):
    await interaction.response.defer()
    user_id = str(interaction.user.id)

    global cached_users  # the dict version
    
    user_data = cached_users.get(interaction.user.id)  # user_id as int, no need to cast to string if keys are ints
    
    if not user_data:
        await interaction.followup.send("❌ You are not registered. Use `/register` first.")
        return
    
    own_id = str(user_data.get("NationID", "")).strip()

    if not own_id:
            await interaction.followup.send("❌ Could not find your Nation ID in the sheet.")
            return
    try:
        try:
            opponent = get_military(nation_id)
            me = get_military(own_id)
        except ValueError:
            await interaction.followup.send("❌ Failed to retrieve nation data via API.")
            return

        (
            nation_name, nation_leader, nation_rank, nation_score, war_policy,
            soldiers, tanks, aircraft, ships, spies, missiles, nuclear
        ) = opponent

        (
            me_name, me_leader, me_rank, me_score, me_policy,
            me_soldiers, me_tanks, me_aircraft, me_ships, me_spies, me_missiles, me_nukes
        ) = me

        # Convert and calculate
        def safe_int(x):
            if isinstance(x, str):
                return int(x.replace(",", ""))
            return int(x)
        
        soldiers_int = safe_int(soldiers)
        tanks_int = safe_int(tanks)
        aircraft_int = safe_int(aircraft)
        ships_int = safe_int(ships)
        missiles_int = safe_int(missiles)
        nuclear_int = safe_int(nuclear)

        me_soldiers_int = safe_int(me_soldiers)
        me_tanks_int = safe_int(me_tanks)
        me_aircraft_int = safe_int(me_aircraft)
        me_ships_int = safe_int(me_ships)
        me_missiles_int = safe_int(me_missiles)
        me_nukes_int = safe_int(me_nukes)


        me_ground = me_soldiers_int + me_tanks_int
        enemy_ground = soldiers_int + tanks_int

        per_ground = calculation('tanks', me_ground, enemy_ground, me_policy, war_type)
        per_air = calculation('aircraft', me_aircraft_int, aircraft_int, me_policy, war_type)
        per_naval = calculation('ships', me_ships_int, ships_int, me_policy, war_type)
        per_missiles = calculation('missiles', me_missiles_int, missiles_int, me_policy, war_type)
        per_nuclear = calculation('nuclear', me_nukes_int, nuclear_int, me_policy, war_type)

        percent = round((
            per_ground["success_chance"] +
            per_air["success_chance"] +
            per_naval["success_chance"] +
            per_missiles["success_chance"] +
            per_nuclear["success_chance"]
        ) / 5, 2)

        total_loss = (
            per_ground["loss_value"] +
            per_air["loss_value"] +
            per_naval["loss_value"] +
            per_missiles["loss_value"] +
            per_nuclear["loss_value"]
        )

        total_win = (
            per_ground['win_value'] +
            per_air['win_value'] + 
            per_naval['win_value'] +
            per_missiles['win_value'] +
            per_nuclear['win_value']
        )

        msg = (
            f"> **Score:** {me_score} vs {nation_score}\n"
            f"> **War Policy:** {me_policy} vs {war_policy}\n\n"

            f"**🪖 Ground Battle (Soldiers + Tanks)**\n"
            f"> {me_ground} vs {enemy_ground} | 🎯Success Chance: {per_ground['success_chance']}% | 💥Damage Dealt: ${per_ground['win_value']} | 💸Damage Received: ${per_ground['loss_value']}\n"

            f"**✈️ Airstrike (Aircraft)**\n"
            f"> {me_aircraft_int} vs {aircraft_int} | 🎯Success Chance: {per_air['success_chance']}% | 💥Damage Dealt: ${per_air['win_value']} | 💸Damage Received: ${per_air['loss_value']}\n"

            f"**🚢 Naval Attack (Ships)**\n"
            f"> {me_ships_int} vs {ships_int} | 🎯Success Chance: {per_naval['success_chance']}% | 💥Damage Dealt: ${per_naval['win_value']} | 💸Damage Received: ${per_naval['loss_value']}\n"

            f"**🧨 Missiles**\n"
            f"> {me_missiles_int} vs {missiles_int} | 🎯Success Chance: {per_missiles['success_chance']}% | 💥Damage Dealt: ${per_missiles['win_value']} | 💸Damage Received: ${per_missiles['loss_value']}\n"

            f"**☢️ Nuclear Weapons**\n"
            f"> {me_nukes_int} vs {nuclear_int} | 🎯Success Chance: {per_nuclear['success_chance']}% | 💥Damage Dealt: ${per_nuclear['win_value']} | 💸Damage Received: ${per_nuclear['loss_value']}\n"

            f"\n🏆 ***Average Victory Chance: {percent}%***"
            f"\n💥 ***Total Damage Dealt: ${total_win}***"
            f"\n💸 ***Total Damage Received: ${total_loss}***"

        )

        embed = discord.Embed(
            title= f"🪖 **{me_name} (led by {me_leader}) vs {nation_name} (led by {nation_leader})**",
            color=discord.Color.dark_embed(),
            description=(msg)
        )
        image_url = "https://i.ibb.co/qJygzr7/Leonardo-Phoenix-A-dazzling-star-emits-white-to-bluish-light-s-2.jpg"
        embed.set_footer(text=f"Brought to you by Darkstar", icon_url=image_url)
        await interaction.followup.send(embed=embed)

    except Exception as e:
        await interaction.followup.send(f"❌ Error: {e}")


@bot.tree.command(name="my_nation", description="Your own Nation")
async def own_nation(interaction: discord.Interaction):
    await interaction.response.defer()

    user_id = str(interaction.user.id)
    try:
        global cached_users  # the dict version
        
        user_data = cached_users.get(interaction.user.id)  # user_id as int, no need to cast to string if keys are ints
        
        if not user_data:
            await interaction.followup.send("❌ You are not registered. Use `/register` first.")
            return
        
        own_id = str(user_data.get("NationID", "")).strip()

        if not own_id:
            await interaction.followup.send("❌ Could not find your Nation ID in the sheet.")
            return

        nation_name, nation_leader, nation_score, war_policy, soldiers, tanks, aircraft, ships, spies, missiles, nuclear = get_military(own_id)
        msg = (
            f"🧑‍✈️ **Leader:** {nation_leader}\n"
            f"📈 **Score:** {nation_score}\n"
            f"🛡️ **War Policy:** {war_policy}\n\n"
            f"🪖 **Soldiers:** {soldiers}\n"
            f"🛠️ **Tanks:** {tanks}\n"
            f"✈️ **Aircraft:** {aircraft}\n"
            f"🚢 **Ships:** {ships}\n"
            f"🕵️ **Spies:** {spies}\n"
            f"🧨 **Missiles:** {missiles}\n"
            f"☢️ **Nuclear Weapons:** {nuclear}"
        )
        embed = discord.Embed(
            title= f"🏳️ **Nation Name:** {nation_name}",
            color=discord.Color.dark_embed(),
            description=(msg)
        )
        image_url = "https://i.ibb.co/qJygzr7/Leonardo-Phoenix-A-dazzling-star-emits-white-to-bluish-light-s-2.jpg"
        embed.set_footer(text=f"Brought to you by Darkstar", icon_url=image_url)
        await interaction.followup.send(embed=embed)
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {e}")


reasons_for_grant = [
    app_commands.Choice(name="Warchest", value="warchest"),
    app_commands.Choice(name="Rebuilding Stage 1", value="rebuilding_stage_1"),
    app_commands.Choice(name="Rebuilding Stage 2", value="rebuilding_stage_2"),
    app_commands.Choice(name="Rebuilding Stage 3", value="rebuilding_stage_3"),
    app_commands.Choice(name="Rebuilding Stage 4", value="rebuilding_stage_4"),
    app_commands.Choice(name="Project", value="project"),
    app_commands.Choice(name="Resources for Production", value="Resources for Production"),
]

RESOURCE_ABBR = {
    'g': '-g',  # Gasoline
    'm': '-m',  # Munition
    'a': '-a',  # Aluminium
    's': '-s',  # Steel
    'f': '-f',  # Food
    'u': '-u',  # Uranium
    'l': '-l',  # Lead
    'b': '-b',  # Bauxite
    'o': '-o',  # Oil
    'c': '-c',  # Coal
    'i': '-i',  # Iron
    '$': '-$',  # Money
}

@bot.tree.command(name="resources", description="Resources of the nation")
async def resources(interaction: discord.Interaction):
    await interaction.response.defer()
    user_id = interaction.user.id  # use as int if dict keys are ints

    global cached_users

    user_data = cached_users.get(user_id)

    if not user_data:
        await interaction.followup.send("❌ You are not registered. Use `/register` first.")
        return

    own_id = str(user_data.get("NationID", "")).strip()
    if not own_id:
        await interaction.followup.send("❌ Could not find your Nation ID in the sheet.")
        return

    # === API Call ===
    GRAPHQL_URL = f"https://api.politicsandwar.com/graphql?api_key={API_KEY}"
    query = f"""
    {{
      nations(id: [{own_id}]) {{
        data {{
          id
          nation_name
          num_cities
          food
          money
          gasoline
          munitions
          steel
          aluminum
        }}
      }}
    }}
    """
    try:
        response = requests.post(
            GRAPHQL_URL,
            json={"query": query},
            headers={"Content-Type": "application/json"}
        )
        response_json = response.json()
    except Exception as e:
        await interaction.followup.send(f"❌ API call failed: {e}")
        return

    if "data" not in response_json or "nations" not in response_json["data"] or "data" not in response_json["data"]["nations"]:
        await interaction.followup.send("❌ Failed to fetch nation data. Please check the Nation ID or try again later.")
        return

    nation_data = response_json["data"]["nations"]["data"]
    if not nation_data:
        await interaction.followup.send("❌ Nation not found. Please try again.")
        return

    nation = nation_data[0]

    # === Embed Response ===
    embed = discord.Embed(
        title=f"📦 Resources for {nation['nation_name']}",
        color=discord.Color.blue(),
        description=f"Cities: {nation['num_cities']}"
    )
    embed.add_field(name="💰 Money", value=f"${float(nation['money']):,.0f}", inline=True)
    embed.add_field(name="🍖 Food", value=f"{float(nation['food']):,.0f}", inline=True)
    embed.add_field(name="⛽ Gasoline", value=f"{float(nation['gasoline']):,.0f}", inline=True)
    embed.add_field(name="💣 Munitions", value=f"{float(nation['munitions']):,.0f}", inline=True)
    embed.add_field(name="🪨 Steel", value=f"{float(nation['steel']):,.0f}", inline=True)
    embed.add_field(name="🛠️ Aluminum", value=f"{float(nation['aluminum']):,.0f}", inline=True)

    image_url = "https://i.ibb.co/qJygzr7/Leonardo-Phoenix-A-dazzling-star-emits-white-to-bluish-light-s-2.jpg"
    embed.set_footer(text=f"Brought to you by Darkstar", icon_url=image_url)
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="request_grant", description="Request a grant from the alliance bank")
@app_commands.describe(
    reason="Select the reason for your grant request.",
    uranium="Amount of uranium requested",
    coal="Amount of coal requested",
    oil="Amount of oil requested",
    bauxite="Amount of bauxite requested",
    lead="Amount of lead requested",
    iron="Amount of iron requested",
    steel="Amount of steel requested",
    aluminum="Amount of aluminum requested",
    gasoline="Amount of gasoline requested",
    money="Amount of money requested",
    food="Amount of food requested",
    munitions="Amount of munitions requested"
)
@app_commands.choices(reason=reasons_for_grant)
async def request_grant(
    interaction: discord.Interaction,
    reason: app_commands.Choice[str],
    uranium: int = 0,
    coal: int = 0,
    oil: int = 0,
    bauxite: int = 0,
    lead: int = 0,
    iron: int = 0,
    steel: int = 0,
    aluminum: int = 0,
    gasoline: int = 0,
    money: int = 0,
    food: int = 0,
    munitions: int = 0,
):
    await interaction.response.defer()
    user_id = str(interaction.user.id)

    try:
        global cached_users

        user_data = cached_users.get(interaction.user.id)
        if not user_data:
            await interaction.followup.send("❌ You are not registered. Use `/register` first.")
            return

        own_id = str(user_data.get("NationID", "")).strip()
        if not own_id:
            await interaction.followup.send("❌ Could not find your Nation ID in the sheet.", ephemeral=True)
            return

        nation_data = get_military(own_id)
        nation_name = nation_data[0]

        # Build resource list
        resources = {
            "Uranium": uranium,
            "Coal": coal,
            "Oil": oil,
            "Bauxite": bauxite,
            "Lead": lead,
            "Iron": iron,
            "Steel": steel,
            "Aluminum": aluminum,
            "Gasoline": gasoline,
            "Money": money,
            "Food": food,
            "Munitions": munitions,
        }

        # Filter out 0 amounts so we only show requested resources
        requested_resources = {k: v for k, v in resources.items() if v > 0}
        if not requested_resources:
            await interaction.followup.send("❌ You must request at least one resource.", ephemeral=True)
            return

        # Format lines with commas for thousands
        formatted_lines = [
            f"{resource}: {amount:,}".replace(",", ".")
            for resource, amount in requested_resources.items()
        ]
        description_text = "\n".join(formatted_lines)

        embed = discord.Embed(
            title="💰 Grant Request",
            color=discord.Color.gold(),
            description=(
                f"**Nation:** {nation_name} (`{own_id}`)\n"
                f"**Requested by:** {interaction.user.mention}\n"
                f"**Request:**\n{description_text}\n"
                f"**Reason:** {reason.value.title()}\n"
            )
        )
        image_url = "https://i.ibb.co/qJygzr7/Leonardo-Phoenix-A-dazzling-star-emits-white-to-bluish-light-s-2.jpg"
        embed.set_footer(text="Brought to you by Darkstar", icon_url=image_url)

        await interaction.followup.send(embed=embed, view=GrantView())

    except Exception as e:
        await interaction.followup.send(f"❌ An unexpected error occurred: {e}", ephemeral=True)


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

# --- Bot Command ---
@bot.tree.command(name="warn_maint", description="Notify users of bot maintenance (Dev only)")
async def warn_maint(interaction: discord.Interaction, time: str):
    await interaction.response.defer()
    user_id = str(interaction.user.id)

    if user_id != "1148678095176474678":
        await interaction.followup.send("You don't have the required permission level", ephemeral=True)
        return

    try:
        # YouTube API Config
        CHANNEL_ID = "UC_ID-A3YnSQXCwyIcCs9QFw"

        # Fetch latest 50 videos
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

        # Get video durations
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

        # Pick a random Short
        chosen_vid = random.choice(shorts) if shorts else "https://www.youtube.com"

        # Send maintenance message
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


percent_list = [
    app_commands.Choice(name="50%", value="50%"),
    app_commands.Choice(name="100%", value="100%")
]
reasons_for_grant = [
    app_commands.Choice(name="Warchest", value="warchest"),
    app_commands.Choice(name="Rebuilding Stage 1", value="rebuilding_stage_1"),
    app_commands.Choice(name="Rebuilding Stage 2", value="rebuilding_stage_2"),
    app_commands.Choice(name="Rebuilding Stage 3", value="rebuilding_stage_3"),
    app_commands.Choice(name="Rebuilding Stage 4", value="rebuilding_stage_4"),
    app_commands.Choice(name="Project", value="project"),
]

@bot.tree.command(name="request_warchest", description="Request a Warchest grant")
@app_commands.describe(percent="How much percent of the warchest do you want")
@app_commands.choices(percent=percent_list)
async def warchest(interaction: discord.Interaction, percent: app_commands.Choice[str]):
    await interaction.response.defer()
    global commandscalled
    commandscalled["_global"] += 1
    user_id = str(interaction.user.id)
    
    global cached_users  # the dict version
    
    user_data = cached_users.get(interaction.user.id)  # user_id as int, no need to cast to string if keys are ints
    
    if not user_data:
        await interaction.followup.send("❌ You are not registered. Use `/register` first.")
        return
    
    own_id = str(user_data.get("NationID", "")).strip()

    if not own_id:
            await interaction.followup.send("❌ Could not find your Nation ID in the sheet.")
            return


    try:
        # === API Call ===
        GRAPHQL_URL = f"https://api.politicsandwar.com/graphql?api_key={API_KEY}"
        query = f"""
        {{
          nations(id: [{own_id}]) {{
            data {{
              id
              nation_name
              num_cities
              food
              money
              gasoline
              munitions
              steel
              aluminum
            }}
          }}
        }}
        """
        response = requests.post(
            GRAPHQL_URL,
            json={"query": query},
            headers={"Content-Type": "application/json"}
        )
        response_json = response.json()

        if "data" not in response_json or "nations" not in response_json["data"] or "data" not in response_json["data"]["nations"]:
            await interaction.followup.send("❌ Failed to fetch nation data. Please check the Nation ID or try again later.")
            return

        nation_data = response_json["data"]["nations"]["data"]

        if not nation_data:
            await interaction.followup.send("❌ Nation not found. Please try again.")
            return

        # Normalize the data
        nation = nation_data[0]
        nation_name = nation["nation_name"]
        cities = nation["num_cities"]
        food = nation["food"]
        money = nation["money"]
        gasoline = nation["gasoline"]
        munition = nation["munitions"]
        steel = nation["steel"]
        aluminium = nation["aluminum"]

        if any(x is None for x in [cities, food, money, gasoline, munition, steel, aluminium]):
            await interaction.followup.send("❌ Missing resource data. Please try again.")
            return

        city = int(cities)

        # Adjust per-city requirements if 50% is selected
        percent_value = percent.value.strip().lower()
        if percent_value in ["50", "50%"]:
            nr_a = 325
            nr_a_f = 1500
            nr_a_m = 500000
        else:
            nr_a = 750
            nr_a_f = 3000
            nr_a_m = 1000000

        # Calculate total required
        nr_a_minus = city * nr_a
        nr_a_f_minus = city * nr_a_f
        money_needed = city * nr_a_m

        # Calculate deficits
        money_n = 0
        gas_n = 0
        mun_n = 0
        ste_n = 0
        all_n = 0
        foo_n = 0

        for res, resource_value in {
            'money': money, 'gasoline': gasoline, 'munitions': munition,
            'steel': steel, 'aluminum': aluminium, 'food': food
        }.items():
            if res == 'money':
                new_value = resource_value - money_needed
                money_n = 0 if new_value >= 0 else -new_value
            elif res == 'gasoline':
                new_value = resource_value - nr_a_minus
                gas_n = 0 if new_value >= 0 else -new_value
            elif res == 'munitions':
                new_value = resource_value - nr_a_minus
                mun_n = 0 if new_value >= 0 else -new_value
            elif res == 'steel':
                new_value = resource_value - nr_a_minus
                ste_n = 0 if new_value >= 0 else -new_value
            elif res == 'aluminum':
                new_value = resource_value - nr_a_minus
                all_n = 0 if new_value >= 0 else -new_value
            elif res == 'food':
                new_value = resource_value - nr_a_f_minus
                foo_n = 0 if new_value >= 0 else -new_value

        request_lines = []
        if money_n > 0:
            request_lines.append(f"Money: {round(money_n):,.0f}\n")
        if foo_n > 0:
            request_lines.append(f"Food: {round(foo_n):,.0f}\n")
        if gas_n > 0:
            request_lines.append(f"Gasoline: {round(gas_n):,.0f}\n")
        if mun_n > 0:
            request_lines.append(f"Munitions: {round(mun_n):,.0f}\n")
        if ste_n > 0:
            request_lines.append(f"Steel: {round(ste_n):,.0f}\n")
        if all_n > 0:
            request_lines.append(f"Aluminum: {round(all_n):,.0f}")
        
        request_lines = ' '.join(request_lines)
        description_text = request_lines
        embed = discord.Embed(
            title="💰 Grant Request",
            color=discord.Color.gold(),
            description=(
                f"**Nation:** {nation_name} (`{own_id}`)\n"
                f"**Requested by:** {interaction.user.mention}\n"
                f"**Request:**\n{description_text}\n"
                f"**Reason:** Warchest\n"
            )
        )
        image_url = "https://i.ibb.co/qJygzr7/Leonardo-Phoenix-A-dazzling-star-emits-white-to-bluish-light-s-2.jpg"
        embed.set_footer(text=f"Brought to you by Darkstar", icon_url=image_url)
        await interaction.followup.send(embed=embed, view=GrantView())
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {e}")


user_nation_ids = {
    "lordygon": 459160,
    "patrickrickrickpatrick": 636722,
    "masteraced": 365325,
    "vladmier1": 510930,
    "goswat14542308": 683429,
    "darko50110": 671583,
    "arstotzka111": 605608,
    "hypercombatman": 236312,
    ".technostan": 665217,
    "wholelottawar": 635047,
    "aeternite": 619412,
    "speckgard": 631277,
    "fishpool0211": 510895,
    "micmou123": 277286,
    "tymon_pik": 615360,
    "cookie_xdsorry": 648675,
    "jhon_tachanka_doe": 538189,
    "pindakaas07": 613818,
    "ellianmarkwell": 646388,
    "sabtien123": 447228,
    "kaelkek": 614369,
    "lemyrzin": 650657,
    "brutallich": 259382,
    "varant1x": 646579,
    "chevdev98": 680527,
    "rogue__5": 673641,
    "peoplerep_the_great": 554863,
    "iam_jinxed": 671871,
    "bendover995": 667252,
    "scottyboi3413": 679028,
    "1khri": 679562,
    "acoldlinks": 615210,
    "bruhbaboon": 683575,
    "miranacious_17083": 680196,
    ".nygi": 677500,
    "skryni": 688146,
    "sayyedistan.": 685174,
    "jonas9629": 433465,
    "dietc0ke": 622443,
    "chrissyno": 551321,
    "bigmoney89": 649719,
    "man.is.80090": 625208,
    "actuallyprille": 608492,
    "fumzy0207": 652466,
    "georgewashington1111": 645621,
    "ticklemctickleson": 607513,
    "r0b3rt11": 646757,
    "supersmart_09262": 684684,
    "papang0001": 690323,
    "gtag4ever": 647486,
    "jiradin": 656339,
    "pzoez2": 547638,
}

@bot.tree.command(name="help", description="Get the available commands")
async def help(interaction: discord.Interaction):
    await interaction.response.defer()
    register_description = (
        "Register yourself using this command to use the *many amazing* freatures of this bot, developed by **`@masteraced`**\n"
        "The command is `/register nation_id: 680627`\n"
        "**Note:** The bot only works if you're registered\n"
    )
    warchest_desc = (
        "Calculates the needed amount of materials for a warchest and requests those\n"
        "Once your request was approved, it will inform you by pinging you\n"
        "The command is `/request_warchest percent: 50% or 100%`\n"
    )
    warchest_audit_desc = (
        "Calculates the needed amount of materials for a warchest and generates a message to send to the audited user (no ping)\n"
        "The command is `/warchest_audit who: 680627`\n"
    )
    battle_sim_desc = (
        "Generates an approximate battle based on the military of both nations and shows approximate win-chance\n"
        "The command is `/battle_sim nation_id: 680627 war_type: Raid`\n"
    )
    my_nation_desc = (
        "Gives you your own nation's military, score and war policy\n"
        "The command is `/my_nation`\n"
    )
    resources_desc = (
        "Gives you your own nation's resources\n"
        "The command is `/resources`\n"
    )
    request_grant_desc = (
        "Requests the requested materials. This command is to make the EA departments job easier\n"
        "The command is `/request_grant request: money 9mil, steel 7k, munition 70, ... reason: Warchest`\n"
    )
    request_city_desc = (
        "Calculates the approximate cost to buy the requested cities and, if wanted, requests them\n"
        "The command is `/request_city current_city: 10 target_city: 15`\n"
        "**Note**: on bigger request the cost inflates a bit\n"
    )
    request_infra_grant_desc = (
        "Calculates the approximate cost of the wanted infra and, if wanted, requests them\n"
        "The command is `/request_infra_grant current_infra: 10 wanted_infra: 1500 city_amount:10`\n"
        "**Note**: on bigger request the cost inflates a bit\n"
    )
    request_project_desc = (
        "Calculates the needed materials and money to get the wanted project and, if wanted, requests it\n"
        "The command is `/request_project project: Moon Landing`\n"
    )
    bug_rep_desc = (
        "Report a bug"
        "The command is `/bug_report bug: insert bug report here`\n"
    )
    gov_msg = (
        "\n***`/register`:***\n"
        f"{register_description}"
        "\n***`/request_warchest`:***\n"
        f"{warchest_desc}"
        "\n***`/warchest_audit`\n:***"
        f"{warchest_audit_desc}"
        "\n***`/battle_sim`:***\n"
        f"{battle_sim_desc}"
        "\n***`/my_nation`:***\n"
        f"{my_nation_desc}"
        "\n***`/resources`:***\n"
        f"{resources_desc}"
        "\n***`/request_grant`:***\n"
        f"{request_grant_desc}"
        "\n***`/request_city`:***\n"
        f"{request_city_desc}"
        "\n***`/request_infra_grant`:***\n"
        f"{request_infra_grant_desc}"
        "\n***`/request_project`:***\n"
        f"{request_project_desc}"
        "\n***`/bug_report`:***\n"
        f"{bug_rep_desc}"
    )
    gov_mssg = discord.Embed(
        title="List of the commands (including the government once):",
        color=discord.Color.purple(),
        description=gov_msg
    )
    image_url = "https://i.ibb.co/qJygzr7/Leonardo-Phoenix-A-dazzling-star-emits-white-to-bluish-light-s-2.jpg"
    gov_mssg.set_footer(text=f"Brought to you by Darkstar", icon_url=image_url)

    norm_msg = (
        "\n***`/register`:***\n"
        f"{register_description}"
        "\n***`/request_warchest`:***\n"
        f"{warchest_desc}"
        "\n***`/battle_sim`:***\n"
        f"{battle_sim_desc}"
        "\n***`/my_nation`:***\n"
        f"{my_nation_desc}"
        "\n***`/resources`:***\n"
        f"{resources_desc}"
        "\n***`/request_grant`:***\n"
        f"{request_grant_desc}"
        "\n***`/request_city`:***\n"
        f"{request_city_desc}"
        "\n***`/request_infra_grant`:***\n"
        f"{request_infra_grant_desc}"
        "\n***`/request_project`:***\n"
        f"{request_project_desc}"
        "\n***`/bug_report`:***\n"
        f"{bug_rep_desc}"
    )

    norm_mssg = discord.Embed(
        title="List of the commands:",
        color=discord.Color.blue(),
        description=norm_msg
    )
    image_url = "https://i.ibb.co/qJygzr7/Leonardo-Phoenix-A-dazzling-star-emits-white-to-bluish-light-s-2.jpg"
    norm_mssg.set_footer(text=f"Brought to you by Darkstar", icon_url=image_url)
    async def is_high_power(interaction):
        return (
            any(role.name == "Government member" for role in interaction.user.roles)
            or str(interaction.user.id) == "1148678095176474678"
        )
    
    if not await is_high_power(interaction):
        await interaction.followup.send(embed=norm_mssg)
    else:
        await interaction.followup.send(embed=gov_mssg)

@bot.tree.command(name="warchest_audit", description="Request a Warchest grant audit")
@app_commands.describe(who="Tag the person you want to audit")
async def warchest_audit(interaction: discord.Interaction, who: discord.Member):
    await interaction.response.defer()

    target_username = who.name.lower()

    # Find cached discord ID by matching DiscordUsername from cached_users
    target_discord_id = None
    for discord_id, info in cached_users.items():
        if info['DiscordUsername'].lower() == target_username:
            target_discord_id = discord_id
            break

    if target_discord_id is None:
        await interaction.followup.send(
            f"❌ Could not find Nation ID for {who.mention}. "
            "They must be registered in the Google Sheet with their Discord username."
        )
        return

    async def is_banker(interaction):
        return (
            any(role.name == "Government member" for role in interaction.user.roles)
            or str(interaction.user.id) == "1148678095176474678"
        )
    if not await is_banker(interaction):
        await interaction.followup.send("❌ You don't have the rights to perform this action.")
        return

    target_nation_id = int(cached_users[target_discord_id]["NationID"])

    def get_completion_color(percent_complete: float) -> str:
        if percent_complete >= 76:
            return "🟢"
        elif percent_complete >= 51:
            return "🟡"
        elif percent_complete >= 26:
            return "🟠"
        elif percent_complete >= 10:
            return "🔴"
        else:
            return "⚫"

    def format_missing(resource_name, missing_amount, current_amount):
        total = missing_amount + current_amount
        if total == 0:
            percent_complete = 100
        else:
            percent_complete = (current_amount / total) * 100

        color_emoji = get_completion_color(percent_complete)
        return f"{round(missing_amount):,} {resource_name} missing {color_emoji} ({percent_complete:.0f}% complete)"

    try:
        GRAPHQL_URL = f"https://api.politicsandwar.com/graphql?api_key={API_KEY}"
        query = f"""
        {{
          nations(id: [{target_nation_id}]) {{
            data {{
              id
              nation_name
              num_cities
              food
              money
              gasoline
              munitions
              steel
              aluminum
            }}
          }}
        }}
        """
        response = requests.post(
            GRAPHQL_URL,
            json={"query": query},
            headers={"Content-Type": "application/json"}
        )
        response_json = response.json()

        nation_data = response_json.get("data", {}).get("nations", {}).get("data", [])
        if not nation_data:
            await interaction.followup.send("❌ Nation not found. Please try again.")
            return

        nation = nation_data[0]
        nation_name = nation["nation_name"]
        cities = nation["num_cities"]
        food = nation["food"]
        money = nation["money"]
        gasoline = nation["gasoline"]
        munition = nation["munitions"]
        steel = nation["steel"]
        aluminium = nation["aluminum"]

        city = int(cities)
        nr_a = 750
        nr_a_f = 3000
        nr_a_m = 1000000

        nr_a_minus = city * nr_a
        nr_a_f_minus = city * nr_a_f
        money_needed = city * nr_a_m

        money_n = max(0, money_needed - money)
        gas_n = max(0, nr_a_minus - gasoline)
        mun_n = max(0, nr_a_minus - munition)
        ste_n = max(0, nr_a_minus - steel)
        all_n = max(0, nr_a_minus - aluminium)
        foo_n = max(0, nr_a_f_minus - food)

        request_lines = [
            format_missing("Money", money_n, money),
            format_missing("Food", foo_n, food),
            format_missing("Gasoline", gas_n, gasoline),
            format_missing("Munitions", mun_n, munition),
            format_missing("Steel", ste_n, steel),
            format_missing("Aluminum", all_n, aluminium),
        ]

        if all(missing == 0 for missing in [money_n, foo_n, gas_n, mun_n, ste_n, all_n]):
            description_text = "0 material missing"
        else:
            description_text = "\n".join(request_lines)

        embed = discord.Embed(
            title="Warchest Audit",
            color=discord.Color.gold(),
            description=(
                f"**Nation:** {nation_name} (`{target_nation_id}`)\n"
                f"**Leader:** {who.mention}\n"
                f"**Missing Materials:**\n{description_text}\n"
            )
        )
        image_url = "https://i.ibb.co/qJygzr7/Leonardo-Phoenix-A-dazzling-star-emits-white-to-bluish-light-s-2.jpg"
        embed.set_footer(text="Brought to you by Darkstar", icon_url=image_url)

        await interaction.followup.send(embed=embed, view=MessageView(description_text))
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {e}")


@bot.tree.command(name="request_city", description="Calculate cost for upgrading from current city to target city")
@app_commands.describe(current_cities="Your current number of cities", target_cities="Target number of cities")
async def request_city(interaction: discord.Interaction, current_cities: int, target_cities: int):
    await interaction.response.defer()
    user_id = str(interaction.user.id)
    commandscalled[user_id] = commandscalled.get(user_id, 0) + 1
    try:
        global cached_users  # the dict version
        
        user_data = cached_users.get(interaction.user.id)  # user_id as int, no need to cast to string if keys are ints
        
        if not user_data:
            await interaction.followup.send("❌ You are not registered. Use `/register` first.")
            return
        
        own_id = str(user_data.get("NationID", "")).strip()
    except Exception as e:
        print(f"Error checking registration: {e}")
        await interaction.followup.send("🚫 Error checking registration. Please try again later.")
        return
    if target_cities <= current_cities:
        await interaction.followup.send("❌ Target cities must be greater than current cities.")
        return
    elif current_cities <= 0:
        await interaction.followup.send("❌ Current cities must be greater than 0.")
        return        

    datta = get_resources(own_id)
    nation_name = datta[0]
    total_cost = 0
    cost_details = []
    top20Average = 41.47  # This is static, you can change this

    def compute_city_cost(cityToBuy: int, top20Average: float) -> float:
        # Static costs for cities 2–10
        static_costs = {
            2: 400_000,
            3: 900_000,
            4: 1_600_000,
            5: 2_500_000,
            6: 3_600_000,
            7: 4_900_000,
            8: 6_400_000,
            9: 8_100_000,
            10: 10_000_000,
        }

        if cityToBuy < 11:
            return static_costs.get(cityToBuy, 0)

        delta = cityToBuy - (top20Average / 4)
        clause_1 = (100_000 * (delta ** 3)) + (150_000 * delta) + 75_000
        clause_2 = max(clause_1, (cityToBuy ** 2) * 100_000)

        return clause_2

    def round_up_to_nearest(value: float, round_to: float) -> float:
        """
        Round the value up to the nearest specified round_to value.
        """
        return math.ceil(value / round_to) * round_to

    def get_rounding_multiple(city_number: int) -> int:
        """
        Returns the appropriate rounding multiple based on the city number.
        For city numbers 30, 40, 50, etc.
        """
        if city_number < 30:
            return 1_000_000  # Round to nearest 1 million for cities 17 to 29
        elif city_number < 60:
            return 5_000_000  # Round to nearest 5 million for cities 30 to 59
        elif city_number < 100:
            return 11_000_000  # Round to nearest 11 million for cities 60 to 99
        else:
            return 20_000_000  # Round to nearest 20 million for cities 100+

    for i in range(current_cities + 1, target_cities + 1):
        cost = compute_city_cost(i, top20Average)

        # Apply the rounding logic based on the new rounding criteria
        rounding_multiple = get_rounding_multiple(i)
        
        # Apply rounding to the nearest multiple depending on the city number
        if i >= 30:
            cost = round_up_to_nearest(cost, rounding_multiple)

        total_cost += cost
        cost_details.append(f"City {i}: ${cost:,.2f}")

    embed = discord.Embed(
        title="🏙️ City Upgrade Cost",
        color=discord.Color.green(),
        description="\n".join(cost_details)
    )
    embed.add_field(name="Total Cost:", value=f"${total_cost:,.0f}", inline=False)
    image_url = "https://i.ibb.co/qJygzr7/Leonardo-Phoenix-A-dazzling-star-emits-white-to-bluish-light-s-2.jpg"
    embed.set_footer(text="Brought to you by Darkstar", icon_url=image_url)

    await interaction.followup.send(
        embed=embed,
        view=BlueGuy(category="city", data={
            "nation_name": nation_name,
            "nation_id": own_id,
            "from": current_cities,
            "city_num": target_cities,
            "total_cost": total_cost
        })
)

def get_city_data(nation_id: str) -> list[dict]:
    GRAPHQL_URL = f"https://api.politicsandwar.com/graphql?api_key={API_KEY}"

    query = f"""
    {{
      cities(nation_id: {nation_id}) {{
        data {{
          name
          infrastructure
        }}
      }}
    }}
    """

    response = requests.post(
        GRAPHQL_URL,
        json={"query": query},
        headers={"Content-Type": "application/json"}
    )
    try:
        response_json = response.json()
        city_data = response_json.get("data", {}).get("cities", {}).get("data", [])
    except Exception:
        city_data = []

    if not city_data:
        return []

    return [{"name": city.get("name", "Unknown"), "infra": city.get("infrastructure", 0)} for city in city_data]

def calculate_infra_cost_for_range(start_infra: int, end_infra: int) -> float:
    """
    Calculate cost for upgrading infrastructure from start_infra to end_infra for a single city,
    handling partial tiers correctly.
    """
    tiers = [
        (0, 100, 30_000),
        (100, 200, 30_000),
        (200, 300, 40_000),
        (300, 400, 70_000),
        (400, 500, 100_000),
        (500, 600, 150_000),
        (600, 700, 200_000),
        (700, 800, 280_000),
        (800, 900, 370_000),
        (900, 1000, 470_000),
        (1000, 1100, 580_000),
        (1100, 1200, 710_000),
        (1200, 1300, 850_000),
        (1300, 1400, 1_000_000),
        (1400, 1500, 1_200_000),
        (1500, 1600, 1_400_000),
        (1600, 1700, 1_600_000),
        (1700, 1800, 1_800_000),
        (1800, 1900, 2_000_000),
        (1900, 2000, 2_300_000)
    ]
    
    total_cost = 0.0
    for low, high, cost_per_100 in tiers:
        if start_infra >= high or end_infra <= low:
            continue

        segment_start = max(start_infra, low)
        segment_end = min(end_infra, high)

        portion = (segment_end - segment_start) / 100
        total_cost += portion * cost_per_100

    return total_cost

def calculate_total_infra_cost(start_infra: int, end_infra: int, num_cities: int) -> float:
    """
    Calculate the total cost to upgrade multiple cities from start_infra to end_infra.
    Applies `calculate_infra_cost_for_range` for each city and multiplies by the number of cities.
    """
    cost_per_city = calculate_infra_cost_for_range(start_infra, end_infra)
    return cost_per_city * num_cities

@bot.tree.command(name="request_infra_cost", description="Calculate infrastructure upgrade cost (single city, all cities, or custom)")
@app_commands.describe(
    target_infra="Target infrastructure level (max 2000)",
    current_infra="Your current infrastructure level (manual mode only)",
    city_amount="Number of cities to upgrade (manual mode only)",
    auto_calculate="Automatically fetch and calculate cost for all cities",
    city_name="Calculate for a specific city by name"
)
async def infra_upgrade_cost(
    interaction: discord.Interaction,
    target_infra: int,
    current_infra: int = None,
    city_amount: int = None,
    auto_calculate: bool = True,
    city_name: str = None
):
    await interaction.response.defer()
    user_id = str(interaction.user.id)

    if target_infra > 2000:
        await interaction.followup.send("❌ Target infrastructure above 2000 is not supported.(*** Personal Contribution by `@patrickrickrickpatrick` ***)")
        return

    # 🔹 Validate registration
    try:
        global cached_users  # the dict version
        
        user_data = cached_users.get(interaction.user.id)  # user_id as int, no need to cast to string if keys are ints
        
        if not user_data:
            await interaction.followup.send("❌ You are not registered. Use `/register` first.")
            return
        
        own_id = str(user_data.get("NationID", "")).strip()
        if not own_id:
            await interaction.followup.send("❌ Could not find your Nation ID in the sheet.")
            return
    except Exception as e:
        await interaction.followup.send(f"❌ Failed to access your data: {e}")
        return

    # 🔹 Retrieve city data
    city_data = get_city_data(own_id)
    if not city_data:
        await interaction.followup.send("❌ Could not retrieve city data for your nation.")
        return

    # 🔹 Specific city calculation
    if city_name:
        city = next((c for c in city_data if c["name"].lower() == city_name.lower()), None)
        if not city:
            await interaction.followup.send(f"❌ Could not find city named '{city_name}' in your nation.")
            return

        current = city["infra"]
        if current >= target_infra:
            await interaction.followup.send(f"❌ '{city_name}' already has infrastructure >= target.")
            return

        cost = calculate_infra_cost_for_range(current, target_infra)
        if cost > 900_000:
            cost = math.ceil(cost / 10_000) * 10_000
        data = {
            "nation_name": nation_name,
            "nation_id": nation_id,
            "from": current_infra,
            "infra": target_infra,
            "ct_count": city_amount,
            "total_cost": cost
        }

        embed = discord.Embed(
            title=f"Upgrade Cost for {city_name}",
            color=discord.Color.gold(),
            description=f"Upgrade from {current} to {target_infra}\nEstimated Cost: **${cost:,.0f}**"
        )
        embed.set_footer(text="Brought to you by Darkstar\nPersonal Contribution by @patrickrickrickpatrick", icon_url="https://i.ibb.co/qJygzr7/Leonardo-Phoenix-A-dazzling-star-emits-white-to-bluish-light-s-2.jpg")
        await interaction.followup.send(
            embed=embed,
            view=BlueGuy(category="infra", data=data)
        )
        return

    # 🔹 Auto calculate for all cities
    if auto_calculate:
        total_cost = 0
        description_lines = []

        for city in city_data:
            name = city["name"]
            current = city["infra"]
            if current >= target_infra:
                continue
            cost = calculate_infra_cost_for_range(current, target_infra)
            total_cost += cost
            description_lines.append(f"**{name}:** ${cost:,.0f}")

        if not description_lines:
            await interaction.followup.send("✅ All cities are already at or above the target infrastructure.")
            return
            
        rounded_total_cost = int(math.ceil(total_cost / 1_000_000.0)) * 1_000_000
        data = {
            "nation_name": nation_name,
            "nation_id": nation_id,
            "from": current_infra,
            "infra": target_infra,
            "ct_count": city_amount,
            "total_cost": rounded_total_cost
        }
        
        embed = discord.Embed(
            title=f"🛠️ Infrastructure Upgrade Cost for {len(description_lines)} City(ies)",
            color=discord.Color.green(),
            description="\n".join(description_lines) + f"\n\n**Total estimated cost(rounded up to the nearest million): ${rounded_total_cost:,.0f}**"
        )
        embed.set_footer(text="Brought to you by Darkstar\nPersonal Contribution by @patrickrickrickpatrick", icon_url="https://i.ibb.co/qJygzr7/Leonardo-Phoenix-A-dazzling-star-emits-white-to-bluish-light-s-2.jpg")
        await interaction.followup.send(
            embed=embed,
            view=BlueGuy(category="infra", data=data)
        )
        return

    # 🔹 Manual input fallback
    if current_infra is None:
        current_infra = 0
    if city_amount is None:
        city_amount = 1
    if target_infra <= current_infra:
        await interaction.followup.send("❌ Target infrastructure must be greater than current infrastructure.")
        return

    total_cost = calculate_total_infra_cost(current_infra, target_infra, city_amount)
    if total_cost > 900_000:
        total_cost = math.ceil(total_cost / 100_000) * 100_000

    embed = discord.Embed(
        title="🛠️ Infrastructure Upgrade Cost",
        color=discord.Color.green(),
        description=f"From `{current_infra}` to `{target_infra}` for `{city_amount}` city(ies)\nEstimated Cost: **${total_cost:,.0f}**"
    )
    embed.set_footer(text="Brought to you by Darkstar", icon_url="https://i.ibb.co/qJygzr7/Leonardo-Phoenix-A-dazzling-star-emits-white-to-bluish-light-s-2.jpg")
    await interaction.followup.send(embed=embed, view=BlueGuy(money=total_cost))


list_of_em = [
    app_commands.Choice(name="Infrastructure Projects", value="infrastructure_projects"),
    app_commands.Choice(name="Space Projects", value="space_projects"),
    app_commands.Choice(name="Defense Projects", value="defense_projects"),
    app_commands.Choice(name="Military Projects", value="military_projects"),
    app_commands.Choice(name="Espionage Projects", value="espionage_projects"),
    app_commands.Choice(name="Research Projects", value="research_projects"),
    app_commands.Choice(name="Economic Projects", value="economic_projects"),
    app_commands.Choice(name="Industry Boosters", value="industry_boosters"),
    app_commands.Choice(name="Domestic Affairs", value="domestic_affairs"),
    app_commands.Choice(name="Commerce Enhancements", value="commerce_enhancements"),
    app_commands.Choice(name="Login Bonus", value="login_bonus")
]

all_names = [
    "Center for Civil Engineering",
    "Advanced Engineering Corps",
    "Arable Land Agency",
    "Space Program",
    "Moon Landing",
    "Mars Landing",
    "Telecommunications Satellite",
    "Guiding Satellite",
    "Nuclear Research Facility",
    "Nuclear Launch Facility",
    "Missile Launch Pad",
    "Vital Defense System",
    "Iron Dome",
    "Fallout Shelter",
    "Arms Stockpile",
    "Military Salvage",
    "Propaganda Bureau",
    "Intelligence Agency",
    "Spy Satellite",
    "Surveillance Network",
    "Clinical Research Center",
    "Recycling Initiative",
    "Research and Development Center",
    "Green Technologies",
    "Pirate Economy",
    "Advanced Pirate Economy",
    "International Trade Center",
    "Ironworks",
    "Bauxiteworks",
    "Emergency Gasoline Reserve",
    "Mass Irrigation",
    "Uranium Enrichment Program",
    "Government Support Agency",
    "Bureau of Domestic Affairs",
    "Specialized Police Training Program",
    "Activity Center"
]

aller_names = [app_commands.Choice(name=name, value=name) for name in all_names]

project_costs = {
    "Infrastructure Projects": {
        "Center for Civil Engineering": {"Money": 3000000, "Oil": 1000, "Iron": 1000, "Bauxite": 1000},
        "Advanced Engineering Corps": {"Money": 50000000, "Munitions": 10000, "Gasoline": 10000, "Uranium": 1000},
        "Arable Land Agency": {"Money": 3000000, "Coal": 1500, "Lead": 1500},
    },
    "Space Projects": {
        "Space Program": {"Money": 50000000, "Aluminum": 25000},
        "Moon Landing": {"Money": 50000000, "Oil": 5000, "Aluminum": 5000, "Munitions": 5000, "Steel": 5000, "Gasoline": 5000, "Uranium": 10000},
        "Mars Landing": {"Money": 200000000, "Oil": 20000, "Aluminum": 20000, "Munitions": 20000, "Steel": 20000, "Gasoline": 20000, "Uranium": 20000},
        "Telecommunications Satellite": {"Money": 300000000, "Oil": 10000, "Aluminum": 10000, "Iron": 10000, "Uranium": 10000},
        "Guiding Satellite": {"Money": 200000000, "Munitions": 40000, "Uranium": 40000, "Gasoline": 40000, "Aluminum": 40000, "Steel": 20000},
    },
    "Defense Projects": {
        "Nuclear Research Facility": {"Money": 75000000, "Uranium": 5000, "Gasoline": 5000, "Aluminum": 5000},
        "Nuclear Launch Facility": {"Money": 750000000, "Uranium": 50000, "Gasoline": 50000, "Aluminum": 50000},
        "Missile Launch Pad": {"Money": 15000000, "Munitions": 5000, "Gasoline": 5000, "Aluminum": 5000},
        "Vital Defense System": {"Money": 40000000, "Steel": 5000, "Aluminum": 5000, "Munitions": 5000, "Gasoline": 5000},
        "Iron Dome": {"Money": 15000000, "Munitions": 5000},
        "Fallout Shelter": {"Money": 25000000, "Food": 100000, "Lead": 10000, "Aluminum": 15000, "Steel": 10000},
    },
    "Military Projects": {
        "Arms Stockpile": {"Money": 10000000, "Coal": 500, "Iron": 500, "Oil": 500, "Bauxite": 500, "Lead": 500},
        "Military Salvage": {"Money": 20000000, "Aluminum": 5000, "Steel": 5000, "Gasoline": 5000},
        "Propaganda Bureau": {"Money": 10000000, "Gasoline": 2000, "Munitions": 2000, "Aluminum": 2000, "Steel": 2000},
    },
    "Espionage Projects": {
        "Intelligence Agency": {"Money": 5000000, "Steel": 500, "Gasoline": 500},
        "Spy Satellite": {"Money": 20000000, "Oil": 10000, "Bauxite": 10000, "Iron": 10000, "Lead": 10000, "Coal": 10000},
        "Surveillance Network": {"Money": 50000000, "Aluminum": 50000, "Bauxite": 15000, "Iron": 15000, "Lead": 15000, "Coal": 15000},
    },
    "Research Projects": {
        "Clinical Research Center": {"Money": 10000000, "Food": 100000},
        "Recycling Initiative": {"Money": 10000000, "Food": 100000},
        "Research and Development Center": {"Money": 50000000, "Aluminum": 5000, "Food": 100000, "Uranium": 1000},
        "Green Technologies": {"Money": 50000000, "Food": 100000, "Aluminum": 10000, "Iron": 10000, "Oil": 10000},
    },
    "Economic Projects": {
        "Pirate Economy": {"Money": 25000000, "Coal": 7500, "Iron": 7500, "Oil": 7500, "Bauxite": 7500, "Lead": 7500},
        "Advanced Pirate Economy": {"Money": 50000000, "Coal": 10000, "Iron": 10000, "Oil": 10000, "Bauxite": 10000, "Lead": 10000},
        "International Trade Center": {"Money": 50000000, "Aluminum": 10000},
    },
    "Industry Boosters": {
        "Ironworks": {"Money": 10000000, "Coal": 500, "Iron": 500, "Oil": 500, "Bauxite": 500, "Lead": 500},
        "Bauxiteworks": {"Money": 10000000, "Coal": 500, "Iron": 500, "Oil": 500, "Bauxite": 500, "Lead": 500},
        "Emergency Gasoline Reserve": {"Money": 10000000, "Coal": 500, "Iron": 500, "Oil": 500, "Bauxite": 500, "Lead": 500},
        "Mass Irrigation": {"Money": 10000000, "Food": 50000, "Coal": 500, "Iron": 500, "Oil": 500, "Bauxite": 500, "Lead": 500},
        "Uranium Enrichment Program": {"Money": 25000000, "Uranium": 2500, "Coal": 500, "Iron": 500, "Oil": 500, "Bauxite": 500, "Lead": 500},
    },
    "Domestic Affairs": {
        "Government Support Agency": {"Money": 20000000, "Aluminum": 10000, "Food": 200000},
        "Bureau of Domestic Affairs": {"Money": 20000000, "Food": 500000, "Coal": 8000, "Bauxite": 8000, "Lead": 8000, "Iron": 8000, "Oil": 8000},
        "Specialized Police Training Program": {"Money": 50000000, "Food": 250000, "Aluminum": 5000},
    },
    "Commerce Enhancements": {
        "Telecommunications Satellite": {"Money": 300000000, "Oil": 10000, "Aluminum": 10000, "Iron": 10000, "Uranium": 10000},
        "International Trade Center": {"Money": 50000000, "Aluminum": 10000},
    },
    "Login Bonus": {
        "Activity Center": {"Money": 500000, "Food": 1000},
    }
}

def get_materials(project_name):
    for category, projects in project_costs.items():
        if project_name in projects:
            return projects[project_name]
    return None  # Project not found

@bot.tree.command(name="request_project", description="Fetch resources for a project")
#@app_commands.choices(project_name=aller_names)
@app_commands.describe(project_name="Name of the project", tech_advancement="Is Technological Advancement active?")
async def request_project(interaction: Interaction, project_name: str, tech_advancement: bool = False):
    await interaction.response.defer()
    user_id = str(interaction.user.id)

    try:
        global cached_users  # the dict version
        
        user_data = cached_users.get(interaction.user.id)  # user_id as int, no need to cast to string if keys are ints
        
        if not user_data:
            await interaction.followup.send("❌ You are not registered. Use `/register` first.")
            return
        
        own_id = str(user_data.get("NationID", "")).strip()

        if not own_id:
            await interaction.followup.send("❌ Could not find your Nation ID in the sheet.")
            return

    except Exception as e:
        await interaction.followup.send(f"❌ Failed to access your data: {e}")
        return

    nation_data = get_resources(own_id)
    nation_name = nation_data[0] if nation_data else "?"
    mats = get_materials(project_name)

    if mats:
        if tech_advancement:
            for mat in mats:
                mats[mat] = mats[mat] * 0.95

        embed = discord.Embed(
            title=f"***Cost for {project_name.title()}***",
            color=discord.Color.blue()
        )

        embed.description = (
            f"**Nation:** {nation_name} (`{own_id}`)\n"
            f"**Request:**\n" +
            "\n".join([f"{mat}: {amount:,.0f}" for mat, amount in mats.items()]) +
            f"\n\n**Requested by:** {interaction.user.mention}\n"
            f"**Reason:**\nBuild project: {project_name.title()}"
        )

        await interaction.followup.send(
            embed=embed,
            view=BlueGuy(category="project", data={"nation_name": nation_name, "nation_id": own_id, "project_name": project_name, "materials": mats})
        )
    else:
        await interaction.followup.send("❌ Project not found.")




@bot.tree.command(name="send_message_to_channels", description="Send a message to multiple channels by their IDs")
@app_commands.describe(
    channel_ids="Space-separated list of channel IDs (e.g. 1319746766337478680 1357611748462563479)",
    message="The message to send to the channels"
)
async def send_message_to_channels(interaction: discord.Interaction, channel_ids: str, message: str):
    await interaction.response.defer()

    # Clean and split channel IDs
    channel_ids_list = [cid.strip().replace("<#", "").replace(">", "") for cid in channel_ids.split()]

    # Permission check function
    async def is_banker(interaction):
        return (
            any(role.name == "Government member" for role in interaction.user.roles)
            or str(interaction.user.id) == "1148678095176474678"
        )

    if not await is_banker(interaction):
        await interaction.followup.send("❌ You don't have the rights, lil bro.")
        return

    sent_count = 0
    failed_count = 0

    for channel_id in channel_ids_list:
        try:
            channel = interaction.guild.get_channel(int(channel_id))
            if channel:
                await channel.send(message)
                sent_count += 1
            else:
                failed_count += 1
        except Exception:
            failed_count += 1

    await interaction.followup.send(
        f"✅ Sent message to **{sent_count}** channel(s).\n"
        f"❌ Failed for **{failed_count}** channel(s)."
    )

@bot.tree.command(name="bug_report", description="Report a bug you found")
@app_commands.describe(bug="Describe the bug and tell me on which command you got it")
async def bug_report(interaction: discord.Interaction, bug: str):
    await interaction.response.defer()
    user_name = interaction.user.name
    try:
        with open("Bugs.json", "r") as f:
            data = json.load(f)  # Make sure we're loading the file as a dictionary, not a string
    except FileNotFoundError:
        data = {}  # If file doesn't exist, initialize an empty dictionary


    # Add the new registration
    data[user_name] = {
        "Bug": bug
    }

    # Save the updated data to the file
    try:
        with open("Bugs.json", "w") as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        await interaction.followup.send(f"❌ Error saving bug report: {e}")
        return

    await interaction.followup.send("✅ You're report was loged successfully, we will follow-up shortly")




bot.run(bot_key)
