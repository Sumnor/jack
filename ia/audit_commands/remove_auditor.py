import discord
from discord import app_commands
from settings.bot_instance import bot
from databases.sql.data_puller import supabase

@bot.tree.command(name="remove_auditor", description="Remove an auditor from this server.")
@app_commands.describe(user="The user to remove from the auditor list")
async def remove_auditor(interaction: discord.Interaction, user: discord.User):
    guild_id = str(interaction.guild_id)
    auditor_id = str(user.id)

    existing = supabase.select("auditor_quotas", filters={"guild_id": guild_id, "auditor_id": auditor_id})
    if not existing or not existing.get("data"):
        await interaction.response.send_message(f"⚠️ {user.mention} is not listed as an auditor.", ephemeral=True)
        return

    try:
        supabase.delete("auditor_quotas", filters={"guild_id": guild_id, "auditor_id": auditor_id})
        await interaction.response.send_message(f"🗑️ Removed {user.mention} from the auditor list.")
    except Exception as e:
        await interaction.response.send_message(f"❌ Failed to remove auditor: {e}", ephemeral=True)