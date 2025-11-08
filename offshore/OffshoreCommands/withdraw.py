import discord
from discord import app_commands
from settings.bot_instance import bot
from offshore.offshore_utils.utils import get_aa_id_from_guild
from offshore.processes.process_withdrawal import process_withdrawal

@bot.tree.command(name='withdraw', description='Withdraw resources from your safekeep account')
@app_commands.describe(
    resources='Resources to withdraw (e.g., money=1000000 oil=50000)',
    note='Optional note for the transaction'
)
async def slash_withdraw(interaction: discord.Interaction, resources: str, note: str = "Discord withdrawal"):
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
            description="This server is not linked to an alliance. An admin must use `/ebo_setkey` first.",
            color=0xff0000
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        return
    
    await process_withdrawal(interaction, alliance_id, resources, note)