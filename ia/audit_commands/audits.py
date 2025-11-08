import discord
from discord import app_commands
from ia.audits_utils import get_audits
from settings.bot_instance import bot, wrap_as_prefix_command 
from ia.AuditView import AuditView, build_audit_embed
from databases.sql.data_puller import supabase

@bot.tree.command(name="audits", description="Show and manage audits for this server")
@app_commands.describe(
    nation_id="Target a specific nation by ID",
    filter_incomplete="Only show nations with incomplete audits"
)
async def audits(
    interaction: discord.Interaction, 
    nation_id: str = None,
    filter_incomplete: bool = False
):
    await interaction.response.defer(ephemeral=True)
    
    user_id = interaction.user.id
    auditors = supabase.select("auditor_quotas", filters={"guild_id": str(interaction.guild_id)})

    found_auditor = None
    for auditor in auditors.get("data", []):
        if auditor.get("auditor_id") == str(user_id):
            found_auditor = auditor
            break

    if not found_auditor:
        await interaction.followup.send("❌ You are not registered as an auditor in this server.", ephemeral=True)
        return


    records = get_audits(interaction.guild_id)
    if not records:
        await interaction.followup.send(
            "❌ No audits found for this server. Use `/audits_setup` first.",
            ephemeral=True
        )
        return
    if nation_id:
        records = [r for r in records if r.get('nation_id') == nation_id]
        if not records:
            await interaction.followup.send(
                f"❌ No audit found for nation ID `{nation_id}`.",
                ephemeral=True
            )
            return
    if filter_incomplete:
        records = [
            r for r in records
            if not (r.get('wc_audit') and r.get('build_audit') and r.get('tax_audit'))
        ]
        
        if not records:
            await interaction.followup.send(
                "✅ All audits are complete! No incomplete audits found.",
                ephemeral=True
            )
            return
    records.sort(key=lambda r: (
        r.get('wc_audit', False) and r.get('build_audit', False) and r.get('tax_audit', False),
        r.get('nation_name', '')
    ))

    embed = build_audit_embed(records[0])
    view = AuditView(records, interaction.guild_id)
    await interaction.followup.send(embed=embed, view=view, ephemeral=True)

bot.command(name="audits")(wrap_as_prefix_command(audits.callback))