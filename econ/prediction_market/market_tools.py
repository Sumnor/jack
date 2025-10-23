import discord
import io
from discord.ui import View, Button
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
from settings.bot_instance import bot, API_KEY, wrap_as_prefix_command
from databases.sql.databases import fetch_columns, fetch_latest_model, get_alerts_for_user, update_alert, fetch_columnss, fetch_query, execute_query
from econ.prediction_market.regression_models import predict_turns_ahead
from datetime import datetime, timedelta, timezone
from scipy import stats
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge
import warnings
warnings.filterwarnings('ignore')

TABLE_NAME = "materials"
MATERIALS = ["food","uranium","iron","coal","bauxite","oil","lead","steel","aluminum","munitions","gasoline"]

def predict_next_price(material, days_ahead=1):
    """FIXED: Predict next price with proper error handling"""
    turn_data, timestamps = fetch_columnss("materials", material, last_n=500, with_timestamps=True)
    if not turn_data or not timestamps:
        return None

    daily_data = turns_to_daily_averages_with_timestamps(turn_data, timestamps, days=60)
    if len(daily_data) < 10:
        return None

    
    pred = ensemble_predict_multistep(material, daily_data, days_ahead=days_ahead)
    
    if isinstance(pred, list):
        
        return pred[0] if pred and pred[0] is not None else None
    elif pred is not None:
        return pred
    else:
        return None

def turns_to_daily_averages(data, turns_per_day=12):
    if len(data) < turns_per_day:
        return data
    
    daily_averages = []
    for i in range(0, len(data), turns_per_day):
        day_data = data[i:i+turns_per_day]
        if len(day_data) == turns_per_day:
            daily_averages.append(sum(day_data) / len(day_data))
    
    return daily_averages

from datetime import datetime, timedelta, timezone

def turns_to_daily_averages_with_timestamps(data, timestamps, days=30, turns_per_day=12):
    parsed_ts = [
        datetime.fromisoformat(ts.replace("Z", "+00:00")) if isinstance(ts, str) else ts
        for ts in timestamps
    ]

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    filtered = [(price, ts) for price, ts in zip(data, parsed_ts) if ts >= cutoff]

    if not filtered:
        return []

    daily_data = {}
    for price, ts in filtered:
        day_key = ts.date()
        if day_key not in daily_data:
            daily_data[day_key] = []
        daily_data[day_key].append(price)

    daily_averages = [sum(prices) / len(prices) for day, prices in sorted(daily_data.items())]
    return daily_averages

def calculate_forecast_accuracy(hist_preds, actual_data):
    """Calculate model accuracy with proper error handling"""
    errors = []
    
    for pred, actual in zip(hist_preds, actual_data):
        
        if pred is None or actual <= 0:
            continue
            
        
        if isinstance(pred, list):
            pred = pred[0] if pred and pred[0] is not None else None
            if pred is None:
                continue
        
        
        error = abs(pred - actual) / actual * 100
        errors.append(error)
    
    if not errors:
        return 50.0  
    
    
    avg_error = sum(errors) / len(errors)
    accuracy = max(0, min(100, 100 - avg_error))
    
    return accuracy


def create_features(data, window=5):
    """Create technical indicators and features for prediction"""
    features = {}
    data = np.array(data)
    
    
    features['price'] = data[-1]
    features['price_change'] = (data[-1] - data[-2]) / data[-2] if len(data) > 1 else 0
    
    
    if len(data) >= window:
        features['sma'] = np.mean(data[-window:])
        features['price_vs_sma'] = (data[-1] - features['sma']) / features['sma']
    else:
        features['sma'] = data[-1]
        features['price_vs_sma'] = 0
    
    
    if len(data) >= window:
        features['volatility'] = np.std(data[-window:])
        features['volatility_normalized'] = features['volatility'] / np.mean(data[-window:])
    else:
        features['volatility'] = 0
        features['volatility_normalized'] = 0
    
    
    if len(data) >= 3:
        features['momentum'] = (data[-1] - data[-3]) / data[-3]
    else:
        features['momentum'] = 0
    
    
    if len(data) >= 10:
        recent_data = data[-10:]
        features['distance_to_high'] = (max(recent_data) - data[-1]) / data[-1]
        features['distance_to_low'] = (data[-1] - min(recent_data)) / data[-1]
    else:
        features['distance_to_high'] = 0
        features['distance_to_low'] = 0
    
    
    if len(data) >= 7:
        x = np.arange(7)
        y = data[-7:]
        slope, intercept, r_value, p_value, std_err = stats.linregress(x, y)
        features['trend_strength'] = r_value ** 2  
        features['trend_slope'] = slope / np.mean(y)  
    else:
        features['trend_strength'] = 0
        features['trend_slope'] = 0
    
    return features


def save_predictions_to_supabase(material, predictions, confidence_scores=None, model_used="ensemble"):
    """Save predictions to Supabase database"""
    try:
        today = datetime.now(timezone.utc).date()
        
        for i, pred in enumerate(predictions):
            if pred is None:
                continue
                
            target_date = today + timedelta(days=i+1)
            confidence = confidence_scores[i] if confidence_scores and i < len(confidence_scores) else 75.0
            
            query = """
                INSERT INTO predictions (material, target_date, predicted_price, confidence_score, model_used)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING
            """
            execute_query(query, (material, target_date, float(pred), confidence, model_used))
            
    except Exception as e:
        print(f"Error saving predictions to Supabase: {e}")

def load_predictions_from_supabase(material, days=30):
    """Load recent predictions from Supabase"""
    try:
        query = """
            SELECT target_date, predicted_price, confidence_score
            FROM predictions
            WHERE material = %s AND target_date >= CURRENT_DATE
            ORDER BY target_date
            LIMIT %s
        """
        results = fetch_query(query, (material, days))
        return [(row[0], row[1], row[2]) for row in results] if results else []
    except Exception as e:
        print(f"Error loading predictions from Supabase: {e}")
        return []


