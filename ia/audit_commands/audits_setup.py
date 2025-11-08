import discord
from discord import app_commands
from ia.audits_utils import upsert_audit, bulk_upsert_audits
from settings.bot_instance import bot, wrap_as_prefix_command 
from databases.sql.data_puller import get_nations_data_sql_by_nation_id, get_nations_data_sql_by_alliance_id

@bot.tree.command(name="audits_setup", description="Set up an audit entry for a nation or entire alliance")
@app_commands.describe(
    nation_id="Nation ID to add (optional if using alliance)",
    alliance_id="Alliance ID to add all members (optional if using nation_id)"
)
async def audits_setup(
    interaction: discord.Interaction, 
    nation_id: str = None,
    alliance_id: str = None
):
    await interaction.response.defer(ephemeral=True)
    if not nation_id and not alliance_id:
            await interaction.followup.send(
                "❌ No nation_id or alliance_id provided, and no default alliance set for this guild.",
                ephemeral=True
            )
            return
    
    if nation_id:
        nation = get_nations_data_sql_by_nation_id(nation_id)
        if not nation:
            await interaction.followup.send(f"❌ No nation found for `{nation_id}`.", ephemeral=True)
            return

        nation_name = nation.get("nation_name") or nation.get("name") or "Unknown"
        if upsert_audit(interaction.guild_id, nation_id, nation_name):
            embed = discord.Embed(
                title=f"✅ Audit setup for {nation_name}",
                description=f"Nation `{nation_id}` added to audits.",
                color=discord.Color.green()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.followup.send("❌ Failed to create audit entry.", ephemeral=True)
        return
    
    if alliance_id:
        nations = get_nations_data_sql_by_alliance_id(alliance_id)
        if not nations:
            await interaction.followup.send(f"❌ No nations found in alliance `{alliance_id}`.", ephemeral=True)
            return
        
        success, failed = bulk_upsert_audits(interaction.guild_id, nations)
        
        embed = discord.Embed(
            title=f"✅ Bulk Audit Setup Complete",
            description=(
                f"**Alliance ID:** `{alliance_id}`\n"
                f"**Nations Added:** {success}\n"
                f"**Failed:** {failed}\n\n"
                f"Use `/audits` to view and manage all audit entries."
            ),
            color=discord.Color.green()
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

bot.command(name="audits_setup")(wrap_as_prefix_command(audits_setup.callback))