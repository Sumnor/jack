import discord
from discord import app_commands
from settings.bot_instance import bot, wrap_as_prefix_command
from settings.initializer_functions.cached_users_initializer import cached_users
from information.nation_info.nation_information import NationInfoView
from information.alliance_info.alliance_information import AllianceInfoView
from databases.graphql_requests import get_general_data, get_military
from information.info_who import identifier

@bot.tree.command(name="info", description="Info on the chosen Nation or Alliance")
@app_commands.describe(
    who="UID, ID, or nation/alliance name (e.g. @sumnor_the_lazy, Neprito, 680627, 14207, INTRA, ...)"
)
async def info(interaction: discord.Interaction, who: str = None):
    await interaction.response.defer()
    global cached_users
    user_id = str(interaction.user.id)
    
    nation_id, discord_id, data, sub_operation = identifier(interaction, who, user_id)

    if nation_id == "Error":
        await interaction.followup.send(discord_id, ephemeral=True)  # discord_id contains error message
        return

        # --- NATION HANDLING ---
    if sub_operation in ["by_uid", "by_id", "by_nation_name", "by_name/username", "nation_id"]:
        try:
            if not nation_id:
                await interaction.followup.send("❌ Could not resolve a valid nation ID.", ephemeral=True)
                return

            # Fetch API data safely
            military_data = get_military(nation_id, interaction)
            if not military_data:
                await interaction.followup.send("❌ Failed to fetch military data.", ephemeral=True)
                return

            try:
                (
                    nation_name,
                    nation_leader,
                    nation_score,
                    war_policy,
                    soldiers,
                    tanks,
                    aircraft,
                    ships,
                    spies,
                    missiles,
                    nuclear
                ) = military_data
            except Exception:
                await interaction.followup.send("❌ Unexpected military data format.", ephemeral=True)
                return

            gen_data = get_general_data(nation_id, interaction)

            # Fallback if GraphQL returns None
            if not gen_data and data:
                gen_data = (
                    data.get("alliance_id"),
                    data.get("position", "Unknown"),
                    data.get("alliance_name", "None"),
                    data.get("domestic_policy", "Unknown"),
                    data.get("cities", "Unknown"),
                    data.get("color", "Unknown"),
                    data.get("last_active", "Unknown"),
                    data.get("projects", "Unknown"),
                    data.get("turns_since_last_project", "Unknown")
                )

            if not gen_data:
                await interaction.followup.send("❌ Failed to fetch general nation data.", ephemeral=True)
                return

            try:
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
            except Exception:
                await interaction.followup.send("❌ Unexpected general data format.", ephemeral=True)
                return

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

            # Build Nation Embed
            msg = (
                f"**📋 GENERAL INFO:**\n"
                f"🌍 *Nation:* [{nation_name}](https://politicsandwar.com/nation/id={nation_id}) (ID: `{nation_id}`)\n"
                f"👑 *Leader:* {nation_leader}\n"
                f"🔛 *Active:* {activity_str}\n"
                f"🫂 *Alliance:* [{alliance}](https://politicsandwar.com/alliance/id={alliance_id}) (ID: `{alliance_id}`)\n"
                f"🎖️ *Position:* {alliance_position}\n"
                f"🏙️ *Cities:* {num_cities}\n"
                f"🎨 *Color:* {colour}\n"
                f"📈 *Score:* {nation_score}\n"
                f"🚧 *Projects:* {project}\n"
                f"⏳ *Turns Since Last Project:* {turns_since_last_project}\n"
                f"📜 *Domestic Policy:* {domestic_policy}\n"
                f"🛡 *War Policy:* {war_policy}\n\n"
                f"**⚔️ MILITARY:**\n"
                f"🪖 Soldiers: {soldiers}\n"
                f"🚛 Tanks: {tanks}\n"
                f"✈️ Aircraft: {aircraft}\n"
                f"🚢 Ships: {ships}\n"
                f"🕵️ Spies: {spies}\n"
                f"🚀 Missiles: {missiles}\n"
                f"☢️ Nukes: {nuclear}"
            )

            embed = discord.Embed(
                title=f"🏳️🧑‍✈️ {nation_name}, led by {nation_leader}",
                color=discord.Color.dark_embed(),
                description=msg
            )
            image_url = "https://i.ibb.co/Kpsfc8Jm/jack.webp"
            embed.set_footer(text="Brought to you by Sumnor", icon_url=image_url)

            nation_id_str = str(nation_id)
            view = NationInfoView(nation_id_str, embed)
            await interaction.followup.send(embed=embed, view=view)

        except Exception as e:
            await interaction.followup.send(f"❌ Error while fetching nation info: {e}", ephemeral=True)

    # --- ALLIANCE HANDLING ---
    elif sub_operation in ["aa_id", "by_alliance_name"]:
        try:
            aa_id = str(data.get("id"))
            aa_name = data.get("name", "Unknown")
            aa_rank = data.get("rank", "Unknown")
            acronym = data.get("acronym", "Unknown")
            score = data.get("score", "Unknown")
            colour = data.get("colour", "Unknown")
            flag = data.get("flag")
            discord_link = data.get("discord_link")
            created = data.get("date", "Unknown")
            creation_unix = None
            if created:
                try:
                    if isinstance(created, str):
                        created_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                    else:
                        created_dt = created
                    creation_unix = int(created_dt.timestamp())
                except Exception:
                    creation_unix = None



            msg = (
                f"**🏰 ALLIANCE INFO:**\n"
                f"🫂 *Alliance:* [{aa_name}({acronym})](https://politicsandwar.com/alliance/id={aa_id})\n"
                f"🏷️ *ID:* `{aa_id}`\n"
                f"🏆 *Rank:* {aa_rank}\n"
                f"👑 *Score:* {score}\n"
                f"📅 *Created:* {'<t:' + str(creation_unix) + ':F>' if creation_unix else 'Unknown'}\n"
                f"🔗 *Discord Link:* {discord_link}"
            )

            embed = discord.Embed(
                title=f"🏰 {aa_name}",
                color=discord.Color.blue(),
                description=msg
            )
            embed.set_image(url=flag)
            embed.set_footer(text="Brought to you by Sumnor")
            view = AllianceInfoView(str(aa_id), embed)
            await interaction.followup.send(view=view, embed=embed)

        except Exception as e:
            await interaction.followup.send(f"❌ Error while fetching alliance info: {e}", ephemeral=True)

bot.command(name="info")(wrap_as_prefix_command(info.callback))