def ensemble_predict_multistep(material, history, days_ahead=1):
    """FIXED: Multi-step ensemble prediction for dynamic forecasts"""
    if not history or len(history) < 10:
        return simple_predict(history, days_ahead) if history else [None] * days_ahead

    extended_history = history.copy()
    predictions = []

    for day in range(days_ahead):
        try:
            
            features = create_features(extended_history)
            X_current = np.array([list(features.values())])
            
            
            X_train, y_train = [], []
            min_lookback = min(10, len(extended_history) - 1)
            
            for i in range(min_lookback, len(extended_history)):
                f = create_features(extended_history[:i])
                X_train.append(list(f.values()))
                y_train.append(extended_history[i])
            
            if len(X_train) < 5:
                pred = simple_predict(extended_history, days_ahead=1)
                if isinstance(pred, list):
                    pred = pred[0] if pred else extended_history[-1] * 1.01
            else:
                X_train = np.array(X_train)
                y_train = np.array(y_train)

                
                scaler = StandardScaler()
                X_scaled = scaler.fit_transform(X_train)
                
                
                ridge = Ridge(alpha=1.0).fit(X_scaled, y_train)
                
                
                rf = RandomForestRegressor(
                    n_estimators=100, 
                    max_depth=10, 
                    min_samples_split=3,
                    random_state=42 + day  
                ).fit(X_train, y_train)
                
                
                X_scaled_current = scaler.transform(X_current)
                pred_ridge = ridge.predict(X_scaled_current)[0]
                pred_rf = rf.predict(X_current)[0]

                
                recent_volatility = np.std(extended_history[-10:]) if len(extended_history) >= 10 else np.std(extended_history)
                recent_trend = np.mean(np.diff(extended_history[-5:])) if len(extended_history) >= 5 else 0
                
                
                if abs(recent_trend) > recent_volatility * 0.1:
                    
                    pred = 0.7 * pred_ridge + 0.3 * pred_rf
                else:
                    
                    pred = 0.3 * pred_ridge + 0.7 * pred_rf

                
                noise_factor = 0.02 * (day + 1) * recent_volatility
                noise = np.random.normal(0, noise_factor)
                pred += noise

                
                if day > 7:
                    long_term_mean = np.mean(history[-30:]) if len(history) >= 30 else np.mean(history)
                    reversion_strength = min(0.3, (day - 7) * 0.05)
                    pred = pred * (1 - reversion_strength) + long_term_mean * reversion_strength

                
                recent_range = max(extended_history[-20:]) - min(extended_history[-20:]) if len(extended_history) >= 20 else extended_history[-1] * 0.5
                lower_bound = min(extended_history[-10:]) - recent_range * 0.5 if len(extended_history) >= 10 else extended_history[-1] * 0.5
                upper_bound = max(extended_history[-10:]) + recent_range * 0.5 if len(extended_history) >= 10 else extended_history[-1] * 2
                pred = max(lower_bound, min(upper_bound, pred))
            
            predictions.append(max(0.1, pred))  
            extended_history.append(pred)

        except Exception as e:
            
            fallback = simple_predict(extended_history, days_ahead=1)
            if isinstance(fallback, list):
                fallback = fallback[0] if fallback else extended_history[-1] * 1.01
            predictions.append(max(0.1, fallback))
            extended_history.append(predictions[-1])
    
    return predictions

def simple_predict(history, days_ahead=1):
    """FIXED: Simple prediction fallback"""
    
    flat_history = []
    for h in history:
        if isinstance(h, list):
            flat_history.extend(h)
        else:
            flat_history.append(float(h))
    history = flat_history

    if len(history) < 3:
        base_price = history[-1] if history else 1.0
        return [base_price * (1 + np.random.normal(0, 0.02)) for _ in range(days_ahead)]

    
    recent_trend = (history[-1] - history[-min(5, len(history))]) / min(5, len(history))
    mean_val = np.mean(history[-min(10, len(history)):])
    std_val = np.std(history[-min(10, len(history)):])

    predictions = []
    last_price = history[-1]
    
    for day in range(days_ahead):
        
        trend_component = recent_trend * (0.9 ** day)
        
        
        reversion_strength = 0.1 * (day + 1)
        reversion_component = (mean_val - last_price) * reversion_strength
        
        
        noise = np.random.normal(0, std_val * 0.05)
        
        pred = last_price + trend_component + reversion_component + noise
        pred = max(0.1, pred)  
        
        predictions.append(pred)
        last_price = pred
    
    return predictions[0] if days_ahead == 1 else predictions



def detect_trading_signals(prices, predictions=None):
    """FIXED: Detect buy/sell signals based on technical analysis"""
    if len(prices) < 10:
        return [], []
    
    prices = np.array(prices)
    buy_signals = []
    sell_signals = []
    
    
    sma_short = []
    sma_long = []
    
    for i in range(len(prices)):
        if i >= 4:
            sma_short.append(np.mean(prices[max(0, i-4):i+1]))
        else:
            sma_short.append(prices[i])
            
        if i >= 9:
            sma_long.append(np.mean(prices[max(0, i-9):i+1]))
        else:
            sma_long.append(prices[i])
    
    
    def calculate_rsi(prices, window=14):
        deltas = np.diff(prices)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        rsi_values = []
        for i in range(len(prices)):
            if i < window:
                rsi_values.append(50)  
            else:
                start_idx = max(0, i-window)
                avg_gain = np.mean(gains[start_idx:i]) if start_idx < i else 0
                avg_loss = np.mean(losses[start_idx:i]) if start_idx < i else 0
                
                if avg_loss == 0:
                    rsi_values.append(100)
                else:
                    rs = avg_gain / avg_loss
                    rsi = 100 - (100 / (1 + rs))
                    rsi_values.append(rsi)
        return rsi_values
    
    rsi = calculate_rsi(prices)
    
    
    for i in range(10, len(prices)):
        
        buy_conditions = [
            
            len(sma_short) > i and len(sma_long) > i and i > 0 and 
            sma_short[i] > sma_long[i] and sma_short[i-1] <= sma_long[i-1],
            
            
            len(rsi) > i and rsi[i] < 30 and (i == 0 or rsi[i] > rsi[i-1]),
            
            
            i >= 5 and prices[i] > prices[i-1] and 
            prices[i-1] == min(prices[max(0, i-5):i]),
            
            
            i >= 5 and prices[i] > max(prices[max(0, i-5):i-1]) and 
            len(sma_long) > i and prices[i] > sma_long[i] * 1.02
        ]
        
        if sum(buy_conditions) >= 2:  
            buy_signals.append(i)
    
        
        sell_conditions = [
            
            len(sma_short) > i and len(sma_long) > i and i > 0 and
            sma_short[i] < sma_long[i] and sma_short[i-1] >= sma_long[i-1],
            
            
            len(rsi) > i and rsi[i] > 70 and (i == 0 or rsi[i] < rsi[i-1]),
            
            
            i >= 5 and prices[i] < prices[i-1] and 
            prices[i-1] == max(prices[max(0, i-5):i]),
            
            
            i >= 5 and prices[i] < min(prices[max(0, i-5):i-1]) and 
            len(sma_long) > i and prices[i] < sma_long[i] * 0.98
        ]
        
        if sum(sell_conditions) >= 2:
            sell_signals.append(i)
    
    return buy_signals, sell_signals


