import discord
from discord import app_commands
from typing import Optional
from settings.initializer_functions.supabase_initializer import supabase
from settings.bot_instance import bot, wrap_as_prefix_command
from tickets.TicketView import TicketButtonView
    
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
        veri = verify.value if hasattr(verify, "value") else verify
        veri = str(veri.strip()).lower()
        sent_message = await interaction.channel.send(embed=embed, view=TicketButtonView())
        await interaction.edit_original_response(content="⏳ Saving configuration...")
        
        try:
            data = {
                'message_id': str(sent_message.id),
                'message': welcome_message_decrypt,
                'category_id': category.id,
                'register': veri
            }
            supabase.insert('ticket_configs', data)
            
            view_with_id = TicketButtonView(message_id=sent_message.id)
            await sent_message.edit(view=view_with_id)
            
            await interaction.edit_original_response(content="✅ Ticket message sent and configuration saved.")
        except Exception as sheet_error:
            print(f"Supabase error: {sheet_error}")
            await interaction.edit_original_response(content="⚠️ Ticket message sent but failed to save configuration. Button may not work after restart.")
            
    except Exception as e:
        print(f"Error in create_ticket_message: {e}")
        await interaction.edit_original_response(content="❌ Failed to create ticket message.")

bot.command(name="create_ticket_message")(wrap_as_prefix_command(create_ticket_message.callback))

def get_ticket_config(message_id: int) -> Optional[dict]:
    try:
        response = supabase.select(
            table="ticket_configs",
            columns="*",
            filters={"message_id": str(message_id)}
        )

        if not response or not isinstance(response, list):
            return None
        
        row = response[0]
        return {
            'message': row.get("message", ""),
            'category': int(row["category_id"]) if row.get("category_id") else None,
            'register': row.get("register", False)
        }

    except Exception as e:
        print(f"❌ Failed to get ticket config: {e}")
        return None


def get_all_ticket_configs():
    try:

        response = supabase.select(
            table="ticket_configs",
            columns="*"
        )

        if not response or not isinstance(response, list):
            return []

        formatted = []
        for record in response:
            formatted.append({
                'message_id': record.get('message_id', ''),
                'message': record.get('message', ''),
                'category': record.get('category', ''),
                'register': record.get('register', False)
            })
        return formatted

    except Exception as e:
        print(f"❌ Failed to get all ticket configs: {e}")
        return []
