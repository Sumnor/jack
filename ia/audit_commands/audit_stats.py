import discord
from ia.audits_utils import get_audits
from settings.bot_instance import bot, wrap_as_prefix_command
from databases.sql.data_puller import supabase
from collections import Counter

@bot.tree.command(name="audits_stats", description="Show audit completion statistics")
async def audits_stats(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    
    records = get_audits(interaction.guild_id)
    if not records:
        await interaction.followup.send("❌ No audits found.", ephemeral=True)
        return
    
    total = len(records)
    wc_complete = sum(1 for r in records if r.get('wc_audit'))
    build_complete = sum(1 for r in records if r.get('build_audit'))
    tax_complete = sum(1 for r in records if r.get('tax_audit'))
    fully_complete = sum(
        1 for r in records 
        if r.get('wc_audit') and r.get('build_audit') and r.get('tax_audit')
    )
    
    embed = discord.Embed(
        title="📊 Audit Statistics",
        color=discord.Color.blue()
    )
    embed.add_field(name="Total Nations", value=str(total), inline=True)
    embed.add_field(name="Fully Complete", value=f"{fully_complete} ({fully_complete/total*100:.1f}%)", inline=True)
    embed.add_field(name="\u200b", value="\u200b", inline=True)
    
    embed.add_field(name="🌐 War Chest", value=f"{wc_complete}/{total} ({wc_complete/total*100:.1f}%)", inline=True)
    embed.add_field(name="🏗️ Build Audit", value=f"{build_complete}/{total} ({build_complete/total*100:.1f}%)", inline=True)
    embed.add_field(name="💰 Tax Audit", value=f"{tax_complete}/{total} ({tax_complete/total*100:.1f}%)", inline=True)

    auditor_stats = {}
    
    for r in records:
        wc_auditor = r.get("wc_auditor")
        if wc_auditor and wc_auditor != 0:
            if wc_auditor not in auditor_stats:
                auditor_stats[wc_auditor] = {"wc": 0, "build": 0, "tax": 0}
            if r.get("wc_audit"):
                auditor_stats[wc_auditor]["wc"] += 1
        
        build_auditor = r.get("build_auditor")
        if build_auditor and build_auditor != 0:
            if build_auditor not in auditor_stats:
                auditor_stats[build_auditor] = {"wc": 0, "build": 0, "tax": 0}
            if r.get("build_audit"):
                auditor_stats[build_auditor]["build"] += 1
        
        tax_auditor = r.get("tax_auditor")
        if tax_auditor and tax_auditor != 0:
            if tax_auditor not in auditor_stats:
                auditor_stats[tax_auditor] = {"wc": 0, "build": 0, "tax": 0}
            if r.get("tax_audit"):
                auditor_stats[tax_auditor]["tax"] += 1
    
    leaderboard_lines = []
    for auditor_id, stats in auditor_stats.items():
        try:
            quota_response = supabase.select(
                "auditor_quotas",
                filters={"guild_id": str(interaction.guild_id), "auditor_id": str(auditor_id)}
            )
            
            if isinstance(quota_response, dict):
                quota = quota_response.get('data', [])
            else:
                quota = quota_response
            
            total_completed = stats["wc"] + stats["build"] + stats["tax"]
            
            if quota and len(quota) > 0:
                assigned = quota[0].get("assigned", 0)
                percent = (total_completed / assigned * 100) if assigned > 0 else 0
                leaderboard_lines.append({
                    'auditor_id': auditor_id,
                    'total': total_completed,
                    'assigned': assigned,
                    'percent': percent,
                    'stats': stats
                })
            else:
                leaderboard_lines.append({
                    'auditor_id': auditor_id,
                    'total': total_completed,
                    'assigned': 0,
                    'percent': 0,
                    'stats': stats
                })
        except Exception as e:
            print(f"Error loading quota for {auditor_id}: {e}")
            total_completed = stats["wc"] + stats["build"] + stats["tax"]
            leaderboard_lines.append({
                'auditor_id': auditor_id,
                'total': total_completed,
                'assigned': 0,
                'percent': 0,
                'stats': stats
            })
    leaderboard_lines.sort(key=lambda x: x['total'], reverse=True)
    
    if leaderboard_lines:
        formatted_lines = []
        for entry in leaderboard_lines:
            auditor_id = entry['auditor_id']
            total = entry['total']
            assigned = entry['assigned']
            percent = entry['percent']
            stats = entry['stats']
            if assigned > 0:
                line = f"<@{auditor_id}> - {total}/{assigned} ({percent:.1f}%) "
            else:
                line = f"<@{auditor_id}> - {total} audits "
            
            breakdown = []
            if stats["wc"] > 0:
                breakdown.append(f"WC: {stats['wc']}")
            if stats["build"] > 0:
                breakdown.append(f"Build: {stats['build']}")
            if stats["tax"] > 0:
                breakdown.append(f"Tax: {stats['tax']}")
            
            if breakdown:
                line += f"[{', '.join(breakdown)}]"
            
            formatted_lines.append(line)
        
        embed.add_field(name="👷 Auditor Progress", value="\n".join(formatted_lines)[:1024], inline=False)
    else:
        embed.add_field(name="👷 Auditor Progress", value="No auditors assigned yet.", inline=False)
    
    await interaction.followup.send(embed=embed, ephemeral=True)

bot.command(name="audits_stats")(wrap_as_prefix_command(audits_stats.callback))