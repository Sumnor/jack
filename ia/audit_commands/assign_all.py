import discord
from discord import app_commands
from datetime import datetime
from settings.bot_instance import bot
from databases.sql.data_puller import supabase
from settings.settings_multi import get_ia_gov_role

@bot.tree.command(name="assign_all", description="Assign audits equally to all IA members")
@app_commands.describe(amount="Number of audits per auditor")
async def assign_all(interaction: discord.Interaction, amount: int):
    ia_role_id = get_ia_gov_role(interaction.guild_id)
    role = interaction.guild.get_role(ia_role_id)
    if not role:
        await interaction.response.send_message("❌ IA role not found.", ephemeral=True)
        return

    members = [m for m in role.members if not m.bot]
    if not members:
        await interaction.response.send_message("❌ No IA members found.", ephemeral=True)
        return

    for member in members:
        try:
            supabase.insert("auditor_quotas", {
                "guild_id": interaction.guild_id,
                "auditor_id": member.id,
                "assigned": amount,
                "completed": 0,
                "due_date": datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc) + datetime.timedelta(days=7),
            })
        except Exception as e:
            print(f"Error assigning to {member.id}: {e}")

    await interaction.response.send_message(f"✅ Assigned {amount} audits to all IA members.", ephemeral=True)