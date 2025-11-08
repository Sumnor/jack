import math
import discord
import requests
from discord import app_commands
from settings.bot_instance import bot, commandscalled, wrap_as_prefix_command
from settings.initializer_functions.cached_users_initializer import cached_users
from settings.settings_multi import get_api_key_for_interaction
from econ.grants.grant_views.InfraGrantView import BlueGuy
from databases.sql.data_puller import get_nations_data_sql_by_nation_id

@bot.tree.command(name="request_city", description="Calculate cost for upgrading from current city to target city")
@app_commands.describe(current_cities="Your current number of cities", target_cities="Target number of cities")
async def request_city(interaction: discord.Interaction, current_cities: int, target_cities: int):
    await interaction.response.defer()
    user_id = str(interaction.user.id)
    commandscalled[user_id] = commandscalled.get(user_id, 0) + 1
    try:
        global cached_users  
        
        guild_id = str(interaction.guild.id)

        user_data = cached_users.get(user_id)
        if not user_data:
            await interaction.followup.send(
                "❌ You are not registered. Please register first.", ephemeral=True
            )
            return
        own_id = str(user_data.get("NationID", "")).strip()
    except Exception as e:
        print(f"Error checking registration: {e}")
        await interaction.followup.send("🚫 Error checking registration. Please try again later.")
        return
    if target_cities <= current_cities:
        await interaction.followup.send("❌ Target cities must be greater than current cities.")
        return
    elif current_cities <= 0:
        await interaction.followup.send("❌ Current cities must be greater than 0.")
        return        

    datta = get_nations_data_sql_by_nation_id(own_id)
    nation_name = datta.get("nation_name")
    total_cost = 0
    cost_details = []
    top20Average = get_top20Average(interaction)

    def compute_city_cost(cityToBuy: int, top20Average: float) -> float:
        # keep your static table for 2..10 if you want
        static_costs = {
            2: 400_000,
            3: 900_000,
            4: 1_600_000,
            5: 2_500_000,
            6: 3_600_000,
            7: 4_900_000,
            8: 6_400_000,
            9: 8_100_000,
            10: 10_000_000,
        }

        if cityToBuy < 11:
            return static_costs.get(cityToBuy, 0)


        n = float(cityToBuy)
        top20AverageQuarter = float(top20Average) * 0.25
        clause_1 = 100_000 * (n - top20AverageQuarter) ** 3 + 150_000 * (n - top20AverageQuarter) + 75_000
        clause_2 = 100_000 * (n ** 2)
        cost = max(clause_1, clause_2)
        return max(1.0, cost)



    for i in range(current_cities + 1, target_cities + 1):
        cost = compute_city_cost(i, top20Average)
        user_id = interaction.user.id

        total_cost += cost
        cost_details.append(f"City {i}: ${cost:,.2f}")

    embed = discord.Embed(
        title="🏙️ City Upgrade Cost",
        color=discord.Color.green(),
        description="\n".join(cost_details)
    )
    embed.add_field(name="Total Cost:", value=f"${total_cost:,.0f}", inline=False)
    image_url = "https://i.ibb.co/Kpsfc8Jm/jack.webp"
    embed.set_footer(text="Brought to you by Sumnor", icon_url=image_url)

    await interaction.followup.send(
        embed=embed,
        view=BlueGuy(category="city", data={
            "nation_name": nation_name,
            "nation_id": own_id,
            "from": current_cities,
            "city_num": target_cities,
            "total_cost": total_cost,
            "person": user_id,
        }, guild_id=guild_id)
        
                    )
    
bot.command(name="request_city")(wrap_as_prefix_command(request_city.callback))

def get_city_data(nation_id: str, interaction) -> list[dict]:
    API_KEY = get_api_key_for_interaction(interaction)
    GRAPHQL_URL = f"https://api.politicsandwar.com/graphql?api_key={API_KEY}"

    query = f"""
    {{
      cities(nation_id: {nation_id}) {{
        data {{
          name
          infrastructure
        }}
      }}
    }}
    """

    response = requests.post(
        GRAPHQL_URL,
        json={"query": query},
        headers={"Content-Type": "application/json"}
    )
    try:
        response_json = response.json()
        city_data = response_json.get("data", {}).get("cities", {}).get("data", [])
    except Exception:
        city_data = []

    if not city_data:
        return []

    return [{"name": city.get("name", "Unknown"), "infra": city.get("infrastructure", 0)} for city in city_data]

def get_top20Average(interaction) -> float:
    """
    Fetches the game_info city_average from the API.
    """
    api_key = get_api_key_for_interaction(interaction)
    GRAPHQL_URL = f"https://api.politicsandwar.com/graphql?api_key={api_key}"

    query = """
    query GameInfo {
      game_info {
        city_average
      }
    }
    """

    try:
        response = requests.post(
            GRAPHQL_URL,
            json={"query": query},
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
        data = response.json()

        # Access city_average directly from game_info
        game_info = data.get("data", {}).get("game_info", {})
        average = game_info.get("city_average", 40.8216)  # fallback default
        print(f"[AVERAGE] {average}")
        return round(float(average), 4)

    except Exception as e:
        print(f"[ERROR] fetching city_average: {e}")
        return 40.8216
