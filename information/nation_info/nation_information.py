import requests
import discord
from collections import defaultdict
from settings.settings_multi import get_api_key_for_interaction, get_gov_role
from databases.graphql_requests import graphql_cities, get_military, get_resources
from databases.sql.data_puller import get_wars_data_sql_by_nation_id
from information.nation_info.trades import TradeModal
from information.SharedInformational.avg_mmr import average_militarisation
from information.nation_info.cities_detail import ShowCitiesDetailButton, extract_cities_from_df
from information.SharedInformational.banking import BankModal
from information.SharedInformational.control_buttons import PrevPageButton, NextPageButton, BackButton, CloseButton
    
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
    def __init__(self, nation_id, original_embed, user_id=None):
        super().__init__(timeout=None)
        self.who = user_id
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
            await interaction.followup.send(err, ephemeral=True)
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
        self.add_item(ShowCitiesDetailButton(
            nation_id=self.nation_id, 
            original_embed=self.original_embed, 
            parent_view=self, 
            user_id=interaction.user.id
        ))
        self.add_item(BackButton(self.original_embed, self))
        self.add_item(CloseButton())

        await interaction.edit_original_response(embed=embed, view=self)

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

        self.add_item(ShowCitiesDetailButton(
            nation_id=self.nation_id, 
            original_embed=self.original_embed, 
            parent_view=self, 
            user_id=interaction.user.id
        ))
        self.add_item(BackButton(self.original_embed, self))
        self.add_item(CloseButton())

        await interaction.edit_original_response(embed=embed, view=self)

    @discord.ui.button(label="Cities", style=discord.ButtonStyle.primary)
    async def builds_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        df = graphql_cities(self.nation_id, interaction)
        if df is None or df.empty:
            await interaction.followup.send("❌ Failed to fetch or parse city data.", ephemeral=True)
            return

        try:
            nation = df.iloc[0]
            num_cities = nation.get("num_cities", 999999)
            cities = nation.get("cities", [])

            grouped = {}
            for city in cities:
                infra = city.get("infrastructure", 0)
                id = city.get("id", 0)
                build_signature = tuple((key, city.get(key, 0)) for key in BUILD_KEYS)
                grouped.setdefault(build_signature, []).append((city["name"], infra, id))

            blocks = []

            for build, city_list in grouped.items():
                count = len(city_list)
                header = f"🏙️ **{count}/{num_cities} have this build:**\n"
                build_lines = [f"🔗 [{name} (Infra: {infra})](https://politicsandwar.com/city/id={id})" for name, infra, id in city_list]

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

    @discord.ui.button(label="Projects", style=discord.ButtonStyle.secondary)
    async def projects_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
    
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
    
            await interaction.edit_original_response(embed=embed, view=self)
    
        except Exception as e:
            await interaction.followup.send(f"❌ Error while formatting projects: {e}", ephemeral=True)

    @discord.ui.button(label="Militarisation", style=discord.ButtonStyle.primary)
    async def wartime_mmr_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        alliance_id = self.nation_id
        embed, file = await average_militarisation(interaction, alliance_id, 'nation')
        self.clear_items()
        self.add_item(BackButton(self.original_embed, self))
        self.add_item(CloseButton())
        await interaction.edit_original_response(embed=embed, attachments=[file], view=self)
                
    @discord.ui.button(label="Resources/Warchest", style=discord.ButtonStyle.success)
    async def audit_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        nation_id = self.nation_id
        who = self.who
        async def is_banker():
            GOV_ROLE = get_gov_role(interaction)
            return (
                any(role.name == GOV_ROLE for role in interaction.user.roles)
            )
        if interaction.user.id != who:
            if not await is_banker():
                await interaction.followup.send("❌ You don't have the rights")
                return
    
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
            nation_name, num_cities, food, money, gasoline, munitions, steel, aluminum, bauxite, lead, iron, oil, coal, uranium = get_resources(nation_id, interaction)
    
            embed = discord.Embed(
                title="Warchest Audit",
                description=f"**Nation:** {nation['nation_name']} (`{nation_id}`)\n"
                            f"**🏭 ALL RESOURCES:**\n"
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
                            f"**Missing Materials:**\n{description}",
                color=discord.Color.gold()
            )
            embed.set_footer(
                text="Brought to you by Sumnor",
                icon_url="https://i.ibb.co/Kpsfc8Jm/jack.webp"
            )
    
            self.clear_items()
            self.add_item(BackButton(self.original_embed, self))  
            self.add_item(CloseButton())
    
            await interaction.edit_original_response(embed=embed, view=self)
    
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
                text="Brought to you by Sumnor",
                icon_url="https://i.ibb.co/Kpsfc8Jm/jack.webp"
            )
    
            
            self.clear_items()
            self.add_item(BackButton(self.original_embed, self))  
            self.add_item(CloseButton())
    
            await interaction.edit_original_response(embed=embed, view=self)
    
        except Exception as e:
            await interaction.followup.send(f"❌ An error occurred during MMR audit: {e}", ephemeral=True)

    @discord.ui.button(label="Wars", style=discord.ButtonStyle.red)
    async def wars_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        nation_id = self.nation_id
        wars = get_wars_data_sql_by_nation_id(nation_id)
    
        if not wars:
            embed = discord.Embed(
                title=f"WARS FOR {nation_id}",
                description="No active wars found.",
                colour=discord.Colour.dark_grey()
            )
            await interaction.edit_original_response(embed=embed)
            return
    
        wars_per_page = 20
        self.pages = [wars[i:i + wars_per_page] for i in range(0, len(wars), wars_per_page)]
        self.current_page = 0
        embed = discord.Embed(
            title=f"WARS FOR {nation_id} (Page {self.current_page + 1}/{len(self.pages)})",
            colour=discord.Colour.dark_grey()
        )
    
        for war in self.pages[self.current_page]:
            war_id = war.get('id')
            attacker_emojis, defender_emojis = [], []
    
            groundcontrol = war.get('groundcontrol')
            airsuperiority = war.get('airsuperiority')
            navalblockade = war.get('navalblockade')
    
            attacker_nation_name = war.get('attacker_nation_name')
            attacker_id = war.get('attacker_id')
            attacker_alliance_name = war.get('attacker_alliance_name')
            attacker_alliance_id = war.get('attacker_alliance_id')
    
            defender_nation_name = war.get('defender_nation_name')
            defender_id = war.get('defender_id')
            defender_alliance_name = war.get('defender_alliance_name')
            defender_alliance_id = war.get('defender_alliance_id')
    
            if groundcontrol == attacker_id:
                attacker_emojis.append('🪖')
            elif groundcontrol == defender_id:
                defender_emojis.append('🪖')
    
            if airsuperiority == attacker_id:
                attacker_emojis.append('✈️')
            elif airsuperiority == defender_id:
                defender_emojis.append('✈️')
    
            if navalblockade == attacker_id:
                attacker_emojis.append('🚢')
            elif navalblockade == defender_id:
                defender_emojis.append('🚢')
    
            if attacker_emojis:
                attacker_nation_name = f"{attacker_nation_name} ({''.join(attacker_emojis)})"
            if defender_emojis:
                defender_nation_name = f"{defender_nation_name} ({''.join(defender_emojis)})"
    
            if attacker_alliance_name:
                attacker = f"[{attacker_nation_name}](https://www.politicsandwar.com/nation/id={attacker_id}) ([{attacker_alliance_name}](https://www.politicsandwar.com/alliance/id={attacker_alliance_id}))"
            else:
                attacker = f"[{attacker_nation_name}](https://www.politicsandwar.com/nation/id={attacker_id})"
    
            if defender_alliance_name:
                defender = f"[{defender_nation_name}](https://www.politicsandwar.com/nation/id={defender_id}) ([{defender_alliance_name}](https://www.politicsandwar.com/alliance/id={defender_alliance_id}))"
            else:
                defender = f"[{defender_nation_name}](https://www.politicsandwar.com/nation/id={defender_id})"
    
            embed.add_field(
                name=f"--------------------------------------------------------------------------",
                value=f"[War: {war_id}](https://politicsandwar.com/nation/war/timeline/war={war_id}) | Type: {war.get('war_type')} | Attacker: {attacker} | Defender: {defender}",
                inline=False
            )
    
        self.clear_items()
        self.add_item(PrevPageButton())
        self.add_item(NextPageButton())
        self.add_item(BackButton(self.original_embed, self))
        await interaction.edit_original_response(embed=embed, view=self)

    @discord.ui.button(label="Trade Records", style=discord.ButtonStyle.green)
    async def trades_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(
            TradeModal(
                self.nation_id, 
                self.original_embed, 
                self, 
                interaction.channel_id,
                interaction.message.id
            )
        )

    @discord.ui.button(label="Bank Records", style=discord.ButtonStyle.green)
    async def bank_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(
            BankModal(
                self.nation_id, 
                self.original_embed, 
                self, 
                interaction.channel_id,
                interaction.message.id,
                is_nation=True
            )
        ) 
