import discord
from settings.bot_instance import bot
from offshore.processes.process_balance import process_balance

@bot.tree.command(name='balance', description='Check your safekeep balance')
async def slash_balance(interaction: discord.Interaction):
    await interaction.response.defer()
    await process_balance(interaction)