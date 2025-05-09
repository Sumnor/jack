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
import re


load_dotenv("cred.env")
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="/", intents=intents)
bot_ey = os.getenv("bot_key")
API_KEY = os.getenv("API_KEY")
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
                "Food": "-f"
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


@bot.event
async def on_ready():
    if not hasattr(bot, "persistent_views_added"):
        bot.add_view(GrantView()) 
        bot.persistent_views_added = True
    await bot.tree.sync()
    print(f'Logged in as {bot.user}')


@bot.tree.command(name="register", description="register")
@app_commands.describe(nation_id="Not the link, just the numbers (e.g., 365325)")
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
        discord_ur = discord_label.parent.find_next_sibling("td").text.strip()
    except Exception:
        await interaction.followup.send("❌ Could not parse nation information. Possibly an invalid Nation ID.")
        return

    user_name = interaction.user.name
    user_id = str(interaction.user.id)

    if discord_ur != user_name:
        await interaction.followup.send("❌ The Discord username on the nation page doesn't match your Discord username.")
        return
    
    try:
        with open("Alliance.json", "r") as f:
            data = json.load(f)
    except FileNotFoundError:
        data = {}

    for user_data in data.values():
        if user_data["Name"] == discord_ur:
            await interaction.followup.send("❌ This Discord username is already registered.")
            return

    data[user_id] = {
        "Name": discord_ur,
        "NationID": nation_id
    }

    with open("Alliance.json", "w") as f:
        json.dump(data, f, indent=4)

    await interaction.followup.send("✅ You're registered successfully!")

@bot.tree.command(name="battle_sim", description="simulate a battle")
async def simulation(interaction: discord.Interaction, nation_id: str, war_type: str):
    await interaction.response.defer()
    user_id = str(interaction.user.id)

    try:
        with open("Alliance.json", "r") as f:
            data = json.load(f)

        if user_id not in data:
            await interaction.followup.send("You are not registered. Use `/register` first.")
            return

        own_id = data[user_id]["NationID"]

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

    try:
        with open("Alliance.json", "r") as f:
            data = json.load(f)

        user_id = str(interaction.user.id)
        if user_id not in data:
            await interaction.followup.send("❌ You are not registered.")
            return

        own_id = data[user_id]["NationID"]
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
    user_id = str(interaction.user.id)

    with open("Alliance.json", "r") as f:
        data = json.load(f)
        if user_id not in data:
            await interaction.followup.send("❌ You are not registered. Use `/register` first.")
            return

        own_id = data[user_id]["NationID"]
        
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
            await interaction.response.send_message("❌ Failed to fetch nation data. Please check the Nation ID or try again later.")
            return

        nation_data = response_json["data"]["nations"]["data"]

        if not nation_data:
            await interaction.response.send_message("❌ Nation not found. Please try again.")
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

        if any(x is None for x in [cities, food, money, gasoline, munition, steel, aluminium]):
            await interaction.followup.send("❌ Missing resource data. Please try again.")
            return 

        msg = (
            f"**Cities:** {cities}\n"
            f"**Food:** {round(food):,.0f}\n"
            f"**Money:** {round(money):,.0f}\n"
            f"**Gasoline:** {round(gasoline):,.0f}\n"
            f"**Munition:** {round(munition):,.0f}\n"
            f"**Steel:** {round(steel):,.0f}\n"
            f"**Aluminum:** {round(aluminium):,.0f}\n"
        )
        embed = discord.Embed(
            title= f"***Nation:***  {nation_name}",
            color=discord.Color.dark_embed(),
            description=(msg)
        )
        image_url = "https://i.ibb.co/qJygzr7/Leonardo-Phoenix-A-dazzling-star-emits-white-to-bluish-light-s-2.jpg"
        embed.set_footer(text=f"Brought to you by Darkstar", icon_url=image_url)
        await interaction.followup.send(embed=embed)

