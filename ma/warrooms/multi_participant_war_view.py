import discord
from typing import List
from general_war_utils import get_nation_info

class MultiWarParticipantView(discord.ui.View):
    
    def __init__(self, participants: List[str], api_key: str, all_war_ids: List[str]):
        super().__init__(timeout=None)
        self.participants = participants
        self.api_key = api_key
        self.all_war_ids = all_war_ids
        self.current_participant = 0
        self.current_war = 0
        
    async def get_current_embed(self) -> discord.Embed:
        """Get embed showing current participant's status across all their wars"""
        try:
            current_nation_id = self.participants[self.current_participant]
            nation_info = await get_nation_info(current_nation_id, self.api_key)
            
            embed = discord.Embed(
                title=f"🌟 Multi-War Participant {self.current_participant + 1}/{len(self.participants)}",
                description=f"**{nation_info.get('nation_name', 'Unknown Nation')}**\n*All active wars overview*",
                color=discord.Color.gold()
            )
            resistance = nation_info.get('resistance', 0)
            military_power = nation_info.get('military_power', 0)
            
            embed.add_field(
                name="💪 Overall Status",
                value=f"**Resistance:** {resistance:.1f}%\n**Military Power:** {military_power:,}",
                inline=True
            )
            wars = nation_info.get('wars', {}).get('data', [])
            relevant_wars = [w for w in wars if str(w.get('id')) in self.all_war_ids]
            
            if relevant_wars:
                war_summary = []
                total_maps = 0
                
                for war in relevant_wars[:5]:  # Show up to 5 wars
                    war_id = war.get('id')
                    turns_left = war.get('turns_left', 'Unknown')
                    if str(war.get('att_id', '')) == current_nation_id:
                        role = "🗡️"
                        points = war.get('att_points', 0)
                        war_resistance = war.get('att_resistance', resistance)
                    else:
                        role = "🛡️"
                        points = war.get('def_points', 0)
                        war_resistance = war.get('def_resistance', resistance)
                    
                    total_maps += points
                    status = "🟢" if war_resistance > 50 else "🔴" if war_resistance < 25 else "🟡"
                    
                    war_summary.append(f"{role} **War {war_id}**: {points} MAPs {status}")
                
                embed.add_field(
                    name=f"⚔️ Active Wars ({len(relevant_wars)})",
                    value="\n".join(war_summary) + f"\n\n**Total MAPs:** {total_maps}",
                    inline=False
                )
            else:
                embed.add_field(
                    name="⚔️ Wars",
                    value="No active wars found",
                    inline=False
                )
            
            embed.set_footer(
                text=f"Multi-war overview • Use buttons to navigate • Updated: {discord.utils.utcnow().strftime('%H:%M UTC')}"
            )
            
            return embed
            
        except Exception as e:
            print(f"Error creating multi-war participant embed: {e}")
            return discord.Embed(
                title="❌ Error",
                description="Failed to load multi-war participant information",
                color=discord.Color.red()
            )
    
    @discord.ui.button(label="◀️ Prev Nation", style=discord.ButtonStyle.secondary)
    async def previous_nation(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Navigate to previous nation"""
        if self.current_participant > 0:
            self.current_participant -= 1
        else:
            self.current_participant = len(self.participants) - 1
            
        embed = await self.get_current_embed()
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="▶️ Next Nation", style=discord.ButtonStyle.secondary)
    async def next_nation(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Navigate to next nation"""
        if self.current_participant < len(self.participants) - 1:
            self.current_participant += 1
        else:
            self.current_participant = 0
            
        embed = await self.get_current_embed()
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="🔄 Refresh", style=discord.ButtonStyle.primary)
    async def refresh_data(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Refresh current data"""
        await interaction.response.defer()
        embed = await self.get_current_embed()
        await interaction.edit_original_response(embed=embed, view=self)