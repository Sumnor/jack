import requests
import discord
from discord.ui import View, button
from discord import Button, ButtonStyle
from datetime import datetime
from collections import defaultdict
from utils import get_registration_sheet, get_verify_conf, get_ticket_config
from settings_multi import get_banking_role, get_api_key_for_interaction, get_gov_role, get_grant_channel
from graphql_requests import graphql_cities, get_military, get_general_data, get_resources

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

# participant_view.py
import discord
from typing import List
import aiohttp

async def get_nation_info(nation_id: str, api_key: str) -> dict:
    """Get nation information from PnW API"""
    try:
        url = f"https://api.politicsandwar.com/graphql?api_key={api_key}"
        query = """
        query($id: ID!) {
            nation(id: $id) {
                id
                nation_name
                leader_name
                alliance {
                    id
                    name
                }
                soldiers
                tanks
                aircraft
                ships
                military_power
                resistance
                wars(active: true) {
                    data {
                        id
                        att_points
                        def_points
                        att_resistance
                        def_resistance
                        turns_left
                        war_type
                    }
                }
            }
        }
        """
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json={
                'query': query,
                'variables': {'id': nation_id}
            }) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get('data', {}).get('nation', {})
                else:
                    print(f"API request failed with status {response.status}")
                    return {}
    except Exception as e:
        print(f"Error fetching nation info for {nation_id}: {e}")
        return {}

