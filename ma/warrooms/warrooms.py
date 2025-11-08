import json
import discord
from pathlib import Path
import asyncio
from typing import Dict, List, Optional, Set
from settings.bot_instance import bot, wrap_as_prefix_command    
from settings.initializer_functions.cached_users_initializer import cached_users
from settings.settings_multi import get_warroom_id, get_api_key_for_guild, get_aa_name_guild, get_settings_value


active_war_rooms: Dict[str, Dict] = {}  
war_rooms_active: Dict[int, bool] = {}  

async def get_attack_data(war_id: str, api_key: str) -> dict:
    
    import aiohttp

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
        return {}

async def get_nation_info(nation_id: str, api_key: str) -> Dict:
    
    try:
        import aiohttp
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
                    return {}
    except Exception as e:
        return {}


async def get_alliance_members(guild_id: int) -> List[Dict]:
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



def get_war_color(war_type: str) -> int:
    
    war_type = war_type.lower()
    if "nuke" in war_type:
        return discord.Color.yellow()
    elif "naval" in war_type:
        discord.Color.dark_blue()
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
            
        war_data = active_war_rooms.get(str(war_id), {})

        
        attacker_info = await get_nation_info(attacker_id, api_key)
        defender_info = await get_nation_info(defender_id, api_key)
        attacker_name = attacker_info.get("nation_name", f"Nation {attacker_id}")
        defender_name = defender_info.get("nation_name", f"Nation {defender_id}")

        
        attack_data = await get_attack_data(war_id, api_key)
        if is_new_turn:
            action_name, success_text = await get_action_data(war_id, api_key)
            color = get_war_color(action_name)
            if action_name in ["🕊️ Peace Offer", "🛡️ Fortify"]:
                if success_text == "⚠️ **PYRRHIC VICTORY**":
                    if action_name == "🕊️ Peace Offer":
                        action_name = "🕊️ Sent Peace Offer"
                    elif action_name == "🛡️ Fortify":
                        action_name = "🛡️ Fortified"
                if success_text == "💥 **UTTER FAILURE**":
                    if action_name == "🕊️ Peace Offer":
                        action_name = "💥 Cancelled Peace Offer"
                        
                turn_embed = discord.Embed(
                    title=f"{action_name}",
                    description=f"Done by **{attacker_name}**",
                    color=color
                )
                turn_embed.set_footer(text=f"Turn Update | War ID: {war_id}")
                await war_channel.send(embed=turn_embed)
            elif action_name == "❓ Unknown Action":
                Placeholder = None
            else:
                turn_embed = discord.Embed(
                    title=f"{action_name} - {success_text}",
                    description=f"Attack performed by **{attacker_name}**",
                    color=color
                )
                
                
                att_soldiers_lost = attack_data.get("att_soldiers_lost", 0)
                att_tanks_lost = attack_data.get("att_tanks_lost", 0) 
                att_aircraft_lost = attack_data.get("att_aircraft_lost", 0)
                att_ships_lost = attack_data.get("att_ships_lost", 0)
                
                att_losses = []
                if att_soldiers_lost > 0: att_losses.append(f"👥 Soldiers: **{att_soldiers_lost:,}**")
                if att_tanks_lost > 0: att_losses.append(f"🚛 Tanks: **{att_tanks_lost:,}**")
                if att_aircraft_lost > 0: att_losses.append(f"✈️ Aircraft: **{att_aircraft_lost:,}**")
                if att_ships_lost > 0: att_losses.append(f"🚢 Ships: **{att_ships_lost:,}**")

                
                if our_side == "attacker" or (our_side == "both" and attacker_id in aa_member_ids):
                    att_loss_label = "💔 Our Losses"
                else:
                    att_loss_label = "🎯 Enemy Losses"
                    
                turn_embed.add_field(
                    name=f"{att_loss_label} ({attacker_name})", 
                    value="\n".join(att_losses) if att_losses else "None", 
                    inline=True
                )
                
                
                def_soldiers_lost = attack_data.get("def_soldiers_lost", 0)
                def_tanks_lost = attack_data.get("def_tanks_lost", 0)
                def_aircraft_lost = attack_data.get("def_aircraft_lost", 0) 
                def_ships_lost = attack_data.get("def_ships_lost", 0)

                def_losses = []
                if def_soldiers_lost > 0: def_losses.append(f"👥 Soldiers: **{def_soldiers_lost:,}**")
                if def_tanks_lost > 0: def_losses.append(f"🚛 Tanks: **{def_tanks_lost:,}**")
                if def_aircraft_lost > 0: def_losses.append(f"✈️ Aircraft: **{def_aircraft_lost:,}**")
                if def_ships_lost > 0: def_losses.append(f"🚢 Ships: **{def_ships_lost:,}**")

                
                if our_side == "defender" or (our_side == "both" and defender_id in aa_member_ids):
                    def_loss_label = "💔 Our Losses"
                else:
                    def_loss_label = "🎯 Enemy Losses"
                    
                turn_embed.add_field(
                    name=f"{def_loss_label} ({defender_name})", 
                    value="\n".join(def_losses) if def_losses else "None", 
                    inline=True
                )
                turn_embed.add_field(name="\u200b", value="\u200b", inline=True) 

                
                naval_blockade_id = war.get("naval_blockade", 0)
                blockade_status = get_blockade_status(naval_blockade_id, int(attacker_id), int(defender_id), our_side)
                turn_embed.add_field(name="🚢 Blockade Status", value=blockade_status, inline=False)

                
                last_action_data = war_data.get('last_action', {})
                ground_gained = (war.get('ground_control', 0) != last_action_data.get('ground_control', 0) and war.get('ground_control', 0) in [int(attacker_id), int(defender_id)])
                air_gained = (war.get('air_superiority', 0) != last_action_data.get('air_superiority', 0) and war.get('air_superiority', 0) in [int(attacker_id), int(defender_id)])
                naval_gained = (war.get('naval_blockade', 0) != last_action_data.get('naval_blockade', 0) and war.get('naval_blockade', 0) in [int(attacker_id), int(defender_id)])

                
                gained_control_text = []
                if ground_gained: gained_control_text.append("🪖 Ground Control")
                if air_gained: gained_control_text.append("✈️ Air Superiority") 
                if naval_gained: gained_control_text.append("🚢 Naval Blockade")

                turn_embed.add_field(
                    name="🏆 Control Gained This Turn",
                    value="\n".join(gained_control_text) if gained_control_text else "None",
                    inline=False
                )
                
                turn_embed.timestamp = discord.utils.utcnow()
                turn_embed.set_footer(text=f"Turn Update | War ID: {war_id}")
                await war_channel.send(embed=turn_embed)

        
        
        
        total_losses = {
            'att_soldiers': 0, 'att_tanks': 0, 'att_aircraft': 0, 'att_ships': 0,
            'def_soldiers': 0, 'def_tanks': 0, 'def_aircraft': 0, 'def_ships': 0
        }

        
        total_losses['att_soldiers'] = war.get("att_soldiers_lost", 0)
        total_losses['att_tanks'] = war.get("att_tanks_lost", 0) 
        total_losses['att_aircraft'] = war.get("att_aircraft_lost", 0)
        total_losses['att_ships'] = war.get("att_ships_lost", 0)
        total_losses['def_soldiers'] = war.get("def_soldiers_lost", 0)
        total_losses['def_tanks'] = war.get("def_tanks_lost", 0)
        total_losses['def_aircraft'] = war.get("def_aircraft_lost", 0) 
        total_losses['def_ships'] = war.get("def_ships_lost", 0)

        
        active_war_rooms[str(war_id)]['total_losses'] = total_losses

        
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

        
        control_info = []
        control_info.append(f"🪖 Ground: {get_control_status(war.get('ground_control', 0), int(attacker_id), int(defender_id), our_side)}")
        control_info.append(f"✈️ Air: {get_control_status(war.get('air_superiority', 0), int(attacker_id), int(defender_id), our_side)}")
        control_info.append(f"🚢 Naval: {get_blockade_status(war.get('naval_blockade', 0), int(attacker_id), int(defender_id), our_side)}")
        
        summary_embed.add_field(name="🌐 Current Control", value="\n".join(control_info), inline=False)

        
        if war_data.get('main_embed_id'):
            try:
                main_message = await war_channel.fetch_message(war_data['main_embed_id'])
                await main_message.edit(embed=summary_embed)
            except discord.NotFound:
                
                main_message = await war_channel.send(embed=summary_embed)
                active_war_rooms[str(war_id)]['main_embed_id'] = main_message.id
        else:
            
            main_message = await war_channel.send(embed=summary_embed)
            active_war_rooms[str(war_id)]['main_embed_id'] = main_message.id
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        try:
            await war_channel.send(f"War {war.get('id', 'Unknown')} updated - check the game for details")
        except:
            pass


