import discord
import json
import math
import io
from collections import defaultdict
import matplotlib.pyplot as plt
from typing import Dict, List, Optional, Union
import matplotlib.dates as mdates
from matplotlib.ticker import FuncFormatter, MaxNLocator
from datetime import datetime, timezone, timedelta
import numpy as np
import platform
import datetime
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.ticker import FuncFormatter
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
from io import BytesIO
import json
from datetime import datetime
import re
from datetime import timezone
import io
from discord import File
from io import StringIO
import matplotlib.pyplot as plt
import asyncio
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import discord
from discord import app_commands, Interaction
import asyncio
from matplotlib.ticker import MaxNLocator, FuncFormatter
from datetime import datetime, timedelta, timezone
import matplotlib.dates as mdates
from discord.ext import tasks
from datetime import datetime, date
from datetime import datetime, timezone
from collections import defaultdict

cached_users = {}
cached_sheet_data = []

load_dotenv("cred.env")
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="/", intents=intents)
bot_key = os.getenv("Key")
#API_KEY = os.getenv("API_KEY")
YT_Key = os.getenv("YT_Key")
commandscalled = {"_global": 0}
snapshots_file = "snapshots.json"
money_snapshots = []

if os.path.exists(snapshots_file):
    with open(snapshots_file, "r") as f:
        money_snapshots = json.load(f)

UNIT_PRICES = {
    "soldiers": 5,
    "tanks": 60,
    "aircraft": 4000,
    "ships": 50000,
    "missiles": 150000,
    "nuclear": 1750000
}

BUILD_CATEGORIES = {
    "Power Plants": [
        "coal_power", "oil_power", "nuclear_power", "wind_power"
    ],
    "Raw Resources": [
        "coal_mine", "iron_mine", "lead_mine", "farm", "oil_well", "uranium_mine", "bauxite_mine"
    ],
    "Manufacturing": [
        "oil_refinery", "steel_mill", "aluminum_refinery", "munitions_factory"
    ],
    "Civil": [
        "police_station", "hospital", "recycling_center", "subway"
    ],
    "Commerce": [
        "supermarket", "bank", "shopping_mall", "stadium"
    ],
    "Military": [
        "barracks", "factory", "hangar", "drydock"
    ]
}

BUILD_KEYS = [k for v in BUILD_CATEGORIES.values() for k in v]

PROJECT_KEYS = [
    "iron_works", "bauxite_works", "arms_stockpile", "emergency_gasoline_reserve",
    "mass_irrigation", "international_trade_center", "missile_launch_pad",
    "nuclear_research_facility", "iron_dome", "vital_defense_system",
    "central_intelligence_agency", "center_for_civil_engineering", "propaganda_bureau",
    "uranium_enrichment_program", "urban_planning", "advanced_urban_planning",
    "space_program", "spy_satellite", "moon_landing", "pirate_economy",
    "recycling_initiative", "telecommunications_satellite", "green_technologies",
    "arable_land_agency", "clinical_research_center", "specialized_police_training_program",
    "advanced_engineering_corps", "government_support_agency",
    "research_and_development_center", "metropolitan_planning", "military_salvage",
    "fallout_shelter", "activity_center", "bureau_of_domestic_affairs",
    "advanced_pirate_economy", "mars_landing", "surveillance_network",
    "guiding_satellite", "nuclear_launch_facility", "military_research_center",
    "military_doctrine"
]

