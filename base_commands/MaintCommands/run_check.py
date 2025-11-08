import discord
import asyncio
from settings.initializer_functions.cached_users_initializer import supabase, load_sheet_data
from settings.bot_instance import bot, wrap_as_prefix_command
from databases.sql.data_puller import get_nations_data_sql_by_nation_id

@bot.tree.command(name="run_check", description="Manual update of members")
async def run_check_slash(interaction: discord.Interaction):
    await interaction.response.defer()
    guild_id = str(interaction.guild.id)

    try:
        all_users = supabase.select('users')
        
        if not all_users:
            await interaction.followup.send("❌ No users found in the database.")
            return

        updated_count = 0
        for user_record in all_users:
            nation_id = user_record.get("nation_id")
            if not nation_id:
                continue

            result = get_nations_data_sql_by_nation_id(nation_id)
            if result is None:
                print(f"Failed to retrieve data for nation {nation_id}")
                continue

            alliance_name = result.get("alliance_name")
            
            try:
                supabase.update('users', 
                    {'aa': alliance_name}, 
                    {'nation_id': nation_id}
                )
                print(f"Updated nation {nation_id} with AA: {alliance_name}")
                updated_count += 1
            except Exception as update_error:
                print(f"Failed to update nation {nation_id}: {update_error}")
            
            await asyncio.sleep(3)

        load_sheet_data()
        
        await interaction.followup.send(f"✅ Manual member update completed. Updated {updated_count} records.")

    except Exception as e:
        await interaction.followup.send(f"❌ Error during manual update: {e}")

bot.command(name="run_check")(wrap_as_prefix_command(run_check_slash.callback))

