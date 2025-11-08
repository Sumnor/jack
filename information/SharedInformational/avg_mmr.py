from databases.sql.data_puller import get_nations_data_sql_by_alliance_id, get_cities_data_sql_by_nation_id, get_nations_data_sql_by_nation_id, get_alliances_data_sql_by_id
import discord

from settings.bot_instance import bot
import aiohttp
import io
import numpy as np
import matplotlib.pyplot as plt
import discord

async def fetch_graphql(query, variables=None):
    api_key = getattr(bot, "api_key", None)
    if not api_key:
        raise ValueError("API key not set in bot_instance")

    async with aiohttp.ClientSession() as session:
        payload = {"query": query, "variables": variables or {}}
        headers = {"Authorization": f"Bearer {api_key}"}
        async with session.post("https://api.politicsandwar.com/graphql", json=payload, headers=headers) as resp:
            data = await resp.json()
            if "errors" in data:
                raise Exception(data["errors"])
            return data["data"]

async def fetch_paginated(query, key, variables=None, per_page=500):
    all_results = []
    page = 0
    while True:
        vars_with_pagination = variables.copy() if variables else {}
        vars_with_pagination.update({"limit": per_page, "offset": page * per_page})
        data = await fetch_graphql(query, vars_with_pagination)
        items = data[key]
        if not items:
            break
        all_results.extend(items)
        if len(items) < per_page:
            break
        page += 1
    return all_results

async def get_alliance_members(alliance_id):
    query = """
    query($alliance_id: ID!, $limit: Int!, $offset: Int!) {
        nations(filter: {alliance_id: $alliance_id}, limit: $limit, offset: $offset) {
            id
            nation_name
            barracks
            factory
            hangar
            drydock
            soldiers
            tanks
            aircraft
            ships
            missiles
            nukes
        }
    }
    """
    return await fetch_paginated(query, "nations", {"alliance_id": alliance_id})

async def get_nation_data(nation_id):
    query = """
    query($nation_id: ID!) {
        nation(id: $nation_id) {
            id
            nation_name
            barracks
            factory
            hangar
            drydock
            soldiers
            tanks
            aircraft
            ships
            missiles
            nukes
        }
    }
    """
    data = await fetch_graphql(query, {"nation_id": nation_id})
    return data["nation"]


