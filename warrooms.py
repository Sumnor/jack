import subprocess
import json
import discord
from discord.ext import commands
import asyncio
import os
import threading
import aiohttp
from typing import Dict, List, Optional, Set
from datetime import datetime, timedelta
from bot_instance import bot, wrap_as_prefix_command, SUPABASE_URL, SUPABASE_KEY
from utils import cached_users
from settings_multi import get_warroom_id, get_api_key_for_guild, get_aa_name_guild, get_toggle_value_gd, set_server_setting, get_settings_value
import requests
from discord_views import MultiWarParticipantView
from data_puller import supabase

RUN = True
CHECK_INTERVAL = 1800  # 30 minutes in seconds

# ==================== SUPABASE DATA FUNCTIONS ====================

def get_tracked_war(war_id: str):
    """Get tracked war from Supabase"""
    try:
        records = supabase.select('tracked_wars', filters={'war_id': str(war_id)})
        if records and len(records) > 0:
            return records[0]
        return None
    except Exception as e:
        print(f"Error fetching tracked war {war_id}: {e}")
        return None

def insert_tracked_war(war_id: str, guild_id: int, channel_id: int, enemy_id: str, start_date: str, participants: str):
    """Insert new tracked war into Supabase"""
    try:
        data = {
            'war_id': str(war_id),
            'guild_id': str(guild_id),
            'channel_id': str(channel_id),
            'enemy_id': str(enemy_id),
            'start_date': start_date,
            'last_checked': datetime.utcnow().isoformat(),
            'participants': participants,
            'is_completed': False
        }
        return supabase.insert('tracked_wars', data)
    except Exception as e:
        print(f"Error inserting tracked war {war_id}: {e}")
        return None

def update_tracked_war_last_checked(war_id: str):
    """Update last checked timestamp for a war"""
    try:
        data = {'last_checked': datetime.utcnow().isoformat()}
        return supabase.update('tracked_wars', data, filters={'war_id': str(war_id)})
    except Exception as e:
        print(f"Error updating tracked war {war_id}: {e}")
        return None

def mark_war_completed(war_id: str):
    """Mark a war as completed"""
    try:
        data = {
            'is_completed': True,
            'completed_date': datetime.utcnow().isoformat()
        }
        return supabase.update('tracked_wars', data, filters={'war_id': str(war_id)})
    except Exception as e:
        print(f"Error marking war {war_id} as completed: {e}")
        return None

def get_active_tracked_wars_for_guild(guild_id: int):
    """Get all active tracked wars for a guild"""
    try:
        records = supabase.select('tracked_wars', filters={'guild_id': str(guild_id), 'is_completed': 'false'})
        return records if records else []
    except Exception as e:
        print(f"Error fetching tracked wars for guild {guild_id}: {e}")
        return []

def delete_tracked_war(war_id: str):
    """Delete a tracked war from database"""
    try:
        return supabase.delete('tracked_wars', filters={'war_id': str(war_id)})
    except Exception as e:
        print(f"Error deleting tracked war {war_id}: {e}")
        return None

# ==================== EXISTING FUNCTIONS ====================

async def get_attack_data(war_id: str, api_key: str) -> dict:
    url = f"https://api.politicsandwar.com/graphql?api_key={api_key}"
    query = """
    query($id: [Int]) {
        wars(id: $id) {
            data {
                id
                attacks {
                    city_id
                    type
                    success
                    resistance_lost
                    att_soldiers_used
                    att_soldiers_lost
                    def_soldiers_used
                    def_soldiers_lost
                    att_tanks_used
                    att_tanks_lost
                    def_tanks_used
                    def_tanks_lost
                    att_aircraft_used
                    att_aircraft_lost
                    def_aircraft_used
                    def_aircraft_lost
                    att_ships_used
                    att_ships_lost
                    def_ships_used
                    def_ships_lost
                    att_missiles_lost
                    def_missiles_lost
                    att_nukes_lost
                    def_nukes_lost
                    improvements_destroyed
                    infra_destroyed_percentage
                    money_looted
                    coal_looted
                    oil_looted
                    uranium_looted
                    iron_looted
                    bauxite_looted
                    lead_looted
                    gasoline_looted
                    munitions_looted
                    steel_looted
                    aluminum_looted
                    food_looted
                }
            }
        }
    }
    """

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json={"query": query, "variables": {"id": int(war_id)}}) as resp:
                if resp.status != 200:
                    print(f"API request failed with status {resp.status}")
                    return {}

                data = await resp.json()
                wars_dict = data.get("data", {}).get("wars", {})
                wars_list = wars_dict.get("data", [])
                if not wars_list:
                    return {}

                war = wars_list[0]
                attacks = war.get("attacks", [])
                if not attacks:
                    return {}

                return attacks[-1]

    except Exception as e:
        print(f"Error fetching latest attack for war {war_id}: {e}")
        return {}