class NationInfoView(discord.ui.View):
    def __init__(self, nation_id, original_embed):
        super().__init__(timeout=None)
        self.nation_id = nation_id
        self.original_embed = original_embed

        self.pages = []
        self.current_page = 0

    async def fetch_and_group(self, keys, interaction):
        df = graphql_cities(self.nation_id, interaction)
        cities = extract_cities_from_df(df)
        if cities is None:
            return None, "Failed to fetch city data."
        
        groups = defaultdict(list)
        for city in cities:
            present = tuple(
                (key, city.get(key))
                for key in keys
                if city.get(key) not in (0, None, False, "")
            )
            groups[present].append(f"{city.get('name')} ({city.get('id')})")

        return groups, None

    async def show_grouped(self, interaction: discord.Interaction, keys, title):
        groups, err = await self.fetch_and_group(keys, interaction)
        if err:
            await interaction.response.send_message(err, ephemeral=True)
            return

        description = ""
        for buildings, city_names in groups.items():
            if not buildings:
                continue
            building_str = ", ".join(
                f"{k.replace('_', ' ').title()}: {v}" if not isinstance(v, bool) else f"{k.replace('_', ' ').title()}"
                for k, v in buildings
            )
            description += f"**{building_str}**\nCities: {', '.join(city_names)}\n\n"

        if description == "":
            description = "No cities with those buildings/projects found."

        embed = discord.Embed(title=title, description=description, color=discord.Color.blurple())
        embed.set_footer(text="Data fetched live from Politics & War API")

        self.clear_items()
        self.add_item(BackButton(self.original_embed, self))
        self.add_item(CloseButton())

        await interaction.response.edit_message(embed=embed, view=self)

    async def show_current_page(self, interaction):
        page_blocks = self.pages[self.current_page]
        description = "".join(page_blocks)

        embed = discord.Embed(
            title=f"Grouped City Builds (Page {self.current_page + 1}/{len(self.pages)})",
            description=description,
            color=discord.Color.blurple()
        )
        embed.set_footer(text="Data fetched live from Politics & War API")

        self.clear_items()
        if len(self.pages) > 1:
            if self.current_page > 0:
                self.add_item(PrevPageButton())
            if self.current_page < len(self.pages) - 1:
                self.add_item(NextPageButton())

        self.add_item(BackButton(self.original_embed, self))
        self.add_item(CloseButton())

        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Show Builds", style=discord.ButtonStyle.primary)
    async def builds_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        df = graphql_cities(self.nation_id, interaction)
        if df is None or df.empty:
            await interaction.response.send_message("❌ Failed to fetch or parse city data.", ephemeral=True)
            return

        try:
            nation = df.iloc[0]
            num_cities = nation.get("num_cities", 999999)
            cities = nation.get("cities", [])

            grouped = {}
            for city in cities:
                infra = city.get("infrastructure", 0)
                build_signature = tuple((key, city.get(key, 0)) for key in BUILD_KEYS)
                grouped.setdefault(build_signature, []).append((city["name"], infra))

            blocks = []

            for build, city_list in grouped.items():
                count = len(city_list)
                header = f"🏙️ **{count}/{num_cities} have this build:**\n"
                build_lines = [f"{name} (Infra: {infra})" for name, infra in city_list]

                build_dict = dict(build)
                category_lines = []
                for cat, keys in BUILD_CATEGORIES.items():
                    parts = [f"{k.replace('_', ' ').title()}: {build_dict.get(k, 0)}"
                             for k in keys if k in build_dict and build_dict[k]]
                    if parts:
                        category_lines.append(f"🔹 __{cat}__:\n" + "\n".join(f"• {p}" for p in parts))

                build_desc = "\n".join(category_lines)
                block = header + "\n".join(build_lines) + f"\n\n{build_desc}\n\n"
                blocks.append(block)

            self.pages = [blocks[i:i + 4] for i in range(0, len(blocks), 4)]
            self.current_page = 0

            await self.show_current_page(interaction)

        except Exception as e:
            await interaction.followup.send(f"❌ Error while formatting builds: {e}", ephemeral=True)

    @discord.ui.button(label="Show Projects", style=discord.ButtonStyle.secondary)
    async def projects_button(self, interaction: discord.Interaction, button: discord.ui.Button):
    
        nation_id = self.nation_id
        df = graphql_cities(nation_id, interaction)
    
        if df is None or df.empty:
            await interaction.followup.send("❌ Failed to fetch project data.", ephemeral=True)
            return
    
        try:
            nation = df.iloc[0]
            projects_status = []
    
            for proj in PROJECT_KEYS:
                emoji = "✅" if nation.get(proj, False) else "❌"
                if emoji == "✅":
                    projects_status.append(f"{proj.replace('_', ' ').title()}")
    
            chunks = [projects_status[i:i + 20] for i in range(0, len(projects_status), 20)]
            embed = discord.Embed(
                title="Projects",
                colour=discord.Colour.purple()
            )
            for chunk in chunks:
                embed.add_field(name="Projects", value="\n".join(chunk), inline=False)
    
            self.clear_items()
            self.add_item(BackButton(self.original_embed, self))
            self.add_item(CloseButton())
    
            await interaction.response.edit_message(embed=embed, view=self)
    
        except Exception as e:
            await interaction.followup.send(f"❌ Error while formatting projects: {e}", ephemeral=True)
                
    @discord.ui.button(label="Warchest", style=discord.ButtonStyle.success)
    async def audit_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        nation_id = self.nation_id
    
        try:
            API_KEY = get_api_key_for_interaction(interaction)
            GRAPHQL_URL = f"https://api.politicsandwar.com/graphql?api_key={API_KEY}"
            query = f"""
            {{
              nations(id: [{nation_id}]) {{
                data {{
                  id
                  nation_name
                  num_cities
                  food
                  uranium
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
    
            data = response.json()["data"]["nations"]["data"]
            if not data:
                await interaction.followup.send("❌ Nation not found.", ephemeral=True)
                return
    
            nation = data[0]
            city_count = int(nation["num_cities"])
    
            requirements = {
                "Money": (city_count * 1_000_000, nation["money"]),
                "Food": (city_count * 3000, nation["food"]),
                "Uranium": (city_count * 40, nation["uranium"]),
                "Gasoline": (city_count * 750, nation["gasoline"]),
                "Munitions": (city_count * 750, nation["munitions"]),
                "Steel": (city_count * 750, nation["steel"]),
                "Aluminum": (city_count * 750, nation["aluminum"]),
            }
    
            def get_completion_color(pct: float) -> str:
                if pct >= 76: return "🟢"
                if pct >= 51: return "🟡"
                if pct >= 26: return "🟠"
                if pct >= 10: return "🔴"
                return "⚫"
    
            def format_missing(name, missing, current):
                total = missing + current
                pct = (current / total) * 100 if total > 0 else 100
                return f"{round(missing):,} {name} missing {get_completion_color(pct)} ({pct:.0f}% complete)"
    
            missing_lines = [
                format_missing(name, max(0, need - have), have)
                for name, (need, have) in requirements.items()
            ]
    
            description = (
                "✅ **All materials present**"
                if all("🟢" in line for line in missing_lines)
                else "\n".join(missing_lines)
            )
    
            embed = discord.Embed(
                title="Warchest Audit",
                description=f"**Nation:** {nation['nation_name']} (`{nation_id}`)\n"
                            f"**Missing Materials:**\n{description}",
                color=discord.Color.gold()
            )
            embed.set_footer(
                text="Brought to you by Darkstar",
                icon_url="https://i.ibb.co/qJygzr7/Leonardo-Phoenix-A-dazzling-star-emits-white-to-bluish-light-s-2.jpg"
            )
    
            self.clear_items()
            self.add_item(BackButton(self.original_embed, self))  
            self.add_item(CloseButton())
    
            await interaction.message.edit(embed=embed, view=self)
    
        except Exception as e:
            await interaction.followup.send(f"❌ Error while running audit: {e}", ephemeral=True)
            
    @discord.ui.button(label="MMR", style=discord.ButtonStyle.primary)
    async def mmr_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        nation_id = self.nation_id
    
        try:
            API_KEY = get_api_key_for_interaction(interaction)
            GRAPHQL_URL = f"https://api.politicsandwar.com/graphql?api_key={API_KEY}"
    
            query = """
            query GetNationData($id: [Int]) {
                nations(id: $id) {
                    data {
                        nation_name
                        num_cities
                        cities {
                            name
                            barracks
                            factory
                            hangar
                            drydock
                        }
                    }
                }
            }
            """
            variables = {"id": [int(nation_id)]}
            response = requests.post(
                GRAPHQL_URL,
                json={"query": query, "variables": variables},
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            data = response.json()
            print("GraphQL Raw Response:", data)
    
            nation_list = data.get("data", {}).get("nations", {}).get("data", [])
            if not nation_list:
                await interaction.followup.send("❌ No nation data found.", ephemeral=True)
                return
    
            nation_data = nation_list[0]
            nation_name = nation_data.get("nation_name", "Unknown Nation")
            num_cities = nation_data.get("num_cities", 0)
            cities = nation_data.get("cities", [])
    
            barracks = sum(city.get("barracks", 0) for city in cities)
            factory = sum(city.get("factory", 0) for city in cities)
            hangar = sum(city.get("hangar", 0) for city in cities)
            drydocks = sum(city.get("drydock", 0) for city in cities)
    
            military_data = get_military(nation_id, interaction)
            if military_data is None:
                await interaction.followup.send("❌ Could not retrieve military data for this nation.", ephemeral=True)
                return
    
            (
                nation_name,
                leader_name,
                score,
                warpolicy,
                soldiers,
                tanks,
                aircraft,
                ships,
                spies,
                missiles,
                nukes,
            ) = military_data
    
            valid_mmrs = (
                [[0, 5, 5, 1], [5, 5, 5, 3]] if num_cities < 16 else [[0, 3, 5, 1], [5, 5, 5, 3]]
            )
    
            from collections import Counter
    
            def distribute_structures(total, parts):
                if parts == 0:
                    return []
                base = total // parts
                extras = total % parts
                return [base + (1 if i < extras else 0) for i in range(parts)]
    
            b_list = distribute_structures(barracks, num_cities)
            f_list = distribute_structures(factory, num_cities)
            h_list = distribute_structures(hangar, num_cities)
            d_list = distribute_structures(drydocks, num_cities)
    
            city_mmrs = list(zip(b_list, f_list, h_list, d_list))
            mmr_counts = Counter(city_mmrs)
    
            is_valid = all([b, f, h, d] in valid_mmrs for (b, f, h, d) in city_mmrs)
    
            grouped_mmr_string = "\n".join(
                f"{count} Cities: {b}/{f}/{h}/{d}" for (b, f, h, d), count in sorted(mmr_counts.items(), reverse=True)
            ) or "No cities"
    
            valid_options = "\n".join(f"{m[0]}/{m[1]}/{m[2]}/{m[3]}" for m in valid_mmrs)
    
            embed = discord.Embed(
                title=f"MMR Audit for {nation_name}",
                color=discord.Color.green() if is_valid else discord.Color.red(),
            )
            embed.add_field(name="Cities", value=str(num_cities), inline=False)
            embed.add_field(name="Grouped City MMRs", value=grouped_mmr_string, inline=False)
            embed.add_field(name="Soldiers", value=f"{soldiers}/{barracks*3000} (Missing {barracks*3000 - soldiers})", inline=False)
            embed.add_field(name="Tanks", value=f"{tanks}/{factory*250} (Missing {factory*250 - tanks})", inline=False)
            embed.add_field(name="Aircrafts", value=f"{aircraft}/{hangar*15} (Missing {hangar*15 - aircraft})", inline=False)
            embed.add_field(name="Ships", value=f"{ships}/{drydocks*5} (Missing {drydocks*5 - ships})", inline=False)
            embed.add_field(name="Status", value="✅ Valid MMR" if is_valid else "❌ Invalid MMR", inline=False)
            if not is_valid:
                embed.add_field(name="Valid Options", value=valid_options, inline=False)
    
            embed.set_footer(
                text="Brought to you by Darkstar",
                icon_url="https://i.ibb.co/qJygzr7/Leonardo-Phoenix-A-dazzling-star-emits-white-to-bluish-light-s-2.jpg"
            )
    
            
            self.clear_items()
            self.add_item(BackButton(self.original_embed, self))  
            self.add_item(CloseButton())
    
            await interaction.message.edit(embed=embed, view=self)
    
        except Exception as e:
            await interaction.followup.send(f"❌ An error occurred during MMR audit: {e}", ephemeral=True)

class PrevPageButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="⬅ Prev", style=discord.ButtonStyle.secondary)

    async def callback(self, interaction: discord.Interaction):
        view: NationInfoView = self.view
        if view.current_page > 0:
            view.current_page -= 1
            await view.show_current_page(interaction)


class NextPageButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Next ➡", style=discord.ButtonStyle.secondary)

    async def callback(self, interaction: discord.Interaction):
        view: NationInfoView = self.view
        if view.current_page < len(view.pages) - 1:
            view.current_page += 1
            await view.show_current_page(interaction)

class BackButton(discord.ui.Button):
    def __init__(self, original_embed, parent_view):
        super().__init__(label="Back", style=discord.ButtonStyle.success)
        self.original_embed = original_embed
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        self.parent_view.clear_items()
        self.parent_view.add_item(self.parent_view.builds_button)
        self.parent_view.add_item(self.parent_view.projects_button)
        self.parent_view.add_item(self.parent_view.audit_button)
        self.parent_view.add_item(CloseButton())

        await interaction.response.edit_message(embed=self.original_embed, view=self.parent_view)

class CloseButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Close", style=discord.ButtonStyle.danger)

    async def callback(self, interaction: discord.Interaction):
        await interaction.message.delete()
        self.view.stop()

from discord.ui import View, button
from discord import ButtonStyle

class MMRView(View):
    def __init__(self, is_valid, soldiers, barracks, factory, tanks, aircraft, ships, drydocks, hangars, num_cities):
        super().__init__(timeout=None)
        self.is_valid = is_valid
        self.soldiers = soldiers
        self.barracks = barracks
        self.factory = factory
        self.tanks = tanks
        self.aircraft = aircraft
        self.ships = ships
        self.drydocks = drydocks
        self.hangars = hangars
        self.num_cities = num_cities

    @button(label="Fix MMR", style=ButtonStyle.red)
    async def fix_mmr(self, interaction, button):
        if self.is_valid:
            await interaction.response.send_message(
                "Your MMR is already valid! No need to fix it."
            )
        else:
            
            peace_mmr = "0/5/5/1" if self.num_cities <= 15 else "0/3/5/1"
            war_mmr = "5/5/5/3"
            await interaction.response.send_message(
                f"Please, get that MMR to either war MMR (option={war_mmr}) or peacetime MMR (option={peace_mmr})."
            )
        await interaction.message.edit(view=None)

    @button(label="Buy Troops", style=ButtonStyle.blurple)
    async def buy_troops(self, interaction, button):
        if not self.is_valid:
            await interaction.response.send_message(
                "MMR is invalid. Please fix your MMR first."
            )
            return

        missing = []
        max_soldiers = self.barracks * 3000
        max_tanks = self.factory * 250
        max_aircraft = self.hangars * 15
        max_ships = self.drydocks * 5

        if self.soldiers < max_soldiers:
            missing.append(f"{max_soldiers - self.soldiers} soldiers")
        if self.tanks < max_tanks:
            missing.append(f"{max_tanks - self.tanks} tanks")
        if self.aircraft < max_aircraft:
            missing.append(f"{max_aircraft - self.aircraft} aircraft")
        if self.ships < max_ships:
            missing.append(f"{max_ships - self.ships} ships")

        if not missing:
            await interaction.response.send_message(
                "Your troops are all stocked up. No need to buy more."
            )
            await interaction.message.edit(view=None)
            return

        if len(missing) == 1:
            msg = missing[0]
        else:
            msg = ", ".join(missing[:-1]) + " and " + missing[-1]

        await interaction.response.send_message(
            f"The MMR is looking good, but please buy your troops: {msg}."
        )
        await interaction.message.edit(view=None)

    @button(label="Close", style=ButtonStyle.gray)
    async def close(self, interaction, button):
        await interaction.response.send_message(
            "Looking good. Nothing to complain about."
        )
        await interaction.message.edit(view=None)
        self.stop()



class BlueGuy(discord.ui.View):
    def __init__(self, category=None, data=None):
        super().__init__(timeout=None)
        self.category = category
        self.data = data or {}

    @discord.ui.button(label="Request Grant", style=discord.ButtonStyle.green, custom_id="req_money_needed")
    async def send_request(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        person = str(self.data.get("person", None))
        print(person)
        presser = str(interaction.user.id)
        print(presser)
        if presser != person:
            if presser not in ["1378012299507269692", "1148678095176474678"]:
                await interaction.followup.send("No :wilted_rose:", ephemeral=True)
                return

        embed = discord.Embed(title="Request Grant", color=discord.Color.green())

        reason = "Unknown Request"
        materials = {}
        nation_name = self.data.get("nation_name", "?")
        nation_id = self.data.get("nation_id", "unknown")

        note = "/"
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
            reason = f"City {from_cities} - {to_cities}"
            materials = {"Money": self.data.get("total_cost", 0)}

        elif self.category == "project":
            project_name = self.data.get("project_name", "?")
            reason = f"Build project: {project_name}"
            materials = self.data.get("materials", {})
            notes = self.data.get("note", "None")
            note = f"Note: {notes}"

        
        description_lines = [f"**Nation:** {nation_name} (`{nation_id}`)", "**Request:**"]
        if materials:
            for name, amount in materials.items():
                description_lines.append(f"{name}: {amount:,.0f}")
        else:
            description_lines.append("None")

        description_lines.append(f"\n**Requested by:** <@{presser}>")
        embed.description = "\n".join(description_lines)

        
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.add_field(name="Note", value=note, inline=False)

        
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
                pass  
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
                
                await interaction.channel.send(f"✅ Grant request has been approved and sent! {user_mention}")

        except Exception as e:
            try:
                await interaction.followup.send(f"❌ Error: `{e}`", ephemeral=True)
            except discord.NotFound:
                await interaction.channel.send(f"❌ Error (no followup): `{e}`")


    @button(label="🕒 Delay", style=discord.ButtonStyle.primary, custom_id="grant_delay")
    async def delay_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.is_government_member(interaction):
            await interaction.response.send_message("❌ You need the 'Banker' role to approve grant requests.", ephemeral=True)
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
                "Iron": "-i",
                "Bauxite": "-b",
                "Coal": "-c",
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

            await interaction.response.send_message(f"{' '.join(command_parts)}", ephemeral=True)

        except Exception as e:
            await interaction.response.send_message(f"❌ Error parsing embed: `{e}`", ephemeral=True)

class RawsAuditView(discord.ui.View):
    def __init__(self, output, audits):
        super().__init__(timeout=None)
        self.output = output
        self.audits = audits  

    @discord.ui.button(label="Request Yellow", style=discord.ButtonStyle.primary, custom_id="request_yellow")
    async def request_yellow(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_request(interaction, "🟡", discord.Color.yellow())

    @discord.ui.button(label="Request Orange", style=discord.ButtonStyle.primary, custom_id="request_orange")
    async def request_orange(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_request(interaction, "🟠", discord.Color.orange())

    @discord.ui.button(label="Request Red", style=discord.ButtonStyle.danger, custom_id="request_red")
    async def request_red(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_request(interaction, "🔴", discord.Color.red())

    async def handle_request(self, interaction: discord.Interaction, color_emoji: str, embed_color: discord.Color):
        await interaction.response.defer(ephemeral=True)

        user_id = interaction.user.id
        guild_id = interaction.guild.id
        bot = interaction.client

        channel = bot.get_channel(get_grant_channel(guild_id))
        if not channel:
            await interaction.followup.send("❌ Target channel not found.")
            return

        sheet = get_registration_sheet()
        rows = sheet.get_all_records()

        for nation_id, entry in self.audits.items():
            nation_name = entry["nation_name"]
            missing_resources = entry.get("missing", [])
        
            relevant_lines = [
                f"{res_name}: {float(amount):.2f}"
                for res_name, amount, res_color in missing_resources
                if res_color == color_emoji
            ]
        
            if not relevant_lines:
                continue  

            row = next((r for r in rows if str(r.get("NationID", "")).strip() == str(nation_id)), None)
            if not row:
                continue

            discord_id = row.get("DiscordID", None)
            if not discord_id:
                continue

            embed = discord.Embed(
                title="Resource Request",
                description=(
                    f"**Nation:** {nation_name} (`{nation_id}`)\n"
                    f"**Request:**\n" + "\n".join(relevant_lines) + "\n"
                    f"**Reason:** Resources for Production\n"
                    f"**Requested by:** <@{discord_id}>"
                ),
                color=embed_color
            )
            image_url = "https://i.ibb.co/qJygzr7/Leonardo-Phoenix-A-dazzling-star-emits-white-to-bluish-light-s-2.jpg"
            embed.set_footer(text="Brought to you by Darkstar", icon_url=image_url)

            await channel.send(embed=embed, view=GrantView())

        await interaction.followup.send(f"✅ Processed {color_emoji} requests.")
    
def graphql_cities(nation_id, interaction=None, guild_id=None):
    if not guild_id:
        API_KEY = get_api_key_for_interaction(interaction)
    if not interaction:
        API_KEY = get_api_key_for_guild(guild_id)
    GRAPHQL_URL = f"https://api.politicsandwar.com/graphql?api_key={API_KEY}"

    
    project_fields = "\n".join(PROJECT_KEYS)

    query = f"""
    {{
      nations(id: [{nation_id}]) {{
        data {{
          num_cities
          {project_fields}
          cities {{
            name
            id
            infrastructure
            land
            powered
            oil_power
            wind_power
            coal_power
            nuclear_power
            coal_mine
            oil_well
            uranium_mine
            barracks
            farm
            police_station
            hospital
            recycling_center
            subway
            supermarket
            bank
            shopping_mall
            stadium
            lead_mine
            iron_mine
            bauxite_mine
            oil_refinery
            aluminum_refinery
            steel_mill
            munitions_factory
            factory
            hangar
            drydock
          }}
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

def graphql_request(nation_id, interaction=None, guild_id=None):
    if not guild_id:
        API_KEY = get_api_key_for_interaction(interaction)
    if not interaction:
        API_KEY = get_api_key_for_guild(guild_id)
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
          war_policy
          domestic_policy
          projects
          turns_since_last_project
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

# --- Core Logic ---
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

def extract_cities_from_df(df):
    if df is None or df.empty:
        return None
    try:
        cities = df.at[0, "cities"]
        return cities
    except Exception as e:
        print(f"Error extracting cities from df: {e}")
        return None

def get_resources(nation_id, interaction=None, guild_id=None):
    if not guild_id:
        df = graphql_request(nation_id, interaction, None)
    if not interaction:
        df = graphql_request(nation_id, None, guild_id)
    if df is not None:
        try:
            row = df[df["id"].astype(str) == str(nation_id)].iloc[0]

            return (
                row.get("nation_name", ""),
                row.get("num_cities", 0),
                row.get("food", 0),
                row.get("money", 0),
                row.get("gasoline", 0),
                row.get("munitions", 0),
                row.get("steel", 0),
                row.get("aluminum", 0),
                row.get("bauxite", 0),
                row.get("lead", 0),
                row.get("iron", 0),
                row.get("oil", 0),
                row.get("coal", 0),
                row.get("uranium", 0),
            )
        except IndexError:
            return None

def get_general_data(nation_id, interaction):
    df = graphql_request(nation_id, interaction)
    if df is not None:
        try:
            row = df[df["id"].astype(str) == str(nation_id)].iloc[0]
            return (
                row.get("alliance_id", "Unknown"),
                row.get("alliance_position", "Unknown"),
                row.get("alliance.name", "None/Unaffiliated"),
                row.get("domestic_policy", "Unknown"),
                row.get("num_cities", "/"),
                row.get("color", "Unknown"),
                row.get("last_active", "/"),
                row.get("projects", "Unknown"),
                row.get("turns_since_last_project", "/"),
            )
        except IndexError:
            return None

def get_military(nation_id, interaction):
    df = graphql_request(nation_id, interaction)
    if df is not None:
        try:
            row = df[df["id"].astype(str) == str(nation_id)].iloc[0]
            return (
                row.get("nation_name", ""),
                row.get("leader_name", ""),
                row.get("score", 0),
                row.get("war_policy", ""),
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




import os
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import datetime
import asyncio
import traceback



def get_credentials():
    creds_str = os.environ.get("GOOGLE_CREDENTIALS")
    if not creds_str:
        raise RuntimeError("GOOGLE_CREDENTIALS not found in environment.")
    try:
        creds_json = json.loads(creds_str)
        return creds_json
    except Exception as e:
        raise RuntimeError(f"Failed to load GOOGLE_CREDENTIALS: {e}")

def get_client():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(get_credentials(), scope)
    client = gspread.authorize(creds)
    return client



def get_registration_sheet(guild_id):
    client = get_client()
    sheet_name = f"{guild_id}_Registrations"
    print(f"🔍 Looking for sheet: '{sheet_name}'")
    
    try:
        # Try to open the guild-specific sheet
        spreadsheet = client.open(sheet_name)
        sheet = spreadsheet.sheet1
        print(f"✅ Found sheet: '{sheet_name}' (worksheet title: '{sheet.title}')")
        
        # Check if sheet is empty or has minimal data
        records = sheet.get_all_records()
        if len(records) <= 1:
            print(f"⚠️ Guild sheet only has {len(records)} records. Consider running migration.")
        
        return sheet
    except gspread.SpreadsheetNotFound:
        print(f"❌ Sheet '{sheet_name}' not found.")
        '''try:
            # Create new guild-specific sheet
            spreadsheet = client.create(sheet_name)
            sheet = spreadsheet.sheet1
            sheet.update('A1:C1', [['DiscordUsername', 'DiscordID', 'NationID']])
            print(f"✅ Created new sheet: '{sheet_name}'")
            
            # Auto-migrate data from main sheet
            print(f"🔄 Auto-migrating data from main 'Registrations' sheet...")
            migrate_data_to_guild_sheet(guild_id)
            
            return sheet
        except Exception as create_error:
            print(f"❌ Failed to create sheet '{sheet_name}': {create_error}")
            raise'''
    except Exception as e:
        print(f"❌ Unexpected error opening sheet '{sheet_name}': {e}")
        raise

def get_dm_sheet():
    client = get_client()
    return client.open("DmsSentByGov").sheet1

def get_alliance_sheet(guild_id):
    client = get_client()
    return client.open(f"{guild_id}_AllianceNet").sheet1

def get_auto_requests_sheet(guild_id):
    client = get_client()
    return client.open(f"{guild_id}_AutoRequests").sheet1  


def get_gov_role(interaction: discord.Interaction):
    return get_settings_value("GOV_ROLE", interaction.guild.id)

def get_member_role(interaction: discord.Interaction):
    return get_settings_value("MEMBER_ROLE", interaction.guild.id)

def get_server_sheet():
    client = get_client()
    return client.open("BotServerSettings").sheet1  # Your sheet must have: server_id | api_key | lott_channel_ids

# --- Sheet Access Logic ---
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

def save_to_alliance_net(data_row, guild_id):
    try:
        sheet = get_alliance_sheet(guild_id)
        sheet.append_row(data_row)
        print("✅ Data saved to Alliance Net")
    except Exception as e:
        print(f"❌ Failed to save to Alliance Net: {e}")

def save_dm_to_sheet(sender_name, recipient_name, message):
    sheet = get_dm_sheet()
    headers = sheet.row_values(1)  
    data = {
        "Timestamp": datetime.now(timezone.utc).isoformat(),
        "Sender": sender_name,
        "Recipient": recipient_name,
        "Message": message
    }

    
    row = [data.get(header, "") for header in headers]
    sheet.append_row(row)

cached_users = {}
cached_registrations = {}
cached_conflicts = []
cached_conflict_data = []

def load_registration_data(guild_id):
    global cached_users, cached_registrations

    guild_id = str(guild_id)

    try:
        sheet = get_registration_sheet(guild_id)
        print(f"📄 Sheet object: {sheet}")
        print(f"📘 Sheet title: {sheet.title}")

        records = sheet.get_all_records()
        print(f"📥 Records fetched: {len(records)}")

        user_map = {}

        for record in records:
            discord_id = str(record.get('DiscordID', '')).strip()
            discord_username = str(record.get('DiscordUsername', '')).strip().lower()
            nation_id = str(record.get('NationID', '')).strip()

            if discord_id and discord_username and nation_id:
                user_map[discord_id] = {
                    'DiscordUsername': discord_username,
                    'NationID': nation_id
                }

        # Store guild-specific data instead of overwriting global
        if guild_id not in cached_users:
            cached_users[guild_id] = {}
        if guild_id not in cached_registrations:
            cached_registrations[guild_id] = {}
            
        cached_users[guild_id] = user_map
        cached_registrations[guild_id] = records

        print(f"✅ Loaded {len(user_map)} users from registration sheet for guild {guild_id}.")

    except Exception as e:
        print(f"❌ Failed to load registration sheet data for guild {guild_id}: {e}")
        import traceback
        print(traceback.format_exc())

from datetime import datetime, timezone
async def daily_refresh_loop(guild_id):
    while True:
        now = datetime.now(timezone.utc)
        next_midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        wait_seconds = (next_midnight - now).total_seconds()
        await asyncio.sleep(wait_seconds)
        print("🔄 Refreshing all cached sheet data at UTC midnight...")
        load_registration_data(guild_id)


def load_sheet_data(guild_id):
    """Simplified function that just calls load_registration_data"""
    guild_id = str(guild_id)
    try:
        load_registration_data(guild_id)
        # Only create the daily refresh loop once
        if not hasattr(bot, '_refresh_loops'):
            bot._refresh_loops = set()
        if guild_id not in bot._refresh_loops:
            bot.loop.create_task(daily_refresh_loop(guild_id))
            bot._refresh_loops.add(guild_id)
    except Exception as e:
        print(f"❌ Failed to load sheet data for guild {guild_id}: {e}")
        import traceback
        print(traceback.format_exc())

def migrate_data_to_guild_sheet(guild_id):
    client = get_client()
    
    try:
        # Open the main registrations sheet
        main_sheet = client.open("Registrations").sheet1
        main_records = main_sheet.get_all_records()
        print(f"📋 Found {len(main_records)} records in main 'Registrations' sheet")
        
        # Get or create guild-specific sheet
        guild_sheet = get_registration_sheet(guild_id)
        
        # Clear existing data and add headers
        guild_sheet.clear()
        guild_sheet.update('A1:C1', [['DiscordUsername', 'DiscordID', 'NationID']])
        
        # Copy all data
        if main_records:
            data_to_copy = []
            for record in main_records:
                data_to_copy.append([
                    record.get('DiscordUsername', ''),
                    record.get('DiscordID', ''),
                    record.get('NationID', '')
                ])
            
            guild_sheet.update(f'A2:C{len(data_to_copy)+1}', data_to_copy)
            print(f"✅ Migrated {len(data_to_copy)} records to guild {guild_id} sheet")
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")

def get_grant_channel(guild_id):
    try:
        sheet = get_settings_sheet()
        rows = sheet.get_all_records()

        for row in rows:
            if str(row.get("server_id")) == str(guild_id) and row.get("key") == "GRANTS_CHANNEL":
                value = row.get("value")
                return str(value).strip() if value is not None else None

        print(f"⚠️ GRANTS_CHANNEL not found for guild {guild_id}")
        return None

    except Exception as e:
        print(f"❌ Error fetching grant channel for guild {guild_id}: {e}")
        return None

@tasks.loop(hours=1)
async def process_auto_requests():
    REASON_FOR_GRANT = "Resources for Production (Auto)"
    
    try:
        guilds = bot.guilds
        
        if not guilds:
            print("No guilds found")
            return
        
        now = datetime.now(timezone.utc)
        
        for guild in guilds:
            try:
                print(f"Processing guild: {guild.name} ({guild.id})")
                
                channel_id = get_grant_channel(guild.id)
                if not channel_id:
                    print(f"No grant channel configured for guild: {guild.name} ({guild.id})")
                    continue
                
                channel = guild.get_channel(int(channel_id))
                if channel is None:
                    continue
                
                sheet = get_auto_requests_sheet(guild.id)
                if not sheet:
                    continue
                
                all_rows = await asyncio.to_thread(sheet.get_all_values)
                if not all_rows or len(all_rows) < 2:
                    continue
                
                header = [h.strip() for h in all_rows[0] if h.strip()]
                if len(header) != len(set(header)):
                    raise ValueError(f"Guild {guild.name} sheet header row contains duplicates or blanks: {header}")
                
                col_index = {col: idx for idx, col in enumerate(all_rows[0])}
                rows = all_rows[1:]
                
                processed_count = 0
                
                for i, row in enumerate(rows, start=2):
                    try:
                        nation_id = row[col_index.get("NationID", -1)] if col_index.get("NationID", -1) != -1 else ""
                        if not nation_id:
                            print(f"Guild {guild.name}, row {i}: Skipping due to empty NationID")
                            continue
                        
                        nation_info_df = graphql_request(nation_id, interaction=discord.Interaction)
                        nation_name = nation_info_df.loc[0, "nation_name"] if nation_info_df is not None and not nation_info_df.empty else "Unknown"
                        
                        discord_id = row[col_index["DiscordID"]]
                        time_period_days = int(float(row[col_index["TimePeriod"]].strip() or "1"))
                        
                        last_requested_str = row[col_index["LastRequested"]].strip()
                        last_requested = (
                            datetime.strptime(last_requested_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
                            if last_requested_str else datetime.min.replace(tzinfo=timezone.utc)
                        )
                        
                        if now - last_requested < timedelta(days=time_period_days):
                            continue
                        
                        requested_resources = {}
                        for res in ["Coal", "Oil", "Bauxite", "Lead", "Iron"]:
                            val_str = row[col_index[res]].strip()
                            amount = parse_amount(val_str)
                            if amount > 0:
                                requested_resources[res] = amount
                        
                        if not requested_resources:
                            continue
                        
                        description_text = "\n".join([f"{resource}: {amount:,}".replace(",", ".") for resource, amount in requested_resources.items()])
                        
                        embed = discord.Embed(
                            title="💰 Grant Request",
                            color=discord.Color.gold(),
                            description=(
                                f"**Nation:** {nation_name} (`{nation_id}`)\n"
                                f"**Requested by:** <@{discord_id}>\n"
                                f"**Request:**\n{description_text}\n"
                                f"**Reason:** {REASON_FOR_GRANT}\n"
                            )
                        )
                        image_url = "https://i.ibb.co/qJygzr7/Leonardo-Phoenix-A-dazzling-star-emits-white-to-bluish-light-s-2.jpg"
                        embed.set_footer(text="Brought to you by Darkstar", icon_url=image_url)
                        
                        await channel.send(embed=embed, view=GrantView())
                        
                        await asyncio.to_thread(sheet.update_cell, i, col_index["LastRequested"] + 1, now.strftime("%Y-%m-%d %H:%M:%S"))
                        processed_count += 1
                        
                        await asyncio.sleep(0.5)
                        
                    except Exception as inner_ex:
                        print(f"Error processing guild {guild.name}, row {i}: {inner_ex}")
                
                print(f"Processed {processed_count} requests from guild: {guild.name}")
                
            except Exception as guild_ex:
                print(f"Error processing guild {guild.name}: {guild_ex}")
    
    except Exception as ex:
        print(f"Error in process_auto_requests task: {ex}")
    
@tasks.loop(hours=1)
async def hourly_snapshot():
    now = datetime.now(timezone.utc)
    current_hour = now.replace(minute=0, second=0, microsecond=0)

    guild_ids = {str(guild.id) for guild in bot.guilds}

    for guild_id in guild_ids.copy():  
        try:
            alliance_sheet = get_alliance_sheet(guild_id)
            rows = alliance_sheet.get_all_records()
            if rows:
                last_time_str = rows[-1].get("TimeT", "")
                last_time = datetime.fromisoformat(last_time_str)
                last_time_hour = last_time.replace(minute=0, second=0, microsecond=0)
                if last_time_hour == current_hour:
                    print(f"⏭ Already saved snapshot this hour for guild {guild_id} (last snapshot time: {last_time_hour})")
                    guild_ids.remove(guild_id)
            else:
                print(f"⚠️ No entries in alliance sheet for guild {guild_id}; proceeding with snapshot.")
        except Exception as e:
            print(f"❌ Failed to check alliance sheet for guild {guild_id}: {e}")

    if not guild_ids:
        print("⚠️ No guilds require snapshots this hour. Exiting.")
        return

    try:
        settings_sheet = get_settings_sheet()
        settings_rows = settings_sheet.get_all_records()
    except Exception as e:
        print(f"❌ Failed to get settings sheet: {e}")
        return

    guild_api_keys = {}
    for row in settings_rows:
        server_id = str(row.get("server_id")).strip()
        key_name = row.get("key", "").strip()
        value = row.get("value", "")
        if isinstance(value, str):
            value = value.strip()
        if key_name == "API_KEY" and server_id in guild_ids and value:
            guild_api_keys[server_id] = value

    if not guild_api_keys:
        print("⚠️ No API_KEYs found for current guilds. Skipping snapshot.")
        return

    for guild_id, api_key in guild_api_keys.items():

        try:
            if guild_id not in cached_users:
                load_sheet_data(guild_id)

            guild_users = cached_users.get(guild_id, {})
            print(f"👥 Found {len(guild_users)} registered users in guild {guild_id}")

            if not guild_users:
                print(f"⚠️ No registered users found for guild {guild_id}. Skipping.")
                continue

            totals = {
                "money": 0, "food": 0, "gasoline": 0, "munitions": 0, "steel": 0,
                "aluminum": 0, "bauxite": 0, "lead": 0, "iron": 0,
                "oil": 0, "uranium": 0, "coal": 0, "num_cities": 0
            }
            processed_nations = 0
            failed = 0

            GRAPHQL_URL = f"https://api.politicsandwar.com/graphql?api_key={api_key}"
            prices_query = """
            {
              top_trade_info {
                resources {
                  resource
                  average_price
                }
              }
            }
            """
            try:
                resp = requests.post(GRAPHQL_URL, json={"query": prices_query}, headers={"Content-Type": "application/json"})
                resp.raise_for_status()
                prices = {item["resource"]: float(item["average_price"]) for item in resp.json()["data"]["top_trade_info"]["resources"]}
            except Exception as e:
                print(f"❌ Error fetching prices for guild {guild_id}: {e}")
                prices = {}

            seen_ids = set()

            for user_id, user_data in guild_users.items():
                nation_id = str(user_data.get("NationID", "")).strip()
                username = user_data.get("DiscordUsername", "unknown")

                if not nation_id:
                    print(f"⚠️ No Nation ID for user {username} ({user_id}) in guild {guild_id}")
                    failed += 1
                    continue

                if nation_id in seen_ids:
                    print(f"⚠️ Duplicate Nation ID {nation_id} for user {username} in guild {guild_id}")
                    failed += 1
                    continue

                seen_ids.add(nation_id)

                try:
                    resources = get_resources(nation_id, None, guild_id)
                    (nation_name, num_cities, food, money, gasoline, munitions, steel,
                     aluminum, bauxite, lead, iron, oil, coal, uranium) = resources

                    totals["money"] += money
                    totals["food"] += food
                    totals["gasoline"] += gasoline
                    totals["munitions"] += munitions
                    totals["steel"] += steel
                    totals["aluminum"] += aluminum
                    totals["bauxite"] += bauxite
                    totals["lead"] += lead
                    totals["iron"] += iron
                    totals["oil"] += oil
                    totals["coal"] += coal
                    totals["uranium"] += uranium
                    totals["num_cities"] += num_cities
                    processed_nations += 1

                    await asyncio.sleep(5)
                except Exception as e:
                    failed += 1
                    print(f"❌ Failed for nation {nation_id} ({username}) in guild {guild_id}: {e}")
                    continue

            resource_values = {}
            total_wealth = totals["money"]

            for resource, amount in totals.items():
                if resource in ["money", "num_cities"]:
                    continue
                price = prices.get(resource, 0)
                value = amount * price
                resource_values[resource] = value
                total_wealth += value

            timestamp = current_hour.isoformat()
            money_snapshots.append({"time": timestamp, "total": total_wealth})

            save_row = [timestamp, total_wealth, totals["money"]]
            ordered_resources = [
                "food", "gasoline", "munitions", "steel", "aluminum",
                "bauxite", "lead", "iron", "oil", "coal", "uranium"
            ]
            for res in ordered_resources:
                save_row.append(resource_values.get(res, 0))

            try:
                save_to_alliance_net(save_row, guild_id=guild_id)
                print(f"💾 Snapshot saved at {timestamp} for guild {guild_id}: ${total_wealth:,.0f} (processed {processed_nations} nations, {failed} failed)")
            except Exception as e:
                print(f"❌ Failed to save snapshot for guild {guild_id}: {e}")

        except Exception as e:
            print(f"❌ Error processing guild {guild_id}: {e}")

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

@tasks.loop(hours=2)
async def check_api_loop():
    nation_id = "680627"

    for guild in bot.guilds:
        try:
            channel_id = get_warn_channel(guild.id)
            if not channel_id:
                print(f"⚠️ No WARN_CHANNEL configured for guild: {guild.name} ({guild.id})")
                continue

            channel = guild.get_channel(int(channel_id))
            if channel is None:
                print(f"⚠️ WARN_CHANNEL ID {channel_id} not found in guild {guild.name}")
                continue

            score = get_nation_score(nation_id)

            if score is None:
                message1 = (
                    f"# ❗ Important ❗\n"
                    f"The PnW API is currently **offline**, so commands which rely on it are unavailable:\n"
                    f"- All `/request_...` commands\n"
                    f"- `/nation_info`\n"
                    f"You will be notified when the API is back online. Thank you for your understanding. ||<@&1192368632622219305>||"
                )
                await channel.send(message1)

                for _ in range(12):  # 12 * 5min = 1 hour of checking
                    await asyncio.sleep(300)
                    score = get_nation_score(nation_id)
                    if score is not None:
                        message2 = (
                            f"# ✅ Good News ✅\n"
                            f"The API is back online! 🎉\n"
                            f"You may now use all bot commands again. Thank you for your patience 🍪 ||<@&1192368632622219305>||"
                        )
                        await channel.send(message2)
                        break

        except Exception as e:
            print(f"❌ Error processing guild {guild.name}: {e}")


def get_nation_score(nation_id: str) -> float | None:
    API_KEY = get_api_key_for_interaction(interaction=discord.Interaction)
    GRAPHQL_URL = f"https://api.politicsandwar.com/graphql?api_key={API_KEY}"
    query = """
    query ($id: [Int!]) {
      nations(id: $id) {
        data {
          id
          nation_name
          score
        }
      }
    }
    """
    variables = {"id": [int(nation_id)]}
    try:
        res = requests.post(GRAPHQL_URL, json={"query": query, "variables": variables})
        res.raise_for_status()
        data = res.json()
        nation_data = data["data"]["nations"]["data"]
        if not nation_data:
            return None
        return float(nation_data[0]["score"])
    except Exception as e:
        print(f"[ERROR] get_nation_score: {e}")
        return None

@hourly_snapshot.before_loop
async def before_hourly():
    print("Waiting for bot to be ready before starting hourly snapshots...")
    await bot.wait_until_ready()

def get_api_key_for_interaction(interaction: discord.Interaction) -> str:
    return get_settings_value("API_KEY", interaction.guild.id)

def get_api_key_for_guild(guild_id: int) -> str | None:
    try:
        sheet = get_settings_sheet()
        rows = sheet.get_all_records()

        for row in rows:
            if str(row.get("server_id")) == str(guild_id) and row.get("key") == "API_KEY":
                return row.get("value").strip()

        print(f"⚠️ API_KEY not found for guild {guild_id}")
        return None

    except Exception as e:
        print(f"❌ Error fetching API key for guild {guild_id}: {e}")
        return None


@bot.event
async def on_ready():
    bot.add_view(GrantView())  
    for guild in bot.guilds:
        load_sheet_data(guild.id)
        load_registration_data(guild.id)
    bot.add_view(BlueGuy()) 
    print("Starting hourly snapshot task...")
    if not hourly_snapshot.is_running():
        hourly_snapshot.start()
    if not process_auto_requests.is_running():
        process_auto_requests.start()
    '''if not check_api_loop.is_running():
        check_api_loop.start()'''
    await bot.tree.sync()
    print(f"✅ Logged in as {bot.user}")

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    # ── INTEL PARSING ──────────────────────────────────────────────
    intel_pattern = re.compile(
        r"You successfully gathered intelligence about (?P<nation>.+?)\. .*?has "
        r"\$(?P<money>[\d,\.]+), (?P<coal>[\d,\.]+) coal, (?P<oil>[\d,\.]+) oil, "
        r"(?P<uranium>[\d,\.]+) uranium, (?P<lead>[\d,\.]+) lead, (?P<iron>[\d,\.]+) iron, "
        r"(?P<bauxite>[\d,\.]+) bauxite, (?P<gasoline>[\d,\.]+) gasoline, "
        r"(?P<munitions>[\d,\.]+) munitions, (?P<steel>[\d,\.]+) steel, "
        r"(?P<aluminum>[\d,\.]+) aluminum and (?P<food>[\d,\.]+) food"
    )

    match = intel_pattern.search(message.content)
    if match:
        await message.add_reaction("<:traumacat:1383500525189861517>")

        nation = match.group("nation")
        resources = {
            key: float(match.group(key).replace(",", ""))
            for key in match.groupdict() if key != "nation"
        }

        try:
            # Get guild ID if message is in a guild
            guild_id = message.guild.id if message.guild else None

            # 🔑 Get prices with guild context
            prices = get_prices(guild_id=guild_id)  # <-- this assumes your function accepts it

            resource_prices = {
                item["resource"]: float(item["average_price"])
                for item in prices["data"]["top_trade_info"]["resources"]
            }

            total_value = sum(
                val * resource_prices.get(key, 1) if key != "money" else val
                for key, val in resources.items()
            )
            estimated_loot = total_value * 0.14

        except Exception as e:
            print(f"Error getting prices or calculating loot: {e}")
            estimated_loot = 0.0

        try:
            sheet = get_sheet_s("Nation WC")
            all_records = sheet.get_all_records()
            nation_names = [row["Nation"] for row in all_records if "Nation" in row]

            update_row = [
                nation,
                f"{resources['money']:.2f}",
                f"{resources['coal']:.2f}",
                f"{resources['oil']:.2f}",
                f"{resources['uranium']:.2f}",
                f"{resources['lead']:.2f}",
                f"{resources['iron']:.2f}",
                f"{resources['bauxite']:.2f}",
                f"{resources['gasoline']:.2f}",
                f"{resources['munitions']:.2f}",
                f"{resources['steel']:.2f}",
                f"{resources['aluminum']:.2f}",
                f"{resources['food']:.2f}",
                datetime.now().strftime('%B %d, %Y at %I:%M %p')
            ]

            if nation in nation_names:
                row_index = nation_names.index(nation) + 2
                existing_row = sheet.row_values(row_index)
                existing_data = existing_row[1:13]
                new_data = update_row[1:13]

                if all(f"{float(e):.2f}" == f"{float(n):.2f}" for e, n in zip(existing_data, new_data)):
                    await message.channel.send(f"✅ Intel on **{nation}** already reported and unchanged.")
                    await bot.process_commands(message)
                    return

                sheet.update(f"A{row_index}:N{row_index}", [update_row])
            else:
                sheet.append_row(update_row)

            embed = discord.Embed(
                title=f"🕵️ Intel Report: {nation}",
                description="Your spies report the following stockpile:",
                color=discord.Color.orange()
            )

            for k, v in resources.items():
                if k in resource_prices:
                    embed.add_field(name=k.capitalize(), value=f"{v:,.2f} @ {resource_prices[k]:,.2f}", inline=True)
                else:
                    embed.add_field(name=k.capitalize(), value=f"{v:,.2f}", inline=True)

            embed.add_field(name="💰 Estimated Loot (14%)", value=f"${estimated_loot:,.2f}", inline=False)

            await message.channel.send(embed=embed)

        except Exception as e:
            print(f"Error in intel handler: {e}")
            await message.channel.send("❌ Failed to process intel report.")

    # ── DM LOGGING ─────────────────────────────────────────────────
    if message.guild is None:
        default_reply = "Thanks for your message! We'll get back to you soon."

        last_bot_msg = None
        async for msg in message.channel.history(limit=20, before=message.created_at):
            if msg.author == bot.user:
                last_bot_msg = msg.content
                break

        if last_bot_msg != default_reply:
            try:
                # Load LOGS channel from BotServerSettings
                settings_sheet = get_sheet_s("BotServerSettings")
                all_settings = settings_sheet.get_all_records()

                # Find first LOGS row for any server (since it's DM)
                logs_channel_id = None
                for row in all_settings:
                    if row["key"] == "LOGS":
                        logs_channel_id = int(row["value"])
                        break

                if logs_channel_id:
                    log_channel = bot.get_channel(logs_channel_id)
                    if log_channel:
                        embed = discord.Embed(
                            title="📩 New DM Received",
                            description=(
                                f"**From:** {message.author} (`{message.author.id}`)\n"
                                f"**User message:**\n{message.content}\n\n"
                                f"**Last bot message to user:**\n{last_bot_msg or 'None'}"
                            ),
                            color=discord.Color.blue()
                        )
                        await log_channel.send(embed=embed)

            except Exception as e:
                print(f"Failed to log DM: {e}")

        await message.channel.send(default_reply)

    await bot.process_commands(message)



@bot.tree.command(name="register", description="Register your Nation ID")
@app_commands.describe(nation_id="Your Nation ID (numbers only, e.g., 365325)")
async def register(interaction: discord.Interaction, nation_id: str):
    await interaction.response.defer()
    MEMBER_ROLE = get_member_role(interaction)
    # Custom permission check
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

    # Check nation existence and discord username
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
    guild_id = str(interaction.guild.id)

    # FORCE reload current guild data to clear any stale cache
    print(f"🔄 Force reloading data for guild {guild_id}")
    load_sheet_data(guild_id)

    # Sumnor bypasses username check
    if user_discord_username != "sumnor":
        if nation_discord_username != user_discord_username:
            await interaction.followup.send(
                f"❌ Username mismatch.\nNation lists: `{nation_discord_username}`\nYour Discord: `{user_discord_username}`"
            )
            return

    # Check for duplicates in cached users for THIS SPECIFIC GUILD
    users_in_guild = cached_users.get(guild_id, {})
    print(f"🔍 Checking duplicates in guild {guild_id}")
    print(f"📊 Current users in guild cache: {len(users_in_guild)}")
    print(f"👤 User ID: {user_id}, Username: {user_discord_username}, Nation: {nation_id_str}")

    # Debug: Show what's in the cache
    for uid, data in users_in_guild.items():
        print(f"  - Cached: ID={uid}, Username={data.get('DiscordUsername')}, Nation={data.get('NationID')}")

    for uid, data in users_in_guild.items():
        if user_discord_username != "sumnor":  # Sumnor can always register
            if uid == user_id:
                await interaction.followup.send(f"❌ This Discord ID ({user_id}) is already registered in this server.")
                return
            if data.get('DiscordUsername', '').lower() == user_discord_username:
                await interaction.followup.send(f"❌ This Discord username ({user_discord_username}) is already registered in this server.")
                return
            if data.get('NationID') == nation_id_str:
                await interaction.followup.send(f"❌ This Nation ID ({nation_id_str}) is already registered in this server.")
                return

    # Save to correct guild-specific sheet
    try:
        sheet = get_registration_sheet(guild_id)
        sheet.append_row([interaction.user.name, user_id, nation_id])
        print(f"📝 Added registration for {interaction.user.name} (ID: {user_id}) in guild {guild_id}")
    except Exception as e:
        await interaction.followup.send(f"❌ Failed to write registration: {e}")
        return

    # Reload cached data after update for this specific guild
    try:
        load_sheet_data(guild_id)
        print(f"✅ Reloaded cache after registration")
    except Exception as e:
        print(f"⚠️ Failed to reload cached sheet data for guild {guild_id}: {e}")

    await interaction.followup.send("✅ You're registered successfully in this server!")

# Add a debug command to clear cache manually
@bot.tree.command(name="clear_cache", description="Clear registration cache (Admin only)")
async def clear_cache(interaction: discord.Interaction):
    await interaction.response.defer()
    if not (interaction.user.guild_permissions.administrator or str(interaction.user.id) == "1148678095176474678"):
        await interaction.followup.send("❌ You need admin permissions to clear cache.", ephemeral=True)
        return

    guild_id = str(interaction.guild.id)
    global cached_users, cached_registrations
    
    # Clear guild-specific cache
    if guild_id in cached_users:
        del cached_users[guild_id]
    if guild_id in cached_registrations:
        del cached_registrations[guild_id]
    
    # Force reload
    load_sheet_data(guild_id)
    
    await interaction.followup.send(f"✅ Cache cleared and reloaded for this server!", ephemeral=True)

@bot.tree.command(name="register_server_aa", description="Register this server and create Google Sheets")
#@app_commands.checks.has_permissions(administrator=True)
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

        intra_title = f"{server_id}_Registrations"
        intra_headers = ["DiscordUsername", "DiscordID", "NationID", "Lotto Dates", "LotteryNumbers"]
        intra_spreadsheet = client.create(intra_title)
        intra_ws = intra_spreadsheet.get_worksheet(0)
        intra_ws.update_title("Registrations")
        intra_ws.append_row(intra_headers)
        intra_spreadsheet.share(share_email, perm_type="user", role="writer")
        intra_spreadsheet.share(sum_email, perm_type="user", role="writer")

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
            f"- `{intra_title}`\n"
            f"- `{alliance_title}`\n"
            f"- `{auto_title}`"
        )

    except Exception as e:
        await interaction.followup.send(f"❌ Failed to create sheets: {e}", ephemeral=True)

SETTING_CHOICES = [
    app_commands.Choice(name="GRANT_REQUEST_CHANNEL_ID", value="GRANT_REQUEST_CHANNEL_ID"),
    app_commands.Choice(name="WARN_CHANNEL", value="WARN_CHANNEL"),
    app_commands.Choice(name="GOV_ROLE", value="GOV_ROLE"),
    app_commands.Choice(name="API_KEY", value="API_KEY"),
    app_commands.Choice(name="LOGS", value="LOGS"),
    app_commands.Choice(name="MEMBER_ROLE", value="MEMBER_ROLE"),
]

@bot.tree.command(name="set_setting", description="Set a server setting (e.g. GRANT_REQUEST_CHANNEL_ID).")
@app_commands.describe(key="The setting key", value="The value to store")
@app_commands.choices(key=SETTING_CHOICES)
async def set_setting(interaction: discord.Interaction, key: app_commands.Choice[str], value: str):
    await interaction.response.defer(ephemeral=True)

    guild = interaction.guild
    guild_id = interaction.guild_id
    if guild is None or guild_id is None:
        await interaction.followup.send("❌ This command can only be used in a server.", ephemeral=True)
        return

    gov_role_id = get_gov_role(interaction)  # Implemented elsewhere
    member = await guild.fetch_member(interaction.user.id)

    if gov_role_id is None:
        set_server_setting(guild_id, key.value, value)
        await interaction.followup.send(f"✅ GOV_ROLE set to `{value}`.", ephemeral=True)
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
    if key.lower() == "api key":
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

@bot.tree.command(name="res_details_for_alliance", description="Get each Alliance Member's resources and money individually")
async def res_details_for_alliance(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True)
    guild_id = str(interaction.guild.id)

    sheet = get_registration_sheet(guild_id)
    rows = sheet.get_all_records()
    user_id = str(interaction.user.id)
    
    
    user_data = next(
        (r for r in rows if str(r.get("DiscordID", "")).strip() == user_id),
        None
    )
    
    user_id = str(interaction.user.id)

    user_data = cached_users.get(guild_id, {}).get(user_id)
    if not user_data:
        await interaction.followup.send(
            "❌ You are not registered. Please register first.", ephemeral=True
        )
        return
    
    own_id = str(user_data.get("NationID", "")).strip()
    
    if not own_id:
        await interaction.followup.send("❌ Could not find your Nation ID in the sheet.")
        return
    
    async def is_banker(interaction):
        GOV_ROLE = get_gov_role(interaction)
        print(GOV_ROLE)
        return (
            any(role.name == GOV_ROLE for role in interaction.user.roles)
        )
    
    if not await is_banker(interaction):
        await interaction.followup.send("❌ You don't have the rights, lil bro.")
        return
    
    lines = []
    processed_nations = 0
    processed = []
    failed_nations = []
    failed = 0
    
    totals = {
        "money": 0,
        "food": 0,
        "gasoline": 0,
        "munitions": 0,
        "steel": 0,
        "aluminum": 0,
        "bauxite": 0,
        "lead": 0,
        "iron": 0,
        "oil": 0,
        "coal": 0,
        "uranium": 0,
        "num_cities": 0,
    }
    batch_count = 0
    for row in rows:
        nation_id = str(row.get("NationID", "")).strip()
        row_user_id = str(row.get("DiscordID", "")).strip()

        try:
            result = get_resources(nation_id, interaction)
            if len(result) != 14:
                raise ValueError("Invalid result length from get_resources")

            (
                nation_name,
                num_cities,
                food,
                money,
                gasoline,
                munitions,
                steel,
                aluminum,
                bauxite,
                lead,
                iron,
                oil,
                coal,
                uranium
            ) = result

            totals["money"] += money
            totals["food"] += food
            totals["gasoline"] += gasoline
            totals["munitions"] += munitions
            totals["steel"] += steel
            totals["aluminum"] += aluminum
            totals["bauxite"] += bauxite
            totals["lead"] += lead
            totals["iron"] += iron
            totals["oil"] += oil
            totals["coal"] += coal
            totals["uranium"] += uranium
            totals["num_cities"] += num_cities
            processed_nations += 1
            processed.append(nation_id)

            lines.append(
                f"{nation_name} (ID: {nation_id}): Cities={num_cities}, Money=${money:,}, "
                f"Food={food:,}, Gasoline={gasoline:,}, Munitions={munitions:,}, "
                f"Steel={steel:,}, Aluminum={aluminum:,}, Bauxite={bauxite:,}, "
                f"Lead={lead:,}, Iron={iron:,}, Oil={oil:,}, Coal={coal:,}, Uranium={uranium:,}"
            )
            batch_count += 1

            if batch_count == 30:
                await asyncio.sleep(35)
                batch_count = 0

        except Exception as e:
            print(f"Failed processing nation {nation_id}: {e}")
            failed += 1
            failed_nations.append(nation_id)
            continue

    total_resources_line = (
        f"\nAlliance totals - Nations counted: {processed_nations}, Failed: {failed}\n"
        f"Total Cities: {totals['num_cities']:,}\n"
        f"Money: ${totals['money']:,}\n"
        f"Food: {totals['food']:,}\n"
        f"Gasoline: {totals['gasoline']:,}\n"
        f"Munitions: {totals['munitions']:,}\n"
        f"Steel: {totals['steel']:,}\n"
        f"Aluminum: {totals['aluminum']:,}\n"
        f"Bauxite: {totals['bauxite']:,}\n"
        f"Lead: {totals['lead']:,}\n"
        f"Iron: {totals['iron']:,}\n"
        f"Oil: {totals['oil']:,}\n"
        f"Coal: {totals['coal']:,}\n"
        f"Uranium: {totals['uranium']:,}\n"
    )

    text_content = "\n".join(lines) + total_resources_line
    

    embed = discord.Embed(
        title="Alliance Members' Resources and Money (Detailed)",
        description=f"Nations counted: **{processed_nations}**\nFailed to retrieve data for: **{failed}**\n**FAILED: {failed_nations}\n**SUCCESS: {processed}",
        colour=discord.Colour.dark_magenta()
    )

    image_url = "https://i.ibb.co/qJygzr7/Leonardo-Phoenix-A-dazzling-star-emits-white-to-bluish-light-s-2.jpg"
    embed.set_footer(text=f"Brought to you by Darkstar", icon_url=image_url)
    try:
        await interaction.followup.send(embed=embed,  file=discord.File(io.StringIO(text_content), filename="alliance_resources.txt"))
    except Exception as e:
        print(f"Error sending detailed resources file: {e}")
        await interaction.followup.send(embed=embed)

import asyncio
import io
import requests
import discord
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from matplotlib.ticker import FuncFormatter, MaxNLocator
import asyncio
import discord
from discord import app_commands
from datetime import datetime, timezone
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.ticker import FuncFormatter
import io
import pandas as pd  
import requests
'''
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options

@bot.tree.command(name="check_site", description="Check for messages and buttons on a site.")
async def check_site(interaction: discord.Interaction):
    await interaction.response.defer()

    options = Options()
    options.add_argument("--headless")  
    options.add_argument("user-agent=Mozilla/5.0")  
    driver = webdriver.Chrome(options=options)

    results = []

    try:
        driver.get("https://politicsandwar.com/obl/host/")
        page_text = driver.page_source.lower()

        if "login" in page_text:
            results.append("Login requested")

        if "are you a robot?" in page_text:
            try:
                driver.switch_to.frame(driver.find_element(By.XPATH, "//iframe[contains(@src, 'recaptcha')]"))
                checkbox = driver.find_element(By.ID, "recaptcha-anchor")
                checkbox.click()
                driver.switch_to.default_content()
                results.append("Clicked 'I'm not a robot'")
            except:
                results.append("CAPTCHA interaction failed")

        try:
            host_div = driver.find_element(By.XPATH, "//div[@class='columnheader' and contains(text(), 'Host Home Game')]")
            host_div.click()
            results.append("Clicked 'Host Home Game'")
        except:
            results.append("'Host Home Game' not found")

        await interaction.followup.send("\n".join(results))

    except Exception as e:
        await interaction.followup.send(f"Error occurred: {e}")
    finally:
        driver.quit()
        '''

@bot.tree.command(name="auto_week_summary", description="See the total materials which are requested for this week")
async def auto_week_summary(interaction: discord.Interaction):
    await interaction.response.defer()
    try:
        sheet = get_auto_requests_sheet(interaction.guild.id)
        all_rows = await asyncio.to_thread(sheet.get_all_values)

        if not all_rows or len(all_rows) < 2:
            await interaction.followup.send("No data available.", ephemeral=True)
            return

        header = all_rows[0]
        col_index = {col: idx for idx, col in enumerate(header)}
        rows = all_rows[1:]

        total_week = {res: 0 for res in ["Coal", "Oil", "Bauxite", "Lead", "Iron"]}

        for row in rows:
            if not any(row):  
                continue
            try:
                time_period = float(row[col_index["TimePeriod"]]) if row[col_index["TimePeriod"]] else 1
                if time_period <= 0:
                    continue

                for res in total_week:
                    val_str = row[col_index[res]].strip()
                    amount = float(val_str) if val_str else 0
                    per_day = amount / time_period
                    total_week[res] += per_day * 5  
            except Exception as row_ex:
                print(f"Skipping row due to error: {row_ex}")
                continue

        formatted = [f"{emoji} **{res}**: {int(amount):,}".replace(",", ".") for res, emoji, amount in zip(
            ["Coal", "Oil", "Bauxite", "Lead", "Iron"],
            ["🪨", "🛢️", "🟤", "🪫", "⛓️"],
            total_week.values()
        )]

        embed = discord.Embed(
            title="📦 Auto-Requested Weekly Summary",
            description="\n".join(formatted),
            color=discord.Color.blue()
        )
        embed.set_footer(text="Calculated from current auto-request data")

        await interaction.followup.send(embed=embed)

    except Exception as e:
        print(f"Error in /auto_week_summary: {e}")
        await interaction.followup.send("❌ Error generating summary.", ephemeral=True)

def get_prices(guild_id):
    API_KEY = get_api_key_for_guild(guild_id)
    if not API_KEY:
        raise ValueError("API key not found for this guild.")

    GRAPHQL_URL = f"https://api.politicsandwar.com/graphql?api_key={API_KEY}"
    prices_query = """
    {
      top_trade_info {
        resources {
          resource
          average_price
        }
      }
    }
    """
    try:
        response = requests.post(
            GRAPHQL_URL,
            json={"query": prices_query},
            headers={"Content-Type": "application/json"}
        )
        return response.json()
    except Exception as e:
        print(f"Error fetching resource prices: {e}")
        raise


@bot.tree.command(name="res_in_m_for_a", description="Get total Alliance Members' resources and money")
@app_commands.describe(
    mode="Group data by time unit",
    scale="Scale for Y-axis (Millions or Billions)"
)
@app_commands.choices(
    mode=[
        app_commands.Choice(name="Hourly", value="hours"),
        app_commands.Choice(name="Daily", value="days")
    ],
    scale=[
        app_commands.Choice(name="Millions", value="millions"),
        app_commands.Choice(name="Billions", value="billions")
    ]
)
async def res_in_m_for_a(
    interaction: discord.Interaction,
    mode: app_commands.Choice[str] = None,
    scale: app_commands.Choice[str] = None
):
    await interaction.response.defer()
    global money_snapshots
    user_id = str(interaction.user.id)
    
    global cached_users  
    
    guild_id = str(interaction.guild.id)
    user_id = str(interaction.user.id)

    user_data = cached_users.get(guild_id, {}).get(user_id)
    if not user_data:
        await interaction.followup.send(
            "❌ You are not registered. Please register first.", ephemeral=True
        )
        return
    
    own_id = str(user_data.get("NationID", "")).strip()

    if not own_id:
            await interaction.followup.send("❌ Could not find your Nation ID in the sheet.")
            return
    
    async def is_banker(interaction):
        GOV_ROLE = get_gov_role(interaction)
        return (
            any(role.name == GOV_ROLE for role in interaction.user.roles)
        )

    if not await is_banker(interaction):
        await interaction.followup.send("❌ You don't have the rights, lil bro.")
        return

    totals = {
        "money": 0,
        "food": 0,
        "gasoline": 0,
        "munitions": 0,
        "steel": 0,
        "aluminum": 0,
        "bauxite": 0,
        "lead": 0,
        "iron": 0,
        "oil": 0,
        "coal": 0,
        "uranium": 0,
        "num_cities": 0,
    }

    processed_nations = 0
    failed = 0
    API_KEY = get_api_key_for_interaction(interaction)
    GRAPHQL_URL = f"https://api.politicsandwar.com/graphql?api_key={API_KEY}"
    prices_query = """
    {
      top_trade_info {
        resources {
          resource
          average_price
        }
      }
    }
    """
    resource_prices = {}
    try:
        response = requests.post(
            GRAPHQL_URL,
            json={"query": prices_query},
            headers={"Content-Type": "application/json"}
        )
        data = response.json()
        for item in data["data"]["top_trade_info"]["resources"]:
            resource_prices[item["resource"]] = float(item["average_price"])
    except Exception as e:
        print(f"Error fetching resource prices: {e}")

    sheet = get_registration_sheet(guild_id)
    rows = sheet.get_all_records()
    batch_count = 0

    for row in rows:
        nation_id = str(row.get("NationID", "")).strip()
        user_id = str(row.get("DiscordID", "")).strip()

        try:
            result = get_resources(nation_id, interaction)
            if len(result) != 14:
                raise ValueError("Invalid result length from get_resources")

            (
                nation_name,
                num_cities,
                food,
                money,
                gasoline,
                munitions,
                steel,
                aluminum,
                bauxite,
                lead,
                iron,
                oil,
                coal,
                uranium
            ) = result

            totals["money"] += money
            totals["food"] += food
            totals["gasoline"] += gasoline
            totals["munitions"] += munitions
            totals["steel"] += steel
            totals["aluminum"] += aluminum
            totals["bauxite"] += bauxite
            totals["lead"] += lead
            totals["iron"] += iron
            totals["oil"] += oil
            totals["coal"] += coal
            totals["uranium"] += uranium
            totals["num_cities"] += num_cities
            processed_nations += 1
            batch_count += 1
            if batch_count == 30:
                await asyncio.sleep(32)
                batch_count = 0

        except Exception as e:
            print(f"Failed processing nation {nation_id}: {e}")
            failed += 1
            continue

    total_sell_value = totals["money"]
    for resource in [
        "food", "gasoline", "munitions", "steel", "aluminum",
        "bauxite", "lead", "iron", "oil", "coal", "uranium"
    ]:
        amount = totals.get(resource, 0)
        price = resource_prices.get(resource, 0)
        total_sell_value += amount * price

    embed = discord.Embed(
        title="Alliance Total Resources & Money",
        colour=discord.Colour.dark_magenta()
    )
    embed.description = (
        f"🧮 Nations counted: **{processed_nations}**\n"
        f"⚠️ Failed to retrieve data for: **{failed}**\n\n"
        f"🌆 Total Cities: **{totals['num_cities']:,}**\n"
        f"💰 Money: **${totals['money']:,}**\n"
        f"🍞 Food: **{totals['food']:,}**\n"
        f"⛽ Gasoline: **{totals['gasoline']:,}**\n"
        f"💣 Munitions: **{totals['munitions']:,}**\n"
        f"🏗️ Steel: **{totals['steel']:,}**\n"
        f"🧱 Aluminum: **{totals['aluminum']:,}**\n"
        f"🪨 Bauxite: **{totals['bauxite']:,}**\n"
        f"🧪 Lead: **{totals['lead']:,}**\n"
        f"⚙️ Iron: **{totals['iron']:,}**\n"
        f"🛢️ Oil: **{totals['oil']:,}**\n"
        f"🏭 Coal: **{totals['coal']:,}**\n"
        f"☢️ Uranium: **{totals['uranium']:,}**\n\n"
        f"💸 Total Money if all was sold: **${total_sell_value:,.2f}**"
    )

    try:
        sheet = get_alliance_sheet(guild_id)
        rows = sheet.get_all_records()

        df = pd.DataFrame(rows)
        df.columns = [col.strip() for col in df.columns]

        
        df["TimeT"] = pd.to_datetime(df["TimeT"], errors='coerce', utc=True)
        df = df.dropna(subset=["TimeT"])

        resource_cols = [
            "Money", "Food", "Gasoline", "Munitions", "Steel", "Aluminum",
            "Bauxite", "Lead", "Iron", "Oil", "Coal", "Uranium"
        ]

        color_map = {
            "Money": "#1f77b4",
            "Food": "#ff7f0e",
            "Gasoline": "#2ca02c",
            "Munitions": "#d62728",
            "Steel": "#9467bd",
            "Aluminum": "#8c564b",
            "Bauxite": "#e377c2",
            "Lead": "#7f7f7f",
            "Iron": "#bcbd22",
            "Oil": "#17becf",
            "Coal": "#aec7e8",
            "Uranium": "#ffbb78"
        }
        resource_cols = [col for col in resource_cols if col in df.columns]

        
        for col in resource_cols:
            df[col] = (
                df[col]
                .astype(str)
                .str.replace(",", ".", regex=False)
                .str.replace(" ", "", regex=False)
                .str.replace(u"\u00A0", "", regex=False)
                .str.extract(r"([\d.]+)", expand=False)
                .astype(float)
            )

        
        df["TotalMoney"] = (
            df["TotalMoney"]
            .astype(str)
            .str.replace(",", ".", regex=False)
            .str.replace(" ", "", regex=False)
            .str.replace(u"\u00A0", "", regex=False)
            .str.extract(r"([\d.]+)", expand=False)
            .astype(float)
        )
        df["Total"] = df["TotalMoney"]

        
        df = df.sort_values("TimeT").set_index("TimeT")

        if mode and mode.value.lower() == "days":
            df = df.resample("d").mean().interpolate()
            df = df[df.index >= (df.index.max() - pd.Timedelta(days=7))]
        else:
            df = df.resample("h").max().interpolate()
            df = df[df.index >= (df.index.max() - pd.Timedelta(hours=24))]
        
        df = df.reset_index()


    except Exception as e:
        print(f"Failed loading/parsing sheet data for graph: {e}")
        await interaction.followup.send(embed=embed)
        return

    
    try:
        value_scale = scale.value if scale else "millions"
        divisor = {"billions": 1e9, "millions": 1e6}.get(value_scale, 1)
        label_suffix = {"billions": "B", "millions": "M"}.get(value_scale, "")

        def format_yaxis(value, pos):
            return f"{value:,.2f}{label_suffix}"

        plt.style.use("ggplot")
        fig, ax = plt.subplots(figsize=(13, 8))

        times = df["TimeT"]

        for resource in resource_cols:
            ax.plot(times, df[resource] / divisor, label=resource, color=color_map[resource])

        if mode and mode.value.lower() == "days":
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%d-%m"))
            ax.set_xlim(times.min(), times.max())
            ax.xaxis.set_major_locator(mdates.DayLocator())
        else:
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
            ax.set_xlim(times.min(), times.max())
            ax.xaxis.set_major_locator(mdates.HourLocator(interval=2))
            plt.setp(ax.get_xticklabels(), rotation=30, ha='right')

        ax.set_xlim(times.min(), times.max())
        ax.yaxis.set_major_formatter(FuncFormatter(format_yaxis))
        ax.set_ylabel(f"Resources ({label_suffix})")
        ax.set_title("Alliance Resources Over Time")
        ax.legend(loc="upper left", fontsize=8, frameon=False, ncols=len(resource_cols))
        plt.tight_layout()
        plt.grid(False)

        ax_total = ax.twinx()
        ax_total.plot(times, df["Total"] / divisor, label="Total", color="black", linewidth=3)
        ax_total.yaxis.set_major_formatter(FuncFormatter(format_yaxis))

        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=150)
        plt.close(fig)
        buf.seek(0)

        image_url = "https://i.ibb.co/qJygzr7/Leonardo-Phoenix-A-dazzling-star-emits-white-to-bluish-light-s-2.jpg"
        embed.set_footer(text=f"Brought to you by Darkstar", icon_url=image_url)
        await interaction.followup.send(embed=embed, file=discord.File(fp=buf, filename="resources_graph.png"))

    except Exception as e:
        print(f"Failed to generate or send graph: {e}")
        await interaction.followup.send(embed=embed)

@bot.tree.command(name="member_activity", description="Shows the activity of our members")
async def member_activity(interaction: discord.Interaction):
    await interaction.response.defer()
    user_id = str(interaction.user.id)

    global cached_users

    guild_id = str(interaction.guild.id)
    user_data = cached_users.get(guild_id, {}).get(str(interaction.user.id))

    guild_id = str(interaction.guild.id)
    user_id = str(interaction.user.id)

    user_data = cached_users.get(guild_id, {}).get(user_id)
    if not user_data:
        await interaction.followup.send(
            "❌ You are not registered. Please register first.", ephemeral=True
        )
        return

    own_id = str(user_data.get("NationID", "")).strip()

    if not own_id:
        await interaction.followup.send("❌ Could not find your Nation ID in the sheet.")
        return

    async def is_banker(interaction):
        GOV_ROLE = get_gov_role(interaction)
        return (
            any(role.name == GOV_ROLE for role in interaction.user.roles)
        )

    if not await is_banker(interaction):
        await interaction.followup.send("❌ You don't have the rights, lil bro.")
        return

    activish = 0
    activish_wo_bloc = 0
    active_w_bloc = 0
    active_wo_bloc = 0
    inactive = 0
    activish_list = []
    activish_wo_bloc_list = []
    active_w_bloc_list = []
    active_wo_bloc_list = []
    inactive_list = []

    try:
        sheet = get_registration_sheet()
        rows = sheet.get_all_records()
        df = pd.DataFrame(rows)
        df.columns = [col.strip() for col in df.columns]
        nation_ids = df["NationID"].dropna().astype(int).tolist()
    except Exception as e:
        await interaction.followup.send(f"❌ Error loading Nation IDs: {e}")
        return

    for own_id in nation_ids:
        try:
            military_data = get_military(own_id, interaction)
            nation_name = military_data[0]
            nation_leader = military_data[1]
            score = military_data[2]
            result = get_general_data(own_id, interaction)
            if result is None or len(result) < 7:
                print(f"Missing data for nation {own_id}")
                continue

            alliance_id, alliance_position, alliance, domestic_policy, num_cities, colour, activity, *_ = result

            try:
                activity_dt = datetime.fromisoformat(activity)
            except (ValueError, TypeError):
                print(f"Invalid activity date for nation {own_id}: {activity}")
                continue

            now = datetime.now(timezone.utc)
            delta = now - activity_dt
            days_inactive = delta.total_seconds() / 86400

            if days_inactive >= 2:
                inactive += 1
                inactive_list.append(f"Nation: {nation_name}(ID: `{own_id}`), Leader: {nation_leader}, Bloc: {colour}, Score: {score}\n")
            elif days_inactive >= 1:
                if colour.lower() == "olive":
                    activish += 1
                    activish_list.append(f"Nation: {nation_name}(ID: `{own_id}`), Leader: {nation_leader}, Bloc: {colour}, Score: {score}\n")
                else:
                    activish_wo_bloc += 1
                    activish_wo_bloc_list.append(f"Nation: {nation_name}(ID: `{own_id}`), Leader: {nation_leader}, Bloc: {colour}, Score: {score}\n")
            else:
                if colour.lower() == "olive":
                    active_w_bloc += 1
                    active_w_bloc_list.append(f"Nation: {nation_name}(ID: `{own_id}`), Leader: {nation_leader}, Bloc: {colour}, Score: {score}\n")
                else:
                    active_wo_bloc += 1
                    active_wo_bloc_list.append(f"Nation: {nation_name}(ID: `{own_id}`), Leader: {nation_leader}, Bloc: {colour}, Score: {score}\n")
            await asyncio.sleep(3)
        except Exception as e:
            print(f"Error processing nation ID {own_id}: {e}")
            continue

    data = [active_w_bloc, active_wo_bloc, activish, activish_wo_bloc, inactive]

    if sum(data) == 0:
        await interaction.followup.send("⚠️ No activity data available to generate chart.")
        return

    
    fig, ax = plt.subplots(figsize=(8, 4), subplot_kw=dict(aspect="equal"))

    labels = [
        "Active (Correct Bloc)",
        "Active (Wrong Bloc)",
        "Activish (Correct Bloc, 1-2 Days)",
        "Activish (Wrong Bloc, 1-2 Days)",
        "Inactive (2+ Days)"
    ]

    def func(pct, allvals):
        absolute = int(np.round(pct / 100. * np.sum(allvals)))
        return f"{pct:.1f}%\n({absolute})"

    wedges, texts, autotexts = ax.pie(data, autopct=lambda pct: func(pct, data), textprops=dict(color="w"))

    ax.legend(wedges, labels,
              title="DS Member Statuses",
              loc="center left",
              bbox_to_anchor=(1, 0, 0.5, 1))

    plt.setp(autotexts, size=8, weight="bold")
    ax.set_title("DS Activity Chart")

    buffer = BytesIO()
    plt.savefig(buffer, format="png")
    buffer.seek(0)
    file = discord.File(fp=buffer, filename="ds_activity.png")

    embed = discord.Embed(
        title="📊 DS Activity",
        description="Here are the members not in ideal status categories:",
        color=discord.Color.dark_teal()
    )

    def add_field_chunks(embed, title, lines):
        if not lines:
            return
        current = ""
        for i, line in enumerate(lines):
            if len(current) + len(line) > 1024:
                embed.add_field(name=title if i == 0 else f"{title} (cont.)", value=current, inline=False)
                current = line
            else:
                current += line
        if current:
            embed.add_field(name=title if not embed.fields or embed.fields[-1].name != title else f"{title} (cont.)", value=current, inline=False)

    add_field_chunks(embed, "Active (Wrong Bloc)", active_wo_bloc_list)
    add_field_chunks(embed, "Activish (Correct Bloc)", activish_list)
    add_field_chunks(embed, "Activish (Wrong Bloc)", activish_wo_bloc_list)
    add_field_chunks(embed, "Inactive", inactive_list)

    image_url = "https://i.ibb.co/qJygzr7/Leonardo-Phoenix-A-dazzling-star-emits-white-to-bluish-light-s-2.jpg"
    embed.set_footer(text=f"Brought to you by Darkstar", icon_url=image_url)
    embed.set_image(url="attachment://ds_activity.png")

    await interaction.followup.send(embed=embed, file=file)



import discord
import requests
from io import BytesIO
import matplotlib.pyplot as plt
from collections import defaultdict
from datetime import datetime
from matplotlib.dates import DateFormatter
import matplotlib.dates as mdates

@bot.tree.command(name="war_losses", description="Show recent wars for a nation with optional detailed stats.")
@app_commands.describe(
    nation_id="Nation ID",
    detail="Optional detail to show: infra, money, soldiers",
    wars_count="Number of wars to fetch (default 30)"
)
@app_commands.choices(detail=[
    app_commands.Choice(name="infra", value="infra"),
    app_commands.Choice(name="soldiers", value="soldiers"),
])
async def war_losses(interaction: discord.Interaction, nation_id: int, detail: str = None, wars_count: int = 30):
    await interaction.response.defer()

    import requests
    from collections import defaultdict
    from datetime import datetime
    import matplotlib.pyplot as plt
    from io import BytesIO
    import discord
    user_id = str(interaction.user.id)
    
    global cached_users  
    
    guild_id = str(interaction.guild.id)
    user_data = cached_users.get(guild_id, {}).get(str(interaction.user.id))

    
    guild_id = str(interaction.guild.id)
    user_id = str(interaction.user.id)

    user_data = cached_users.get(guild_id, {}).get(user_id)
    if not user_data:
        await interaction.followup.send(
            "❌ You are not registered. Please register first.", ephemeral=True
        )
        return
    
    own_id = str(user_data.get("NationID", "")).strip()

    if not own_id:
            await interaction.followup.send("❌ Could not find your Nation ID in the sheet.")
            return
    API_KEY = get_api_key_for_interaction(interaction)
    GRAPHQL_URL = f"https://api.politicsandwar.com/graphql?api_key={API_KEY}"

    query = """
    query (
      $nation_id: [Int], 
      $first: Int, 
      $page: Int, 
      $orderBy: [QueryWarsOrderByOrderByClause!], 
      $active: Boolean
    ) {
      wars(
        nation_id: $nation_id, 
        first: $first, 
        page: $page, 
        orderBy: $orderBy,
        active: $active
      ) {
        data {
          id
          date
          end_date
          reason
          war_type
          winner_id
          attacker {
            id
            nation_name
          }
          defender {
            id
            nation_name
          }
          att_infra_destroyed
          def_infra_destroyed
          att_money_looted
          def_money_looted
          def_soldiers_lost
          att_soldiers_lost
        }
      }
    }
    """

    variables = {
        "nation_id": [nation_id],
        "first": wars_count,
        "page": 1,
        "orderBy": [{"column": "ID", "order": "DESC"}],
        "active": False,
    }

    headers = {"Content-Type": "application/json"}

    try:
        response = requests.post(GRAPHQL_URL, json={"query": query, "variables": variables}, headers=headers)
        response.raise_for_status()
    except requests.RequestException as e:
        await interaction.followup.send(f"Error fetching data: {e}")
        return

    result = response.json()
    if "errors" in result:
        await interaction.followup.send(f"API errors: {result['errors']}")
        return

    wars = result.get("data", {}).get("wars", {}).get("data", [])
    if not wars:
        await interaction.followup.send("No wars found for this nation.")
        return

    all_log = ""
    war_results = []
    money_per_war = []

    for war in wars:
        war_id = war.get("id")
        winner_id = str(war.get("winner_id", "0"))

        attacker = war.get("attacker") or {}
        defender = war.get("defender") or {}

        atk_id = str(attacker.get("id", "0"))
        def_id = str(defender.get("id", "0"))
        atk_name = attacker.get("nation_name", "Unknown")
        def_name = defender.get("nation_name", "Unknown")
        nation_id_str = str(nation_id)

        
        if winner_id == nation_id_str:
            outcome_val = 1
            outcome = "Win"
        elif winner_id in [atk_id, def_id] and winner_id != nation_id_str:
            outcome_val = -1
            outcome = "Loss"
        else:
            outcome_val = 0
            outcome = "Draw"

        war_results.append(outcome_val)
        money = war.get("att_money_looted", 0) + war.get("def_money_looted", 0)
        money_per_war.append(money)

        line = f"War ID: {war_id} | Attacker: {atk_name} | Defender: {def_name} | Outcome: {outcome}"
        if detail == "infra":
            line += f" | Infra Destroyed - Att: {war.get('att_infra_destroyed', 0)}, Def: {war.get('def_infra_destroyed', 0)}"
        elif detail == "money":
            line += f" | Money Looted - Att: {war.get('att_money_looted', 0)}, Def: {war.get('def_money_looted', 0)}"
        elif detail == "soldiers":
            line += f" | Soldiers Lost - Att: {war.get('att_soldiers_lost', 0)}, Def: {war.get('def_soldiers_lost', 0)}"

        all_log += line + "\n"

    
    indices = list(range(1, len(war_results) + 1))
    looted_millions = [m / 1_000_000 for m in money_per_war]

    fig, ax1 = plt.subplots(figsize=(10, 5))
    ax1.bar(indices, looted_millions, width=0.6, color="red", label="Money Looted (M)", zorder=2)
    ax1.set_ylabel("Money ($M)")
    ax1.set_xlabel("War Index")
    ax1.set_xticks(indices)

    ax2 = ax1.twinx()
    ax2.plot(indices, war_results, color="blue", marker="o", label="Outcome", zorder=3)
    ax2.set_ylabel("Outcome")
    ax2.set_yticks([-1, 0, 1])
    ax2.set_yticklabels(["Loss", "Draw", "Win"])

    
    ax2.axhline(y=1, color="green", linestyle="--", linewidth=1, label="Win")
    ax2.axhline(y=0, color="gray", linestyle="--", linewidth=1, label="Draw")
    ax2.axhline(y=-1, color="red", linestyle="--", linewidth=1, label="Loss")

    ax1.set_xlim(0.5, len(indices) + 0.5)
    ax1.legend(loc="upper left")
    ax2.legend(loc="upper right")
    plt.title(f"Nation {nation_id} War Outcomes & Money Looted")
    plt.tight_layout()

    buf = BytesIO()
    plt.savefig(buf, format="png")
    plt.close()
    buf.seek(0)
    txt_buffer = BytesIO(all_log.encode("utf-8"))
    txt_buffer.seek(0)

    await interaction.followup.send(
        file=discord.File(buf, filename="combined_war_graph.png"),
        content=f"Combined War Outcome & Money Graph for Nation {nation_id}"
    )
    file=discord.File(txt_buffer, filename=f"nation_{nation_id}_wars_summary.txt")
    embed = discord.Embed(
        title="War Results:",
        colour=discord.Colour.dark_orange(),
        description=(file)
    )
    image_url = "https://i.ibb.co/qJygzr7/Leonardo-Phoenix-A-dazzling-star-emits-white-to-bluish-light-s-2.jpg"
    embed.set_footer(text=f"Brought to you by Darkstar", icon_url=image_url)
    
    await interaction.followup.send(embed=embed, file=discord.File(txt_buffer, filename=f"nation_{nation_id}_wars_summary.txt"))






from datetime import datetime, date
from collections import defaultdict
import matplotlib.pyplot as plt
from matplotlib.dates import DateFormatter
import matplotlib.dates as mdates
from io import BytesIO
import discord
import requests
from discord import app_commands
from dateutil import parser
import matplotlib.dates as mdates

@bot.tree.command(name="war_losses_alliance", description="Show recent wars for an alliance with optional detailed stats and conflict mode.")
@app_commands.describe(
    alliance_id="Alliance ID",
    war_count="Number of recent wars to display (default 30)",
    money_more_detail="Set to true to show detailed money and outcome graphs (default false)"
)
async def war_losses_alliance(interaction: discord.Interaction, alliance_id: int, war_count: int = 30, money_more_detail: bool = False):
    await interaction.response.defer()
    
    user_id = str(interaction.user.id)
    global cached_users
    guild_id = str(interaction.guild.id)
    user_data = cached_users.get(guild_id, {}).get(str(interaction.user.id))
    
    guild_id = str(interaction.guild.id)
    user_id = str(interaction.user.id)

    user_data = cached_users.get(guild_id, {}).get(user_id)
    if not user_data:
        await interaction.followup.send(
            "❌ You are not registered. Please register first.", ephemeral=True
        )
        return
    
    own_id = str(user_data.get("NationID", "")).strip()
    if not own_id:
        await interaction.followup.send("❌ Could not find your Nation ID in the sheet.")
        return

    API_KEY = get_api_key_for_interaction(interaction)
    GRAPHQL_URL = f"https://api.politicsandwar.com/graphql?api_key={API_KEY}"
    orderBy = [{"column": "ID", "order": "DESC"}]

    query = """ query ( $id: [Int], $limit: Int, $orderBy: [AllianceWarsOrderByOrderByClause!] ) {
        alliances(id: $id) {
            data {
                id
                name
                wars(limit: $limit, orderBy: $orderBy) {
                    id
                    date
                    end_date
                    reason
                    war_type
                    winner_id
                    attacker { nation_name id alliance_id }
                    defender { nation_name id alliance_id }
                    att_infra_destroyed
                    def_infra_destroyed
                    def_soldiers_lost
                    att_soldiers_lost
                    att_money_looted
                    def_money_looted
                    attacks { money_stolen }
                }
            }
        }
    }"""

    variables = {"id": [alliance_id], "limit": 500, "orderBy": orderBy}
    headers = {"Content-Type": "application/json"}

    try:
        response = requests.post(GRAPHQL_URL, json={"query": query, "variables": variables}, headers=headers)
        response.raise_for_status()
    except requests.RequestException as e:
        await interaction.followup.send(f"Error fetching data: {e}")
        return

    result = response.json()
    if "errors" in result:
        await interaction.followup.send(f"API errors: {result['errors']}")
        return

    alliances_data = result.get("data", {}).get("alliances", {}).get("data", [])
    if not alliances_data:
        await interaction.followup.send("No alliance data found.")
        return
    alliance = alliances_data[0]
    wars = alliance.get("wars", [])[:war_count]  

    def chunks(lst, n):
        for i in range(0, len(lst), n):
            yield lst[i:i + n]

    all_log = ""
    money_by_day = defaultdict(float)
    outcome_by_day = defaultdict(list)

    
    

    
    
    for idx, war in enumerate(wars):
        attacker = war.get("attacker") or {}
        defender = war.get("defender") or {}
        atk_alliance = str(attacker.get("alliance_id", 0))
        def_alliance = str(defender.get("alliance_id", 0))

        is_attacker = atk_alliance == str(alliance_id)
        is_defender = def_alliance == str(alliance_id)

        money_looted = war.get("att_money_looted", 0) if is_attacker else war.get("def_money_looted", 0)

        winner_id = str(war.get("winner_id"))
        atk_id = str(attacker.get("id", 0))
        def_id = str(defender.get("id", 0))

        if winner_id == atk_id and is_attacker:
            outcome = "Win"
            y_val = 1
        elif winner_id == def_id and is_defender:
            outcome = "Win"
            y_val = 1
        elif winner_id == def_id and is_attacker:
            outcome = "Loss"
            y_val = -1
        elif winner_id == atk_id and is_defender:
            outcome = "Loss"
            y_val = -1
        else:
            outcome = "Draw"
            y_val = 0

        war_datetime_raw = war.get("date")
        try:
            from dateutil import parser
            war_dt = parser.isoparse(war_datetime_raw)
            war_date = war_dt.date().isoformat()  
        except Exception as e:
            print(f"⛔ Failed to parse war date: {war_datetime_raw} | Error: {e}")
            continue

        
        money_by_day[war_date] += money_looted
        outcome_by_day[war_date].append(y_val)

        all_log += (
            f"Date: {war_date} | {attacker.get('nation_name','?')} vs {defender.get('nation_name','?')} | "
            f"Outcome: {outcome} | Looted: {money_looted:,}\n"
        )

    

    if money_more_detail:
    
        
        war_dates_all = sorted(set(
            datetime.strptime(war.get("date")[:10], "%Y-%m-%d").date()
            for war in wars if war.get("date")
        ))
    
        
        values = [money_by_day[d.strftime("%Y-%m-%d")] for d in war_dates_all]
        outcome_avgs = [
            sum(outcome_by_day[d.strftime("%Y-%m-%d")]) / len(outcome_by_day[d.strftime("%Y-%m-%d")])
            for d in war_dates_all
        ]
    
        
        fig_money, ax_money = plt.subplots(figsize=(10, 5))
        ax_money.bar(war_dates_all, values, color="red")
        ax_money.set_title(f"{alliance['name']} - Money Looted Per Day")
        ax_money.set_ylabel("Money Looted ($M)")
        ax_money.xaxis.set_major_formatter(DateFormatter("%Y-%m-%d"))
        ax_money.xaxis.set_major_locator(mdates.DayLocator(interval=max(1, len(war_dates_all) // 10)))
        plt.xticks(rotation=45)
        plt.tight_layout()
    
        buf_money = BytesIO()
        plt.savefig(buf_money, format="png")
        buf_money.seek(0)
        plt.close(fig_money)
        await interaction.followup.send(file=discord.File(buf_money, filename="money_detail_graph.png"))
    
        
        fig_outcome, ax_outcome = plt.subplots(figsize=(10, 5))
        ax_outcome.plot(war_dates_all, outcome_avgs, color="blue", marker="o")
        ax_outcome.set_title(f"{alliance['name']} - Average Outcome Per Day")
        ax_outcome.set_ylabel("Outcome")
        ax_outcome.set_yticks([-1, 0, 1])
        ax_outcome.set_yticklabels(["Loss", "Draw", "Win"])
        ax_outcome.xaxis.set_major_formatter(DateFormatter("%Y-%m-%d"))
        ax_outcome.xaxis.set_major_locator(mdates.DayLocator(interval=max(1, len(war_dates_all) // 10)))
        plt.xticks(rotation=45)
        plt.tight_layout()
    
        buf_outcome = BytesIO()
        plt.savefig(buf_outcome, format="png")
        buf_outcome.seek(0)
        plt.close(fig_outcome)
        file=discord.File(buf_outcome, filename="outcome_detail_graph.png")
        embed = discord.Embed(
            title="##War Results:##",
            colour=discord.Colour.dark_orange(),
            description="Visialized War Results:"
        )
        image_url = "https://i.ibb.co/qJygzr7/Leonardo-Phoenix-A-dazzling-star-emits-white-to-bluish-light-s-2.jpg"
        embed.set_footer(text=f"Brought to you by Darkstar", icon_url=image_url)
        await interaction.followup.send(embed=embed)


    else:
        WARS_PER_GRAPH = 30
        
        for batch_index, war_batch in enumerate(chunks(wars, WARS_PER_GRAPH), start=1):
            war_results = []
            money_per_war = []

            for war in war_batch:
                attacker = war.get("attacker") or {}
                defender = war.get("defender") or {}
                atk_alliance = str(attacker.get("alliance_id", 0))
                def_alliance = str(defender.get("alliance_id", 0))

                is_attacker = atk_alliance == str(alliance_id)
                is_defender = def_alliance == str(alliance_id)

                money_looted = war.get("att_money_looted", 0) if is_attacker else war.get("def_money_looted", 0)

                winner_id = str(war.get("winner_id"))
                atk_id = str(attacker.get("id", 0))
                def_id = str(defender.get("id", 0))

                if winner_id == atk_id and is_attacker:
                    y_val = 1
                elif winner_id == def_id and is_defender:
                    y_val = 1
                elif winner_id == def_id and is_attacker:
                    y_val = -1
                elif winner_id == atk_id and is_defender:
                    y_val = -1
                else:
                    y_val = 0

                war_results.append(y_val)
                money_per_war.append(money_looted / 1_000_000)  

            indices = list(range(1, len(war_results) + 1))

            fig, ax1 = plt.subplots(figsize=(9, 5))
            bar_width = 0.6

            
            ax1.bar(indices, money_per_war, width=bar_width, color="red", label="Money Looted (M)", align='center', zorder=2)
            ax1.set_ylabel("Money Looted ($M)")
            ax1.set_xlabel("War Number")
            ax1.set_xticks(indices)

            
            ax2 = ax1.twinx()
            ax2.plot(indices, war_results, color="blue", linestyle="-", marker="o", label="Outcome", zorder=1)
            ax2.set_ylabel("Outcome")
            ax2.set_yticks([-1, 0, 1])
            ax2.set_yticklabels(["Loss", "Draw", "Win"])
            ax2.grid(False)

            ax1.set_xlim(0.5, len(indices) + 0.5)

            
            ax1.legend(loc="upper center", bbox_to_anchor=(0.5, -0.15), ncol=1)
            ax2.legend(loc="upper center", bbox_to_anchor=(0.5, -0.25), ncol=1)

            plt.title(f"{alliance['name']} - War Batch {batch_index}")
            plt.tight_layout()

            buf = BytesIO()
            plt.savefig(buf, format="png")
            buf.seek(0)
            plt.close(fig)
            file=discord.File(buf, filename=f"war_graph_batch{batch_index}.png")
            embed = discord.Embed(
                title="War Results Alliance:",
                colour=discord.Colour.dark_orange(),
                description="Visualised Results:"
            )
            image_url = "https://i.ibb.co/qJygzr7/Leonardo-Phoenix-A-dazzling-star-emits-white-to-bluish-light-s-2.jpg"
            embed.set_footer(text=f"Brought to you by Darkstar", icon_url=image_url)
            embed.set_image(url=f"attachment://war_graph_batch{batch_index}.png")
            await interaction.followup.send(embed=embed, file=file)

    
    log_file = BytesIO(all_log.encode("utf-8"))
    log_file.seek(0)
    await interaction.followup.send(file=discord.File(log_file, filename=f"war_summary_{alliance_id}.txt"))



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

@bot.tree.command(name="see_report", description="See the WC of other nations (may be wrong, idk nor care)")
async def see_report(interaction: discord.Interaction, nation: str):
    await interaction.response.defer(thinking=True)

    try:
        guild_id = str(interaction.guild.id)
        sheet = get_sheet_s("Nation WC")
        rows = sheet.get_all_records()
        prices = get_prices(guild_id)
        
        
        resource_prices = {
            item["resource"]: float(item["average_price"])
            for item in prices["data"]["top_trade_info"]["resources"]
        }

        
        match = next((row for row in rows if row["Nation"].lower() == nation.lower()), None)

        if not match:
            await interaction.followup.send(f"❌ No report found for `{nation}`.")
            return

        timestamp = match.get("Timestamp", "Unknown time")
        last_update = match.get("Last update", None)

        embed = discord.Embed(
            title=f"🕵️ WC Report: {match['Nation']}",
            description=f"Report as of `{timestamp}`",
            color=discord.Color.blue()
        )

        total_value = 0.0

        for key, value in match.items():
            if key in ("Nation", "Timestamp", "Last update"):
                continue

            try:
                val = float(value.replace(",", "")) if isinstance(value, str) else float(value)
            except:
                embed.add_field(name=key.capitalize(), value=str(value), inline=True)
                continue

            
            if key in resource_prices:
                resource_value = val * resource_prices[key]
                total_value += resource_value
                embed.add_field(
                    name=key.capitalize(),
                    value=f"{val:,.2f} @ {resource_prices[key]:,.2f}",
                    inline=True
                )
            elif key.lower() == "money":
                total_value += val
                embed.add_field(name="Money", value=f"{val:,.2f}", inline=True)
            else:
                embed.add_field(name=key.capitalize(), value=f"{val:,.2f}", inline=True)

        
        estimated_loot = total_value * 0.14
        embed.add_field(name="💰 Estimated Loot (14%)", value=f"{estimated_loot:,.2f}", inline=False)

        
        if last_update:
            embed.set_footer(text=f"Last update: {last_update}")

        await interaction.followup.send(embed=embed)

    except Exception as e:
        print(f"Error in see_report: {e}")
        await interaction.followup.send("❌ An error occurred while fetching the report.")

@bot.tree.command(name="list_reports", description="See which nations have spy reports stored.")
async def list_reports(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True)

    try:
        sheet = get_sheet_s("Nation WC")
        rows = sheet.get_all_records()

        nation_names = sorted(set(row["Nation"] for row in rows if row.get("Nation")))

        if not nation_names:
            await interaction.followup.send("❌ No nation reports are currently stored.")
            return

        embed = discord.Embed(
            title="🗂️ Stored Spy Reports",
            description=f"Total Nations: `{len(nation_names)}`",
            color=discord.Color.green()
        )

        
        chunk_size = 20
        for i in range(0, len(nation_names), chunk_size):
            chunk = nation_names[i:i+chunk_size]
            embed.add_field(name=f"Nations {i+1}-{i+len(chunk)}", value="\n".join(chunk), inline=False)

        await interaction.followup.send(embed=embed)

    except Exception as e:
        print(f"Error in list_reports: {e}")
        await interaction.followup.send("❌ An error occurred while retrieving the nation list.")


@bot.tree.command(name="raws_audits", description="Audit building and raw usage per nation")
async def raws_audits(interaction: discord.Interaction, day: int):
    await interaction.response.defer(thinking=True)
    sheet = get_registration_sheet()
    rows = sheet.get_all_records()
    user_id = str(interaction.user.id)

    user_data = next((r for r in rows if str(r.get("DiscordID", "")).strip() == user_id), None)
    guild_id = str(interaction.guild.id)
    user_id = str(interaction.user.id)

    user_data = cached_users.get(guild_id, {}).get(user_id)
    if not user_data:
        await interaction.followup.send(
            "❌ You are not registered. Please register first.", ephemeral=True
        )
        return

    async def is_banker(inter):
        GOV_ROLE = get_gov_role(inter)
        return (
            any(role.name == GOV_ROLE for role in inter.user.roles)
        )

    if not await is_banker(interaction):
        await interaction.followup.send("❌ You don't have the rights, lil bro.")
        return

    output = StringIO()
    audits_by_nation = {}
    batch_count = 0

    for idx, row in enumerate(rows):
        nation_id = str(row.get("NationID", "")).strip()
        if not nation_id:
            continue

        cities_df = graphql_cities(nation_id)
        if cities_df is None or cities_df.empty:
            output.write(f"❌ Nation ID {nation_id} - City data not found.\n\n")
            continue

        try:
            cities = cities_df.iloc[0]["cities"]
        except (KeyError, IndexError, TypeError):
            output.write(f"❌ Nation ID {nation_id} - Malformed city data.\n\n")
            continue

        projects = {
            "iron_works": 0,
            "bauxite_works": 0,
            "arms_stockpile": 0,
            "emergency_gasoline_reserve": 0
        }
        cons = {
            "iron_works": 6.12,
            "bauxite_works": 6.12,
            "arms_stockpile": 4.5,
            "emergency_gasoline_reserve": 6.12
        }
        buildings = {
            "steel_mill": 0,
            "oil_refinery": 0,
            "aluminum_refinery": 0,
            "munitions_factory": 0
        }
        suffitient = {
            "coal_mine": 0,
            "oil_well": 0,
            "lead_mine": 0,
            "iron_mine": 0,
            "bauxite_mine": 0
        }
        nu_uh = {
            "coal_mine": 3,
            "oil_well": 3,
            "lead_mine": 3,
            "iron_mine": 3,
            "bauxite_mine": 3
        }
        
        for city in cities:
            for p in projects:
                projects[p] += int(city.get(p, 0))
            for b in buildings:
                buildings[b] += int(city.get(b, 0))
            for s in suffitient:
                suffitient[s] += int(city.get(s, 0))
        
        res = get_resources(nation_id, interaction)
        if not res:
            output.write(f"❌ Nation ID {nation_id} - Resource data not found.\n\n")
            continue
        
        nation_name, _, _, _, gasoline, munitions, steel, aluminum, bauxite, lead, iron, oil, coal, _ = res
        
        required = {
            "steel_mill": {"coal": day * cons["iron_works"] * buildings["steel_mill"], "iron": day * cons["iron_works"] * buildings["steel_mill"]},
            "oil_refinery": {"oil": day * cons["emergency_gasoline_reserve"] * buildings["oil_refinery"]},
            "aluminum_refinery": {"bauxite": day * cons["bauxite_works"] * buildings["aluminum_refinery"]},
            "munitions_factory": {"lead": day * cons["arms_stockpile"] * buildings["munitions_factory"]}
        }
        
        resources = {
            "coal": coal,
            "iron": iron,
            "oil": oil,
            "bauxite": bauxite,
            "lead": lead
        }
        
        mine_map = {
            "coal": "coal_mine",
            "oil": "oil_well",
            "lead": "lead_mine",
            "iron": "iron_mine",
            "bauxite": "bauxite_mine"
        }
        
        all_ok = True
        building_lines = []
        request_lines = []
        
        for bld, reqs in required.items():
            if buildings[bld] == 0:
                continue
        
            lines = []
            fulfillment_ratios = []
        
            for res_type, req_val in reqs.items():
                had = resources[res_type]
                mine_type = mine_map[res_type]
                mine_output = suffitient[mine_type] * nu_uh[mine_type] * day
                adjusted_req = max(0, req_val - mine_output)
                ratio = had / adjusted_req if adjusted_req > 0 else 1
                fulfillment_ratios.append(ratio)
        
            min_ratio = min(fulfillment_ratios)
        
            if min_ratio >= 1:
                color = "🟢"
            elif min_ratio >= (day / 3 + day / 3) / day:
                color = "🟡"
                all_ok = False
            elif min_ratio >= (day / 3) / day:
                color = "🟠"
                all_ok = False
            else:
                color = "🔴"
                all_ok = False
        
            for res_type, req_val in reqs.items():
                had = resources[res_type]
                mine_type = mine_map[res_type]
                mine_output = suffitient[mine_type] * nu_uh[mine_type] * day
                adjusted_req = max(0, req_val - mine_output)
                missing = max(0, adjusted_req - had)
                lines.append(f"{res_type.capitalize()}: (Missing: {missing:.0f})")
                if missing > 0 and color != "🟢":
                    request_lines.append((res_type.capitalize(), missing, color))
        
            if color != "🟢":
                building_lines.append(
                    f"{bld.replace('_', ' ').title()}: {buildings[bld]} ({', '.join(lines)}) {color}"
                )
        
        if not all_ok:
            output.write(f"{nation_name} ({nation_id})\n")
            for line in building_lines:
                output.write(line + "\n")
            output.write("\n")
        
            audits_by_nation[nation_id] = {
                "nation_name": nation_name,
                "missing": request_lines,
                "color": color
            }
        
        await asyncio.sleep(2.5)

        '''batch_count += 1
        if batch_count == 30:
            await asyncio.sleep(60)
            batch_count = 0'''

    output.seek(0)
    discord_file = discord.File(fp=output, filename="raws_audit.txt")
    await interaction.followup.send("✅ Audit complete.", file=discord_file, view=RawsAuditView(output=output.getvalue(), audits=audits_by_nation))

@bot.tree.command(name="nation_info", description="Info on the chosen Nation")
@app_commands.describe(
    who="The Discord member to query",
    external_id="Raw Nation ID to override user lookup (optional)"
)
async def who_nation(interaction: discord.Interaction, who: discord.Member, external_id: str = "None"):
    await interaction.response.defer()
    global cached_users 
    async def is_banker():
        GOV_ROLE = get_gov_role(interaction)
        return (
            any(role.name == GOV_ROLE for role in interaction.user.roles)
        )

    user_id = str(interaction.user.id)
    own_id = None

    
    if external_id != "None":
        own_id = external_id.strip()

    else:
        
        if interaction.user.id != who.id:
            if not await is_banker():
                await interaction.followup.send("❌ You don't have the rights")
                return

        
        guild_id = str(interaction.guild.id)
        user_id = str(interaction.user.id)
    
        user_data = cached_users.get(guild_id, {}).get(user_id)
        if not user_data:
            await interaction.followup.send(
                "❌ You are not registered. Please register first.", ephemeral=True
            )
            return
            
        
        own_id = str(user_data.get("NationID", "")).strip()

    
    try:
        nation_name, nation_leader, nation_score, war_policy, soldiers, tanks, aircraft, ships, spies, missiles, nuclear = get_military(own_id, interaction)
        nation_name, num_cities, food, money, gasoline, munitions, steel, aluminum, bauxite, lead, iron, oil, coal, uranium = get_resources(own_id, interaction)
        gen_data = get_general_data(own_id, interaction)

        if not gen_data:
            await interaction.followup.send("❌ Failed to fetch general data.")
            return

        (
            alliance_id,
            alliance_position,
            alliance,
            domestic_policy,
            num_cities,
            colour,
            activity,
            project,
            turns_since_last_project
        ) = gen_data

        
        try:
            from datetime import datetime, timezone
            activity_dt = datetime.fromisoformat(activity)
            now = datetime.now(timezone.utc)
            delta = now - activity_dt
            if delta.total_seconds() < 60:
                activity_str = "just now"
            elif delta.total_seconds() < 3600:
                minutes = int(delta.total_seconds() // 60)
                activity_str = f"{minutes} minute{'s' if minutes != 1 else ''} ago"
            elif delta.total_seconds() < 86400:
                hours = int(delta.total_seconds() // 3600)
                activity_str = f"{hours} hour{'s' if hours != 1 else ''} ago"
            else:
                days = int(delta.total_seconds() // 86400)
                activity_str = f"{days} day{'s' if days != 1 else ''} ago"
        except Exception:
            activity_str = "Unknown"

        msg = (
            f"**📋 GENERAL INFOS:**\n"
            f"🌍 *Nation:* {nation_name} (Nation ID: `{own_id}`)\n"
            f"👑 *Leader:* {nation_leader}\n"
            f"🔛 *Active:* {activity_str}\n"
            f"🫂 *Alliance:* {alliance} (Alliance ID: `{alliance_id}`)\n"
            f"🎖️ *Alliance Position:* {alliance_position}\n"
            f"🏙️ *Cities:* {num_cities}\n"
            f"🎨 *Color Trade Bloc:* {colour}\n"
            f"📈 *Score:* {nation_score}\n"
            f"🚧 *Projects:* {project}\n"
            f"⏳ *Turn Since Last Project:* {turns_since_last_project}\n"
            f"📜 *Domestic Policy:* {domestic_policy}\n"
            f"🛡 *War Policy:* {war_policy}\n\n"

            f"**🏭 RESOURCES:**\n"
            f"🛢️ *Steel:* {steel}\n"
            f"⚙️ *Aluminum:* {aluminum}\n"
            f"💥 *Munitions:* {munitions}\n"
            f"⛽ *Gasoline:* {gasoline}\n"
            f"🛢 *Oil:* {oil}\n"
            f"⛏️ *Bauxite:* {bauxite}\n"
            f"🪨 *Coal:* {coal}\n"
            f"🔩 *Lead:* {lead}\n"
            f"🪓 *Iron:* {iron}\n"
            f"🍞 *Food:* {food}\n"
            f"💰 *Money:* ${money}\n"
            f"☢️ *Uranium:* {uranium}\n\n"

            f"**🛡 MILITARY FORCES:**\n"
            f"🪖 *Soldiers:* {soldiers}\n"
            f"🚛 *Tanks:* {tanks}\n"
            f"✈️ *Aircraft:* {aircraft}\n"
            f"🚢 *Ships:* {ships}\n"
            f"🕵️ *Spies:* {spies}\n"
            f"🚀 *Missiles:* {missiles}\n"
            f"☢️ *Nuclear Weapons:* {nuclear}"
        )

        embed = discord.Embed(
            title=f"🏳️🧑‍✈️ {nation_name}, lead by {nation_leader}",
            color=discord.Color.dark_embed(),
            description=msg
        )
        image_url = "https://i.ibb.co/qJygzr7/Leonardo-Phoenix-A-dazzling-star-emits-white-to-bluish-light-s-2.jpg"
        embed.set_footer(text="Brought to you by Darkstar", icon_url=image_url)

        nation_id = own_id
        view = NationInfoView(nation_id, embed)
        await interaction.followup.send(embed=embed, view=view)

    except Exception as e:
        await interaction.followup.send(f"❌ Error: {e}")


reasons_for_grant = [
    
    
   
    
    
    
    app_commands.Choice(name="Uranium and Food", value="Uranium and Food"),
    app_commands.Choice(name="Resources for Production", value="Resources for Production"),
]

RESOURCE_ABBR = {
    'g': '-g',  
    'm': '-m',  
    'a': '-a',  
    's': '-s',  
    'f': '-f',  
    'u': '-u',  
    'l': '-l',  
    'b': '-b',  
    'o': '-o',  
    'c': '-c',  
    'i': '-i',  
    '$': '-$',  
}

@bot.tree.command(
    name="auto_resources_for_prod_req", 
    description="Set up auto resources request for production (bauxite, coal, iron, lead, oil)"
)
@app_commands.describe(
    coal="Amount of coal requested",
    oil="Amount of oil requested",
    bauxite="Amount of bauxite requested",
    lead="Amount of lead requested",
    iron="Amount of iron requested",
    time_period="How often would you want this requested in days",
    visual_confirmation="Type `Hypopothamus` for further confirmation"
)
async def auto_resources_for_prod_req(
    interaction: discord.Interaction,
    coal: str = "0",
    oil: str = "0",
    bauxite: str = "0",
    lead: str = "0",
    iron: str = "0",
    time_period: str = "1",
    visual_confirmation: str = ""
):
    await interaction.response.defer(ephemeral=True)
    user_id = str(interaction.user.id)

    if visual_confirmation.strip() != "Hypopothamus":
        await interaction.followup.send(
            "❌ Visual confirmation failed. Please type `Hypopothamus` exactly.", ephemeral=True
        )
        return

    guild_id = str(interaction.guild.id)
    user_data = cached_users.get(guild_id, {}).get(user_id)
    if not user_data:
        await interaction.followup.send(
            "❌ You are not registered. Please register first.", ephemeral=True
        )
        return
    
    nation_id = user_data.get("NationID", "").strip()
    if not nation_id:
        await interaction.followup.send(
            "❌ Could not find your Nation ID in the registration data.", ephemeral=True
        )
        return

    try:
        time_period_int = int(time_period.strip())
        if time_period_int < 1:
            raise ValueError
    except ValueError:
        await interaction.followup.send(
            "❌ The minimum allowed time period is 1 day.", ephemeral=True
        )
        return

    sheet = get_auto_requests_sheet(guild_id)
    all_rows = await asyncio.to_thread(sheet.get_all_values)

    if not all_rows or len(all_rows) < 1:
        await interaction.followup.send(
            "❌ AutoRequests sheet is empty or not found.", ephemeral=True
        )
        return

    header = all_rows[0]
    col_index = {col: idx for idx, col in enumerate(header)}

    def parse_amount(amount):
        try:
            amount = str(amount).lower().replace(",", "").strip()
            match = re.match(r"^([\d\.]+)\s*(k|m|mil|million)?$", amount)
            if not match:
                return 0
            num, suffix = match.groups()
            num = float(num)
            if suffix in ("k",):
                return int(num * 1_000)
            elif suffix in ("m", "mil", "million"):
                return int(num * 1_000_000)
            return int(num)
        except Exception:
            return 0

    now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    data_to_store = {
        "DiscordID": user_id,
        "NationID": nation_id,
        "Coal": parse_amount(coal),
        "Oil": parse_amount(oil),
        "Bauxite": parse_amount(bauxite),
        "Lead": parse_amount(lead),
        "Iron": parse_amount(iron),
        "TimePeriod": str(time_period_int),
    }

    rows = all_rows[1:]
    user_row_index = None
    for idx, row in enumerate(rows, start=2):
        if len(row) > col_index.get("DiscordID", -1) and row[col_index["DiscordID"]] == user_id:
            user_row_index = idx
            break

    if user_row_index:
        for key, val in data_to_store.items():
            if key in col_index:
                await asyncio.to_thread(sheet.update_cell, user_row_index, col_index[key] + 1, val)
        if "LastRequested" in col_index:
            await asyncio.to_thread(sheet.update_cell, user_row_index, col_index["LastRequested"] + 1, now_str)
        await interaction.followup.send(
            "✅ Your auto-request has been updated successfully.", ephemeral=True
        )
    else:
        new_row = []
        for col in header:
            if col == "LastRequested":
                new_row.append(now_str)
            else:
                new_row.append(data_to_store.get(col, ""))
        await asyncio.to_thread(sheet.append_row, new_row)
        await interaction.followup.send(
            "✅ Your auto-request has been added successfully.", ephemeral=True
        )

@bot.tree.command(name="disable_auto_request", description="Disable your auto-request for key raw resources")
async def disable_auto_request(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)

    user_id = str(interaction.user.id)
    sheet = get_auto_requests_sheet(interaction.guild.id)
    all_rows = sheet.get_all_values()

    if not all_rows or len(all_rows) < 2:
        await interaction.followup.send("⚠️ No auto-requests found in the sheet.", ephemeral=True)
        return

    header = all_rows[0]
    rows = all_rows[1:]

    try:
        discord_idx = header.index("DiscordID")
        tracked_resources = ["Bauxite", "Coal", "Iron", "Oil", "Lead"]
        resource_indices = [header.index(r) for r in tracked_resources]
    except ValueError as e:
        await interaction.followup.send(f"❌ Header missing: {e}", ephemeral=True)
        return

    deleted = False
    for i, row in enumerate(rows, start=2):  
        if row[discord_idx] != user_id:
            continue

        try:
            if any(int(row[j].replace(",", "")) > 0 for j in resource_indices):
                sheet.delete_rows(i)
                deleted = True
                break
        except ValueError:
            continue  

    if deleted:
        await interaction.followup.send("✅ Your auto-request for raw resources has been disabled.", ephemeral=True)
    else:
        await interaction.followup.send("⚠️ No active auto-request for those resources found under your account.", ephemeral=True)
        
@bot.tree.command(name="request_for_ing", description="Request a grant for another member ingame with a screenshot")
@app_commands.describe(
    nation_id="Nation ID of the person you're requesting for",
    screenshot="Screenshot proving this grant request is legitimate",
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
    munitions="Amount of munitions requested",
    note="A note"
)
async def request_for_ing(
    interaction: discord.Interaction,
    nation_id: str,
    screenshot: discord.Attachment,
    uranium: str = "0",
    coal: str = "0",
    oil: str = "0",
    bauxite: str = "0",
    lead: str = "0",
    iron: str = "0",
    steel: str = "0",
    aluminum: str = "0",
    gasoline: str = "0",
    money: str = "0",
    food: str = "0",
    munitions: str = "0",
    note: str= "/"
):
    await interaction.response.defer()
    user_id = str(interaction.user.id)

    try:
        if not screenshot.content_type.startswith("image/"):
            await interaction.followup.send("❌ The screenshot must be an image.", ephemeral=True)
            return

        nation_id = nation_id.strip()
        if not nation_id.isdigit():
            await interaction.followup.send("❌ Nation ID must be a number.", ephemeral=True)
            return

        nation_data = get_military(nation_id, interaction)
        if not nation_data:
            await interaction.followup.send("❌ Could not retrieve nation data.", ephemeral=True)
            return

        nation_name = nation_data[0]

        raw_inputs = {
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

        resources = {k: parse_amount(v) for k, v in raw_inputs.items()}
        requested_resources = {k: v for k, v in resources.items() if v > 0}

        if not requested_resources:
            await interaction.followup.send("❌ You must request at least one resource.", ephemeral=True)
            return

        formatted_lines = [
            f"{resource}: {amount:,}".replace(",", ".")
            for resource, amount in requested_resources.items()
        ]
        description_text = "\n".join(formatted_lines)

        embed = discord.Embed(
            title="💰 Grant Request (ING)",
            color=discord.Color.gold(),
            description=(
                f"**Nation:** {nation_name} (`{nation_id}`)\n"
                f"**Requested by:** {interaction.user.mention}\n"
                f"**Request:**\n{description_text}\n"
                f"**Reason:** Player support (with screenshot)\n"
                f"**Note:** {note}\n"
            )
        )
        embed.set_image(url=screenshot.url)
        image_url = "https://i.ibb.co/qJygzr7/Leonardo-Phoenix-A-dazzling-star-emits-white-to-bluish-light-s-2.jpg"
        embed.set_footer(text="Brought to you by Darkstar", icon_url=image_url)

        await interaction.followup.send(embed=embed, view=GrantView())

    except Exception as e:
        await interaction.followup.send(f"❌ An unexpected error occurred: {e}", ephemeral=True)



@bot.tree.command(name="request_miscellaneous", description="Request a custom amount of resources from the alliance bank")
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
    munitions="Amount of munitions requested",
    note="A Note"
)

async def request_grant(
    interaction: discord.Interaction,
    reason: str,
    uranium: str = "0",
    coal: str = "0",
    oil: str = "0",
    bauxite: str = "0",
    lead: str = "0",
    iron: str = "0",
    steel: str = "0",
    aluminum: str = "0",
    gasoline: str = "0",
    money: str = "0",
    food: str = "0",
    munitions: str = "0",
    note: str = "0",
):
    await interaction.response.defer()
    user_id = str(interaction.user.id)

    try:
        global cached_users
        guild_id = str(interaction.guild.id)
        user_data = cached_users.get(guild_id, {}).get(str(interaction.user.id))

        if not user_data:
            await interaction.followup.send("❌ You are not registered. Use `/register` first.")
            return

        own_id = str(user_data.get("NationID", "")).strip()
        if not own_id:
            await interaction.followup.send("❌ Could not find your Nation ID in the sheet.", ephemeral=True)
            return

        nation_data = get_military(own_id, interaction)
        nation_name = nation_data[0]
        if reason.title() in ["Warchest", "WC", "Wc"]:
            await interaction.followup.send("❌ Don't use `/request_grant`, use `/request_warchest`", ephemeral=True)
            return
        
        raw_inputs = {
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

        resources = {k: parse_amount(v) for k, v in raw_inputs.items()}
        requested_resources = {k: v for k, v in resources.items() if v > 0}

        if not requested_resources:
            await interaction.followup.send("❌ You must request at least one resource.", ephemeral=True)
            return

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
                f"**Reason:** {reason.title()}\n"
                f"**Note:** {note}\n"
            )
        )
        image_url = "https://i.ibb.co/qJygzr7/Leonardo-Phoenix-A-dazzling-star-emits-white-to-bluish-light-s-2.jpg"
        embed.set_footer(text="Brought to you by Darkstar", icon_url=image_url)
        message = await interaction.followup.send("<@1390237054872322148> <@1388161354086617220>")
        await message.delete()
        await interaction.followup.send(embed=embed, view=GrantView())

    except Exception as e:
        await interaction.followup.send(f"❌ An unexpected error occurred: {e}", ephemeral=True)

def parse_amount(amount):
    if isinstance(amount, (int, float)):
        return amount

    amount = str(amount).lower().replace(",", "").strip()
    match = re.match(r"^([\d\.]+)\s*(k|m|mil|million)?$", amount)
    if not match:
        raise ValueError(f"Invalid amount format: {amount}")

    num, suffix = match.groups()
    num = float(num)

    if suffix in ("k",):
        return int(num * 1_000)
    elif suffix in ("m", "mil", "million"):
        return int(num * 1_000_000)
    return int(num)

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

@bot.tree.command(name="request_warchest", description="Request a  grant")
@app_commands.describe(percent="How much percent of the warchest do you want", note="A Note")
@app_commands.choices(percent=percent_list)
async def warchest(interaction: discord.Interaction, percent: app_commands.Choice[str], note: str = None):
    await interaction.response.defer()
    global commandscalled
    commandscalled["_global"] += 1
    user_id = str(interaction.user.id)
    
    global cached_users  
    
    guild_id = str(interaction.guild.id)
    user_id = str(interaction.user.id)

    user_data = cached_users.get(guild_id, {}).get(user_id)
    if not user_data:
        await interaction.followup.send(
            "❌ You are not registered. Please register first.", ephemeral=True
        )
        return
        
    
    own_id = str(user_data.get("NationID", "")).strip()

    if not own_id:
            await interaction.followup.send("❌ Could not find your Nation ID in the sheet.")
            return


    try:
        API_KEY = get_api_key_for_interaction(interaction)
        GRAPHQL_URL = f"https://api.politicsandwar.com/graphql?api_key={API_KEY}"
        query = f"""
        {{
          nations(id: [{own_id}]) {{
            data {{
              id
              nation_name
              num_cities
              food
              uranium
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

        
        nation = nation_data[0]
        nation_name = nation["nation_name"]
        cities = nation["num_cities"]
        food = nation["food"]
        uranium = nation["uranium"]
        money = nation["money"]
        gasoline = nation["gasoline"]
        munition = nation["munitions"]
        steel = nation["steel"]
        aluminium = nation["aluminum"]

        if any(x is None for x in [cities, food, uranium, money, gasoline, munition, steel, aluminium]):
            await interaction.followup.send("❌ Missing resource data. Please try again.")
            return

        city = int(cities)

        
        percent_value = percent.value.strip().lower()
        if percent_value in ["50", "50%"]:
            nr_a = 325
            nr_a_f = 1500
            nr_a_m = 500000
            nr_a_u = 20
        else:
            nr_a = 750
            nr_a_f = 3000
            nr_a_m = 1000000
            nr_a_u = 40

        
        nr_a_minus = city * nr_a
        nr_a_f_minus = city * nr_a_f
        nr_a_u_minus = city * nr_a_u
        money_needed = city * nr_a_m

        
        money_n = 0
        gas_n = 0
        mun_n = 0
        ste_n = 0
        all_n = 0
        foo_n = 0
        ur_n = 0

        for res, resource_value in {
            'money': money, 'gasoline': gasoline, 'munitions': munition,
            'steel': steel, 'aluminum': aluminium, 'food': food, 'uranium': uranium
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
            elif res == 'uranium':
                new_value = resource_value - nr_a_u_minus
                ur_n = 0 if new_value >= 0 else -new_value
        
        request_lines = []
        if money_n > 0:
            request_lines.append(f"Money: {round(money_n):,.0f}\n")
        if foo_n > 0:
            request_lines.append(f"Food: {round(foo_n):,.0f}\n")
        if ur_n > 0:
            request_lines.append(f"Uranium: {round(ur_n):,.0f}\n")
        if gas_n > 0:
            request_lines.append(f"Gasoline: {round(gas_n):,.0f}\n")
        if mun_n > 0:
            request_lines.append(f"Munitions: {round(mun_n):,.0f}\n")
        if ste_n > 0:
            request_lines.append(f"Steel: {round(ste_n):,.0f}\n")
        if all_n > 0:
            request_lines.append(f"Aluminum: {round(all_n):,.0f}")
        
        description_text = ''.join(request_lines).strip()
        
        if not description_text:
            await interaction.followup.send(
                f"You already possess all needed resources for a {percent_value} warchest",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title="💰 Grant Request",
            color=discord.Color.gold(),
            description=(
                f"**Nation:** {nation_name} (`{own_id}`)\n"
                f"**Requested by:** {interaction.user.mention}\n"
                f"**Request:**\n{description_text}\n"
                f"**Reason:** Warchest\n"
                f"**Note:** {note}\n"
            )
        )
        image_url = "https://i.ibb.co/qJygzr7/Leonardo-Phoenix-A-dazzling-star-emits-white-to-bluish-light-s-2.jpg"
        embed.set_footer(text=f"Brought to you by Darkstar", icon_url=image_url)
        message = await interaction.followup.send("<@1390237054872322148> <@1388161354086617220> <@1148678095176474678>")
        await message.delete()
        await interaction.followup.send(embed=embed, view=GrantView())
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {e}")

@bot.tree.command(name="help", description="Get the available commands")
async def help(interaction: discord.Interaction):
    await interaction.response.defer()
    user_id = str(interaction.user.id)
    
    global cached_users  
    
    guild_id = str(interaction.guild.id)
    user_id = str(interaction.user.id)

    user_data = cached_users.get(guild_id, {}).get(user_id)
    if not user_data:
        await interaction.followup.send(
            "❌ You are not registered. Please register first.", ephemeral=True
        )
        return
    
    own_id = str(user_data.get("NationID", "")).strip()

    if not own_id:
            await interaction.followup.send("❌ Could not find your Nation ID in the sheet.")
            return
    register_description = (
        "Register yourself using this command to use the *many amazing* freatures of this bot, developed by **<@722094493343416392>**\n"
        "The command is /register nation_id: 680627\n"
        "**Note:** The bot only works if you're registered\n"
    )
    warchest_desc = (
        "Calculates the needed amount of materials for a warchest and requests those\n"
        "Once your request was approved, it will inform you by pinging you\n"
        "The command is /request_warchest percent: 50% or 100%\n"
    )
    warchest_audit_desc = (
        "Calculates the needed amount of materials for a warchest and generates a message to send to the audited user (no ping)\n"
        "The command is /warchest_audit who: @sumnor_the_lazy\n"
    )
    war_losses_desc = (
        "Get the war details for your last few wars\n"
        "The command is /war_losses nation_id: 680627, wars_count: 20\n"
    )
    war_losses_alliance_desc = (
        "Get the war details for the alliance\n"
        "The command is /war_losses_alliance alliance_id: 10259, war_count: 150, money_more_detail: False\n"
    )
    res_in_m_desc = (
        "Get the worth of the Alliance and their members with a graph\n"
        "The command is /res_in_m_for_a mode: Hourly, scale: Billions\n "
    )
    res_detail_desc = (
        "Get the exact number of resources and money + the total of the members of the alliance\n"
        "The command is /res_details_for_alliance"
    )
    mmr_audit_desc = (
        "Get the MMR and the military of the chosen person, with buttons to generate messages to whatever is wrong\n"
        "The command is /mmr_audit who: @sumnor_the_lazy\n"
    )
    member_activity_desc = (
        "Get a Pie Chart for the member activity\n"
        "The command is /member_activity\n"
    )
    send_message_to_channels_desc = (
        "Send a message to a few of you chosen channels\n"
        "The command is /send_message_to_channels channels: #channel message: Pookie :heart:\n"
    )
    dm_user_desc = (
        "Dm one user who is in the server\n"
        "The command is /dm_user who: @masteraced message: Hello ~Pookie :heart:~\n"
    )
    battle_sim_desc = (
        "Generates an approximate battle based on the military of both nations and shows approximate win-chance\n"
        "The command is /battle_sim nation_id: 680627, war_type: Raid\n"
    )
    my_nation_desc = (
        "Shows some general information about the chosen person's nation\n"
        "The command is /nation_info who: @sumnor_the_lazy\n"
    )
    request_grant_desc = (
        "Requests the requested materials. This command is to make the EA departments job easier\n"
        "The command is /request_grant food: 18mil, uranium: 6k, bauxite: 980, ..., reason: Resources for Production, ...\n"
    )
    request_city_desc = (
        "Calculates the approximate cost to buy the requested cities and, if wanted, requests them\n"
        "The command is /request_city current_city: 10, target_city: 15\n"
        "**Note**: On bigger requests the cost inflates a bit\n"
    )
    request_infra_grant_desc = (
        "Calculates the approximate cost of the wanted infra and, if wanted, requests them\n"
        "The command is /request_infra_cost current_infra: 10, target_infra: 1500, city_amount: 10 or if you want it automatically calculated /request_infra_grant target_infra: 2000. This will calculate the cost to get all your cities to 2k infra\n"
        "**Note**: On bigger requests the cost inflates a bit\n"
    )
    request_project_desc = (
        "Calculates the needed materials and money to get the wanted project and, if wanted, requests it\n"
        "The command is /request_project project: Moon Landing\n"
    )
    bug_rep_desc = (
        "Report a bug"
        "The command is /bug_report bug: insert bug report here\n"
    )
    gov_msg = (
        "\n***`/register`:***\n"
        f"{register_description}"
        "\n***`/request_warchest`:***\n"
        f"{warchest_desc}"
        "\n***`/warchest_audit`:***\n"
        f"{warchest_audit_desc}"
        "\n***`/war_losses`:***\n"
        f"{war_losses_desc}"
        "\n***`/war_losses_alliance`:***\n"
        f"{war_losses_alliance_desc}"
        "\n***`/res_in_m_for_a`:***\n"
        f"{res_in_m_desc}"
        "\n***`/res_details_for_alliance`:***\n"
        f"{res_detail_desc}"
        "\n***`/mmr_audit`:***\n"
        f"{mmr_audit_desc}"
        "\n***`/member_activity`:***\n"
        f"{member_activity_desc}"
        "\n***`/send_message_to_channels`:***\n"
        f"{send_message_to_channels_desc}"
        "\n***`/dm_user`:***\n"
        f"{dm_user_desc}"
        "\n***`/battle_sim`:***\n"
        f"{battle_sim_desc}"
        "\n***`/nation_info`:***\n"
        f"{my_nation_desc}"
        "\n***`/request_grant`:***\n"
        f"{request_grant_desc}"
        "\n***`/request_city`:***\n"
        f"{request_city_desc}"
        "\n***`/request_infra_grant`:***\n"
        f"{request_infra_grant_desc}"
        "\n***`/request_project`:***\n"
        f"{request_project_desc}"
    )
    gov_mssg = discord.Embed(
        title="List of the commands (including the government ones):",
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
        "\n***`/war_losses`:***\n"
        f"{war_losses_desc}"
        "\n***`/war_losses_alliance`:***\n"
        f"{war_losses_alliance_desc}"
        "\n***`/battle_sim`:***\n"
        f"{battle_sim_desc}"
        "\n***`/nation_info`:***\n"
        f"{my_nation_desc}"
        "\n***`/request_grant`:***\n"
        f"{request_grant_desc}"
        "\n***`/request_city`:***\n"
        f"{request_city_desc}"
        "\n***`/request_infra_grant`:***\n"
        f"{request_infra_grant_desc}"
        "\n***`/request_project`:***\n"
        f"{request_project_desc}"
    )

    norm_mssg = discord.Embed(
        title="List of the commands:",
        color=discord.Color.blue(),
        description=norm_msg
    )
    image_url = "https://i.ibb.co/qJygzr7/Leonardo-Phoenix-A-dazzling-star-emits-white-to-bluish-light-s-2.jpg"
    norm_mssg.set_footer(text=f"Brought to you by Darkstar", icon_url=image_url)
    async def is_high_power(interaction):
        GOV_ROLE = get_gov_role(interaction)
        return (
            any(role.name == GOV_ROLE for role in interaction.user.roles)
        )
    
    if not await is_high_power(interaction):
        await interaction.followup.send(embed=norm_mssg)
    else:
        await interaction.followup.send(embed=gov_mssg)


@bot.tree.command(name="request_city", description="Calculate cost for upgrading from current city to target city")
@app_commands.describe(current_cities="Your current number of cities", target_cities="Target number of cities")
async def request_city(interaction: discord.Interaction, current_cities: int, target_cities: int):
    await interaction.response.defer()
    user_id = str(interaction.user.id)
    commandscalled[user_id] = commandscalled.get(user_id, 0) + 1
    try:
        global cached_users  
        
        guild_id = str(interaction.guild.id)
        user_data = cached_users.get(guild_id, {}).get(str(interaction.user.id))  
        
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

    datta = get_resources(own_id, interaction)
    nation_name = datta[0]
    total_cost = 0
    cost_details = []
    top20Average = 41.47  

    def compute_city_cost(cityToBuy: int, top20Average: float) -> float:
        
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
            return 1_000_000  
        elif city_number < 60:
            return 5_000_000  
        elif city_number < 100:
            return 11_000_000  
        else:
            return 20_000_000  

    for i in range(current_cities + 1, target_cities + 1):
        cost = compute_city_cost(i, top20Average)
        user_id = interaction.user.id

        
        rounding_multiple = get_rounding_multiple(i)
        
        
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
            "total_cost": total_cost,
            "person": user_id
        })
        
                    )

def get_city_data(nation_id: str, interaction) -> list[dict]:
    API_KEY = get_api_key_for_interaction(interaction)
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
    current_infra: int = 0,
    city_amount: int = 1,
    auto_calculate: bool = True,
    city_name: str = None
):
    await interaction.response.defer()
    user_id = str(interaction.user.id)

    if target_infra > 2000:
        await interaction.followup.send("❌ Target infrastructure above 2000 is not supported.(*** Personal Contribution by `@patrickrickrickpatrick` ***)")
        return

    
    try:
        global cached_users  
        
        guild_id = str(interaction.guild.id)
        user_data = cached_users.get(guild_id, {}).get(str(interaction.user.id))  
        
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

    
    city_data = get_city_data(own_id, interaction)
    if not city_data:
        await interaction.followup.send("❌ Could not retrieve city data for your nation.")
        return

    nation_data = get_resources(own_id, interaction)
    nation_name = nation_data[0]
    nation_id = own_id
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
        user_id = interaction.user.id
        data = {
            "nation_name": nation_name,
            "nation_id": nation_id,
            "from": current_infra,
            "infra": target_infra,
            "ct_count": city_amount,
            "total_cost": cost,
            "person": user_id
        }

        embed = discord.Embed(
            title=f"Upgrade Cost for {city_name}",
            color=discord.Color.gold(),
            description=f"Upgrade from {current} to {target_infra}\nEstimated Cost: **${cost:,.0f}**"
        )
        embed.set_footer(text="Brought to you by Darkstar\nPersonal Contribution by <@1026284133481189388>", icon_url="https://i.ibb.co/qJygzr7/Leonardo-Phoenix-A-dazzling-star-emits-white-to-bluish-light-s-2.jpg")
        await interaction.followup.send(
            embed=embed,
            view=BlueGuy(category="infra", data=data)
        )
        return

    
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
            city_amount += 1

        if not description_lines:
            await interaction.followup.send("✅ All cities are already at or above the target infrastructure.")
            return
        user_id = interaction.user.id
        rounded_total_cost = int(math.ceil(total_cost / 1_000_000.0)) * 1_000_000
        data = {
            "nation_name": nation_name,
            "nation_id": nation_id,
            "from": current_infra,
            "infra": target_infra,
            "ct_count": city_amount,
            "total_cost": rounded_total_cost,
            "person": user_id
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

    
    if current_infra is None:
        current_infra = 0
    if city_amount is None:
        city_amount = 1
    if target_infra <= current_infra:
        await interaction.followup.send("❌ Target infrastructure must be greater than current infrastructure.")
        return

    total_cost = calculate_total_infra_cost(current_infra, target_infra, city_amount)
    if total_cost > 900_000:
        rounded_total_cost = math.ceil(total_cost / 100_000) * 100_000
        
    data = {
            "nation_name": nation_name,
            "nation_id": nation_id,
            "from": current_infra,
            "infra": target_infra,
            "ct_count": city_amount,
            "total_cost": rounded_total_cost,
            "person": user_id
        }


    embed = discord.Embed(
        title="🛠️ Infrastructure Upgrade Cost",
        color=discord.Color.green(),
        description=f"From `{current_infra}` to `{target_infra}` for `{city_amount}` city(ies)\nEstimated Cost: **${total_cost:,.0f}**"
    )
    embed.set_footer(text="Brought to you by Darkstar", icon_url="https://i.ibb.co/qJygzr7/Leonardo-Phoenix-A-dazzling-star-emits-white-to-bluish-light-s-2.jpg")
    await interaction.followup.send(embed=embed, view=BlueGuy(category="infra", data=data))


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
        "Military Doctrine": {"Money": 10000000, "Steel": 10000,  "Aluminum": 10000, "Munitions": 10000, "Gasoline": 10000},
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
        "Military Research Center": {"Money": 100000000, "Steel": 10000,  "Aluminum": 10000, "Munitions": 10000, "Gasoline": 10000},
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
    return None  

@bot.tree.command(name="request_project", description="Fetch resources for a project")

@app_commands.describe(project_name="Name of the project", tech_advancement="Is Technological Advancement active?")
async def request_project(interaction: Interaction, project_name: str, tech_advancement: bool = False, note: str = "None"):
    await interaction.response.defer()
    user_id = str(interaction.user.id)

    try:
        global cached_users  
        
        guild_id = str(interaction.guild.id)
        user_data = cached_users.get(guild_id, {}).get(str(interaction.user.id))  
        
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

    nation_data = get_resources(own_id, interaction)
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
            f"**Reason:**\nBuild project: {project_name.title()}\n"
            f"**Note:** {note}\n" 
        )
        user_id = interaction.user.id

        await interaction.followup.send(
            embed=embed,
            view=BlueGuy(category="project", data={"nation_name": nation_name, "nation_id": own_id, "project_name": project_name, "materials": mats, "person": user_id, "note": note})
        )
    else:
        await interaction.followup.send("❌ Project not found.")

@bot.tree.command(name="dm_user", description="DM a user by mentioning them")
@app_commands.describe(
    user="Mention the user to DM",
    message="The message to send"
)
async def dm_user(interaction: discord.Interaction, user: discord.User, message: str):
    await interaction.response.defer(ephemeral=True)
    user_id = str(interaction.user.id)
    
    global cached_users  
    
    guild_id = str(interaction.guild.id)
    user_id = str(interaction.user.id)

    user_data = cached_users.get(guild_id, {}).get(user_id)
    if not user_data:
        await interaction.followup.send(
            "❌ You are not registered. Please register first.", ephemeral=True
        )
        return
    
    own_id = str(user_data.get("NationID", "")).strip()

    if not own_id:
            await interaction.followup.send("❌ Could not find your Nation ID in the sheet.")
            return
    async def is_banker(interaction):
        GOV_ROLE = get_gov_role(interaction)
        return (
            any(role.name == GOV_ROLE for role in interaction.user.roles)
        )

    if not await is_banker(interaction):
        await interaction.followup.send("❌ You don't have the rights, lil bro.")
        return
    better_msg = message.replace(")(", "\n")
    try:
        await user.send(better_msg)
        await interaction.followup.send(f"✅ Sent DM to {user.mention}")

        
        save_dm_to_sheet(interaction.user.name, user.name, better_msg)

    except discord.Forbidden:
        await interaction.followup.send(f"❌ Couldn't send DM to {user.mention} (they may have DMs disabled).")
    except Exception as e:
        await interaction.followup.send(f"❌ An error occurred: {e}")



@bot.tree.command(name="send_message_to_channels", description="Send a message to multiple channels by their IDs")
@app_commands.describe(
    channel_ids="Space-separated list of channel IDs (e.g. 1319746766337478680 1357611748462563479)",
    message="The message to send to the channels"
)
async def send_message_to_channels(interaction: discord.Interaction, channel_ids: str, message: str):
    await interaction.response.defer()
    user_id = str(interaction.user.id)
    
    global cached_users  
    
    guild_id = str(interaction.guild.id)
    user_id = str(interaction.user.id)

    user_data = cached_users.get(guild_id, {}).get(user_id)
    if not user_data:
        await interaction.followup.send(
            "❌ You are not registered. Please register first.", ephemeral=True
        )
        return
    
    own_id = str(user_data.get("NationID", "")).strip()

    if not own_id:
            await interaction.followup.send("❌ Could not find your Nation ID in the sheet.")
            return
    
    channel_ids_list = [cid.strip().replace("<#", "").replace(">", "") for cid in channel_ids.split()]

    
    async def is_banker(interaction):
        GOV_ROLE = get_gov_role(interaction)
        return (
            any(role.name == GOV_ROLE for role in interaction.user.roles)
        )

    if not await is_banker(interaction):
        await interaction.followup.send("❌ You don't have the rights, lil bro.")
        return

    sent_count = 0
    failed_count = 0

    from discord import TextChannel

    for channel_id in channel_ids_list:
        try:
            channel = await bot.fetch_channel(int(channel_id))
            if isinstance(channel, TextChannel):
                better_msg = message.replace(")(", "\n")
                await channel.send(better_msg)
                sent_count += 1
            else:
                failed_count += 1
        except Exception as e:
            failed_count += 1

    await interaction.followup.send(
        f"✅ Sent message to **{sent_count}** channel(s).\n"
        f"❌ Failed for **{failed_count}** channel(s)."
    )

def get_sheet_s(sheet_name: str):
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(get_credentials(), scope)
    client = gspread.authorize(creds)
    return client.open(sheet_name).sheet1

bot.run(bot_key)
