import discord
from discord import app_commands
from settings.bot_instance import bot, wrap_as_prefix_command
from settings.settings_multi import get_api_key_for_interaction
from settings.initializer_functions.cached_users_initializer import cached_users
from ma.filtering.get_filtered_nations_async import get_filtered_nations_async
from ma.filtering.FilterView import NationPaginationView
from databases.graphql_requests import get_military
from typing import Optional
import pandas as pd

@bot.tree.command(name="filter_nations", description="Filter Politics and War nations by various criteria")
@app_commands.describe(
    beige_days="Days in beige (0 = not beige, 1+ = days in beige)",
    has_alliance="Filter by alliance membership (True/False)",
    alliance_ids="Comma-separated alliance IDs (e.g., 1234,5678)",
    min_soldiers="Minimum soldiers",
    min_tanks="Minimum tanks",
    min_aircraft="Minimum aircraft",
    min_ships="Minimum ships",
    nation_limit="Maximum nations to return (default 50, min 20)"
)
async def filter_nations(
    interaction: discord.Interaction,
    beige_days: Optional[int] = None,
    has_alliance: Optional[bool] = None,
    alliance_ids: Optional[str] = None,
    min_soldiers: Optional[int] = None,
    min_tanks: Optional[int] = None,
    min_aircraft: Optional[int] = None,
    min_ships: Optional[int] = None,
    nation_limit: Optional[int] = 50
):
    
    await interaction.response.defer(thinking=True)
    global cached_users
    user_id = str(interaction.user.id)
    user_data = cached_users.get(user_id)
    if not user_data:
        await interaction.followup.send(
            "❌ You are not registered. Please register first.", ephemeral=True
        )
        return
    own_id = str(user_data.get("NationID", "")).strip()
    nation_name, nation_leader, nation_score, war_policy, soldiers, tanks, aircraft, ships, spies, missiles, nuclear = get_military(own_id, interaction)
    
    try:
        
        api_key = get_api_key_for_interaction(interaction)
        if not api_key:
            await interaction.followup.send("❌ No API key found for your account. Please register your API key first.")
            return
        
        
        alliance_id_list = None
        if alliance_ids:
            try:
                alliance_id_list = [int(x.strip()) for x in alliance_ids.split(',')]
            except ValueError:
                await interaction.followup.send("❌ Invalid alliance IDs format. Use comma-separated numbers like: 1234,5678")
                return
        
        
        if nation_limit and nation_limit < 20:
            nation_limit = 20
        elif not nation_limit:
            nation_limit = 50
            
        if nation_limit > 500:
            nation_limit = 500

        
        df = await get_filtered_nations_async(
            api_key=api_key,
            nation_score=nation_score,
            beige_turns=beige_days,
            has_alliance=has_alliance,
            alliance_ids=alliance_id_list,
            min_soldiers=min_soldiers,
            min_tanks=min_tanks,
            min_aircraft=min_aircraft,
            min_ships=min_ships,
            nation_limit=nation_limit
        )
        
        if isinstance(df, dict):
            df = pd.DataFrame(df)

        if df is None or df.empty:
            await interaction.followup.send("🔍 No nations found matching the specified criteria.")
            return
        
        
        embed = discord.Embed(
            title="🏴󠁧󠁢󠁳󠁣󠁴󠁿 Filtered Nations Results",
            description=f"Found **{len(df)}** nations matching your criteria",
            color=discord.Color.blue()
        )
        
        
        filters = []
        if beige_days is not None:
            if beige_days == 0:
                filters.append("Not in beige")
            else:
                filters.append(f"Beige: {beige_days} days")
        if has_alliance is not None:
            filters.append(f"Has Alliance: {'Yes' if has_alliance else 'No'}")
        if alliance_id_list:
            filters.append(f"Alliance IDs: {', '.join(map(str, alliance_id_list))}")
        if min_soldiers:
            filters.append(f"Min Soldiers: {min_soldiers:,}")
        if min_tanks:
            filters.append(f"Min Tanks: {min_tanks:,}")
        if min_aircraft:
            filters.append(f"Min Aircraft: {min_aircraft:,}")
        if min_ships:
            filters.append(f"Min Ships: {min_ships:,}")
        
        
        view = NationPaginationView(df, filters)
        embed = view.create_embed()
        
        await interaction.followup.send(embed=embed, view=view)
        
    except Exception as e:
        print(f"Error in filter_nations command: {e}")
        await interaction.followup.send(f"❌ An error occurred while filtering nations: {str(e)}")

bot.command(name="filter_nations")(wrap_as_prefix_command(filter_nations.callback))