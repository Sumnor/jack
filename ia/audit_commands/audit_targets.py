import datetime
import discord
from discord.ui import View, Button
from settings.bot_instance import bot
from databases.sql.data_puller import supabase

class QuotaPaginator(View):
    def __init__(self, embeds):
        super().__init__(timeout=300)
        self.embeds = embeds
        self.index = 0

    @discord.ui.button(label="◀️ Prev", style=discord.ButtonStyle.secondary)
    async def prev(self, interaction: discord.Interaction, button: Button):
        self.index = (self.index - 1) % len(self.embeds)
        await interaction.response.edit_message(embed=self.embeds[self.index], view=self)

    @discord.ui.button(label="Next ▶️", style=discord.ButtonStyle.secondary)
    async def next(self, interaction: discord.Interaction, button: Button):
        self.index = (self.index + 1) % len(self.embeds)
        await interaction.response.edit_message(embed=self.embeds[self.index], view=self)
def parse_dt(value):
    if not value:
        return None
    if isinstance(value, datetime.datetime):
        return value
    try:
        return datetime.datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(datetime.timezone.utc)
    except Exception:
        return None

@bot.tree.command(name="audit_targets", description="Show all nations' audits and their ages (20 per page)")
async def show_quotas(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    guild_id = str(interaction.guild_id)

    audits = supabase.select("audits", filters={"guild_id": guild_id})
    if not audits:
        await interaction.followup.send("❌ No audit records found for this guild.", ephemeral=True)
        return

    now = datetime.datetime.now(datetime.timezone.utc)
    for a in audits:
        for t in ["wc_audit_updated_at", "build_audit_updated_at", "tax_audit_updated_at"]:
            a[t] = parse_dt(a.get(t))
    audits.sort(
        key=lambda a: min(
            (now - a[t]).days if a.get(t) else 9999
            for t in ["wc_audit_updated_at", "build_audit_updated_at", "tax_audit_updated_at"]
        ),
        reverse=True,  # 🔴 red (oldest) first
    )

    def audit_age_color(dt):
        dt = parse_dt(dt)
        if not dt:
            return "🟥 Never"
        days = (now - dt).days
        if days <= 7:
            return f"🟩 {days}d ago"
        elif days <= 14:
            return f"🟨 {days}d ago"
        else:
            return f"🟥 {days}d ago"

    embeds = []
    for i in range(0, len(audits), 20):
        page = audits[i:i + 20]
        desc = ""

        for a in page:
            nation = a.get("nation_name") or a.get("nation_id", "Unknown Nation")
            wc = audit_age_color(a.get("wc_audit_updated_at"))
            build = audit_age_color(a.get("build_audit_updated_at"))
            tax = audit_age_color(a.get("tax_audit_updated_at"))

            desc += f"**{nation}**\n 📦 WC: {wc} 🏗️ Build: {build} 💰 Tax: {tax}\n"

        embed = discord.Embed(
            title=f"📊 Audit Status — Page {i//20 + 1}",
            description=desc or "✅ No audits found.",
            color=discord.Color.blurple(),
        )
        embed.set_footer(text=f"Nations {i + 1}–{min(i + 20, len(audits))} of {len(audits)}")
        embeds.append(embed)

    if not embeds:
        await interaction.followup.send("✅ No audits available.", ephemeral=True)
        return

    view = QuotaPaginator(embeds)
    await interaction.followup.send(embed=embeds[0], view=view, ephemeral=True)
