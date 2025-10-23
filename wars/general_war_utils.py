import aiohttp

async def get_nation_info(nation_id: str, api_key: str) -> dict:
    """Get nation information from PnW API"""
    try:
        url = f"https://api.politicsandwar.com/graphql?api_key={api_key}"
        query = """
        query($id: ID!) {
            nation(id: $id) {
                id
                nation_name
                leader_name
                alliance {
                    id
                    name
                }
                soldiers
                tanks
                aircraft
                ships
                military_power
                resistance
                wars(active: true) {
                    data {
                        id
                        att_points
                        def_points
                        att_resistance
                        def_resistance
                        turns_left
                        war_type
                    }
                }
            }
        }
        """
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json={
                'query': query,
                'variables': {'id': nation_id}
            }) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get('data', {}).get('nation', {})
                else:
                    print(f"API request failed with status {response.status}")
                    return {}
    except Exception as e:
        print(f"Error fetching nation info for {nation_id}: {e}")
        return {}