import requests
import discord
from discord import app_commands
from datetime import datetime
from settings.bot_instance import bot, commandscalled, wrap_as_prefix_command
from settings.settings_multi import get_api_key_for_interaction
from econ.grants.grant_views.GrantView import GrantView
from settings.initializer_functions.cached_users_initializer import cached_users

percent_list = [
    app_commands.Choice(name="50%", value="50%"),
    app_commands.Choice(name="100%", value="100%")
]

@bot.tree.command(name="request_warchest", description="Request a  grant")
@app_commands.describe(percent="How much percent of the warchest do you want", note="A Note")
@app_commands.choices(percent=percent_list)
async def warchest(interaction: discord.Interaction, percent: app_commands.Choice[str], note: str = None):
    await interaction.response.defer()
    global commandscalled
    commandscalled["_global"] += 1
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


    try:
        API_KEY = get_api_key_for_interaction(interaction)
        GRAPHQL_URL = f"https://api.politicsandwar.com/graphql?api_key={API_KEY}"
        query = f"""
        {{
          nations(id: [{own_id}]) {{
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
        response_json = response.json()

        if "data" not in response_json or "nations" not in response_json["data"] or "data" not in response_json["data"]["nations"]:
            await interaction.followup.send("❌ Failed to fetch nation data. Please check the Nation ID or try again later.")
            return

        nation_data = response_json["data"]["nations"]["data"]

        if not nation_data:
            await interaction.followup.send("❌ Nation not found. Please try again.")
            return

        
        nation = nation_data[0]
        nation_name = nation["nation_name"]
        cities = nation["num_cities"]
        food = nation["food"]
        uranium = nation["uranium"]
        money = nation["money"]
        gasoline = nation["gasoline"]
        munition = nation["munitions"]
        steel = nation["steel"]
        aluminium = nation["aluminum"]

        if any(x is None for x in [cities, food, uranium, money, gasoline, munition, steel, aluminium]):
            await interaction.followup.send("❌ Missing resource data. Please try again.")
            return

        city = int(cities)

        
        percent_value = percent.value if hasattr(percent, "value") else percent
        percent_value = percent_value.strip().lower()
        if percent_value in ["50", "50%"]:
            nr_a = 325
            nr_a_f = 1500
            nr_a_m = 500000
            nr_a_u = 20
        else:
            nr_a = 750
            nr_a_f = 3000
            nr_a_m = 1000000
            nr_a_u = 40

        
        nr_a_minus = city * nr_a
        nr_a_f_minus = city * nr_a_f
        nr_a_u_minus = city * nr_a_u
        money_needed = city * nr_a_m

        
        money_n = 0
        gas_n = 0
        mun_n = 0
        ste_n = 0
        all_n = 0
        foo_n = 0
        ur_n = 0

        for res, resource_value in {
            'money': money, 'gasoline': gasoline, 'munitions': munition,
            'steel': steel, 'aluminum': aluminium, 'food': food, 'uranium': uranium
        }.items():
            if res == 'money':
                new_value = resource_value - money_needed
                money_n = 0 if new_value >= 0 else -new_value
            elif res == 'gasoline':
                new_value = resource_value - nr_a_minus
                gas_n = 0 if new_value >= 0 else -new_value
            elif res == 'munitions':
                new_value = resource_value - nr_a_minus
                mun_n = 0 if new_value >= 0 else -new_value
            elif res == 'steel':
                new_value = resource_value - nr_a_minus
                ste_n = 0 if new_value >= 0 else -new_value
            elif res == 'aluminum':
                new_value = resource_value - nr_a_minus
                all_n = 0 if new_value >= 0 else -new_value
            elif res == 'food':
                new_value = resource_value - nr_a_f_minus
                foo_n = 0 if new_value >= 0 else -new_value
            elif res == 'uranium':
                new_value = resource_value - nr_a_u_minus
                ur_n = 0 if new_value >= 0 else -new_value
        
        request_lines = []
        if money_n > 0:
            request_lines.append(f"Money: {round(money_n):,.0f}\n")
        if foo_n > 0:
            request_lines.append(f"Food: {round(foo_n):,.0f}\n")
        if ur_n > 0:
            request_lines.append(f"Uranium: {round(ur_n):,.0f}\n")
        if gas_n > 0:
            request_lines.append(f"Gasoline: {round(gas_n):,.0f}\n")
        if mun_n > 0:
            request_lines.append(f"Munitions: {round(mun_n):,.0f}\n")
        if ste_n > 0:
            request_lines.append(f"Steel: {round(ste_n):,.0f}\n")
        if all_n > 0:
            request_lines.append(f"Aluminum: {round(all_n):,.0f}")
        
        description_text = ''.join(request_lines).strip()
        
        if not description_text:
            await interaction.followup.send(
                f"You already possess all needed resources for a {percent_value} warchest",
                ephemeral=True
            )
            return
        
        now = datetime.now()
        unix_timestamp = int(now.timestamp())
        embed = discord.Embed(
            title="💰 Grant Request",
            color=discord.Color.gold(),
            description=(
                f"**Nation:** 🔗 [{nation_name}](https://politicsandwar.com/nation/id={own_id})\n"
                f"**Requested by:** {interaction.user.mention}\n"
                f"**Request:**\n{description_text}\n\n"
                f"**Submited:** <t:{unix_timestamp}:R>\n" 
                f"**Reason:** Warchest\n"
                f"**Note:** {note}\n"
            )
        )
        image_url = "https://i.ibb.co/Kpsfc8Jm/jack.webp"
        embed.set_footer(text=f"Brought to you by Sumnor", icon_url=image_url)
        await interaction.followup.send(embed=embed, view=GrantView())
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {e}")

bot.command(name="request_warchest")(wrap_as_prefix_command(warchest.callback))
