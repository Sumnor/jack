import discord


class PrevButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="◀ Previous", style=discord.ButtonStyle.secondary)
    
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        view = self.view
        view.current_page -= 1
        description = view.pages[view.current_page]
        embed = interaction.message.embeds[0]
        leaders = view.leaders if hasattr(view, 'leaders') else []
        officers = view.officers if hasattr(view, 'officers') else []
        
        new_description = ""
        if leaders:
            new_description += "**👑 Leaders:**\n" + "\n".join(view.format_member(m) for m in leaders) + "\n\n"
        if officers:
            new_description += "**🎖️ Officers:**\n" + "\n".join(view.format_member(m) for m in officers) + "\n\n"
        new_description += f"**👥 Members ({view.total_regular}):**\n" + "\n".join(description)
        
        embed.description = new_description[:4096]
        view.clear_items()
        if view.current_page > 0:
            view.add_item(PrevButton())
        if view.current_page < len(view.pages) - 1:
            view.add_item(NextButton())
        view.add_item(BackAAButton(view.original_embed, view))
        view.add_item(CloseAAButton())
        
        await interaction.edit_original_response(embed=embed, view=view)


class NextButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Next ▶", style=discord.ButtonStyle.secondary)
    
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        view = self.view
        view.current_page += 1
        description = view.pages[view.current_page]
        embed = interaction.message.embeds[0]
        leaders = view.leaders if hasattr(view, 'leaders') else []
        officers = view.officers if hasattr(view, 'officers') else []
        
        new_description = ""
        if leaders:
            new_description += "**👑 Leaders:**\n" + "\n".join(view.format_member(m) for m in leaders) + "\n\n"
        if officers:
            new_description += "**🎖️ Officers:**\n" + "\n".join(view.format_member(m) for m in officers) + "\n\n"
        new_description += f"**👥 Members ({view.total_regular}):**\n" + "\n".join(description)
        
        embed.description = new_description[:4096]
        view.clear_items()
        if view.current_page > 0:
            view.add_item(PrevButton())
        if view.current_page < len(view.pages) - 1:
            view.add_item(NextButton())
        view.add_item(BackAAButton(view.original_embed, view))
        view.add_item(CloseAAButton())
        
        await interaction.edit_original_response(embed=embed, view=view)


class BackAAButton(discord.ui.Button):
    def __init__(self, original_embed, parent_view):
        super().__init__(label="⬅ Back", style=discord.ButtonStyle.secondary)
        self.original_embed = original_embed
        self.parent_view = parent_view
    
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        self.parent_view.clear_items()
        self.parent_view.add_item(discord.ui.Button(label="Members", style=discord.ButtonStyle.primary, custom_id="members_button"))
        self.parent_view.add_item(discord.ui.Button(label="Average Build", style=discord.ButtonStyle.secondary, custom_id="avg_build_button"))
        self.parent_view.add_item(discord.ui.Button(label="Militarisation", style=discord.ButtonStyle.green, custom_id="wartime_mmr_button"))
        self.parent_view.add_item(discord.ui.Button(label="Bank Records", style=discord.ButtonStyle.success, custom_id="bank_button"))
        
        await interaction.edit_original_response(embed=self.original_embed, view=self.parent_view)


class CloseAAButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="✖ Close", style=discord.ButtonStyle.danger)
    
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await interaction.delete_original_response()