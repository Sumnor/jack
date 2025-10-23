import discord
from discord.ui import View, button
from discord import Button, ButtonStyle
from settings.initializer_functions.cached_users_initializer import get_registration_sheet
from settings.initializer_functions.tickets_initializer import get_ticket_config, get_verify_conf
from settings.settings_multi import get_gov_role
from graphql_requests import get_military, get_general_data

class TicketButtonView(View):
    def __init__(self, message_id: int = None):
        super().__init__(timeout=None)
        self.message_id = message_id

    @button(label="🎟️ Open Ticket", style=ButtonStyle.primary, custom_id="ticket_open")
    async def open_ticket(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer(ephemeral=True)
        try:
            
            guild_id = str(interaction.guild.id)
            message_id = str(interaction.message.id)
            reg_sheet = get_registration_sheet(guild_id)
            verify_config = get_verify_conf(message_id)
            verify = verify_config['verify']
            print(verify)
            records = reg_sheet.get_all_records()
            user_row = next(
                (r for r in records if str(r.get("DiscordID")) == str(interaction.user.id)),
                None
            )
            if verify == "True":
                if not user_row:
                    await interaction.followup.send("❌ You are not registered.", ephemeral=True)
                    return

                nation_id = user_row.get("NationID")
                if not nation_id:
                    await interaction.followup.send("❌ Nation ID not found in your registration.", ephemeral=True)
                    return
                data = get_military(nation_id, interaction)
                cities = get_general_data(nation_id, interaction)
                if data is None:
                    nation_name = "unknown-nation"
                    leader_name = "Leader"
                    city_count = "00"
                else:
                    nation_name, leader_name = data[0], data[1]
                    city_count = cities[4]
            else:
                nation_name = interaction.user.name


            guild = interaction.guild
            if not guild:
                await interaction.followup.send("❌ Must be used in a server.", ephemeral=True)
                return
            ticket_config = None
            welcome_message = ""
            category = None
            
            if self.message_id:
                ticket_config = get_ticket_config(message_id)
            
            if ticket_config and ticket_config.get('category'):
                category_id = ticket_config['category']
                
                category = discord.settings.utils.get(guild.categories, id=category_id)
                if not category:
                    category = guild.get_channel(category_id)
                    if category and not isinstance(category, discord.CategoryChannel):
                        category = None
                
                welcome_message = ticket_config.get('message', '')
            
            if not category or not isinstance(category, discord.CategoryChannel):
                await interaction.followup.send("❌ Ticket category not found.", ephemeral=True)
                return
            
            role_name = get_gov_role(interaction)
            GOV_ROLE = discord.settings.utils.get(guild.roles, name=role_name)
            if not GOV_ROLE:
                return await interaction.followup.send("Define a GOV_ROLE using `/set_setting` first")

            overwrites = {
                guild.default_role: discord.PermissionOverwrite(view_channel=False),
                interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True),
                guild.me: discord.PermissionOverwrite(view_channel=True),
                GOV_ROLE: discord.PermissionOverwrite(view_channel=True),
            }

            if verify == "True":
                channel_name = f"{city_count}︱{nation_name.replace(' ', '-').lower()}"
                ticket_channel = await guild.create_text_channel(
                    name=channel_name,
                    category=category,
                    overwrites=overwrites,
                    reason=f"Ticket opened by {interaction.user}"
                )

                try:
                    await interaction.user.edit(nick=f"{leader_name} | {nation_id}")
                except discord.Forbidden:
                    print("Missing permissions to change nickname")
            else:
                channel_name = f"{nation_name.replace(' ', '-').lower()}"
                ticket_channel = await guild.create_text_channel(
                    name=channel_name,
                    category=category,
                    overwrites=overwrites,
                    reason=f"Ticket opened by {interaction.user}"
                )

            if welcome_message:
                await ticket_channel.send(f"{welcome_message}\n ||@everyone||")
            else:
                await ticket_channel.send("Welcome to your ticket! ||@everyone||")
            if verify == "True":
                await ticket_channel.send(f"NATION LINK: https://politicsandwar.com/nation/id={nation_id}")
            await interaction.followup.send(
                f"✅ Ticket created: {ticket_channel.mention}", ephemeral=True
            )

        except Exception as e:
            print(f"[Ticket Error] {e}")
            await interaction.followup.send("❌ Failed to create ticket.", ephemeral=True)