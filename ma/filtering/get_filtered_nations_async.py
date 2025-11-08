import pandas as pd
import asyncio
from typing import Optional, List

async def get_filtered_nations_async(
    api_key: str,
    nation_score: str,
    beige_turns: Optional[int] = None,
    has_alliance: Optional[bool] = None,
    alliance_ids: Optional[List[int]] = None,
    min_soldiers: Optional[int] = None,
    min_tanks: Optional[int] = None,
    min_aircraft: Optional[int] = None,
    min_ships: Optional[int] = None,
    nation_limit: Optional[int] = 50
) -> Optional[pd.DataFrame]:
    max_calc_s = nation_score*1.5
    min_calc_s = nation_score*0.25
    min_score = nation_score - min_calc_s
    max_score = nation_score + max_calc_s

    
    query_template = """
    query ($first: Int, $page: Int, $alliance_id: [Int], $min_score: Float, $max_score: Float, $vmode: Boolean) {
        nations(
            first: $first,
            page: $page,
            alliance_id: $alliance_id,
            min_score: $min_score,
            max_score: $max_score,
            vmode: $vmode
        ) {
            data {
                id
                nation_name
                leader_name
                continent
                color
                alliance_id
                num_cities
                soldiers
                tanks
                aircraft
                ships
                score
                vacation_mode_turns
                beige_turns
                last_active
                alliance {
                    id
                    name
                    acronym
                    score
                }
            }
            paginatorInfo {
                count
                currentPage
                hasMorePages
            }
        }
    }
    """

    all_nations = []
    batch_size = 100
    fetched = 0
    page = 1
    max_fetch = min(nation_limit * 20, 10000)

    variables = {"page": page}

    if has_alliance == False:
        variables["alliance_id"] = [0]
    elif alliance_ids:
        variables["alliance_id"] = alliance_ids
    if min_score is not None:
        variables["min_score"] = min_score
    if max_score is not None:
        variables["max_score"] = max_score

    variables["vmode"] = False

    GRAPHQL_URL = f"https://api.politicsandwar.com/graphql?api_key={api_key}"
    headers = {"Content-Type": "application/json"}

    while fetched < max_fetch:
        variables["first"] = min(batch_size, max_fetch - fetched)
        variables["page"] = page

        try:
            loop = asyncio.get_event_loop()
            import aiohttp

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    GRAPHQL_URL,
                    json={"query": query_template, "variables": variables},
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                    else:
                        print(f"API failed: {response.status}")
                        print(await response.text())
                        break  # not return



            if "errors" in data:
                print(f"GraphQL error: {data['errors']}")
                break

            nations = data.get("data", {}).get("nations", {}).get("data", [])
            if not nations:
                break

            all_nations.extend(nations)
            fetched += len(nations)
            page += 1

            paginator_info = data.get("data", {}).get("nations", {}).get("paginatorInfo", {})
            if not paginator_info.get("hasMorePages", False):
                break

            if len(nations) < batch_size:
                break

        except Exception as e:
            print(f"Error fetching nations: {e}")
            break

    if not all_nations:
        return None

    try:
        df = pd.json_normalize(all_nations)

        
        numeric_cols = ['alliance_id', 'soldiers', 'tanks', 'aircraft', 'ships', 'beige_turns']
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

        df['alliance_id_clean'] = df['alliance_id'].astype(int)

        print(f"Nations fetched from GraphQL: {len(df)}")

        
        if min_soldiers is not None:
            df = df[df['soldiers'] >= min_soldiers]
        if min_tanks is not None:
            df = df[df['tanks'] >= min_tanks]
        if min_aircraft is not None:
            df = df[df['aircraft'] >= min_aircraft]
        if min_ships is not None:
            df = df[df['ships'] >= min_ships]

        if has_alliance == True:
            df = df[df['alliance_id_clean'] > 0]
            
        if beige_turns is not None:
            if beige_turns == 0:
                df = df[df['beige_turns'] == 0]
            else:
                
                min_turns = beige_turns
                max_turns = (beige_turns + 1) - 1
                df = df[(df['beige_turns'] >= min_turns) & (df['beige_turns'] <= max_turns)]

        
        df = df.sort_values('score', ascending=False)
        df = df.head(nation_limit)

        return df if not df.empty else None

    except Exception as e:
        print(f"Error processing nations data: {e}")
        return None