async def find_existing_war_room(guild: discord.Guild, enemy_id: str, category_id: int) -> Optional[discord.TextChannel]:
    try:
        category = await bot.fetch_channel(category_id)
        enemy_suffix = f"-{enemy_id}"
        
        for channel in category.channels:
            if isinstance(channel, discord.TextChannel) and channel.name.endswith(enemy_suffix):
                return channel
        return None
    except Exception as e:
        return None


async def add_member_to_war_room(
    channel: discord.TextChannel,
    war_id: str,
    member_nation_id: str,
    member_discord_id: str,
    guild: discord.Guild
) -> bool:
    try:
        discord_member = guild.get_member(int(member_discord_id))
        if not discord_member:
            return False
        
        overwrites = dict(channel.overwrites)
        overwrites[discord_member] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
        await channel.edit(overwrites=overwrites)
        
        for existing_war_id, war_data in active_war_rooms.items():
            if war_data.get('channel_id') == channel.id:
                if member_nation_id not in war_data['participants']:
                    war_data['participants'].append(member_nation_id)
                if war_id != existing_war_id:
                    active_war_rooms[war_id] = war_data
                break
        
        await channel.send(f"<@{member_discord_id}> has joined the war room! (War ID: {war_id})")
        return True
        
    except Exception as e:
        return False