@bot.tree.command(name="request_grant", description="Request a grant from the alliance bank")
@app_commands.describe(request="Details of your grant request", reason="Select the reason for your grant request.")
@app_commands.choices(reason=reasons_for_grant)
async def request_grant(interaction: discord.Interaction, request: str, reason: app_commands.Choice[str]):
    user_id = str(interaction.user.id)

    with open("Alliance.json", "r") as f:
        data = json.load(f)
        if user_id not in data:
            await interaction.followup.send("❌ You are not registered. Use `/register` first.")
            return

        own_id = data[user_id]["NationID"]

    # Get the nation's data
    nation_data = get_military(own_id)
    nation_name = nation_data[0]

    # Validate request format
    request_lines = request.replace(",", "\n").split("\n")
    valid_request = True

    for line in request_lines:
        parts = line.strip().split()
        if len(parts) != 2:
            valid_request = False
            break
        resource, amount_str = parts

        if not re.match(r'^\d+(\.\d+)?(k|mil)?$', amount_str.lower()):
            valid_request = False
            break

    if not valid_request:
        await interaction.followup.send(
            f"❌ Invalid format. Please use `resource amount` format, e.g., `steel 900k` or `oil 1.2mil`.",
            ephemeral=True
        )
        return

    await interaction.response.defer()

    formatted_lines = []
    for line in request_lines:
        resource, amount_str = line.strip().split()
        amount_str = amount_str.lower().replace("mil", "000000").replace("k", "000")
        try:
            amount = int(float(amount_str))
            formatted_amount = f"{amount:,}".replace(",", ".")
            formatted_lines.append(f"{resource}: {formatted_amount}")
        except ValueError:
            formatted_lines.append(line)

    final_output = "\n".join(formatted_lines)
    description_text = f"{final_output}\n".title()


    embed = discord.Embed(
        title="💰 Grant Request",
        color=discord.Color.gold(),
        description=(
            f"**Nation:** {nation_name} (`{own_id}`)\n"
            f"**Requested by:** {interaction.user.mention}\n"
            f"**Request:**\n{description_text}"
            f"**Reason:** {reason.value.title()}\n"
        )
    )
    image_url = "https://i.ibb.co/qJygzr7/Leonardo-Phoenix-A-dazzling-star-emits-white-to-bluish-light-s-2.jpg"
    embed.set_footer(text=f"Brought to you by Darkstar", icon_url=image_url)

    await interaction.followup.send(embed=embed, view=GrantView())

@bot.tree.command(name="warn_maint", description="Notify users of bot maintenance (Dev only)")
async def warn_maint(interaction: discord.Interaction, time: str):
    await interaction.response.defer()
    user_id = str(interaction.user.id)
    POS_VIDS = [
        "https://www.youtube.com/shorts/tGKtrrX8EPU",
        "https://www.youtube.com/shorts/fFXAxN-QwIg",
        "https://www.youtube.com/shorts/kqI6NewiHZM",
        "https://www.youtube.com/shorts/4M_n-0762Og",
        "https://www.youtube.com/shorts/MYCwp05N-is",
        "https://www.youtube.com/shorts/SWr_tqW6s0Q",
        "https://www.youtube.com/shorts/4M_n-0762Og",
        "https://www.youtube.com/shorts/sFf5gOwAzDU",
        "https://www.youtube.com/shorts/NKQQJnBClAg",
        "https://www.youtube.com/shorts/rZu43eI6h1Q",
        "https://www.youtube.com/shorts/OYtN9np2LZ8"
    ]
    if user_id == "1148678095176474678":
        chosen_vid = random.choice(POS_VIDS)
        try:
            msg = (
                f"⚠️ **Bot Maintenance Notice** ⚠️\n\n"
                f"🔧 The bot will be undergoing maintenance **until {time} (UTC +1)**.\n"
                f"❌ Please **do not** accept, deny, or copy grant codes during this time.\n"
                f"🛑 Also avoid using any of the bot's commands.\n\n"
                f"We’ll be back soon! Sorry for any inconvenience this may cause.\n"
                f"If you have questions, please ping @Sumnor.\n"
                f"P.S.: If you're bored, watch this: {chosen_vid}"
            )
            await interaction.followup.send(msg)
        except Exception as e:
            await interaction.followup.send(f"❌ Failed to send maintenance warning: `{e}`")
    else:
        await interaction.followup.send("You don't have the required permission level", ephemeral=True)

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

