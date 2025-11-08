import discord
import asyncio
from typing import Optional, Dict
from datetime import datetime, timezone
from discord import app_commands
from settings.bot_instance import bot
from settings.initializer_functions.resource_prices import ALL_RESOURCES
from offshore.offshore_utils.utils import safekeep_db, get_safekeep_by_nation_id
from offshore.offshore_utils.initialize import pnw_api

async def _upsert_safekeep_account_metadata(nation_id: int, interaction) -> Optional[Dict]:
    nation_info = await asyncio.to_thread(pnw_api.get_nation_info, nation_id, interaction)
    
    if not nation_info:
        return None
        
    initial_resources = {res: 0 for res in ALL_RESOURCES}
    metadata_to_upsert = {
        'nation_id': nation_id,
        'discord_id': None,
        'alliance_id': nation_info.get('alliance_id'),
        'alliance_name': nation_info.get('alliance', {}).get('name'),
        'created_at': datetime.now(timezone.utc).isoformat(),
        **initial_resources
    }
    
    try:
        safekeep_db._upsert("safekeep", metadata_to_upsert, conflict_columns='nation_id')
        return get_safekeep_by_nation_id(nation_id) 
        
    except Exception as e:
        return None

@bot.tree.command(name='create_safekeep_account', description='Link your Discord account to your nation for safekeep')
@app_commands.describe(
    nation_id='Your Politics and War nation ID'
)
async def slash_create_safekeep_account(interaction: discord.Interaction, nation_id: int):
    await interaction.response.defer(ephemeral=True)
    
    discord_id = str(interaction.user.id)
    
    existing_user = safekeep_db.get_safekeep_by_discord_id(discord_id)
    if existing_user:
        embed = discord.Embed(
            title="❌ Already Linked",
            description=f"Your Discord account is already linked to nation ID `{existing_user['nation_id']}`",
            color=0xff0000
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        return
    
    nation_account = get_safekeep_by_nation_id(nation_id)
    
    if not nation_account:
        await interaction.followup.send(
            embed=discord.Embed(
                title="⚠️ Creating Account",
                description=f"Safekeep account for Nation ID `{nation_id}` not found. Creating and linking now...",
                color=0xffaa00
            ), 
            ephemeral=True
        )
        
        nation_account = await _upsert_safekeep_account_metadata(nation_id, interaction)
        
        if not nation_account:
             embed = discord.Embed(
                title="❌ Creation Failed",
                description=f"Failed to create safekeep account for nation `{nation_id}`. Could not fetch nation info or database error occurred. Check logs.",
                color=0xff0000
            )
             await interaction.followup.send(embed=embed, ephemeral=True)
             return
    
    if nation_account.get('discord_id'):
        embed = discord.Embed(
            title="❌ Nation Already Linked",
            description=f"Nation ID `{nation_id}` is already linked to another Discord account.",
            color=0xff0000
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        return
    
    try:
        safekeep_db._patch(
            f"safekeep?nation_id=eq.{nation_id}",
            {'discord_id': discord_id}
        )
        
        embed = discord.Embed(
            title="✅ Account Linked Successfully",
            description=f"Your Discord has been linked to nation ID `{nation_id}`",
            color=0x00ff00
        )
        embed.add_field(name="Nation ID", value=f"`{nation_id}`", inline=True)
        
        alliance_display = nation_account.get('alliance_name') or f"AA {nation_account.get('alliance_id')}"
        embed.add_field(name="Alliance", value=f"`{alliance_display}`", inline=True)
        
        await interaction.followup.send(embed=embed, ephemeral=True)
        
    except Exception as e:
        print(f"[ERROR] Failed to link Discord ID {discord_id} to nation {nation_id}: {e}")
        embed = discord.Embed(
            title="❌ Link Failed",
            description="Failed to link your account. Please contact an admin.",
            color=0xff0000
        )
        await interaction.followup.send(embed=embed, ephemeral=True)