def predict_trading_signals(material, future_predictions):
    """Predict future buy/sell signals based on forecasted prices"""
    if not future_predictions or len(future_predictions) < 10:
        return [], []
    
    
    clean_predictions = [float(p) for p in future_predictions if p is not None]
    
    if len(clean_predictions) < 10:
        return [], []
    
    
    buy_sigs, sell_sigs = detect_trading_signals(clean_predictions)
    return buy_sigs, sell_sigs

def generate_predictions(material, days=30):
    """FIXED: Generate predictions and save to Supabase"""
    turn_data, timestamps = fetch_columnss("materials", material, last_n=500, with_timestamps=True)
    if not turn_data or not timestamps:
        return [None] * days
        
    daily_data = turns_to_daily_averages_with_timestamps(turn_data, timestamps, days=60)
    if len(daily_data) < 10:
        return [None] * days

    
    predictions = ensemble_predict_multistep(material, daily_data, days_ahead=days)
    
    
    confidence_scores = []
    for i, pred in enumerate(predictions):
        if pred is not None:
            
            base_confidence = max(50, 90 - (i * 2))
            
            
            recent_volatility = np.std(daily_data[-10:]) if len(daily_data) >= 10 else np.std(daily_data)
            volatility_penalty = min(20, recent_volatility * 2)
            
            confidence = max(30, base_confidence - volatility_penalty)
            confidence_scores.append(confidence)
        else:
            confidence_scores.append(0)
    
    
    valid_predictions = [p for p in predictions if p is not None]
    if valid_predictions:
        save_predictions_to_supabase(material, valid_predictions, confidence_scores, "ensemble")
    
    return predictions


def generate_historical_predictions(material, daily_data):
    """Generate historical predictions for accuracy testing"""
    if len(daily_data) < 20:
        return []
    
    historical_preds = []
    for i in range(10, len(daily_data) - 5):  
        subset = daily_data[:i]
        pred = ensemble_predict_multistep(material, subset, days_ahead=1)
        
        
        if isinstance(pred, list):
            pred = pred[0] if pred and pred[0] is not None else None
        
        historical_preds.append(pred)
    
    return historical_preds

def create_graph(data, avg=None, title="Material Price", view_type="day"):
    """Create a basic price graph"""
    plt.figure(figsize=(10, 6))
    plt.plot(data, marker='o', linewidth=2, markersize=4, color='blue')
    
    if avg is not None:
        plt.axhline(y=avg, color='red', linestyle='--', alpha=0.7, label=f'Average: {avg:.2f}')
        plt.legend()
    
    plt.title(title)
    plt.xlabel("Days" if view_type == "day" else "Turns")
    plt.ylabel("Price")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=100)
    plt.close()
    buf.seek(0)
    return buf

def create_graph_with_predictions(daily_data, material, avg, title="Material Price"):
    """FIXED: Create enhanced graph with predictions and trading signals"""
    
    predictions = generate_predictions(material, days=30)
    
    
    valid_predictions = [p for p in predictions if p is not None]
    
    
    hist_buy, hist_sell = detect_trading_signals(daily_data)
    future_buy, future_sell = predict_trading_signals(material, valid_predictions)
    
    plt.figure(figsize=(14, 8))
    
    
    days_hist = list(range(1, len(daily_data) + 1))
    plt.plot(days_hist, daily_data, marker='o', linewidth=2, markersize=4, 
             color='blue', label='Historical Prices')
    
    
    if valid_predictions:
        days_pred = list(range(len(daily_data) + 1, len(daily_data) + len(valid_predictions) + 1))
        plt.plot(days_pred, valid_predictions, marker='s', linewidth=2, markersize=3, 
                 color='purple', alpha=0.7, label='Predictions', linestyle='--')
    
    
    if avg is not None:
        total_days = len(daily_data) + len(valid_predictions)
        plt.axhline(y=avg, color='red', linestyle=':', alpha=0.7, label=f'Historical Avg: {avg:.2f}')
    
    
    for buy_idx in hist_buy:
        if buy_idx < len(daily_data):
            plt.scatter(buy_idx + 1, daily_data[buy_idx], color='green', s=100, 
                       marker='^', label='Buy Signal' if buy_idx == hist_buy[0] else "", zorder=5)
    
    for sell_idx in hist_sell:
        if sell_idx < len(daily_data):
            plt.scatter(sell_idx + 1, daily_data[sell_idx], color='red', s=100, 
                       marker='v', label='Sell Signal' if sell_idx == hist_sell[0] else "", zorder=5)
    
    
    for buy_idx in future_buy:
        if buy_idx < len(valid_predictions):
            plt.scatter(len(daily_data) + buy_idx + 1, valid_predictions[buy_idx], 
                       color='green', s=80, marker='^', alpha=0.6, zorder=5)
    
    for sell_idx in future_sell:
        if sell_idx < len(valid_predictions):
            plt.scatter(len(daily_data) + sell_idx + 1, valid_predictions[sell_idx], 
                       color='red', s=80, marker='v', alpha=0.6, zorder=5)
    
    plt.title(f"{title} - Price Forecast with Trading Signals")
    plt.xlabel("Days")
    plt.ylabel("Price")
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=100)
    plt.close()
    buf.seek(0)
    
    return buf, hist_buy, hist_sell, future_buy, future_sell

