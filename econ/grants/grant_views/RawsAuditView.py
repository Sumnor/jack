import discord
from settings_multi import get_grant_channel
from utils import get_registration_sheet
from GrantView import GrantView

class RawsAuditView(discord.ui.View):
    def __init__(self, output, audits):
        super().__init__(timeout=None)
        self.output = output
        self.audits = audits  

    @discord.ui.button(label="Request Yellow", style=discord.ButtonStyle.primary, custom_id="request_yellow")
    async def request_yellow(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_request(interaction, "🟡", discord.Color.yellow())

    @discord.ui.button(label="Request Orange", style=discord.ButtonStyle.primary, custom_id="request_orange")
    async def request_orange(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_request(interaction, "🟠", discord.Color.orange())

    @discord.ui.button(label="Request Red", style=discord.ButtonStyle.danger, custom_id="request_red")
    async def request_red(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_request(interaction, "🔴", discord.Color.red())

    async def handle_request(self, interaction: discord.Interaction, color_emoji: str, embed_color: discord.Color):
        await interaction.response.defer(ephemeral=True)

        user_id = interaction.user.id
        guild_id = interaction.guild.id
        bot = interaction.client

        channel = bot.get_channel(get_grant_channel(guild_id))
        if not channel:
            await interaction.followup.send("❌ Target channel not found.")
            return

        sheet = get_registration_sheet(guild_id)
        rows = sheet.get_all_records()

        for nation_id, entry in self.audits.items():
            nation_name = entry["nation_name"]
            missing_resources = entry.get("missing", [])
        
            relevant_lines = [
                f"{res_name}: {float(amount):.2f}"
                for res_name, amount, res_color in missing_resources
                if res_color == color_emoji
            ]
        
            if not relevant_lines:
                continue  

            row = next((r for r in rows if str(r.get("NationID", "")).strip() == str(nation_id)), None)
            if not row:
                continue

            discord_id = row.get("DiscordID", None)
            if not discord_id:
                continue

            embed = discord.Embed(
                title="Resource Request",
                description=(
                    f"**Nation:** {nation_name} (`{nation_id}`)\n"
                    f"**Request:**\n" + "\n".join(relevant_lines) + "\n"
                    f"**Reason:** Resources for Production\n"
                    f"**Requested by:** <@{discord_id}>"
                ),
                color=embed_color
            )
            image_url = "https://i.ibb.co/Kpsfc8Jm/jack.webp"
            embed.set_footer(text="Brought to you by Sumnor", icon_url=image_url)

            await channel.send(embed=embed, view=GrantView())

        await interaction.followup.send(f"✅ Processed {color_emoji} requests.")
