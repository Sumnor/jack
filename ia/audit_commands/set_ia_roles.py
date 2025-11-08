import discord
import discord
from discord import app_commands
from settings.bot_instance import bot, wrap_as_prefix_command
from settings.initializer_functions.supabase_initializer import supabase
from settings.settings_multi import get_gov_role

def set_server_setting(server_id, key, value):
    try:
        server_id = str(server_id)
        key = key.strip().upper()
        existing = supabase.select('server_settings', filters={'server_id': server_id, 'key': key})
        
        if existing:
            supabase.update('server_settings', {'value': str(value)}, {'server_id': server_id, 'key': key})
        else:
            data = {
                'server_id': server_id,
                'key': key,
                'value': str(value)
            }
            supabase.insert('server_settings', data)
    except Exception as e:
        print(f"❌ Failed to set server setting: {e}")

SETTING_CHOICES = [
    app_commands.Choice(name="IA Head", value="IA Head"),
    app_commands.Choice(name="IA Staff", value="IA Staff"),
    app_commands.Choice(name="Quota Validation Lenght(Days, eg. 7 = 7 days)", value="Quota Due")
]

@bot.tree.command(name="set_internal_settings", description="Set IA server roles")
@app_commands.describe(key="The setting key", value="The value to store")
@app_commands.choices(key=SETTING_CHOICES)
async def set_ia_roles(interaction: discord.Interaction, key: app_commands.Choice[str], value: str):
    await interaction.response.defer(ephemeral=True)
    raw_value = value.strip()
    if raw_value.startswith("<@&") and raw_value.endswith(">"):
        role_id = int(raw_value.replace("<@&", "").replace(">", ""))
        role = interaction.guild.get_role(role_id)
        if role:
            value = role.id
        else:
            await interaction.followup.send(f"❌ Could not find role with ID `{role_id}`.", ephemeral=True)
            return
    elif raw_value.startswith("<#") and raw_value.endswith(">"):
        value = raw_value.replace("<#", "").replace(">", "")

    guild = interaction.guild
    guild_id = interaction.guild_id
    if guild is None or guild_id is None:
        await interaction.followup.send("❌ This command can only be used in a server.", ephemeral=True)
        return

    gov_role_id = get_gov_role(interaction)
    member = await guild.fetch_member(interaction.user.id)
    key_value = key.value if hasattr(key, "value") else key
    key_value = key_value.strip().lower()

    if gov_role_id is None:
        set_server_setting(guild_id, key_value, value)
        await interaction.followup.send(f"✅ {key_value} set to `{value}`.", ephemeral=True)
        return

    if not any(role.name == gov_role_id for role in member.roles):
        await interaction.followup.send("❌ You do not have permission to use this command. Only members with the GOV_ROLE can set settings.", ephemeral=True)
        return

    try:
        set_server_setting(guild_id, key_value, value)
        await interaction.followup.send(f"✅ `{key_value}` set to `{value}`.", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ Failed to set setting: {e}", ephemeral=True)

bot.command(name="set_internal_settings")(wrap_as_prefix_command(set_ia_roles.callback))