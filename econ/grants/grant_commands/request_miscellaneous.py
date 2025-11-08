import discord
from discord import app_commands
from datetime import datetime
from settings.bot_instance import bot, wrap_as_prefix_command
from econ.grants.grant_views.GrantView import GrantView
from settings.initializer_functions.cached_users_initializer import cached_users
from econ.grants.general_request_utils import parse_amount
from databases.graphql_requests import get_military

@bot.tree.command(name="request_miscellaneous", description="Request a custom amount of resources from the alliance bank")
@app_commands.describe(
    reason="Select the reason for your grant request.",
    uranium="Amount of uranium requested",
    coal="Amount of coal requested",
    oil="Amount of oil requested",
    bauxite="Amount of bauxite requested",
    lead="Amount of lead requested",
    iron="Amount of iron requested",
    steel="Amount of steel requested",
    aluminum="Amount of aluminum requested",
    gasoline="Amount of gasoline requested",
    money="Amount of money requested",
    food="Amount of food requested",
    munitions="Amount of munitions requested",
    note="A Note"
)

async def request_grant(
    interaction: discord.Interaction,
    reason: str,
    uranium: str = "0",
    coal: str = "0",
    oil: str = "0",
    bauxite: str = "0",
    lead: str = "0",
    iron: str = "0",
    steel: str = "0",
    aluminum: str = "0",
    gasoline: str = "0",
    money: str = "0",
    food: str = "0",
    munitions: str = "0",
    note: str = "0",
):
    await interaction.response.defer()
    user_id = str(interaction.user.id)

    try:
        global cached_users
        guild_id = str(interaction.guild.id)
        user_data = cached_users.get(user_id)

        if not user_data:
            await interaction.followup.send("❌ You are not registered. Use `/register` first.")
            return

        own_id = str(user_data.get("NationID", "")).strip()
        if not own_id:
            await interaction.followup.send("❌ Could not find your Nation ID in the sheet.", ephemeral=True)
            return

        nation_data = get_military(own_id, interaction)
        nation_name = nation_data[0]
        if reason.title() in ["Warchest", "WC", "Wc"]:
            await interaction.followup.send("❌ Don't use `/request_grant`, use `/request_warchest`", ephemeral=True)
            return
        
        raw_inputs = {
            "Uranium": uranium,
            "Coal": coal,
            "Oil": oil,
            "Bauxite": bauxite,
            "Lead": lead,
            "Iron": iron,
            "Steel": steel,
            "Aluminum": aluminum,
            "Gasoline": gasoline,
            "Money": money,
            "Food": food,
            "Munitions": munitions,
        }

        resources = {k: parse_amount(v) for k, v in raw_inputs.items()}
        requested_resources = {k: v for k, v in resources.items() if v > 0}

        if not requested_resources:
            await interaction.followup.send("❌ You must request at least one resource.", ephemeral=True)
            return

        formatted_lines = [
            f"{resource}: {amount:,}".replace(",", ".")
            for resource, amount in requested_resources.items()
        ]
        description_text = "\n".join(formatted_lines)
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
                f"**Reason:** {reason.title()}\n"
                f"**Note:** {note}\n"
            )
        )
        image_url = "https://i.ibb.co/Kpsfc8Jm/jack.webp"
        embed.set_footer(text="Brought to you by Sumnor", icon_url=image_url)
        message = await interaction.followup.send("<@1390237054872322148> <@1388161354086617220>")
        await message.delete()
        await interaction.followup.send(embed=embed, view=GrantView())

    except Exception as e:
        await interaction.followup.send(f"❌ An unexpected error occurred: {e}", ephemeral=True)

bot.command(name="request_miscellaneous")(wrap_as_prefix_command(request_grant.callback))