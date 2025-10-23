import os
import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime
from dotenv import load_dotenv

# Import your Supabase client & helpers
from settings.bot_instance import SUPABASE_URL_DATA, SUPABASE_KEY_DATA, bot
from databases.sql.data_puller import supabase, get_nations_data_sql_by_nation_id, get_nations_data_sql_by_alliance_id

load_dotenv()

# ─────────────────────────────────────────────
# Utility functions for audits table
# ─────────────────────────────────────────────

def upsert_audit(guild_id: int, nation_id: str, nation_name: str):
    """Create or update a single audit entry"""
    data = {
        "guild_id": str(guild_id),
        "nation_id": str(nation_id),
        "nation_name": nation_name,
        "wc_audit": False,
        "build_audit": False,
        "tax_audit": False,
        "updated_at": datetime.utcnow().isoformat()
    }
    try:
        # Check if exists
        existing = supabase.select("audits", filters={"guild_id": str(guild_id), "nation_id": str(nation_id)})
        if existing:
            # Update existing
            supabase.update(
                "audits",
                {"nation_name": nation_name, "updated_at": datetime.utcnow().isoformat()},
                {"guild_id": str(guild_id), "nation_id": str(nation_id)}
            )
        else:
            # Insert new
            supabase.insert("audits", data)
        return True
    except Exception as e:
        print(f"Error upserting audit: {e}")
        return False

def bulk_upsert_audits(guild_id: int, nations: list):
    """Bulk create audit entries for multiple nations"""
    success_count = 0
    failed_count = 0
    
    for nation in nations:
        nation_id = str(nation.get('id'))
        nation_name = nation.get('nation_name', 'Unknown')
        
        if upsert_audit(guild_id, nation_id, nation_name):
            success_count += 1
        else:
            failed_count += 1
    
    return success_count, failed_count

def get_audits(guild_id: int):
    """Get all audits for a guild"""
    try:
        records = supabase.select("audits", filters={"guild_id": str(guild_id)})
        return records or []
    except Exception as e:
        print(f"Error fetching audits: {e}")
        return []

def delete_audit(guild_id: int, nation_id: str):
    """Delete a specific audit entry"""
    try:
        supabase.delete("audits", {"guild_id": str(guild_id), "nation_id": str(nation_id)})
        return True
    except Exception as e:
        print(f"Error deleting audit: {e}")
        return False

def toggle_audit(guild_id: int, nation_id: str, field: str):
    """Toggle a specific audit field"""
    valid_fields = ["wc_audit", "build_audit", "tax_audit"]
    if field not in valid_fields:
        raise ValueError("Invalid audit field")

    try:
        audits = supabase.select("audits", filters={"guild_id": str(guild_id), "nation_id": str(nation_id)})
        if not audits:
            raise ValueError("Audit not found. Run /audits_setup first.")

        current = audits[0]
        new_val = not current.get(field, False)
        timestamp_field = f"{field}_updated_at"

        supabase.update(
            "audits",
            {field: new_val, timestamp_field: datetime.utcnow().isoformat()},
            {"guild_id": str(guild_id), "nation_id": str(nation_id)}
        )

        updated = supabase.select("audits", filters={"guild_id": str(guild_id), "nation_id": str(nation_id)})
        return updated[0] if updated else current
    except Exception as e:
        print(f"Error toggling audit: {e}")
        raise


# ─────────────────────────────────────────────
# Discord Embed & View Logic
# ─────────────────────────────────────────────

def build_audit_embed(audit):
    """Build embed for a single audit"""
    embed = discord.Embed(
        title=f"{audit.get('nation_name', 'Unknown Nation')} — Audit",
        description=f"Nation ID: `{audit.get('nation_id')}`",
        color=discord.Color.blurple(),
        timestamp=datetime.utcnow()
    )
    embed.add_field(name="🌐 War Chest", value="✅ Passed" if audit.get("wc_audit") else "❌ Not Done", inline=True)
    embed.add_field(name="🏗️ Build Audit", value="✅ Passed" if audit.get("build_audit") else "❌ Not Done", inline=True)
    embed.add_field(name="💰 Tax Audit", value="✅ Passed" if audit.get("tax_audit") else "❌ Not Done", inline=True)
    
    # Add last updated times if available
    wc_time = audit.get('wc_audit_updated_at')
    build_time = audit.get('build_audit_updated_at')
    tax_time = audit.get('tax_audit_updated_at')
    
    times = []
    if wc_time:
        try:
            dt = datetime.fromisoformat(wc_time.replace('Z', '+00:00'))
            times.append(f"WC: <t:{int(dt.timestamp())}:R>")
        except:
            pass
    if build_time:
        try:
            dt = datetime.fromisoformat(build_time.replace('Z', '+00:00'))
            times.append(f"Build: <t:{int(dt.timestamp())}:R>")
        except:
            pass
    if tax_time:
        try:
            dt = datetime.fromisoformat(tax_time.replace('Z', '+00:00'))
            times.append(f"Tax: <t:{int(dt.timestamp())}:R>")
        except:
            pass
    
    if times:
        embed.add_field(name="⏰ Last Updated", value=" | ".join(times), inline=False)
    
    embed.set_footer(text=f"Nation ID: {audit.get('nation_id')}")
    return embed


