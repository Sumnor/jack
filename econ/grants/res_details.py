import discord
from settings.bot_instance import bot
from settings.initializer_functions.cached_users_initializer import cached_users
from settings.settings_multi import get_gov_role, get_aa_name
from databases.graphql_requests import get_resources
import time
import asyncio
import io

@bot.tree.command(
    name="res_details_for_alliance",
    description="Get each Alliance Member's resources, money, and wartime readiness"
)
async def res_details_for_alliance(interaction: discord.Interaction):
    await interaction.response.defer()
    msg = await interaction.followup.send("Calculating wait-times...")

    user_id = str(interaction.user.id)
    guild_id = str(interaction.guild.id)
    user_data = cached_users.get(user_id)
    if not user_data:
        await msg.edit(content="❌ Error")
        await interaction.followup.send(
            "❌ You are not registered. Please register first.", ephemeral=True
        )
        return

    own_id = str(user_data.get("NationID", "")).strip()
    if not own_id:
        await msg.edit(content="❌ Error")
        await interaction.followup.send(
            "❌ Could not find your Nation ID in the cache.", ephemeral=True
        )
        return

    async def is_banker(interaction):
        GOV_ROLE = get_gov_role(interaction)
        return any(role.name == GOV_ROLE for role in interaction.user.roles)

    if not await is_banker(interaction):
        await msg.edit(content="❌ Error")
        await interaction.followup.send(
            "❌ You don't have the rights necessary to perform this action.", ephemeral=True
        )
        return

    try:
        aa_name = get_aa_name(interaction)
        alliance_members = [
            {"NationID": data.get("NationID"), "DiscordID": discord_id, "AA": data.get("AA")}
            for discord_id, data in cached_users.items()
            if data.get("AA", "").strip().lower() == aa_name.strip().lower()
        ]
        if not alliance_members:
            await msg.edit(content="❌ Error")
            await interaction.followup.send(f"❌ No members found in AA: {aa_name}", ephemeral=True)
            return

        member_count = len(alliance_members)
        batches_of_30 = (member_count + 29) // 30
        total_wait_seconds = batches_of_30 * 32
        target_time = int(time.time()) + total_wait_seconds
        await msg.edit(content=f"Estimated total wait time: <t:{target_time}:R>")

    except Exception as e:
        await msg.edit(content="❌ Error")
        await interaction.followup.send(f"❌ Error loading alliance members: {e}", ephemeral=True)
        return

    data_rows = []
    failed_nations = []
    processed_nations = 0
    processed = []
    underprepared = []
    batch_count = 0

    for i, member in enumerate(alliance_members):
        nation_id = str(member.get("NationID", "")).strip()
        if not nation_id:
            continue

        try:
            result = get_resources(nation_id, interaction)
            if not result or len(result) != 14:
                raise ValueError(f"Invalid result length for {nation_id}")

            (
                nation_name,
                num_cities,
                food,
                money,
                gasoline,
                munitions,
                steel,
                aluminum,
                bauxite,
                lead,
                iron,
                oil,
                coal,
                uranium
            ) = result

            data_rows.append({
                "NationID": nation_id,
                "NationName": nation_name,
                "Cities": num_cities or 0,
                "Money": money or 0,
                "Food": food or 0,
                "Gasoline": gasoline or 0,
                "Munitions": munitions or 0,
                "Steel": steel or 0,
                "Aluminum": aluminum or 0,
                "Bauxite": bauxite or 0,
                "Lead": lead or 0,
                "Iron": iron or 0,
                "Oil": oil or 0,
                "Coal": coal or 0,
                "Uranium": uranium or 0
            })
            requirements = {
                "Money": (num_cities * 1_000_000, money),
                "Food": (num_cities * 3000, food),
                "Uranium": (num_cities * 40, uranium),
                "Gasoline": (num_cities * 750, gasoline),
                "Munitions": (num_cities * 750, munitions),
                "Steel": (num_cities * 750, steel),
                "Aluminum": (num_cities * 750, aluminum),
            }

            total_pct = 0
            missing = []
            for res, (req, have) in requirements.items():
                pct = (have / req * 100) if req > 0 else 100
                total_pct += min(pct, 100)
                if pct < 100:
                    missing.append(f"{res} ({pct:,.1f}%)")

            avg_pct = total_pct / len(requirements)

            def get_color(pct: float) -> str:
                if pct >= 76: return "🟢"
                if pct >= 51: return "🟡"
                if pct >= 26: return "🟠"
                if pct >= 10: return "🔴"
                return "⚫"

            color = get_color(avg_pct)
            if avg_pct < 75:
                underprepared.append((nation_name, avg_pct, color, missing))

            processed_nations += 1
            processed.append(nation_id)
            batch_count += 1

            if batch_count == 30:
                await asyncio.sleep(35)
                batch_count = 0

            if (i + 1) % 10 == 0 or i == len(alliance_members) - 1:
                remaining_members = len(alliance_members) - (i + 1)
                remaining_batches = (remaining_members + 29) // 30
                remaining_wait = remaining_batches * 32
                if remaining_wait > 0:
                    new_target_time = int(time.time()) + remaining_wait
                    await msg.edit(content=f"Processing... {i + 1}/{len(alliance_members)} done. Estimated completion: <t:{new_target_time}:R>")
                else:
                    await msg.edit(content=f"Processing... {i + 1}/{len(alliance_members)} done. Almost finished!")

        except Exception as e:
            print(f"Failed processing nation {nation_id}: {e}")
            failed_nations.append(nation_id)
            continue
    totals = {key: sum(row[key] for row in data_rows) for key in data_rows[0] if isinstance(data_rows[0][key], (int, float))}
    lines = [
        f"{row['NationName']} (ID: {row['NationID']}): Cities={row['Cities']}, Money=${row['Money']:,}, "
        f"Food={row['Food']:,}, Gasoline={row['Gasoline']:,}, Munitions={row['Munitions']:,}, "
        f"Steel={row['Steel']:,}, Aluminum={row['Aluminum']:,}, Bauxite={row['Bauxite']:,}, "
        f"Lead={row['Lead']:,}, Iron={row['Iron']:,}, Oil={row['Oil']:,}, Coal={row['Coal']:,}, Uranium={row['Uranium']:,}"
        for row in data_rows
    ]

    total_resources_line = (
        f"\nAlliance totals - Nations counted: {processed_nations}, Failed: {len(failed_nations)}\n"
        f"Total Cities: {totals.get('Cities',0):,}\n"
        f"Money: ${totals.get('Money',0):,}\n"
        f"Food: {totals.get('Food',0):,}\n"
        f"Gasoline: {totals.get('Gasoline',0):,}\n"
        f"Munitions: {totals.get('Munitions',0):,}\n"
        f"Steel: {totals.get('Steel',0):,}\n"
        f"Aluminum: {totals.get('Aluminum',0):,}\n"
        f"Bauxite: {totals.get('Bauxite',0):,}\n"
        f"Lead: {totals.get('Lead',0):,}\n"
        f"Iron: {totals.get('Iron',0):,}\n"
        f"Oil: {totals.get('Oil',0):,}\n"
        f"Coal: {totals.get('Coal',0):,}\n"
        f"Uranium: {totals.get('Uranium',0):,}\n"
    )

    text_content = "\n".join(lines) + total_resources_line
    text_file = discord.File(io.BytesIO(text_content.encode()), filename="alliance_resources.txt")
    embeds = []
    chunk_size = 10
    for i in range(0, len(underprepared), chunk_size):
        chunk = underprepared[i:i+chunk_size]
        desc = "\n".join([
            f"{color} **{name}** — {pct:,.1f}% ready\nMissing: {', '.join(missing)}"
            for name, pct, color, missing in chunk
        ])
        embeds.append(discord.Embed(
            title=f"⚠️ Underprepared Nations (Part {i//chunk_size + 1})",
            description=desc or "All nations meet wartime readiness ✅",
            color=discord.Color.orange()
        ))

    main_embed = discord.Embed(
        title="Alliance Members' Resources and Money (Detailed)",
        description=f"Nations counted: **{processed_nations}**\nFailed: **{len(failed_nations)}**\n"
                    f"**FAILED:** {failed_nations}\n**SUCCESS:** {processed}",
        colour=discord.Colour.dark_magenta()
    )
    image_url = "https://i.ibb.co/Kpsfc8Jm/jack.webp"
    main_embed.set_footer(text="Brought to you by Sumnor", icon_url=image_url)

    await msg.edit(embed=main_embed, attachments=[text_file])
    for e in embeds:
        await interaction.followup.send(embed=e)