@bot.tree.command(name="warchest", description="Request a Warchest grant")
@app_commands.describe(percent="How much percent of the warchest do you want")
@app_commands.choices(percent=percent_list)
async def warchest(interaction: discord.Interaction, percent: app_commands.Choice[str]):
    await interaction.response.defer()
    global commandscalled
    commandscalled["_global"] += 1
    print(f"/warchest invoked by {interaction.user.name} in guild {interaction.guild.name}")

    user_id = str(interaction.user.id)
    commandscalled[user_id] = commandscalled.get(user_id, 0) + 1
    try:
        with open("Alliance.json", "r") as f:
            data = json.load(f)
            if user_id not in data:
                await interaction.followup.send("❌ You are not registered. Use `/register` first.")
                return
        own_id = data[user_id]["NationID"]
    except Exception as e:
        print(f"Error checking registration: {e}")
        await interaction.followup.send("🚫 Error checking registration. Please try again later.")
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
            await interaction.response.send_message("❌ Failed to fetch nation data. Please check the Nation ID or try again later.")
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


@bot.tree.command(name="request_infra_grant", description="Calculate resources needed to upgrade infrastructure")
@app_commands.describe(current_infra="Your current infrastructure level", target_infra="Target infrastructure level", city_amount="Cities you want to upgrade")
async def request_infra_grant(interaction: Interaction, current_infra: int, target_infra: int, city_amount: int):
    await interaction.response.defer()
    user_id = str(interaction.user.id)
    commandscalled[user_id] = commandscalled.get(user_id, 0) + 1
    try:
        with open("Alliance.json", "r") as f:
            data = json.load(f)
            if user_id not in data:
                await interaction.followup.send("❌ You are not registered. Use `/register` first.")
                return
        own_id = data[user_id]["NationID"]
    except Exception as e:
        print(f"Error checking registration: {e}")
        await interaction.followup.send("🚫 Error checking registration. Please try again later.")
        return

    # Check if the target infrastructure is greater than the current infrastructure
    if target_infra <= current_infra:
        await interaction.followup.send("❌ Target infrastructure must be greater than current infrastructure.")
        return

    datta = get_resources(own_id)
    nation_name = datta[0]
    cost = calculate_total_infra_cost(current_infra, target_infra, city_amount)

    # Check if the cost exceeds 900,000 and round up if necessary
    if cost > 900_000:
        cost = math.ceil(cost / 100_000) * 100_000

    embed = discord.Embed(
        title="🛠️ Infrastructure Upgrade Cost",
        color=discord.Color.green(),
        description=f"From `{current_infra}` to `{target_infra}`\nEstimated Cost: **${cost:,.0f}**"
    )
    image_url = "https://i.ibb.co/qJygzr7/Leonardo-Phoenix-A-dazzling-star-emits-white-to-bluish-light-s-2.jpg"
    embed.set_footer(text=f"Brought to you by Darkstar", icon_url=image_url)

    await interaction.followup.send(
        embed=embed,
        view=BlueGuy(category="infra", data={
            "nation_name": nation_name,
            "nation_id": own_id,
            "from": current_infra,
            "infra": target_infra,
            "ct_count": city_amount,
            "total_cost": cost
        })
    )

def infra_cost_per_level(level: int) -> float:
    if 1 <= level <= 5:
        return 300.21 - (level * 0.035)
    elif 6 <= level <= 9:
        return 300.00
    elif 10 <= level <= 19:
        return 3000.0
    elif 20 <= level <= 29:
        return 3002.20
    elif 30 <= level <= 39:
        return 3010.30
    elif 40 <= level <= 50:
        return 3025.00
    else:
        return 3050.00 + (level - 50) * 5  # mild inflation after 50

def calculate_total_infra_cost(current_infra: int, target_infra: int, city_amount: int) -> float:
    if target_infra <= current_infra:
        return 0

    total_cost = 0
    for level in range(current_infra + 1, target_infra + 1):
        cost_per_city = infra_cost_per_level(level)
        total_cost += cost_per_city * city_amount

    return total_cost

