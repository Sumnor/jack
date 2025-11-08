import discord
from discord import app_commands
from settings.bot_instance import bot
from databases.sql.data_puller import supabase

@bot.tree.command(name="add_auditor", description="Add a new auditor to this server.")
@app_commands.describe(user="The user to add as an auditor", assigned="Number of audits assigned (default: 50)")
async def add_auditor(interaction: discord.Interaction, user: discord.User, assigned: int = 50):
    guild_id = str(interaction.guild_id)
    auditor_id = str(user.id)

    existing = supabase.select("auditor_quotas", filters={"guild_id": guild_id, "auditor_id": auditor_id})
    if existing and existing.get("data"):
        await interaction.response.send_message(f"⚠️ {user.mention} is already an auditor.", ephemeral=True)
        return

    data = {
        "guild_id": guild_id,
        "auditor_id": auditor_id,
        "assigned": assigned,
        "excused": False
    }

    try:
        supabase.insert("auditor_quotas", data)
        await interaction.response.send_message(f"✅ Added {user.mention} as an auditor with **{assigned}** assigned audits.")
    except Exception as e:
        await interaction.response.send_message(f"❌ Failed to add auditor: {e}", ephemeral=True)