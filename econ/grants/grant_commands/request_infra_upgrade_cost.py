import math
import discord
from discord import app_commands
from settings.bot_instance import bot, wrap_as_prefix_command
from settings.initializer_functions.cached_users_initializer import cached_users
from econ.grants.grant_views.InfraGrantView import BlueGuy
from databases.sql.data_puller import get_nations_data_sql_by_nation_id, get_cities_data_sql_by_nation_id

def calculate_infra_cost_for_range(start_infra: int, end_infra: int) -> float:
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
        (1900, 2000, 2_300_000),
        (2000, 2100, 2_500_000),
        (2100, 2200, 2_500_000),
        (2200, 2200, 2_700_000),
        (2300, 2400, 3_000_000),
        (2400, 2500, 3_700_000)
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
    target_infra="Target infrastructure level (max 2500)",
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

    if target_infra > 2500:
        await interaction.followup.send("❌ Target infrastructure above 2000 is not supported.(*** Personal Contribution by `@patrickrickrickpatrick` ***)")
        return

    
    try:
        global cached_users  

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
    except Exception as e:
        await interaction.followup.send(f"❌ Failed to access your data: {e}")
        return
    
    city_data = get_cities_data_sql_by_nation_id(own_id)
    if not city_data:
        await interaction.followup.send("❌ Could not retrieve city data for your nation.")
        return

    nation_data = get_nations_data_sql_by_nation_id(own_id)
    nation_name = nation_data.get("nation_name")
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
        guild_id = interaction.guild.id
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
        embed.set_footer(text="Brought to you by Sumnor\nPersonal Contribution by <@1026284133481189388>", icon_url="https://i.ibb.co/Kpsfc8Jm/jack.webp")
        await interaction.followup.send(
            embed=embed,
            view=BlueGuy(category="infra", data=data, guild_id=guild_id)
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
        guild_id = interaction.guild_id
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
        embed.set_footer(text="Brought to you by Sumnor\nPersonal Contribution by @patrickrickrickpatrick", icon_url="https://i.ibb.co/Kpsfc8Jm/jack.webp")
        await interaction.followup.send(
            embed=embed,
            view=BlueGuy(category="infra", data=data, guild_id=guild_id)
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
    guild_id = interaction.guild.id
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
    embed.set_footer(text="Brought to you by Sumnor", icon_url="https://i.ibb.co/Kpsfc8Jm/jack.webp")
    await interaction.followup.send(embed=embed, view=BlueGuy(category="infra", data=data, guild_id=guild_id))

bot.command(name="request_infra_cost")(wrap_as_prefix_command(infra_upgrade_cost.callback))
