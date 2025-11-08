import discord
from typing import List
from general_war_utils import get_nation_info

class ParticipantView(discord.ui.View):
    def __init__(self, participants: List[str], api_key: str, war_id: str):
        super().__init__(timeout=None)
        self.participants = participants
        self.api_key = api_key
        self.war_id = war_id
        self.current_index = 0
        
    async def get_current_embed(self) -> discord.Embed:
        try:
            current_nation_id = self.participants[self.current_index]
            nation_info = await get_nation_info(current_nation_id, self.api_key)
            
            embed = discord.Embed(
                title=f"👤 Participant {self.current_index + 1}/{len(self.participants)} - War {self.war_id}",
                description=f"**{nation_info.get('nation_name', 'Unknown Nation')}**\n*Leader: {nation_info.get('leader_name', 'Unknown')}*",
                color=discord.Color.blue()
            )
            
            resistance = nation_info.get('resistance', 0)
            military_power = nation_info.get('military_power', 0)
            
            embed.add_field(
                name="💪 Military Readiness",
                value=f"**Resistance:** {resistance:.1f}%\n**Military Power:** {military_power:,}",
                inline=True
            )
            
            soldiers = nation_info.get('soldiers', 0)
            tanks = nation_info.get('tanks', 0)
            aircraft = nation_info.get('aircraft', 0)
            ships = nation_info.get('ships', 0)
            
            embed.add_field(
                name="🏗️ Current Forces",
                value=(
                    f"👥 Soldiers: **{soldiers:,}**\n"
                    f"🚛 Tanks: **{tanks:,}**\n"
                    f"✈️ Aircraft: **{aircraft:,}**\n"
                    f"🚢 Ships: **{ships:,}**"
                ),
                inline=True
            )
            
            embed.add_field(name="\u200b", value="\u200b", inline=True)
            
            wars = nation_info.get('wars', {}).get('data', [])
            current_war = None
            for war in wars:
                if str(war.get('id')) == str(self.war_id):
                    current_war = war
                    break
            
            if current_war:
                is_attacker = str(current_war.get('att_id', '')) == current_nation_id
                
                if is_attacker:
                    war_resistance = current_war.get('att_resistance', resistance)
                    war_points = current_war.get('att_points', 0)
                    role = "🗡️ Attacker"
                else:
                    war_resistance = current_war.get('def_resistance', resistance)
                    war_points = current_war.get('def_points', 0)
                    role = "🛡️ Defender"
                
                embed.add_field(
                    name=f"⚔️ War Stats - {role}",
                    value=(
                        f"**Resistance:** {war_resistance:.1f}%\n"
                        f"**MAP Score:** {war_points}\n"
                        f"**Turns Left:** {current_war.get('turns_left', 'Unknown')}\n"
                        f"**War Type:** {current_war.get('war_type', 'Unknown').title()}"
                    ),
                    inline=True
                )
            else:
                embed.add_field(
                    name="⚔️ War Stats",
                    value="War data not found",
                    inline=True
                )
            
            alliance = nation_info.get('alliance', {})
            alliance_name = alliance.get('name', 'None')
            alliance_id = alliance.get('id', 'N/A')
            
            embed.add_field(
                name="🏛️ Alliance",
                value=f"**{alliance_name}** (ID: {alliance_id})",
                inline=True
            )
            
            embed.add_field(name="\u200b", value="\u200b", inline=True)
            
            total_military = soldiers + (tanks * 40) + (aircraft * 3) + (ships * 4)
            efficiency = (military_power / total_military * 100) if total_military > 0 else 0
            
            embed.add_field(
                name="📊 Military Efficiency",
                value=f"**{efficiency:.1f}%** efficiency rating\n*Based on unit composition*",
                inline=False
            )
            
            if resistance >= 75:
                embed.color = discord.Color.green()
            elif resistance >= 50:
                embed.color = discord.Color.yellow()
            elif resistance >= 25:
                embed.color = discord.Color.orange()
            else:
                embed.color = discord.Color.red()
            
            embed.set_footer(
                text=f"Use buttons to navigate • Nation ID: {current_nation_id} • Updated: {discord.utils.utcnow().strftime('%H:%M UTC')}"
            )
            
            return embed
            
        except Exception as e:
            return discord.Embed(
                title="❌ Error",
                description="Failed to load participant information",
                color=discord.Color.red()
            )
    
    @discord.ui.button(label="◀️ Previous", style=discord.ButtonStyle.secondary)
    async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_index > 0:
            self.current_index -= 1
        else:
            self.current_index = len(self.participants) - 1
            
        embed = await self.get_current_embed()
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="▶️ Next", style=discord.ButtonStyle.secondary)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_index < len(self.participants) - 1:
            self.current_index += 1
        else:
            self.current_index = 0
            
        embed = await self.get_current_embed()
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="🔄 Refresh", style=discord.ButtonStyle.primary)
    async def refresh_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Refresh current participant data"""
        await interaction.response.defer()
        embed = await self.get_current_embed()
        await interaction.edit_original_response(embed=embed, view=self)
    
    @discord.ui.button(label="📊 All Stats", style=discord.ButtonStyle.success)
    async def all_stats_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show summary of all participants"""
        await interaction.response.defer()
        
        embed = discord.Embed(
            title=f"📊 All Participants Summary - War {self.war_id}",
            description=f"Overview of all {len(self.participants)} participants",
            color=discord.Color.purple()
        )
        
        try:
            for i, nation_id in enumerate(self.participants):
                nation_info = await get_nation_info(nation_id, self.api_key)
                name = nation_info.get('nation_name', f'Nation {nation_id}')
                resistance = nation_info.get('resistance', 0)
                military_power = nation_info.get('military_power', 0)
                if resistance >= 75:
                    status = "🟢"
                elif resistance >= 50:
                    status = "🟡"
                elif resistance >= 25:
                    status = "🟠"
                else:
                    status = "🔴"
                
                embed.add_field(
                    name=f"{status} {name}",
                    value=f"**Res:** {resistance:.1f}%\n**MP:** {military_power:,}",
                    inline=True
                )
                if (i + 1) % 3 == 0:
                    embed.add_field(name="\u200b", value="\u200b", inline=False)
        
        except Exception as e:
            embed.add_field(
                name="❌ Error",
                value="Failed to load summary data",
                inline=False
            )
        
        embed.set_footer(text="Click Previous/Next to view individual details")
        await interaction.edit_original_response(embed=embed, view=self)