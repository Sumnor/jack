import requests
import discord
from discord import app_commands
from datetime import datetime, timezone, timedelta
from io import BytesIO
import io
import time
import pandas as pd
import asyncio
from matplotlib.ticker import FuncFormatter
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from bot_instance import bot, wrap_as_prefix_command
from utils import cached_users, supabase
from settings_multi import get_gov_role, get_aa_name, get_api_key_for_interaction, get_colour_bloc
from graphql_requests import get_resources, get_general_data, get_military

@bot.tree.command(
    name="res_details_for_alliance",
    description="Get each Alliance Member's resources and money individually"
)
async def res_details_for_alliance(interaction: discord.Interaction):
    await interaction.response.defer()
    msg = await interaction.followup.send("Calculating wait-times...")
    
    user_id = str(interaction.user.id)
    guild_id = str(interaction.guild.id)
    user_data = cached_users.get(user_id)
    if not user_data:
        await msg.edit(content="❌ Error")
        await interaction.followup.send(
            "❌ You are not registered. Please register first.", ephemeral=True
        )
        return

    own_id = str(user_data.get("NationID", "")).strip()
    if not own_id:
        await msg.edit(content="❌ Error")
        await interaction.followup.send(
            "❌ Could not find your Nation ID in the cache.", ephemeral=True
        )
        return

    async def is_banker(interaction):
        GOV_ROLE = get_gov_role(interaction)
        return any(role.name == GOV_ROLE for role in interaction.user.roles)

    if not await is_banker(interaction):
        await msg.edit(content="❌ Error")
        await interaction.followup.send(
            "❌ You don't have the rights necessary to perform this action.", ephemeral=True
        )
        return


    try:
        aa_name = get_aa_name(interaction)
        alliance_members = [
            {"NationID": data.get("NationID"), "DiscordID": discord_id, "AA": data.get("AA")}
            for discord_id, data in cached_users.items()
            if data.get("AA", "").strip().lower() == aa_name.strip().lower()
        ]
        if not alliance_members:
            await msg.edit(content="❌ Error")
            await interaction.followup.send(f"❌ No members found in AA: {aa_name}", ephemeral=True)
            return

        member_count = len(alliance_members)
        batches_of_30 = (member_count + 29) // 30
        total_wait_seconds = batches_of_30 * 32
        target_time = int(time.time()) + total_wait_seconds
        await msg.edit(content=f"Estimated total wait time: <t:{target_time}:R>")

    except Exception as e:
        await msg.edit(content="❌ Error")
        await interaction.followup.send(f"❌ Error loading alliance members: {e}", ephemeral=True)
        return


    data_rows = []
    processed_nations = 0
    processed = []
    failed_nations = []
    batch_count = 0

    for i, member in enumerate(alliance_members):
        nation_id = str(member.get("NationID", "")).strip()
        if not nation_id:
            continue

        try:
            result = get_resources(nation_id, interaction)
            if not result or len(result) != 14:
                raise ValueError(f"Invalid result length from get_resources for {nation_id}")

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


            data_rows.append({
                "NationID": nation_id,
                "NationName": nation_name,
                "Cities": num_cities or 0,
                "Money": money or 0,
                "Food": food or 0,
                "Gasoline": gasoline or 0,
                "Munitions": munitions or 0,
                "Steel": steel or 0,
                "Aluminum": aluminum or 0,
                "Bauxite": bauxite or 0,
                "Lead": lead or 0,
                "Iron": iron or 0,
                "Oil": oil or 0,
                "Coal": coal or 0,
                "Uranium": uranium or 0
            })

            processed_nations += 1
            processed.append(nation_id)
            batch_count += 1

            if batch_count == 30:
                await asyncio.sleep(35)
                batch_count = 0

            if (i + 1) % 10 == 0 or i == len(alliance_members) - 1:
                remaining_members = len(alliance_members) - (i + 1)
                remaining_batches = (remaining_members + 29) // 30
                remaining_wait = remaining_batches * 32
                if remaining_wait > 0:
                    new_target_time = int(time.time()) + remaining_wait
                    await msg.edit(content=f"Processing... {i + 1}/{len(alliance_members)} nations completed. Estimated completion: <t:{new_target_time}:R>")
                else:
                    await msg.edit(content=f"Processing... {i + 1}/{len(alliance_members)} nations completed. Almost done!")

        except Exception as e:
            print(f"Failed processing nation {nation_id}: {e}")
            failed_nations.append(nation_id)
            continue

    if not data_rows:
        await msg.edit(content="❌ Error")
        await interaction.followup.send("❌ No valid resource data could be retrieved.", ephemeral=True)
        return


    totals = {key: sum(row[key] for row in data_rows) for key in data_rows[0] if isinstance(data_rows[0][key], (int, float))}


    lines = [
        f"{row['NationName']} (ID: {row['NationID']}): Cities={row['Cities']}, Money=${row['Money']:,}, "
        f"Food={row['Food']:,}, Gasoline={row['Gasoline']:,}, Munitions={row['Munitions']:,}, "
        f"Steel={row['Steel']:,}, Aluminum={row['Aluminum']:,}, Bauxite={row['Bauxite']:,}, "
        f"Lead={row['Lead']:,}, Iron={row['Iron']:,}, Oil={row['Oil']:,}, Coal={row['Coal']:,}, Uranium={row['Uranium']:,}"
        for row in data_rows
    ]

    total_resources_line = (
        f"\nAlliance totals - Nations counted: {processed_nations}, Failed: {len(failed_nations)}\n"
        f"Total Cities: {totals.get('Cities',0):,}\n"
        f"Money: ${totals.get('Money',0):,}\n"
        f"Food: {totals.get('Food',0):,}\n"
        f"Gasoline: {totals.get('Gasoline',0):,}\n"
        f"Munitions: {totals.get('Munitions',0):,}\n"
        f"Steel: {totals.get('Steel',0):,}\n"
        f"Aluminum: {totals.get('Aluminum',0):,}\n"
        f"Bauxite: {totals.get('Bauxite',0):,}\n"
        f"Lead: {totals.get('Lead',0):,}\n"
        f"Iron: {totals.get('Iron',0):,}\n"
        f"Oil: {totals.get('Oil',0):,}\n"
        f"Coal: {totals.get('Coal',0):,}\n"
        f"Uranium: {totals.get('Uranium',0):,}\n"
    )

    text_content = "\n".join(lines) + total_resources_line

    embed = discord.Embed(
        title="Alliance Members' Resources and Money (Detailed)",
        description=f"Nations counted: **{processed_nations}**\nFailed to retrieve data for: **{len(failed_nations)}**\n**FAILED: {failed_nations}\n**SUCCESS: {processed}",
        colour=discord.Colour.dark_magenta()
    )
    image_url = "https://i.ibb.co/Kpsfc8Jm/jack.webp"
    embed.set_footer(text="Brought to you by Sumnor", icon_url=image_url)

    try:
        text_file = discord.File(io.BytesIO(text_content.encode()), filename="alliance_resources.txt")
        await msg.edit(embed=embed, attachments=[text_file])
    except Exception as e:
        print(f"Error sending detailed resources file: {e}")
        await msg.edit(embed=embed)

