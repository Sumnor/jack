import discord
import asyncio
from datetime import datetime, timezone
from discord import app_commands
from typing import Optional, Dict, List, Set
import requests
from settings.bot_instance import bot, WHITEKEY, BOT_KEY
from databases.sql.databases import SafekeepDB, MaterialsDB
from settings.settings_multi import get_api_key_for_interaction
from settings.initializer_functions.resource_prices import parse_resources, RESOURCE_EMOJIS, format_number, ALL_RESOURCES
from databases.sql.data_puller import get_bank_data_sql_by_everything

CONFIG_OFFSHORE_AA_ID = 14207
CONFIG_DEPOSIT_NOTE = "Jack Safekeep"

config = None
safekeep_db = None
materials_db = None
pnw_api = None
stored_white_keys = {}

# Track processed transactions and warned nations
processed_transaction_ids: Set[int] = set()
warned_nations: Dict[int, str] = {}  # nation_id -> timestamp of last warning

try:
    from settings.initializer_functions.cached_users_initializer import cached_users
except ImportError:
    cached_users = {}

class PnWAPI:
    def __init__(self, api_key: str, bot_key: str):
        self.api_key = api_key
        self.bot_key = bot_key

    def get_whitekey_for_aa(self, aa_id: int) -> str:
        for key_info in stored_white_keys.values():
            if key_info.get("aa_id") == aa_id:
                return key_info["key"]

        raise ValueError(f"No WHITEKEY found for AA ID {aa_id}")
    
    def execute_query(self, query: str, account_api_key: str = None) -> Optional[Dict]:
        API_URL = f"https://api.politicsandwar.com/graphql?api_key={account_api_key}"
        if account_api_key is None:
            account_api_key = WHITEKEY

        headers = {
            "Content-Type": "application/json",
            "X-Bot-Key": BOT_KEY,
            "X-Api-Key": account_api_key
        }

        try:
            response = requests.post(API_URL, json={"query": query}, headers=headers, timeout=30)

            if response.status_code == 401:
                print(f"[ERROR] Unauthorized - X-Api-Key: {account_api_key[:4]}..., X-Bot-Key: {BOT_KEY[:4]}...")
                print("Response text:", response.text)
                return None

            if not response.ok:
                print(f"[ERROR] HTTP {response.status_code}: {response.text}")
                return None

            data = response.json()

            if "errors" in data:
                print(f"[ERROR] GraphQL errors: {data['errors']}")
                return None

            return data

        except requests.Timeout:
            print("[ERROR] Request timeout")
            return None
        except Exception as e:
            print(f"[ERROR] Exception during API call: {e}")
            import traceback
            traceback.print_exc()
            return None

        
    def get_alliance_info(self, alliance_id: int) -> Optional[Dict]:
        aa_id = None
        for key_info in stored_white_keys.values():
            if key_info.get("aa_id"):
                aa_id = key_info["aa_id"]
                break

        if aa_id is None:
            print(f"[ERROR] No WHITEKEY/AA found for alliance {alliance_id}")
            return None

        try:
            whitekey = self.get_whitekey_for_aa(aa_id)
        except ValueError as e:
            print(f"[ERROR] {e}")
            return None

        query = f"""
        {{
        alliances(id: {alliance_id}, first: 1) {{
            data {{
            id
            name
            money
            coal
            oil
            uranium
            iron
            bauxite
            lead
            gasoline
            munitions
            steel
            aluminum
            food
            }}
        }}
        }}
        """

        result = self.execute_query(query=query, account_api_key=whitekey)
        if result and result.get("data", {}).get("alliances", {}).get("data"):
            alliances = result["data"]["alliances"]["data"]
            return alliances[0] if alliances else None

        return None

    
    def get_nation_info(self, nation_id: int, interaction) -> Optional[Dict]:
        api_key = get_api_key_for_interaction(interaction)
        query = f"""
        {{
          nations(id: {nation_id}, first: 1) {{
            data {{
              id
              nation_name
              leader_name
              alliance_id
              alliance {{
                id
                name
              }}
            }}
          }}
        }}
        """
        
        result = self.execute_query(query, api_key)
        if result and result.get("data", {}).get("nations", {}).get("data"):
            nations = result["data"]["nations"]["data"]
            return nations[0] if nations else None
        return None
    
    def withdraw_to_nation(self, nation_id: int, resources: Dict[str, float], note: str = "Discord withdrawal") -> bool:
        valid_resources = [
            "money", "coal", "oil", "uranium", "iron", "bauxite",
            "lead", "gasoline", "munitions", "steel", "aluminum", "food"
        ]

        # Build resource string
        resource_params = [f"{res}: {resources.get(res, 0)}" for res in valid_resources]

        # Add note if provided
        if note:
            resource_params.append(f'note: "{note}"')

        resource_string = ",\n".join(resource_params)

        mutation = f"""
        mutation {{
        bankWithdraw(
            receiver: "{nation_id}",
            receiver_type: 1,
            {resource_string}
        ) {{
            id
            date
            note
        }}
        }}
        """

        result = self.execute_query(query=mutation, account_api_key=WHITEKEY)
        return result is not None


    def transfer_to_alliance(self, target_alliance_id: int, resources: Dict[str, float], note: str = "EBO Transfer") -> bool:
        """
        Transfer resources to an alliance.
        """
        resource_params = [f"{res}: {resources.get(res, 0)}" for res in ALL_RESOURCES]
        resource_string = ", ".join(resource_params)

        mutation = f"""
        mutation {{
        bankWithdraw(
            receiver: "{target_alliance_id}",
            receiver_type: 2,
            {resource_string},
            note: "{note}"
        ) {{
            id
            date
            note
        }}
        }}
        """

        result = self.execute_query(query=mutation, account_api_key=WHITEKEY)
        return result is not None

    def get_recent_bank_transactions(self, alliance_id: int, note: str, limit: int = 100) -> Optional[List[Dict]]:
        records = get_bank_data_sql_by_everything('', str(alliance_id), '/')
        return records if records else None