class AuditView(discord.ui.View):
    def __init__(self, audits, guild_id):
        super().__init__(timeout=None)
        self.audits = audits
        self.guild_id = guild_id
        self.index = 0
        self._update_buttons()

    def _update_buttons(self):
        self.prev_button.disabled = self.index == 0
        self.next_button.disabled = self.index >= len(self.audits) - 1

    @discord.ui.button(label="◀ Prev", style=discord.ButtonStyle.secondary, row=0)
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.index = max(0, self.index - 1)
        self._update_buttons()
        await interaction.response.edit_message(embed=build_audit_embed(self.audits[self.index]), view=self)

    @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.secondary, row=0)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.index = min(len(self.audits) - 1, self.index + 1)
        self._update_buttons()
        await interaction.response.edit_message(embed=build_audit_embed(self.audits[self.index]), view=self)

    @discord.ui.button(label="🗑️ Delete", style=discord.ButtonStyle.danger, row=0)
    async def delete_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        current = self.audits[self.index]
        if delete_audit(self.guild_id, current["nation_id"]):
            self.audits.pop(self.index)
            if not self.audits:
                await interaction.response.edit_message(
                    content="❌ No more audits to display.",
                    embed=None,
                    view=None
                )
                return
            
            self.index = min(self.index, len(self.audits) - 1)
            self._update_buttons()
            await interaction.response.edit_message(embed=build_audit_embed(self.audits[self.index]), view=self)
        else:
            await interaction.response.send_message("❌ Failed to delete audit.", ephemeral=True)

    @discord.ui.select(
        placeholder="Toggle an audit type",
        options=[
            discord.SelectOption(label="🌐 World Congress", value="wc_audit", description="Mark WC as done/undone"),
            discord.SelectOption(label="🏗️ Build Audit", value="build_audit", description="Mark build audit as done/undone"),
            discord.SelectOption(label="💰 Tax Audit", value="tax_audit", description="Mark tax audit as done/undone")
        ],
        row=1
    )
    async def select_callback(self, interaction: discord.Interaction, select: discord.ui.Select):
        current = self.audits[self.index]
        try:
            updated = toggle_audit(self.guild_id, current["nation_id"], select.values[0])
            self.audits[self.index] = updated
            await interaction.response.edit_message(embed=build_audit_embed(updated), view=self)
        except Exception as e:
            await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)