class ParticipantView(discord.ui.View):
    """View for scrolling through multiple participants' detailed war stats"""
    
    def __init__(self, participants: List[str], api_key: str, war_id: str):
        super().__init__(timeout=None)
        self.participants = participants
        self.api_key = api_key
        self.war_id = war_id
        self.current_index = 0
        
    async def get_current_embed(self) -> discord.Embed:
        """Get detailed embed for current participant"""
        try:
            current_nation_id = self.participants[self.current_index]
            nation_info = await get_nation_info(current_nation_id, self.api_key)
            
            embed = discord.Embed(
                title=f"👤 Participant {self.current_index + 1}/{len(self.participants)} - War {self.war_id}",
                description=f"**{nation_info.get('nation_name', 'Unknown Nation')}**\n*Leader: {nation_info.get('leader_name', 'Unknown')}*",
                color=discord.Color.blue()
            )
            
            # Current resistance and military power
            resistance = nation_info.get('resistance', 0)
            military_power = nation_info.get('military_power', 0)
            
            embed.add_field(
                name="💪 Military Readiness",
                value=f"**Resistance:** {resistance:.1f}%\n**Military Power:** {military_power:,}",
                inline=True
            )
            
            # Current military forces
            soldiers = nation_info.get('soldiers', 0)
            tanks = nation_info.get('tanks', 0)
            aircraft = nation_info.get('aircraft', 0)
            ships = nation_info.get('ships', 0)
            
            embed.add_field(
                name="🏗️ Current Forces",
                value=(
                    f"👥 Soldiers: **{soldiers:,}**\n"
                    f"🚛 Tanks: **{tanks:,}**\n"
                    f"✈️ Aircraft: **{aircraft:,}**\n"
                    f"🚢 Ships: **{ships:,}**"
                ),
                inline=True
            )
            
            embed.add_field(name="\u200b", value="\u200b", inline=True)
            
            # War-specific stats
            wars = nation_info.get('wars', {}).get('data', [])
            current_war = None
            for war in wars:
                if str(war.get('id')) == str(self.war_id):
                    current_war = war
                    break
            
            if current_war:
                # Determine if this nation is attacker or defender
                is_attacker = str(current_war.get('att_id', '')) == current_nation_id
                
                if is_attacker:
                    war_resistance = current_war.get('att_resistance', resistance)
                    war_points = current_war.get('att_points', 0)
                    role = "🗡️ Attacker"
                else:
                    war_resistance = current_war.get('def_resistance', resistance)
                    war_points = current_war.get('def_points', 0)
                    role = "🛡️ Defender"
                
                embed.add_field(
                    name=f"⚔️ War Stats - {role}",
                    value=(
                        f"**Resistance:** {war_resistance:.1f}%\n"
                        f"**MAP Score:** {war_points}\n"
                        f"**Turns Left:** {current_war.get('turns_left', 'Unknown')}\n"
                        f"**War Type:** {current_war.get('war_type', 'Unknown').title()}"
                    ),
                    inline=True
                )
            else:
                embed.add_field(
                    name="⚔️ War Stats",
                    value="War data not found",
                    inline=True
                )
            
            # Alliance info
            alliance = nation_info.get('alliance', {})
            alliance_name = alliance.get('name', 'None')
            alliance_id = alliance.get('id', 'N/A')
            
            embed.add_field(
                name="🏛️ Alliance",
                value=f"**{alliance_name}** (ID: {alliance_id})",
                inline=True
            )
            
            embed.add_field(name="\u200b", value="\u200b", inline=True)
            
            # Military efficiency calculation
            total_military = soldiers + (tanks * 40) + (aircraft * 3) + (ships * 4)
            efficiency = (military_power / total_military * 100) if total_military > 0 else 0
            
            embed.add_field(
                name="📊 Military Efficiency",
                value=f"**{efficiency:.1f}%** efficiency rating\n*Based on unit composition*",
                inline=False
            )
            
            # Color coding based on resistance
            if resistance >= 75:
                embed.color = discord.Color.green()
            elif resistance >= 50:
                embed.color = discord.Color.yellow()
            elif resistance >= 25:
                embed.color = discord.Color.orange()
            else:
                embed.color = discord.Color.red()
            
            embed.set_footer(
                text=f"Use buttons to navigate • Nation ID: {current_nation_id} • Updated: {discord.utils.utcnow().strftime('%H:%M UTC')}"
            )
            
            return embed
            
        except Exception as e:
            print(f"Error creating participant embed: {e}")
            return discord.Embed(
                title="❌ Error",
                description="Failed to load participant information",
                color=discord.Color.red()
            )
    
    @discord.ui.button(label="◀️ Previous", style=discord.ButtonStyle.secondary)
    async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Navigate to previous participant"""
        if self.current_index > 0:
            self.current_index -= 1
        else:
            self.current_index = len(self.participants) - 1
            
        embed = await self.get_current_embed()
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="▶️ Next", style=discord.ButtonStyle.secondary)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Navigate to next participant"""
        if self.current_index < len(self.participants) - 1:
            self.current_index += 1
        else:
            self.current_index = 0
            
        embed = await self.get_current_embed()
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="🔄 Refresh", style=discord.ButtonStyle.primary)
    async def refresh_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Refresh current participant data"""
        await interaction.response.defer()
        embed = await self.get_current_embed()
        await interaction.edit_original_response(embed=embed, view=self)
    
    @discord.ui.button(label="📊 All Stats", style=discord.ButtonStyle.success)
    async def all_stats_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show summary of all participants"""
        await interaction.response.defer()
        
        embed = discord.Embed(
            title=f"📊 All Participants Summary - War {self.war_id}",
            description=f"Overview of all {len(self.participants)} participants",
            color=discord.Color.purple()
        )
        
        try:
            for i, nation_id in enumerate(self.participants):
                nation_info = await get_nation_info(nation_id, self.api_key)
                name = nation_info.get('nation_name', f'Nation {nation_id}')
                resistance = nation_info.get('resistance', 0)
                military_power = nation_info.get('military_power', 0)
                
                # Resistance status emoji
                if resistance >= 75:
                    status = "🟢"
                elif resistance >= 50:
                    status = "🟡"
                elif resistance >= 25:
                    status = "🟠"
                else:
                    status = "🔴"
                
                embed.add_field(
                    name=f"{status} {name}",
                    value=f"**Res:** {resistance:.1f}%\n**MP:** {military_power:,}",
                    inline=True
                )
                
                # Add spacer every 3 participants
                if (i + 1) % 3 == 0:
                    embed.add_field(name="\u200b", value="\u200b", inline=False)
        
        except Exception as e:
            embed.add_field(
                name="❌ Error",
                value="Failed to load summary data",
                inline=False
            )
        
        embed.set_footer(text="Click Previous/Next to view individual details")
        await interaction.edit_original_response(embed=embed, view=self)