async def get_nation_info(nation_id: str, api_key: str) -> Dict:
    try:
        url = f"https://api.politicsandwar.com/graphql?api_key={api_key}"
        query = """
        query($id: ID!) {
            nation(id: $id) {
                id
                nation_name
                leader_name
                alliance {
                    id
                    name
                }
                soldiers
                tanks
                aircraft
                ships
                military_power
                resistance
            }
        }
        """
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json={
                'query': query,
                'variables': {'id': nation_id}
            }) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get('data', {}).get('nation', {})
                else:
                    print(f"API request failed with status {response.status}")
                    return {}
    except Exception as e:
        print(f"Error fetching nation info for {nation_id}: {e}")
        return {}

async def get_alliance_members(guild_id: int) -> List[Dict]:
    """Get alliance members dynamically from cached_users"""
    try:    
        aa_name = get_aa_name_guild(guild_id)
        alliance_members = []
        for discord_id, data in cached_users.items():
            if data.get("AA", "").strip().lower() == aa_name.strip().lower():
                nation_id = data.get("NationID")
                if nation_id:
                    alliance_members.append({
                        "NationID": str(nation_id),
                        "DiscordID": str(discord_id)
                    })
        
        if not alliance_members:
            print(f"No members found in AA: {aa_name}")
            return []
        
        print(f"Found {len(alliance_members)} alliance members for guild {guild_id}")
        return alliance_members
    except Exception as e:
        print(f"Error getting alliance members for guild {guild_id}: {e}")
        import traceback
        traceback.print_exc()
        return []

def get_participants_from_description(channel: discord.TextChannel) -> Set[str]:
    """Extract participant nation IDs from channel description"""
    try:
        if not channel.topic:
            return set()
        
        if "Participants:" in channel.topic:
            parts = channel.topic.split("Participants:")
            if len(parts) > 1:
                participant_str = parts[1].strip().split("|")[0].strip()
                return set(participant_str.split(","))
        
        return set()
    except Exception as e:
        print(f"Error parsing participants from description: {e}")
        return set()

async def update_channel_description(channel: discord.TextChannel, participant_ids: Set[str]):
    """Update channel description with current participants"""
    try:
        participant_str = ",".join(sorted(participant_ids))
        new_topic = f"Participants: {participant_str}"
        
        if len(new_topic) > 1024:
            new_topic = new_topic[:1020] + "..."
        
        await channel.edit(topic=new_topic)
        print(f"Updated channel {channel.name} description with participants: {participant_str}")
    except Exception as e:
        print(f"Error updating channel description: {e}")

async def check_war_completion(war_id: str, start_date: str, api_key: str) -> bool:
    """Check if a war should be marked as completed (120 hours since start)"""
    try:
        start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        current_dt = datetime.utcnow().replace(tzinfo=start_dt.tzinfo)
        
        hours_elapsed = (current_dt - start_dt).total_seconds() / 3600
        
        if hours_elapsed >= 120:
            print(f"War {war_id} has exceeded 120 hours ({hours_elapsed:.1f} hours)")
            return True
        
        return False
        
    except Exception as e:
        print(f"Error checking war completion for {war_id}: {e}")
        return False

async def get_war_data_from_api(war_id: str, api_key: str) -> Optional[Dict]:
    """Fetch current war data from API"""
    try:
        url = f"https://api.politicsandwar.com/graphql?api_key={api_key}"
        query = """
        query($id: [Int]) {
            wars(id: $id) {
                data {
                    id
                    att_id
                    def_id
                    att_points
                    def_points
                    att_resistance
                    def_resistance
                    ground_control
                    air_superiority
                    naval_blockade
                    turns_left
                    war_type
                    att_soldiers_lost
                    def_soldiers_lost
                    att_tanks_lost
                    def_tanks_lost
                    att_aircraft_lost
                    def_aircraft_lost
                    att_ships_lost
                    def_ships_lost
                    end_date
                }
            }
        }
        """
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json={
                "query": query,
                "variables": {"id": int(war_id)}
            }) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    wars = data.get("data", {}).get("wars", {}).get("data", [])
                    if wars:
                        return wars[0]
        return None
    except Exception as e:
        print(f"Error fetching war data for {war_id}: {e}")
        return None

