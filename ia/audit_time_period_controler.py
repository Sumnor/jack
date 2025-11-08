import datetime
import discord
from discord.ext import tasks
from settings.bot_instance import bot
from databases.sql.data_puller import supabase
from settings.settings_multi import get_ia_head_role, get_quota_due_date, get_quota_days_remaining, get_quota_expiery


async def send_dm(user_id: int, message: str):
    user = bot.get_user(user_id)
    if user:
        await user.send(message)


def format_time_left(delta: datetime.timedelta) -> str:
    if delta.total_seconds() < 0:
        return "Overdue"
    days = delta.days
    hours = delta.seconds // 3600
    if days > 0:
        return f"{days}d {hours}h"
    elif hours > 0:
        return f"{hours}h"
    else:
        return "< 1h"


async def cleanup_expired_audits():
    print("[QuotaChecker] Checking for expired audits...")
    try:
        all_audits = supabase.select("audits", filters={})
        if isinstance(all_audits, dict):
            all_audits = all_audits.get("data", [])
        now = datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc)
        for audit in all_audits:
            guild_id = audit.get("guild_id")
            nation_id = audit.get("nation_id")
            if not guild_id or not nation_id:
                continue
            print(f"[DEBUG] Processing nation={nation_id}, guild={guild_id}")
            quota_days = get_quota_expiery(int(guild_id))
            try:
                quota_days = int(quota_days)
            except (TypeError, ValueError):
                quota_days = 7
            print(f"   [DEBUG] quota_days for guild={guild_id} → {quota_days}")

            wc_updated = audit.get("wc_audit_updated_at")
            build_updated = audit.get("build_audit_updated_at")
            tax_updated = audit.get("tax_audit_updated_at")
            wc_audit = audit.get("wc_audit", False)
            build_audit = audit.get("build_audit", False)
            tax_audit = audit.get("tax_audit", False)

            print(f"   [DEBUG] wc_updated={wc_updated}, build_updated={build_updated}, tax_updated={tax_updated}")
            print(f"   [DEBUG] audit flags: WC={wc_audit}, BUILD={build_audit}, TAX={tax_audit}")

            updates = {}
            if wc_audit and wc_updated:
                if isinstance(wc_updated, str):
                    wc_updated = datetime.datetime.fromisoformat(wc_updated.replace("Z", "+00:00"))
                if wc_updated.tzinfo is None:
                    wc_updated = wc_updated.replace(tzinfo=datetime.timezone.utc)
                delta = (now - wc_updated).days
                print(f"   [DEBUG] WC delta={delta} days (cutoff={quota_days})")
                if delta > quota_days:
                    updates["wc_audit"] = False
                    updates["wc_auditor"] = None
                    print(f"   ❌ Expired WC audit for nation {nation_id}")

            if build_audit and build_updated:
                if isinstance(build_updated, str):
                    build_updated = datetime.datetime.fromisoformat(build_updated.replace("Z", "+00:00"))
                if build_updated.tzinfo is None:
                    build_updated = build_updated.replace(tzinfo=datetime.timezone.utc)
                delta = (now - build_updated).days
                print(f"   [DEBUG] Build delta={delta} days (cutoff={quota_days})")
                if delta > quota_days:
                    updates["build_audit"] = False
                    updates["build_auditor"] = None
                    print(f"   ❌ Expired Build audit for nation {nation_id}")

            if tax_audit and tax_updated:
                if isinstance(tax_updated, str):
                    tax_updated = datetime.datetime.fromisoformat(tax_updated.replace("Z", "+00:00"))
                if tax_updated.tzinfo is None:
                    tax_updated = tax_updated.replace(tzinfo=datetime.timezone.utc)
                delta = (now - tax_updated).days
                print(f"   [DEBUG] Tax delta={delta} days (cutoff={quota_days})")
                if delta > quota_days:
                    updates["tax_audit"] = False
                    updates["tax_auditor"] = None
                    print(f"   ❌ Expired Tax audit for nation {nation_id}")

            if updates:
                print(f"   [DEBUG] Updates to apply: {updates}")
                try:
                    resp = supabase.update(
                        "audits",
                        filters={"guild_id": guild_id, "nation_id": nation_id},
                        data=updates
                    )
                    print(f"   ✅ Update response: {resp}")
                except Exception as e:
                    print(f"   ❌ Failed to update nation {nation_id}: {e}")
                    continue

                remaining_wc = wc_audit if "wc_audit" not in updates else False
                remaining_build = build_audit if "build_audit" not in updates else False
                remaining_tax = tax_audit if "tax_audit" not in updates else False
                print(f"   [DEBUG] Remaining audits → WC={remaining_wc}, BUILD={remaining_build}, TAX={remaining_tax}")

                if not remaining_wc and not remaining_build and not remaining_tax:
                    print(f"   🧹 Removing auditor assignment for nation {nation_id}...")
                    try:
                        resp2 = supabase.update(
                            "audits",
                            filters={"guild_id": guild_id, "nation_id": nation_id},
                            data={
                                "wc_auditor": None,
                                "build_auditor": None,
                                "tax_auditor": None
                            }
                        )
                        print(f"   ✅ Cleared auditor fields: {resp2}")
                    except Exception as e:
                        print(f"   ❌ Failed to clear auditor for nation {nation_id}: {e}")
                        import traceback
                        traceback.print_exc()
    except Exception as e:
        print(f"[ERROR] Error cleaning up expired audits: {e}")
        import traceback
        traceback.print_exc()


