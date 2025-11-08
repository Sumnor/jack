import discord
from discord import app_commands
from settings.bot_instance import bot
from offshore.offshore_utils.utils import get_aa_id_from_guild
from offshore.processes.process_ebo import process_ebo

@bot.tree.command(name='ebo', description='Execute Emergency Bank Operation to transfer resources')
@app_commands.describe(
    resources='Resources to transfer (e.g., money=1000000 oil=50000)',
    note='Reason for the emergency transfer'
)
async def slash_ebo(interaction: discord.Interaction, resources: str, note: str = "Emergency Bank Operation"):
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
    
    await process_ebo(interaction, alliance_id, resources, note)