bot.command(name="res_details_for_alliance")(wrap_as_prefix_command(res_details_for_alliance.callback))

@bot.tree.command(name="res_in_m_for_a", description="Get total Alliance Members' resources and money from historical data")
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
    msg = await interaction.followup.send("Loading historical data...")
    user_id = str(interaction.user.id)
    guild_id = str(interaction.guild.id)
    user_data = cached_users.get(user_id)
    if not user_data:
        await msg.edit(content="❌ Error")
        await interaction.followup.send("❌ You are not registered. Please register first.", ephemeral=True)
        return
    own_id = str(user_data.get("NationID", "")).strip()
    if not own_id:
        await msg.edit(content="❌ Error")
        await interaction.followup.send("❌ Could not find your Nation ID in the cache.")
        return
    async def is_banker(interaction):
        GOV_ROLE = get_gov_role(interaction)
        return any(role.name == GOV_ROLE for role in interaction.user.roles)
    if not await is_banker(interaction):
        await msg.edit(content="❌ Error")
        await interaction.followup.send("❌ You don't have the rights, lil bro.")
        return
    
    try:
        records = supabase.select('alliance_snapshots', filters={'guild_id': guild_id})
        if not records:
            await msg.edit(content="❌ Error")
            await interaction.followup.send("❌ No historical data found for this server.")
            return
            
        df = pd.DataFrame(records)
        if df.empty:
            await msg.edit(content="❌ Error")
            await interaction.followup.send("❌ No historical data available for graphing.")
            return
            
        if 'time_t' not in df.columns:
            await msg.edit(content="❌ Error")
            await interaction.followup.send("❌ Snapshot data missing time_t column.")
            return
            
        df['time_t'] = pd.to_datetime(df['time_t'])
        df = df.sort_values('time_t')
        

        mode_value = mode.value if mode else "days"
        scale_value = scale.value if scale else "millions"
        
        target_time = int(time.time()) + 5
        await msg.edit(content=f"Processing snapshots... Estimated finish: <t:{target_time}:R>")
        
    except Exception as e:
        print(f"Error loading historical data: {e}")
        await msg.edit(content="❌ Error")
        await interaction.followup.send(f"❌ Error loading historical data: {e}")
        return
    
    try:
        resource_cols = [
            "money", "food", "gasoline", "munitions", "steel", "aluminum",
            "bauxite", "lead", "iron", "oil", "coal", "uranium"
        ]
        

        if mode_value == "hours":
            df['period'] = df['time_t'].dt.floor('H')
        else:
            df['period'] = df['time_t'].dt.floor('D')
        

        grouped = df.groupby('period').last().reset_index()
        

        if scale_value == "billions":
            scale_divisor = 1000000000
            scale_label = "Billions ($)"
        else:
            scale_divisor = 1000000
            scale_label = "Millions ($)"
        

        plt.figure(figsize=(14, 10))
        

        plt.subplot(2, 2, 1)
        plt.plot(grouped['period'], grouped['total_money'] / scale_divisor, marker='o', linewidth=2, markersize=4)
        plt.title('Total Alliance Wealth Over Time', fontsize=12, fontweight='bold')
        plt.xlabel('Time')
        plt.ylabel(f'Total Wealth ({scale_label})')
        plt.xticks(rotation=45)
        plt.grid(True, alpha=0.3)
        

        plt.subplot(2, 2, 2)
        for resource in ['money', 'food', 'uranium', 'gasoline', 'munitions', 'steel', 'aluminum']:
            plt.plot(grouped['period'], grouped[resource] / scale_divisor, marker='o', linewidth=1.5, markersize=3, label=resource.capitalize())
        plt.title('Primary Resources Over Time', fontsize=12, fontweight='bold')
        plt.xlabel('Time')
        plt.ylabel(f'Value ({scale_label})')
        plt.xticks(rotation=45)
        plt.legend(fontsize=8)
        plt.grid(True, alpha=0.3)
        
        plt.subplot(2, 2, 3)
        for resource in ['steel', 'aluminum', 'munitions', 'gasoline']:
            plt.plot(grouped['period'], grouped[resource] / scale_divisor, marker='o', linewidth=1.5, markersize=3, label=resource.capitalize())
        plt.title('Manufacturing Resources Over Time', fontsize=12, fontweight='bold')
        plt.xlabel('Time')
        plt.ylabel(f'Value ({scale_label})')
        plt.xticks(rotation=45)
        plt.legend(fontsize=8)
        plt.grid(True, alpha=0.3)
        
        plt.subplot(2, 2, 4)
        for resource in ['iron', 'oil', 'coal', 'bauxite', 'lead']:
            plt.plot(grouped['period'], grouped[resource] / scale_divisor, marker='o', linewidth=1.5, markersize=3, label=resource.capitalize())
        plt.title('Raw Materials Over Time', fontsize=12, fontweight='bold')
        plt.xlabel('Time')
        plt.ylabel(f'Value ({scale_label})')
        plt.xticks(rotation=45)
        plt.legend(fontsize=8)
        plt.grid(True, alpha=0.3)
        
        plt.tight_layout()
        

        buffer = BytesIO()
        plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
        buffer.seek(0)
        plt.close()
        

        latest_record = df.iloc[-1]
        totals = {col: latest_record.get(col, 0) for col in resource_cols}
        total_wealth = latest_record.get('total_money', 0)
        
        embed = discord.Embed(
            title="Alliance Total Resources & Money (Historical)",
            colour=discord.Colour.dark_magenta(),
            description=(
                f"📊 Latest snapshot data ({mode_value} view, {scale_value} scale):\n\n"
                f"💰 Money: **${totals.get('money', 0):,}**\n"
                f"🍞 Food Value: **${totals.get('food', 0):,}**\n"
                f"⛽ Gasoline Value: **${totals.get('gasoline', 0):,}**\n"
                f"💣 Munitions Value: **${totals.get('munitions', 0):,}**\n"
                f"🏗️ Steel Value: **${totals.get('steel', 0):,}**\n"
                f"🧱 Aluminum Value: **${totals.get('aluminum', 0):,}**\n"
                f"🪨 Bauxite Value: **${totals.get('bauxite', 0):,}**\n"
                f"🧪 Lead Value: **${totals.get('lead', 0):,}**\n"
                f"⚙️ Iron Value: **${totals.get('iron', 0):,}**\n"
                f"🛢️ Oil Value: **${totals.get('oil', 0):,}**\n"
                f"🏭 Coal Value: **${totals.get('coal', 0):,}**\n"
                f"☢️ Uranium Value: **${totals.get('uranium', 0):,}**\n\n"
                f"💸 Total Alliance Wealth: **${total_wealth:,.2f}**"
            )
        )
        
        image_url = "https://i.ibb.co/Kpsfc8Jm/jack.webp"
        embed.set_footer(text=f"Brought to you by Sumnor", icon_url=image_url)
        embed.set_image(url="attachment://alliance_resources_graph.png")
        
        file = discord.File(fp=buffer, filename="alliance_resources_graph.png")
        await msg.edit(embed=embed, attachments=[file])
        
    except Exception as e:
        print(f"Failed to generate graphs: {e}")
        import traceback
        traceback.print_exc()
        await msg.edit(content="❌ Failed to generate resource graphs")