async def get_auditor_completed_count(guild_id: int, auditor_id: int, due_date: datetime.datetime) -> int:
    try:
        audits_response = supabase.select("audits", filters={"guild_id": str(guild_id)})
        if isinstance(audits_response, dict):
            audits = audits_response.get('data', [])
        elif isinstance(audits_response, list):
            audits = audits_response
        else:
            audits = []

        if not audits:
            return 0

        completed = 0
        for audit in audits:
            if audit.get("wc_auditor") == auditor_id and audit.get("wc_audit"):
                completed += 1
            if audit.get("build_auditor") == auditor_id and audit.get("build_audit"):
                completed += 1
            if audit.get("tax_auditor") == auditor_id and audit.get("tax_audit"):
                completed += 1
        return completed
    except Exception:
        import traceback
        traceback.print_exc()
        return 0


async def update_quota_display(guild_id: int, channel_id: int, message_id: int):
    try:
        guild = bot.get_guild(guild_id)
        if not guild:
            return
        channel = guild.get_channel(channel_id)
        if not channel:
            return
        
        try:
            old_message = await channel.fetch_message(message_id)
            await old_message.delete()
        except discord.NotFound:
            print(f"Old message not found for guild {guild_id}, creating new one...")
        except Exception as e:
            print(f"Failed to delete old message: {e}")

        quotas_response = supabase.select("auditor_quotas", filters={"guild_id": str(guild_id)})
        quotas = quotas_response.get('data', quotas_response) if isinstance(quotas_response, dict) else quotas_response
        now = datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc)
        due_date = get_quota_due_date(guild_id)
        days_remaining = get_quota_days_remaining(guild_id)

        embed = discord.Embed(
            title="📊 Audit Quota Status",
            color=discord.Color.blue(),
            timestamp=now
        )

        active_quotas = []
        for q in quotas:
            auditor_id = int(q["auditor_id"])
            assigned = int(q.get("assigned", 0))
            excused = bool(q.get("excused", False))
            delta = due_date - now
            completed = await get_auditor_completed_count(guild_id, auditor_id, due_date)
            left = assigned - completed

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

        embed.set_footer(text=f"Updates every 12 hours • {days_remaining} days remaining in period")
        new_message = await channel.send(embed=embed)
        supabase.update("quota_displays", {"message_id": str(new_message.id)}, filters={"guild_id": str(guild_id)})
        print(f"Updated quota display for guild {guild_id}, new message ID {new_message.id}")
    except Exception as e:
        print(f"Error updating quota display: {e}")


@tasks.loop(hours=12)
async def quota_check_loop():
    print("[QuotaChecker] Running periodic check...")
    await cleanup_expired_audits()
    
    try:
        quotas_response = supabase.select("auditor_quotas", filters={})
        quotas = quotas_response.get('data', quotas_response) if isinstance(quotas_response, dict) else quotas_response
    except Exception as e:
        print(f"Error fetching quotas: {e}")
        return

    now = datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc)

    for q in quotas:
        guild_id = int(q["guild_id"])
        auditor_id = int(q["auditor_id"])
        assigned = int(q.get("assigned", 0))
        excused = q.get("excused", False)
        due_date = get_quota_due_date(guild_id)
        delta = due_date - now

        completed = await get_auditor_completed_count(guild_id, auditor_id, due_date)
        left = assigned - completed
        
        if excused:
            continue
        if datetime.timedelta(hours=0) < delta <= datetime.timedelta(days=7):
            timestamp = f"<t:{int(due_date.timestamp())}:R>"
            await send_dm(
                auditor_id,
                f"⏰ Reminder: You have **{left} audits** left, due {timestamp}. Please complete your quota!"
            )

        if delta <= datetime.timedelta(hours=0) and left > 0:
            ia_role_id = get_ia_head_role(None, guild_id)
            guild = bot.get_guild(guild_id)
            ia_role = guild.get_role(ia_role_id) if guild else None
            timestamp = f"<t:{int(due_date.timestamp())}:R>"
            msg = f"⚠️ Auditor <@{auditor_id}> failed their quota by {left} audits! (Due {timestamp})"
            if ia_role:
                if guild.system_channel:
                    await guild.system_channel.send(f"{ia_role.mention} {msg}")
                else:
                    print(f"[QuotaChecker] No system channel for guild {guild_id}")
            else:
                print(f"[QuotaChecker] Could not find IA Minister role in guild {guild_id}")

    try:
        displays = supabase.select("quota_displays", filters={})
        for display in displays:
            await update_quota_display(
                int(display["guild_id"]),
                int(display["channel_id"]),
                int(display["message_id"])
            )
    except Exception as e:
        print(f"Error updating quota displays: {e}")