def initialize(bot_config: dict, supabase_url: str, supabase_key: str, 
               api_key: str, bot_key: str):
    global safekeep_db, materials_db, pnw_api, config
    config = bot_config
    safekeep_db = SafekeepDB(supabase_url, supabase_key)
    materials_db = MaterialsDB(supabase_url, supabase_key)
    pnw_api = PnWAPI(api_key, bot_key)
    
    load_white_keys_from_db()
    load_warned_nations_from_db()


def load_white_keys_from_db():
    global stored_white_keys
    try:
        guild_keys = safekeep_db._get("guild_white_keys?select=*")
        for record in guild_keys:
            guild_id = record.get('guild_id')
            white_key = record.get('white_key')
            aa_id = record.get('aa_id')
            if guild_id and white_key:
                stored_white_keys[int(guild_id)] = {
                    'key': white_key,
                    'aa_id': aa_id,
                    'stored_by': record.get('stored_by', 'System'),
                    'stored_at': record.get('stored_at', datetime.now(timezone.utc).isoformat())
                }
        print(f"[INFO] Loaded {len(stored_white_keys)} white keys from database")
    except Exception as e:
        print(f"[ERROR] Failed to load white keys: {e}")


def load_warned_nations_from_db():
    """Load nations that have already been warned about AA changes"""
    global warned_nations
    try:
        # You'll need to create this table: nation_id, warned_at, original_aa_id
        warned = safekeep_db._get("safekeep_warnings?select=*")
        for record in warned:
            nation_id = record.get('nation_id')
            warned_at = record.get('warned_at')
            if nation_id and warned_at:
                warned_nations[nation_id] = warned_at
        print(f"[INFO] Loaded {len(warned_nations)} warned nations from database")
    except Exception as e:
        print(f"[INFO] No warnings table found or empty: {e}")


def save_warning_to_db(nation_id: int, original_aa_id: int) -> bool:
    """Save that we warned a nation about AA change"""
    try:
        data = {
            'nation_id': nation_id,
            'warned_at': datetime.now(timezone.utc).isoformat(),
            'original_aa_id': original_aa_id
        }
        
        existing = safekeep_db._get(f"safekeep_warnings?nation_id=eq.{nation_id}")
        if existing:
            safekeep_db._patch(f"safekeep_warnings?nation_id=eq.{nation_id}", data)
        else:
            safekeep_db._post("safekeep_warnings", data)
        
        return True
    except Exception as e:
        print(f"[ERROR] Failed to save warning: {e}")
        return False