async def average_militarisation(interaction, id, type):
        if type == 'alliance':
            members_raw = get_nations_data_sql_by_alliance_id(id)
            data_name = get_alliances_data_sql_by_id(id)
            name = data_name.get("name")
            by = "Alliance"
        elif type == 'nation':
            members_raw = get_nations_data_sql_by_nation_id(id)
            name = members_raw.get("nation_name")
            by = "Nation"

        members = []
        if hasattr(members_raw, '__iter__') and not isinstance(members_raw, (dict, str)):
            for member in members_raw:
                if isinstance(member, dict):
                    members.append(member)
        elif isinstance(members_raw, dict):
            members = [members_raw]
        elif isinstance(members_raw, list):
            members = members_raw
    
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

        import numpy as np
        import io
        import matplotlib.pyplot as plt
        import discord

        # --- average per city group ---
        city_groups = sorted(grouped.keys())
        soldiers_perc = [np.mean(grouped[c]['soldiers']) for c in city_groups]
        tanks_perc = [np.mean(grouped[c]['tanks']) for c in city_groups]
        aircraft_perc = [np.mean(grouped[c]['aircraft']) for c in city_groups]
        ships_perc = [np.mean(grouped[c]['ships']) for c in city_groups]
        city_labels = [f"C{c}" for c in city_groups]
        if type == 'alliance':
            def cap(val, max_val):
                return (val / max_val * 100) if max_val else 0

            current_pct = {
                'soldiers': cap(totals['soldiers'], totals['barracks'] * 3000),
                'tanks': cap(totals['tanks'], totals['factory'] * 250),
                'aircraft': cap(totals['aircraft'], totals['hangar'] * 15),
                'ships': cap(totals['ships'], totals['drydock'] * 5)
            }

            total_capacity = (
                totals['barracks'] * 3000 +
                totals['factory'] * 250 +
                totals['hangar'] * 15 +
                totals['drydock'] * 5
            )

            total_per = sum(current_pct.values())
            tm_percent = (total_per / 4) if total_capacity else 0

            # --- plotting ---
            fig, axs = plt.subplots(2, 1, figsize=(12, 7), gridspec_kw={'height_ratios': [3, 1]})

            axs[0].plot(city_labels, soldiers_perc, label='Soldiers', color='#5cb85c', marker='o')
            axs[0].plot(city_labels, tanks_perc, label='Tanks', color='#0275d8', marker='o')
            axs[0].plot(city_labels, aircraft_perc, label='Aircraft', color='#f0ad4e', marker='o')
            axs[0].plot(city_labels, ships_perc, label='Ships', color='#d9534f', marker='o')
            axs[0].set_ylabel("% of Capacity")
            axs[0].set_title(f"📈 {name} ({id}) Militarization Graph ({total_members} nations)")
            axs[0].legend()
            axs[0].set_ylim(0, 100)

            axs[1].bar(["MMR Current", "Wartime Goal"], [tm_percent, 100], color=["#0275d8", "#d9534f"])
            axs[1].set_ylim(0, 120)
            axs[1].set_ylabel("% Total")
            axs[1].set_title("📊 Total Militarization Comparison")

            plt.tight_layout()
            buf = io.BytesIO()
            plt.savefig(buf, format="png", dpi=150)
            buf.seek(0)
            plt.close(fig)

            file = discord.File(buf, filename="wartime_mmr.png")

        elif type == 'nation':
            def cap(val, max_val):
                return (val / max_val * 100) if max_val else 0

            current_pct = {
                "soldiers": cap(totals['soldiers'], totals['barracks'] * 3000),
                "tanks": cap(totals['tanks'], totals['factory'] * 250),
                "aircraft": cap(totals['aircraft'], totals['hangar'] * 15),
                "ships": cap(totals['ships'], totals['drydock'] * 5)
            }

            labels = list(current_pct.keys())
            values = list(current_pct.values())
            colors = ["#5cb85c", "#0275d8", "#f0ad4e", "#d9534f"]

            total_capacity = (
                totals['barracks'] * 3000 +
                totals['factory'] * 250 +
                totals['hangar'] * 15 +
                totals['drydock'] * 5
            )

            total_per = sum(current_pct.values())
            tm_percent = (total_per / 4) if total_capacity else 0

            fig, ax = plt.subplots(figsize=(8, 5))
            bars = ax.bar(labels, values, color=colors)

            for bar, val in zip(bars, values):
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    bar.get_height() + 2,
                    f"{val:.1f}%",
                    ha='center',
                    va='bottom',
                    fontsize=10,
                    weight='bold'
                )

            ax.set_ylim(0, 120)
            ax.set_ylabel("% of Capacity")
            ax.set_title(f"⚔️ Militarization for {name} ({id})", pad=15)
            ax.text(0.95, 0.9, f"Total Readiness: {tm_percent:.1f}%",
                    transform=ax.transAxes, ha="right", fontsize=11, color="#333", weight='bold')

            plt.tight_layout()
            buf = io.BytesIO()
            plt.savefig(buf, format="png", dpi=150)
            buf.seek(0)
            plt.close(fig)

            file = discord.File(buf, filename="militarization.png")



        # --- exact same description block ---
        description = (
            f"**Average MMR:**\n"
            f"Barracks: {totals['barracks']:,.2f}\n"
            f"Factories: {totals['factory']:,.2f}\n"
            f"Hangars: {totals['hangar']:,.2f}\n"
            f"Drydocks: {totals['drydock']:,.2f}\n"
            f"**{by} Militarisation:**\n"
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
        if type == "alliance":
            embed = discord.Embed(
                title=f"Militarization for {name}`({id})` | ({total_members} members)",
                description=description,
                color=discord.Color.purple()
            )
            embed.set_image(url="attachment://wartime_mmr.png")
        elif type == "nation":
            embed = discord.Embed(
                title=f"Militarization for {name}`({id})`",
                description=description,
                color=discord.Color.purple()
            )
            embed.set_image(url="attachment://militarization.png")
        return embed, file