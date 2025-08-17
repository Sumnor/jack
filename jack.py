from datetime import datetime, timezone, timedelta
import asyncio
import discord
import requests
import datetime
import pandas as pd
from discord.ext import tasks
import os
import re
from bot_instance import bot_key, bot
from discord_views import TicketButtonView, GrantView, BlueGuy
from settings_multi import get_alliance_sheet, get_settings_sheet, get_warn_channel, get_api_key_for_interaction, get_grant_channel
from graphql_requests import graphql_request, get_general_data, get_resources
from utils import get_registration_sheet, load_registration_data, get_sheet_s, save_to_alliance_net, get_prices, get_ticket_sheet,  cached_users, load_sheet_data

UNIT_PRICES = {
    "soldiers": 5,x
    "tanks": 60,
    "aircraft": 4000,
    "ships": 50000,
    "missiles": 150000,
    "nuclear": 1750000
}

def parse_amount(amount):
    if isinstance(amount, (int, float)):
        return amount

    amount = str(amount).lower().replace(",", "").strip()
    match = re.match(r"^([\d\.]+)\s*(k|m|mil|million)?$", amount)
    if not match:
        raise ValueError(f"Invalid amount format: {amount}")

    num, suffix = match.groups()
    num = float(num)

    if suffix in ("k",):
        return int(num * 1_000)
    elif suffix in ("m", "mil", "million"):
        return int(num * 1_000_000)
    return int(num)

@bot.event
async def on_guild_join(guild):
    
    embed = discord.Embed(
        title="🎉 Thanks for adding me!",
        description=f"Hello **{guild.name}**! I'm ready to help your server.",
        color=0x00ff00 
    )
    
    embed.add_field(
        name="🚀 Getting Started", 
        value="Use `/help` to see all available commands, use `/bot_info_and_invite` for all the bot info", 
        inline=False
    )
    
    embed.add_field(
        name="⚙️ Setup", 
        value=(
            "- Run the `/register_server_aa` command (If you already did so once, don't do it again)\n"
            "- Using `/set_setting` set the different settings like API KEY, Channels, etc\n"
            "- Register yourself using `/register` and enjoy the bot"
        ), 
        inline=False
    )
    
    embed.add_field(
        name="🔗 Support", 
        value="Need help? Join the discord server: [Jack Support](https://discord.gg/qqtb3kccjv)", 
        inline=False
    )
    
    embed.set_footer(
        text=f"Joined {guild.name} • {len(guild.members)} members",
        icon_url=bot.user.avatar.url if bot.user.avatar else None
    )
    
    embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
    
    channel = None
    
    channel_names = ['general', 'welcome', 'main', 'chat', 'lobby']
    
    for name in channel_names:
        channel = discord.utils.get(guild.text_channels, name=name)
        if channel and channel.permissions_for(guild.me).send_messages:
            break
    
    if not channel:
        for text_channel in guild.text_channels:
            if text_channel.permissions_for(guild.me).send_messages:
                channel = text_channel
                break
    
    if not channel and guild.system_channel:
        if guild.system_channel.permissions_for(guild.me).send_messages:
            channel = guild.system_channel

    if channel:
        try:
            await channel.send(embed=embed)
            print(f"Sent welcome message to {guild.name} in #{channel.name}")
        except discord.Forbidden:
            print(f"No permission to send message in {guild.name}")
        except Exception as e:
            print(f"Error sending welcome message to {guild.name}: {e}")
    else:
        print(f"Could not find a suitable channel in {guild.name}")
    
    try:
        owner_embed = discord.Embed(
            title="🎉 Bot Added Successfully!",
            description=f"Thank you for adding me to **{guild.name}**!",
            color=0x0099ff
        )
        
        owner_embed.add_field(
            name="📋 Quick Setup Tips",
            value="• Make sure I have `Send Messages` and `Embed Links` permissions\n"
                  "• Use `/help` to see all commands\n"
                  "• Check out the setup guide in the discord message",
            inline=False
        )
        
        await guild.owner.send(embed=owner_embed)
        print(f"Sent DM to owner of {guild.name}")
        
    except discord.Forbidden:
        print(f"Could not DM owner of {guild.name}")
    except Exception as e:
        print(f"Error DMing owner of {guild.name}: {e}")

