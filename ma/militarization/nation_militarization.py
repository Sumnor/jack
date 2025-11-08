import discord
from settings.bot_instance import bot, wrap_as_prefix_command
from information.SharedInformational.avg_mmr import average_militarisation
from information.info_who import identifier

@bot.tree.command(name="nation_militarization", description="The Militarization go a certain nation")
async def nation_militarization(interaction: discord.Interaction, nation: str):
    await interaction.response.defer()
    user_id = str(interaction.user.id)
    await interaction.followup.send(f"Gathering Data for {nation}...", ephemeral=True)
    
    nation_id, discord_id, _, _ = identifier(interaction, nation, user_id)

    if nation_id == "Error":
        await interaction.followup.send(discord_id, ephemeral=True)
        return
    embed, file = await average_militarisation(interaction, nation_id, "nation")
    await interaction.followup.send(embed=embed, file=file)

bot.command(name="nation_militarization")(wrap_as_prefix_command(nation_militarization.callback))