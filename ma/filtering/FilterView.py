import discord
import pandas as pd

class NationPaginationView(discord.ui.View):
    def __init__(self, df, filters):
        super().__init__(timeout=300)  
        self.df = df
        self.filters = filters
        self.current_page = 0
        self.per_page = 10
        self.max_pages = (len(df) + self.per_page - 1) // self.per_page
        
    def create_embed(self):
        embed = discord.Embed(
            title="🏴󠁧󠁢󠁳󠁣󠁴󠁿 Filtered Nations Results",
            description=f"Found **{len(self.df)}** nations matching your criteria",
            color=discord.Color.blue()
        )
        
        if self.filters:
            embed.add_field(
                name="🎯 Active Filters", 
                value="\n".join(f"• {f}" for f in self.filters), 
                inline=False
            )
        
        start_idx = self.current_page * self.per_page
        end_idx = start_idx + self.per_page
        page_nations = self.df.iloc[start_idx:end_idx]
        
        current_field_content = []
        current_field_length = 0
        field_count = 1
        
        for _, nation in page_nations.iterrows():
            alliance_name = "None"
            if nation.get('alliance_id_clean', 0) > 0:
                if pd.notna(nation.get('alliance.name')):
                    alliance_name = f"{nation['alliance.name']}"
                    if pd.notna(nation.get('alliance.acronym')) and nation['alliance.acronym']:
                        alliance_name += f" [{nation['alliance.acronym']}]"
                else:
                    alliance_name = f"AA ID: {nation['alliance_id_clean']}"
            
            beige_status = ""
            if nation.get('beige_turns', 0) > 0:
                beige_days_calc = nation['beige_turns'] // 12
                beige_status = f" 🟤({beige_days_calc}d)"
            
            nation_info = (
                f"**{nation.get('nation_name', 'Unknown')}** - {nation.get('num_cities', 0)}c | "
                f"{nation.get('score', 0):,.0f} score{beige_status}\n"
                f"Military: {nation.get('soldiers', 0):,}👥 {nation.get('tanks', 0):,}🚗 {nation.get('aircraft', 0):,}✈️ {nation.get('ships', 0):,}🚢\n"
                f"Alliance: {alliance_name}\n"
                f"[Nation](https://politicsandwar.com/nation/id={nation.get('id', 0)}) | "
                f"[Espionage](https://politicsandwar.com/nation/espionage/eid={nation.get('id', 0)}) | "
                f"[War](https://politicsandwar.com/nation/war/declare/id={nation.get('id', 0)})"
            )
            
            
            if current_field_length + len(nation_info) > 1024 and current_field_content:
                embed.add_field(
                    name=f"🏆 Results (cont.)", 
                    value="\n\n".join(current_field_content), 
                    inline=False
                )
                current_field_content = [nation_info]
                current_field_length = len(nation_info)
                field_count += 1
            else:
                current_field_content.append(nation_info)
                current_field_length += len(nation_info)
                
        
        if current_field_content:
            embed.add_field(
                name=f"🏆 Results (Page {self.current_page + 1}/{self.max_pages})", 
                value="\n\n".join(current_field_content), 
                inline=False
            )
        
        stats = []
        stats.append(f"Avg Cities: {self.df['num_cities'].mean():.1f}")
        stats.append(f"Avg Score: {self.df['score'].mean():,.0f}")
        
        embed.add_field(name="📊 Statistics", value=" | ".join(stats), inline=False)
        embed.set_footer(text=f"Page {self.current_page + 1}/{self.max_pages} • {len(self.df)} total results")
        
        return embed
    
    @discord.ui.button(label='◀️ Previous', style=discord.ButtonStyle.secondary)
    async def previous_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page > 0:
            self.current_page -= 1
            embed = self.create_embed()
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.defer()
    
    @discord.ui.button(label='▶️ Next', style=discord.ButtonStyle.secondary)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page < self.max_pages - 1:
            self.current_page += 1
            embed = self.create_embed()
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.defer()
    
    async def on_timeout(self):
        
        for item in self.children:
            item.disabled = True

