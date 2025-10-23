import discord
import requests
from collections import defaultdict
from discord import app_commands
from datetime import datetime
from io import BytesIO
from datetime import datetime
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.dates import DateFormatter
from settings.bot_instance import bot, wrap_as_prefix_command
from settings.settings_multi import get_api_key_for_interaction
from settings.initializer_functions.cached_users_initializer import cached_users
from graphql_requests import get_military
import pandas as pd
import asyncio
from typing import Optional, List

class NationPaginationView(discord.ui.View):
    def __init__(self, df, filters):
        super().__init__(timeout=300)  
        self.df = df
        self.filters = filters
        self.current_page = 0
        self.per_page = 10
        self.max_pages = (len(df) + self.per_page - 1) // self.per_page
        
    def create_embed(self):
        embed = discord.Embed(
            title="🏴󠁧󠁢󠁳󠁣󠁴󠁿 Filtered Nations Results",
            description=f"Found **{len(self.df)}** nations matching your criteria",
            color=discord.Color.blue()
        )
        
        if self.filters:
            embed.add_field(
                name="🎯 Active Filters", 
                value="\n".join(f"• {f}" for f in self.filters), 
                inline=False
            )
        
        start_idx = self.current_page * self.per_page
        end_idx = start_idx + self.per_page
        page_nations = self.df.iloc[start_idx:end_idx]
        
        current_field_content = []
        current_field_length = 0
        field_count = 1
        
        for _, nation in page_nations.iterrows():
            alliance_name = "None"
            if nation.get('alliance_id_clean', 0) > 0:
                if pd.notna(nation.get('alliance.name')):
                    alliance_name = f"{nation['alliance.name']}"
                    if pd.notna(nation.get('alliance.acronym')) and nation['alliance.acronym']:
                        alliance_name += f" [{nation['alliance.acronym']}]"
                else:
                    alliance_name = f"AA ID: {nation['alliance_id_clean']}"
            
            beige_status = ""
            if nation.get('beige_turns', 0) > 0:
                beige_days_calc = nation['beige_turns'] // 12
                beige_status = f" 🟤({beige_days_calc}d)"
            
            nation_info = (
                f"**{nation.get('nation_name', 'Unknown')}** - {nation.get('num_cities', 0)}c | "
                f"{nation.get('score', 0):,.0f} score{beige_status}\n"
                f"Military: {nation.get('soldiers', 0):,}👥 {nation.get('tanks', 0):,}🚗 {nation.get('aircraft', 0):,}✈️ {nation.get('ships', 0):,}🚢\n"
                f"Alliance: {alliance_name}\n"
                f"[Nation](https://politicsandwar.com/nation/id={nation.get('id', 0)}) | "
                f"[Espionage](https://politicsandwar.com/nation/espionage/eid={nation.get('id', 0)}) | "
                f"[War](https://politicsandwar.com/nation/war/declare/id={nation.get('id', 0)})"
            )
            
            
            if current_field_length + len(nation_info) > 1024 and current_field_content:
                embed.add_field(
                    name=f"🏆 Results (cont.)", 
                    value="\n\n".join(current_field_content), 
                    inline=False
                )
                current_field_content = [nation_info]
                current_field_length = len(nation_info)
                field_count += 1
            else:
                current_field_content.append(nation_info)
                current_field_length += len(nation_info)
                
        
        if current_field_content:
            embed.add_field(
                name=f"🏆 Results (Page {self.current_page + 1}/{self.max_pages})", 
                value="\n\n".join(current_field_content), 
                inline=False
            )
        
        stats = []
        stats.append(f"Avg Cities: {self.df['num_cities'].mean():.1f}")
        stats.append(f"Avg Score: {self.df['score'].mean():,.0f}")
        
        embed.add_field(name="📊 Statistics", value=" | ".join(stats), inline=False)
        embed.set_footer(text=f"Page {self.current_page + 1}/{self.max_pages} • {len(self.df)} total results")
        
        return embed
    
    @discord.ui.button(label='◀️ Previous', style=discord.ButtonStyle.secondary)
    async def previous_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page > 0:
            self.current_page -= 1
            embed = self.create_embed()
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.defer()
    
    @discord.ui.button(label='▶️ Next', style=discord.ButtonStyle.secondary)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page < self.max_pages - 1:
            self.current_page += 1
            embed = self.create_embed()
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.defer()
    
    async def on_timeout(self):
        
        for item in self.children:
            item.disabled = True

