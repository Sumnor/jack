import discord
from discord.ui import View, button
from settings.settings_multi import get_banking_role

class GrantView(View):
    def __init__(self):
        super().__init__(timeout=None)

    async def is_government_member(self, interaction):
        BANKER = get_banking_role(interaction)
        if BANKER:
            return (
            any(role.name == BANKER for role in interaction.user.roles)
            )
        else:
            return None

    @button(label="✅ Sent", style=discord.ButtonStyle.green, custom_id="grant_approve")
    async def approve_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        if not await self.is_government_member(interaction):
            BANKER = get_banking_role(interaction)
            if BANKER:
                try:
                    await interaction.followup.send("❌ You need the 'Banker' role to approve grant requests.", ephemeral=True)
                except discord.NotFound:
                    pass  
                return

        try:
            embed = interaction.message.embeds[0]
            embed.color = discord.Color.green()
            embed.description += f"\n**Status:** ✅ **GRANT SENT**"

            image_url = "https://i.ibb.co/Kpsfc8Jm/jack.webp"
            embed.set_footer(text="Brought to you by Sumnor", icon_url=image_url)

            await interaction.edit_original_response(embed=embed, view=None)

            lines = embed.description.splitlines()
            user_mention = "@someone"
            for line in lines:
                if line.startswith("**Requested by:**"):
                    user_mention = line.split("**Requested by:**")[1].strip()
                    break

            try:
                await interaction.followup.send(f"✅ Grant request has been approved and sent! {user_mention}", ephemeral=False)
            except discord.NotFound:
                
                await interaction.channel.send(f"✅ Grant request has been approved and sent! {user_mention}")

        except Exception as e:
            try:
                await interaction.followup.send(f"❌ Error: `{e}`", ephemeral=True)
            except discord.NotFound:
                await interaction.channel.send(f"❌ Error (no followup): `{e}`")


    @button(label="🕒 Delay", style=discord.ButtonStyle.primary, custom_id="grant_delay")
    async def delay_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        if not await self.is_government_member(interaction):
            BANKER = get_banking_role(interaction)
            if BANKER:
                try:
                    await interaction.followup.send("❌ You need the 'Banker' role to approve grant requests.", ephemeral=True)
                except discord.NotFound:
                    pass  
                return

        try:
            embed = interaction.message.embeds[0]
            embed.color = discord.Color.orange()
            embed.description += f"\n**Status:** 🕒 **DELAYED**"
            image_url = "https://i.ibb.co/Kpsfc8Jm/jack.webp"
            embed.set_footer(text=f"Brought to you by Sumnor", icon_url=image_url)

            new_view = GrantView()
            new_view.remove_item(new_view.children[1]) 

            await interaction.edit_original_response(embed=embed, view=new_view)
            await interaction.message.pin()
            await interaction.followup.send("✅ Grant delayed and message pinned.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Error: `{e}`", ephemeral=True)

    @button(label="❌ Deny", style=discord.ButtonStyle.red, custom_id="grant_denied")
    async def deny_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        if not await self.is_government_member(interaction):
            BANKER = get_banking_role(interaction)
            if BANKER:
                try:
                    await interaction.followup.send("❌ You need the 'Banker' role to approve grant requests.", ephemeral=True)
                except discord.NotFound:
                    pass  
                return
        try:
            embed = interaction.message.embeds[0]
            embed.color = discord.Color.red()
            embed.description += f"\n**Status:** ❌ **GRANT DENIED**"
            image_url = "https://i.ibb.co/Kpsfc8Jm/jack.webp"
            embed.set_footer(text=f"Brought to you by Sumnor", icon_url=image_url)
            await interaction.edit_original_response(embed=embed, view=None)
        except Exception as e:
            await interaction.followup.send(f"❌ Error: `{e}`", ephemeral=True)