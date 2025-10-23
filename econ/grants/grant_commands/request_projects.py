import discord
from discord import app_commands
from settings.bot_instance import bot, wrap_as_prefix_command
from econ.grants.grant_views.InfraGrantView import BlueGuy
from settings.initializer_functions.cached_users_initializer import cached_users
from econ.grants.general_request_utils import all_names, get_materials
from databases.sql.data_puller import get_nations_data_sql_by_nation_id

@bot.tree.command(name="request_project", description="Fetch resources for a project")
@app_commands.describe(project_name="Name of the project", tech_advancement="Is Technological Advancement active?")
async def request_project(interaction: discord.Interaction, project_name: str, tech_advancement: bool = False, note: str = "None"):
    await interaction.response.defer()
    user_id = str(interaction.user.id)

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

        if not own_id:
            await interaction.followup.send("❌ Could not find your Nation ID in the sheet.")
            return

    except Exception as e:
        await interaction.followup.send(f"❌ Failed to access your data: {e}")
        return

    nation_data = get_nations_data_sql_by_nation_id(own_id)
    nation_name = nation_data.get("nation_name")
    mats = get_materials(project_name)

    if mats:
        if tech_advancement:
            for mat in mats:
                mats[mat] = mats[mat] * 0.95

        embed = discord.Embed(
            title=f"***Cost for {project_name.title()}***",
            color=discord.Color.blue()
        )

        embed.description = (
            f"**Nation:** 🔗 [{nation_name}](https://politicsandwar.com/nation/id={own_id})\n"
            f"**Request:**\n" +
            "\n".join([f"{mat}: {amount:,.0f}" for mat, amount in mats.items()]) +
            f"\n\n**Requested by:** {interaction.user.mention}\n"
            f"**Reason:**\nBuild project: {project_name.title()}\n"
            f"**Note:** {note}\n" 
        )
        user_id = interaction.user.id
        guild_id = interaction.guild.id

        await interaction.followup.send(
            embed=embed,
            view=BlueGuy(category="project", data={"nation_name": nation_name, "nation_id": own_id, "project_name": project_name, "materials": mats, "person": user_id, "note": note}, guild_id=guild_id)
        )
    else:
        await interaction.followup.send("❌ Project not found.")

bot.command(name="request_project")(wrap_as_prefix_command(request_project.callback))

@request_project.autocomplete("project_name")
async def project_autocomplete(interaction: discord.Interaction, current: str):
    return [
        app_commands.Choice(name=name, value=name)
        for name in all_names
        if current.lower() in name.lower()
    ][:25]