bot.command(name="res_in_m_for_a")(wrap_as_prefix_command(res_in_m_for_a.callback))

@bot.tree.command(name="member_activity", description="Shows the activity of our members")
async def member_activity(interaction: discord.Interaction):
    await interaction.response.defer()
    msg = await interaction.followup.send("Calculating wait-times...")
    guild_id = str(interaction.guild.id)
    user_id = str(interaction.user.id)
    user_data = cached_users.get(user_id)
    if not user_data:
        await msg.edit(content="❌ Error")
        await interaction.followup.send("❌ You are not registered. Please register first.", ephemeral=True)
        return
    COLOUR_BLOC = get_colour_bloc(interaction)
    if not COLOUR_BLOC:
        await msg.edit(content="❌ Error")
        await interaction.followup.send("❌ Set the colour bloc first.", ephemeral=True)
        return
    own_id = str(user_data.get("NationID", "")).strip()
    if not own_id:
        await msg.edit(content="❌ Error")
        await interaction.followup.send("❌ Could not find your Nation ID in the cache.", ephemeral=True)
        return
    async def is_banker():
        GOV_ROLE = get_gov_role(interaction)
        return any(role.name == GOV_ROLE for role in interaction.user.roles)
    if not await is_banker():
        await msg.edit(content="❌ Error")
        await interaction.followup.send("❌ You don't have the rights, lil bro.", ephemeral=True)
        return
    try:
        aa_name = get_aa_name(interaction)
        nation_ids = []
        for discord_id, data in cached_users.items():
            if data.get("AA", "").strip().lower() == aa_name.strip().lower():
                nation_id = data.get("NationID")
                if nation_id:
                    nation_ids.append(int(nation_id))
        if not nation_ids:
            await msg.edit(content="❌ Error")
            await interaction.followup.send(f"❌ No members found in AA: {aa_name}", ephemeral=True)
            return
        member_count = len(nation_ids)
        batches_of_30 = (member_count + 29) // 30
        total_wait_seconds = batches_of_30 * 32
        target_time = int(time.time()) + total_wait_seconds
        await msg.edit(content=f"Estimated total wait time: <t:{target_time}:R>")
    except Exception as e:
        await msg.edit(content="❌ Error")
        await interaction.followup.send(f"❌ Error loading alliance members: {e}", ephemeral=True)
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
    now = datetime.now(timezone.utc)
    for i, nation_id in enumerate(nation_ids):
        try:
            military_data = get_military(nation_id, interaction)
            if not military_data:
                continue
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
            info_line = f"Nation: {nation_name} (ID: `{nation_id}`), Leader: {nation_leader}, Bloc: {colour}, Score: {score}\n"
            if days_inactive >= 2:
                inactive += 1
                inactive_list.append(info_line)
            elif days_inactive >= 1:
                if colour and colour.lower() == COLOUR_BLOC.lower():
                    activish += 1
                    activish_list.append(info_line)
                else:
                    activish_wo_bloc += 1
                    activish_wo_bloc_list.append(info_line)
            else:
                if colour and colour.lower() == COLOUR_BLOC.lower():
                    active_w_bloc += 1
                    active_w_bloc_list.append(info_line)
                else:
                    active_wo_bloc += 1
                    active_wo_bloc_list.append(info_line)
            await asyncio.sleep(3)
            

            if (i + 1) % 10 == 0 or i == len(nation_ids) - 1:
                remaining_nations = len(nation_ids) - (i + 1)
                remaining_batches = (remaining_nations + 29) // 30
                remaining_wait = remaining_batches * 32
                if remaining_wait > 0:
                    new_target_time = int(time.time()) + remaining_wait
                    await msg.edit(content=f"Processing activity... {i + 1}/{len(nation_ids)} nations completed. Estimated completion: <t:{new_target_time}:R>")
                else:
                    await msg.edit(content=f"Processing activity... {i + 1}/{len(nation_ids)} nations completed. Almost done!")
                    
        except Exception as e:
            print(f"Error processing nation ID {nation_id}: {e}")
            continue
    data = [active_w_bloc, active_wo_bloc, activish, activish_wo_bloc, inactive]
    total_activity = sum(data)
    if total_activity == 0:
        await msg.edit(content="❌ Error")
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
    await msg.edit(embed=embed, attachments=[file])

bot.command(name="member_activity")(wrap_as_prefix_command(member_activity.callback))