@bot.tree.command(name="filter_nations", description="Filter Politics and War nations by various criteria")
@app_commands.describe(
    beige_days="Days in beige (0 = not beige, 1+ = days in beige)",
    has_alliance="Filter by alliance membership (True/False)",
    alliance_ids="Comma-separated alliance IDs (e.g., 1234,5678)",
    min_soldiers="Minimum soldiers",
    min_tanks="Minimum tanks",
    min_aircraft="Minimum aircraft",
    min_ships="Minimum ships",
    nation_limit="Maximum nations to return (default 50, min 20)"
)
async def filter_nations(
    interaction: discord.Interaction,
    beige_days: Optional[int] = None,
    has_alliance: Optional[bool] = None,
    alliance_ids: Optional[str] = None,
    min_soldiers: Optional[int] = None,
    min_tanks: Optional[int] = None,
    min_aircraft: Optional[int] = None,
    min_ships: Optional[int] = None,
    nation_limit: Optional[int] = 50
):
    """Filter nations by beige days, alliance, and military criteria"""
    
    await interaction.response.defer(thinking=True)
    global cached_users
    user_id = str(interaction.user.id)
    user_data = cached_users.get(user_id)
    if not user_data:
        await interaction.followup.send(
            "❌ You are not registered. Please register first.", ephemeral=True
        )
        return
    own_id = str(user_data.get("NationID", "")).strip()
    nation_name, nation_leader, nation_score, war_policy, soldiers, tanks, aircraft, ships, spies, missiles, nuclear = get_military(own_id, interaction)
    
    try:
        
        api_key = get_api_key_for_interaction(interaction)
        if not api_key:
            await interaction.followup.send("❌ No API key found for your account. Please register your API key first.")
            return
        
        
        alliance_id_list = None
        if alliance_ids:
            try:
                alliance_id_list = [int(x.strip()) for x in alliance_ids.split(',')]
            except ValueError:
                await interaction.followup.send("❌ Invalid alliance IDs format. Use comma-separated numbers like: 1234,5678")
                return
        
        
        if nation_limit and nation_limit < 20:
            nation_limit = 20
        elif not nation_limit:
            nation_limit = 50
            
        if nation_limit > 500:
            nation_limit = 500

        
        df = await get_filtered_nations_async(
            api_key=api_key,
            nation_score=nation_score,
            beige_days=beige_days,
            has_alliance=has_alliance,
            alliance_ids=alliance_id_list,
            min_soldiers=min_soldiers,
            min_tanks=min_tanks,
            min_aircraft=min_aircraft,
            min_ships=min_ships,
            nation_limit=nation_limit
        )
        
        if df is None or df.empty:
            await interaction.followup.send("🔍 No nations found matching the specified criteria.")
            return
        
        
        embed = discord.Embed(
            title="🏴󠁧󠁢󠁳󠁣󠁴󠁿 Filtered Nations Results",
            description=f"Found **{len(df)}** nations matching your criteria",
            color=discord.Color.blue()
        )
        
        
        filters = []
        if beige_days is not None:
            if beige_days == 0:
                filters.append("Not in beige")
            else:
                filters.append(f"Beige: {beige_days} days")
        if has_alliance is not None:
            filters.append(f"Has Alliance: {'Yes' if has_alliance else 'No'}")
        if alliance_id_list:
            filters.append(f"Alliance IDs: {', '.join(map(str, alliance_id_list))}")
        if min_soldiers:
            filters.append(f"Min Soldiers: {min_soldiers:,}")
        if min_tanks:
            filters.append(f"Min Tanks: {min_tanks:,}")
        if min_aircraft:
            filters.append(f"Min Aircraft: {min_aircraft:,}")
        if min_ships:
            filters.append(f"Min Ships: {min_ships:,}")
        
        
        view = NationPaginationView(df, filters)
        embed = view.create_embed()
        
        await interaction.followup.send(embed=embed, view=view)
        
    except Exception as e:
        print(f"Error in filter_nations command: {e}")
        await interaction.followup.send(f"❌ An error occurred while filtering nations: {str(e)}")

