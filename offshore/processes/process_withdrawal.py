import discord
import asyncio
from datetime import datetime, timezone
from discord import app_commands
from typing import Optional, Dict, List, Set
import requests
from settings.bot_instance import bot, WHITEKEY, BOT_KEY
from databases.sql.databases import SafekeepDB, MaterialsDB
from settings.settings_multi import get_api_key_for_interaction
from settings.initializer_functions.resource_prices import parse_resources, RESOURCE_EMOJIS, format_number
from offshore.offshore_utils.initialize import safekeep_db, CONFIG_DEPOSIT_NOTE, PnWAPI
from offshore.offshore_utils.utils import get_white_key_from_guild


async def process_withdrawal(interaction: discord.Interaction, alliance_id: int, resources_str: str, note: str):
    discord_id = str(interaction.user.id)
    
    user_data = safekeep_db.get_safekeep_by_discord_id(discord_id)
    if not user_data:
        embed = discord.Embed(
            title="❌ Not Registered",
            description=f"You don't have a safekeep account. Deposit resources with note **'{CONFIG_DEPOSIT_NOTE}'** to open one, then use `/create_safekeep_account`.",
            color=0xff0000
        )
        await interaction.followup.send(embed=embed)
        return
    
    if user_data['alliance_id'] != alliance_id:
        embed = discord.Embed(
            title="❌ Wrong Alliance",
            description=f"Your safekeep account is in AA {user_data['alliance_id']}, not AA {alliance_id}. If you recently changed alliances, please contact an admin.",
            color=0xff0000
        )
        await interaction.followup.send(embed=embed)
        return
    
    resources_requested, parse_errors = parse_resources(resources_str)
    
    if not resources_requested:
        embed = discord.Embed(
            title="⚠️ Invalid Format",
            description="Please specify resources like: `money=1000000 oil=50000`",
            color=0xffaa00
        )
        await interaction.followup.send(embed=embed)
        return
    
    insufficient = []
    for res, amt in resources_requested.items():
        available = user_data.get(res, 0) or 0
        if amt > available:
            insufficient.append(
                f"**{res.capitalize()}**: Need {format_number(amt)}, Have {format_number(available)}"
            )
    
    if insufficient:
        embed = discord.Embed(
            title="❌ Insufficient Balance",
            description="\n".join(insufficient),
            color=0xff0000
        )
        await interaction.followup.send(embed=embed)
        return
    
    white_key = get_white_key_from_guild(interaction.guild_id)
    if not white_key:
        embed = discord.Embed(
            title="❌ No API Key",
            description="No API key configured for this server.",
            color=0xff0000
        )
        await interaction.followup.send(embed=embed)
        return
    
    nation_id = user_data['nation_id']
    offshore_api = PnWAPI(white_key, white_key)
    result = await asyncio.to_thread(
        offshore_api.withdraw_to_nation,
        nation_id,
        resources_requested,
        note
    )
    
    if result:
        safekeep_db.update_safekeep_balance(nation_id=nation_id, resources=resources_requested, subtract=True)
        
        resource_list = "\n".join([
            f"{RESOURCE_EMOJIS.get(res, '📦')} **{res.capitalize()}**: {format_number(amt)}"
            for res, amt in resources_requested.items()
        ])
        
        embed = discord.Embed(
            title="✅ Withdrawal Successful",
            description=f"Resources withdrawn to nation ID `{nation_id}`:\n\n{resource_list}",
            color=0x00ff00
        )
        await interaction.followup.send(embed=embed)
    else:
        embed = discord.Embed(
            title="❌ Withdrawal Failed",
            description="The withdrawal could not be completed. Check API access and try again.",
            color=0xff0000
        )
        await interaction.followup.send(embed=embed)