import discord
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from information.nation_info.nation_information import NationInfoView

class PrevPageButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="⬅ Prev", style=discord.ButtonStyle.secondary)

    async def callback(self, interaction: discord.Interaction):
        view: "NationInfoView" = self.view
        if view.current_page > 0:
            view.current_page -= 1
            try:
                await view.show_current_page(interaction)
            except discord.NotFound:
                await interaction.response.send_message("This interaction has expired.", ephemeral=True)


class NextPageButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Next ➡", style=discord.ButtonStyle.secondary)

    async def callback(self, interaction: discord.Interaction):
        view: "NationInfoView" = self.view
        if view.current_page < len(view.pages) - 1:
            view.current_page += 1
            try:
                await view.show_current_page(interaction)
            except discord.NotFound:
                await interaction.response.send_message("This interaction has expired.", ephemeral=True)

class BackButton(discord.ui.Button):
    def __init__(self, original_embed, parent_view):
        super().__init__(label="Back", style=discord.ButtonStyle.success)
        self.original_embed = original_embed
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        view = self.parent_view
        view.clear_items()
        # Re-add main buttons
        view.add_item(view.builds_button)
        view.add_item(view.projects_button)
        view.add_item(view.wartime_mmr_button)
        view.add_item(view.audit_button)
        view.add_item(view.mmr_button)
        view.add_item(view.wars_button)
        view.add_item(view.trades_button)
        view.add_item(view.bank_button)
        view.add_item(CloseButton())

        try:
            await interaction.response.edit_message(embed=self.original_embed, view=view)
        except discord.NotFound:
            await interaction.response.send_message("Interaction expired.", ephemeral=True)

class CloseButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Close", style=discord.ButtonStyle.danger)

    async def callback(self, interaction: discord.Interaction):
        try:
            await interaction.message.delete()
        except (discord.NotFound, discord.Forbidden):
            try:
                await interaction.response.edit_message(content="This interaction has been closed.", embed=None, view=None)
            except:
                pass
        finally:
            self.view.stop()
