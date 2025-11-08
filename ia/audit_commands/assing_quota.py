import discord
from discord import app_commands
from ia.audits_utils import get_audits
from settings.bot_instance import bot, wrap_as_prefix_command 
from databases.sql.data_puller import supabase

@bot.tree.command(name="assign_quota", description="Assign audits to a specific auditor")
@app_commands.describe(
    auditor_id="Discord ID of the auditor",
    amount="Number of nations to assign",
    incomplete_only="Only assign nations with incomplete audits"
)
async def assign_quota(
    interaction: discord.Interaction,
    auditor_id: str,
    amount: int,
    incomplete_only: bool = True
):
    await interaction.response.defer(ephemeral=True)

    records = get_audits(interaction.guild_id)
    if not records:
        await interaction.followup.send("❌ No audits found for this server.", ephemeral=True)
        return
    if incomplete_only:
        records = [
            r for r in records
            if not (r.get('wc_audit') and r.get('build_audit') and r.get('tax_audit'))
        ]

    if not records:
        await interaction.followup.send("✅ All audits are already complete!", ephemeral=True)
        return
    to_assign = records[:amount]

    '''for r in to_assign:
        try:
            supabase.update(
                "audits",
                {"auditor": int(auditor_id)},
                {"guild_id": interaction.guild_id, "nation_id": r["nation_id"]}
            )
            assigned_count += 1
        except Exception as e:
            print(f"Error assigning audit for nation {r['nation_id']}: {e}")'''
    try:
        existing = supabase.select("auditor_quotas", filters={
            "guild_id": interaction.guild_id,
            "auditor_id": int(auditor_id)
        })
        
        if existing and len(existing) > 0:
            current = existing[0].get("assigned", 0)
            supabase.update(
                "auditor_quotas",
                {"assigned": amount},
                {"guild_id": interaction.guild_id, "auditor_id": int(auditor_id)}
            )
        else:
            supabase.insert("auditor_quotas", {
                "guild_id": interaction.guild_id,
                "auditor_id": int(auditor_id),
                "assigned": amount,
                "completed": 0
            })
    except Exception as e:
        print(f"Error updating auditor_quotas: {e}")

    embed = discord.Embed(
        title="🧾 Audit Quota Assigned",
        description=f"Assigned **{amount}** audits to <@{auditor_id}>.",
        color=discord.Color.green()
    )
    await interaction.followup.send(embed=embed, ephemeral=True)


bot.command(name="assign_quota")(wrap_as_prefix_command(assign_quota.callback))
