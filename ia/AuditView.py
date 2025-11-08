import discord
from datetime import datetime
from ia.audits_utils import delete_audit, toggle_audit
from databases.sql.data_puller import supabase

def build_audit_embed(audit):
    embed = discord.Embed(
        title=f"{audit.get('nation_name', 'Unknown Nation')} — Audit",
        description=f"Nation ID: `{audit.get('nation_id')}`",
        color=discord.Color.blurple(),
        timestamp=datetime.utcnow()
    )
    embed.add_field(name="🌐 War Chest", value="✅ Passed" if audit.get("wc_audit") else "❌ Not Done", inline=True)
    embed.add_field(name="🏗️ Build Audit", value="✅ Passed" if audit.get("build_audit") else "❌ Not Done", inline=True)
    embed.add_field(name="💰 Tax Audit", value="✅ Passed" if audit.get("tax_audit") else "❌ Not Done", inline=True)
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
            discord.SelectOption(label="🌐 War Chest", value="wc_audit", description="Mark WC as done/undone"),
            discord.SelectOption(label="🏗️ Build Audit", value="build_audit", description="Mark build audit as done/undone"),
            discord.SelectOption(label="💰 Tax Audit", value="tax_audit", description="Mark tax audit as done/undone")
        ],
        row=1
    )
    async def select_callback(self, interaction: discord.Interaction, select: discord.ui.Select):
        current = self.audits[self.index]
        try:
            updated = toggle_audit(self.guild_id, current["nation_id"], select.values[0], interaction.user.id)
            self.audits[self.index] = updated
            await interaction.response.edit_message(embed=build_audit_embed(updated), view=self)
        except Exception as e:
            await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)

def increment_auditor_completed(auditor_id: int, guild_id: str):
    try:
        records = supabase.select(
            "audits",
            filters={"auditor": str(auditor_id), "guild_id": guild_id}
        )

        if not records:
            return 0
        total_completed = 0
        for r in records:
            total_completed += sum([
                bool(r.get("wc_audit")),
                bool(r.get("build_audit")),
                bool(r.get("tax_audit"))
            ])

        return total_completed

    except Exception as e:
        print(f"Error counting completed audits: {e}")
        return 0
