import discord
import asyncio
from settings.initializer_functions.resource_prices import RESOURCE_EMOJIS, format_number, ALL_RESOURCES
from offshore.offshore_utils.initialize import safekeep_db, pnw_api

async def process_aa_balance(interaction: discord.Interaction, alliance_id: int):
    guild_id = str(interaction.guild.id)
    user_data = safekeep_db.get_or_create_aa_sheet(alliance_id, guild_id)

    
    if not user_data:
        embed = discord.Embed(
            title="❌ Not Registered",
            description=f"This server hasn't been bound to an existing AA",
            color=0xff0000
        )
        await interaction.followup.send(embed=embed)
        return
    
    embed = discord.Embed(
        title="💰 AA Balance",
        color=0x3498db
    )
    
    alliance_display = f"AA:{user_data.get('alliance_id')}"
    embed.add_field(name="Alliance", value=f"`{alliance_display}`", inline=True)
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