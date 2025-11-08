import requests
import json
import pandas as pd
from settings.settings_multi import get_api_key_for_interaction, get_api_key_for_guild

PROJECT_KEYS = [
    "iron_works", "bauxite_works", "arms_stockpile", "emergency_gasoline_reserve",
    "mass_irrigation", "international_trade_center", "missile_launch_pad",
    "nuclear_research_facility", "iron_dome", "vital_defense_system",
    "central_intelligence_agency", "center_for_civil_engineering", "propaganda_bureau",
    "uranium_enrichment_program", "urban_planning", "advanced_urban_planning",
    "space_program", "spy_satellite", "moon_landing", "pirate_economy",
    "recycling_initiative", "telecommunications_satellite", "green_technologies",
    "arable_land_agency", "clinical_research_center", "specialized_police_training_program",
    "advanced_engineering_corps", "government_support_agency",
    "research_and_development_center", "metropolitan_planning", "military_salvage",
    "fallout_shelter", "activity_center", "bureau_of_domestic_affairs",
    "advanced_pirate_economy", "mars_landing", "surveillance_network",
    "guiding_satellite", "nuclear_launch_facility", "military_research_center",
    "military_doctrine"
]

def graphql_cities(nation_id, interaction=None, guild_id=None):
    if not guild_id:
        API_KEY = get_api_key_for_interaction(interaction)
    if not interaction:
        API_KEY = get_api_key_for_guild(guild_id)
    GRAPHQL_URL = f"https://api.politicsandwar.com/graphql?api_key={API_KEY}"

    
    project_fields = "\n".join(PROJECT_KEYS)

    query = f"""
    {{
      nations(id: [{nation_id}]) {{
        data {{
          num_cities
          {project_fields}
          cities {{
            name
            id
            infrastructure
            land
            powered
            oil_power
            wind_power
            coal_power
            nuclear_power
            coal_mine
            oil_well
            uranium_mine
            barracks
            farm
            police_station
            hospital
            recycling_center
            subway
            supermarket
            bank
            shopping_mall
            stadium
            lead_mine
            iron_mine
            bauxite_mine
            oil_refinery
            aluminum_refinery
            steel_mill
            munitions_factory
            factory
            hangar
            drydock
          }}
        }}
      }}
    }}
    """

    try:
        response = requests.post(
            GRAPHQL_URL,
            json={"query": query},
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
        json_data = response.json()

        if "errors" in json_data:
            print("GraphQL Errors:", json_data["errors"])
            return None

        nations_data = json_data.get("data", {}).get("nations", {}).get("data", [])
        if not nations_data:
            print("No nation data found.")
            return None

        df = pd.json_normalize(nations_data)
        return df

    except requests.RequestException as e:
        print(f"HTTP Error during GraphQL request: {e}")
        return None
    except (KeyError, TypeError, json.JSONDecodeError) as e:
        print(f"Parsing Error: {e}")
        return None

def graphql_request(nation_id, interaction=None, guild_id=None, API_KEY=None):
    if guild_id:
        API_KEY = get_api_key_for_guild(guild_id)
        print("1")
    elif interaction:
        API_KEY = get_api_key_for_interaction(interaction)
        print("2")
    elif API_KEY:
        API_KEY = API_KEY
        print("3")
    GRAPHQL_URL = f"https://api.politicsandwar.com/graphql?api_key={API_KEY}"

    query = f"""
    {{
      nations(id: [{nation_id}]) {{
        data {{
          id
          nation_name
          leader_name
          last_active
          alliance_id
          alliance_position
          alliance {{ name }}
          color
          war_policy
          domestic_policy
          projects
          turns_since_last_project
          continent
          num_cities
          score
          population
          vmode
          beigeturns
          soldiers
          tanks
          aircraft
          ships
          missiles
          nukes
          espionage_available
          spies
          money
          coal
          oil
          uranium
          iron
          bauxite
          lead
          gasoline
          munitions
          steel
          aluminum
          food
        }}
      }}
    }}
    """

    try:
        response = requests.post(
            GRAPHQL_URL,
            json={"query": query},
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
        json_data = response.json()

        if "errors" in json_data:
            print("GraphQL Errors:", json_data["errors"])
            return None

        nations_data = json_data.get("data", {}).get("nations", {}).get("data", [])
        if not nations_data:
            print("No nation data found.")
            return None

        df = pd.json_normalize(nations_data)
        return df

    except requests.RequestException as e:
        print(f"HTTP Error during GraphQL request: {e}")
        return None
    except (KeyError, TypeError, json.JSONDecodeError) as e:
        print(f"Parsing Error: {e}")
        return None
    
def get_resources(nation_id, interaction=None, guild_id=None):
    print(guild_id)
    if not guild_id:
        df = graphql_request(nation_id, interaction, None)
    if not interaction:
        df = graphql_request(nation_id, None, guild_id)
    if df is not None:
        try:
            row = df[df["id"].astype(str) == str(nation_id)].iloc[0]
            print(row.get("money", 0))

            return (
                row.get("nation_name", ""),
                row.get("num_cities", 0),
                row.get("food", 0),
                row.get("money", 0),
                row.get("gasoline", 0),
                row.get("munitions", 0),
                row.get("steel", 0),
                row.get("aluminum", 0),
                row.get("bauxite", 0),
                row.get("lead", 0),
                row.get("iron", 0),
                row.get("oil", 0),
                row.get("coal", 0),
                row.get("uranium", 0),
            )
        except IndexError:
            return None

def get_general_data(nation_id, interaction=None, API_KEY=None, guild_id=None):
    if API_KEY:
        df = graphql_request(nation_id, None, None, API_KEY)
    if interaction:
        df = graphql_request(nation_id, interaction)
    if guild_id:
        df = graphql_request(nation_id, None, guild_id)
    if df is not None:
        try:
            row = df[df["id"].astype(str) == str(nation_id)].iloc[0]
            return (
                row.get("alliance_id", "Unknown"),
                row.get("alliance_position", "Unknown"),
                row.get("alliance.name", "None/Unaffiliated"),
                row.get("domestic_policy", "Unknown"),
                row.get("num_cities", "/"),
                row.get("color", "Unknown"),
                row.get("last_active", "/"),
                row.get("projects", "Unknown"),
                row.get("turns_since_last_project", "/"),
            )
        except IndexError:
            return None

def get_military(nation_id, interaction):
    df = graphql_request(nation_id, interaction)
    if df is not None:
        try:
            row = df[df["id"].astype(str) == str(nation_id)].iloc[0]
            return (
                row.get("nation_name", ""),
                row.get("leader_name", ""),
                row.get("score", 0),
                row.get("war_policy", ""),
                row.get("soldiers", 0),
                row.get("tanks", 0),
                row.get("aircraft", 0),
                row.get("ships", 0),
                row.get("spies", 0),
                row.get("missiles", 0),
                row.get("nukes", 0)
            )
        except IndexError:
            return None