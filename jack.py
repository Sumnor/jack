from datetime import datetime, timedelta
import asyncio
import discord
import requests
import datetime
from datetime import timedelta
import pandas as pd
from discord.ext import tasks
import os
import re
from settings.bot_instance import bot_key, bot, API_KEY, BOT_KEY, SUPABASE_URL, SUPABASE_KEY
from econ.grants.grant_views.InfraGrantView import BlueGuy
from econ.grants.grant_views.GrantView import GrantView
from settings.bot_instance import bot_key, bot, API_KEY, BOT_KEY, SUPABASE_URL, SUPABASE_KEY
from econ.grants.grant_views.InfraGrantView import BlueGuy
from econ.grants.grant_views.GrantView import GrantView
from databases.graphql_requests import get_general_data
from settings.initializer_functions.cached_users_initializer import get_registration_sheet
from settings.initializer_functions.resource_prices import get_prices
from settings.initializer_functions.supabase_initializer import supabase
from databases.sql.databases import get_all_alerts, fetch_latest_price, MATERIALS, SUPABASE_KEY, SUPABASE_URL
from econ.prediction_market.regression_models import fetch_material_data, train_model_for_resource
from offshore.processes.process_new_deposits import process_new_deposits
from ia.audit_time_period_controler import quota_check_loop

UNIT_PRICES = {
    "soldiers": 5,
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

async def send_alert(user, message):
    try:
        await user.send(message)
    except:
        pass

@tasks.loop(hours=2)
async def price_snapshots():
    print("Running Price Snapshots...")
    prices = {}

    try:
        query = """
        query {
          tradeprices {
            data {
              date
              food
              coal
              oil
              uranium
              iron
              bauxite
              lead
              steel
              aluminum
              munitions
              gasoline
            }
          }
        }
        """
        res = requests.post(
            f"https://api.politicsandwar.com/graphql?api_key={os.getenv('API_KEY')}",
            json={"query": query},
            headers={"Content-Type": "application/json"}
        )
        res.raise_for_status()
        json_data = res.json()

        if "data" not in json_data or "tradeprices" not in json_data["data"]:
            print("⚠️ tradeprices not in GraphQL response")
            return

        tradeprices = json_data["data"]["tradeprices"]
        resources_data = tradeprices.get("data", tradeprices)
        if not resources_data:
            print("⚠️ No trade price data returned")
            return

        latest = resources_data[-1]
        prices = {r: float(latest[r]) for r in latest if r != "date"}
        print("✅ Latest Prices:", prices)

    except Exception as e:
        print(f"⚠️ Failed to fetch prices: {e}")
        return


    row = {"timestamp": datetime.datetime.now().isoformat()}
    for mat in MATERIALS:
        row[mat] = prices.get(mat)

    try:
        url = f"{SUPABASE_URL}/materials"
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal"
        }
        response = requests.post(url, json=row, headers=headers)
        response.raise_for_status()
        print(f"✅ Snapshot saved at {row['timestamp']}")
    except Exception as e:
        print(f"⚠️ Failed to save snapshot: {e}")
        return


    try:
        df = fetch_material_data()
        for mat in MATERIALS:
            intercept, coef = train_model_for_resource(df, mat)
            if intercept is not None:
                print(f"📈 Updated model for {mat}: intercept={intercept:.2f}, coef={coef}")
    except Exception as e:
        print(f"⚠️ Failed to train models: {e}")

@price_snapshots.before_loop
async def before_price_snapshots():
    await bot.wait_until_ready()

@tasks.loop(minutes=15)
async def deposit_check_loop():
    await process_new_deposits()

last_alert_time = {}
max_triggered_price = {}

ALERT_COOLDOWN = timedelta(hours=2)

