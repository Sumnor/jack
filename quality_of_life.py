import discord
from discord import app_commands
from bot_instance import bot, wrap_as_prefix_command
from utils import save_dm_to_sheet, cached_users
from settings_multi import get_gov_role
from discord_views import HelpView, NationInfoView
from graphql_requests import get_general_data, get_military, get_resources

@bot.tree.command(name="nation_info", description="Info on the chosen Nation")
@app_commands.describe(
    who="The Discord member to query",
    external_id="Raw Nation ID to override user lookup (optional)"
)
async def who_nation(interaction: discord.Interaction, who: discord.Member, external_id: str = "None"):
    await interaction.response.defer()
    global cached_users 
    async def is_banker():
        GOV_ROLE = get_gov_role(interaction)
        return (
            any(role.name == GOV_ROLE for role in interaction.user.roles)
        )

    user_id = str(interaction.user.id)
    own_id = None

    
    if external_id != "None":
        own_id = external_id.strip()
    else:

        
        guild_id = str(interaction.guild.id)
        target_id = str(who.id)
        user_id = str(interaction.user.id)
    
        user_data = cached_users.get(user_id)
        if not user_data:
            await interaction.followup.send(
                "❌ You are not registered. Please register first.", ephemeral=True
            )
            return

        user_data = cached_users.get(target_id)
        if not user_data:
            await interaction.followup.send(
                "❌ Your target is not registered", ephemeral=True
            )
            return
            
        
        own_id = str(user_data.get("NationID", "")).strip()

    
    try:
        nation_name, nation_leader, nation_score, war_policy, soldiers, tanks, aircraft, ships, spies, missiles, nuclear = get_military(own_id, interaction)
        gen_data = get_general_data(own_id, interaction)

        if not gen_data:
            await interaction.followup.send("❌ Failed to fetch general data.")
            return

        (
            alliance_id,
            alliance_position,
            alliance,
            domestic_policy,
            num_cities,
            colour,
            activity,
            project,
            turns_since_last_project
        ) = gen_data

        
        try:
            from datetime import datetime, timezone
            activity_dt = datetime.fromisoformat(activity)
            now = datetime.now(timezone.utc)
            delta = now - activity_dt
            if delta.total_seconds() < 60:
                activity_str = "just now"
            elif delta.total_seconds() < 3600:
                minutes = int(delta.total_seconds() // 60)
                activity_str = f"{minutes} minute{'s' if minutes != 1 else ''} ago"
            elif delta.total_seconds() < 86400:
                hours = int(delta.total_seconds() // 3600)
                activity_str = f"{hours} hour{'s' if hours != 1 else ''} ago"
            else:
                days = int(delta.total_seconds() // 86400)
                activity_str = f"{days} day{'s' if days != 1 else ''} ago"
        except Exception:
            activity_str = "Unknown"

        msg = (
            f"**📋 GENERAL INFOS:**\n"
            f"🌍 *Nation:* {nation_name} (Nation ID: `{own_id}`)\n"
            f"👑 *Leader:* {nation_leader}\n"
            f"🔛 *Active:* {activity_str}\n"
            f"🫂 *Alliance:* {alliance} (Alliance ID: `{alliance_id}`)\n"
            f"🎖️ *Alliance Position:* {alliance_position}\n"
            f"🏙️ *Cities:* {num_cities}\n"
            f"🎨 *Color Trade Bloc:* {colour}\n"
            f"📈 *Score:* {nation_score}\n"
            f"🚧 *Projects:* {project}\n"
            f"⏳ *Turn Since Last Project:* {turns_since_last_project}\n"
            f"📜 *Domestic Policy:* {domestic_policy}\n"
            f"🛡 *War Policy:* {war_policy}\n\n"

            f"**🛡 MILITARY FORCES:**\n"
            f"🪖 *Soldiers:* {soldiers}\n"
            f"🚛 *Tanks:* {tanks}\n"
            f"✈️ *Aircraft:* {aircraft}\n"
            f"🚢 *Ships:* {ships}\n"
            f"🕵️ *Spies:* {spies}\n"
            f"🚀 *Missiles:* {missiles}\n"
            f"☢️ *Nuclear Weapons:* {nuclear}"
        )

        embed = discord.Embed(
            title=f"🏳️🧑‍✈️ {nation_name}, lead by {nation_leader}",
            color=discord.Color.dark_embed(),
            description=msg
        )
        image_url = "https://i.ibb.co/Kpsfc8Jm/jack.webp"
        embed.set_footer(text="Brought to you by Sumnor", icon_url=image_url)

        nation_id = own_id
        view = NationInfoView(nation_id, embed)
        await interaction.followup.send(embed=embed, view=view)

    except Exception as e:
        await interaction.followup.send(f"❌ Error: {e}")

bot.command(name="nation_info")(wrap_as_prefix_command(who_nation.callback))

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

@bot.tree.command(name="send_message_to_channels", description="Send a message to multiple channels by their IDs")
@app_commands.describe(
    channel_ids="Space-separated list of channel IDs (e.g. 1319746766337478680 1357611748462563479)",
    message="The message to send to the channels"
)
async def send_message_to_channels(interaction: discord.Interaction, channel_ids: str, message: str):
    await interaction.response.defer()
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
    
    channel_ids_list = [cid.strip().replace("<#", "").replace(">", "") for cid in channel_ids.split()]

    
    async def is_banker(interaction):
        GOV_ROLE = get_gov_role(interaction)
        return (
            any(role.name == GOV_ROLE for role in interaction.user.roles)
        )

    if not await is_banker(interaction):
        await interaction.followup.send("❌ You don't have the rights, lil bro.")
        return

    sent_count = 0
    failed_count = 0

    from discord import TextChannel

    for channel_id in channel_ids_list:
        try:
            channel = await bot.fetch_channel(int(channel_id))
            if isinstance(channel, TextChannel):
                better_msg = message.replace(")(", "\n")
                await channel.send(better_msg)
                sent_count += 1
            else:
                failed_count += 1
        except Exception as e:
            failed_count += 1

    await interaction.followup.send(
        f"✅ Sent message to **{sent_count}** channel(s).\n"
        f"❌ Failed for **{failed_count}** channel(s)."
    )

bot.command(name="send_message_to_channels")(wrap_as_prefix_command(send_message_to_channels.callback))
