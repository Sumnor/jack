import discord
from discord import app_commands
from settings.bot_instance import bot, wrap_as_prefix_command
from settings.initializer_functions.supabase_initializer import supabase

@bot.tree.command(name="register_server_aa", description="Register this server and create database tables")
@app_commands.checks.has_permissions(administrator=True)
async def register_server_aa(interaction: discord.Interaction):
    await interaction.response.defer()
    guild = interaction.guild
    if guild is None:
        await interaction.followup.send("This command can only be used in a guild.", ephemeral=True)
        return

    server_id = str(guild.id)

    try:
        supabase.select('alliance_snapshots', filters={'guild_id': server_id})
        print(f"✅ Alliance snapshots table accessible for guild {server_id}")
        
        supabase.select('auto_requests', filters={'guild_id': server_id})
        print(f"✅ Auto requests table accessible for guild {server_id}")
        
        test_data = {
            'guild_id': server_id,
            'total_money': 0,
            'money': 0,
            'food': 0,
            'gasoline': 0,
            'munitions': 0,
            'steel': 0,
            'aluminum': 0,
            'bauxite': 0,
            'lead': 0,
            'iron': 0,
            'oil': 0,
            'coal': 0,
            'uranium': 0
        }
        
        result = supabase.insert('alliance_snapshots', test_data)
        if result:
            supabase._make_request('DELETE', f"alliance_snapshots?guild_id=eq.{server_id}&total_money=eq.0")
            print(f"✅ Write test successful for guild {server_id}")

        await interaction.followup.send(
            f"✅ Database ready for server **{guild.name}**!\n"
            f"- Alliance snapshots: Ready for guild `{server_id}`\n"
            f"- Auto requests: Ready for guild `{server_id}`"
        )

    except Exception as e:
        await interaction.followup.send(f"❌ Failed to verify database setup: {e}")

bot.command(name="register_server_aa")(wrap_as_prefix_command(register_server_aa.callback))