import discord
from settings.bot_instance import bot
from offshore.offshore_utils.utils import get_aa_id_from_guild
from offshore.processes.process_aa_balance import process_aa_balance

@bot.tree.command(name='aabalance', description='Check total safekeep balances for the alliance')
async def slash_aa_balance(interaction: discord.Interaction):
    await interaction.response.defer()
    
    guild_id = interaction.guild_id
    if not guild_id:
        embed = discord.Embed(
            title="❌ Error",
            description="This command must be used in a server.",
            color=0xff0000
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        return
    
    alliance_id = get_aa_id_from_guild(guild_id)
    if not alliance_id:
        embed = discord.Embed(
            title="❌ Not Configured",
            description="This server is not linked to an alliance.",
            color=0xff0000
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        return

    await process_aa_balance(interaction, alliance_id)