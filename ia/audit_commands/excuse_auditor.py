import discord
from discord import app_commands
from settings.bot_instance import bot
from databases.sql.data_puller import supabase

@bot.tree.command(name="excuse_auditor", description="Excuse an auditor from current quota")
@app_commands.describe(auditor_id="Auditor's Discord ID")
async def excuse_auditor(interaction: discord.Interaction, auditor_id: str):
    if auditor_id.startswith("<@"):
        auditor_id = int(auditor_id.replace("<@", "").replace(">", ""))
    check = bot.fetch_user(auditor_id)
    if not check:
        return await interaction.response.send_message(f"User `{auditor_id}` does not exist")
    supabase.update("auditor_quotas", {"excused": True}, {"guild_id": interaction.guild_id, "auditor_id": int(auditor_id)})
    await interaction.response.send_message(f"✅ Excused <@{auditor_id}> from their current quota.", ephemeral=True)