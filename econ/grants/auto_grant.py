import discord
from discord import app_commands
from settings.bot_instance import bot
from settings.settings_multi import get_banking_role, set_server_setting, get_server_setting

def is_auto_grant_enabled(guild_id: int) -> bool:
    config = get_server_setting(guild_id, 'AUTO_REQ_TOGGLE')
    return config


@bot.tree.command(name="toggle_auto_grant", description="Enable or disable automatic grant processing")
async def toggle_auto_grant(interaction: discord.Interaction, enabled: str):
        BANKER = get_banking_role(interaction)
        if BANKER:
            if not any(role.name == BANKER for role in interaction.user.roles):
                await interaction.response.send_message(
                    "❌ You need the 'Banker' role to change auto-grant settings.", 
                    ephemeral=True
                )
                return
        config = get_server_setting(interaction.guild.id, "AUTO_REQ_TOGGLE")
        
        if config == "false":
            config = 'true'
        elif config == 'true':
            config = 'false'
        elif not config:
            config == 'true'
        if set_server_setting(interaction.guild.id, "AUTO_REQ_TOGGLE", config):
            status = "✅ **ENABLED**" if enabled else "❌ **DISABLED**"
            mode_description = (
                "Grants will be **automatically sent** via PnW API and deducted from AA balance when approved." 
                if enabled else 
                "Grants will be **marked as sent** but must be processed manually through PnW."
            )
            
            embed = discord.Embed(
                title="⚙️ Auto-Grant Settings Updated",
                description=f"Auto-grant processing is now {status}\n\n{mode_description}",
                color=discord.Color.green() if enabled else discord.Color.orange()
            )
            embed.add_field(name="Guild", value=interaction.guild.name, inline=True)
            embed.add_field(name="Changed by", value=interaction.user.mention, inline=True)
            embed.set_footer(text="Use /toggle_auto_grant to change this setting")
            
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message(
                "❌ Failed to save configuration. Check file permissions.", 
                ephemeral=True
            )

@bot.tree.command(name="check_auto_grant", description="Check current auto-grant status")
async def check_auto_grant(interaction: discord.Interaction):
        """Check if auto-grant is enabled for this server"""
        
        enabled = is_auto_grant_enabled(interaction.guild_id)
        status = "✅ **ENABLED**" if enabled == 'true' else "❌ **DISABLED**"
        mode_description = (
            "Grants are **automatically sent** via PnW API and deducted from AA balance when approved." 
            if enabled == 'true' else 
            "Grants are **marked as sent** but must be processed manually through PnW."
        )
        
        embed = discord.Embed(
            title="⚙️ Auto-Grant Status",
            description=f"Auto-grant processing is {status}\n\n{mode_description}",
            color=discord.Color.green() if enabled else discord.Color.orange()
        )
        embed.add_field(name="Guild", value=interaction.guild.name, inline=True)
        embed.set_footer(text="Use /toggle_auto_grant to change this setting")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)