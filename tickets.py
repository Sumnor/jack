import discord
from discord import app_commands
from utils import save_ticket_config
from bot_instance import bot
from discord_views import TicketButtonView
    
tof = [
    app_commands.Choice(name="True", value="True"),
    app_commands.Choice(name="False", value="False")
]

@bot.tree.command(name="create_ticket_message", description="Post a ticket embed in this channel. (\\n for enter key)")
@app_commands.describe(
    embed_description="Description text for the ticket embed",
    embed_title="Title for the ticket embed", 
    welcome_message="Welcome message to show in new tickets",
    category="Category where tickets will be created"
)
@app_commands.choices(verify = tof)
async def create_ticket_message(interaction: discord.Interaction, embed_description: str, embed_title: str, welcome_message: str, category: discord.CategoryChannel, verify: app_commands.Choice[str]):
    await interaction.response.send_message("⏳ Creating ticket message...", ephemeral=True)
    embed_description_decrypt = embed_description.replace("\\n","\n")
    welcome_message_decrypt = welcome_message.replace("\\n","\n")
    
    try:
        embed = discord.Embed(
            title=embed_title,
            description=embed_description_decrypt,
            color=discord.Color.blurple()
        )
        embed.set_footer(text=f"Posted by {interaction.user.display_name}")
        veri = str(verify.value)
        sent_message = await interaction.channel.send(embed=embed, view=TicketButtonView())
        await interaction.edit_original_response(content="⏳ Saving configuration...")
        try:
            save_ticket_config(sent_message.id, welcome_message_decrypt, category.id, veri)
            view_with_id = TicketButtonView(message_id=sent_message.id)
            await sent_message.edit(view=view_with_id)
            
            await interaction.edit_original_response(content="✅ Ticket message sent and configuration saved.")
        except Exception as sheet_error:
            print(f"Sheet error: {sheet_error}")
            await interaction.edit_original_response(content="⚠️ Ticket message sent but failed to save configuration. Button may not work after restart.")
            
    except Exception as e:
        print(f"Error in create_ticket_message: {e}")
        await interaction.edit_original_response(content="❌ Failed to create ticket message.")