@bot.tree.command(name="request_city", description="Calculate cost for upgrading from current city to target city")
@app_commands.describe(current_cities="Your current number of cities", target_cities="Target number of cities")
async def request_city(interaction: discord.Interaction, current_cities: int, target_cities: int):
    await interaction.response.defer()
    user_id = str(interaction.user.id)
    commandscalled[user_id] = commandscalled.get(user_id, 0) + 1
    try:
        with open("Alliance.json", "r") as f:
            data = json.load(f)
            if user_id not in data:
                await interaction.followup.send("❌ You are not registered. Use `/register` first.")
                return
        own_id = data[user_id]["NationID"]
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


mssg = (
    "Infrastructure Projects: Center for Civil Engineering, Advanced Engineering Corps, Arable Land Agency\n",
    "Space Projects: Space Program, Moon Landing, Mars Landing, Telecommunications Satellite, Guiding Satellite\n",
    "Defense Projects: Nuclear Research Facility, Nuclear Launch Facility, Missile Launch Pad, Vital Defense System, Iron Dome, Fallout Shelter\n",
    "Military Projects: Arms Stockpile, Military Salvage, Propaganda Bureau\n",
    "Espionage Projects: Intelligence Agency, Spy Satellite, Surveillance Network\n",
    "Research Projects: Clinical Research Center, Recycling Initiative, Research and Development Center, Green Technologies\n",
    "Economic Projects: Pirate Economy, Advanced Pirate Economy, International Trade Center\n",
    "Industry Boosters: Ironworks, Bauxiteworks, Emergency Gasoline Reserve, Mass Irrigation, Uranium Enrichment Program\n",
    "Domestic Affairs: Government Support Agency, Bureau of Domestic Affairs, Specialized Police Training Program\n",
    "Commerce Enhancements: Telecommunications Satellite, International Trade Center\n",
    "Login Bonus: Activity Center\n"
)


@bot.tree.command(name="send_message_to_channels", description="Send a message to multiple channels by their IDs")
@app_commands.describe(channel_ids="Space-separated list of channel IDs (e.g. 1319746766337478680 1357611748462563479)", message="The message to send to the channels")
async def send_message_to_channels(interaction: discord.Interaction, channel_ids: str, message: str):
    await interaction.response.defer()

    # Prepare the list of channel IDs by stripping the unwanted characters and handling space separation
    channel_ids_list = [channel_id.strip().replace("<#", "").replace(">", "") for channel_id in channel_ids.split()]


    # Function to check if the user has a specific role (e.g., "Government member")
    async def is_banker(interaction):
        return (
            any(role.name == "Government member" for role in interaction.user.roles)  # Modify this to fit your needs
            or str(interaction.user.id) == "1148678095176474678"
        )

    # Check if the user has permission to run the command
    if not await is_banker(interaction):
        await interaction.followup.send("You don't have the rights, lil bro.")
        return

    sent_count = 0
    failed_count = 0

    # Iterate through each channel ID provided in the list
    for channel_id in channel_ids_list:
        channel_found = False

        # Iterate over the guild's text channels and match by ID
        for channel in interaction.guild.text_channels:
            # Debug: Print the channels the bot is checking agains

            # Check if the channel ID matches
            if str(channel.id) == channel_id:
                channel_found = True

                # Check if the bot has permission to send messages in this channel
                if channel.permissions_for(interaction.guild.me).send_messages:
                    try:
                        # Send the message to the channel
                        await channel.send(message)
                        sent_count += 1
                    except discord.Forbidden:
                        failed_count += 1
                    except discord.HTTPException:
                        failed_count += 1
                    break  # Stop once the message is sent to the correct channel
        if not channel_found:
            failed_count += 1

    # Send a summary of the result
    await interaction.followup.send(
        f"✅ Sent message to {sent_count} channels.\n"
        f"❌ Failed to send message to {failed_count} channels or channel not found."
    )



bot.run(bot_key)
