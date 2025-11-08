import discord
import json
from typing import Optional, Dict, List, Any
from datetime import datetime, date
from databases.sql.data_puller import get_cities_data_sql_by_nation_id
from information.SharedInformational.control_buttons import PrevPageButton, NextPageButton, BackButton, CloseButton

class ShowCitiesDetailButton(discord.ui.Button):
    def __init__(self, nation_id: int, original_embed: discord.Embed, parent_view: discord.ui.View, user_id: int):
        super().__init__(label="Detailed Cities", style=discord.ButtonStyle.secondary, row=1)
        self.nation_id = nation_id
        self.original_embed = original_embed
        self.parent_view = parent_view 
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This view isn't meant for you.", ephemeral=True)
            return

        await interaction.response.defer() 
        message = interaction.message 
        
        try:
            city_imp_plans = {} 

            cities_detail_view = CitiesDetail(
                nation_id=self.nation_id, 
                original_embed=self.original_embed, 
                original_view_instance=self.parent_view,
                user_id=self.user_id
            )

            await cities_detail_view.display_cities(
                message=message, 
                city_imp_plans=city_imp_plans
            )

        except Exception as e:
            await interaction.followup.send(f"❌ Error switching to detailed view: {e}", ephemeral=True)

BUILDING_KEY_MAP = {
    'oil_power': 'imp_oilpower', 'wind_power': 'imp_windpower', 'coal_power': 'imp_coalpower',
    'nuclear_power': 'imp_nuclearpower', 'coal_mine': 'imp_coalmine', 'oil_well': 'imp_oilwell',
    'uranium_mine': 'imp_uramine', 'barracks': 'imp_barracks', 'farm': 'imp_farm',
    'police_station': 'imp_policestation', 'hospital': 'imp_hospital', 'recycling_center': 'imp_recyclingcenter',
    'subway': 'imp_subway', 'supermarket': 'imp_supermarket', 'bank': 'imp_bank', 
    'shopping_mall': 'imp_mall', 'stadium': 'imp_stadium', 'lead_mine': 'imp_leadmine', 
    'iron_mine': 'imp_ironmine', 'bauxite_mine': 'imp_bauxitemine', 'oil_refinery': 'imp_gasrefinery', 
    'aluminum_refinery': 'imp_aluminumrefinery', 'steel_mill': 'imp_steelmill',
    'munitions_factory': 'imp_munitionsfactory', 'factory': 'imp_factory', 'hangar': 'imp_hangars', 
    'drydock': 'imp_drydock',
}

class CitiesDetail(discord.ui.View):
    def __init__(self, nation_id: int, original_embed: discord.Embed, original_view_instance: discord.ui.View = None, user_id: Optional[int] = None):
        super().__init__(timeout=None)
    
        self.who = user_id
        self.nation_id = nation_id
        self.original_embed = original_embed 
        self.original_view_instance = original_view_instance 
        self.pages: List[Dict[str, Any]] = [] 
        self.current_page = 0
        self.cities_per_page = 1 
        self.paginator_title = f"Details Cities for {nation_id}"


    def _generate_city_pages(self, city_imp_plans: Dict[int, Dict[str, Any]]) -> List[Dict[str, Any]]:
        city_pages = []
        cities = get_cities_data_sql_by_nation_id(self.nation_id)
        
        for city in cities:
            city_id = city.get('id', 0)
            date_obj = city.get('date')
            date_ts = int(date_obj.timestamp()) if isinstance(date_obj, (datetime, date)) else None
            
            imp_plan = city_imp_plans.get(city_id, {})
            
            city_data_json = {
                "infra_needed": imp_plan.get("infra_needed", 0),
                "imp_total": imp_plan.get("imp_total", 0),
            }
            
            for db_key, imp_key in BUILDING_KEY_MAP.items():
                existing_buildings = city.get(db_key, 0)
                planned_improvements = imp_plan.get(imp_key, 0)
                city_data_json[imp_key] = existing_buildings + planned_improvements

            city_pages.append({
                'city_id': city_id, 'city_name': city.get('name', 'Unnamed City'),
                'infra': city.get('infrastructure', 0), 'land': city.get('land', 0),
                'date_ts': date_ts, 'json_block': city_data_json
            })
        return city_pages


    async def display_cities(self, message: discord.Message, city_imp_plans: Dict[int, Dict[str, Any]]):
        """Public entry point: Processes data, sets up buttons, and displays the first page."""
        self.pages = self._generate_city_pages(city_imp_plans)
        self.current_page = 0
        
        if not self.pages:
             view_to_return_to = self.original_view_instance or None
             await message.edit(
                embed=discord.Embed(title="No Cities Found", description="Could not find city data for this nation.", color=discord.Color.red()), 
                view=view_to_return_to
            )
             return

        self.add_navigation_buttons()
        await self.show_first_page(message)


    def add_navigation_buttons(self):
        self.clear_items()
        if len(self.pages) > 1:
            self.add_item(PrevPageButton())
            self.add_item(NextPageButton())
            
        if self.original_view_instance:
            self.add_item(BackButton(self.original_embed, self.original_view_instance))
        self.add_item(CloseButton())


    async def show_first_page(self, message: discord.Message):
        embed = self.build_embed_for_page()
        await message.edit(embed=embed, view=self)


    async def show_current_page(self, interaction: discord.Interaction):
        self.add_navigation_buttons()
        
        embed = self.build_embed_for_page()
        await interaction.response.edit_message(embed=embed, view=self)
    
    
    def build_embed_for_page(self):
        if not self.pages:
            return discord.Embed(title="No City Data Found", color=discord.Color.red())

        page_data = self.pages[self.current_page]
        
        embed = discord.Embed(
            title=f"{self.paginator_title} (City {self.current_page + 1} of {len(self.pages)})",
            colour=discord.Colour.blue()
        )
        
        city_id = page_data.get('city_id')
        city_name = page_data.get('city_name')
        
        embed.add_field(name="City", value=f"[{city_name}](https://politicsandwar.com/city/id={city_id})", inline=True)
        embed.add_field(name="Infra", value=f"{page_data.get('infra', 0):,.0f}", inline=True)
        embed.add_field(name="Land", value=f"{page_data.get('land', 0):,.0f}", inline=True)
        
        date_ts = page_data.get('date_ts')
        if date_ts:
            age_value = f"Created: <t:{date_ts}:f> (<t:{date_ts}:R> ago)"
            embed.add_field(name="Age", value=age_value, inline=False)
        
        json_data = page_data.get('json_block', {})
        json_string = json.dumps(json_data, indent=4)
        
        embed.description = f"\n```json\n{json_string}\n```"
        
        embed.set_footer(text=f"Page {self.current_page + 1}/{len(self.pages)} | Use arrows to navigate cities.")
        
        return embed
    
def extract_cities_from_df(df):
    if df is None or df.empty:
        return None
    try:
        cities = df.at[0, "cities"]
        return cities
    except Exception as e:
        print(f"Error extracting cities from df: {e}")
        return None