async def check_and_update_wars():
    """Periodic task to check and update all tracked wars"""
    while RUN:
        try:
            print(f"[{datetime.utcnow().isoformat()}] Starting periodic war check...")
            
            for guild in bot.guilds:
                try:
                    if not get_toggle_value_gd("WAR_ROOMS_TOGGLE", guild.id):
                        continue
                    
                    api_key = get_api_key_for_guild(guild.id)
                    if not api_key:
                        continue
                    
                    tracked_wars = get_active_tracked_wars_for_guild(guild.id)
                    print(f"Guild {guild.id}: Checking {len(tracked_wars)} active wars")
                    
                    for tracked_war in tracked_wars:
                        try:
                            war_id = tracked_war['war_id']
                            channel_id = tracked_war['channel_id']
                            start_date = tracked_war['start_date']
                            
                            # Check if war has reached 120 hours
                            is_completed = await check_war_completion(war_id, start_date, api_key)
                            
                            if is_completed:
                                print(f"War {war_id} completed (120 hours elapsed)")
                                mark_war_completed(war_id)
                                
                                try:
                                    channel = await bot.fetch_channel(int(channel_id))
                                    if channel:
                                        await channel.delete(reason=f"War {war_id} completed (120 hours)")
                                except:
                                    pass
                                
                                continue
                            
                            # Get current war data
                            war_data = await get_war_data_from_api(war_id, api_key)
                            
                            if not war_data:
                                print(f"Could not fetch data for war {war_id}")
                                continue
                            
                            # Check if war has ended
                            if war_data.get('end_date'):
                                print(f"War {war_id} has ended")
                                mark_war_completed(war_id)
                                
                                try:
                                    channel = await bot.fetch_channel(int(channel_id))
                                    if channel:
                                        await channel.delete(reason=f"War {war_id} ended")
                                except:
                                    pass
                                
                                continue
                            
                            # Update the war room
                            try:
                                channel = await bot.fetch_channel(int(channel_id))
                                if channel:
                                    alliance_members = await get_alliance_members(guild.id)
                                    await send_detailed_war_update(
                                        channel, war_data, alliance_members, False, api_key
                                    )
                                    update_tracked_war_last_checked(war_id)
                            except Exception as e:
                                print(f"Error updating war room for {war_id}: {e}")
                            
                        except Exception as e:
                            print(f"Error processing tracked war {tracked_war.get('war_id', 'Unknown')}: {e}")
                            import traceback
                            traceback.print_exc()
                    
                except Exception as e:
                    print(f"Error processing guild {guild.id}: {e}")
                    import traceback
                    traceback.print_exc()
            
            print(f"[{datetime.utcnow().isoformat()}] Periodic check completed. Sleeping for {CHECK_INTERVAL} seconds...")
            
        except Exception as e:
            print(f"Error in periodic check: {e}")
            import traceback
            traceback.print_exc()
        
        await asyncio.sleep(CHECK_INTERVAL)

# ==================== WAR ROOM HELPER FUNCTIONS ====================

def get_war_color(war_type: str) -> int:
    war_type = war_type.lower()
    if "nuke" in war_type:
        return discord.Color.yellow()
    elif "naval" in war_type:
        return discord.Color.dark_blue()
    elif "ground" in war_type:
        return discord.Color.green()
    elif "missile" in war_type:
        return discord.Color.darker_grey()
    elif "fortify" in war_type:
        return discord.Color.brand_red()
    elif "peace" in war_type:
        return discord.Color.lighter_grey()
    elif "air" in war_type:
        return discord.Color.blue()
    return discord.Color.orange()

async def get_action_data(war_id: str, api_key: str) -> tuple[str, str]:
    attack_data = await get_attack_data(war_id, api_key)
    action_type = str(attack_data.get("type")).lower()
    success_code = attack_data.get("success", "")
    
    if "ground" in action_type:
        action_name = "⚔️ Ground Attack"
    elif "air" in action_type:
        action_name = "✈️ Airstrike"
    elif "naval" in action_type:
        action_name = "🚢 Naval Attack"
    elif "missile" in action_type:
        action_name = "🚀 Missile Strike"
    elif "nuke" in action_type or "nuclear" in action_type:
        action_name = "☢️ Nuclear Strike"
    elif "fortify" in action_type or "defend" in action_type:
        action_name = "🛡️ Fortify"
    elif "peace" in action_type:
        action_name = "🕊️ Peace Offer"
    else:
        action_name = "❓ Unknown Action"

    if success_code == 3: 
        success_text = "🎉 **IMMENSE TRIUMPH**"
    elif success_code == 2:  
        success_text = "⚖️ **MODERATE SUCCESS**"
    elif success_code == 1: 
        success_text = "⚠️ **PYRRHIC VICTORY**"
    elif success_code == 0: 
        success_text = "💥 **UTTER FAILURE**"
    else: 
        success_text = "❓ Unknown Outcome"
        
    return action_name, success_text

def format_war_score(our_points: float, enemy_points: float, bar_length: int = 10) -> str:
    total = our_points + enemy_points
    if total == 0:
        return "Score: 0 - 0\n[----------]"
        
    our_ratio = our_points / total
    our_blocks = round(our_ratio * bar_length)
    enemy_blocks = bar_length - our_blocks
    
    bar = '🟢' * our_blocks + '⚫' * enemy_blocks
    
    return f"Score: **{our_points}** - **{enemy_points}**\n[{bar}]"

