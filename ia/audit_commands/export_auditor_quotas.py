import discord
from settings.bot_instance import bot
from databases.sql.data_puller import supabase
import pandas as pd

@bot.tree.command(name="export_auditor_quotas", description="Export auditor quota data to Excel")
async def export_auditor_quotas(interaction: discord.Interaction):
    quotas = supabase.select("audits", filters={"guild_id": interaction.guild_id})
    if not quotas:
        await interaction.response.send_message("❌ No quota data found.", ephemeral=True)
        return

    df = pd.DataFrame(quotas)
    filename = f"nation_audits_{interaction.guild_id}.xlsx"
    df.to_excel(filename, index=False)

    await interaction.response.send_message(
        file=discord.File(filename),
        ephemeral=True
    )