def save_white_key_to_db(guild_id: int, white_key: str, aa_id: int, stored_by: str) -> bool:
    try:
        existing = safekeep_db._get(f"guild_white_keys?guild_id=eq.{guild_id}")
        
        data = {
            'guild_id': guild_id,
            'white_key': white_key,
            'aa_id': aa_id,
            'stored_by': stored_by,
            'stored_at': datetime.now(timezone.utc).isoformat()
        }
        
        if existing:
            safekeep_db._patch(f"guild_white_keys?guild_id=eq.{guild_id}", data)
        else:
            safekeep_db._post("guild_white_keys", data)
        
        return True
    except Exception as e:
        print(f"[ERROR] Failed to save white key: {e}")
        return False


def get_aa_id_from_guild(guild_id: int) -> Optional[int]:
    guild_data = stored_white_keys.get(guild_id)
    return guild_data.get('aa_id') if guild_data else None


def get_white_key_from_guild(guild_id: int) -> Optional[str]:
    guild_data = stored_white_keys.get(guild_id)
    return guild_data.get('key') if guild_data else None


def get_safekeep_by_nation_id(nation_id: int) -> Optional[Dict]:
    try:
        result = safekeep_db._get(f"safekeep?nation_id=eq.{nation_id}")
        return result[0] if result else None
    except Exception as e:
        print(f"[ERROR] Failed to get safekeep by nation_id {nation_id}: {e}")
        return None


