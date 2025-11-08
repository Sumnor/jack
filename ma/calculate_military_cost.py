import discord
from settings.bot_instance import bot

costs = {
    "soldiers": {"money": 5.00},
    "tanks": {"money": 60.00, "steel": 0.50},
    "aircrafts": {"money": 4000.00, "aluminum": 10.00},
    "ships": {"money": 50000.00, "steel": 30.00},
    "missiles": {"money": 150000.00, "gasoline": 100.00, "munitions": 100.00, "aluminum": 150.00},
    "nukes": {"money": 1750000.00, "uranium": 500.00, "gasoline": 500.00, "aluminum": 1000.00},
    "spies": {"money": 50000.00}
}

@bot.tree.command(name="calculate_military_cost", description="Calculate the cost to buy x military")
async def calculate_military_cost(
    interaction: discord.Interaction,
    soldiers: int = None, tanks: int = None, aircrafts: int = None,
    ships: int = None, missiles: int = None, nukes: int = None, spies: int = None
):
    await interaction.response.defer()

    totals = {
        "money": 0,
        "steel": 0,
        "aluminum": 0,
        "uranium": 0,
        "munitions": 0,
        "gasoline": 0
    }

    if not any([soldiers, tanks, aircrafts, ships, missiles, nukes, spies]):
        await interaction.followup.send("At least pick 1 of the provided units.", ephemeral=True)
        return

    for unit, amount in {
        "soldiers": soldiers, "tanks": tanks, "aircrafts": aircrafts,
        "ships": ships, "missiles": missiles, "nukes": nukes, "spies": spies
    }.items():
        if not amount:
            continue
        for resource, cost in costs[unit].items():
            totals[resource] += cost * amount

    embed = discord.Embed(
        title="💰 Military Cost Calculator",
        colour=discord.Colour.brand_green()
    )

    resource_lines = []
    for res, total in totals.items():
        if total > 0:
            resource_lines.append(f"**{res.title()}**: {total:,.2f}")

    embed.add_field(name="Resource Totals", value="\n".join(resource_lines), inline=False)

    await interaction.followup.send(embed=embed)
