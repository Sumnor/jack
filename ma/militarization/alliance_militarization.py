import discord
from settings.bot_instance import bot, wrap_as_prefix_command
from information.SharedInformational.avg_mmr import average_militarisation
from information.info_who import identifier

@bot.tree.command(name="alliance_militarization", description="The Militarization go a certain alliance")
async def alliance_militarization(interaction: discord.Interaction, alliance: str):
    await interaction.response.defer()
    user_id = str(interaction.user.id)
    await interaction.followup.send(f"Gathering Data for {alliance}...", ephemeral=True)
    
    nation_id, discord_id, _, _ = identifier(interaction, alliance, user_id)

    if nation_id == "Error":
        await interaction.followup.send(discord_id, ephemeral=True)
        return
    embed, file = await average_militarisation(interaction, nation_id, "alliance")
    await interaction.followup.send(embed=embed, file=file)

bot.command(name="alliance_militarization")(wrap_as_prefix_command(alliance_militarization.callback))