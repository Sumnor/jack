import discord
import io
from discord.ui import View, Button
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
from bot_instance import bot, API_KEY, wrap_as_prefix_command
from databases import fetch_columns, fetch_latest_model, get_alerts_for_user, update_alert, fetch_columnss
from regression_models import predict_turns_ahead
from datetime import datetime, timedelta, timezone

TABLE_NAME = "materials"
MATERIALS = ["food","uranium","iron","coal","bauxite","oil","lead","steel","aluminum","munitions","gasoline"]
GRAPHQL_URL = f"https://api.politicsandwar.com/graphql?api_key={API_KEY}"


# ---------------------------
# Utility: daily averaging
# ---------------------------
def turns_to_daily_averages(data, turns_per_day=12):
    if len(data) < turns_per_day:
        return data
    daily_averages = []
    for i in range(0, len(data), turns_per_day):
        day_data = data[i:i+turns_per_day]
        if len(day_data) == turns_per_day:
            daily_averages.append(sum(day_data) / len(day_data))
    return daily_averages


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


# ---------------------------
# Advanced forecasting engine
# ---------------------------
def advanced_predict_price(material, history, days_ahead=1):
    """
    Improved autoregressive + cyclical predictor with volatility and non-negative clamp.
    """
    if not history or len(history) < 7:
        return None

    series = np.array(history, dtype=float)
    n = len(series)

    # --- Basic stats ---
    mean_val = np.mean(series)
    std_val = np.std(series)
    last_val = series[-1]

    # --- AR component ---
    if n >= 5:
        X = np.column_stack([series[i:n-1-i] for i in range(1, min(5, n))])
        y = series[min(5, n):]
        if len(y) > 0 and X.shape[0] >= len(y):
            coef, *_ = np.linalg.lstsq(X[:len(y)], y, rcond=None)
            ar_pred = np.dot(series[-len(coef):][::-1], coef)
        else:
            ar_pred = last_val
    else:
        ar_pred = last_val

    # --- Cycle component ---
    fft_vals = np.fft.rfft(series - mean_val)
    freqs = np.fft.rfftfreq(n, d=1.0)
    idx = np.argmax(np.abs(fft_vals[1:])) + 1 if len(fft_vals) > 1 else 0
    if idx > 0:
        cycle_len = 1 / freqs[idx] if freqs[idx] != 0 else 7
        phase = np.angle(fft_vals[idx])
        cycle_pred = mean_val + np.abs(fft_vals[idx]) / n * np.cos(2*np.pi*days_ahead/cycle_len + phase)
    else:
        cycle_pred = last_val

    # --- Blend AR + Cycle ---
    weight_ar = 0.6
    weight_cycle = 0.4
    raw_pred = weight_ar * ar_pred + weight_cycle * cycle_pred

    # --- Add volatility noise ---
    noise_scale = std_val * 0.1  # 10% of recent volatility
    noise = np.random.normal(0, noise_scale)

    # --- Final forecast ---
    pred = raw_pred + noise

    # --- Clamp to realistic bounds ---
    pred = max(pred, 0)  # no negatives
    # Optionally cap extreme spikes (e.g. 3x historical max)
    pred = min(pred, np.max(series) * 3)

    return float(pred)



# ---------------------------
# Prediction wrappers
# ---------------------------
def predict_next_price(material, days_ahead=1):
    turn_data, timestamps = fetch_columnss("materials", material, last_n=500, with_timestamps=True)
    if not turn_data or not timestamps:
        return None
    daily_data = turns_to_daily_averages_with_timestamps(turn_data, timestamps, days=60)
    if len(daily_data) < 7:
        return None
    return advanced_predict_price(material, daily_data, days_ahead)


def generate_predictions(material, days=30):
    turn_data, timestamps = fetch_columnss("materials", material, last_n=500, with_timestamps=True)
    if not turn_data or not timestamps:
        return [None] * days
    daily_data = turns_to_daily_averages_with_timestamps(turn_data, timestamps, days=60)
    if len(daily_data) < 7:
        return [None] * days

    predictions = []
    base_data = daily_data.copy()
    for day in range(1, days + 1):
        extended = base_data + predictions
        pred = advanced_predict_price(material, extended, days_ahead=1)
        if pred is not None:
            predictions.append(pred)
        else:
            last_pred = predictions[-1] if predictions else daily_data[-1]
            variation = np.random.normal(0, abs(last_pred) * 0.02)
            predictions.append(last_pred + variation)
    return predictions


def generate_historical_predictions(material, historical_data, lookback_days=30):
    preds = []
    for i in range(len(historical_data)):
        if i < 7:
            preds.append(None)
            continue
        available = historical_data[:i]
        try:
            pred = advanced_predict_price(material, available, days_ahead=1)
            preds.append(pred)
        except Exception:
            preds.append(None)
    return preds


