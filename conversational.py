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

# -----------------------
# Gemini Setup (v2.5)
# -----------------------
genai.configure(api_key=GEMINI_API_KEY)

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
    model_name="gemini-2.5-flash",  # or "gemini-2.5-pro"
    generation_config=generation_config,
    safety_settings=safety_settings
)

# -----------------------
# Supabase Setup (NO /rest/v1 in URL!)
# -----------------------
supabase: Client = create_client(
    SUPABASE_URL,  # should just be https://xxxx.supabase.co
    SUPABASE_KEY
)

# -----------------------
# System Prompt
# -----------------------
SYSTEM_PROMPT = """You are a quirky, chill Discord bot assistant with personality. Here's how you should act:

[... your system prompt here ...]
"""

# -----------------------
# Utils
# -----------------------
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

# -----------------------
# Memory Functions
# -----------------------
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

# -----------------------
# AI Response
# -----------------------
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

        # Handle response consistently with new SDK
        bot_response = ""
        if hasattr(response, "text") and response.text:
            bot_response = response.text.strip()
        elif hasattr(response, "candidates") and response.candidates:
            bot_response = response.candidates[0].content.parts[0].text.strip()
        else:
            bot_response = "uhh i spaced out, say that again?"

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

# -----------------------
# Discord Events
# -----------------------
@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    if message.guild is not None:
        channel_id = message.channel.id
        bot_mentioned = bot.user in message.mentions

        if not bot_mentioned and len(message.content) > 20:
            if any(keyword in message.content.lower() for keyword in ['important', 'remember', 'note', 'document', 'announcement']):
                await save_observation(channel_id, message.content, context=f"Posted by {message.author.name}")
            await bot.process_commands(message)
            return

        if bot_mentioned:
            if not is_message_targeting_bot(message.content, bot_mentioned, bot.user):
                await message.reply(get_funny_comeback())
                await bot.process_commands(message)
                return

            content = message.content
            for mention in message.mentions:
                content = content.replace(f'<@{mention.id}>', '').replace(f'<@!{mention.id}>', '')
            content = content.strip()

            if not content:
                await message.reply("yeah?")
                await bot.process_commands(message)
                return

            async with message.channel.typing():
                response = await generate_response(message, content)
                if len(response) > 2000:
                    chunks = [response[i:i+2000] for i in range(0, len(response), 2000)]
                    for chunk in chunks:
                        await message.reply(chunk)
                else:
                    await message.reply(response)

            await bot.process_commands(message)
            return

    await bot.process_commands(message)

# -----------------------
# Background Tasks
# -----------------------
'''@tasks.loop(hours=6)
async def cleanup_old_memories():
    try:
        cutoff = (datetime.utcnow() - timedelta(hours=24)).isoformat()
        supabase.table('bot_short_memory').delete().lt('timestamp', cutoff).execute()
        print("Cleaned up old short-term memories")
    except Exception as e:
        print(f"Error cleaning up memories: {e}")


@tasks.loop(hours=12)
async def curate_memories_task():
    try:
        result = supabase.table('bot_short_memory').select('channel_id').execute()
        if not result.data:
            return
        channels = set(m['channel_id'] for m in result.data)
        for channel_id in channels:
            await curate_memories(channel_id)
        print(f"Curated memories for {len(channels)} channels")
    except Exception as e:
        print(f"Error in memory curation task: {e}")'''

# -----------------------
# Commands
# -----------------------
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
