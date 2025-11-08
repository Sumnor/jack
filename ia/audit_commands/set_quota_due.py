import discord
from discord import app_commands
import datetime
from settings.bot_instance import bot
from settings.settings_multi import set_server_setting


@bot.tree.command(name="set_quota_due", description="Set a due date for auditor quotas")
@app_commands.describe(days="How many days until quota is due")
async def set_quota_due(interaction: discord.Interaction, days: int):
    due = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=days)
    due_iso = due.isoformat()
    set_server_setting(interaction.guild.id, "QUOTA DUE", days)
    await interaction.response.send_message(
        f"✅ Quota due date set to **{due_iso} UTC**.",
        ephemeral=True
    )