@tasks.loop(hours=2)
async def check_alerts():
    print("🔍 Checking alerts...")
    alerts = get_all_alerts()
    now = datetime.datetime.utcnow()

    mat_prices = {}
    for mat in MATERIALS:
        price = fetch_latest_price(mat)
        if price is not None:
            mat_prices[mat] = price
    print(f"✅ Cached material prices: {mat_prices}")

    for alert in alerts:
        user_id = alert["discord_id"]

        if user_id not in last_alert_time:
            last_alert_time[user_id] = {}
        if user_id not in max_triggered_price:
            max_triggered_price[user_id] = {}

        try:
            user = await bot.fetch_user(user_id)
        except Exception as e:
            print(f"⚠️ Failed to fetch user {user_id}: {e}")
            continue

        for mat in MATERIALS:
            alert_value = alert.get(mat, 0)
            if alert_value == 0:
                continue

            latest_price = mat_prices.get(mat)
            if latest_price is None:
                continue

            if mat not in last_alert_time[user_id]:
                last_alert_time[user_id][mat] = {"high": datetime.datetime.min, "low": datetime.datetime.min}
            if mat not in max_triggered_price[user_id]:
                max_triggered_price[user_id][mat] = {"high": latest_price, "low": latest_price}

            if alert_value in (1, 3):
                ref_high = max_triggered_price[user_id][mat]["high"]
                threshold = ref_high * 1.2
                if latest_price >= threshold and now - last_alert_time[user_id][mat]["high"] >= ALERT_COOLDOWN:
                    try:
                        embed = discord.Embed(
                            title=f"{mat.capitalize()} prices rising",
                            colour=discord.Colour.dark_gold(),
                            description=(
                                f"📈 {mat.capitalize()} crossed HIGH threshold {threshold:.2f}!\n"
                                f"Sell now: [Market](https://politicsandwar.com/index.php?id=26&display=world&resource1={mat}&buysell=buy)"
                            ),
                        )
                        await user.send(embed=embed)
                    except Exception as e:
                        print(f"⚠️ Failed to DM {user_id} for {mat} high alert: {e}")
                    last_alert_time[user_id][mat]["high"] = now
                    max_triggered_price[user_id][mat]["high"] = latest_price

            if alert_value in (2, 3):
                ref_low = max_triggered_price[user_id][mat]["low"]
                threshold = ref_low * 0.8
                if latest_price <= threshold and now - last_alert_time[user_id][mat]["low"] >= ALERT_COOLDOWN:
                    try:
                        embed = discord.Embed(
                            title=f"{mat.capitalize()} prices dropping",
                            colour=discord.Colour.dark_gold(),
                            description=(
                                f"📉 {mat.capitalize()} crossed LOW threshold {threshold:.2f}!\n"
                                f"Buy now: [Market](https://politicsandwar.com/index.php?id=26&display=world&resource1={mat}&buysell=sell)"
                            ),
                        )
                        await user.send(embed=embed)
                    except Exception as e:
                        print(f"⚠️ Failed to DM {user_id} for {mat} low alert: {e}")
                    last_alert_time[user_id][mat]["low"] = now
                    max_triggered_price[user_id][mat]["low"] = latest_price

@check_alerts.before_loop
async def before_check_alerts():
    await bot.wait_until_ready()

@tasks.loop(hours=168)
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
            await asyncio.sleep(1800)

    except Exception as e:
        print(f"[Updater] Unhandled error during update: {e}")

@weekly_member_updater.before_loop
async def before_updater():
    await bot.wait_until_ready()
    print("[Updater] Bot is ready. Waiting for weekly loop to begin.")

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
            prices = get_prices()
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
            
            timestamp = datetime.datetime.now().strftime('%B %d, %Y at %I:%M %p')
            
            data = {
                'nation_name': nation.lower(),
                'timestamp': timestamp,
                'money': resources['money'],
                'coal': resources['coal'],
                'oil': resources['oil'],
                'uranium': resources['uranium'],
                'lead': resources['lead'],
                'iron': resources['iron'],
                'bauxite': resources['bauxite'],
                'gasoline': resources['gasoline'],
                'munitions': resources['munitions'],
                'steel': resources['steel'],
                'aluminum': resources['aluminum'],
                'food': resources['food']
            }

            
            existing = supabase.select('nation_reports', filters={'nation_name': nation.lower()})
            
            if existing:
                
                latest_record = max(existing, key=lambda x: x.get('timestamp', ''))
                data_changed = any(
                    float(latest_record.get(key, 0)) != val 
                    for key, val in resources.items()
                )
                
                if not data_changed:
                    await message.channel.send(f"✅ Intel on **{nation}** already reported and unchanged.")
                    await bot.process_commands(message)
                    return
                
                
                record_id = latest_record.get('id')
                supabase.update('nation_reports', data, {'id': record_id})
            else:
                
                supabase.insert('nation_reports', data)

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
            await message.channel.send("⚪ Failed to process intel report.")

    
    if message.guild is None:
        default_reply = "Thanks for your message! We'll get back to you soon."

        last_bot_msg = None
        async for msg in message.channel.history(limit=20, before=message.created_at):
            if msg.author == bot.user:
                last_bot_msg = msg.content
                break

        if last_bot_msg != default_reply:
            
            try:
                logs_setting = supabase.select('server_settings', filters={'key': 'LOGS'})
                if logs_setting:
                    logs_channel_ids = logs_setting[0].get('value', '')
                    
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
            except Exception as e:
                print(f"Error handling DM logging: {e}")

        await message.channel.send(default_reply)

    await bot.process_commands(message)

