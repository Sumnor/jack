import datetime
import discord
from discord import app_commands
from settings.bot_instance import bot
from databases.sql.data_puller import supabase
from settings.settings_multi import get_ia_head_role, get_ia_gov_role, get_quota_due_date
from ia.audit_time_period_controler import get_auditor_completed_count

@bot.tree.command(name="quota_display", description="Create or view the quota status display message")
async def quota_display(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)

    user = interaction.user
    guild = interaction.guild

    ia_head = int(get_ia_head_role(interaction))
    ia_staff = int(get_ia_gov_role(interaction))
    has_head = ia_head in [r.id for r in user.roles]
    has_staff = ia_staff in [r.id for r in user.roles]

    if not (has_head or has_staff):
        await interaction.followup.send("❌ You don't have permission to use this command.", ephemeral=True)
        return

    try:
        quotas_response = supabase.select("auditor_quotas", filters={"guild_id": str(guild.id)})
        if isinstance(quotas_response, dict):
            quotas = quotas_response.get('data', quotas_response)
        else:
            quotas = quotas_response

        now = datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc)

        embed = discord.Embed(
            title="📊 Audit Quota Status",
            color=discord.Color.blue(),
            timestamp=now
        )

        active_quotas = []
        for q in quotas:
            due = get_quota_due_date(interaction.guild.id)
            due_date = get_quota_due_date(interaction.guild.id)
            if not due:
                continue

            if isinstance(due, str):
                try:
                    due = datetime.datetime.fromisoformat(due.replace('Z', '+00:00'))
                except Exception:
                    continue

            if due.tzinfo is None:
                due = due.replace(tzinfo=datetime.timezone.utc)

            delta = due - now
            if delta.total_seconds() < -86400:
                continue

            auditor_id = int(q["auditor_id"])
            assigned = int(q.get("assigned", 0))
            completed = await get_auditor_completed_count(guild.id, auditor_id, due)
            left = assigned - completed
            excused = bool(q.get("excused", False))

            status = "✅" if left <= 0 else "⚠️" if delta.total_seconds() > 0 else "❌"
            if excused:
                status = "💤"

            time_str = f"<t:{int(due_date.timestamp())}:R>"

            active_quotas.append({
                'auditor_id': auditor_id,
                'left': left,
                'assigned': assigned,
                'completed': completed,
                'time_str': time_str,
                'status': status,
                'excused': excused,
                'due': due_date
            })

        active_quotas.sort(key=lambda x: x['due'])

        if not active_quotas:
            embed.description = "No active quotas at this time."
        else:
            for aq in active_quotas:
                try:
                    user_obj = await bot.fetch_user(aq['auditor_id'])
                    name = f"{aq['status']} {user_obj.global_name or user_obj.name}"
                except Exception:
                    name = f"{aq['status']} <@{aq['auditor_id']}>"

                value = f"**Progress:** {aq['completed']}/{aq['assigned']} ({aq['left']} left)\n**Due:** {aq['time_str']}"
                if aq['excused']:
                    value += "\n*Excused*"
                embed.add_field(name=name, value=value, inline=False)

        embed.set_footer(text="Updates every 12 hours")
        existing = supabase.select("quota_displays", filters={"guild_id": str(guild.id)})
        if isinstance(existing, dict):
            existing = existing.get('data', existing)

        if has_head:
            if existing:
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            else:
                message = await interaction.channel.send(embed=embed)
                supabase.insert("quota_displays", {
                    "guild_id": str(guild.id),
                    "channel_id": str(interaction.channel_id),
                    "message_id": str(message.id)
                })
                await interaction.followup.send("✅ Quota display created and saved for automatic updates.", ephemeral=True)
                return

        elif has_staff:
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

    except Exception as e:
        await interaction.followup.send("❌ Error creating quota display.", ephemeral=True)


@quota_display.error
async def quota_display_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.errors.MissingPermissions):
        await interaction.response.send_message("❌ You need administrator permissions to use this command.", ephemeral=True)