import discord
from datetime import datetime
from econ.grants.grant_views.GrantView import GrantView

class BlueGuy(discord.ui.View):
    def __init__(self, category=None, data=None, guild_id=None):
        super().__init__(timeout=None)
        self.category = category
        self.data = data or {}
        self.guild_id = guild_id

    @discord.ui.button(label="Request Grant", style=discord.ButtonStyle.green, custom_id="req_money_needed")
    async def send_request(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        person = str(self.data.get("person", None))
        print(person)
        presser = str(interaction.user.id)
        print(presser)
        if presser != person:
            if presser not in ["1378012299507269692", "1148678095176474678"]:
                await interaction.followup.send(f"Only the requester (<@{person}> in this case) may press the button", ephemeral=True)
                return

        embed = discord.Embed(title="Request Grant", color=discord.Color.green())

        reason = "Unknown Request"
        materials = {}
        nation_name = self.data.get("nation_name", "?")
        nation_id = self.data.get("nation_id", "unknown")

        note = "/"
        if self.category == "infra":
            from_level = self.data.get("from", "?")
            to_level = self.data.get("infra", "?")
            cities = self.data.get("ct_count", "?")
            reason = f"Upgrade infrastructure from {from_level} to {to_level} in {cities} cities"
            materials = {"Money": self.data.get("total_cost", 0)}

        elif self.category == "city":
            from_cities = self.data.get("from", "?")
            to_cities = self.data.get("city_num", "?")
            ct_num = to_cities - from_cities
            reason = f"City {from_cities} - {to_cities}"
            materials = {"Money": self.data.get("total_cost", 0)}

        elif self.category == "project":
            project_name = self.data.get("project_name", "?")
            reason = f"Build project: {project_name}"
            materials = self.data.get("materials", {})
            notes = self.data.get("note", "None")
            note = f"Note: {notes}"

        
        description_lines = [f"**Nation:** 🔗 [{nation_name}](https://politicsandwar.com/nation/id={nation_id})", "**Request:**"]
        if materials:
            for name, amount in materials.items():
                description_lines.append(f"{name}: {amount:,.0f}")
        else:
            description_lines.append("None")

        description_lines.append(f"\n**Requested by:** <@{presser}>")
        embed.description = "\n".join(description_lines)

        now = datetime.now()
        unix_timestamp = int(now.timestamp())
        embed.add_field(name="**Reason**", value=reason, inline=False)
        embed.add_field(name="**Submited**", value=f"<t:{unix_timestamp}:R>", inline=False)
        embed.add_field(name="**Note**", value=note, inline=False)

        
        image_url = "https://i.ibb.co/Kpsfc8Jm/jack.webp"
        embed.set_footer(text="Brought to you by Sumnor", icon_url=image_url)

        await interaction.edit_original_response(embed=embed, view=GrantView())