import discord
import requests
from collections import defaultdict
from datetime import datetime
import matplotlib.pyplot as plt
from settings.settings_multi import get_api_key_for_interaction
from databases.sql.data_puller import (
    get_nations_data_sql_by_alliance_id,
    get_cities_data_sql_by_nation_id,
    get_bank_data_sql_by_everything,
    get_treaties_data_sql_by_alliance_id
)

class PrevButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="◀ Previous", style=discord.ButtonStyle.secondary)
    
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        view = self.view
        view.current_page -= 1
        
        # Update embed with new page
        description = view.pages[view.current_page]
        embed = interaction.message.embeds[0]
        
        # Rebuild description with members
        leaders = view.leaders if hasattr(view, 'leaders') else []
        officers = view.officers if hasattr(view, 'officers') else []
        
        new_description = ""
        if leaders:
            new_description += "**👑 Leaders:**\n" + "\n".join(view.format_member(m) for m in leaders) + "\n\n"
        if officers:
            new_description += "**🎖️ Officers:**\n" + "\n".join(view.format_member(m) for m in officers) + "\n\n"
        new_description += f"**👥 Members ({view.total_regular}):**\n" + "\n".join(description)
        
        embed.description = new_description[:4096]
        
        # Update buttons
        view.clear_items()
        if view.current_page > 0:
            view.add_item(PrevButton())
        if view.current_page < len(view.pages) - 1:
            view.add_item(NextButton())
        view.add_item(BackButton(view.original_embed, view))
        view.add_item(CloseButton())
        
        await interaction.edit_original_response(embed=embed, view=view)


class NextButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Next ▶", style=discord.ButtonStyle.secondary)
    
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        view = self.view
        view.current_page += 1
        
        # Update embed with new page
        description = view.pages[view.current_page]
        embed = interaction.message.embeds[0]
        
        # Rebuild description with members
        leaders = view.leaders if hasattr(view, 'leaders') else []
        officers = view.officers if hasattr(view, 'officers') else []
        
        new_description = ""
        if leaders:
            new_description += "**👑 Leaders:**\n" + "\n".join(view.format_member(m) for m in leaders) + "\n\n"
        if officers:
            new_description += "**🎖️ Officers:**\n" + "\n".join(view.format_member(m) for m in officers) + "\n\n"
        new_description += f"**👥 Members ({view.total_regular}):**\n" + "\n".join(description)
        
        embed.description = new_description[:4096]
        
        # Update buttons
        view.clear_items()
        if view.current_page > 0:
            view.add_item(PrevButton())
        if view.current_page < len(view.pages) - 1:
            view.add_item(NextButton())
        view.add_item(BackButton(view.original_embed, view))
        view.add_item(CloseButton())
        
        await interaction.edit_original_response(embed=embed, view=view)


class BackButton(discord.ui.Button):
    def __init__(self, original_embed, parent_view):
        super().__init__(label="⬅ Back", style=discord.ButtonStyle.secondary)
        self.original_embed = original_embed
        self.parent_view = parent_view
    
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        # Reset view to original state
        self.parent_view.clear_items()
        self.parent_view.add_item(discord.ui.Button(label="Members", style=discord.ButtonStyle.primary, custom_id="members"))
        self.parent_view.add_item(discord.ui.Button(label="Average Build", style=discord.ButtonStyle.secondary, custom_id="avg_build"))
        self.parent_view.add_item(discord.ui.Button(label="Bank Records", style=discord.ButtonStyle.success, custom_id="bank"))
        self.parent_view.add_item(discord.ui.Button(label="Possible Offshores", style=discord.ButtonStyle.secondary, custom_id="offshore"))
        self.parent_view.add_item(discord.ui.Button(label="Tax Revenue", style=discord.ButtonStyle.green, custom_id="tax"))
        
        await interaction.edit_original_response(embed=self.original_embed, view=self.parent_view)


class CloseButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="✖ Close", style=discord.ButtonStyle.danger)
    
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await interaction.delete_original_response()