async def send_trading_signals_dm(interaction, material, hist_buy, hist_sell, future_buy, future_sell):
    """Send trading signals to user via DM"""
    try:
        signals_text = f"**Trading Signals for {material.capitalize()}**\n\n"
        
        if hist_buy or hist_sell:
            signals_text += "**Recent Historical Signals:**\n"
            for buy_idx in hist_buy[-3:]:  
                signals_text += f"🟢 BUY signal at day {buy_idx + 1}\n"
            for sell_idx in hist_sell[-3:]:  
                signals_text += f"🔴 SELL signal at day {sell_idx + 1}\n"
            signals_text += "\n"
        
        if future_buy or future_sell:
            signals_text += "**Predicted Signals (Next 30 Days):**\n"
            for buy_idx in future_buy[:5]:  
                signals_text += f"🟢 Predicted BUY on day +{buy_idx + 1}\n"
            for sell_idx in future_sell[:5]:  
                signals_text += f"🔴 Predicted SELL on day +{sell_idx + 1}\n"
        
        if not any([hist_buy, hist_sell, future_buy, future_sell]):
            signals_text += "No clear trading signals detected at this time.\n"
        
        signals_text += "\n⚠️ *These are algorithmic predictions based on technical analysis. Always do your own research and trade responsibly.*"
        
        await interaction.user.send(signals_text)
    except discord.Forbidden:
        
        pass
    except Exception:
        
        pass

async def send_market_digest(interaction: discord.Interaction):
    all_data = {}
    for mat in MATERIALS:
        turn_data, timestamps = fetch_columnss("materials", mat, last_n=360, with_timestamps=True)
        if turn_data and timestamps:
            df = pd.DataFrame({"price": turn_data}, index=pd.to_datetime(timestamps))
            df = df.sort_index()
            daily_data = df["price"].resample("1D").mean().dropna()
            if not daily_data.empty:
                all_data[mat] = daily_data

    if not all_data:
        await interaction.followup.send("⚠️ No data available for market digest.", ephemeral=True)
        return

    plt.figure(figsize=(12, 6))
    colors = plt.cm.get_cmap("tab10", len(all_data))
    for idx, (mat, series) in enumerate(all_data.items()):
        plt.plot(series.index, series.values, label=mat.capitalize(), color=colors(idx))
    plt.title("Market Digest: Last 30 Days")
    plt.xlabel("Date")
    plt.ylabel("Average Price")
    plt.grid(True)
    plt.legend()
    buf = io.BytesIO()
    plt.savefig(buf, format="png", bbox_inches="tight")
    plt.close()
    buf.seek(0)
    file = discord.File(buf, filename="market_digest.png")

    highs, lows, risers, fallers = [], [], [], []
    for mat, series in all_data.items():
        high, low = series.max(), series.min()
        change = series.iloc[-1] - series.iloc[0]
        highs.append((mat, high))
        lows.append((mat, low))
        if change > 0:
            risers.append((mat, change))
        elif change < 0:
            fallers.append((mat, abs(change)))

    top_risers = sorted(risers, key=lambda x: x[1], reverse=True)[:3]
    top_fallers = sorted(fallers, key=lambda x: x[1], reverse=True)[:3]
    top_highs = sorted(highs, key=lambda x: x[1], reverse=True)[:3]
    top_lows = sorted(lows, key=lambda x: x[1])[:3]

    summary = "**Top Risers:** " + ", ".join(f"{mat.capitalize()} (+{chg:.2f})" for mat, chg in top_risers) + "\n"
    summary += "**Top Fallers:** " + ", ".join(f"{mat.capitalize()} (-{chg:.2f})" for mat, chg in top_fallers) + "\n"
    summary += "**Highest Prices:** " + ", ".join(f"{mat.capitalize()} ({price:.2f})" for mat, price in top_highs) + "\n"
    summary += "**Lowest Prices:** " + ", ".join(f"{mat.capitalize()} ({price:.2f})" for mat, price in top_lows)

    embed = discord.Embed(
        title="📊 Daily Market Digest",
        description=summary,
        color=discord.Color.blue()
    )
    embed.set_image(url="attachment://market_digest.png")
    view = View(timeout=None)
    view.add_item(Button(label="Back", style=discord.ButtonStyle.danger, custom_id="overview"))
    await interaction.edit_original_response(embed=embed, view=view, attachments=[file])


class GraphOverviewView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(Button(label="View Material Graphs", style=discord.ButtonStyle.primary, custom_id="graphs_overview"))
        self.add_item(Button(label="Market Stats & Top Movers", style=discord.ButtonStyle.success, custom_id="market_stats"))
        self.add_item(Button(label="Market Digest", style=discord.ButtonStyle.primary, custom_id="market_digest_main"))

class MarketStatsView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(Button(label="Back", style=discord.ButtonStyle.danger, custom_id="overview"))
        self.add_item(Button(label="Heat Map", style=discord.ButtonStyle.success, custom_id="market_heat"))
        self.add_item(Button(label="Volatility", style=discord.ButtonStyle.secondary, custom_id="market_volatility"))
        self.add_item(Button(label="Most Stable", style=discord.ButtonStyle.secondary, custom_id="market_stable"))
        self.add_item(Button(label="Most Profitable", style=discord.ButtonStyle.success, custom_id="market_profitable"))
        self.add_item(Button(label="Trends", style=discord.ButtonStyle.primary, custom_id="market_trends"))

class MaterialView(View):
    def __init__(self, mat):
        super().__init__(timeout=None)
        self.mat = mat
        self.add_item(Button(label="Back", style=discord.ButtonStyle.danger, custom_id="graphs_overview"))
        self.add_item(Button(label="Alert Above +20%", style=discord.ButtonStyle.success, custom_id=f"alert_high_{mat}"))
        self.add_item(Button(label="Alert Below -20%", style=discord.ButtonStyle.danger, custom_id=f"alert_low_{mat}"))
        self.add_item(Button(label="Simulate Trade", style=discord.ButtonStyle.success, custom_id=f"simulate_{mat}"))
        self.add_item(Button(label="Turn View", style=discord.ButtonStyle.primary, custom_id=f"turn_{mat}"))
        self.add_item(Button(label="Forecast", style=discord.ButtonStyle.primary, custom_id=f"forecast_{mat}"))