# ---------------------------
# Graphing with predictions
# ---------------------------
def create_graph_with_predictions(data, material, avg=None, title="Price", view_type="day"):
    plt.figure(figsize=(12, 6), dpi=100)
    hist_preds = generate_historical_predictions(material, data, lookback_days=30)
    days_hist = list(range(1, len(data) + 1))
    plt.plot(days_hist, data, marker='o', label='Actual Price', color='blue', linewidth=2, markersize=4)
    if hist_preds:
        valid_hist = [(i+1, p) for i,p in enumerate(hist_preds) if p is not None and i < len(data)]
        if valid_hist:
            plt.plot([d for d,_ in valid_hist],[p for _,p in valid_hist],marker='x',label='Historical Predictions',color='orange',linestyle=':',alpha=0.8)
    preds = generate_predictions(material, days=30)
    valid_preds = [(len(data)+i+1, p) for i,p in enumerate(preds) if p is not None]
    if valid_preds:
        plt.plot([d for d,_ in valid_preds],[p for _,p in valid_preds],marker='s',label='30-Day Forecasts',color='purple',linestyle='--',alpha=0.8)
        plt.plot([len(data),valid_preds[0][0]],[data[-1],valid_preds[0][1]],color='purple',linestyle='--',alpha=0.6)
    if avg is not None:
        plt.axhline(avg, color='gray', linestyle=':', alpha=0.5, label='Historical Avg')
        plt.axhline(avg*1.2, color='green', linestyle=':', alpha=0.7, label='+20% Avg')
        plt.axhline(avg*0.8, color='red', linestyle=':', alpha=0.7, label='-20% Avg')
    if data:
        plt.axvline(x=len(data), color='orange', linestyle=':', alpha=0.7, label='Today')
    plt.title(f"{title} - Historical vs Predicted")
    plt.xlabel("Days"); plt.ylabel("Price"); plt.grid(True, alpha=0.3); plt.legend(loc='upper left')
    buf = io.BytesIO(); plt.savefig(buf, format='png', bbox_inches='tight'); plt.close(); buf.seek(0)
    return buf

def create_graph(data, avg=None, title="Price", view_type="day"):
    plt.figure(figsize=(8,4), dpi=100)
    plt.plot(data, marker='o', label='Price')
    if avg is not None:
        plt.axhline(avg*1.2, color='green', linestyle='--', label='+20% Avg')
        plt.axhline(avg*0.8, color='red', linestyle='--', label='-20% Avg')
    plt.title(f"{title} ({view_type})")
    plt.xlabel("Days" if view_type == "day" else "Turns")
    plt.ylabel("Price")
    plt.grid(True)
    plt.legend()
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight')
    plt.close()
    buf.seek(0)
    return buf

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
        self.add_item(Button(label="Forecast View", style=discord.ButtonStyle.secondary, custom_id=f"forecast_{mat}"))

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

        avg = sum(daily_data)/len(daily_data)
        buf = create_graph_with_predictions(daily_data, mat, avg, title=mat.capitalize())
        file = discord.File(buf, filename=f"{mat}_forecast.png")

        # Generate some forecast statistics
        predictions = generate_predictions(mat, days=30)
        valid_predictions = [p for p in predictions if p is not None]

        # Calculate historical prediction accuracy
        historical_predictions = generate_historical_predictions(mat, daily_data, lookback_days=30)
        accuracy_stats = ""
        
        if historical_predictions:
            errors = []
            for i, pred in enumerate(historical_predictions):
                if pred is not None and i < len(daily_data):
                    actual = daily_data[i]
                    if actual != 0:
                        error = abs(pred - actual) / actual * 100
                        errors.append(error)
            
            if errors:
                avg_error = sum(errors) / len(errors)
                accuracy_stats = f"Historical Accuracy: ±{avg_error:.1f}% avg error\n"
        
        if valid_predictions:
            pred_avg = sum(valid_predictions) / len(valid_predictions)
            pred_high = max(valid_predictions)
            pred_low = min(valid_predictions)
            current_price = daily_data[-1] if daily_data else 0
            expected_change = ((pred_avg - current_price) / current_price * 100) if current_price > 0 else 0
            
            forecast_desc = (
                f"**30-Day Forecast Analysis:**\n"
                f"Current Price: {current_price:.2f}\n"
                f"Predicted Average: {pred_avg:.2f}\n"
                f"Predicted High: {pred_high:.2f}\n"
                f"Predicted Low: {pred_low:.2f}\n"
                f"Expected Change: {expected_change:+.1f}%\n\n"
                f"{accuracy_stats}"
                f"**Legend:**\n"
                f"🔵 Blue = Actual historical prices\n"
                f"🟠 Orange = Previous predictions (for accuracy)\n"
                f"🟣 Purple = Future forecasts\n"
                f"*Shaded regions show historical vs forecast periods*"
            )
        else:
            forecast_desc = "Unable to generate reliable forecasts for this material."

        embed = discord.Embed(
            title=f"{mat.capitalize()} - Predictive Analysis",
            description=forecast_desc,
            color=discord.Color.purple()
        )
        embed.set_image(url=f"attachment://{mat}_forecast.png")
        await interaction.edit_original_response(embed=embed, view=MaterialView(mat), attachments=[file])
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
