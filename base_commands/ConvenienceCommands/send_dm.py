import discord
from discord import app_commands
from settings.bot_instance import bot, wrap_as_prefix_command
from settings.initializer_functions.cached_users_initializer import cached_users
from settings.initializer_functions.dm_save_initializer import save_dm_to_sheet
from settings.settings_multi import get_gov_role

@bot.tree.command(name="dm_user", description="DM a user by mentioning them")
@app_commands.describe(
    user="Mention the user to DM",
    message="The message to send"
)
async def dm_user(interaction: discord.Interaction, user: discord.User, message: str):
    await interaction.response.defer(ephemeral=True)
    user_id = str(interaction.user.id)
    
    global cached_users  
    
    guild_id = str(interaction.guild.id)
    user_id = str(interaction.user.id)

    user_data = cached_users.get(user_id)
    if not user_data:
        await interaction.followup.send(
            "❌ You are not registered. Please register first.", ephemeral=True
        )
        return
    
    own_id = str(user_data.get("NationID", "")).strip()

    if not own_id:
            await interaction.followup.send("❌ Could not find your Nation ID in the sheet.")
            return
    async def is_banker(interaction):
        GOV_ROLE = get_gov_role(interaction)
        return (
            any(role.name == GOV_ROLE for role in interaction.user.roles)
        )

    if not await is_banker(interaction):
        await interaction.followup.send("❌ You don't have the rights, lil bro.")
        return
    better_msg = message.replace(")(", "\n")
    try:
        await user.send(better_msg)
        await interaction.followup.send(f"✅ Sent DM to {user.mention}")

        
        save_dm_to_sheet(interaction.user.name, user.name, better_msg)

    except discord.Forbidden:
        await interaction.followup.send(f"❌ Couldn't send DM to {user.mention} (they may have DMs disabled).")
    except Exception as e:
        await interaction.followup.send(f"❌ An error occurred: {e}")

bot.command(name="dm_user")(wrap_as_prefix_command(dm_user.callback))