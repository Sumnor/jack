import discord
from discord import app_commands
from settings.bot_instance import bot
from datetime import datetime, timezone
from offshore.offshore_utils.initialize import pnw_api, stored_white_keys, safekeep_db, CONFIG_DEPOSIT_NOTE, CONFIG_OFFSHORE_AA_ID
from offshore.offshore_utils.utils import save_white_key_to_db
import asyncio

@bot.tree.command(name='ebo_setkey', 
                 description='[ADMIN] Link an alliance to this server with API key')
@app_commands.describe(
    aa_id='Alliance ID to link',
    white_key='Whitelisted API key with bank access'
)
async def slash_ebo_setkey(interaction: discord.Interaction, aa_id: int, white_key: str):
    await interaction.response.defer(ephemeral=True)
    
    guild_id = interaction.guild_id
    if not guild_id:
        embed = discord.Embed(
            title="❌ Error",
            description="This command must be used in a server.",
            color=0xff0000
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        return
    
    test_result = await asyncio.to_thread(pnw_api.get_alliance_info, aa_id)
    if not test_result:
        embed = discord.Embed(
            title="❌ Invalid Alliance or API Key",
            description=f"Could not fetch data for Alliance ID `{aa_id}`. Check your API key and alliance ID.",
            color=0xff0000
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        return
    
    stored_white_keys[guild_id] = {
        'key': white_key,
        'aa_id': aa_id,
        'stored_by': str(interaction.user),
        'stored_at': datetime.now(timezone.utc).isoformat()
    }
    
    save_white_key_to_db(guild_id, white_key, aa_id, str(interaction.user))
    safekeep_db.get_or_create_aa_sheet(aa_id, guild_id)
    
    alliance_name = test_result.get('name', f'Alliance {aa_id}')
    
    embed = discord.Embed(
        title="✅ Server Linked Successfully",
        description=f"Server linked to **{alliance_name}**\nAccount creation is now enabled and triggered by deposits with note: **'{CONFIG_DEPOSIT_NOTE}'**",
        color=0x00ff00
    )
    embed.add_field(name="Alliance", value=f"`{alliance_name}` (ID: {aa_id})", inline=False)
    embed.add_field(name="API Key", value=f"`{white_key[:8]}...`", inline=True)
    embed.add_field(name="Offshore AA", value=f"`{CONFIG_OFFSHORE_AA_ID}`", inline=True)
    
    await interaction.edit_original_response(embed=embed)