def format_resistance_bar(our_resistance: float, enemy_resistance: float, bar_length: int = 10) -> str:
    total = our_resistance + enemy_resistance
    if total == 0:
        return "Resistance: 0% - 0%\n[----------]"
        
    our_ratio = our_resistance / total
    our_blocks = round(our_ratio * bar_length)
    enemy_blocks = bar_length - our_blocks
    
    bar = '🟢' * our_blocks + '🔴' * enemy_blocks
    
    return f"Resistance: **{our_resistance:.1f}%** - **{enemy_resistance:.1f}%**\n[{bar}]"
    
def get_control_status(controller_id: int, att_id: int, def_id: int, our_side: str) -> str:
    if controller_id == att_id and our_side in ["attacker", "both"]: 
        return "🟢 **WE CONTROL**"
    elif controller_id == def_id and our_side in ["defender", "both"]: 
        return "🟢 **WE CONTROL**"
    elif controller_id == att_id or controller_id == def_id: 
        return "🔴 **ENEMY CONTROLS**"
    else: 
        return "🟡 **CONTESTED**"

def get_blockade_status(naval_blockade_id: int, att_id: int, def_id: int, our_side: str) -> str:
    if naval_blockade_id == 0:
        return "🟡 **No Blockade**"
    elif naval_blockade_id == att_id and our_side in ["attacker", "both"]:
        return "🟢 **WE ARE BLOCKADING**"
    elif naval_blockade_id == def_id and our_side in ["defender", "both"]:
        return "🟢 **WE ARE BLOCKADING**"
    elif naval_blockade_id == att_id or naval_blockade_id == def_id:
        return "🔴 **WE ARE BLOCKADED**"
    else:
        return "🟡 **Unknown Blockade Status**"

async def send_detailed_war_update(war_channel, war, alliance_members, is_new_turn, api_key):
    try:
        war_id = war.get("id")
        attacker_id = str(war.get("att_id", "Unknown"))
        defender_id = str(war.get("def_id", "Unknown"))
        
        aa_member_ids = {str(member["NationID"]) for member in alliance_members}
        our_side_is_attacker = attacker_id in aa_member_ids
        our_side_is_defender = defender_id in aa_member_ids
        
        if our_side_is_attacker and our_side_is_defender:
            our_side = "both"
        elif our_side_is_attacker:
            our_side = "attacker"
        elif our_side_is_defender:
            our_side = "defender"
        else:
            our_side = "unknown"
        
        attacker_info = await get_nation_info(attacker_id, api_key)
        defender_info = await get_nation_info(defender_id, api_key)
        attacker_name = attacker_info.get("nation_name", f"Nation {attacker_id}")
        defender_name = defender_info.get("nation_name", f"Nation {defender_id}")

        total_losses = {
            'att_soldiers': war.get("att_soldiers_lost", 0),
            'att_tanks': war.get("att_tanks_lost", 0),
            'att_aircraft': war.get("att_aircraft_lost", 0),
            'att_ships': war.get("att_ships_lost", 0),
            'def_soldiers': war.get("def_soldiers_lost", 0),
            'def_tanks': war.get("def_tanks_lost", 0),
            'def_aircraft': war.get("def_aircraft_lost", 0),
            'def_ships': war.get("def_ships_lost", 0)
        }

        current_participants = get_participants_from_description(war_channel)
        our_participants = []
        if our_side_is_attacker:
            our_participants.append(attacker_id)
        if our_side_is_defender:
            our_participants.append(defender_id)
            
        if len(our_participants) > 1:
            view = MultiWarParticipantView(our_participants, api_key, str(war_id))
            embed = await view.get_current_embed()
        else:
            summary_embed = await create_summary_embed(war, attacker_info, defender_info, our_side, total_losses, war_id)
            embed = summary_embed
            view = None

        pinned_messages = await war_channel.pins()
        main_message = None
        for msg in pinned_messages:
            if msg.author == war_channel.guild.me and msg.embeds:
                main_message = msg
                break
        
        if main_message:
            try:
                await main_message.edit(embed=embed, view=view)
            except discord.NotFound:
                main_message = await war_channel.send(embed=embed, view=view)
                await main_message.pin()
        else:
            main_message = await war_channel.send(embed=embed, view=view)
            await main_message.pin()
        
    except Exception as e:
        print(f"Error sending detailed war update: {e}")
        import traceback
        traceback.print_exc()

