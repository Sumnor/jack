import discord
from discord.ext import commands, tasks
import google.generativeai as genai
import os
import re
from typing import Optional, List, Dict
from datetime import datetime, timedelta
from supabase import create_client, Client
import json
import random
from bot_instance import bot, SUPABASE_URL, SUPABASE_KEY, GEMINI_API_KEY

# Configure Gemini
genai.configure(api_key=GEMINI_API_KEY)

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

generation_config = {
    "temperature": 0.9,
    "top_p": 0.95,
    "top_k": 40,
    "max_output_tokens": 400,
}

safety_settings = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
]

gemini_model = genai.GenerativeModel(
    model_name="gemini-1.5-flash",
    generation_config=generation_config,
    safety_settings=safety_settings
)

SYSTEM_PROMPT = """You are a quirky, chill Discord bot assistant with personality. ... (unchanged) ..."""


def is_message_targeting_bot(content: str, bot_mentioned: bool, bot_user) -> bool:
    if not bot_mentioned:
        return False
    not_targeting_patterns = [
        r'@everyone',
        r'@here',
        r'and <@\d+>',
        r'<@\d+> and',
        r'not you <@\d+>',
        r'ignore <@\d+>',
    ]
    for pattern in not_targeting_patterns:
        if re.search(pattern, content):
            return False
    return True


def get_funny_comeback() -> str:
    comebacks = [
        "why am i here, just to suffer?",
        "you rang? oh wait nvmd",
        "i heard my name but i'll pretend i didn't",
        "standing by... still standing by...",
        "im choosing to ignore this",
        "tagged but not bagged, story of my life",
        "sorry i was processing other packets",
        "present but not accounted for",
    ]
    return random.choice(comebacks)


async def save_short_memory(channel_id: int, user_id: int, username: str, message: str, response: str = None, is_pinged: bool = False):
    try:
        supabase.table('bot_short_memory').insert({
            'channel_id': channel_id,
            'user_id': user_id,
            'username': username,
            'message': message,
            'response': response,
            'is_pinged': is_pinged,
            'timestamp': datetime.utcnow().isoformat()
        }).execute()
    except Exception as e:
        print(f"Error saving short memory: {e}")


async def save_observation(channel_id: int, observation: str, context: str = None):
    try:
        supabase.table('bot_observations').insert({
            'channel_id': channel_id,
            'observation': observation,
            'context': context,
            'timestamp': datetime.utcnow().isoformat()
        }).execute()
    except Exception as e:
        print(f"Error saving observation: {e}")


async def get_recent_memory(channel_id: int, hours: int = 24) -> List[Dict]:
    try:
        cutoff = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
        result = supabase.table('bot_short_memory')\
            .select('*')\
            .eq('channel_id', channel_id)\
            .gte('timestamp', cutoff)\
            .order('timestamp', desc=True)\
            .limit(50)\
            .execute()
        return result.data if result.data else []
    except Exception as e:
        print(f"Error getting recent memory: {e}")
        return []


async def get_long_memory(channel_id: int) -> List[Dict]:
    try:
        result = supabase.table('bot_long_memory')\
            .select('*')\
            .eq('channel_id', channel_id)\
            .gte('importance_score', 5)\
            .order('importance_score', desc=True)\
            .limit(20)\
            .execute()
        
        if result.data:
            ids = [m['id'] for m in result.data]
            supabase.table('bot_long_memory')\
                .update({'last_accessed': datetime.utcnow().isoformat()})\
                .in_('id', ids)\
                .execute()
        
        return result.data if result.data else []
    except Exception as e:
        print(f"Error getting long memory: {e}")
        return []


async def get_observations(channel_id: int, limit: int = 10) -> List[Dict]:
    try:
        cutoff = (datetime.utcnow() - timedelta(days=7)).isoformat()
        result = supabase.table('bot_observations')\
            .select('*')\
            .eq('channel_id', channel_id)\
            .gte('timestamp', cutoff)\
            .order('timestamp', desc=True)\
            .limit(limit)\
            .execute()
        return result.data if result.data else []
    except Exception as e:
        print(f"Error getting observations: {e}")
        return []


