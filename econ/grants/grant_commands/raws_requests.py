import discord
from settings.bot_instance import bot, wrap_as_prefix_command
from datetime import datetime
from discord import app_commands
from settings.initializer_functions.cached_users_initializer import cached_users, supabase
from settings.settings_multi import get_auto_requests_sheet
from econ.grants.general_request_utils import parse_amount

@bot.tree.command(name="auto_week_summary", description="See the total materials which are requested for this week")
async def auto_week_summary(interaction: discord.Interaction):
    await interaction.response.defer()
    try:
        guild_id = str(interaction.guild.id)
        
        
        records = supabase.select('auto_requests', filters={'guild_id': guild_id})

        if not records:
            await interaction.followup.send("No data available.", ephemeral=True)
            return

        total_week = {res: 0 for res in ["coal", "oil", "bauxite", "lead", "iron"]}

        for record in records:
            try:
                time_period = float(record.get('time_period', 1))
                if time_period <= 0:
                    continue

                for res in total_week:
                    amount = float(record.get(res, 0))
                    per_day = amount / time_period
                    total_week[res] += per_day * 5  
            except Exception as row_ex:
                print(f"Skipping record due to error: {row_ex}")
                continue

        formatted = [
            f"{emoji} **{res.capitalize()}**: {int(amount):,}".replace(",", ".") 
            for res, emoji, amount in zip(
                ["coal", "oil", "bauxite", "lead", "iron"],
                ["🪨", "🛢️", "🟤", "🪫", "⛏️"],
                total_week.values()
            )
        ]

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

bot.command(name="auto_week_summary")(wrap_as_prefix_command(auto_week_summary.callback))

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
    food="Amount of food requested",
    uranium="Amount of uranium requested",
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
    food: str = "0",
    uranium: str = "0",
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
    user_data = cached_users.get(user_id)
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

    now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    data_to_store = {
        'guild_id': guild_id,
        'discord_id': user_id,
        'nation_id': nation_id,
        'coal': parse_amount(coal),
        'oil': parse_amount(oil),
        'bauxite': parse_amount(bauxite),
        'lead': parse_amount(lead),
        'iron': parse_amount(iron),
        'food': parse_amount(food),
        'uranium': parse_amount(uranium),
        'time_period': time_period_int,
        'last_requested': now_str
    }

    try:
        
        existing = supabase.select('auto_requests', filters={'guild_id': guild_id, 'discord_id': user_id})
        
        if existing:
            
            record_id = existing[0].get('id')
            supabase.update('auto_requests', data_to_store, {'id': record_id})
            await interaction.followup.send(
                "✅ Your auto-request has been updated successfully.", ephemeral=True
            )
        else:
            
            supabase.insert('auto_requests', data_to_store)
            await interaction.followup.send(
                "✅ Your auto-request has been added successfully.", ephemeral=True
            )
    
    except Exception as e:
        print(f"Error saving auto request: {e}")
        await interaction.followup.send(
            "❌ Failed to save auto-request. Please try again.", ephemeral=True
        )

bot.command(name="auto_resources_for_prod_req")(wrap_as_prefix_command(auto_resources_for_prod_req.callback))

@bot.tree.command(name="disable_auto_request", description="Disable your auto-request for key raw resources")
async def disable_auto_request(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)

    user_id = str(interaction.user.id)
    guild_id = str(interaction.guild.id)
    
    try:
        
        existing = supabase.select('auto_requests', filters={'guild_id': guild_id, 'discord_id': user_id})
        
        if not existing:
            await interaction.followup.send("⚠️ No auto-requests found under your account.", ephemeral=True)
            return

        
        tracked_resources = ["bauxite", "coal", "iron", "oil", "lead"]
        has_active_requests = False
        
        for record in existing:
            if any(int(record.get(resource, 0)) > 0 for resource in tracked_resources):
                has_active_requests = True
                
                record_id = record.get('id')
                supabase._make_request('DELETE', f'auto_requests?id=eq.{record_id}')

        if has_active_requests:
            await interaction.followup.send("✅ Your auto-request for raw resources has been disabled.", ephemeral=True)
        else:
            await interaction.followup.send("⚠️ No active auto-request for those resources found under your account.", ephemeral=True)

    except Exception as e:
        print(f"Error disabling auto request: {e}")
        await interaction.followup.send("❌ Failed to disable auto-request. Please try again.", ephemeral=True)

bot.command(name="disable_auto_request")(wrap_as_prefix_command(disable_auto_request.callback))

'''
@bot.tree.command(name="raws_audits", description="Audit building and raw usage per nation")
async def raws_audits(interaction: discord.Interaction, day: int):
    await interaction.response.defer(thinking=True)
    guild_id = interaction.guild.id
    sheet = get_registration_sheet(guild_id)
    rows = sheet.get_all_records()
    user_id = str(interaction.user.id)

    user_data = next((r for r in rows if str(r.get("DiscordID", "")).strip() == user_id), None)
    guild_id = str(interaction.guild.id)
    user_id = str(interaction.user.id)

    user_data = cached_users.get(user_id)
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

        cities_df = graphql_cities(nation_id, None, guild_id)
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
        
        res = get_resources(nation_id, None, guild_id)
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

        batch_count += 1
        if batch_count == 30:
            await asyncio.sleep(60)
            batch_count = 0

    output.seek(0)
    discord_file = discord.File(fp=output, filename="raws_audit.txt")
    await interaction.followup.send("✅ Audit complete.", file=discord_file, view=RawsAuditView(output=output.getvalue(), audits=audits_by_nation))'''