async def get_filtered_nations_async(
    api_key: str,
    nation_score: str,
    beige_days: Optional[int] = None,
    has_alliance: Optional[bool] = None,
    alliance_ids: Optional[List[int]] = None,
    min_soldiers: Optional[int] = None,
    min_tanks: Optional[int] = None,
    min_aircraft: Optional[int] = None,
    min_ships: Optional[int] = None,
    nation_limit: Optional[int] = 50
) -> Optional[pd.DataFrame]:
    max_calc_s = nation_score*1.5
    min_calc_s = nation_score*0.25
    min_score = nation_score - min_calc_s
    max_score = nation_score + max_calc_s

    
    query_template = """
    query ($first: Int, $page: Int, $alliance_id: [Int], $min_score: Float, $max_score: Float, $vmode: Boolean) {
        nations(
            first: $first,
            page: $page,
            alliance_id: $alliance_id,
            min_score: $min_score,
            max_score: $max_score,
            vmode: $vmode
        ) {
            data {
                id
                nation_name
                leader_name
                continent
                color
                alliance_id
                num_cities
                soldiers
                tanks
                aircraft
                ships
                score
                vacation_mode_turns
                beige_turns
                last_active
                alliance {
                    id
                    name
                    acronym
                    score
                }
            }
            paginatorInfo {
                count
                currentPage
                hasMorePages
            }
        }
    }
    """

    all_nations = []
    batch_size = 100
    fetched = 0
    page = 1
    max_fetch = min(nation_limit * 20, 10000)

    variables = {"page": page}

    if has_alliance == False:
        variables["alliance_id"] = [0]
    elif alliance_ids:
        variables["alliance_id"] = alliance_ids
    if min_score is not None:
        variables["min_score"] = min_score
    if max_score is not None:
        variables["max_score"] = max_score

    variables["vmode"] = False

    GRAPHQL_URL = f"https://api.politicsandwar.com/graphql?api_key={api_key}"
    headers = {"Content-Type": "application/json"}

    while fetched < max_fetch:
        variables["first"] = min(batch_size, max_fetch - fetched)
        variables["page"] = page

        try:
            loop = asyncio.get_event_loop()
            resp = await loop.run_in_executor(
                None,
                lambda: requests.post(
                    GRAPHQL_URL,
                    json={"query": query_template, "variables": variables},
                    headers=headers,
                    timeout=30
                )
            )
            resp.raise_for_status()
            data = resp.json()

            if "errors" in data:
                print(f"GraphQL error: {data['errors']}")
                break

            nations = data.get("data", {}).get("nations", {}).get("data", [])
            if not nations:
                break

            all_nations.extend(nations)
            fetched += len(nations)
            page += 1

            paginator_info = data.get("data", {}).get("nations", {}).get("paginatorInfo", {})
            if not paginator_info.get("hasMorePages", False):
                break

            if len(nations) < batch_size:
                break

        except Exception as e:
            print(f"Error fetching nations: {e}")
            break

    if not all_nations:
        return None

    try:
        df = pd.json_normalize(all_nations)

        
        numeric_cols = ['alliance_id', 'soldiers', 'tanks', 'aircraft', 'ships', 'beige_turns']
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

        df['alliance_id_clean'] = df['alliance_id'].astype(int)

        print(f"Nations fetched from GraphQL: {len(df)}")

        
        if min_soldiers is not None:
            df = df[df['soldiers'] >= min_soldiers]
        if min_tanks is not None:
            df = df[df['tanks'] >= min_tanks]
        if min_aircraft is not None:
            df = df[df['aircraft'] >= min_aircraft]
        if min_ships is not None:
            df = df[df['ships'] >= min_ships]

        if has_alliance == True:
            df = df[df['alliance_id_clean'] > 0]
            
        if beige_days is not None:
            if beige_days == 0:
                df = df[df['beige_turns'] == 0]
            else:
                
                min_turns = beige_days * 12
                max_turns = (beige_days + 1) * 12 - 1
                df = df[(df['beige_turns'] >= min_turns) & (df['beige_turns'] <= max_turns)]

        
        df = df.sort_values('score', ascending=False)
        df = df.head(nation_limit)

        return df if not df.empty else None

    except Exception as e:
        print(f"Error processing nations data: {e}")
        return None


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
    
    
    txt_buffer = BytesIO(all_log.encode("utf-8"))
    txt_buffer.seek(0)
    
    embed = discord.Embed(
        title="War Results:",
        colour=discord.Colour.dark_orange(),
        description="Detailed war summary attached as text file"
    )
    image_url = "https://i.ibb.co/Kpsfc8Jm/jack.webp"
    embed.set_footer(text=f"Brought to you by Sumnor", icon_url=image_url)
    
    await interaction.followup.send(embed=embed, file=discord.File(txt_buffer, filename=f"nation_{nation_id}_wars_summary.txt"))

bot.command(name="war_losses")(wrap_as_prefix_command(war_losses.callback))

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

    user_data = cached_users.get(user_id)
    if not user_data:
        await interaction.followup.send(
            "⚠️ You are not registered. Please register first.", ephemeral=True
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
    
        values = [money_by_day[d.strftime("%Y-%m-%d")] / 1_000_000 for d in war_dates_all]  
        outcome_avgs = [
            sum(outcome_by_day[d.strftime("%Y-%m-%d")]) / len(outcome_by_day[d.strftime("%Y-%m-%d")])
            if outcome_by_day[d.strftime("%Y-%m-%d")] else 0
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
        
        embed = discord.Embed(
            title="War Results:",
            colour=discord.Colour.dark_orange(),
            description="Visualized War Results:"
        )
        image_url = "https://i.ibb.co/Kpsfc8Jm/jack.webp"
        embed.set_footer(text=f"Brought to you by Sumnor", icon_url=image_url)
        await interaction.followup.send(embed=embed, file=discord.File(buf_outcome, filename="outcome_detail_graph.png"))

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
            
            embed = discord.Embed(
                title="War Results Alliance:",
                colour=discord.Colour.dark_orange(),
                description="Visualised Results:"
            )
            image_url = "https://i.ibb.co/Kpsfc8Jm/jack.webp"
            embed.set_footer(text=f"Brought to you by Sumnor", icon_url=image_url)
            embed.set_image(url=f"attachment://war_graph_batch{batch_index}.png")
            await interaction.followup.send(embed=embed, file=discord.File(buf, filename=f"war_graph_batch{batch_index}.png"))

    
    log_file = BytesIO(all_log.encode("utf-8"))
    log_file.seek(0)
    await interaction.followup.send(file=discord.File(log_file, filename=f"war_summary_{alliance_id}.txt"))

bot.command(name="war_losses_alliance")(wrap_as_prefix_command(war_losses_alliance.callback))