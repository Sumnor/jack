import discord
from bot_instance import bot, wrap_as_prefix_command
from utils import get_prices, supabase
from settings_multi import get_member_role

@bot.tree.command(name="see_report", description="See the WC of other nations (may be wrong, idk nor care)")
async def see_report(interaction: discord.Interaction, nation: str):
    await interaction.response.defer(thinking=True)
    MEMBER_ROLE = get_member_role(interaction)
    
    async def is_banker(interaction):
        return (
            any(role.name == MEMBER_ROLE for role in interaction.user.roles)
            or str(interaction.user.id) == "1148678095176474678"
        )

    if not await is_banker(interaction):
        await interaction.followup.send("❌ You need to be a Member to use this command")
        return

    try:
        guild_id = str(interaction.guild.id)
        

        records = supabase.select('nation_reports', filters={'nation_name': nation.lower()})
        prices = get_prices()
        
        resource_prices = {
            item["resource"]: float(item["average_price"])
            for item in prices["data"]["top_trade_info"]["resources"]
        }

        if not records:
            await interaction.followup.send(f"❌ No report found for `{nation}`.")
            return


        match = max(records, key=lambda x: x.get('timestamp', ''))
        
        timestamp = match.get("timestamp", "Unknown time")
        nation_name = match.get("nation_name", nation)

        embed = discord.Embed(
            title=f"🕵️ WC Report: {nation_name}",
            description=f"Report as of `{timestamp}`",
            color=discord.Color.blue()
        )

        total_value = 0.0


        resource_fields = {
            'money': 'Money',
            'coal': 'Coal', 
            'oil': 'Oil',
            'uranium': 'Uranium',
            'lead': 'Lead',
            'iron': 'Iron',
            'bauxite': 'Bauxite',
            'gasoline': 'Gasoline',
            'munitions': 'Munitions',
            'steel': 'Steel',
            'aluminum': 'Aluminum',
            'food': 'Food'
        }

        for db_key, display_name in resource_fields.items():
            value = match.get(db_key, 0)
            if value is None:
                continue
                
            try:
                val = float(value)
            except (ValueError, TypeError):
                embed.add_field(name=display_name, value=str(value), inline=True)
                continue

            if db_key in resource_prices:
                resource_value = val * resource_prices[db_key]
                total_value += resource_value
                embed.add_field(
                    name=display_name,
                    value=f"{val:,.2f} @ {resource_prices[db_key]:,.2f}",
                    inline=True
                )
            elif db_key == "money":
                total_value += val
                embed.add_field(name="Money", value=f"{val:,.2f}", inline=True)
            else:
                embed.add_field(name=display_name, value=f"{val:,.2f}", inline=True)


        estimated_loot = total_value * 0.14
        embed.add_field(name="💰 Estimated Loot (14%)", value=f"{estimated_loot:,.2f}", inline=False)

        embed.set_footer(text=f"Last update: {timestamp}")

        await interaction.followup.send(embed=embed)

    except Exception as e:
        print(f"Error in see_report: {e}")
        await interaction.followup.send("❌ An error occurred while fetching the report.")

bot.command(name="see_report")(wrap_as_prefix_command(see_report.callback))

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