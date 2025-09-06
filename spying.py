import discord
from bot_instance import bot
from utils import get_prices, get_sheet_s
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
        sheet = get_sheet_s("Nation WC")
        rows = sheet.get_all_records()
        prices = get_prices()
        
        
        resource_prices = {
            item["resource"]: float(item["average_price"])
            for item in prices["data"]["top_trade_info"]["resources"]
        }

        
        match = next((row for row in rows if row["Nation"].lower() == nation.lower()), None)

        if not match:
            await interaction.followup.send(f"❌ No report found for `{nation}`.")
            return

        timestamp = match.get("Timestamp", "Unknown time")
        last_update = match.get("Last update", None)

        embed = discord.Embed(
            title=f"🕵️ WC Report: {match['Nation']}",
            description=f"Report as of `{timestamp}`",
            color=discord.Color.blue()
        )

        total_value = 0.0

        for key, value in match.items():
            if key in ("Nation", "Timestamp", "Last update"):
                continue

            try:
                val = float(value.replace(",", "")) if isinstance(value, str) else float(value)
            except:
                embed.add_field(name=key.capitalize(), value=str(value), inline=True)
                continue

            
            if key in resource_prices:
                resource_value = val * resource_prices[key]
                total_value += resource_value
                embed.add_field(
                    name=key.capitalize(),
                    value=f"{val:,.2f} @ {resource_prices[key]:,.2f}",
                    inline=True
                )
            elif key.lower() == "money":
                total_value += val
                embed.add_field(name="Money", value=f"{val:,.2f}", inline=True)
            else:
                embed.add_field(name=key.capitalize(), value=f"{val:,.2f}", inline=True)

        
        estimated_loot = total_value * 0.14
        embed.add_field(name="💰 Estimated Loot (14%)", value=f"{estimated_loot:,.2f}", inline=False)

        
        if last_update:
            embed.set_footer(text=f"Last update: {last_update}")

        await interaction.followup.send(embed=embed)

    except Exception as e:
        print(f"Error in see_report: {e}")
        await interaction.followup.send("❌ An error occurred while fetching the report.")

@bot.tree.command(name="list_reports", description="See which nations have spy reports stored.")
async def list_reports(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True)

    try:
        sheet = get_sheet_s("Nation WC")
        rows = sheet.get_all_records()

        nation_names = sorted(set(row["Nation"] for row in rows if row.get("Nation")))

        if not nation_names:
            await interaction.followup.send("❌ No nation reports are currently stored.")
            return

        embed = discord.Embed(
            title="🗂️ Stored Spy Reports",
            description=f"Total Nations: `{len(nation_names)}`",
            color=discord.Color.green()
        )

        
        chunk_size = 20
        for i in range(0, len(nation_names), chunk_size):
            chunk = nation_names[i:i+chunk_size]
            embed.add_field(name=f"Nations {i+1}-{i+len(chunk)}", value="\n".join(chunk), inline=False)

        await interaction.followup.send(embed=embed)

    except Exception as e:
        print(f"Error in list_reports: {e}")
        await interaction.followup.send("❌ An error occurred while retrieving the nation list.")