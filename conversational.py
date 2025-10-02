import discord
from discord.ext import commands, tasks
import google.generativeai as genai
import os
import re
import asyncio
from typing import Optional, List, Dict
from datetime import datetime, timedelta
from supabase import create_client, Client
import json
import random
from bot_instance import bot, SUPABASE_URL, SUPABASE_KEY, GEMINI_API_KEY

# New deps
import aiohttp
import tempfile
from PyPDF2 import PdfReader
from docx import Document

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

# safety disabled fully
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
SYSTEM_PROMPT = """You are Jack, a quirky, chill Discord bot assistant with personality.
You live in this Discord server and should always respond to users.
You can also save and recall memories when users tell you something important.

MEMORY RULES:
- If a user says something is a "core memory" or asks you to remember, treat it seriously and save it to long-term memory.
- If you don't know what to say, still reply casually (never stay silent).
- Never refuse safe roleplay or instructions unless they are truly harmful.

CHILL MODE (default):
- Keep responses short and casual (1-3 sentences usually)
- lowercase vibe unless emphasis
- witty, sarcastic, but never mean

SERIOUS MODE (when needed):
- clear, structured, professional
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
# Internet + File Handling
# -----------------------
async def fetch_url(url: str) -> str:
    """Fetch content from a URL (basic HTML/text)"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=15) as resp:
                if resp.status == 200:
                    text = await resp.text()
                    return text[:5000]  # limit length
                else:
                    return f"Failed to fetch {url}, status {resp.status}"
    except Exception as e:
        return f"Error fetching {url}: {e}"


async def read_attachment(attachment: discord.Attachment) -> str:
    """Download and parse supported file types"""
    try:
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            await attachment.save(tmp.name)
            filepath = tmp.name

        if attachment.filename.endswith(".txt"):
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()[:5000]

        elif attachment.filename.endswith(".pdf"):
            reader = PdfReader(filepath)
            text = ""
            for page in reader.pages[:10]:
                text += page.extract_text() or ""
            return text[:5000]

        elif attachment.filename.endswith(".docx"):
            doc = Document(filepath)
            text = "\n".join([p.text for p in doc.paragraphs])
            return text[:5000]

        else:
            return f"(can't read {attachment.filename}, unsupported type)"

    except Exception as e:
        return f"Error reading file {attachment.filename}: {e}"

# -----------------------
# Memory Functions
# -----------------------
async def save_short_memory(channel_id: int, user_id: int, username: str, message: str, response: str = None, is_pinged: bool = False):
    """Save short-term memory for a specific channel (max 1 hour)"""
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


async def get_recent_messages(channel: discord.TextChannel, limit: int = 10) -> List[Dict]:
    """Fetch last N messages from a channel (ignoring who sent them)"""
    try:
        messages = await channel.history(limit=limit).flatten()
        result = []
        for msg in reversed(messages):
            result.append({
                'username': msg.author.name,
                'message': msg.content,
                'response': None
            })
        return result
    except Exception as e:
        print(f"Error fetching recent messages: {e}")
        return []


async def get_long_memory() -> List[Dict]:
    """Get global long-term memory shared across all channels"""
    try:
        result = supabase.table('bot_long_memory')\
            .select('*')\
            .gte('importance_score', 5)\
            .order('importance_score', desc=True)\
            .limit(50)\
            .execute()
        return result.data if result.data else []
    except Exception as e:
        print(f"Error getting long memory: {e}")
        return []


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
# AI Response (Updated)
# -----------------------
async def generate_response(message: discord.Message, user_message: str) -> str:
    """Generate AI response using Gemini with last 10 messages as context when pinged"""
    try:
        channel_id = message.channel.id

        # Global long-term memory
        long_memory = await get_long_memory()

        # Last 10 messages in channel
        recent_memory = await get_recent_messages(message.channel, limit=10)

        context_parts = [SYSTEM_PROMPT]

        # Add long-term memory
        if long_memory:
            memory_text = "\n".join([f"- {m['content']}" for m in long_memory[:10]])
            context_parts.append(f"\n\nIMPORTANT THINGS YOU REMEMBER:\n{memory_text}")

        # Add last 10 messages in channel
        if recent_memory:
            recent_text = "\n".join([f"{m['username']}: {m['message']}" for m in recent_memory])
            context_parts.append(f"\n\nRECENT CONVERSATION:\n{recent_text}")

        context_parts.append(f"\n\nCurrent message from {message.author.name}: {user_message}")

        # 🔹 Internet fetch if URLs present
        url_match = re.findall(r'https?://\S+', user_message)
        if url_match:
            for url in url_match[:2]:
                page_content = await fetch_url(url)
                context_parts.append(f"\n\nCONTENT FROM {url}:\n{page_content}")

        # 🔹 File reading if attachments present
        if message.attachments:
            for att in message.attachments[:2]:
                file_text = await read_attachment(att)
                context_parts.append(f"\n\nCONTENT FROM FILE {att.filename}:\n{file_text}")

        full_prompt = "\n".join(context_parts)

        # Run Gemini
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, lambda: gemini_model.generate_content(full_prompt))

        bot_response = None
        if hasattr(response, "text") and response.text:
            bot_response = response.text.strip()
        elif response.candidates and response.candidates[0].content.parts:
            bot_response = response.candidates[0].content.parts[0].text.strip()
        else:
            bot_response = "ngl, i'm kinda blanking rn 😅"

        # 🔹 Auto-core-memory saving
        if "core memory" in user_message.lower():
            try:
                supabase.table('bot_long_memory').insert({
                    'channel_id': channel_id,
                    'memory_type': 'fact',
                    'content': user_message,
                    'importance_score': 10,
                    'context': f"Saved directly from {message.author.name}",
                    'created_at': datetime.utcnow().isoformat()
                }).execute()
                print(f"Saved core memory from {message.author.name}")
            except Exception as e:
                print(f"Error saving core memory: {e}")

        # Save short memory
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