@bot.tree.command(name='withdraw', description='Withdraw resources from your safekeep account')
@app_commands.describe(
    resources='Resources to withdraw (e.g., money=1000000 oil=50000)',
    note='Optional note for the transaction'
)
async def slash_withdraw(interaction: discord.Interaction, resources: str, 
                        note: str = "Discord withdrawal"):
    await interaction.response.defer()
    
    guild_id = interaction.guild_id
    if not guild_id:
        embed = discord.Embed(
            title="❌ Error",
            description="This command must be used in a server.",
            color=0xff0000
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        return
    
    alliance_id = get_aa_id_from_guild(guild_id)
    if not alliance_id:
        embed = discord.Embed(
            title="❌ Not Configured",
            description="This server is not linked to an alliance. An admin must use `/ebo_setkey` first.",
            color=0xff0000
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        return
    
    await process_withdrawal(interaction, alliance_id, resources, note)

async def _upsert_safekeep_account_metadata(nation_id: int, interaction) -> Optional[Dict]:
    nation_info = await asyncio.to_thread(pnw_api.get_nation_info, nation_id, interaction)
    
    if not nation_info:
        print(f"[ERROR] Could not fetch info for nation {nation_id} during account UPSERT.")
        return None
        
    initial_resources = {res: 0 for res in ALL_RESOURCES}
    
    metadata_to_upsert = {
        'nation_id': nation_id,
        'discord_id': None,
        'alliance_id': nation_info.get('alliance_id'),
        'alliance_name': nation_info.get('alliance', {}).get('name'),
        'created_at': datetime.now(timezone.utc).isoformat(),
        **initial_resources
    }
    
    try:
        safekeep_db._upsert("safekeep", metadata_to_upsert, conflict_columns='nation_id')
        print(f"[INFO] UPSERT successful for safekeep account {nation_id}.")
        return get_safekeep_by_nation_id(nation_id) 
        
    except Exception as e:
        print(f"[ERROR] Failed to UPSERT safekeep account metadata for nation {nation_id}: {e}")
        return None

@bot.tree.command(name='create_safekeep_account', 
                 description='Link your Discord account to your nation for safekeep')
@app_commands.describe(
    nation_id='Your Politics and War nation ID'
)
async def slash_create_safekeep_account(interaction: discord.Interaction, nation_id: int):
    await interaction.response.defer(ephemeral=True)
    
    discord_id = str(interaction.user.id)
    
    existing_user = safekeep_db.get_safekeep_by_discord_id(discord_id)
    if existing_user:
        embed = discord.Embed(
            title="❌ Already Linked",
            description=f"Your Discord account is already linked to nation ID `{existing_user['nation_id']}`",
            color=0xff0000
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        return
    
    nation_account = get_safekeep_by_nation_id(nation_id)
    
    if not nation_account:
        await interaction.followup.send(
            embed=discord.Embed(
                title="⚠️ Creating Account",
                description=f"Safekeep account for Nation ID `{nation_id}` not found. Creating and linking now...",
                color=0xffaa00
            ), 
            ephemeral=True
        )
        
        nation_account = await _upsert_safekeep_account_metadata(nation_id, interaction)
        
        if not nation_account:
             embed = discord.Embed(
                title="❌ Creation Failed",
                description=f"Failed to create safekeep account for nation `{nation_id}`. Could not fetch nation info or database error occurred. Check logs.",
                color=0xff0000
            )
             await interaction.followup.send(embed=embed, ephemeral=True)
             return
    
    if nation_account.get('discord_id'):
        embed = discord.Embed(
            title="❌ Nation Already Linked",
            description=f"Nation ID `{nation_id}` is already linked to another Discord account.",
            color=0xff0000
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        return
    
    try:
        safekeep_db._patch(
            f"safekeep?nation_id=eq.{nation_id}",
            {'discord_id': discord_id}
        )
        
        embed = discord.Embed(
            title="✅ Account Linked Successfully",
            description=f"Your Discord has been linked to nation ID `{nation_id}`",
            color=0x00ff00
        )
        embed.add_field(name="Nation ID", value=f"`{nation_id}`", inline=True)
        
        alliance_display = nation_account.get('alliance_name') or f"AA {nation_account.get('alliance_id')}"
        embed.add_field(name="Alliance", value=f"`{alliance_display}`", inline=True)
        
        await interaction.followup.send(embed=embed, ephemeral=True)
        
    except Exception as e:
        print(f"[ERROR] Failed to link Discord ID {discord_id} to nation {nation_id}: {e}")
        embed = discord.Embed(
            title="❌ Link Failed",
            description="Failed to link your account. Please contact an admin.",
            color=0xff0000
        )
        await interaction.followup.send(embed=embed, ephemeral=True)


@bot.tree.command(name='balance', description='Check your safekeep balance')
async def slash_balance(interaction: discord.Interaction):
    await interaction.response.defer()
    await process_balance(interaction)


@bot.tree.command(name='aabalance', description='Check total safekeep balances for the alliance')
async def slash_aa_balance(interaction: discord.Interaction):
    await interaction.response.defer()
    
    guild_id = interaction.guild_id
    if not guild_id:
        embed = discord.Embed(
            title="❌ Error",
            description="This command must be used in a server.",
            color=0xff0000
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        return
    
    alliance_id = get_aa_id_from_guild(guild_id)
    if not alliance_id:
        embed = discord.Embed(
            title="❌ Not Configured",
            description="This server is not linked to an alliance.",
            color=0xff0000
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        return
    
    await process_aa_balance(interaction, alliance_id)


@bot.tree.command(name='ebo', description='Execute Emergency Bank Operation to transfer resources')
@app_commands.describe(
    resources='Resources to transfer (e.g., money=1000000 oil=50000)',
    note='Reason for the emergency transfer'
)
async def slash_ebo(interaction: discord.Interaction, resources: str, 
                   note: str = "Emergency Bank Operation"):
    await interaction.response.defer()
    
    guild_id = interaction.guild_id
    if not guild_id:
        embed = discord.Embed(
            title="❌ Error",
            description="This command must be used in a server.",
            color=0xff0000
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        return
    
    alliance_id = get_aa_id_from_guild(guild_id)
    if not alliance_id:
        embed = discord.Embed(
            title="❌ Not Configured",
            description="This server is not linked to an alliance.",
            color=0xff0000
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        return
    
    await process_ebo(interaction, alliance_id, resources, note)


@bot.tree.command(name='ebo_setkey', 
                 description='[ADMIN] Link an alliance to this server with API key')
@app_commands.describe(
    aa_id='Alliance ID to link',
    white_key='Whitelisted API key with bank access'
)
async def slash_ebo_setkey(interaction: discord.Interaction, aa_id: int, white_key: str):
    await interaction.response.defer(ephemeral=True)
    
    guild_id = interaction.guild_id
    if not guild_id:
        embed = discord.Embed(
            title="❌ Error",
            description="This command must be used in a server.",
            color=0xff0000
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        return
    
    test_result = await asyncio.to_thread(pnw_api.get_alliance_info, aa_id)
    if not test_result:
        embed = discord.Embed(
            title="❌ Invalid Alliance or API Key",
            description=f"Could not fetch data for Alliance ID `{aa_id}`. Check your API key and alliance ID.",
            color=0xff0000
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        return
    
    stored_white_keys[guild_id] = {
        'key': white_key,
        'aa_id': aa_id,
        'stored_by': str(interaction.user),
        'stored_at': datetime.now(timezone.utc).isoformat()
    }
    
    save_white_key_to_db(guild_id, white_key, aa_id, str(interaction.user))
    safekeep_db.get_or_create_aa(aa_id, is_registered=True)
    
    alliance_name = test_result.get('name', f'Alliance {aa_id}')
    
    embed = discord.Embed(
        title="✅ Server Linked Successfully",
        description=f"Server linked to **{alliance_name}**\nAccount creation is now enabled and triggered by deposits with note: **'{CONFIG_DEPOSIT_NOTE}'**",
        color=0x00ff00
    )
    embed.add_field(name="Alliance", value=f"`{alliance_name}` (ID: {aa_id})", inline=False)
    embed.add_field(name="API Key", value=f"`{white_key[:8]}...`", inline=True)
    embed.add_field(name="Offshore AA", value=f"`{CONFIG_OFFSHORE_AA_ID}`", inline=True)
    
    await interaction.edit_original_response(embed=embed)


async def process_withdrawal(interaction: discord.Interaction, alliance_id: int, 
                            resources_str: str, note: str):
    discord_id = str(interaction.user.id)
    
    user_data = safekeep_db.get_safekeep_by_discord_id(discord_id)
    if not user_data:
        embed = discord.Embed(
            title="❌ Not Registered",
            description=f"You don't have a safekeep account. Deposit resources with note **'{CONFIG_DEPOSIT_NOTE}'** to open one, then use `/create_safekeep_account`.",
            color=0xff0000
        )
        await interaction.followup.send(embed=embed)
        return
    
    if user_data['alliance_id'] != alliance_id:
        embed = discord.Embed(
            title="❌ Wrong Alliance",
            description=f"Your safekeep account is in AA {user_data['alliance_id']}, not AA {alliance_id}. If you recently changed alliances, please contact an admin.",
            color=0xff0000
        )
        await interaction.followup.send(embed=embed)
        return
    
    resources_requested, parse_errors = parse_resources(resources_str)
    
    if not resources_requested:
        embed = discord.Embed(
            title="⚠️ Invalid Format",
            description="Please specify resources like: `money=1000000 oil=50000`",
            color=0xffaa00
        )
        await interaction.followup.send(embed=embed)
        return
    
    insufficient = []
    for res, amt in resources_requested.items():
        available = user_data.get(res, 0) or 0
        if amt > available:
            insufficient.append(
                f"**{res.capitalize()}**: Need {format_number(amt)}, Have {format_number(available)}"
            )
    
    if insufficient:
        embed = discord.Embed(
            title="❌ Insufficient Balance",
            description="\n".join(insufficient),
            color=0xff0000
        )
        await interaction.followup.send(embed=embed)
        return
    
    white_key = get_white_key_from_guild(interaction.guild_id)
    if not white_key:
        embed = discord.Embed(
            title="❌ No API Key",
            description="No API key configured for this server.",
            color=0xff0000
        )
        await interaction.followup.send(embed=embed)
        return
    
    nation_id = user_data['nation_id']
    
    # FIX: Withdraw from offshore AA, not the main alliance
    offshore_api = PnWAPI(white_key, white_key)
    result = await asyncio.to_thread(
        offshore_api.withdraw_to_nation,
        nation_id,
        resources_requested,
        note
    )
    
    if result:
        # FIX: Use nation_id instead of discord_id for balance update
        safekeep_db.update_safekeep_balance(nation_id=nation_id, resources=resources_requested, subtract=True)
        
        resource_list = "\n".join([
            f"{RESOURCE_EMOJIS.get(res, '📦')} **{res.capitalize()}**: {format_number(amt)}"
            for res, amt in resources_requested.items()
        ])
        
        embed = discord.Embed(
            title="✅ Withdrawal Successful",
            description=f"Resources withdrawn to nation ID `{nation_id}`:\n\n{resource_list}",
            color=0x00ff00
        )
        await interaction.followup.send(embed=embed)
    else:
        embed = discord.Embed(
            title="❌ Withdrawal Failed",
            description="The withdrawal could not be completed. Check API access and try again.",
            color=0xff0000
        )
        await interaction.followup.send(embed=embed)


async def process_balance(interaction: discord.Interaction):
    discord_id = str(interaction.user.id)
    user_data = safekeep_db.get_safekeep_by_discord_id(discord_id)
    
    if not user_data:
        embed = discord.Embed(
            title="❌ Not Registered",
            description=f"You don't have a safekeep account. Deposit resources with note **'{CONFIG_DEPOSIT_NOTE}'** to open one, then use `/create_safekeep_account` to get started.",
            color=0xff0000
        )
        await interaction.followup.send(embed=embed)
        return
    
    embed = discord.Embed(
        title="💰 Your Safekeep Balance",
        color=0x3498db
    )
    
    alliance_display = user_data.get('alliance_name') or f"AA {user_data.get('alliance_id')}"
    embed.add_field(name="Alliance", value=f"`{alliance_display}`", inline=True)
    embed.add_field(name="Nation ID", value=f"`{user_data.get('nation_id')}`", inline=True)
    embed.add_field(name="\u200b", value="\u200b", inline=True)
    
    for res in ALL_RESOURCES:
        amount = user_data.get(res, 0) or 0
        emoji = RESOURCE_EMOJIS.get(res, "📦")
        embed.add_field(
            name=f"{emoji} {res.capitalize()}",
            value=format_number(amount),
            inline=True
        )
    
    await interaction.followup.send(embed=embed)


async def process_aa_balance(interaction: discord.Interaction, alliance_id: int):
    aa_data = safekeep_db.calculate_aa_totals(alliance_id)
    
    if aa_data['member_count'] == 0:
        embed = discord.Embed(
            title="❌ No Members",
            description=f"No safekeep accounts found for Alliance ID {alliance_id}",
            color=0xff0000
        )
        await interaction.followup.send(embed=embed)
        return
    
    alliance_info = await asyncio.to_thread(pnw_api.get_alliance_info, alliance_id)
    alliance_name = alliance_info.get('name') if alliance_info else f"Alliance {alliance_id}"
    
    embed = discord.Embed(
        title=f"🏛️ Alliance Safekeep Totals",
        description=f"**{alliance_name}** (ID: {alliance_id})\n{aa_data['member_count']} members with safekeep accounts",
        color=0x3498db
    )
    
    for res in ALL_RESOURCES:
        amount = aa_data['totals'].get(res, 0)
        emoji = RESOURCE_EMOJIS.get(res, "📦")
        embed.add_field(
            name=f"{emoji} {res.capitalize()}",
            value=format_number(amount),
            inline=True
        )
    
    await interaction.followup.send(embed=embed)


async def process_ebo(interaction: discord.Interaction, alliance_id: int, 
                     resources_str: str, note: str):
    resources_requested, parse_errors = parse_resources(resources_str)
    
    if not resources_requested:
        embed = discord.Embed(
            title="⚠️ Invalid Format",
            description="Please specify resources like: `money=1000000 oil=50000`",
            color=0xffaa00
        )
        await interaction.followup.send(embed=embed)
        return
    
    white_key = get_white_key_from_guild(interaction.guild_id)
    if not white_key:
        embed = discord.Embed(
            title="❌ No API Key",
            description="No API key configured for this server.",
            color=0xff0000
        )
        await interaction.followup.send(embed=embed)
        return
    
    offshore_alliance_id = CONFIG_OFFSHORE_AA_ID
    
    result = await asyncio.to_thread(
        pnw_api.transfer_to_alliance,
        offshore_alliance_id,
        resources_requested,
        note,
        white_key
    )
    
    if result:
        resource_list = "\n".join([
            f"{RESOURCE_EMOJIS.get(res, '📦')} **{res.capitalize()}**: {format_number(amt)}"
            for res, amt in resources_requested.items()
        ])
        
        embed = discord.Embed(
            title="✅ EBO Complete",
            description=f"Resources transferred to offshore alliance:\n\n{resource_list}",
            color=0x00ff00
        )
        embed.add_field(name="Note", value=note, inline=False)
    else:
        embed = discord.Embed(
            title="❌ EBO Failed",
            description="The emergency transfer could not be completed. Check API access and try again.",
            color=0xff0000
        )
    
    await interaction.followup.send(embed=embed)


async def process_new_deposits():
    global processed_transaction_ids
    
    for guild_id, data in stored_white_keys.items():
        alliance_id = data['aa_id']
        white_key = data['key']
        offshore_id = CONFIG_OFFSHORE_AA_ID
        
        transactions = await asyncio.to_thread(
            pnw_api.get_recent_bank_transactions,
            alliance_id,
            CONFIG_DEPOSIT_NOTE
        )
        
        if not transactions:
            continue