async def update_war_room_description(channel: discord.TextChannel, war_ids: List[str]):
    try:
        topic = f"Active Wars: {', '.join(war_ids)}"
        await channel.edit(topic=topic[:1024])
    except Exception as e:
        print(f"Error updating war room description: {e}")


async def create_war_room(
    guild: discord.Guild, 
    war_data: Dict, 
    alliance_members: List[Dict], 
    api_key: str
) -> Optional[discord.TextChannel]:
    try:
        war_id = war_data.get("id")
        if not war_id:
            return None
            
        attacker_id = str(war_data.get("att_id", "Unknown"))
        defender_id = str(war_data.get("def_id", "Unknown"))
        category_id = get_warroom_id(guild.id)
        war_type = war_data.get("war_type", "Unknown")

        try:
            category = await bot.fetch_channel(category_id)
        except discord.NotFound:
            return None
        except discord.Forbidden:
            return None
        
        aa_member_ids = {str(member["NationID"]) for member in alliance_members}
        our_side = []
        enemy_id = None
        
        if attacker_id in aa_member_ids:
            our_side.append(attacker_id)
            enemy_id = defender_id
        if defender_id in aa_member_ids:
            our_side.append(defender_id)
            if enemy_id is None:
                enemy_id = attacker_id
            
        if not our_side:
            return None
        
        existing_room = await find_existing_war_room(guild, enemy_id, category_id)
        
        if existing_room:
            for nation_id in our_side:
                member_data = next((m for m in alliance_members if str(m["NationID"]) == nation_id), None)
                if member_data:
                    await add_member_to_war_room(
                        existing_room,
                        str(war_id),
                        nation_id,
                        member_data["DiscordID"],
                        guild
                    )
            
            war_ids_in_room = [
                wid for wid, data in active_war_rooms.items() 
                if data.get('channel_id') == existing_room.id
            ]
            if str(war_id) not in war_ids_in_room:
                war_ids_in_room.append(str(war_id))
            
            await update_war_room_description(existing_room, war_ids_in_room)
            
            return existing_room
        
        attacker_info = await get_nation_info(attacker_id, api_key)
        defender_info = await get_nation_info(defender_id, api_key)
        
        enemy_info = attacker_info if enemy_id == attacker_id else defender_info
        enemy_name = enemy_info.get('nation_name', f'Nation {enemy_id}')
        
        sanitized_enemy_name = ''.join(c for c in enemy_name if c.isalnum() or c in [' ', '-']).strip()
        sanitized_enemy_name = sanitized_enemy_name.lower().replace(' ', '-')[:20]
        
        channel_name = f"war-{war_id}-vs-{sanitized_enemy_name}-{enemy_id}"
        
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        
        try:
            gov_role_name = get_settings_value("GOV_ROLE", guild.id)
            if gov_role_name:
                gov_role = discord.utils.get(guild.roles, name=gov_role_name)
                if gov_role:
                    overwrites[gov_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
        except Exception as e:
            print(f"Could not add government role: {e}")
        for member_data in alliance_members:
            if str(member_data["NationID"]) in our_side:
                try:
                    discord_member = guild.get_member(int(member_data["DiscordID"]))
                    if discord_member:
                        overwrites[discord_member] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
                except (ValueError, TypeError):
                    print(f"Invalid Discord ID for Nation {member_data['NationID']}: {member_data['DiscordID']}")
        
        channel = await category.create_text_channel(
            name=channel_name,
            overwrites=overwrites,
            topic=f"Active Wars: {war_id}",
            reason=f"War room for war ID {war_id}"
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
        if naval_blockade == int(attacker_id): 
            naval_text = "🟢 **Attacker Blockades**"
        elif naval_blockade == int(defender_id): 
            naval_text = "🟢 **Defender Blockades**"
        else: 
            naval_text = "🟡 **No Blockade**"
        control_info.append(f"🚢 Naval: {naval_text}")
        
        embed.add_field(name="🌐 Current War Control", value="\n".join(control_info), inline=False)
        embed.add_field(name="Attacker's Readiness", value=f"**Resistance:** {war_data.get('att_resistance', 'N/A')}%\n**AP:** {war_data.get('att_ap', 'N/A')}\n**MP:** {war_data.get('att_mp', 'N/A')}", inline=True)
        embed.add_field(name="Defender's Readiness", value=f"**Resistance:** {war_data.get('def_resistance', 'N/A')}%\n**AP:** {war_data.get('def_ap', 'N/A')}\n**MP:** {war_data.get('def_mp', 'N/A')}", inline=True)
        embed.add_field(name="\u200b", value="\u200b", inline=True)
        embed.timestamp = discord.utils.utcnow()
        embed.set_footer(text="Live Updates will follow shortly | This channel is automatically managed.")
        
        involved_discord_ids = [
            f"<@{member['DiscordID']}>" for member in alliance_members 
            if str(member["NationID"]) in our_side
        ]
        
        await channel.send(
            f"**Welcome to the War Room!** {', '.join(involved_discord_ids)}\n"
            f"A war has started. All initial intel is below. Wait for the first update for battle details."
        )
        
        main_message = await channel.send(embed=embed)
        
        active_war_rooms[str(war_id)] = {
            'channel_id': channel.id,
            'participants': our_side,
            'guild_id': guild.id,
            'enemy_id': enemy_id,
            'main_embed_id': main_message.id,
            'total_losses': {
                'att_soldiers': 0, 'att_tanks': 0, 'att_aircraft': 0, 'att_ships': 0,
                'def_soldiers': 0, 'def_tanks': 0, 'def_aircraft': 0, 'def_ships': 0
            },
            'last_action': {},
            'peace_offered': False
        }
        
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


async def update_war_room_access(guild: discord.Guild, war_id: str, current_participants: Set[str]):
    try:
        if str(war_id) not in active_war_rooms:
            return
            
        war_room_data = active_war_rooms[str(war_id)]
        channel = guild.get_channel(war_room_data['channel_id'])
        if not channel:
            del active_war_rooms[str(war_id)]
            return
        
        alliance_members = await get_alliance_members(guild.id)
        aa_member_map = {str(member["NationID"]): member["DiscordID"] for member in alliance_members}
        
        overwrites = dict(channel.overwrites)
        
        old_participants = set(war_room_data['participants'])
        removed_participants = old_participants - current_participants
        
        for nation_id in removed_participants:
            if nation_id in aa_member_map:
                try:
                    discord_member = guild.get_member(int(aa_member_map[nation_id]))
                    if discord_member and discord_member in overwrites:
                        del overwrites[discord_member]
                except (ValueError, TypeError):
                    print(f"Invalid Discord ID when removing access: {aa_member_map[nation_id]}")
                    continue
        
        new_participants = current_participants - old_participants
        for nation_id in new_participants:
            if nation_id in aa_member_map:
                try:
                    discord_member = guild.get_member(int(aa_member_map[nation_id]))
                    if discord_member:
                        overwrites[discord_member] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
                except (ValueError, TypeError):
                    print(f"Invalid Discord ID when adding access: {aa_member_map[nation_id]}")
                    continue
        
        await channel.edit(overwrites=overwrites)
        war_room_data['participants'] = list(current_participants)
        wars_in_room = [wid for wid, data in active_war_rooms.items() if data.get('channel_id') == channel.id]
        
        if not current_participants or not wars_in_room:
            await channel.delete(reason=f"No alliance members left in war room")
            for wid in wars_in_room:
                if wid in active_war_rooms:
                    del active_war_rooms[wid]
            print(f"Deleted war room for wars {wars_in_room} - no alliance members remaining")
        
    except discord.HTTPException as e:
        print(f"Discord API error updating war room access for war {war_id}: {e}")
    except Exception as e:
        print(f"Error updating war room access for war {war_id}: {e}")


async def run_node_listener():
    """Start the Node.js PnW event listener"""
    try:
        project_path = Path(__file__).parent.resolve()
        print("Installing Node.js packages...")
        install_process = await asyncio.create_subprocess_exec(
            "node", "pnw_listener.mjs",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(project_path),  
            limit=1024*1024
        )

        await install_process.wait()\
        
        if install_process.returncode == 0:
            print("Node.js packages installed successfully")
        else:
            print(f"Package installation failed with code {install_process.returncode}")
        node_modules_path = project_path / "node_modules"
        if node_modules_path.exists():
            print(f"node_modules directory exists at {node_modules_path}")
            pusher_path = node_modules_path / "pusher-js"
            if pusher_path.exists():
                print("pusher-js package found")
            else:
                print("pusher-js package NOT found")
        else:
            print("node_modules directory does NOT exist")
        
        print("Starting Node.js listener process...")
        process = await asyncio.create_subprocess_exec(
            "node", "pnw_listener.mjs",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(project_path), 
            limit=1024*1024
        )
        
        print(f"Node.js process started with PID: {process.pid}")

        async def read_stream(stream):
            while True:
                line = await stream.readline()
                if not line:
                    print("Node.js stream ended")
                    break
                yield line.decode("utf-8").strip()

        return process, read_stream(process.stdout), read_stream(process.stderr)
    except Exception as e:
        print(f"Error starting Node.js listener: {e}")
        return None, None, None


async def handle_pnw_events():
    listener_result = await run_node_listener()
    if not all(listener_result):
        print("❌ Failed to start PnW listener")
        return

    process, stdout_lines, stderr_lines = listener_result
    await asyncio.sleep(1)

    async def handle_stdout():
        async for line in stdout_lines:
            try:
                if not line or not (line.startswith("{") or line.startswith("[")):
                    continue

                event = json.loads(line)
                event_type = event.get("type", "")
                event_data = event.get("data", {})

                if event_type not in ("BULK_WAR_UPDATE", "WAR_CREATE", "BULK_WAR_CREATE", "WAR_UPDATE"):
                    continue

                wars = event_data if isinstance(event_data, list) else [event_data]

                for guild in bot.guilds:
                    try:
                        if not war_rooms_active.get(guild.id, False):
                            continue

                        api_key = get_api_key_for_guild(guild.id)
                        if not api_key:
                            continue

                        alliance_members = await get_alliance_members(guild.id)
                        if not alliance_members:
                            continue

                        aa_member_map = {str(m["NationID"]): m["DiscordID"] for m in alliance_members}

                        for war in wars:
                            is_new_turn = True
                            try:
                                war_id = str(war.get("id"))
                                if not war_id or war_id == "None":
                                    continue

                                attacker_id = str(war.get("att_id", "Unknown"))
                                defender_id = str(war.get("def_id", "Unknown"))

                                if attacker_id not in aa_member_map and defender_id not in aa_member_map:
                                    continue

                                if war_id not in active_war_rooms:
                                    war_channel = await create_war_room(guild, war, alliance_members, api_key)
                                    is_new_turn = False
                                    if not war_channel:
                                        continue
                                else:
                                    war_room_data = active_war_rooms[war_id]
                                    if war_room_data.get("guild_id") != guild.id:
                                        continue
                                    war_channel = guild.get_channel(war_room_data["channel_id"])
                                    if not war_channel:
                                        continue

                                await send_detailed_war_update(
                                    war_channel, war, alliance_members, is_new_turn, api_key=api_key
                                )

                                current_participants = {
                                    pid for pid in (attacker_id, defender_id) if pid in aa_member_map
                                }
                                await update_war_room_access(guild, war_id, current_participants)
                            

                            except Exception as e:
                                print(f"❌ Error processing war {war.get('id','Unknown')} in guild {guild.id}: {e}")
                                import traceback
                                traceback.print_exc()

                    except Exception as e:
                        print(f"❌ Error processing events for guild {guild.id}: {e}")
                        import traceback
                        traceback.print_exc()

            except json.JSONDecodeError:
                print(f"⚠️ JSON decode failed: {line}")
            except Exception as e:
                print(f"❌ Fatal error in stdout handler: {e}")
                import traceback
                traceback.print_exc()
        
        processed += 1
        if processed % 50 == 0:
            await asyncio.sleep(0.05)

    async def handle_stderr():
        async for line in stderr_lines:
            continue

    try:
        await asyncio.gather(handle_stdout(), handle_stderr())
    finally:
        if process and process.returncode is None:
            print(f"Terminating Node.js process (PID {process.pid})")
            process.terminate()
            await process.wait()


@bot.tree.command(name='toggle_war_rooms', description='Enable or disable automatic war room creation')
async def toggle_war_rooms(interaction: discord.Interaction):
    """Toggle war rooms on/off for the guild"""
    try:
        await interaction.response.defer()
        guild_id = interaction.guild.id
        current_status = war_rooms_active.get(guild_id, False)
        war_rooms_active[guild_id] = not current_status
        
        status_text = "enabled" if war_rooms_active[guild_id] else "disabled"
        embed = discord.Embed(
            title="War Rooms Toggle",
            description=f"War rooms have been **{status_text}** for this server.",
            color=0x00ff00 if war_rooms_active[guild_id] else 0xff0000
        )
        
        if war_rooms_active[guild_id]:
            embed.add_field(
                name="What happens now?", 
                value="• War rooms will be created when alliance members are involved in wars\n• Rooms will auto-delete when wars end\n• Only involved members get access\n• Multiple wars vs same enemy = same room",
                inline=False
            )
        else:
            embed.add_field(
                name="What happens now?",
                value="• No new war rooms will be created\n• Existing war rooms will remain until wars end",
                inline=False
            )
        
        await interaction.followup.send(embed=embed)
    except Exception as e:
        print(f"Error in toggle_war_rooms command: {e}")
        if not interaction.response.is_done():
            await interaction.response.send_message("An error occurred while toggling war rooms.", ephemeral=True)
        else:
            await interaction.followup.send("An error occurred while toggling war rooms.", ephemeral=True)

bot.command(name="toggle_war_rooms")(wrap_as_prefix_command(toggle_war_rooms.callback))