import discord
import datetime
import os
from settings.bot_instance import bot, wrap_as_prefix_command

@bot.tree.command(name=f"bot_info_and_invite", description="Get the Info and invite for me")
async def bot_info(interaction: discord.Interaction):
    now = datetime.datetime.now()
    unix_timestamp = int(now.timestamp())
    Status = os.getenv("STATUS", "ERROR")
    messages = (
    "- Name: Jack\n"
    "- Discriminator: #8205\n"
    "- User ID: ```1367997847978377247```\n"
    f"- Current Date: <t:{unix_timestamp}:d>\n"
    f"- Command Called: <t:{unix_timestamp}:R>\n"
    f"- STATUS: {Status}\n"
    "- Bugs Dashboard: [Jack's Dashboard](https://jack-support.streamlit.app)\n"
    "- Help Server: [Jack Support](https://discord.gg/qqtb3kccjv)\n"
    "- Script: [Github](https://github.com/Sumnor/jack/tree/main)\n"
    "- Invite: [Jack](https://discord.com/oauth2/authorize?client_id=1367997847978377247&permissions=8&scope=bot%20applications.commands)"
)
    embed = discord.Embed(
        title="BOT INFO",
        colour=discord.Colour.brand_green(),
        description=messages
    )

    await interaction.response.send_message(embed=embed)

bot.command(name="bot_info_and_invite")(wrap_as_prefix_command(bot_info.callback))