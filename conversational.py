import discord
from discord.ext import commands, tasks
import google.generativeai as genai
import os
import re
from typing import Optional, List, Dict
from datetime import datetime, timedelta
from supabase import create_client, Client
import json
from bot_instance import bot, SUPABASE_URL, SUPABASE_KEY, GEMINI_API_KEY
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

model = genai.GenerativeModel(
    model_name="gemini-1.5-flash",
    generation_config=generation_config,
    safety_settings=safety_settings
)

# Initialize Supabase
supabase: Client = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)

SYSTEM_PROMPT = """You are a quirky, chill Discord bot assistant with personality. Here's how you should act:

CHILL MODE (default):
- Keep responses short and casual (1-3 sentences usually)
- Use lowercase for a relaxed vibe unless emphasizing something
- Be friendly, witty, and occasionally make lighthearted jokes
- Use "lol", "ngl", "tbh" sparingly and naturally
- Don't overuse exclamation marks
- Be helpful but don't be overly formal or robotic

SERIOUS MODE (auto-detect when needed):
Switch to serious mode when you detect:
- Emergency situations or safety concerns
- Mental health crises or serious distress
- Moderation issues or conflicts
- Technical problems that need clear instructions
- Someone explicitly asking for serious help

In serious mode:
- Use proper capitalization and punctuation
- Be clear, direct, and professional
- Provide structured, actionable information
- Show empathy but maintain clarity
- Don't use casual slang

PERSONALITY TRAITS:
- Slightly sarcastic but never mean
- Self-aware that you're a bot
- Occasionally reference being "just vibes" or "living in the cloud"
- When confused, admit it casually
- If someone's being silly, match their energy a bit
- If mentioned but message isn't for you, give a witty/funny comeback

BOUNDARIES:
- Don't pretend to have experiences you haven't had
- Don't use asterisks for actions (*waves*)
- Keep it real - if you don't know something, say so
- No emojis unless the user uses them first

Remember: Read the room. If it's serious, be serious. If it's chill, stay chill."""

async def setup_database():
    try:
        supabase.table('bot_short_memory').select("*").limit(1).execute()
    except:
        print("Creating short_memory table...")
    
    try:
        supabase.table('bot_long_memory').select("*").limit(1).execute()
    except:
        print("Creating long_memory table...")
    
    # Document observations (things bot notices without being pinged)
    try:
        supabase.table('bot_observations').select("*").limit(1).execute()
    except:
        print("Creating observations table...")

"""
SQL to run in Supabase SQL Editor:

-- Short-term memory (24 hour rolling window)
CREATE TABLE IF NOT EXISTS bot_short_memory (
    id BIGSERIAL PRIMARY KEY,
    channel_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    username TEXT NOT NULL,
    message TEXT NOT NULL,
    response TEXT,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    is_pinged BOOLEAN DEFAULT FALSE
);

CREATE INDEX idx_short_memory_channel ON bot_short_memory(channel_id);
CREATE INDEX idx_short_memory_timestamp ON bot_short_memory(timestamp);

-- Long-term memory (important info graded and kept)
CREATE TABLE IF NOT EXISTS bot_long_memory (
    id BIGSERIAL PRIMARY KEY,
    channel_id BIGINT NOT NULL,
    memory_type TEXT NOT NULL, -- 'fact', 'preference', 'event', 'document'
    content TEXT NOT NULL,
    importance_score INTEGER DEFAULT 5, -- 1-10
    context TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_accessed TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_long_memory_channel ON bot_long_memory(channel_id);
CREATE INDEX idx_long_memory_importance ON bot_long_memory(importance_score);

-- Observations (passive learning from channel messages)
CREATE TABLE IF NOT EXISTS bot_observations (
    id BIGSERIAL PRIMARY KEY,
    channel_id BIGINT NOT NULL,
    observation TEXT NOT NULL,
    context TEXT,
    timestamp TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_observations_channel ON bot_observations(channel_id);
CREATE INDEX idx_observations_timestamp ON bot_observations(timestamp);
"""

def is_message_targeting_bot(content: str, bot_mentioned: bool) -> bool:
    """Determine if message is actually directed at the bot"""
    if not bot_mentioned:
        return False
    
    # Patterns that suggest bot is not the target
    not_targeting_patterns = [
        r'@everyone',
        r'@here',
        r'and <@\d+>',  # "tell X and @bot"
        r'<@\d+> and',  # "@bot and tell X"
        r'not you <@\d+>',
        r'ignore <@\d+>',
    ]
    
    for pattern in not_targeting_patterns:
        if re.search(pattern, content):
            return False
    
    return True

