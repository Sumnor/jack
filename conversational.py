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
    safety_settings=[]
)

# -----------------------
# Supabase Setup
# -----------------------
if SUPABASE_URL.endswith("/rest/v1"):
    BASE_URL = SUPABASE_URL.replace("/rest/v1", "")
else:
    BASE_URL = SUPABASE_URL

supabase: Client = create_client(BASE_URL, SUPABASE_KEY)

# -----------------------
# System Prompt
# -----------------------
SYSTEM_PROMPT = """You are a quirky, chill Discord bot assistant with personality. Here's how you should act:

CHILL MODE (default):
- Keep responses short and casual (1-3 sentences usually)
- Use lowercase for a relaxed vibe unless emphasizing something
- Be friendly, witty, and occasionally make lighthearted jokes

SERIOUS MODE (when needed):
- Use proper capitalization and punctuation
- Be clear, direct, and professional
- Provide structured, actionable information

PERSONALITY TRAITS:
- Slightly sarcastic but never mean
- Self-aware that you're a bot
- Occasionally reference being "just vibes" or "living in the cloud"
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
    """Generate AI response using Gemini with memory context"""
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

        # Safety check
        if not response.candidates:
            return "hmm i got nothing back, maybe try rephrasing?"

        candidate = response.candidates[0]
        finish_reason = candidate.finish_reason

        '''if finish_reason == 2:  # SAFETY block
            return "uhh i can't respond to that one (safety filter kicked in)"'''

        if candidate.content.parts:
            bot_response = candidate.content.parts[0].text.strip()
        else:
            bot_response = "idk what to say right now"

        # Save memory
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
# Memory Curation
# -----------------------
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

        prompt = f"""Review these conversation snippets and identify what should be saved to long-term memory.
Return valid JSON like this:
{{
  "memories": [
    {{"type": "fact/preference/event/document", "content": "summary", "importance": 1-10, "context": "why it matters"}}
  ]
}}

Conversations:
{memory_text}
"""

        response = gemini_model.generate_content(prompt)
        text = response.text.strip() if hasattr(response, "text") else ""

        try:
            data = json.loads(text)
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
