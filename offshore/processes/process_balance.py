import discord
from settings.initializer_functions.resource_prices import RESOURCE_EMOJIS, format_number, ALL_RESOURCES
from offshore.offshore_utils.initialize import safekeep_db, CONFIG_DEPOSIT_NOTE

async def process_balance(interaction: discord.Interaction):
    discord_id = str(interaction.user.id)
    user_data = safekeep_db.get_safekeep_by_discord_id(discord_id)
    
    if not user_data:
        embed = discord.Embed(
            title="❌ Not Registered",
            description=f"You don't have a safekeep account. Deposit resources with note **'{CONFIG_DEPOSIT_NOTE}'** to open one, then use `/create_safekeep_account` to get started.",
            color=0xff0000
        )
        await interaction.followup.send(embed=embed)
        return
    
    embed = discord.Embed(
        title="💰 Your Safekeep Balance",
        color=0x3498db
    )
    
    alliance_display = user_data.get('alliance_name') or f"AA {user_data.get('alliance_id')}"
    embed.add_field(name="Alliance", value=f"`{alliance_display}`", inline=True)
    embed.add_field(name="Nation ID", value=f"`{user_data.get('nation_id')}`", inline=True)
    embed.add_field(name="\u200b", value="\u200b", inline=True)
    
    for res in ALL_RESOURCES:
        amount = user_data.get(res, 0) or 0
        emoji = RESOURCE_EMOJIS.get(res, "📦")
        embed.add_field(
            name=f"{emoji} {res.capitalize()}",
            value=format_number(amount),
            inline=True
        )
    
    await interaction.followup.send(embed=embed)