# ─────────────────────────────────────────────
# Discord Bot Commands
# ─────────────────────────────────────────────
@bot.tree.command(name="audits_setup", description="Set up an audit entry for a nation or entire alliance")
@app_commands.describe(
    nation_id="Nation ID to add (optional if using alliance)",
    alliance_id="Alliance ID to add all members (optional if using nation_id)"
)
async def audits_setup(
    interaction: discord.Interaction, 
    nation_id: str = None,
    alliance_id: str = None
):
    await interaction.response.defer(ephemeral=True)
    
    # If no parameters, use guild's default alliance
    '''if not nation_id and not alliance_id:
        try:
            alliance_id = str(get_aa_id_guild(interaction.guild_id))
        except:
            await interaction.followup.send(
                "❌ No nation_id or alliance_id provided, and no default alliance set for this guild.",
                ephemeral=True
            )
            return'''
    
    # Single nation setup
    if nation_id:
        nation = get_nations_data_sql_by_nation_id(nation_id)
        if not nation:
            await interaction.followup.send(f"❌ No nation found for `{nation_id}`.", ephemeral=True)
            return

        nation_name = nation.get("nation_name") or nation.get("name") or "Unknown"
        if upsert_audit(interaction.guild_id, nation_id, nation_name):
            embed = discord.Embed(
                title=f"✅ Audit setup for {nation_name}",
                description=f"Nation `{nation_id}` added to audits.",
                color=discord.Color.green()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.followup.send("❌ Failed to create audit entry.", ephemeral=True)
        return
    
    # Alliance bulk setup
    if alliance_id:
        nations = get_nations_data_sql_by_alliance_id(alliance_id)
        if not nations:
            await interaction.followup.send(f"❌ No nations found in alliance `{alliance_id}`.", ephemeral=True)
            return
        
        success, failed = bulk_upsert_audits(interaction.guild_id, nations)
        
        embed = discord.Embed(
            title=f"✅ Bulk Audit Setup Complete",
            description=(
                f"**Alliance ID:** `{alliance_id}`\n"
                f"**Nations Added:** {success}\n"
                f"**Failed:** {failed}\n\n"
                f"Use `/audits` to view and manage all audit entries."
            ),
            color=discord.Color.green()
        )
        await interaction.followup.send(embed=embed, ephemeral=True)


@bot.tree.command(name="audits", description="Show and manage audits for this server")
@app_commands.describe(
    nation_id="Target a specific nation by ID",
    filter_incomplete="Only show nations with incomplete audits"
)
async def audits(
    interaction: discord.Interaction, 
    nation_id: str = None,
    filter_incomplete: bool = False
):
    await interaction.response.defer(ephemeral=True)
    
    records = get_audits(interaction.guild_id)
    if not records:
        await interaction.followup.send(
            "❌ No audits found for this server. Use `/audits_setup` first.",
            ephemeral=True
        )
        return
    
    # Target specific nation if provided
    if nation_id:
        records = [r for r in records if r.get('nation_id') == nation_id]
        if not records:
            await interaction.followup.send(
                f"❌ No audit found for nation ID `{nation_id}`.",
                ephemeral=True
            )
            return
    
    # Filter incomplete if requested
    if filter_incomplete:
        records = [
            r for r in records
            if not (r.get('wc_audit') and r.get('build_audit') and r.get('tax_audit'))
        ]
        
        if not records:
            await interaction.followup.send(
                "✅ All audits are complete! No incomplete audits found.",
                ephemeral=True
            )
            return

    # Sort by completion status (incomplete first)
    records.sort(key=lambda r: (
        r.get('wc_audit', False) and r.get('build_audit', False) and r.get('tax_audit', False),
        r.get('nation_name', '')
    ))

    embed = build_audit_embed(records[0])
    view = AuditView(records, interaction.guild_id)
    await interaction.followup.send(embed=embed, view=view, ephemeral=True)


'''@bot.tree.command(name="audits_clear", description="Clear all audit entries for this server")
async def audits_clear(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    
    records = get_audits(interaction.guild_id)
    if not records:
        await interaction.followup.send("❌ No audits to clear.", ephemeral=True)
        return
    
    # Confirmation embed
    embed = discord.Embed(
        title="⚠️ Confirm Audit Deletion",
        description=f"This will delete **{len(records)}** audit entries for this server.\n\nThis action cannot be undone.",
        color=discord.Color.red()
    )
    
    class ConfirmView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=30)
            self.value = None
        
        @discord.ui.button(label="✅ Confirm Delete", style=discord.ButtonStyle.danger)
        async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.defer()
            deleted = 0
            for record in records:
                if delete_audit(interaction.guild_id, record['nation_id']):
                    deleted += 1
            
            self.value = True
            self.stop()
            
            result_embed = discord.Embed(
                title="✅ Audits Cleared",
                description=f"Deleted {deleted} audit entries.",
                color=discord.Color.green()
            )
            await interaction.edit_original_response(embed=result_embed, view=None)
        
        @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.secondary)
        async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
            self.value = False
            self.stop()
            await interaction.response.edit_message(content="Cancelled.", embed=None, view=None)
    
    view = ConfirmView()
    await interaction.followup.send(embed=embed, view=view, ephemeral=True)'''


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

        # Group by auditor
    from collections import Counter
    auditor_counts = Counter([r.get("auditor") for r in records if r.get("auditor") and r["auditor"] != 0])

    if auditor_counts:
        leaderboard = "\n".join(
            [f"<@{aid}> — {count} audits" for aid, count in auditor_counts.most_common()]
        )
        embed.add_field(name="👷 Auditor Activity", value=leaderboard[:1024], inline=False)
    else:
        embed.add_field(name="👷 Auditor Activity", value="No auditors assigned yet.", inline=False)

    
    await interaction.followup.send(embed=embed, ephemeral=True)

@bot.tree.command(name="assign_quota", description="Assign audits to a specific auditor")
@app_commands.describe(
    auditor_id="Discord ID of the auditor",
    amount="Number of nations to assign",
    incomplete_only="Only assign nations with incomplete audits"
)
async def assign_quota(
    interaction: discord.Interaction,
    auditor_id: str,
    amount: int,
    incomplete_only: bool = True
):
    await interaction.response.defer(ephemeral=True)

    records = get_audits(interaction.guild_id)
    if not records:
        await interaction.followup.send("❌ No audits found for this server.", ephemeral=True)
        return

    if incomplete_only:
        records = [
            r for r in records
            if not (r.get('wc_audit') and r.get('build_audit') and r.get('tax_audit'))
        ]

    if not records:
        await interaction.followup.send("✅ All audits are already complete!", ephemeral=True)
        return

    # Find unassigned audits
    unassigned = [r for r in records if not r.get("auditor") or r["auditor"] == 0]
    if not unassigned:
        await interaction.followup.send("⚠️ All audits already have auditors assigned.", ephemeral=True)
        return

    # Assign up to `amount`
    to_assign = unassigned[:amount]
    assigned_count = 0

    for r in to_assign:
        success = update_audit_field(
            guild_id=interaction.guild_id,
            nation_id=r["nation_id"],
            field="auditor",
            value=int(auditor_id)
        )
        if success:
            assigned_count += 1

    embed = discord.Embed(
        title="🧾 Audit Quota Assigned",
        description=f"Assigned **{assigned_count}** audits to <@{auditor_id}>.",
        color=discord.Color.green()
    )
    await interaction.followup.send(embed=embed, ephemeral=True)


def update_audit_field(guild_id: str, nation_id: str, field: str, value):
    try:
        supabase.table("audits").update({field: value}).eq("guild_id", guild_id).eq("nation_id", nation_id).execute()
        return True
    except Exception as e:
        print(f"Error updating audit field: {e}")
        return False