class MultiWarParticipantView(discord.ui.View):
    """Enhanced view for participants involved in multiple wars"""
    
    def __init__(self, participants: List[str], api_key: str, all_war_ids: List[str]):
        super().__init__(timeout=None)
        self.participants = participants
        self.api_key = api_key
        self.all_war_ids = all_war_ids
        self.current_participant = 0
        self.current_war = 0
        
    async def get_current_embed(self) -> discord.Embed:
        """Get embed showing current participant's status across all their wars"""
        try:
            current_nation_id = self.participants[self.current_participant]
            nation_info = await get_nation_info(current_nation_id, self.api_key)
            
            embed = discord.Embed(
                title=f"🌟 Multi-War Participant {self.current_participant + 1}/{len(self.participants)}",
                description=f"**{nation_info.get('nation_name', 'Unknown Nation')}**\n*All active wars overview*",
                color=discord.Color.gold()
            )
            
            # Overall stats
            resistance = nation_info.get('resistance', 0)
            military_power = nation_info.get('military_power', 0)
            
            embed.add_field(
                name="💪 Overall Status",
                value=f"**Resistance:** {resistance:.1f}%\n**Military Power:** {military_power:,}",
                inline=True
            )
            
            # Wars this nation is involved in
            wars = nation_info.get('wars', {}).get('data', [])
            relevant_wars = [w for w in wars if str(w.get('id')) in self.all_war_ids]
            
            if relevant_wars:
                war_summary = []
                total_maps = 0
                
                for war in relevant_wars[:5]:  # Show up to 5 wars
                    war_id = war.get('id')
                    turns_left = war.get('turns_left', 'Unknown')
                    
                    # Determine role and get appropriate stats
                    if str(war.get('att_id', '')) == current_nation_id:
                        role = "🗡️"
                        points = war.get('att_points', 0)
                        war_resistance = war.get('att_resistance', resistance)
                    else:
                        role = "🛡️"
                        points = war.get('def_points', 0)
                        war_resistance = war.get('def_resistance', resistance)
                    
                    total_maps += points
                    status = "🟢" if war_resistance > 50 else "🔴" if war_resistance < 25 else "🟡"
                    
                    war_summary.append(f"{role} **War {war_id}**: {points} MAPs {status}")
                
                embed.add_field(
                    name=f"⚔️ Active Wars ({len(relevant_wars)})",
                    value="\n".join(war_summary) + f"\n\n**Total MAPs:** {total_maps}",
                    inline=False
                )
            else:
                embed.add_field(
                    name="⚔️ Wars",
                    value="No active wars found",
                    inline=False
                )
            
            embed.set_footer(
                text=f"Multi-war overview • Use buttons to navigate • Updated: {discord.utils.utcnow().strftime('%H:%M UTC')}"
            )
            
            return embed
            
        except Exception as e:
            print(f"Error creating multi-war participant embed: {e}")
            return discord.Embed(
                title="❌ Error",
                description="Failed to load multi-war participant information",
                color=discord.Color.red()
            )
    
    @discord.ui.button(label="◀️ Prev Nation", style=discord.ButtonStyle.secondary)
    async def previous_nation(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Navigate to previous nation"""
        if self.current_participant > 0:
            self.current_participant -= 1
        else:
            self.current_participant = len(self.participants) - 1
            
        embed = await self.get_current_embed()
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="▶️ Next Nation", style=discord.ButtonStyle.secondary)
    async def next_nation(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Navigate to next nation"""
        if self.current_participant < len(self.participants) - 1:
            self.current_participant += 1
        else:
            self.current_participant = 0
            
        embed = await self.get_current_embed()
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="🔄 Refresh", style=discord.ButtonStyle.primary)
    async def refresh_data(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Refresh current data"""
        await interaction.response.defer()
        embed = await self.get_current_embed()
        await interaction.edit_original_response(embed=embed, view=self)

class HelpView(discord.ui.View):
    def __init__(self, user_id: str, is_gov: bool, called_with_prefix: bool = False):
        super().__init__(timeout=300)
        self.user_id = user_id
        self.is_gov = is_gov
        self.called_with_prefix = called_with_prefix  # track how help was called
        self.current_category = 0

        self.base_categories = [
            {
                "name": "📋 Basic Commands",
                "commands": {
                    "register": "Register yourself to use the bot's features.\nUsage: `/register nation_id: 680627` or `!register -n 680627`",
                    "nation_info": "Shows general nation info.\nUsage: `/nation_info who: @sumnor_the_lazy` or `!nation_info -w @sumnor_the_lazy`"
                }
            },
            {
                "name": "⚔️ Spy & Military",
                "commands": {
                    "war_losses": "Get war details for your last few wars.\nUsage: `/war_losses nation_id: 680627 wars_count: 20` or `!war_losses -n 680627 -w 20`",
                    "see_report": "Find warchest of a registered nation.\nUsage: `/see_report nation: Neprito` or `!see_report -n Neprito`",
                    "list_reports": "See all logged nations.\nUsage: `/list_reports` or `!list_reports`"
                }
            },
            {
                "name": "💰 EA Related",
                "commands": {
                    "request_warchest": "Calculate/request warchest.\nUsage: `/request_warchest percent: 50%` or `!request_warchest -p 50%`",
                    "request_city": "Approximate city costs.\nUsage: `/request_city current_city: 10 target_city: 15` or `!request_city -c 10 -t 15`",
                    "request_infra_grant": "Approx infra costs.\nUsage: `/request_infra_cost current_infra: 10 target_infra: 1500 city_amount: 10` or `!request_infra_cost -c 10 -t 1500 -a 10`",
                    "request_project": "Calculate/request project costs.\nUsage: `/request_project project: Moon Landing` or `!request_project -p Moon Landing`",
                    "request_miscellaneous": "Request materials.\nUsage: `/request_grant food: 18mil uranium: 6k reason: Production` or `!request_grant -f 18mil -u 6k -r Production`",
                    "auto_resources_for_prod_req": "Repeat resource request.\nUsage: `/auto_resources_for_prod_req coal: 100 period: 7` or `!auto_resources_for_prod_req -c 100 -p 7`",
                    "disable_auto_request": "Disable automatic requests.\nUsage: `/disable_auto_request` or `!disable_auto_request`",
                    "auto_week_summary": "Summary of all requests.\nUsage: `/auto_week_summary` or `!auto_week_summary`"
                }
            }
        ]

        self.gov_categories = [
            {
                "name": "🛡️ Government Commands",
                "commands": {
                    "send_message_to_channels": "Send a message to channels.\nUsage: `/send_message_to_channels channels: #channel message: Hi!` or `!send_message_to_channels -c #channel -m Hi!`",
                    "dm_user": "Send a DM to a user.\nUsage: `/dm_user who: @user message: Hello` or `!dm_user -w @user -m Hello`",
                    "create_ticket_message": "Create ticket system.\nUsage: `/create_ticket_message message: Press button title: Create Ticket` or `!create_ticket_message -m Press button -t Create Ticket`"
                }
            },
            {
                "name": "📊 Analytics",
                "commands": {
                    "member_activity": "Pie chart of member activity.\nUsage: `/member_activity` or `!member_activity`",
                    "res_in_m_for_a": "Alliance worth chart.\nUsage: `/res_in_m_for_a mode: Hourly scale: Billions` or `!res_in_m_for_a -m Hourly -s Billions`",
                    "res_details_for_alliance": "Detailed resources & money.\nUsage: `/res_details_for_alliance` or `!res_details_for_alliance`",
                    "war_losses_alliance": "Alliance war losses.\nUsage: `/war_losses_alliance alliance_id: 10259 war_count: 150` or `!war_losses_alliance -a 10259 -w 150`"
                }
            },
            {
                "name": "⚙️ Server Settings",
                "commands": {
                    "register_server_aa": "Register server for alliance features.\nUsage: `/register_server_aa` or `!register_server_aa`",
                    "set_setting": "Set server settings.\nUsage: `/set_setting key: GOV_ROLE value: High Gov` or `!set_setting -k GOV_ROLE -v 'High Gov'`",
                    "get_setting": "Get a setting.\nUsage: `/get_setting key: GOV_ROLE` or `!get_setting -k GOV_ROLE`",
                    "list_settings": "List all settings.\nUsage: `/list_settings` or `!list_settings`"
                }
            }
        ]


        self.categories = self.base_categories.copy()
        if self.is_gov:
            self.categories.extend(self.gov_categories)

        self.update_buttons()

    def update_buttons(self):
        self.clear_items()
        if len(self.categories) > 1:
            self.add_item(self.previous_button)
            self.add_item(self.next_button)

    @discord.ui.button(label="◀️ Previous", style=discord.ButtonStyle.secondary)
    async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("❌ This help menu is not for you!", ephemeral=True)
            return

        self.current_category = (self.current_category - 1) % len(self.categories)
        embed = self.create_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Next ▶️", style=discord.ButtonStyle.secondary)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("❌ This help menu is not for you!", ephemeral=True)
            return

        self.current_category = (self.current_category + 1) % len(self.categories)
        embed = self.create_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    def create_embed(self):
        category = self.categories[self.current_category]

        # build embed
        embed = discord.Embed(
            title=f"{category['name']}",
            color=discord.Color.purple() if self.is_gov else discord.Color.blue(),
            description="Here are the available commands in this category:"
        )

        for command, description in category["commands"].items():
            if self.called_with_prefix:
                # adapt usage lines to !-style instead of /
                usage = description.replace("Usage: `/", "Usage: `!")
                usage = usage.replace("` or `!member_activity`", "` (or use `!member_activity`)")
                embed.add_field(name=f"`{command.replace('/', '!')}`", value=usage, inline=False)
            else:
                # keep as-is for slash commands
                embed.add_field(name=f"`{command}`", value=description, inline=False)

        # add quick how-to for optional args only if prefix version
        if self.called_with_prefix:
            embed.add_field(
                name="ℹ️ Using `!` commands with optional arguments",
                value="Use `-n` to skip arguments (by first letter).\n"
                      "If multiple share the same letter, use `-n1`, `-n2`, etc.",
                inline=False
            )

        embed.set_footer(
            text=f"Page {self.current_category + 1}/{len(self.categories)} • Brought to you by Sumnor",
            icon_url="https://i.ibb.co/Kpsfc8Jm/jack.webp"
        )

        return embed

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True

class NationInfoView(discord.ui.View):
    def __init__(self, nation_id, original_embed, who=None):
        super().__init__(timeout=None)
        self.who = who
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

        self.add_item(BackButton(self.original_embed, self))
        self.add_item(CloseButton())

        await interaction.edit_original_response(embed=embed, view=self)

    @discord.ui.button(label="Show Builds", style=discord.ButtonStyle.primary)
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

    @discord.ui.button(label="Show Projects", style=discord.ButtonStyle.secondary)
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
                
    @discord.ui.button(label="Warchest", style=discord.ButtonStyle.success)
    async def audit_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        nation_id = self.nation_id
        who = self.who
        async def is_banker():
            GOV_ROLE = get_gov_role(interaction)
            return (
                any(role.name == GOV_ROLE for role in interaction.user.roles)
            )
        if interaction.user.id != who.id:
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

class PrevPageButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="⬅ Prev", style=discord.ButtonStyle.secondary)

    async def callback(self, interaction: discord.Interaction):
        view: NationInfoView = self.view
        if view.current_page > 0:
            view.current_page -= 1
            try:
                await view.show_current_page(interaction)
            except discord.NotFound:
                await interaction.response.send_message("This interaction has expired.", ephemeral=True)


class NextPageButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Next ➡", style=discord.ButtonStyle.secondary)

    async def callback(self, interaction: discord.Interaction):
        view: NationInfoView = self.view
        if view.current_page < len(view.pages) - 1:
            view.current_page += 1
            try:
                await view.show_current_page(interaction)
            except discord.NotFound:
                await interaction.response.send_message("This interaction has expired.", ephemeral=True)


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
        self.parent_view.add_item(self.parent_view.mmr_button)
        self.parent_view.add_item(CloseButton())

        try:
            await interaction.response.edit_message(embed=self.original_embed, view=self.parent_view)
        except discord.NotFound:
            await interaction.response.send_message(embed=self.original_embed, view=self.parent_view, ephemeral=True)


class CloseButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Close", style=discord.ButtonStyle.danger)

    async def callback(self, interaction: discord.Interaction):
        try:
            await interaction.message.delete()
        except (discord.NotFound, discord.Forbidden):
            try:
                # Fallback: try to edit the message to show it's closed
                await interaction.response.edit_message(content="This interaction has been closed.", embed=None, view=None)
            except:
                pass
        finally:
            self.view.stop()

class BlueGuy(discord.ui.View):
    def __init__(self, category=None, data=None, guild_id=None):
        super().__init__(timeout=None)
        self.category = category
        self.data = data or {}
        self.guild_id = guild_id

    @discord.ui.button(label="Request Grant", style=discord.ButtonStyle.green, custom_id="req_money_needed")
    async def send_request(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        person = str(self.data.get("person", None))
        print(person)
        presser = str(interaction.user.id)
        print(presser)
        if presser != person:
            if presser not in ["1378012299507269692", "1148678095176474678"]:
                await interaction.followup.send(f"Only the requester (<@{person}> in this case) may press the button", ephemeral=True)
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

        
        description_lines = [f"**Nation:** 🔗 [{nation_name}](https://politicsandwar.com/nation/id={nation_id})", "**Request:**"]
        if materials:
            for name, amount in materials.items():
                description_lines.append(f"{name}: {amount:,.0f}")
        else:
            description_lines.append("None")

        description_lines.append(f"\n**Requested by:** <@{presser}>")
        embed.description = "\n".join(description_lines)

        now = datetime.now()
        unix_timestamp = int(now.timestamp())
        embed.add_field(name="**Reason**", value=reason, inline=False)
        embed.add_field(name="**Submited**", value=f"<t:{unix_timestamp}:R>", inline=False)
        embed.add_field(name="**Note**", value=note, inline=False)

        
        image_url = "https://i.ibb.co/Kpsfc8Jm/jack.webp"
        embed.set_footer(text="Brought to you by Sumnor", icon_url=image_url)

        await interaction.edit_original_response(embed=embed, view=GrantView())

class GrantView(View):
    def __init__(self):
        super().__init__(timeout=None)

    async def is_government_member(self, interaction):
        BANKER = get_banking_role(interaction)
        if BANKER:
            return (
            any(role.name == BANKER for role in interaction.user.roles)
            )
        else:
            return None

    @button(label="✅ Sent", style=discord.ButtonStyle.green, custom_id="grant_approve")
    async def approve_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        if not await self.is_government_member(interaction):
            BANKER = get_banking_role(interaction)
            if BANKER:
                try:
                    await interaction.followup.send("❌ You need the 'Banker' role to approve grant requests.", ephemeral=True)
                except discord.NotFound:
                    pass  
                return

        try:
            embed = interaction.message.embeds[0]
            embed.color = discord.Color.green()
            embed.description += f"\n**Status:** ✅ **GRANT SENT**"

            image_url = "https://i.ibb.co/Kpsfc8Jm/jack.webp"
            embed.set_footer(text="Brought to you by Sumnor", icon_url=image_url)

            await interaction.edit_original_response(embed=embed, view=None)

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
        await interaction.response.defer()
        if not await self.is_government_member(interaction):
            BANKER = get_banking_role(interaction)
            if BANKER:
                try:
                    await interaction.followup.send("❌ You need the 'Banker' role to approve grant requests.", ephemeral=True)
                except discord.NotFound:
                    pass  
                return

        try:
            embed = interaction.message.embeds[0]
            embed.color = discord.Color.orange()
            embed.description += f"\n**Status:** 🕒 **DELAYED**"
            image_url = "https://i.ibb.co/Kpsfc8Jm/jack.webp"
            embed.set_footer(text=f"Brought to you by Sumnor", icon_url=image_url)

            new_view = GrantView()
            new_view.remove_item(new_view.children[1]) 

            await interaction.edit_original_response(embed=embed, view=new_view)
            await interaction.message.pin()
            await interaction.followup.send("✅ Grant delayed and message pinned.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Error: `{e}`", ephemeral=True)

    @button(label="❌ Deny", style=discord.ButtonStyle.red, custom_id="grant_denied")
    async def deny_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        if not await self.is_government_member(interaction):
            BANKER = get_banking_role(interaction)
            if BANKER:
                try:
                    await interaction.followup.send("❌ You need the 'Banker' role to approve grant requests.", ephemeral=True)
                except discord.NotFound:
                    pass  
                return
        try:
            embed = interaction.message.embeds[0]
            embed.color = discord.Color.red()
            embed.description += f"\n**Status:** ❌ **GRANT DENIED**"
            image_url = "https://i.ibb.co/Kpsfc8Jm/jack.webp"
            embed.set_footer(text=f"Brought to you by Sumnor", icon_url=image_url)
            await interaction.edit_original_response(embed=embed, view=None)
        except Exception as e:
            await interaction.followup.send(f"❌ Error: `{e}`", ephemeral=True)

class TicketButtonView(View):
    def __init__(self, message_id: int = None):
        super().__init__(timeout=None)
        self.message_id = message_id

    @button(label="🎟️ Open Ticket", style=ButtonStyle.primary, custom_id="ticket_open")
    async def open_ticket(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer(ephemeral=True)
        try:
            
            guild_id = str(interaction.guild.id)
            message_id = str(interaction.message.id)
            reg_sheet = get_registration_sheet(guild_id)
            verify_config = get_verify_conf(message_id)
            verify = verify_config['verify']
            print(verify)
            records = reg_sheet.get_all_records()
            user_row = next(
                (r for r in records if str(r.get("DiscordID")) == str(interaction.user.id)),
                None
            )
            if verify == "True":
                if not user_row:
                    await interaction.followup.send("❌ You are not registered.", ephemeral=True)
                    return

                nation_id = user_row.get("NationID")
                if not nation_id:
                    await interaction.followup.send("❌ Nation ID not found in your registration.", ephemeral=True)
                    return
                data = get_military(nation_id, interaction)
                cities = get_general_data(nation_id, interaction)
                if data is None:
                    nation_name = "unknown-nation"
                    leader_name = "Leader"
                    city_count = "00"
                else:
                    nation_name, leader_name = data[0], data[1]
                    city_count = cities[4]
            else:
                nation_name = interaction.user.name


            guild = interaction.guild
            if not guild:
                await interaction.followup.send("❌ Must be used in a server.", ephemeral=True)
                return
            ticket_config = None
            welcome_message = ""
            category = None
            
            if self.message_id:
                ticket_config = get_ticket_config(message_id)
            
            if ticket_config and ticket_config.get('category'):
                category_id = ticket_config['category']
                
                category = discord.utils.get(guild.categories, id=category_id)
                if not category:
                    category = guild.get_channel(category_id)
                    if category and not isinstance(category, discord.CategoryChannel):
                        category = None
                
                welcome_message = ticket_config.get('message', '')
            
            if not category or not isinstance(category, discord.CategoryChannel):
                await interaction.followup.send("❌ Ticket category not found.", ephemeral=True)
                return
            
            role_name = get_gov_role(interaction)
            GOV_ROLE = discord.utils.get(guild.roles, name=role_name)
            if not GOV_ROLE:
                return await interaction.followup.send("Define a GOV_ROLE using `/set_setting` first")

            overwrites = {
                guild.default_role: discord.PermissionOverwrite(view_channel=False),
                interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True),
                guild.me: discord.PermissionOverwrite(view_channel=True),
                GOV_ROLE: discord.PermissionOverwrite(view_channel=True),
            }

            if verify == "True":
                channel_name = f"{city_count}︱{nation_name.replace(' ', '-').lower()}"
                ticket_channel = await guild.create_text_channel(
                    name=channel_name,
                    category=category,
                    overwrites=overwrites,
                    reason=f"Ticket opened by {interaction.user}"
                )

                try:
                    await interaction.user.edit(nick=f"{leader_name} | {nation_id}")
                except discord.Forbidden:
                    print("Missing permissions to change nickname")
            else:
                channel_name = f"{nation_name.replace(' ', '-').lower()}"
                ticket_channel = await guild.create_text_channel(
                    name=channel_name,
                    category=category,
                    overwrites=overwrites,
                    reason=f"Ticket opened by {interaction.user}"
                )

            if welcome_message:
                await ticket_channel.send(f"{welcome_message}\n ||@everyone||")
            else:
                await ticket_channel.send("Welcome to your ticket! ||@everyone||")
            if verify == "True":
                await ticket_channel.send(f"NATION LINK: https://politicsandwar.com/nation/id={nation_id}")
            await interaction.followup.send(
                f"✅ Ticket created: {ticket_channel.mention}", ephemeral=True
            )

        except Exception as e:
            print(f"[Ticket Error] {e}")
            await interaction.followup.send("❌ Failed to create ticket.", ephemeral=True)

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

        sheet = get_registration_sheet(guild_id)
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
            image_url = "https://i.ibb.co/Kpsfc8Jm/jack.webp"
            embed.set_footer(text="Brought to you by Sumnor", icon_url=image_url)

            await channel.send(embed=embed, view=GrantView())

        await interaction.followup.send(f"✅ Processed {color_emoji} requests.")

def extract_cities_from_df(df):
    if df is None or df.empty:
        return None
    try:
        cities = df.at[0, "cities"]
        return cities
    except Exception as e:
        print(f"Error extracting cities from df: {e}")
        return None