async def create_summary_embed(war, attacker_info, defender_info, our_side, total_losses, war_id):
    """Create the standard summary embed for single participants"""
    attacker_name = attacker_info.get("nation_name", f"Nation {war.get('att_id', 'Unknown')}")
    defender_name = defender_info.get("nation_name", f"Nation {war.get('def_id', 'Unknown')}")
    
    summary_embed = discord.Embed(
        title=f"⚡️ War Summary - ID {war_id}",
        description=f"**{attacker_name}** vs **{defender_name}**\n**Turns Remaining:** {war.get('turns_left', 999)}",
        color=get_war_color(war.get("war_type", ""))
    )

    att_resistance = war.get("att_resistance", 100.0)
    def_resistance = war.get("def_resistance", 100.0)
    
    if our_side == "attacker":
        our_resistance = att_resistance
        enemy_resistance = def_resistance
    elif our_side == "defender":
        our_resistance = def_resistance
        enemy_resistance = att_resistance
    else:
        our_resistance = att_resistance if our_side == "both" else 0
        enemy_resistance = def_resistance if our_side == "both" else 0
        
    resistance_bar = format_resistance_bar(our_resistance, enemy_resistance)
    summary_embed.add_field(name="💪 Resistance", value=resistance_bar, inline=False)

    att_points = war.get("att_points", 0)
    def_points = war.get("def_points", 0)
    our_points = att_points if our_side in ["attacker", "both"] else def_points
    enemy_points = def_points if our_side in ["attacker", "both"] else att_points
    war_score_bar = format_war_score(our_points, enemy_points)
    summary_embed.add_field(name="📈 MAPs", value=war_score_bar, inline=False)

    att_losses = []
    if total_losses['att_soldiers'] > 0: att_losses.append(f"👥 Soldiers: **{total_losses['att_soldiers']:,}**")
    if total_losses['att_tanks'] > 0: att_losses.append(f"🚛 Tanks: **{total_losses['att_tanks']:,}**")
    if total_losses['att_aircraft'] > 0: att_losses.append(f"✈️ Aircraft: **{total_losses['att_aircraft']:,}**")
    if total_losses['att_ships'] > 0: att_losses.append(f"🚢 Ships: **{total_losses['att_ships']:,}**")
    
    if our_side == "attacker" or our_side == "both":
        loss_label_att = "💔 OUR TOTAL LOSSES"
    else:
        loss_label_att = "🎯 ENEMY TOTAL LOSSES"
        
    summary_embed.add_field(name=f"{loss_label_att} ({attacker_name})", value="\n".join(att_losses) if att_losses else "None", inline=True)

    def_losses = []
    if total_losses['def_soldiers'] > 0: def_losses.append(f"👥 Soldiers: **{total_losses['def_soldiers']:,}**")
    if total_losses['def_tanks'] > 0: def_losses.append(f"🚛 Tanks: **{total_losses['def_tanks']:,}**")
    if total_losses['def_aircraft'] > 0: def_losses.append(f"✈️ Aircraft: **{total_losses['def_aircraft']:,}**")
    if total_losses['def_ships'] > 0: def_losses.append(f"🚢 Ships: **{total_losses['def_ships']:,}**")

    if our_side == "defender" or our_side == "both":
        loss_label_def = "💔 OUR TOTAL LOSSES"
    else:
        loss_label_def = "🎯 ENEMY TOTAL LOSSES"
        
    summary_embed.add_field(name=f"{loss_label_def} ({defender_name})", value="\n".join(def_losses) if def_losses else "None", inline=True)
    summary_embed.add_field(name="\u200b", value="\u200b", inline=True) 

    attacker_id = int(war.get('att_id', 0))
    defender_id = int(war.get('def_id', 0))
    control_info = []
    control_info.append(f"🪖 Ground: {get_control_status(war.get('ground_control', 0), attacker_id, defender_id, our_side)}")
    control_info.append(f"✈️ Air: {get_control_status(war.get('air_superiority', 0), attacker_id, defender_id, our_side)}")
    control_info.append(f"🚢 Naval: {get_blockade_status(war.get('naval_blockade', 0), attacker_id, defender_id, our_side)}")
    
    summary_embed.add_field(name="🌐 Current Control", value="\n".join(control_info), inline=False)
    
    return summary_embed

def find_existing_war_room_by_enemy(category: discord.CategoryChannel, enemy_id: str) -> Optional[discord.TextChannel]:
    """Find existing war room channel by checking if enemy nation ID matches the end of channel name"""
    try:
        for channel in category.channels:
            if isinstance(channel, discord.TextChannel):
                if channel.name.endswith(f"-{enemy_id}"):
                    print(f"Found existing room {channel.name} for enemy {enemy_id}")
                    return channel
        
        return None
    except Exception as e:
        print(f"Error finding existing war room: {e}")
        return None

async def update_war_room_access(guild: discord.Guild, channel: discord.TextChannel, new_participant_ids: Set[str], alliance_members: List[Dict]):
    """Add new participants to war room and send join notification"""
    try:
        current_participants = get_participants_from_description(channel)
        truly_new = new_participant_ids - current_participants
        
        if not truly_new:
            return
        
        aa_member_map = {str(member["NationID"]): member["DiscordID"] for member in alliance_members}
        
        for nation_id in truly_new:
            if nation_id in aa_member_map:
                try:
                    discord_member = guild.get_member(int(aa_member_map[nation_id]))
                    if discord_member:
                        await channel.set_permissions(
                            discord_member, 
                            read_messages=True, 
                            send_messages=True
                        )
                except Exception as e:
                    print(f"Error adding participant {nation_id}: {e}")
    except Exception as e:
        print(f"Error updating war room access: {e}")

