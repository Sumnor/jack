import discord
from settings.bot_instance import bot, wrap_as_prefix_command
from settings.initializer_functions.cached_users_initializer import cached_users
from settings.settings_multi import get_gov_role
from base_commands.ConvenienceCommands.HelpView import HelpView

@bot.tree.command(name="help", description="Get the available commands")
async def help(interaction: discord.Interaction):
    await interaction.response.defer()
    user_id = str(interaction.user.id)
    
    global cached_users  
    
    user_data = cached_users.get(user_id)
    if not user_data:
        await interaction.followup.send(
            "❌ You are not registered. Please register first using `/register`.", ephemeral=True
        )
        return
    
    own_id = str(user_data.get("NationID", "")).strip()
    if not own_id:
        await interaction.followup.send("❌ Could not find your Nation ID in the sheet.")
        return
    async def is_high_power(interaction):
        GOV_ROLE = get_gov_role(interaction)
        return any(role.name == GOV_ROLE for role in interaction.user.roles)
    
    is_gov = await is_high_power(interaction)
    view = HelpView(user_id, is_gov)
    embed = view.create_embed()
    
    await interaction.followup.send(embed=embed, view=view)

bot.command(name="help")(wrap_as_prefix_command(help.callback))