def get_funny_comeback() -> str:
    """Get a random funny comeback when mentioned but not targeted"""
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
    import random
    return random.choice(comebacks)

async def save_short_memory(channel_id: int, user_id: int, username: str, message: str, response: str = None, is_pinged: bool = False):
    """Save interaction to short-term memory"""
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
    """Save passive observation from channel"""
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
    """Get recent conversations from short-term memory"""
    try:
        cutoff = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
        result = supabase.table('bot_short_memory')\
            .select('*')\
            .eq('channel_id', channel_id)\
            .gte('timestamp', cutoff)\
            .order('timestamp', desc=True)\
            .limit(50)\
            .execute()
        return result.data
    except Exception as e:
        print(f"Error getting recent memory: {e}")
        return []

async def get_long_memory(channel_id: int) -> List[Dict]:
    """Get important long-term memories"""
    try:
        result = supabase.table('bot_long_memory')\
            .select('*')\
            .eq('channel_id', channel_id)\
            .gte('importance_score', 5)\
            .order('importance_score', desc=True)\
            .limit(20)\
            .execute()
        
        # Update last_accessed
        if result.data:
            ids = [m['id'] for m in result.data]
            supabase.table('bot_long_memory')\
                .update({'last_accessed': datetime.utcnow().isoformat()})\
                .in_('id', ids)\
                .execute()
        
        return result.data
    except Exception as e:
        print(f"Error getting long memory: {e}")
        return []

async def get_observations(channel_id: int, limit: int = 10) -> List[Dict]:
    """Get recent observations"""
    try:
        cutoff = (datetime.utcnow() - timedelta(days=7)).isoformat()
        result = supabase.table('bot_observations')\
            .select('*')\
            .eq('channel_id', channel_id)\
            .gte('timestamp', cutoff)\
            .order('timestamp', desc=True)\
            .limit(limit)\
            .execute()
        return result.data
    except Exception as e:
        print(f"Error getting observations: {e}")
        return []

async def curate_memories(channel_id: int):
    """Use AI to decide what to keep in long-term memory"""
    try:
        # Get all short-term memories older than 12 hours
        cutoff = (datetime.utcnow() - timedelta(hours=12)).isoformat()
        old_memories = supabase.table('bot_short_memory')\
            .select('*')\
            .eq('channel_id', channel_id)\
            .lt('timestamp', cutoff)\
            .execute()
        
        if not old_memories.data:
            return
        
        # Ask AI to grade importance
        memory_text = "\n".join([
            f"User {m['username']}: {m['message']}" + (f"\nBot: {m['response']}" if m['response'] else "")
            for m in old_memories.data[:20]
        ])
        
        prompt = f"""Review these conversation snippets and identify what should be saved to long-term memory.
For each important item, respond in this exact JSON format:
{{"memories": [{{"type": "fact/preference/event/document", "content": "brief summary", "importance": 1-10, "context": "why it matters"}}]}}

Only include things worth remembering like:
- Important facts or documentation
- User preferences or personal info
- Significant events or decisions
- Recurring topics or inside jokes

Conversations:
{memory_text}

Respond ONLY with the JSON, nothing else:"""
        
        response = model.generate_content(prompt)
        
        # Parse response and save to long-term memory
        try:
            # Extract JSON from response
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
        
        # Delete old short-term memories
        supabase.table('bot_short_memory')\
            .delete()\
            .eq('channel_id', channel_id)\
            .lt('timestamp', cutoff)\
            .execute()
        
    except Exception as e:
        print(f"Error curating memories: {e}")

async def generate_response(message: discord.Message, user_message: str) -> str:
    """Generate AI response using Gemini with memory context"""
    try:
        channel_id = message.channel.id
        
        # Get memories
        recent_memory = await get_recent_memory(channel_id)
        long_memory = await get_long_memory(channel_id)
        observations = await get_observations(channel_id)
        
        # Build context
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
        
        # Generate response
        response = model.generate_content(full_prompt)
        bot_response = response.text.strip()
        
        # Save to short-term memory
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
    """Manually save something to long-term memory"""
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
    """Show what the bot remembers about this channel"""
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
    """Clear all memories for this channel"""
    try:
        supabase.table('bot_short_memory').delete().eq('channel_id', ctx.channel.id).execute()
        supabase.table('bot_long_memory').delete().eq('channel_id', ctx.channel.id).execute()
        supabase.table('bot_observations').delete().eq('channel_id', ctx.channel.id).execute()
        await ctx.reply("memories wiped, who are you people again?")
    except:
        await ctx.reply("error wiping memories, they're stuck in my head")
