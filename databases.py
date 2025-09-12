import requests
import time
from discord.ext import tasks
import json
from bot_instance import SUPABASE_URL, SUPABASE_KEY

TABLE_NAME = "materials"
ALERTS_TABLE = "alerts"
MATERIALS = ["food","uranium","iron","coal","bauxite","oil","lead","steel","aluminum","munitions","gasoline"]


def fetch_column(table_name, column_name, limit=100):
    """
    Fetches all values from a specific column in a Supabase table
    """
    url = f"{SUPABASE_URL}/{table_name}?select={column_name}&limit={limit}"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}"
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    data = response.json()

    return [row[column_name] for row in data]

def fetch_columns(table_name, column_name, last_n=None):
    """
    Fetches the latest values from a specific column in Supabase.
    If last_n is provided, returns only the last `last_n` rows.
    """
    url = f"{SUPABASE_URL}/{table_name}?select={column_name}&order=timestamp.desc"
    if last_n:
        url += f"&limit={last_n}"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}"
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    data = response.json()
    

    values = [row[column_name] for row in reversed(data)]
    return values

FORECASTS_TABLE = "forecasts"

def save_forecast(material: str, forecast_avg: float):
    """
    Saves or updates a forecast in the Supabase 'forecasts' table.
    """
    url = f"{SUPABASE_URL}/{FORECASTS_TABLE}?material=eq.{material}"
    payload = {
        "material": material,
        "forecast_avg": forecast_avg,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }

    # Try update first
    resp = requests.patch(url, headers=headers, json=payload)
    if resp.status_code == 200 and resp.json():
        return resp.json()[0]

    # If no existing row, insert
    resp = requests.post(f"{SUPABASE_URL}/{FORECASTS_TABLE}", headers=headers, json=payload)
    resp.raise_for_status()
    return resp.json()[0]


def fetch_columnss(table_name, column_name, last_n=None, with_timestamps=False):
    """
    Fetches the latest values from a specific column in Supabase.
    If last_n is provided, returns only the last `last_n` rows.
    If with_timestamps=True, also fetches the 'timestamp' column.
    """
    select_fields = f"{column_name}"
    if with_timestamps:
        select_fields += ",timestamp"

    url = f"{SUPABASE_URL}/{table_name}?select={select_fields}&order=timestamp.desc"
    if last_n:
        url += f"&limit={last_n}"

    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}"
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    data = response.json()

    if with_timestamps:
        values = [row[column_name] for row in data]
        timestamps = [row["timestamp"] for row in data]
        return values[::-1], timestamps[::-1]
    else:
        return [row[column_name] for row in data][::-1]


def fetch_latest_price(material):
    data = fetch_columns(TABLE_NAME, material, last_n=1)
    return data[-1] if data else None

headers = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}

def get_alerts_for_user(discord_id: int):
    url = f"{SUPABASE_URL}/{ALERTS_TABLE}?discord_id=eq.{discord_id}"
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    data = resp.json()
    if data:
        return data[0]
    else:

        payload = {"discord_id": discord_id}
        resp = requests.post(f"{SUPABASE_URL}/{ALERTS_TABLE}", headers=headers, json=payload)
        resp.raise_for_status()
        return resp.json()[0]

def update_alert(discord_id: int, material: str, mode: int):
    url = f"{SUPABASE_URL}/{ALERTS_TABLE}?discord_id=eq.{discord_id}"
    payload = {material: mode, "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    resp = requests.patch(url, headers=headers, json=payload)
    resp.raise_for_status()
    return resp.json()

def get_all_alerts():
    url = f"{SUPABASE_URL}/{ALERTS_TABLE}"
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    return resp.json()


async def send_alert(user, message):
    try:
        await user.send(message)
    except:
        pass

def setup_alerts_task(bot, table_name="materials"):

    @tasks.loop(minutes=1)
    async def check_alerts():
        rows = get_all_alerts()
        for row in rows:
            user = bot.get_user(row["discord_id"])
            if not user:
                continue
            for mat in MATERIALS:
                mode = row.get(mat, 0)
                if mode == 0:
                    continue
                latest_price = fetch_latest_price(table_name, mat)
                if latest_price is None:
                    continue
                values = fetch_columns(table_name, mat, last_n=30)
                avg = sum(values) / len(values) if values else 0
                if avg == 0:
                    continue
                if mode in (1,3) and latest_price > avg*1.2:
                    await send_alert(user, f"⚠️ {mat.capitalize()} {latest_price} is above +20% ({avg*1.2:.2f})")
                if mode in (2,3) and latest_price < avg*0.8:
                    await send_alert(user, f"⚠️ {mat.capitalize()} {latest_price} is below -20% ({avg*0.8:.2f})")

    check_alerts.start()
    return check_alerts

def fetch_latest_model(material):
    url = f"{SUPABASE_URL}/model_parameters?select=*&material=eq.{material}&order=timestamp.desc&limit=1"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}"
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    data = response.json()
    if not data:
        return None
    row = data[0]
    intercept = float(row["intercept"])
    coefficients = json.loads(row["coefficients"])
    features = json.loads(row["features"])
    return intercept, coefficients, features


