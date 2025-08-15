import requests
import discord
from discord import app_commands
from datetime import datetime
from io import BytesIO
import io
import pandas as pd
from datetime import datetime, timezone, timedelta
import asyncio
from matplotlib.ticker import FuncFormatter
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from bot_instance import bot
from utils import get_registration_sheet, cached_users
from settings_multi import get_gov_role, get_aa_name, get_api_key_for_interaction, get_alliance_sheet, get_colour_bloc
from graphql_requests import get_resources, get_general_data, get_military

@bot.tree.command(name="res_details_for_alliance", description="Get each Alliance Member's resources and money individually")
async def res_details_for_alliance(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True)
    guild_id = str(interaction.guild.id)

    sheet = get_registration_sheet(guild_id)
    rows = sheet.get_all_records()
    user_id = str(interaction.user.id)
    user_data = cached_users.get(user_id)
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
        await interaction.followup.send("❌ You don't have the rights necessary to perform this action.")
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
    try:
        dummy_guild_id = "I'm too lazy to remove it from get_registration_sheet so this is a"
        sheet = get_registration_sheet(dummy_guild_id)
        records = sheet.get_all_records()
        df = pd.DataFrame(records)
        df.columns = [col.strip() for col in df.columns]

        if "NationID" not in df.columns or "AA" not in df.columns:
            await interaction.followup.send("❌ Sheet is missing required 'NationID' or 'AA' column.", ephemeral=True)
            return

        aa_name = get_aa_name(interaction)
        df["AA"] = df["AA"].astype(str).str.strip()
        filtered_df = df[df["AA"].str.lower() == aa_name.strip().lower()]

        if filtered_df.empty:
            await interaction.followup.send(f"❌ No members found in AA: {aa_name}", ephemeral=True)
            return
        nation_rows = filtered_df.to_dict('records')

    except Exception as e:
        await interaction.followup.send(f"❌ Error loading Nation IDs: {e}", ephemeral=True)
        return
    for nation_row in nation_rows:
        nation_id = str(nation_row.get("NationID", "")).strip()
        row_user_id = str(nation_row.get("DiscordID", "")).strip()

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

    image_url = "https://i.ibb.co/Kpsfc8Jm/jack.webp"
    embed.set_footer(text=f"Brought to you by Sumnor", icon_url=image_url)
    try:
        await interaction.followup.send(embed=embed,  file=discord.File(io.StringIO(text_content), filename="alliance_resources.txt"))
    except Exception as e:
        print(f"Error sending detailed resources file: {e}")
        await interaction.followup.send(embed=embed)

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

    user_data = cached_users.get(user_id)
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

    try:
        dummy_guild_id = "I'm too lazy to remove it from get_registration_sheet so this is a"
        sheet = get_registration_sheet(dummy_guild_id)
        records = sheet.get_all_records()
        df = pd.DataFrame(records)
        df.columns = [col.strip() for col in df.columns]

        if "NationID" not in df.columns or "AA" not in df.columns:
            await interaction.followup.send("❌ Sheet is missing required 'NationID' or 'AA' column.", ephemeral=True)
            return

        aa_name = get_aa_name(interaction)
        df["AA"] = df["AA"].astype(str).str.strip()
        filtered_df = df[df["AA"].str.lower() == aa_name.strip().lower()]

        if filtered_df.empty:
            await interaction.followup.send(f"❌ No members found in AA: {aa_name}", ephemeral=True)
            return
        nation_rows = filtered_df.to_dict('records')

    except Exception as e:
        await interaction.followup.send(f"❌ Error loading Nation IDs: {e}", ephemeral=True)
        return
    for nation_row in nation_rows:
        nation_id = str(nation_row.get("NationID", "")).strip()
        user_id = str(nation_row.get("DiscordID", "")).strip()

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

        image_url = "https://i.ibb.co/Kpsfc8Jm/jack.webp"
        embed.set_footer(text=f"Brought to you by Sumnor", icon_url=image_url)
        await interaction.followup.send(embed=embed, file=discord.File(fp=buf, filename="resources_graph.png"))

    except Exception as e:
        print(f"Failed to generate or send graph: {e}")
        await interaction.followup.send(embed=embed)

