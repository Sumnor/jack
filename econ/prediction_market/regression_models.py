
import pandas as pd
import json
import numpy as np
import requests
from databases.sql.databases import SUPABASE_URL, SUPABASE_KEY, fetch_latest_model

MATERIALS = ["food","uranium","iron","coal","bauxite","oil","lead","steel","aluminum","munitions","gasoline"]

def save_regression(material, intercept, coef, steps, count):
    url = f"{SUPABASE_URL}/model_parameters"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "material": material,
        "intercept": intercept,
        "coefficients": json.dumps(coef),
        "features": json.dumps({"time_steps": steps, "count": count})
    }
    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status()


def fetch_material_data():
    """Fetch all historical snapshots from Supabase as a DataFrame."""
    url = f"{SUPABASE_URL}/materials?select=*"
    headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
    res = requests.get(url, headers=headers)
    res.raise_for_status()
    df = pd.DataFrame(res.json())
    if not df.empty:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df = df.sort_values("timestamp")
    return df

def train_model_for_resource(df, resource_name):
    data = df[[resource_name, "timestamp"]].dropna()
    if data.empty:
        return None, None

    data = data.reset_index(drop=True)
    X = np.arange(len(data)).reshape(-1, 1)
    y = data[resource_name].values.reshape(-1, 1)
    intercept = 0.0
    coef = [0.0]
    steps = list(range(len(data)))
    count = len(data)

    if resource_name == "food":

        if data[resource_name].std() < 1e-3 or count < 2:
            predicted_price = data[resource_name].iloc[-1]
        else:
            pct_changes = data[resource_name].pct_change().fillna(0)
            avg_pct_change = pct_changes.mean()
            if not np.isfinite(avg_pct_change):
                avg_pct_change = 0.0
            predicted_price = data[resource_name].iloc[-1] * (1 + avg_pct_change)
            if not np.isfinite(predicted_price):
                predicted_price = float(data[resource_name].iloc[-1])

        intercept = float(predicted_price)
        coef = [0.0]

    else:
        from sklearn.linear_model import LinearRegression
        model = LinearRegression()
        model.fit(X, y)
        intercept = float(model.intercept_[0])
        coef = model.coef_.flatten().tolist()


    save_regression(resource_name, intercept, coef, steps, count)
    return intercept, coef

def predict_next_price(material, days_ahead=1):
    """Predict 1 day ahead (or fractional days)."""
    model_data = fetch_latest_model(material)
    if model_data is None:
        return None
    intercept, coefficients, features = model_data
    last_step = features["time_steps"][-1]
    coef = coefficients[0]

    steps_ahead = int(days_ahead * 24 // 2)
    predicted = intercept + coef * (last_step + steps_ahead)
    return predicted

def predict_turns_ahead(material, turns=3):
    """Predict X turns ahead (1 turn = 2 hours)."""
    model_data = fetch_latest_model(material)
    if model_data is None:
        return None
    intercept, coefficients, features = model_data
    last_step = features["time_steps"][-1]
    coef = coefficients[0]

    steps_ahead = turns
    predicted = intercept + coef * (last_step + steps_ahead)
    return predicted

