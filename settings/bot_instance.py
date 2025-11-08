import discord
import re
from discord.ext import commands
import inspect
import json
from dotenv import load_dotenv
import os

load_dotenv("cred.env")
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="<@1367997847978377247> !", intents=intents, help_command=None)
bot_key = os.getenv("Key")
YT_Key = os.getenv("YT_Key")
SUPABASE_URL = os.getenv("SUPABASE_URL")
WHITEKEY = os.getenv("WHITEKEY")
SUPABASE_URL_DATA = os.getenv("SUPABASE_URL_DATA")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_KEY_DATA = os.getenv("SUPABASE_KEY_DATA")
API_KEY = os.getenv("API_KEY")
BOT_KEY = os.getenv("BOT_KEY")
commandscalled = {"_global": 0}
snapshots_file = "snapshots.json"
money_snapshots = []

if os.path.exists(snapshots_file):
    with open(snapshots_file, "r") as f:
        money_snapshots = json.load(f)

class FakeInteraction:
    def __init__(self, ctx):
        self._ctx = ctx
        self.user = ctx.author
        self.guild = ctx.guild
        self.channel = ctx.channel
        self.message = ctx.message
        self.id = ctx.message.id

        self.response = self.Response(self)
        self.followup = self.Followup(self)

    @property
    def guild_id(self):
        return self.guild.id if self.guild else None

    class Response:
        def __init__(self, outer):
            self.outer = outer

        async def defer(self, ephemeral=False):
            pass

        async def send_message(self, content=None, **kwargs):
            msg = await self.outer._ctx.send(content, **kwargs)
            self.outer.message = msg
            return msg

    class Followup:
        def __init__(self, outer):
            self.outer = outer

        async def send(self, content=None, **kwargs):
            msg = await self.outer._ctx.send(content, **kwargs)
            self.outer.message = msg
            return msg

    async def edit_original_response(self, **kwargs):
        if self.message:
            return await self.message.edit(**kwargs)

    async def delete_original_response(self):
        if self.message:
            return await self.message.delete()

async def resolve_arg(ctx, arg):
    if isinstance(arg, str):
        match = re.match(r"<@!?(\d+)>", arg)
        if match:
            user_id = int(match.group(1))
            member = ctx.guild.get_member(user_id) if ctx.guild else None
            if member:
                return member
            try:
                return await ctx.bot.fetch_user(user_id)
            except discord.NotFound:
                return arg
        if arg.isdigit():
            try:
                return await ctx.bot.fetch_user(int(arg))
            except discord.NotFound:
                return arg
    return arg

def wrap_as_prefix_command(app_command_func):
    original_signature = inspect.signature(app_command_func)
    has_custom_param = '_called_with_prefix' in original_signature.parameters
    can_accept_kwargs = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in original_signature.parameters.values())

    async def wrapper(ctx, *args, **kwargs):
        fake = FakeInteraction(ctx)
        is_prefix = ctx.message.content.strip().startswith("<@1367997847978377247> !")
        params_to_parse = [p.name for p in original_signature.parameters.values() if p.name != "interaction"]
        parsed_kwargs = {}
        dup_counters = {}

        for idx, raw in enumerate(args):
            if idx >= len(params_to_parse):
                break
            if not str(raw).startswith("-"):
                parsed_kwargs[params_to_parse[idx]] = await resolve_arg(ctx, raw)

        i = 0
        while i < len(args):
            raw = str(args[i])
            if raw.startswith("-"):
                flag_match = re.match(r"^-([a-z])(\d+)?$", raw, re.I)
                if flag_match:
                    flag, num = flag_match.groups()
                    flag = flag.lower()
                    match = next((p for p in params_to_parse if p[0].lower() == flag), None)
                    if match:
                        key = match
                        if num:
                            key = f"{match}{num}"
                        elif key in parsed_kwargs:
                            dup_counters[key] = dup_counters.get(key, 1) + 1
                            key = f"{match}{dup_counters[key]}"

                        if i + 1 < len(args) and not str(args[i + 1]).startswith("-"):
                            parsed_kwargs[key] = await resolve_arg(ctx, args[i + 1])
                            i += 1
                        else:
                            parsed_kwargs[key] = "1"
            i += 1
            
        if has_custom_param or can_accept_kwargs:
            kwargs['_called_with_prefix'] = is_prefix
        
        kwargs.update(parsed_kwargs)
        return await app_command_func(fake, **kwargs)

    return wrapper