async def create_war_room(
    guild: discord.Guild, 
    war_data: Dict, 
    alliance_members: List[Dict], 
    api_key: str
) -> Optional[discord.TextChannel]:
    try:
        war_id = war_data.get("id")
        if not war_id:
            print("War ID is missing from war data")
            return None
            
        attacker_id = str(war_data.get("att_id", "Unknown"))
        defender_id = str(war_data.get("def_id", "Unknown"))
        category_id = get_warroom_id(guild.id)
        war_type = war_data.get("war_type", "Unknown")

        try:
            category = await bot.fetch_channel(category_id)
        except discord.NotFound:
            print(f"Category {category_id} not found in guild {guild.id}")
            return None
        except discord.Forbidden:
            print(f"Bot does not have permissions to fetch category {category_id} in guild {guild.id}.")
            return None
        
        aa_member_ids = {str(member["NationID"]) for member in alliance_members}
        our_participants = []
        enemy_id = None
        
        if attacker_id in aa_member_ids:
            our_participants.append(attacker_id)
            enemy_id = defender_id
        if defender_id in aa_member_ids:
            our_participants.append(defender_id)
            if enemy_id is None:
                enemy_id = attacker_id
            
        if not our_participants:
            return None
        
        # Check if room already exists
        existing_room = find_existing_war_room_by_enemy(category, enemy_id)
        if existing_room:
            # Add new participants to existing room
            await update_war_room_access(guild, existing_room, set(our_participants), alliance_members)
            current_participants = get_participants_from_description(existing_room)
            all_participants = current_participants | set(our_participants)
            await update_channel_description(existing_room, all_participants)
            
            # Update tracked war with new participants
            tracked_war = get_tracked_war(str(war_id))
            if not tracked_war:
                insert_tracked_war(
                    str(war_id),
                    guild.id,
                    existing_room.id,
                    enemy_id,
                    war_data.get('date', datetime.utcnow().isoformat()),
                    ",".join(all_participants)
                )
            return existing_room
        
        # Create new room
        attacker_info = await get_nation_info(attacker_id, api_key)
        defender_info = await get_nation_info(defender_id, api_key)
        
        enemy_info = attacker_info if enemy_id == attacker_id else defender_info
        enemy_name = enemy_info.get('nation_name', f'Nation {enemy_id}')
        
        channel_name = f"war-{war_id}-vs-nation-{enemy_id}"
        
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        
        for member_data in alliance_members:
            if str(member_data["NationID"]) in our_participants:
                try:
                    discord_member = guild.get_member(int(member_data["DiscordID"]))
                    if discord_member:
                        overwrites[discord_member] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
                except (ValueError, TypeError):
                    print(f"Invalid Discord ID: {member_data['DiscordID']}")
                    continue

        try:
            gov_role_name = get_settings_value("GOV_ROLE", guild.id)
            if gov_role_name:
                gov_role = discord.utils.get(guild.roles, name=gov_role_name)
                if gov_role:
                    overwrites[gov_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
        except Exception as e:
            print(f"Could not add government role: {e}")
        
        channel = await category.create_text_channel(
            name=channel_name,
            overwrites=overwrites,
            reason=f"War room for war ID {war_id}"
        )
        
        # Set initial description with participants
        await update_channel_description(channel, set(our_participants))
        
        # Insert into tracked wars
        insert_tracked_war(
            str(war_id),
            guild.id,
            channel.id,
            enemy_id,
            war_data.get('date', datetime.utcnow().isoformat()),
            ",".join(our_participants)
        )
        
        embed = discord.Embed(
            title=f"⚔️ **NEW WAR ROOM** - ID {war_id}",
            description=f"Initiated a **{war_type.upper()}** war against **{enemy_name}**.",
            color=get_war_color(war_type)
        )
        
        embed.add_field(name="Attacker", value=f"**{attacker_info.get('nation_name', 'Unknown')}**\n({attacker_info.get('alliance', {}).get('name', 'No Alliance')})", inline=True)
        embed.add_field(name="Defender", value=f"**{defender_info.get('nation_name', 'Unknown')}**\n({defender_info.get('alliance', {}).get('name', 'No Alliance')})", inline=True)
        embed.add_field(name="\u200b", value="\u200b", inline=True)
        
        att_resistance = war_data.get("att_resistance", 100.0)
        def_resistance = war_data.get("def_resistance", 100.0)
        embed.add_field(name="💪 Starting Resistance", value=f"Attacker: **{att_resistance:.1f}%**\nDefender: **{def_resistance:.1f}%**", inline=False)
        
        control_info = []
        control_info.append(f"🪖 Ground: {get_control_status(war_data.get('ground_control', 0), int(attacker_id), int(defender_id), 'unknown')}")
        control_info.append(f"✈️ Air: {get_control_status(war_data.get('air_superiority', 0), int(attacker_id), int(defender_id), 'unknown')}")
        
        naval_text = ""
        naval_blockade = war_data.get("naval_blockade", 0)
        if naval_blockade == int(attacker_id): naval_text = "🟢 **Attacker Blockades**"
        elif naval_blockade == int(defender_id): naval_text = "🟢 **Defender Blockades**"
        else: naval_text = "🟡 **No Blockade**"
        control_info.append(f"🚢 Naval: {naval_text}")
        
        embed.add_field(name="🌐 Current War Control", value="\n".join(control_info), inline=False)
        
        embed.timestamp = discord.utils.utcnow()
        embed.set_footer(text="War Room | Updates every 30 minutes")
        
        involved_discord_ids = [
            f"<@{member['DiscordID']}>" for member in alliance_members 
            if str(member["NationID"]) in our_participants
        ]
        
        await channel.send(
            f"**Welcome to the War Room!** {', '.join(involved_discord_ids)}\n"
            f"A war has started. All initial intel is below."
        )
        
        main_message = await channel.send(embed=embed)
        await main_message.pin()
        
        print(f"Created war room {channel.name} for war {war_id}")
        return channel
        
    except discord.HTTPException as e:
        print(f"Discord API error creating war room for war {war_id}: {e}")
        return None
    except Exception as e:
        print(f"Error creating war room for war {war_id}: {e}")
        import traceback
        traceback.print_exc()
        return None

# ==================== EVENT HANDLERS ====================

async def handle_new_war_event(war_data: Dict, guild: discord.Guild, alliance_members: List[Dict], api_key: str):
    """Handle a new war creation event"""
    try:
        war_id = str(war_data.get("id"))
        attacker_id = str(war_data.get("att_id"))
        defender_id = str(war_data.get("def_id"))
        
        aa_member_ids = {str(member["NationID"]) for member in alliance_members}
        
        # Check if any alliance members are involved
        if attacker_id not in aa_member_ids and defender_id not in aa_member_ids:
            return
        
        # Create war room
        war_channel = await create_war_room(guild, war_data, alliance_members, api_key)
        
        if war_channel:
            # Send initial update
            await send_detailed_war_update(
                war_channel, war_data, alliance_members, False, api_key
            )
            
    except Exception as e:
        print(f"Error handling new war event: {e}")
        import traceback
        traceback.print_exc()

@bot.event
async def on_ready():
    """Start the periodic war check task when bot is ready"""
    if RUN:
        bot.loop.create_task(check_and_update_wars())
        print("✅ Periodic war check task started")

# ==================== COMMANDS ====================

@bot.tree.command(name='toggle_war_rooms', description='Enable or disable automatic war room creation')
async def toggle_war_rooms(interaction: discord.Interaction):
    try:
        await interaction.response.defer()
        guild_id = interaction.guild.id
        current_status = str(get_toggle_value_gd("WAR_ROOMS_TOGGLE", guild_id)).lower()
        
        if current_status == "true":
            new_status = "false"
        elif current_status == "false":
            new_status = "true"
        set_server_setting(guild_id, "WAR_ROOMS_TOGGLE", new_status)
        
        status_text = "enabled" if new_status == "true" else "disabled"
        embed = discord.Embed(
            title="War Rooms Toggle",
            description=f"War rooms have been **{status_text}** for this server.",
            color=0x00ff00 if new_status == "true" else 0xff0000
        )
        
        if new_status == "true":
            embed.add_field(
                name="What happens now?", 
                value="• War rooms will be checked every 30 minutes\n• Wars lasting 120+ hours will be automatically closed\n• Rooms will auto-delete when wars end\n• Only involved members get access",
                inline=False
            )
        else:
            embed.add_field(
                name="What happens now?",
                value="• No new war rooms will be created\n• Existing war rooms will remain until manually deleted",
                inline=False
            )
        
        await interaction.followup.send(embed=embed)
    except Exception as e:
        print(f"Error in toggle_war_rooms command: {e}")
        if not interaction.response.is_done():
            await interaction.response.send_message("An error occurred while toggling war rooms.", ephemeral=True)
        else:
            await interaction.followup.send("An error occurred while toggling war rooms.", ephemeral=True)

@bot.tree.command(name='force_war_check', description='Manually trigger a war check (Admin only)')
async def force_war_check(interaction: discord.Interaction):
    """Manually trigger a war update check"""
    try:
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ You need administrator permissions to use this command.", ephemeral=True)
            return
        
        await interaction.response.defer()
        
        guild_id = interaction.guild.id
        if not get_toggle_value_gd("WAR_ROOMS_TOGGLE", guild_id):
            await interaction.followup.send("❌ War rooms are disabled for this server.", ephemeral=True)
            return
        
        api_key = get_api_key_for_guild(guild_id)
        if not api_key:
            await interaction.followup.send("❌ No API key configured for this server.", ephemeral=True)
            return
        
        tracked_wars = get_active_tracked_wars_for_guild(guild_id)
        
        if not tracked_wars:
            await interaction.followup.send("ℹ️ No active tracked wars found.", ephemeral=True)
            return
        
        updated_count = 0
        completed_count = 0
        
        for tracked_war in tracked_wars:
            try:
                war_id = tracked_war['war_id']
                channel_id = tracked_war['channel_id']
                start_date = tracked_war['start_date']
                
                # Check if war has reached 120 hours
                is_completed = await check_war_completion(war_id, start_date, api_key)
                
                if is_completed:
                    mark_war_completed(war_id)
                    completed_count += 1
                    
                    try:
                        channel = await bot.fetch_channel(int(channel_id))
                        if channel:
                            await channel.delete(reason=f"War {war_id} completed (120 hours)")
                    except:
                        pass
                    
                    continue
                
                # Get current war data
                war_data = await get_war_data_from_api(war_id, api_key)
                
                if not war_data:
                    continue
                
                # Check if war has ended
                if war_data.get('end_date'):
                    mark_war_completed(war_id)
                    completed_count += 1
                    
                    try:
                        channel = await bot.fetch_channel(int(channel_id))
                        if channel:
                            await channel.delete(reason=f"War {war_id} ended")
                    except:
                        pass
                    
                    continue
                
                # Update the war room
                try:
                    channel = await bot.fetch_channel(int(channel_id))
                    if channel:
                        alliance_members = await get_alliance_members(guild_id)
                        await send_detailed_war_update(
                            channel, war_data, alliance_members, False, api_key
                        )
                        update_tracked_war_last_checked(war_id)
                        updated_count += 1
                except Exception as e:
                    print(f"Error updating war room for {war_id}: {e}")
                
            except Exception as e:
                print(f"Error processing tracked war {tracked_war.get('war_id', 'Unknown')}: {e}")
        
        embed = discord.Embed(
            title="✅ War Check Complete",
            description=f"Processed {len(tracked_wars)} tracked wars",
            color=discord.Color.green()
        )
        embed.add_field(name="Updated", value=str(updated_count), inline=True)
        embed.add_field(name="Completed", value=str(completed_count), inline=True)
        embed.add_field(name="Total Tracked", value=str(len(tracked_wars)), inline=True)
        
        await interaction.followup.send(embed=embed)
        
    except Exception as e:
        print(f"Error in force_war_check command: {e}")
        import traceback
        traceback.print_exc()
        if not interaction.response.is_done():
            await interaction.response.send_message("An error occurred while checking wars.", ephemeral=True)
        else:
            await interaction.followup.send("An error occurred while checking wars.", ephemeral=True)

@bot.tree.command(name='create_war_room', description='Manually create a war room for a specific war ID')
async def create_war_room_cmd(interaction: discord.Interaction, war_id: str):
    """Manually create a war room"""
    try:
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ You need administrator permissions to use this command.", ephemeral=True)
            return
        
        await interaction.response.defer()
        
        guild_id = interaction.guild.id
        api_key = get_api_key_for_guild(guild_id)
        
        if not api_key:
            await interaction.followup.send("❌ No API key configured for this server.", ephemeral=True)
            return
        
        # Fetch war data
        war_data = await get_war_data_from_api(war_id, api_key)
        
        if not war_data:
            await interaction.followup.send(f"❌ Could not find war with ID: {war_id}", ephemeral=True)
            return
        
        alliance_members = await get_alliance_members(guild_id)
        
        # Create the war room
        war_channel = await create_war_room(interaction.guild, war_data, alliance_members, api_key)
        
        if war_channel:
            await send_detailed_war_update(war_channel, war_data, alliance_members, False, api_key)
            await interaction.followup.send(f"✅ War room created: {war_channel.mention}", ephemeral=True)
        else:
            await interaction.followup.send("❌ Failed to create war room. Check logs for details.", ephemeral=True)
            
    except Exception as e:
        print(f"Error in create_war_room_cmd: {e}")
        import traceback
        traceback.print_exc()
        if not interaction.response.is_done():
            await interaction.response.send_message("An error occurred while creating the war room.", ephemeral=True)
        else:
            await interaction.followup.send("An error occurred while creating the war room.", ephemeral=True)

bot.command(name="toggle_war_rooms")(wrap_as_prefix_command(toggle_war_rooms.callback))
bot.command(name="force_war_check")(wrap_as_prefix_command(force_war_check.callback))
bot.command(name="create_war_room")(wrap_as_prefix_command(create_war_room_cmd.callback))
                