async def curate_memories(channel_id: int):
    try:
        cutoff = (datetime.utcnow() - timedelta(hours=12)).isoformat()
        old_memories = supabase.table('bot_short_memory')\
            .select('*')\
            .eq('channel_id', channel_id)\
            .lt('timestamp', cutoff)\
            .execute()
        
        if not old_memories.data:
            return
        
        memory_text = "\n".join([
            f"User {m['username']}: {m['message']}" + (f"\nBot: {m['response']}" if m['response'] else "")
            for m in old_memories.data[:20]
        ])
        
        prompt = f"""Review these conversation snippets and identify what to keep..."""
        
        response = gemini_model.generate_content(prompt)
        
        try:
            json_match = re.search(r'\{.*\}', response.text, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                for memory in data.get('memories', []):
                    supabase.table('bot_long_memory').insert({
                        'channel_id': channel_id,
                        'memory_type': memory['type'],
                        'content': memory['content'],
                        'importance_score': memory['importance'],
                        'context': memory.get('context'),
                        'created_at': datetime.utcnow().isoformat()
                    }).execute()
        except json.JSONDecodeError:
            print("Could not parse AI memory curation response")
        
        supabase.table('bot_short_memory')\
            .delete()\
            .eq('channel_id', channel_id)\
            .lt('timestamp', cutoff)\
            .execute()
        
    except Exception as e:
        print(f"Error curating memories: {e}")


async def generate_response(message: discord.Message, user_message: str) -> str:
    try:
        channel_id = message.channel.id
        recent_memory = await get_recent_memory(channel_id)
        long_memory = await get_long_memory(channel_id)
        observations = await get_observations(channel_id)
        
        context_parts = [SYSTEM_PROMPT]
        
        if long_memory:
            memory_text = "\n".join([f"- {m['content']}" for m in long_memory[:10]])
            context_parts.append(f"\n\nIMPORTANT THINGS YOU REMEMBER:\n{memory_text}")
        
        if observations:
            obs_text = "\n".join([f"- {o['observation']}" for o in observations[:5]])
            context_parts.append(f"\n\nTHINGS YOU'VE NOTICED:\n{obs_text}")
        
        if recent_memory:
            recent_text = "\n".join([
                f"{m['username']}: {m['message']}" + (f"\nYou: {m['response']}" if m['response'] else "")
                for m in reversed(recent_memory[:10])
            ])
            context_parts.append(f"\n\nRECENT CONVERSATION:\n{recent_text}")
        
        context_parts.append(f"\n\nCurrent message from {message.author.name}: {user_message}")
        
        full_prompt = "\n".join(context_parts)
        
        response = gemini_model.generate_content(full_prompt)
        bot_response = response.text.strip()
        
        await save_short_memory(
            channel_id=channel_id,
            user_id=message.author.id,
            username=message.author.name,
            message=user_message,
            response=bot_response,
            is_pinged=True
        )
        
        return bot_response
        
    except Exception as e:
        print(f"Error generating response: {e}")
        return "yo my brain just glitched, try again?"


@bot.command(name='remember')
async def remember(ctx, *, fact: str):
    try:
        supabase.table('bot_long_memory').insert({
            'channel_id': ctx.channel.id,
            'memory_type': 'fact',
            'content': fact,
            'importance_score': 8,
            'context': f"Manually saved by {ctx.author.name}",
            'created_at': datetime.utcnow().isoformat()
        }).execute()
        await ctx.reply("got it, locked that in my long-term memory")
    except Exception as e:
        await ctx.reply("couldn't save that, my memory banks are glitching")


@bot.command(name='memories')
async def show_memories(ctx):
    long_mem = await get_long_memory(ctx.channel.id)
    if not long_mem:
        await ctx.reply("my mind is blank for this channel... we gotta make some memories")
        return
    memory_list = "\n".join([
        f"• {m['content']} (importance: {m['importance_score']}/10)"
        for m in long_mem[:10]
    ])
    embed = discord.Embed(
        title="what i remember about this channel",
        description=memory_list,
        color=discord.Color.blue()
    )
    await ctx.reply(embed=embed)


@bot.command(name='forget')
async def forget(ctx):
    try:
        supabase.table('bot_short_memory').delete().eq('channel_id', ctx.channel.id).execute()
        supabase.table('bot_long_memory').delete().eq('channel_id', ctx.channel.id).execute()
        supabase.table('bot_observations').delete().eq('channel_id', ctx.channel.id).execute()
        await ctx.reply("memories wiped, who are you people again?")
    except:
        await ctx.reply("error wiping memories, they're stuck in my head")
