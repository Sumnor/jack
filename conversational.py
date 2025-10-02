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
from google.generativeai.types import HarmCategory, HarmBlockThreshold

safety_settings = {
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
}

gemini_model = genai.GenerativeModel(
    model_name="gemini-2.5-flash",
    generation_config=generation_config,
    safety_settings=safety_settings
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
You can save files, PDFs, and links when users ask you to remember them.

MEMORY RULES:
- When a user says "remember this" or "save this" with a file/link, save it to your knowledge base
- You can retrieve saved files/links when asked
- If you don't know what to say, still reply casually (never stay silent)

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
                    return text[:5000]
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
            return None

    except Exception as e:
        return f"Error reading file {attachment.filename}: {e}"
    finally:
        try:
            os.unlink(filepath)
        except:
            pass


async def save_file_to_knowledge(guild_id: int, channel_id: int, user_id: int, username: str, 
                                  content: str, file_type: str, filename: str = None, url: str = None):
    """Save files/links to knowledge base"""
    try:
        supabase.table('bot_knowledge').insert({
            'guild_id': guild_id,
            'channel_id': channel_id,
            'user_id': user_id,
            'username': username,
            'content': content,
            'file_type': file_type,
            'filename': filename,
            'url': url,
            'timestamp': datetime.utcnow().isoformat()
        }).execute()
        return True
    except Exception as e:
        print(f"Error saving to knowledge base: {e}")
        return False


async def search_knowledge(guild_id: int, query: str = None) -> List[Dict]:
    """Search saved files/links"""
    try:
        if query:
            result = supabase.table('bot_knowledge')\
                .select('*')\
                .eq('guild_id', guild_id)\
                .ilike('content', f'%{query}%')\
                .order('timestamp', desc=True)\
                .limit(10)\
                .execute()
        else:
            result = supabase.table('bot_knowledge')\
                .select('*')\
                .eq('guild_id', guild_id)\
                .order('timestamp', desc=True)\
                .limit(10)\
                .execute()
        return result.data if result.data else []
    except Exception as e:
        print(f"Error searching knowledge: {e}")
        return []

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
    """Fetch last N messages from a channel"""
    try:
        messages = await channel.history(limit=limit).flatten()
        result = []
        for msg in reversed(messages):
            result.append({
                'username': msg.author.name,
                'message': msg.content
            })
        return result
    except Exception as e:
        print(f"Error fetching recent messages: {e}")
        return []

# -----------------------
# AI Response (Updated)
# -----------------------
async def generate_response(message: discord.Message, user_message: str) -> str:
    """Generate AI response using Gemini"""
    try:
        channel_id = message.channel.id
        guild_id = message.guild.id if message.guild else 0

        # Check if user wants to save something
        save_triggers = ["remember this", "save this", "store this", "keep this"]
        should_save = any(trigger in user_message.lower() for trigger in save_triggers)

        # Get last 10 messages for context
        recent_messages = await get_recent_messages(message.channel, limit=10)

        context_parts = [SYSTEM_PROMPT]

        # Add recent conversation
        if recent_messages:
            recent_text = "\n".join([f"{m['username']}: {m['message']}" for m in recent_messages[-10:]])
            context_parts.append(f"\n\nRECENT CONVERSATION:\n{recent_text}")

        # Handle URLs
        url_matches = re.findall(r'https?://\S+', user_message)
        saved_items = []
        
        if url_matches and should_save:
            for url in url_matches[:3]:
                page_content = await fetch_url(url)
                saved = await save_file_to_knowledge(
                    guild_id=guild_id,
                    channel_id=channel_id,
                    user_id=message.author.id,
                    username=message.author.name,
                    content=page_content,
                    file_type='url',
                    url=url
                )
                if saved:
                    saved_items.append(f"link: {url}")
        
        # Handle file attachments
        if message.attachments and should_save:
            for att in message.attachments[:3]:
                if att.filename.endswith(('.pdf', '.docx', '.txt')):
                    file_content = await read_attachment(att)
                    if file_content and not file_content.startswith("Error"):
                        saved = await save_file_to_knowledge(
                            guild_id=guild_id,
                            channel_id=channel_id,
                            user_id=message.author.id,
                            username=message.author.name,
                            content=file_content,
                            file_type=att.filename.split('.')[-1],
                            filename=att.filename
                        )
                        if saved:
                            saved_items.append(f"file: {att.filename}")

        # If saving was requested, return confirmation
        if should_save and saved_items:
            return f"done! saved: {', '.join(saved_items)}"

        # Check if user is asking for saved info
        search_triggers = ["what did i save", "show me", "find", "do you have", "remember when"]
        is_searching = any(trigger in user_message.lower() for trigger in search_triggers)

        if is_searching:
            knowledge = await search_knowledge(guild_id)
            if knowledge:
                context_parts.append("\n\nSAVED KNOWLEDGE BASE:")
                for item in knowledge[:5]:
                    if item['file_type'] == 'url':
                        context_parts.append(f"- Link: {item['url']}")
                        context_parts.append(f"  Content preview: {item['content'][:200]}...")
                    else:
                        context_parts.append(f"- File: {item['filename']}")
                        context_parts.append(f"  Content preview: {item['content'][:200]}...")

        # Add current message
        context_parts.append(f"\n\nCurrent message from {message.author.name}: {user_message}")

        # Add attachments for reading (not saving)
        if message.attachments and not should_save:
            for att in message.attachments[:2]:
                file_content = await read_attachment(att)
                if file_content:
                    context_parts.append(f"\n\nCONTENT FROM FILE {att.filename}:\n{file_content}")

        full_prompt = "\n".join(context_parts)

        # Run Gemini
        loop = asyncio.get_event_loop()
        
        try:
            response = await loop.run_in_executor(None, lambda: gemini_model.generate_content(full_prompt))
            
            # Try multiple ways to extract text
            bot_response = None
            
            # Method 1: Direct text attribute
            if hasattr(response, "text"):
                try:
                    bot_response = response.text.strip()
                except:
                    pass
            
            # Method 2: Through candidates
            if not bot_response and hasattr(response, 'candidates') and response.candidates:
                try:
                    if response.candidates[0].content.parts:
                        bot_response = response.candidates[0].content.parts[0].text.strip()
                except:
                    pass
            
            # Method 3: Check if blocked by safety
            if not bot_response:
                if hasattr(response, 'prompt_feedback'):
                    print(f"Prompt feedback: {response.prompt_feedback}")
                if hasattr(response, 'candidates') and response.candidates:
                    print(f"Finish reason: {response.candidates[0].finish_reason}")
                    print(f"Safety ratings: {response.candidates[0].safety_ratings}")
                
                # Fallback response
                bot_response = "can't respond to that one chief, my filters are acting up 🤷"
            
        except Exception as gemini_error:
            print(f"Gemini API Error: {gemini_error}")
            bot_response = "gemini's having a moment, give me a sec"

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
        print(f"Error type: {type(e)}")
        import traceback
        traceback.print_exc()
        return "yo my brain just glitched, try again?"
