import discord
from settings.bot_instance import bot, wrap_as_prefix_command
from settings.initializer_functions.supabase_initializer import supabase

@bot.tree.command(name="list_reports", description="See which nations have spy reports stored.")
async def list_reports(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True)

    try:

        records = supabase.select('nation_reports', columns='nation_name')
        
        if not records:
            await interaction.followup.send("❌ No nation reports are currently stored.")
            return


        nation_names = sorted(set(record["nation_name"] for record in records if record.get("nation_name")))

        embed = discord.Embed(
            title="🗂️ Stored Spy Reports",
            description=f"Total Nations: `{len(nation_names)}`",
            color=discord.Color.green()
        )


        chunk_size = 20
        for i in range(0, len(nation_names), chunk_size):
            chunk = nation_names[i:i+chunk_size]
            embed.add_field(
                name=f"Nations {i+1}-{i+len(chunk)}", 
                value="\n".join(chunk), 
                inline=False
            )

        await interaction.followup.send(embed=embed)

    except Exception as e:
        print(f"Error in list_reports: {e}")
        await interaction.followup.send("❌ An error occurred while retrieving the nation list.")

bot.command(name="list_reports")(wrap_as_prefix_command(list_reports.callback))