class TurnView(View):
    def __init__(self, mat, show_graph=True):
        super().__init__(timeout=None)
        self.mat = mat
        self.show_graph = show_graph
        self.add_item(Button(label="Back", style=discord.ButtonStyle.danger, custom_id=f"material_{mat}"))
        self.add_item(Button(label="Toggle Graph/Table", style=discord.ButtonStyle.secondary, custom_id=f"toggle_{mat}"))
        self.add_item(Button(label="Simulate Trade", style=discord.ButtonStyle.success, custom_id=f"simulate_{mat}"))


@bot.tree.command(name="market_tool", description="All in one market tool")
async def market_tool(interaction: discord.Interaction):
    embed = discord.Embed(
        title="Market Tools",
        description="Click below to view all material graphs.",
        color=discord.Color.blue()
    )
    await interaction.response.send_message(embed=embed, view=GraphOverviewView())

bot.command(name="market_tool")(wrap_as_prefix_command(market_tool.callback))

@bot.event
async def on_interaction(interaction: discord.Interaction):
    if interaction.type != discord.InteractionType.component:
        return
    custom_id = interaction.data["custom_id"]

    await interaction.response.defer()

    if custom_id == "overview":
        embed = discord.Embed(
            title="Market Tools",
            description="Click below to view all material graphs.",
            color=discord.Color.blue()
        )
        embed.set_image(url=None)
        await interaction.edit_original_response(embed=embed, view=GraphOverviewView(), attachments=[])
        return

    if custom_id == "market_digest_main":
        await send_market_digest(interaction)
        return

    if custom_id == "market_stats":
        embed = discord.Embed(
            title="Market Stats",
            description="All the stats of the market",
            color=discord.Color.gold()
        )
        await interaction.edit_original_response(embed=embed, view=MarketStatsView())
        return
    
    if custom_id == "market_heat":
        embed = discord.Embed(
            title="Market Stats Heatmap",
            description="Current prices relative to recent averages",
            color=discord.Color.gold()
        )

        heatmap_lines = []
        for mat in MATERIALS:

            turn_data = fetch_columns(TABLE_NAME, mat, last_n=50)
            if not turn_data:
                continue
            

            if len(turn_data) > 1:
                avg = sum(turn_data[:-1]) / len(turn_data[:-1])
            else:
                avg = turn_data[0]
            latest = turn_data[-1]
            

            pct_diff = ((latest - avg) / avg * 100) if avg > 0 else 0
            

            if pct_diff >= 5:
                emoji = "🟢🔥"
            elif pct_diff >= 1:
                emoji = "🟢"
            elif pct_diff <= -5:
                emoji = "🔴🧊"
            elif pct_diff <= -1:
                emoji = "🔴"
            else:
                emoji = "🟡"
                
            heatmap_lines.append(f"{emoji} {mat.capitalize()}: {latest:.0f} ({pct_diff:+.1f}% from avg {avg:.0f})")

        embed.add_field(name="Heatmap", value="\n".join(heatmap_lines), inline=False)
        await interaction.edit_original_response(embed=embed, view=MarketStatsView())
        return

    if custom_id == "market_volatility":
        volatility_list = []
        for mat in MATERIALS:

            turn_data = fetch_columns(TABLE_NAME, mat, last_n=50)
            if not turn_data:
                continue
            

            volatility = np.std(turn_data)
            mean_price = np.mean(turn_data)
            

            cv = (volatility / mean_price * 100) if mean_price > 0 else 0
            
            volatility_list.append((mat, volatility, cv, mean_price))

        volatility_list.sort(key=lambda x: x[1], reverse=True)
        top_volatile = "\n".join(
            f"{mat.capitalize()}: SD = {vol:.1f} ({cv:.1f}% of avg {avg:.0f})" 
            for mat, vol, cv, avg in volatility_list[:5]
        )

        embed = discord.Embed(
            title="Top 5 Most Volatile Resources",
            description=top_volatile,
            color=discord.Color.orange()
        )
        await interaction.edit_original_response(embed=embed, view=MarketStatsView())
        return

    if custom_id == "market_stable":
        stability_list = []
        for mat in MATERIALS:

            turn_data = fetch_columns(TABLE_NAME, mat, last_n=50)
            if not turn_data:
                continue
            
            volatility = np.std(turn_data)
            mean_price = np.mean(turn_data)
            cv = (volatility / mean_price * 100) if mean_price > 0 else 0
            
            stability_list.append((mat, volatility, cv, mean_price))
        
        stability_list.sort(key=lambda x: x[1])
        top_stable = "\n".join(
            f"{mat.capitalize()}: SD = {vol:.1f} ({cv:.1f}% of avg {avg:.0f})" 
            for mat, vol, cv, avg in stability_list[:5]
        )

        embed = discord.Embed(
            title="Top 5 Most Stable Resources",
            description=top_stable,
            color=discord.Color.blue()
        )
        await interaction.edit_original_response(embed=embed, view=MarketStatsView())
        return

    if custom_id == "market_profitable":
        performance = []
        for mat in MATERIALS:
            turn_data = fetch_columns(TABLE_NAME, mat, last_n=50)
            if not turn_data:
                continue
            

            first_price = turn_data[0]
            latest_price = turn_data[-1]
            lowest_price = min(turn_data)
            highest_price = max(turn_data)
            

            max_profit_pct = ((highest_price - lowest_price) / lowest_price * 100) if lowest_price > 0 else 0
            

            trend_pct = ((latest_price - first_price) / first_price * 100) if first_price > 0 else 0
            
            performance.append((mat, max_profit_pct, trend_pct, lowest_price, highest_price))

        performance.sort(key=lambda x: x[1], reverse=True)
        top_perf = "\n".join(
            f"{mat.capitalize()}: Max gain {max_pct:.1f}% (Low: {low:.0f}, High: {high:.0f}, Trend: {trend:+.1f}%)" 
            for mat, max_pct, trend, low, high in performance[:5]
        )

        embed = discord.Embed(
            title="Top 5 Most Profitable Resources",
            description=top_perf,
            color=discord.Color.green()
        )
        await interaction.edit_original_response(embed=embed, view=MarketStatsView())
        return

    if custom_id == "market_trends":
        trend_lines = []
        for mat in MATERIALS:
            turn_data = fetch_columns(TABLE_NAME, mat, last_n=20)
            if not turn_data:
                continue
            

            if len(turn_data) == 1:
                trend_pct = 0
            elif len(turn_data) == 2:
                trend_pct = ((turn_data[1] - turn_data[0]) / turn_data[0] * 100) if turn_data[0] > 0 else 0
            else:

                first_half = turn_data[:len(turn_data)//2]
                second_half = turn_data[len(turn_data)//2:]
                
                first_avg = sum(first_half) / len(first_half)
                second_avg = sum(second_half) / len(second_half)
                
                trend_pct = ((second_avg - first_avg) / first_avg * 100) if first_avg > 0 else 0
            
            if trend_pct > 2:
                trend_lines.append(f"{mat.capitalize()}: ⬆️ Strong uptrend (+{trend_pct:.1f}%)")
            elif trend_pct > 0.5:
                trend_lines.append(f"{mat.capitalize()}: ↗️ Uptrend (+{trend_pct:.1f}%)")
            elif trend_pct < -2:
                trend_lines.append(f"{mat.capitalize()}: ⬇️ Strong downtrend ({trend_pct:.1f}%)")
            elif trend_pct < -0.5:
                trend_lines.append(f"{mat.capitalize()}: ↘️ Downtrend ({trend_pct:.1f}%)")
            else:
                trend_lines.append(f"{mat.capitalize()}: ➡️ Sideways ({trend_pct:+.1f}%)")

        embed = discord.Embed(
            title="Market Trends (Recent Data)",
            description="\n".join(trend_lines),
            color=discord.Color.purple()
        )
        await interaction.edit_original_response(embed=embed, view=MarketStatsView())
        return

    if custom_id == "graphs_overview":
        buf = io.BytesIO()
        fig, axs = plt.subplots(4, 3, figsize=(12, 9))
        axs = axs.flatten()

        for idx, mat in enumerate(MATERIALS):
            turn_data, timestamps = fetch_columnss(TABLE_NAME, mat, last_n=1000, with_timestamps=True)
            if not turn_data or not timestamps:
                continue

            daily_data = turns_to_daily_averages_with_timestamps(turn_data, timestamps, days=7)
            if daily_data and len(daily_data) > 1:
                days = list(range(1, len(daily_data) + 1))
                axs[idx].plot(days, daily_data, marker='o', linewidth=2, markersize=4)
                axs[idx].set_title(mat.capitalize(), fontsize=10)
                axs[idx].set_xlabel("Days", fontsize=8)
                axs[idx].set_ylabel("Price", fontsize=8)
                axs[idx].grid(True, alpha=0.3)
                axs[idx].tick_params(labelsize=7)
            else:
                recent_turns, _ = fetch_columnss(TABLE_NAME, mat, last_n=24, with_timestamps=True)
                if recent_turns:
                    axs[idx].plot(recent_turns, marker='o', linewidth=1, markersize=3)
                    axs[idx].set_title(f"{mat.capitalize()} (turns)", fontsize=10)
                    axs[idx].set_xlabel("Turns", fontsize=8)
                    axs[idx].set_ylabel("Price", fontsize=8)
                    axs[idx].grid(True, alpha=0.3)
                    axs[idx].tick_params(labelsize=7)

        plt.tight_layout(pad=2.0)
        plt.savefig(buf, format='png', dpi=100)
        plt.close()
        buf.seek(0)

        file = discord.File(buf, filename="overview.png")
        embed = discord.Embed(
            title="Material Graphs Overview",
            description="Last 7 days (timestamp-based daily averages) for all materials",
            color=discord.Color.green()
        )
        embed.set_image(url="attachment://overview.png")

        view = View(timeout=None)
        for mat in MATERIALS:
            view.add_item(Button(label=mat.capitalize(), style=discord.ButtonStyle.secondary, custom_id=f"material_{mat}"))
        view.add_item(Button(label="Back", style=discord.ButtonStyle.danger, custom_id="overview"))

        await interaction.edit_original_response(embed=embed, view=view, attachments=[file])
        return

    if custom_id.startswith("simulate_"):
        mat = custom_id.split("_")[1]
        latest_turn_data = fetch_columns(TABLE_NAME, mat, last_n=1)
        if not latest_turn_data:
            await interaction.followup.send("No recent price data available.", ephemeral=True)
            return
        current_price = latest_turn_data[-1]

        predicted_price = predict_next_price(mat, days_ahead=1)
        if predicted_price is None:
            await interaction.followup.send("Unable to predict future price.", ephemeral=True)
            return

        amounts = [100, 500, 1000, 5000]
        lines = []
        for amt in amounts:
            cost = amt * current_price
            future_value = amt * predicted_price
            profit = future_value - cost
            lines.append(f"{amt:,} units: Cost = {cost:,.2f}, Future Value = {future_value:,.2f}, Profit = {profit:,.2f}")

        embed = discord.Embed(
            title=f"{mat.capitalize()} Trade Simulation",
            description=f"Current Price: {current_price:.2f} | Predicted Price (1 day ahead): {predicted_price:.2f}",
            color=discord.Color.blurple()
        )
        embed.add_field(name="Simulation (Buy & Sell Profit/Loss)", value="\n".join(lines), inline=False)
        await interaction.edit_original_response(embed=embed)
        return

    if custom_id.startswith("material_"):
        mat = custom_id.split("_")[1]
        turn_data, timestamps = fetch_columnss(TABLE_NAME, mat, last_n=1000, with_timestamps=True)
        if not turn_data or not timestamps:
            await interaction.followup.send(f"No data available for {mat}.", ephemeral=True)
            return

        daily_data = turns_to_daily_averages_with_timestamps(turn_data, timestamps, days=30)
        if not daily_data:
            await interaction.followup.send(f"Not enough data to create daily averages for {mat}.", ephemeral=True)
            return

        avg = sum(daily_data)/len(daily_data)
        buf = create_graph(daily_data, avg, title=mat.capitalize(), view_type="day")
        file = discord.File(buf, filename=f"{mat}_30d.png")

        predicted_price = predict_next_price(mat, days_ahead=1)
        predicted_next_turn = predict_turns_ahead(mat, turns=3)

        embed = discord.Embed(
            title=f"{mat.capitalize()} Market Data (Last 30 Days)",
            description=(
                f"Highest: {max(daily_data):.2f}\n"
                f"Lowest: {min(daily_data):.2f}\n"
                f"Average: {avg:.2f}\n"
                f"Predicted 1 day ahead: {predicted_price:.2f}\n"
                f"Predicted next turn: {predicted_next_turn}"
            ),
            color=discord.Color.gold()
        )
        embed.set_image(url=f"attachment://{mat}_30d.png")
        await interaction.edit_original_response(embed=embed, view=MaterialView(mat), attachments=[file])
        return

    if custom_id.startswith("alert_high_") or custom_id.startswith("alert_low_"):
        mat = custom_id.split("_")[2]
        user_alerts = get_alerts_for_user(interaction.user.id)
        current_mode = user_alerts.get(mat, 0)

        if custom_id.startswith("alert_high_"):
            if current_mode in (0,2):
                new_mode = current_mode + 1
            elif current_mode in (1,3):
                new_mode = current_mode - 1
        else:
            if current_mode in (0,1):
                new_mode = current_mode + 2
            elif current_mode in (2,3):
                new_mode = current_mode - 2

        update_alert(interaction.user.id, mat, new_mode)
        msg = f"🔔 {mat.capitalize()} alert updated: `{new_mode}` (0=Off, 1=Rise, 2=Fall, 3=Both)"
        await interaction.followup.send(msg, ephemeral=True)
        return

    if custom_id.startswith("turn_") or custom_id.startswith("toggle_"):
        mat = custom_id.split("_")[1]
        show_graph = not custom_id.startswith("toggle_")
        data_12 = fetch_columns(TABLE_NAME, mat, last_n=12)
        if not data_12:
            await interaction.followup.send(f"No turn data available for {mat}.", ephemeral=True)
            return
            
        highest, lowest, avg = max(data_12), min(data_12), sum(data_12)/len(data_12)
        if show_graph:
            buf = create_graph(data_12, title=f"{mat.capitalize()} Turn View", view_type="turn")
            file = discord.File(buf, filename=f"{mat}_turns.png")
            embed = discord.Embed(
                title=f"{mat.capitalize()} Turn View (Graph)",
                description=f"Highest: {highest:.2f}\nLowest: {lowest:.2f}\nAverage: {avg:.2f}",
                color=discord.Color.orange()
            )
            embed.set_image(url=f"attachment://{mat}_turns.png")
            await interaction.edit_original_response(embed=embed, view=TurnView(mat, show_graph=True), attachments=[file])
        else:
            table_text = "Turn | Price\n" + "\n".join(f"{i+1:2d} | {val:.2f}" for i, val in enumerate(data_12))
            embed = discord.Embed(
                title=f"{mat.capitalize()} Turn View (Table)",
                description=f"Highest: {highest:.2f}\nLowest: {lowest:.2f}\nAverage: {avg:.2f}\n\n```\n{table_text}\n```",
                color=discord.Color.orange()
            )
            await interaction.edit_original_response(embed=embed, view=TurnView(mat, show_graph=False), attachments=[])
        return

    if custom_id.startswith("signals_"):
        mat = custom_id.split("_")[1]
        turn_data, timestamps = fetch_columnss(TABLE_NAME, mat, last_n=1000, with_timestamps=True)
        if not turn_data or not timestamps:
            await interaction.followup.send(f"No data available for {mat}.", ephemeral=True)
            return
        
        daily_data = turns_to_daily_averages_with_timestamps(turn_data, timestamps, days=30)
        if not daily_data:
            await interaction.followup.send(f"Not enough data to analyze {mat}.", ephemeral=True)
            return
        
        
        hist_buy, hist_sell = detect_trading_signals(daily_data)
        future_preds = generate_predictions(mat, days=30)
        future_buy, future_sell = predict_trading_signals(mat, future_preds)
        
        
        await send_trading_signals_dm(interaction, mat, hist_buy, hist_sell, future_buy, future_sell)
        
        
        signal_strength = len(hist_buy) + len(hist_sell) + len(future_buy) + len(future_sell)
        strength_desc = "Low" if signal_strength < 3 else "Medium" if signal_strength < 6 else "High"
        
        analysis_text = (
            f"**Signal Re-analysis Complete for {mat.capitalize()}**\n\n"
            f"Signal Strength: {strength_desc} ({signal_strength} total signals)\n"
            f"Historical Buy Signals: {len(hist_buy)}\n"
            f"Historical Sell Signals: {len(hist_sell)}\n"
            f"Predicted Buy Signals: {len(future_buy)}\n"
            f"Predicted Sell Signals: {len(future_sell)}\n\n"
            f"Updated signals sent to your DMs!"
        )
        
        embed = discord.Embed(
            title="Trading Signal Analysis",
            description=analysis_text,
            color=discord.Color.blue()
        )
        
        await interaction.followup.send(embed=embed, ephemeral=True)
        return

    if custom_id.startswith("forecast_"):
        mat = custom_id.split("_")[1]
        turn_data, timestamps = fetch_columnss(TABLE_NAME, mat, last_n=1000, with_timestamps=True)
        if not turn_data or not timestamps:
            await interaction.followup.send(f"No data available for {mat}.", ephemeral=True)
            return

        
        daily_data = turns_to_daily_averages_with_timestamps(turn_data, timestamps, days=30)
        if not daily_data:
            await interaction.followup.send(f"Not enough data to create daily averages for {mat}.", ephemeral=True)
            return

        avg = sum(daily_data) / len(daily_data)

        
        buf, hist_buy, hist_sell, future_buy, future_sell = create_graph_with_predictions(
            daily_data, mat, avg, title=mat.capitalize()
        )
        file = discord.File(buf, filename=f"{mat}_forecast.png")

        
        forecast_preds = generate_predictions(mat, days=30)
        
        forecast_preds_flat = [p[0] if isinstance(p, list) else p for p in forecast_preds if p is not None]
        forecast_avg = sum(forecast_preds_flat) / len(forecast_preds_flat) if forecast_preds_flat else None
        forecast_std = np.std(forecast_preds_flat) if len(forecast_preds_flat) > 1 else 0

        
        hist_preds = generate_historical_predictions(mat, daily_data)
        accuracy_score = calculate_forecast_accuracy(hist_preds, daily_data[10:10+len(hist_preds)])
        confidence = max(50, min(95, accuracy_score))

        
        signal_summary = ""
        if hist_buy or hist_sell:
            signal_summary += f"Recent signals: {len(hist_buy)} buy, {len(hist_sell)} sell\n"
        if future_buy or future_sell:
            signal_summary += f"Predicted signals: {len(future_buy)} buy, {len(future_sell)} sell\n"
        else:
            signal_summary += "No clear trading signals predicted\n"

        forecast_desc = (
            f"**Enhanced 30-Day Forecast:**\n"
            f"Current Price: {daily_data[-1]:.2f}\n"
            f"Predicted Average: {forecast_avg:.2f} ± {forecast_std:.2f}\n"
            f"Model Accuracy: {accuracy_score:.1f}%\n"
            f"Confidence Level: {confidence:.0f}%\n\n"
            f"**Trading Signals:**\n"
            f"{signal_summary}\n"
            f"**Legend:**\n"
            f"🔵 Historical prices | 🟠 Past predictions\n"
            f"🟣 Future forecasts | 🟢 Buy signals | 🔴 Sell signals\n"
            f"*Transparent signals = predictions | Bold = historical*\n\n"
            f"📩 *Trading signals sent to your DMs*"
        )

        embed = discord.Embed(
            title=f"{mat.capitalize()} - AI Trading Analysis",
            description=forecast_desc,
            color=discord.Color.purple()
        )
        embed.set_image(url=f"attachment://{mat}_forecast.png")

        view = MaterialView(mat)
        await interaction.edit_original_response(embed=embed, view=view, attachments=[file])

        
        await send_trading_signals_dm(interaction, mat, hist_buy, hist_sell, future_buy, future_sell)
        return

    if custom_id.startswith("material_"):
        mat = custom_id.split("_")[1]
        turn_data, timestamps = fetch_columnss(TABLE_NAME, mat, last_n=1000, with_timestamps=True)
        if not turn_data or not timestamps:
            await interaction.followup.send(f"No data available for {mat}.", ephemeral=True)
            return

        daily_data = turns_to_daily_averages_with_timestamps(turn_data, timestamps, days=30)
        if not daily_data:
            await interaction.followup.send(f"Not enough data to create daily averages for {mat}.", ephemeral=True)
            return

        avg = sum(daily_data)/len(daily_data)
        buf = create_graph(daily_data, avg, title=mat.capitalize(), view_type="day")
        file = discord.File(buf, filename=f"{mat}_30d.png")

        predicted_price = predict_next_price(mat, days_ahead=1)
        predicted_next_turn = predict_turns_ahead(mat, turns=3)

        embed = discord.Embed(
            title=f"{mat.capitalize()} Market Data (Last 30 Days)",
            description=(
                f"Highest: {max(daily_data):.2f}\n"
                f"Lowest: {min(daily_data):.2f}\n"
                f"Average: {avg:.2f}\n"
                f"Predicted 1 day ahead: {predicted_price:.2f}\n"
                f"Predicted next turn: {predicted_next_turn}"
            ),
            color=discord.Color.gold()
        )
        embed.set_image(url=f"attachment://{mat}_30d.png")
        await interaction.edit_original_response(embed=embed, view=MaterialView(mat), attachments=[file])
        return

    if custom_id.startswith("alert_high_") or custom_id.startswith("alert_low_"):
        mat = custom_id.split("_")[2]
        user_alerts = get_alerts_for_user(interaction.user.id)
        current_mode = user_alerts.get(mat, 0)

        if custom_id.startswith("alert_high_"):
            if current_mode in (0,2):
                new_mode = current_mode + 1
            elif current_mode in (1,3):
                new_mode = current_mode - 1
        else:
            if current_mode in (0,1):
                new_mode = current_mode + 2
            elif current_mode in (2,3):
                new_mode = current_mode - 2

        update_alert(interaction.user.id, mat, new_mode)
        msg = f"🔔 {mat.capitalize()} alert updated: `{new_mode}` (0=Off, 1=Rise, 2=Fall, 3=Both)"
        await interaction.followup.send(msg, ephemeral=True)
        return

    if custom_id.startswith("turn_") or custom_id.startswith("toggle_"):
        mat = custom_id.split("_")[1]
        show_graph = not custom_id.startswith("toggle_")
        data_12 = fetch_columns(TABLE_NAME, mat, last_n=12)
        if not data_12:
            await interaction.followup.send(f"No turn data available for {mat}.", ephemeral=True)
            return
            
        highest, lowest, avg = max(data_12), min(data_12), sum(data_12)/len(data_12)
        if show_graph:
            buf = create_graph(data_12, title=f"{mat.capitalize()} Turn View", view_type="turn")
            file = discord.File(buf, filename=f"{mat}_turns.png")
            embed = discord.Embed(
                title=f"{mat.capitalize()} Turn View (Graph)",
                description=f"Highest: {highest:.2f}\nLowest: {lowest:.2f}\nAverage: {avg:.2f}",
                color=discord.Color.orange()
            )
            embed.set_image(url=f"attachment://{mat}_turns.png")
            await interaction.edit_original_response(embed=embed, view=TurnView(mat, show_graph=True), attachments=[file])
        else:
            table_text = "Turn | Price\n" + "\n".join(f"{i+1:2d} | {val:.2f}" for i, val in enumerate(data_12))
            embed = discord.Embed(
                title=f"{mat.capitalize()} Turn View (Table)",
                description=f"Highest: {highest:.2f}\nLowest: {lowest:.2f}\nAverage: {avg:.2f}\n\n```\n{table_text}\n```",
                color=discord.Color.orange()
            )
            await interaction.edit_original_response(embed=embed, view=TurnView(mat, show_graph=False), attachments=[])
        return