class AllianceBankModal(discord.ui.Modal, title="Alliance Bank Records"):
    days = discord.ui.TextInput(
        label="Filters",
        placeholder="Filter by ID (/ for all)",
        required=False,
        default="/"
    )

    def __init__(self, alliance_id, original_embed, parent_view, channel_id, message_id):
        super().__init__()
        self.alliance_id = alliance_id
        self.original_embed = original_embed
        self.parent_view = parent_view
        self.channel_id = channel_id
        self.message_id = message_id

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        try:
            days = self.days.value if self.days.value else "/"
        except ValueError:
            await interaction.followup.send("❌ Invalid number of days", ephemeral=True)
            return
        if days == '/':
            transactions = get_bank_data_sql_by_everything(days, self.alliance_id, days)
        else:
            transactions = get_bank_data_sql_by_everything(days, self.alliance_id, "SMTH")
        
        if not transactions:
            embed = discord.Embed(
                title=f"Bank Records - Last {days} days",
                description="No transactions found.",
                color=discord.Color.greyple()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # Group transactions
        deposits = [t for t in transactions if t.get('receiver_id') == int(self.alliance_id)]
        withdrawals = [t for t in transactions if t.get('sender_id') == int(self.alliance_id)]

        def format_transaction(t):
            date = t.get('date', 'Unknown')
            try:
                dt = datetime.fromisoformat(date.replace('Z', '+00:00'))
                timestamp = f"<t:{int(dt.timestamp())}:R>"
            except:
                timestamp = date

            sender = t.get('sender_name', 'Unknown')
            receiver = t.get('receiver_name', 'Unknown')
            note = t.get('note', 'No note')[:50]
            
            resources = []
            if t.get('money', 0): resources.append(f"${t['money']:,.0f}")
            if t.get('food', 0): resources.append(f"{t['food']:,.0f} food")
            if t.get('coal', 0): resources.append(f"{t['coal']:,.0f} coal")
            if t.get('oil', 0): resources.append(f"{t['oil']:,.0f} oil")
            if t.get('uranium', 0): resources.append(f"{t['uranium']:,.0f} uranium")
            if t.get('lead', 0): resources.append(f"{t['lead']:,.0f} lead")
            if t.get('iron', 0): resources.append(f"{t['iron']:,.0f} iron")
            if t.get('bauxite', 0): resources.append(f"{t['bauxite']:,.0f} bauxite")
            if t.get('gasoline', 0): resources.append(f"{t['gasoline']:,.0f} gasoline")
            if t.get('munitions', 0): resources.append(f"{t['munitions']:,.0f} munitions")
            if t.get('steel', 0): resources.append(f"{t['steel']:,.0f} steel")
            if t.get('aluminum', 0): resources.append(f"{t['aluminum']:,.0f} aluminum")

            return f"{timestamp} | {sender} → {receiver}\n{', '.join(resources)}\n*{note}*\n"

        # Create pages
        transactions_per_page = 10
        dep_pages = [deposits[i:i + transactions_per_page] for i in range(0, len(deposits), transactions_per_page)]
        with_pages = [withdrawals[i:i + transactions_per_page] for i in range(0, len(withdrawals), transactions_per_page)]

        self.parent_view.bank_pages = {
            'deposits': dep_pages,
            'withdrawals': with_pages
        }
        self.parent_view.bank_page_type = 'deposits'
        self.parent_view.bank_current_page = 0

        await self.parent_view.show_bank_page(interaction)


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

    async def show_bank_page(self, interaction):
        pages = self.bank_pages.get(self.bank_page_type, [])
        if not pages:
            await interaction.followup.send("No transactions found.", ephemeral=True)
            return

        page_data = pages[self.bank_current_page]
        description = "\n".join(
            f"**Transaction {i+1}:**\n{self.format_bank_transaction(t)}"
            for i, t in enumerate(page_data)
        )

        embed = discord.Embed(
            title=f"{'Deposits' if self.bank_page_type == 'deposits' else 'Withdrawals'} (Page {self.bank_current_page + 1}/{len(pages)})",
            description=description,
            color=discord.Color.green() if self.bank_page_type == 'deposits' else discord.Color.red()
        )

        self.clear_items()
        
        # Page navigation
        if len(pages) > 1:
            if self.bank_current_page > 0:
                prev_btn = discord.ui.Button(label="◀ Previous", style=discord.ButtonStyle.secondary)
                prev_btn.callback = self.bank_prev_page
                self.add_item(prev_btn)
            if self.bank_current_page < len(pages) - 1:
                next_btn = discord.ui.Button(label="Next ▶", style=discord.ButtonStyle.secondary)
                next_btn.callback = self.bank_next_page
                self.add_item(next_btn)

        # Switch between deposits/withdrawals
        if self.bank_pages.get('deposits') and self.bank_pages.get('withdrawals'):
            switch_btn = discord.ui.Button(
                label=f"Show {'Withdrawals' if self.bank_page_type == 'deposits' else 'Deposits'}",
                style=discord.ButtonStyle.primary
            )
            switch_btn.callback = self.bank_switch_type
            self.add_item(switch_btn)

        self.add_item(BackButton(self.original_embed, self))
        self.add_item(CloseButton())

        await interaction.edit_original_response(embed=embed, view=self)

    def format_bank_transaction(self, t):
        date = t.get('date', 'Unknown')
        try:
            dt = datetime.fromisoformat(date.replace('Z', '+00:00'))
            timestamp = f"<t:{int(dt.timestamp())}:R>"
        except:
            timestamp = date

        sender = t.get('sender_name', 'Unknown')
        receiver = t.get('receiver_name', 'Unknown')
        note = t.get('note', 'No note')[:100]
        
        resources = []
        if t.get('money', 0): resources.append(f"💰 ${t['money']:,.0f}")
        if t.get('food', 0): resources.append(f"🍞 {t['food']:,.0f}")
        if t.get('coal', 0): resources.append(f"🪨 {t['coal']:,.0f}")
        if t.get('oil', 0): resources.append(f"🛢 {t['oil']:,.0f}")
        if t.get('uranium', 0): resources.append(f"☢️ {t['uranium']:,.0f}")
        if t.get('gasoline', 0): resources.append(f"⛽ {t['gasoline']:,.0f}")
        if t.get('munitions', 0): resources.append(f"💥 {t['munitions']:,.0f}")
        if t.get('steel', 0): resources.append(f"🛠️ {t['steel']:,.0f}")
        if t.get('aluminum', 0): resources.append(f"⚙️ {t['aluminum']:,.0f}")

        return f"{timestamp} | **{sender}** → **{receiver}**\n{', '.join(resources)}\n*{note}*"

    async def bank_prev_page(self, interaction: discord.Interaction):
        await interaction.response.defer()
        self.bank_current_page -= 1
        await self.show_bank_page(interaction)

    async def bank_next_page(self, interaction: discord.Interaction):
        await interaction.response.defer()
        self.bank_current_page += 1
        await self.show_bank_page(interaction)

    async def bank_switch_type(self, interaction: discord.Interaction):
        await interaction.response.defer()
        self.bank_page_type = 'withdrawals' if self.bank_page_type == 'deposits' else 'deposits'
        self.bank_current_page = 0
        await self.show_bank_page(interaction)

    @discord.ui.button(label="Members", style=discord.ButtonStyle.primary)
    async def members_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        alliance_id = self.alliance_id
        print(f"Fetching members for alliance_id: {alliance_id}")
        
        # FIXED: The function returns a generator/iterator, collect ALL members
        members_raw = get_nations_data_sql_by_alliance_id(alliance_id)
        
        # Convert to list if it's an iterator/generator
        members = []
        if hasattr(members_raw, '__iter__') and not isinstance(members_raw, (dict, str)):
            # It's iterable but not a dict or string
            for member in members_raw:
                if isinstance(member, dict):
                    members.append(member)
        elif isinstance(members_raw, dict):
            # Single dict returned
            members = [members_raw]
        elif isinstance(members_raw, list):
            members = members_raw
        
        print(f"Total members collected: {len(members)}")
        
        if not members:
            await interaction.followup.send("❌ No members found", ephemeral=True)
            return

        # Group by position (using UPPER since positions are uppercase)
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
            # Paginate regular members if too many
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
        self.add_item(BackButton(self.original_embed, self))
        self.add_item(CloseButton())

        await interaction.edit_original_response(embed=embed, view=self)

    @discord.ui.button(label="Average Build", style=discord.ButtonStyle.secondary)
    async def avg_build_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        alliance_id = self.alliance_id
        print(f"Fetching members for alliance_id: {alliance_id}")
        
        # FIXED: Collect ALL members from iterator
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
            
        # Calculate totals and averages per nation + per city
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
            
            # Get cities for this nation
            cities_raw = get_cities_data_sql_by_nation_id(nid)
            
            # Handle cities being an iterator/generator
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
            
            # Add military from nation data
            for key in ['soldiers','tanks','aircraft','ships','missiles','nukes']:
                totals[key] += m.get(key, 0)
        
        avg_data = {k: totals[k]/totals['cities'] if totals['cities'] > 0 else 0 for k in totals}
        avg_data_c = {k: totals[k]/total_members if totals['cities'] > 0 else 0 for k in totals}

        # Build embed
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
        self.add_item(BackButton(self.original_embed, self))
        self.add_item(CloseButton())

        await interaction.edit_original_response(embed=embed, view=self)

    @discord.ui.button(label="📊 Wartime MMR", style=discord.ButtonStyle.primary)
    async def wartime_mmr_button(self, interaction: discord.Interaction, button: discord.ui.Button):
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
        totals = {k: 0 for k in ['cities','munitions_factory','barracks','factory','hangar','drydock','soldiers','tanks','aircraft','ships','missiles','nukes']}

        # --- collect data ---
        grouped = {}

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

            city_count = len(cities)
            totals['cities'] += city_count

            # sum city infra counts
            for c in cities:
                for key in ['barracks','factory','hangar','drydock']:
                    totals[key] += c.get(key, 0)

            # sum national totals
            for key in ['soldiers','tanks','aircraft','ships','missiles','nukes']:
                totals[key] += m.get(key, 0)

            # --- group by city count ---
            if city_count not in grouped:
                grouped[city_count] = {'soldiers': [], 'tanks': [], 'aircraft': [], 'ships': []}
            barracks = sum(c.get('barracks',0) for c in cities)
            factories = sum(c.get('factory',0) for c in cities)
            hangars = sum(c.get('hangar',0) for c in cities)
            drydocks = sum(c.get('drydock',0) for c in cities)

            def cap(val, max_val):
                return (val / max_val * 100) if max_val else 0

            grouped[city_count]['soldiers'].append(cap(m.get('soldiers',0), barracks*3000))
            grouped[city_count]['tanks'].append(cap(m.get('tanks',0), factories*250))
            grouped[city_count]['aircraft'].append(cap(m.get('aircraft',0), hangars*15))
            grouped[city_count]['ships'].append(cap(m.get('ships',0), drydocks*5))

        # --- average per city group ---
        import numpy as np
        import io
        import matplotlib.pyplot as plt

        city_groups = sorted(grouped.keys())
        soldiers_perc = [np.mean(grouped[c]['soldiers']) for c in city_groups]
        tanks_perc = [np.mean(grouped[c]['tanks']) for c in city_groups]
        aircraft_perc = [np.mean(grouped[c]['aircraft']) for c in city_groups]
        ships_perc = [np.mean(grouped[c]['ships']) for c in city_groups]
        city_labels = [f"C{c}" for c in city_groups]

        # --- total militarisation ---
        def cap(val, max_val):
            return (val / max_val * 100) if max_val else 0

        current_pct = {
            'soldiers': cap(totals['soldiers'], totals['barracks']*3000),
            'tanks': cap(totals['tanks'], totals['factory']*250),
            'aircraft': cap(totals['aircraft'], totals['hangar']*15),
            'ships': cap(totals['ships'], totals['drydock']*5)
        }

        total_capacity = (
            totals['barracks']*3000 +
            totals['factory']*250 +
            totals['hangar']*15 +
            totals['drydock']*5
        )

        total_per = current_pct['soldiers'] + current_pct['tanks'] + current_pct['aircraft'] + current_pct['ships']
        tm_percent = (total_per / 4) if total_capacity else 0

        # --- plotting ---
        fig, axs = plt.subplots(2, 1, figsize=(12,7), gridspec_kw={'height_ratios':[3,1]})

        axs[0].plot(city_labels, soldiers_perc, label='Soldiers', color='#5cb85c', marker='o')
        axs[0].plot(city_labels, tanks_perc, label='Tanks', color='#0275d8', marker='o')
        axs[0].plot(city_labels, aircraft_perc, label='Aircraft', color='#f0ad4e', marker='o')
        axs[0].plot(city_labels, ships_perc, label='Ships', color='#d9534f', marker='o')
        axs[0].set_ylabel("% Readiness")
        axs[0].set_title("📈 Readiness by City Count")
        axs[0].legend()
        axs[0].set_ylim(0,100)

        axs[1].bar(["MMR Current","Wartime Goal"], [tm_percent, 100], color=["#0275d8","#d9534f"])
        axs[1].set_ylim(0,120)
        axs[1].set_ylabel("% Total")
        axs[1].set_title("📊 Total Readiness Comparison")

        plt.tight_layout()
        buf = io.BytesIO()
        plt.savefig(buf, format="png", dpi=150)
        buf.seek(0)
        plt.close(fig)

        file = discord.File(buf, filename="wartime_mmr.png")

        # --- exact same description block ---
        description = (
            f"**MMR (Average per Alliance):**\n"
            f"Barracks: {totals['barracks']:,.2f}\n"
            f"Factories: {totals['factory']:,.2f}\n"
            f"Hangars: {totals['hangar']:,.2f}\n"
            f"Drydocks: {totals['drydock']:,.2f}"
            f"**Alliance Militarisation:**\n"
            f"Total Militarisation: `{tm_percent:,.2f}%`\n"
            f"Soldier Militarization: `{current_pct['soldiers']:,.2f}%`\n"
            f"Tank Militarization: `{current_pct['tanks']:,.2f}%`\n"
            f"Aircraft Militarization: `{current_pct['aircraft']:,.2f}%`\n"
            f"Ship Militarization: `{current_pct['ships']:,.2f}%`\n"
            f"Soldiers: `{totals['soldiers']}/{totals['barracks']*3000}`\n"
            f"Tanks: `{totals['tanks']}/{totals['factory']*250}`\n"
            f"Aircrafts: `{totals['aircraft']}/{totals['hangar']*15}`\n"
            f"Ships: `{totals['ships']}/{totals['drydock']*5}`\n"
            f"**Infra Threats:**\n"
            f"Missiles: `{totals['missiles']}`\n"
            f"Nukes: `{totals['nukes']}`\n"
        )

        embed = discord.Embed(
            title=f"Average Build ({total_members} members)",
            description=description,
            color=discord.Color.purple()
        )
        embed.set_image(url="attachment://wartime_mmr.png")

        self.clear_items()
        self.add_item(BackButton(self.original_embed, self))
        self.add_item(CloseButton())

        await interaction.edit_original_response(embed=embed, attachments=[file], view=self)



    @discord.ui.button(label="Bank Records", style=discord.ButtonStyle.success)
    async def bank_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(
            AllianceBankModal(
                self.alliance_id,
                self.original_embed,
                self,
                interaction.channel_id,
                interaction.message.id
            )
        )

    @discord.ui.button(label="Possible Offshores", style=discord.ButtonStyle.secondary)
    async def offshore_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        
        # Get all bank transactions (last 90 days)
        pull = '/'
        days = 90
        transactions = get_bank_data_sql_by_everything(days, self.alliance_id, pull)
        
        if not transactions:
            await interaction.followup.send("❌ No transactions found", ephemeral=True)
            return

        # Analyze transaction patterns (count-based, not money-based)
        alliance_interactions = defaultdict(lambda: {'sent_count': 0, 'received_count': 0, 'total_money': 0, 'name': 'Unknown'})
        
        for t in transactions:
            sender_id = t.get('sender_id')
            receiver_id = t.get('receiver_id')
            sender_type = t.get('sender_type')
            receiver_type = t.get('receiver_type')
            
            # Only count alliance-to-alliance transactions
            if sender_type != 2 or receiver_type != 2:
                continue
                
            money = t.get('money', 0)
            
            if sender_id == int(self.alliance_id):
                alliance_interactions[receiver_id]['sent_count'] += 1
                alliance_interactions[receiver_id]['total_money'] += money
                alliance_interactions[receiver_id]['name'] = t.get('receiver_name', f'Alliance {receiver_id}')
            elif receiver_id == int(self.alliance_id):
                alliance_interactions[sender_id]['received_count'] += 1
                alliance_interactions[sender_id]['total_money'] += money
                alliance_interactions[sender_id]['name'] = t.get('sender_name', f'Alliance {sender_id}')

        # Calculate offshore probability based on transaction counts
        offshore_candidates = []
        for aa_id, data in alliance_interactions.items():
            total_transactions = data['sent_count'] + data['received_count']
            
            if total_transactions < 3:  # Need at least 3 transactions
                continue
                
            # High sent count ratio = likely offshore
            sent_ratio = data['sent_count'] / total_transactions if total_transactions > 0 else 0
            received_ratio = data['received_count'] / total_transactions if total_transactions > 0 else 0
            
            # Check for treaty relationship
            treaties = get_treaties_data_sql_by_alliance_id(self.alliance_id)
            has_treaty = any(
                t.get('alliance1_id') == aa_id or t.get('alliance2_id') == aa_id
                for t in treaties
            ) if treaties else False
            
            probability = 0
            if sent_ratio > 0.7:  # Mostly outgoing
                probability = min(95, int(sent_ratio * 100))
            elif received_ratio > 0.7:  # Mostly incoming (might be main AA)
                probability = 0
            else:  # Balanced transactions
                probability = 25
                
            # Boost probability if no treaty (random offshore)
            if not has_treaty and probability > 50:
                probability = min(99, probability + 20)
                
            offshore_candidates.append({
                'id': aa_id,
                'name': data['name'],
                'sent_count': data['sent_count'],
                'received_count': data['received_count'],
                'total_money': data['total_money'],
                'total_transactions': total_transactions,
                'probability': probability,
                'has_treaty': has_treaty
            })

        # Sort by probability
        offshore_candidates.sort(key=lambda x: x['probability'], reverse=True)
        
        if not offshore_candidates:
            embed = discord.Embed(
                title="Possible Offshores",
                description="No significant alliance transactions found.",
                color=discord.Color.greyple()
            )
        else:
            description = ""
            for candidate in offshore_candidates[:10]:  # Top 10
                emoji = "🔴" if candidate['probability'] > 50 else "🟡" if candidate['probability'] > 30 else "🟢"
                treaty_marker = " 📜" if candidate['has_treaty'] else ""
                description += (
                    f"{emoji} **[{candidate['name']}](https://politicsandwar.com/alliance/id={candidate['id']})**{treaty_marker}\n"
                    f"Sent: {candidate['sent_count']} txns | Received: {candidate['received_count']} txns\n"
                    f"Total: {candidate['total_transactions']} transactions | ${candidate['total_money']:,.0f} total\n"
                    f"Offshore Probability: **{candidate['probability']}%**\n\n"
                )

            embed = discord.Embed(
                title="Possible Offshores (Last 90 days)",
                description=description[:4096],
                color=discord.Color.orange()
            )
            embed.set_footer(text="📜 = Has treaty relationship | Based on transaction patterns")

        self.clear_items()
        self.add_item(BackButton(self.original_embed, self))
        self.add_item(CloseButton())

        await interaction.edit_original_response(embed=embed, view=self)

    @discord.ui.button(label="Tax Revenue", style=discord.ButtonStyle.green)
    async def revenue_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        
        try:
            API_KEY = get_api_key_for_interaction(interaction)
            GRAPHQL_URL = f"https://api.politicsandwar.com/graphql?api_key={API_KEY}"
            
            # Ensure alliance_id is an integer
            try:
                alliance_id_int = int(self.alliance_id)
            except (ValueError, TypeError):
                await interaction.followup.send("❌ Invalid alliance ID", ephemeral=True)
                return
            
            # GraphQL query for tax revenue
            query = """
            query GetAllianceTaxes($id: [Int]) {
                alliances(id: $id) {
                    data {
                        id
                        name
                        taxBrackets {
                            id
                            bracketName
                            taxRate
                            resource
                            members
                        }
                    }
                }
            }
            """
            
            variables = {"id": [alliance_id_int]}
            print(f"GraphQL request - URL: {GRAPHQL_URL}, Variables: {variables}")
            
            response = requests.post(
                GRAPHQL_URL,
                json={"query": query, "variables": variables},
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
            
            print(f"GraphQL response: {data}")
            
            # Check for errors in response
            if "errors" in data:
                error_msg = data["errors"][0].get("message", "Unknown error")
                await interaction.followup.send(f"❌ API Error: {error_msg}", ephemeral=True)
                return
            
            alliance_data = data.get("data", {}).get("alliances", {}).get("data", [])
            if not alliance_data:
                await interaction.followup.send(f"❌ Alliance {alliance_id_int} not found in API response", ephemeral=True)
                return

            alliance = alliance_data[0]
            tax_brackets = alliance.get("taxBrackets", [])
            
            if not tax_brackets:
                embed = discord.Embed(
                    title="Tax Revenue",
                    description="No tax brackets found.",
                    color=discord.Color.greyple()
                )
            else:
                description = ""
                total_members = 0
                
                for bracket in tax_brackets:
                    name = bracket.get("bracketName", "Unnamed")
                    rate = bracket.get("taxRate", 0)
                    resource = bracket.get("resource", 0)
                    members = bracket.get("members", 0)
                    total_members += members
                    
                    description += (
                        f"**{name}**\n"
                        f"💰 Money Tax: {rate}% | 📦 Resource Tax: {resource}%\n"
                        f"👥 Members: {members}\n\n"
                    )
                
                # Get member data for revenue estimation
                members_raw = get_nations_data_sql_by_alliance_id(self.alliance_id)
                
                # Collect all members
                member_list = []
                if hasattr(members_raw, '__iter__') and not isinstance(members_raw, (dict, str)):
                    for member in members_raw:
                        if isinstance(member, dict):
                            member_list.append(member)
                elif isinstance(members_raw, dict):
                    member_list = [members_raw]
                elif isinstance(members_raw, list):
                    member_list = members_raw
                
                total_score = sum(m.get('score', 0) for m in member_list if isinstance(m, dict))
                avg_score = total_score / len(member_list) if member_list else 0
                
                # Rough revenue estimate (very approximate)
                # Average nation makes ~$200k per day per 1000 score
                estimated_daily_revenue = (avg_score / 1000) * 200000 * len(member_list)
                
                # Calculate average tax rate
                if total_members > 0:
                    weighted_money_tax = sum(
                        b.get('taxRate', 0) * b.get('members', 0) 
                        for b in tax_brackets
                    ) / total_members
                    weighted_resource_tax = sum(
                        b.get('resource', 0) * b.get('members', 0) 
                        for b in tax_brackets
                    ) / total_members
                else:
                    weighted_money_tax = 0
                    weighted_resource_tax = 0
                
                daily_money_tax = estimated_daily_revenue * (weighted_money_tax / 100)
                
                description += (
                    f"**📊 Estimates (Approximate):**\n"
                    f"Average Money Tax Rate: {weighted_money_tax:.1f}%\n"
                    f"Average Resource Tax Rate: {weighted_resource_tax:.1f}%\n"
                    f"Estimated Daily Money Revenue: ${daily_money_tax:,.0f}\n"
                    f"Estimated Monthly Money Revenue: ${daily_money_tax * 30:,.0f}\n"
                )
                
                embed = discord.Embed(
                    title=f"Tax Revenue - {alliance.get('name')}",
                    description=description[:4096],
                    color=discord.Color.gold()
                )
                embed.set_footer(text="Revenue estimates are approximate based on average nation income")

            self.clear_items()
            self.add_item(BackButton(self.original_embed, self))
            self.add_item(CloseButton())

            await interaction.edit_original_response(embed=embed, view=self)
            
        except Exception as e:
            await interaction.followup.send(f"❌ Error fetching tax data: {e}", ephemeral=True)