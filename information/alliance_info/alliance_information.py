import discord
from information.SharedInformational.avg_mmr import average_militarisation
from information.SharedInformational.banking import BankModal
from settings.bot_instance import API_KEY
import requests
from databases.sql.data_puller import (
    get_nations_data_sql_by_alliance_id,
    get_cities_data_sql_by_nation_id,
    get_treaties_data_sql_by_alliance_id
)
from information.alliance_info.control_buttons import PrevButton, NextButton, BackAAButton, CloseAAButton


class AllianceInfoView(discord.ui.View):
    def __init__(self, alliance_id, original_embed):
        super().__init__(timeout=None)
        self.alliance_id = alliance_id
        self.original_embed = original_embed
        self.pages = []
        self.current_page = 0
        self.bank_pages = {}
        self.bank_page_type = 'deposits'
        self.bank_current_page = 0

    @discord.ui.button(label="Members", style=discord.ButtonStyle.primary)
    async def members_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        alliance_id = self.alliance_id
        print(f"Fetching members for alliance_id: {alliance_id}")
        members_raw = get_nations_data_sql_by_alliance_id(alliance_id)
        members = []
        if hasattr(members_raw, '__iter__') and not isinstance(members_raw, (dict, str)):
            for member in members_raw:
                if isinstance(member, dict):
                    members.append(member)
        elif isinstance(members_raw, dict):
            members = [members_raw]
        elif isinstance(members_raw, list):
            members = members_raw
        
        print(f"Total members collected: {len(members)}")
        
        if not members:
            await interaction.followup.send("❌ No members found", ephemeral=True)
            return
        leaders = [m for m in members if isinstance(m, dict) and m.get('alliance_position', '').upper() == 'LEADER']
        officers = [m for m in members if isinstance(m, dict) and m.get('alliance_position', '').upper() in ['HEIR', 'OFFICER']]
        regular = [m for m in members if isinstance(m, dict) and m.get('alliance_position', '').upper() in ['MEMBER', 'APPLICANT', '']]

        def format_member(m):
            name = m.get('nation_name', 'Unknown')
            nation_id = m.get('id', 'Unknown')
            score = m.get('score', 0)
            cities = m.get('num_cities', m.get('cities', 0))  # FIXED: use num_cities
            return f"[{name}](https://politicsandwar.com/nation/id={nation_id}) - {score:,.2f}⚡ | {cities} cities"

        description = ""
        if leaders:
            description += "**👑 Leaders:**\n" + "\n".join(format_member(m) for m in leaders) + "\n\n"
        if officers:
            description += "**🎖️ Officers:**\n" + "\n".join(format_member(m) for m in officers) + "\n\n"
        if regular:
            member_list = [format_member(m) for m in regular]
            chunks = [member_list[i:i + 20] for i in range(0, len(member_list), 20)]
            self.pages = chunks
            self.current_page = 0
            
            description += f"**👥 Members ({len(regular)}):**\n" + "\n".join(chunks[0])

        embed = discord.Embed(
            title=f"Alliance Members ({len(members)} total)",
            description=description[:4096],
            color=discord.Color.blue()
        )

        self.clear_items()
        if len(self.pages) > 1:
            if self.current_page > 0:
                self.add_item(PrevButton())
            if self.current_page < len(self.pages) - 1:
                self.add_item(NextButton())
        self.add_item(BackAAButton(self.original_embed, self))
        self.add_item(CloseAAButton())

        await interaction.edit_original_response(embed=embed, view=self)

    @discord.ui.button(label="Average Build", style=discord.ButtonStyle.secondary)
    async def avg_build_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        alliance_id = self.alliance_id
        print(f"Fetching members for alliance_id: {alliance_id}")
        members_raw = get_nations_data_sql_by_alliance_id(alliance_id)
        
        members = []
        if hasattr(members_raw, '__iter__') and not isinstance(members_raw, (dict, str)):
            for member in members_raw:
                if isinstance(member, dict):
                    members.append(member)
        elif isinstance(members_raw, dict):
            members = [members_raw]
        elif isinstance(members_raw, list):
            members = members_raw
        
        print(f"Total members collected: {len(members)}")
        
        if not members:
            await interaction.followup.send("❌ No members found", ephemeral=True)
            return
        total_members = len(members)
        totals = {k: 0 for k in ['cities','infrastructure', 'land', 'soldiers','tanks','aircraft','ships','missiles','nukes',
                                 'oil_power', 'wind_power', 'coal_power', 'nuclear_power',
                                 'coal_mine','oil_well','uranium_mine','iron_mine','bauxite_mine',
                                 'police_station', 'hospital','recycling_center','subway','supermarket','bank','shopping_mall','stadium',
                                 'lead_mine','farm','oil_refinery','steel_mill','aluminum_refinery',
                                 'munitions_factory','barracks','factory','hangar','drydock']}
        
        for m in members:
            if not isinstance(m, dict):
                continue
            nid = m.get('id')
            if not nid:
                continue
            cities_raw = get_cities_data_sql_by_nation_id(nid)
            cities = []
            if hasattr(cities_raw, '__iter__') and not isinstance(cities_raw, (dict, str)):
                for city in cities_raw:
                    if isinstance(city, dict):
                        cities.append(city)
            elif isinstance(cities_raw, dict):
                cities = [cities_raw]
            elif isinstance(cities_raw, list):
                cities = cities_raw
            
            totals['cities'] += len(cities) if cities else 0
            
            if cities:
                for c in cities:
                    if not isinstance(c, dict):
                        continue
                    for key in totals.keys():
                        if key != 'cities' and key in c:
                            totals[key] += c.get(key, 0)
            for key in ['soldiers','tanks','aircraft','ships','missiles','nukes']:
                totals[key] += m.get(key, 0)
        
        avg_data = {k: totals[k]/totals['cities'] if totals['cities'] > 0 else 0 for k in totals}
        avg_data_c = {k: totals[k]/total_members if totals['cities'] > 0 else 0 for k in totals}
        description = (
            f"**🏙️ Average Cities:** {avg_data_c['cities']:.2f}\n\n"
            f"**🔋 Power (Average per Alliance):**\n"
            f"⛏️ Coal Power Plants: {avg_data['coal_power']:,.2f}\n"
            f"🛢 Oil Power Plants: {avg_data['oil_power']:,.2f}\n"
            f"☢️ Nuclear Power Plants: {avg_data['nuclear_power']:,.2f}\n"
            f"💨 Wind Power Plants: {avg_data['wind_power']:,.2f}\n"
            f"**🏗️ Raw Resources (Average per Alliance):**\n"
            f"⛏️ Coal Mines: {avg_data['coal_mine']:,.2f}\n"
            f"🛢 Oil Wells: {avg_data['oil_well']:,.2f}\n"
            f"☢️ Uranium Mines: {avg_data['uranium_mine']:,.2f}\n"
            f"🪓 Iron Mines: {avg_data['iron_mine']:,.2f}\n"
            f"⛏️ Bauxite Mines: {avg_data['bauxite_mine']:,.2f}\n"
            f"🔩 Lead Mines: {avg_data['lead_mine']:,.2f}\n"
            f"🌾 Farms: {avg_data['farm']:,.2f}\n\n"
            f"**🏭 Manufacturing (Average per Alliance):**\n"
            f"⛽ Oil Refineries: {avg_data['oil_refinery']:,.2f}\n"
            f"🛠️ Steel Mills: {avg_data['steel_mill']:,.2f}\n"
            f"⚙️ Aluminum Refineries: {avg_data['aluminum_refinery']:,.2f}\n"
            f"💥 Munitions Factories: {avg_data['munitions_factory']:,.2f}\n\n"
            f"**👤 Civil (Average per Alliance):**\n"
            f"⚖️ Police Stations: {avg_data['police_station']:,.2f}\n"
            f"🏥 Hospitals: {avg_data['hospital']:,.2f}\n"
            f"♻️ Recycling Centers: {avg_data['recycling_center']:,.2f}\n"
            f"🚅 Subways: {avg_data['subway']:,.2f}\n\n"
            f"**💰 Commerce (Average per Alliance):**\n"
            f"🏪 Supermarkets: {avg_data['supermarket']:,.2f}\n"
            f"🏛️ Banks: {avg_data['bank']:,.2f}\n"
            f"🛒 Shopping Malls: {avg_data['shopping_mall']:,.2f}\n"
            f"🏟 Stadiums: {avg_data['stadium']:,.2f}\n\n"
            f"**🎖️ Military Buildings (Average per Alliance):**\n"
            f"🏰 Barracks: {avg_data['barracks']:,.2f}\n"
            f"🏭 Factories: {avg_data['factory']:,.2f}\n"
            f"🛩️ Hangars: {avg_data['hangar']:,.2f}\n"
            f"⚓ Drydocks: {avg_data['drydock']:,.2f}"
        )

        embed = discord.Embed(
            title=f"Average Build ({total_members} members)",
            description=description,
            color=discord.Color.purple()
        )

        self.clear_items()
        self.add_item(BackAAButton(self.original_embed, self))
        self.add_item(CloseAAButton())

        await interaction.edit_original_response(embed=embed, view=self)

    @discord.ui.button(label="Militarisation", style=discord.ButtonStyle.primary)
    async def wartime_mmr_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        alliance_id = self.alliance_id
        embed, file = await average_militarisation(interaction, alliance_id, 'alliance')
        self.clear_items()
        self.add_item(BackAAButton(self.original_embed, self))
        self.add_item(CloseAAButton())
        await interaction.edit_original_response(embed=embed, attachments=[file], view=self)

    @discord.ui.button(label="Bank Records", style=discord.ButtonStyle.green)
    async def bank_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(
            BankModal(
                self.alliance_id, 
                self.original_embed, 
                self, 
                interaction.channel_id,
                interaction.message.id,
                is_nation=False
            )
        )