@bot.event
async def on_ready():
    from settings.initializer_functions.cached_users_initializer import load_registration_data, load_sheet_data
    bot.add_view(GrantView())  
    load_sheet_data()
    load_registration_data()
    bot.add_view(BlueGuy())
    import ma.calculate_military_cost
    import databases.graphql_requests
    import econ.grants.grant_commands.request_projects
    import econ.grants.grant_commands.request_cities
    import econ.grants.grant_commands.request_infra_upgrade_cost
    import econ.grants.grant_commands.request_miscellaneous
    import econ.grants.grant_commands.request_warchest
    import econ.grants.grant_commands.raws_requests
    import econ.prediction_market.market_tools
    import ma.spying.see_report
    import ma.spying.list_reports
    import ma.war_losses
    import ma.filtering.filter_nations
    import ma.militarization.alliance_militarization
    import ma.militarization.nation_militarization
    import settings.settings_multi
    import base_commands.ConvenienceCommands.help
    import base_commands.ConvenienceCommands.send_dm
    import base_commands.ConvenienceCommands.send_messages
    import base_commands.MaintCommands.bot_info
    import base_commands.MaintCommands.run_check
    import base_commands.MaintCommands.warn_maint
    import base_commands.RegisterCommands.register
    import base_commands.RegisterCommands.register_aa
    import databases.sql.databases
    import databases.sql.data_puller
    import information.info
    import offshore.OffshoreCommands.aabalance
    import offshore.OffshoreCommands.balance
    import offshore.OffshoreCommands.create_safekeep_account
    import offshore.OffshoreCommands.ebo
    import offshore.OffshoreCommands.ebo_setkey
    import offshore.OffshoreCommands.withdraw
    import cogs.tos
    import ia.audit_commands.assing_quota
    import ia.audit_commands.audit_stats
    import ia.audit_commands.audits
    import ia.audit_commands.audits_setup
    import ia.audit_commands.assign_all
    import ia.audit_commands.set_ia_roles
    import ia.audit_commands.set_quota_due
    import ia.audit_commands.excuse_auditor
    import ia.audit_commands.export_auditor_quotas
    import ia.audit_commands.quota_display
    import ia.audit_commands.unexcuse_auditor
    import ia.audit_commands.audit_targets
    import ia.audit_commands.add_auditor
    import ia.audit_commands.remove_auditor
    import econ.grants.res_details
    import econ.grants.auto_grant
    print("Starting tasks...")
    from offshore.offshore_utils.initialize import initialize
    initialize(
        bot_config={'offshore_alliance_id': 14207},
        supabase_url=SUPABASE_URL,
        supabase_key=SUPABASE_KEY,
        api_key=API_KEY,
        bot_key=BOT_KEY,
    )
    if not deposit_check_loop.is_running():
        deposit_check_loop.start() 
    if not quota_check_loop.is_running():
        quota_check_loop.start()
    if not check_alerts.is_running():
        check_alerts.start()
    if not weekly_member_updater.is_running():
        weekly_member_updater.start()
    if not price_snapshots.is_running():
        price_snapshots.start()
        
    await bot.tree.sync()
    print(f"✅ Logged in as {bot.user}")

bot.run(bot_key)