@bot.tree.command(name="member_activity", description="Shows the activity of our members")
async def member_activity(interaction: discord.Interaction):
    await interaction.response.defer()

    guild_id = str(interaction.guild.id)
    user_id = str(interaction.user.id)

    user_data = cached_users.get(user_id)
    if not user_data:
        await interaction.followup.send("❌ You are not registered. Please register first.", ephemeral=True)
        return

    COLOUR_BLOC = get_colour_bloc(interaction)
    if not COLOUR_BLOC:
        await interaction.followup.send("❌ Set the colour bloc first.", ephemeral=True)
        return

    own_id = str(user_data.get("NationID", "")).strip()
    if not own_id:
        await interaction.followup.send("❌ Could not find your Nation ID in the sheet.", ephemeral=True)
        return
    async def is_banker():
        GOV_ROLE = get_gov_role(interaction)
        return any(role.name == GOV_ROLE for role in interaction.user.roles)

    if not await is_banker():
        await interaction.followup.send("❌ You don't have the rights, lil bro.", ephemeral=True)
        return
    active_w_bloc = 0
    active_wo_bloc = 0
    activish = 0
    activish_wo_bloc = 0
    inactive = 0

    active_w_bloc_list = []
    active_wo_bloc_list = []
    activish_list = []
    activish_wo_bloc_list = []
    inactive_list = []

    try:
        sheet = get_registration_sheet(guild_id)
        records = sheet.get_all_records()
        df = pd.DataFrame(records)
        df.columns = [col.strip() for col in df.columns]

        if "NationID" not in df.columns or "AA" not in df.columns:
            await interaction.followup.send("❌ Sheet is missing required 'NationID' or 'AA' column.", ephemeral=True)
            return

        aa_name = get_aa_name(interaction)
        df["AA"] = df["AA"].astype(str).str.strip()
        filtered_df = df[df["AA"].str.lower() == aa_name.strip().lower()]

        if filtered_df.empty:
            await interaction.followup.send(f"❌ No members found in AA: {aa_name}", ephemeral=True)
            return

        nation_ids = filtered_df["NationID"].dropna().astype(int).tolist()

    except Exception as e:
        await interaction.followup.send(f"❌ Error loading Nation IDs: {e}", ephemeral=True)
        return

    now = datetime.now(timezone.utc)

    for nation_id in nation_ids:
        try:
            military_data = get_military(nation_id, interaction)
            nation_name = military_data[0]
            nation_leader = military_data[1]
            score = military_data[2]

            result = get_general_data(nation_id, interaction)
            if not result or len(result) < 7:
                continue

            alliance_id, alliance_position, alliance, domestic_policy, num_cities, colour, activity, *_ = result

            try:
                activity_dt = datetime.fromisoformat(activity)
            except (ValueError, TypeError):
                print(f"Invalid activity date for nation {nation_id}: {activity}")
                continue

            delta = now - activity_dt
            days_inactive = delta.total_seconds() / 86400

            if days_inactive >= 2:
                inactive += 1
                inactive_list.append(f"Nation: {nation_name} (ID: `{nation_id}`), Leader: {nation_leader}, Bloc: {colour}, Score: {score}\n")
            elif days_inactive >= 1:
                if colour.lower() == COLOUR_BLOC.lower():
                    activish += 1
                    activish_list.append(f"Nation: {nation_name} (ID: `{nation_id}`), Leader: {nation_leader}, Bloc: {colour}, Score: {score}\n")
                else:
                    activish_wo_bloc += 1
                    activish_wo_bloc_list.append(f"Nation: {nation_name} (ID: `{nation_id}`), Leader: {nation_leader}, Bloc: {colour}, Score: {score}\n")
            else:
                if colour.lower() == COLOUR_BLOC.lower():
                    active_w_bloc += 1
                    active_w_bloc_list.append(f"Nation: {nation_name} (ID: `{nation_id}`), Leader: {nation_leader}, Bloc: {colour}, Score: {score}\n")
                else:
                    active_wo_bloc += 1
                    active_wo_bloc_list.append(f"Nation: {nation_name} (ID: `{nation_id}`), Leader: {nation_leader}, Bloc: {colour}, Score: {score}\n")

            await asyncio.sleep(3)

        except Exception as e:
            print(f"Error processing nation ID {nation_id}: {e}")
            continue

    data = [active_w_bloc, active_wo_bloc, activish, activish_wo_bloc, inactive]
    total_activity = sum(data)
    if total_activity == 0:
        await interaction.followup.send("⚠️ No activity data available to generate chart.", ephemeral=True)
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
        absolute = int(round(pct / 100. * sum(allvals)))
        return f"{pct:.1f}%\n({absolute})"

    wedges, texts, autotexts = ax.pie(data, autopct=lambda pct: func(pct, data), textprops=dict(color="w"))
    ax.legend(wedges, labels, title="DS Member Statuses", loc="center left", bbox_to_anchor=(1, 0, 0.5, 1))
    plt.setp(autotexts, size=8, weight="bold")
    ax.set_title("Activity Chart")

    buffer = BytesIO()
    plt.savefig(buffer, format="png")
    buffer.seek(0)
    file = discord.File(fp=buffer, filename="ds_activity.png")

    embed = discord.Embed(
        title="📊 Activity",
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

    embed.set_footer(text="Brought to you by Sumnor", icon_url="https://i.ibb.co/Kpsfc8Jm/jack.webp")
    embed.set_image(url="attachment://ds_activity.png")

    await interaction.followup.send(embed=embed, file=file)