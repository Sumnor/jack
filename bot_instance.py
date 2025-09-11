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
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)
bot_key = os.getenv("Key")
YT_Key = os.getenv("YT_Key")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
API_KEY = os.getenv("API_KEY")
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
    sig = inspect.signature(app_command_func)

    async def wrapper(ctx, *args, **kwargs):
        fake = FakeInteraction(ctx)

        is_prefix = ctx.message.content.strip().startswith("!")

        if is_prefix:
            disclaimer = (
                "⚠️ **Note:** You're using the `!` version of this command.\n"
                "Slash commands (`/`) are **preferred** because they autocomplete arguments.\n\n"
                "For optional arguments with `!`, you can:\n"
                "• Use `-<first_letter>` to skip others, e.g. `-f 100k`\n"
                "• If multiple params share the same letter, use `-f1`, `-f2`, etc."
            )
            await ctx.send(disclaimer)

        params = [p.name for p in sig.parameters.values() if p.name != "interaction"]

        parsed_kwargs = {}
        dup_counters = {}

        for idx, raw in enumerate(args):
            if idx >= len(params):
                break
            if not str(raw).startswith("-"):
                parsed_kwargs[params[idx]] = await resolve_arg(ctx, raw)

        i = 0
        while i < len(args):
            raw = str(args[i])

            if raw.startswith("-"):
                flag_match = re.match(r"^-([a-z])(\d+)?$", raw, re.I)
                if flag_match:
                    flag, num = flag_match.groups()
                    flag = flag.lower()

                    match = next((p for p in params if p[0].lower() == flag), None)

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

        parsed_kwargs["_called_with_prefix"] = is_prefix
        kwargs.update(parsed_kwargs)
        return await app_command_func(fake, **kwargs)

    return wrapper
