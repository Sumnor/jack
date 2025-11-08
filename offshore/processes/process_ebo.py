import discord
from offshore.offshore_utils.initialize import pnw_api, safekeep_db, CONFIG_OFFSHORE_AA_ID
from settings.initializer_functions.resource_prices import parse_resources
import asyncio

async def process_ebo(interaction: discord.Interaction, alliance_id: int, resources_str: str, note: str):
    try:
        resources, parsed_note = parse_resources(resources_str)
        if note == "Emergency Bank Operation" and parsed_note:
            note = parsed_note
    except ValueError as e:
        embed = discord.Embed(
            title="❌ Invalid Resource Format",
            description=str(e),
            color=0xff0000
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        return
    
    target_alliance = await asyncio.to_thread(pnw_api.get_alliance_info, alliance_id)
    if not target_alliance:
        embed = discord.Embed(
            title="❌ Alliance Not Found",
            description=f"Could not find alliance with ID {alliance_id}",
            color=0xff0000
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        return
    
    success = await asyncio.to_thread(
        pnw_api.transfer_to_alliance,
        alliance_id,
        resources,
        note
    )
    
    if not success:
        embed = discord.Embed(
            title="❌ Transfer Failed",
            description="Failed to execute bank transfer. Check API key and permissions.",
            color=0xff0000
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        return
    
    ebo_id = await asyncio.to_thread(
        safekeep_db.record_ebo_transaction,
        CONFIG_OFFSHORE_AA_ID,
        alliance_id,
        resources,
        note,
        str(interaction.user)
    )
    
    await asyncio.to_thread(
        safekeep_db.update_aa_sheet,
        CONFIG_OFFSHORE_AA_ID,
        interaction.guild.id,
        resources,
        'subtract'
    )
    
    await asyncio.to_thread(
        safekeep_db.update_aa_sheet,
        alliance_id,
        interaction.guild.id,
        resources,
        'add'
    )
    
    resource_lines = [f"**{res.title()}**: {amount:,.0f}" 
                     for res, amount in resources.items() if amount > 0]
    
    embed = discord.Embed(
        title="✅ Emergency Bank Operation Executed",
        description=f"Transferred resources to **{target_alliance.get('name', 'Unknown')}**",
        color=0x00ff00
    )
    embed.add_field(name="EBO ID", value=f"`#{ebo_id}`", inline=True)
    embed.add_field(name="Target Alliance", value=f"`{alliance_id}`", inline=True)
    embed.add_field(name="Resources", value="\n".join(resource_lines), inline=False)
    embed.add_field(name="Note", value=note, inline=False)
    
    await interaction.followup.send(embed=embed)