@tasks.loop(hours=1)
async def process_auto_requests():
    from raws_requests import get_auto_requests_sheet
    REASON_FOR_GRANT = "Resources for Production (Auto)"
    
    try:
        guilds = bot.guilds
        
        if not guilds:
            print("No guilds found")
            return
        
        now = datetime.datetime.now(timezone.utc)
        
        for guild in guilds:
            try:
                print(f"Processing guild: {guild.name} ({guild.id})")
                
                channel_id = get_grant_channel(guild.id)
                if not channel_id:
                    print(f"No grant channel configured for guild: {guild.name} ({guild.id})")
                    continue
                
                channel = guild.get_channel(int(channel_id))
                if channel is None:
                    continue
                
                sheet = get_auto_requests_sheet(guild.id)
                if not sheet:
                    continue
                
                all_rows = await asyncio.to_thread(sheet.get_all_values)
                if not all_rows or len(all_rows) < 2:
                    continue
                
                header = [h.strip() for h in all_rows[0] if h.strip()]
                if len(header) != len(set(header)):
                    raise ValueError(f"Guild {guild.name} sheet header row contains duplicates or blanks: {header}")
                
                col_index = {col: idx for idx, col in enumerate(all_rows[0])}
                rows = all_rows[1:]
                
                processed_count = 0
                
                for i, row in enumerate(rows, start=2):
                    try:
                        nation_id = row[col_index.get("NationID", -1)] if col_index.get("NationID", -1) != -1 else ""
                        if not nation_id:
                            print(f"Guild {guild.name}, row {i}: Skipping due to empty NationID")
                            continue
                        
                        nation_info_df = graphql_request(nation_id, None, guild.id)
                        nation_name = nation_info_df.loc[0, "nation_name"] if nation_info_df is not None and not nation_info_df.empty else "Unknown"
                        
                        discord_id = row[col_index["DiscordID"]]
                        time_period_days = int(float(row[col_index["TimePeriod"]].strip() or "1"))
                        
                        last_requested_str = row[col_index["LastRequested"]].strip()
                        last_requested = (
                            datetime.strptime(last_requested_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
                            if last_requested_str else datetime.min.replace(tzinfo=timezone.utc)
                        )
                        
                        if now - last_requested < timedelta(days=time_period_days):
                            continue
                        
                        requested_resources = {}
                        for res in ["Coal", "Oil", "Bauxite", "Lead", "Iron"]:
                            val_str = row[col_index[res]].strip()
                            amount = parse_amount(val_str)
                            if amount > 0:
                                requested_resources[res] = amount
                        
                        if not requested_resources:
                            continue
                        
                        description_text = "\n".join([f"{resource}: {amount:,}".replace(",", ".") for resource, amount in requested_resources.items()])
                        
                        embed = discord.Embed(
                            title="💰 Grant Request",
                            color=discord.Color.gold(),
                            description=(
                                f"**Nation:** {nation_name} (`{nation_id}`)\n"
                                f"**Requested by:** <@{discord_id}>\n"
                                f"**Request:**\n{description_text}\n"
                                f"**Reason:** {REASON_FOR_GRANT}\n"
                            )
                        )
                        image_url = "https://i.ibb.co/Kpsfc8Jm/jack.webp"
                        embed.set_footer(text="Brought to you by Sumnor", icon_url=image_url)
                        
                        await channel.send(embed=embed, view=GrantView())
                        
                        await asyncio.to_thread(sheet.update_cell, i, col_index["LastRequested"] + 1, now.strftime("%Y-%m-%d %H:%M:%S"))
                        processed_count += 1
                        
                        await asyncio.sleep(0.5)
                        
                    except Exception as inner_ex:
                        print(f"Error processing guild {guild.name}, row {i}: {inner_ex}")
                
                print(f"Processed {processed_count} requests from guild: {guild.name}")
                
            except Exception as guild_ex:
                print(f"Error processing guild {guild.name}: {guild_ex}")
    
    except Exception as ex:
        print(f"Error in process_auto_requests task: {ex}")
    
@tasks.loop(hours=1)
async def hourly_snapshot():
    now = datetime.datetime.now(timezone.utc)
    current_hour = now.replace(minute=0, second=0, microsecond=0)

    guild_ids_to_process = set()
    for guild in bot.guilds:
        guild_id = str(guild.id)
        try:
            alliance_sheet = get_alliance_sheet(guild_id)
            rows = alliance_sheet.get_all_records()
            if rows:
                last_time_str = rows[-1].get("TimeT", "")
                try:
                    last_time = datetime.datetime.fromisoformat(last_time_str)
                    if last_time.replace(minute=0, second=0, microsecond=0) == current_hour:
                        print(f"⏭ Already saved snapshot for guild {guild_id}")
                        continue
                except ValueError:
                    print(f"⚠️ Invalid timestamp in sheet for guild {guild_id}: {last_time_str}")
            guild_ids_to_process.add(guild_id)
        except Exception as e:
            print(f"❌ Could not access alliance sheet for guild {guild_id}: {e}")

    if not guild_ids_to_process:
        print("✅ All guilds already processed this hour.")
        return
    try:
        settings_sheet = get_settings_sheet()
        settings_rows = settings_sheet.get_all_records()
    except Exception as e:
        print(f"❌ Failed to get settings sheet: {e}")
        return

    guild_settings = {}
    for row in settings_rows:
        server_id = str(row.get("server_id")).strip()
        key = row.get("key", "").strip()
        value = str(row.get("value", "")).strip()
        
        if server_id in guild_ids_to_process and isinstance(value, str) and value:
            if server_id not in guild_settings:
                guild_settings[server_id] = {}
            guild_settings[server_id][key] = value
    valid_guild_settings = {
        guild_id: settings for guild_id, settings in guild_settings.items()
        if "API_KEY" in settings and "AA_NAME" in settings
    }

    if not valid_guild_settings:
        print("⚠️ No guilds found with both API_KEY and AA_NAME settings.")
        return
    load_sheet_data()
    for guild_id, settings in valid_guild_settings.items():
        api_key = settings["API_KEY"]
        target_aa_name = settings["AA_NAME"]
        
        try:
            all_users = cached_users
            print(f"👥 Guild {guild_id}: {len(all_users)} total registered users in global sheet")

            if not all_users:
                print(f"⚠️ Skipping guild {guild_id} (no users in global sheet)")
                continue
            filtered_users = {}
            match_count = 0
            
            print(f"🎯 Target AA: '{target_aa_name}'")
            
            for user_id, user in all_users.items():
                user_aa = str(user.get("AA", "")).strip()
                
                if user_aa.lower() == target_aa_name.lower():
                    match_count += 1
                    filtered_users[user_id] = user

            print(f"🔍 Guild {guild_id}: Found {match_count} users in '{target_aa_name}' alliance")

            if not filtered_users:
                print(f"⚠️ Skipping guild {guild_id} (no users in target alliance '{target_aa_name}')")
                continue
            prices = {}
            try:
                res = requests.post(
                    f"https://api.politicsandwar.com/graphql?api_key={api_key}",
                    json={"query": "{ top_trade_info { resources { resource average_price } } }"},
                    headers={"Content-Type": "application/json"}
                )
                res.raise_for_status()
                resources_data = res.json()["data"]["top_trade_info"]["resources"]
                prices = {r["resource"]: float(r["average_price"]) for r in resources_data}
            except Exception as e:
                print(f"⚠️ Failed to fetch prices for guild {guild_id}: {e}")

            totals = {
                "money": 0, "food": 0, "gasoline": 0, "munitions": 0,
                "steel": 0, "aluminum": 0, "bauxite": 0, "lead": 0,
                "iron": 0, "oil": 0, "coal": 0, "uranium": 0, "num_cities": 0
            }
            processed, failed = 0, 0
            seen_ids = set()
            for user_id, user in filtered_users.items():
                nation_id = str(user.get("NationID", "")).strip()
                if not nation_id or nation_id in seen_ids:
                    failed += 1
                    continue
                seen_ids.add(nation_id)

                try:
                    _, cities, food, money, gasoline, munitions, steel, aluminum, bauxite, lead, iron, oil, coal, uranium = get_resources(nation_id, None, guild_id)
                    if not money:
                        raise ValueError("No data returned")
                    totals["money"] += money
                    totals["food"] += food
                    totals["gasoline"] += gasoline
                    totals["munitions"] += munitions
                    totals["steel"] += steel
                    totals["aluminum"] += aluminum
                    totals["bauxite"] += bauxite
                    totals["lead"] += lead
                    totals["iron"] += iron
                    totals["oil"] += oil
                    totals["coal"] += coal
                    totals["uranium"] += uranium
                    totals["num_cities"] += cities
                    processed += 1
                except Exception as e:
                    failed += 1
                    print(f"❌ Failed for user {user_id} (guild {guild_id}): {e}")
                await asyncio.sleep(5)
            wealth = totals["money"]
            resource_values = {}
            for res, amt in totals.items():
                if res in ["money", "num_cities"]:
                    continue
                val = amt * prices.get(res, 0)
                resource_values[res] = val
                wealth += val

            save_row = [current_hour.isoformat(), wealth, totals["money"]]
            for res in [
                "food", "gasoline", "munitions", "steel", "aluminum",
                "bauxite", "lead", "iron", "oil", "coal", "uranium"
            ]:
                save_row.append(resource_values.get(res, 0))

            try:
                save_to_alliance_net(save_row, guild_id=guild_id)
                print(f"✅ Saved snapshot for guild {guild_id} (AA: '{target_aa_name}'): ${wealth:,.0f} ({processed} processed, {failed} failed)")
            except Exception as e:
                print(f"❌ Failed to save snapshot for guild {guild_id}: {e}")

        except Exception as e:
            print(f"❌ General error in guild {guild_id}: {e}")

@tasks.loop(hours=2)
async def check_api_loop():
    nation_id = "680627"

    for guild in bot.guilds:
        try:
            channel_id = get_warn_channel(guild.id)
            if not channel_id:
                print(f"⚠️ No WARN_CHANNEL configured for guild: {guild.name} ({guild.id})")
                continue

            channel = guild.get_channel(int(channel_id))
            if channel is None:
                print(f"⚠️ WARN_CHANNEL ID {channel_id} not found in guild {guild.name}")
                continue

            score = get_nation_score(nation_id)

            if score is None:
                message1 = (
                    f"# ❗ Important ❗\n"
                    f"The PnW API is currently **offline**, so commands which rely on it are unavailable:\n"
                    f"- All `/request_...` commands\n"
                    f"- `/nation_info`\n"
                    f"You will be notified when the API is back online. Thank you for your understanding. ||<@&1192368632622219305>||"
                )
                await channel.send(message1)

                for _ in range(12):  # 12 * 5min = 1 hour of checking
                    await asyncio.sleep(300)
                    score = get_nation_score(nation_id)
                    if score is not None:
                        message2 = (
                            f"# ✅ Good News ✅\n"
                            f"The API is back online! 🎉\n"
                            f"You may now use all bot commands again. Thank you for your patience 🍪 ||<@&1192368632622219305>||"
                        )
                        await channel.send(message2)
                        break

        except Exception as e:
            print(f"❌ Error processing guild {guild.name}: {e}")


def get_nation_score(nation_id: str) -> float | None:
    API_KEY = get_api_key_for_interaction(interaction=discord.Interaction)
    GRAPHQL_URL = f"https://api.politicsandwar.com/graphql?api_key={API_KEY}"
    query = """
    query ($id: [Int!]) {
      nations(id: $id) {
        data {
          id
          nation_name
          score
        }
      }
    }
    """
    variables = {"id": [int(nation_id)]}
    try:
        res = requests.post(GRAPHQL_URL, json={"query": query, "variables": variables})
        res.raise_for_status()
        data = res.json()
        nation_data = data["data"]["nations"]["data"]
        if not nation_data:
            return None
        return float(nation_data[0]["score"])
    except Exception as e:
        print(f"[ERROR] get_nation_score: {e}")
        return None

@hourly_snapshot.before_loop
async def before_hourly():
    print("Waiting for bot to be ready before starting hourly snapshots...")
    await bot.wait_until_ready()

@tasks.loop(hours=168)  # runs weekly
async def weekly_member_updater():
    print(f"[Updater] Starting weekly member update at {datetime.datetime.utcnow()}")
    try:
        dummy_guild_id = "I'm too lazy to remove it from get_registration_sheet so this is a"
        
        sheet = get_registration_sheet(dummy_guild_id)
        records = sheet.get_all_records()
        df = pd.DataFrame(records)
        df.columns = [col.strip() for col in df.columns]

        if "NationID" not in df.columns:
            print(f"[Updater] 'NationID' column missing in registration sheet")
            return

        print(f"[Updater] Processing {len(df)} nations from registration sheet")

        for index, row in df.iterrows():
            nation_id = row.get("NationID")
            if not nation_id:
                continue
            guild_id = str(bot.guilds[0].id) if bot.guilds else dummy_guild_id
            
            result = get_general_data(nation_id, None, API_KEY=(os.getenv("API_KEY")))
            if result is None or len(result) < 7:
                print(f"[Updater] Failed to retrieve data for nation {nation_id}")
                continue

            _, _, alliance_name, _, _, _, last_active, *_ = result
            cell_range = f"D{index + 2}"
            sheet.update_acell(cell_range, alliance_name)

            print(f"[Updater] Updated nation {nation_id} with AA: {alliance_name}")
            await asyncio.sleep(30)  # Delay to respect API limits

    except Exception as e:
        print(f"[Updater] Unhandled error during update: {e}")

@weekly_member_updater.before_loop
async def before_updater():
    await bot.wait_until_ready()
    print("[Updater] Bot is ready. Waiting for weekly loop to begin.")

@bot.event
async def on_ready():
    bot.add_view(GrantView())  
    load_sheet_data()
    load_registration_data()
    bot.add_view(BlueGuy())
    import discord_views
    import tickets
    import settings_multi
    import request_x
    import graphql_requests
    import spying
    import war
    import quality_of_life
    import res_details
    import raws_requests
    import base_commands
    import request_build
    try:
        sheet = get_ticket_sheet()
        records = sheet.get_all_records()
        
        for row in records:
            message_id = int(row["message_id"])
            bot.add_view(TicketButtonView(message_id=message_id), message_id=message_id)
        
        print(f"✅ Restored {len(records)} persistent ticket views")
    except Exception as e:
        print(f"⚠️ Failed to load ticket views: {e}")
        bot.add_view(TicketButtonView())
    
    print("Starting hourly snapshot task...")
    if not hourly_snapshot.is_running():
        hourly_snapshot.start()
    if not process_auto_requests.is_running():
        process_auto_requests.start()
    if not weekly_member_updater.is_running():
        weekly_member_updater.start()
    if not check_api_loop.is_running():
        check_api_loop.start()
    await bot.tree.sync()
    print(f"✅ Logged in as {bot.user}")

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return
    intel_pattern = re.compile(
        r"You successfully gathered intelligence about (?P<nation>.+?)\. .*?has "
        r"\$(?P<money>[\d,\.]+), (?P<coal>[\d,\.]+) coal, (?P<oil>[\d,\.]+) oil, "
        r"(?P<uranium>[\d,\.]+) uranium, (?P<lead>[\d,\.]+) lead, (?P<iron>[\d,\.]+) iron, "
        r"(?P<bauxite>[\d,\.]+) bauxite, (?P<gasoline>[\d,\.]+) gasoline, "
        r"(?P<munitions>[\d,\.]+) munitions, (?P<steel>[\d,\.]+) steel, "
        r"(?P<aluminum>[\d,\.]+) aluminum and (?P<food>[\d,\.]+) food"
    )

    match = intel_pattern.search(message.content)
    if match:
        await message.add_reaction("✅")

        nation = match.group("nation")
        resources = {
            key: float(match.group(key).replace(",", ""))
            for key in match.groupdict() if key != "nation"
        }

        try:
            prices = get_prices()  # <-- this assumes your function accepts it

            resource_prices = {
                item["resource"]: float(item["average_price"])
                for item in prices["data"]["top_trade_info"]["resources"]
            }

            total_value = sum(
                val * resource_prices.get(key, 1) if key != "money" else val
                for key, val in resources.items()
            )
            estimated_loot = total_value * 0.14

        except Exception as e:
            print(f"Error getting prices or calculating loot: {e}")
            estimated_loot = 0.0

        try:
            sheet = get_sheet_s("Nation WC")
            all_records = sheet.get_all_records()
            nation_names = [row["Nation"] for row in all_records if "Nation" in row]

            update_row = [
                nation,
                f"{resources['money']:.2f}",
                f"{resources['coal']:.2f}",
                f"{resources['oil']:.2f}",
                f"{resources['uranium']:.2f}",
                f"{resources['lead']:.2f}",
                f"{resources['iron']:.2f}",
                f"{resources['bauxite']:.2f}",
                f"{resources['gasoline']:.2f}",
                f"{resources['munitions']:.2f}",
                f"{resources['steel']:.2f}",
                f"{resources['aluminum']:.2f}",
                f"{resources['food']:.2f}",
                datetime.now().strftime('%B %d, %Y at %I:%M %p')
            ]

            if nation in nation_names:
                row_index = nation_names.index(nation) + 2
                existing_row = sheet.row_values(row_index)
                existing_data = existing_row[1:13]
                new_data = update_row[1:13]

                if all(f"{float(e):.2f}" == f"{float(n):.2f}" for e, n in zip(existing_data, new_data)):
                    await message.channel.send(f"✅ Intel on **{nation}** already reported and unchanged.")
                    await bot.process_commands(message)
                    return

                sheet.update([update_row], f"A{row_index}:N{row_index}")
            else:
                sheet.append_row(update_row)

            embed = discord.Embed(
                title=f"🕵️ Intel Report: {nation}",
                description="Your spies report the following stockpile:",
                color=discord.Color.orange()
            )

            for k, v in resources.items():
                if k in resource_prices:
                    embed.add_field(name=k.capitalize(), value=f"{v:,.2f} @ {resource_prices[k]:,.2f}", inline=True)
                else:
                    embed.add_field(name=k.capitalize(), value=f"{v:,.2f}", inline=True)

            embed.add_field(name="💰 Estimated Loot (14%)", value=f"${estimated_loot:,.2f}", inline=False)

            await message.channel.send(embed=embed)

        except Exception as e:
            print(f"Error in intel handler: {e}")
            await message.channel.send("❌ Failed to process intel report.")
    if message.guild is None:
        default_reply = "Thanks for your message! We'll get back to you soon."

        last_bot_msg = None
        async for msg in message.channel.history(limit=20, before=message.created_at):
            if msg.author == bot.user:
                last_bot_msg = msg.content
                break

        if last_bot_msg != default_reply:
                settings_sheet = get_sheet_s("BotServerSettings")
                all_settings = settings_sheet.get_all_records()
                logs_channel_ids = None
                for row in all_settings:
                    if row["key"] == "LOGS":
                        logs_channel_ids = row["value"]
                        break

                if logs_channel_ids:
                    if ',' in logs_channel_ids:
                        channel_id_list = [int(id.strip()) for id in logs_channel_ids.split(',')]
                    elif '/' in logs_channel_ids:
                        channel_id_list = [int(id.strip()) for id in logs_channel_ids.split('/')]
                    else:
                        channel_id_list = [int(logs_channel_ids)]
                    
                    for logs_channel_id in channel_id_list:
                        log_channel = bot.get_channel(logs_channel_id)
                        if log_channel:
                            embed = discord.Embed(
                                title="📩 New DM Received",
                                description=(
                                    f"**From:** {message.author} (`{message.author.id}`)\n"
                                    f"**User message:**\n{message.content}\n\n"
                                    f"**Last bot message to user:**\n{last_bot_msg or 'None'}"
                                ),
                                color=discord.Color.blue()
                            )
                            await log_channel.send(embed=embed)
                        else:
                            print(f"Warning: Could not find log channel with ID {logs_channel_id}")

        await message.channel.send(default_reply)

    await bot.process_commands(message)

bot.run(bot_key)
