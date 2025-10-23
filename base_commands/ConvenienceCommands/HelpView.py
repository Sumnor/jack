import discord

class HelpView(discord.ui.View):
    def __init__(self, user_id: str, is_gov: bool, called_with_prefix: bool = False):
        super().__init__(timeout=300)
        self.user_id = user_id
        self.is_gov = is_gov
        self.called_with_prefix = called_with_prefix  # track how help was called
        self.current_category = 0

        self.base_categories = [
            {
                "name": "📋 Basic Commands",
                "commands": {
                    "register": "Register yourself to use the bot's features.\nUsage: `/register nation_id: 680627` or `!register -n 680627`",
                    "nation_info": "Shows general nation info.\nUsage: `/nation_info who: @sumnor_the_lazy` or `!nation_info -w @sumnor_the_lazy`"
                }
            },
            {
                "name": "⚔️ Spy & Military",
                "commands": {
                    "war_losses": "Get war details for your last few wars.\nUsage: `/war_losses nation_id: 680627 wars_count: 20` or `!war_losses -n 680627 -w 20`",
                    "see_report": "Find warchest of a registered nation.\nUsage: `/see_report nation: Neprito` or `!see_report -n Neprito`",
                    "list_reports": "See all logged nations.\nUsage: `/list_reports` or `!list_reports`"
                }
            },
            {
                "name": "💰 EA Related",
                "commands": {
                    "request_warchest": "Calculate/request warchest.\nUsage: `/request_warchest percent: 50%` or `!request_warchest -p 50%`",
                    "request_city": "Approximate city costs.\nUsage: `/request_city current_city: 10 target_city: 15` or `!request_city -c 10 -t 15`",
                    "request_infra_grant": "Approx infra costs.\nUsage: `/request_infra_cost current_infra: 10 target_infra: 1500 city_amount: 10` or `!request_infra_cost -c 10 -t 1500 -a 10`",
                    "request_project": "Calculate/request project costs.\nUsage: `/request_project project: Moon Landing` or `!request_project -p Moon Landing`",
                    "request_miscellaneous": "Request materials.\nUsage: `/request_grant food: 18mil uranium: 6k reason: Production` or `!request_grant -f 18mil -u 6k -r Production`",
                    "auto_resources_for_prod_req": "Repeat resource request.\nUsage: `/auto_resources_for_prod_req coal: 100 period: 7` or `!auto_resources_for_prod_req -c 100 -p 7`",
                    "disable_auto_request": "Disable automatic requests.\nUsage: `/disable_auto_request` or `!disable_auto_request`",
                    "auto_week_summary": "Summary of all requests.\nUsage: `/auto_week_summary` or `!auto_week_summary`"
                }
            }
        ]

        self.gov_categories = [
            {
                "name": "🛡️ Government Commands",
                "commands": {
                    "send_message_to_channels": "Send a message to channels.\nUsage: `/send_message_to_channels channels: #channel message: Hi!` or `!send_message_to_channels -c #channel -m Hi!`",
                    "dm_user": "Send a DM to a user.\nUsage: `/dm_user who: @user message: Hello` or `!dm_user -w @user -m Hello`",
                    "create_ticket_message": "Create ticket system.\nUsage: `/create_ticket_message message: Press button title: Create Ticket` or `!create_ticket_message -m Press button -t Create Ticket`"
                }
            },
            {
                "name": "📊 Analytics",
                "commands": {
                    "member_activity": "Pie chart of member activity.\nUsage: `/member_activity` or `!member_activity`",
                    "res_in_m_for_a": "Alliance worth chart.\nUsage: `/res_in_m_for_a mode: Hourly scale: Billions` or `!res_in_m_for_a -m Hourly -s Billions`",
                    "res_details_for_alliance": "Detailed resources & money.\nUsage: `/res_details_for_alliance` or `!res_details_for_alliance`",
                    "war_losses_alliance": "Alliance war losses.\nUsage: `/war_losses_alliance alliance_id: 10259 war_count: 150` or `!war_losses_alliance -a 10259 -w 150`"
                }
            },
            {
                "name": "⚙️ Server Settings",
                "commands": {
                    "register_server_aa": "Register server for alliance features.\nUsage: `/register_server_aa` or `!register_server_aa`",
                    "set_setting": "Set server settings.\nUsage: `/set_setting key: GOV_ROLE value: High Gov` or `!set_setting -k GOV_ROLE -v 'High Gov'`",
                    "get_setting": "Get a setting.\nUsage: `/get_setting key: GOV_ROLE` or `!get_setting -k GOV_ROLE`",
                    "list_settings": "List all settings.\nUsage: `/list_settings` or `!list_settings`"
                }
            }
        ]


        self.categories = self.base_categories.copy()
        if self.is_gov:
            self.categories.extend(self.gov_categories)

        self.update_buttons()

    def update_buttons(self):
        self.clear_items()
        if len(self.categories) > 1:
            self.add_item(self.previous_button)
            self.add_item(self.next_button)

    @discord.ui.button(label="◀️ Previous", style=discord.ButtonStyle.secondary)
    async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("❌ This help menu is not for you!", ephemeral=True)
            return

        self.current_category = (self.current_category - 1) % len(self.categories)
        embed = self.create_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Next ▶️", style=discord.ButtonStyle.secondary)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("❌ This help menu is not for you!", ephemeral=True)
            return

        self.current_category = (self.current_category + 1) % len(self.categories)
        embed = self.create_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    def create_embed(self):
        category = self.categories[self.current_category]

        # build embed
        embed = discord.Embed(
            title=f"{category['name']}",
            color=discord.Color.purple() if self.is_gov else discord.Color.blue(),
            description="Here are the available commands in this category:"
        )

        for command, description in category["commands"].items():
            if self.called_with_prefix:
                # adapt usage lines to !-style instead of /
                usage = description.replace("Usage: `/", "Usage: `!")
                usage = usage.replace("` or `!member_activity`", "` (or use `!member_activity`)")
                embed.add_field(name=f"`{command.replace('/', '!')}`", value=usage, inline=False)
            else:
                # keep as-is for slash commands
                embed.add_field(name=f"`{command}`", value=description, inline=False)

        # add quick how-to for optional args only if prefix version
        if self.called_with_prefix:
            embed.add_field(
                name="ℹ️ Using `!` commands with optional arguments",
                value="Use `-n` to skip arguments (by first letter).\n"
                      "If multiple share the same letter, use `-n1`, `-n2`, etc.",
                inline=False
            )

        embed.set_footer(
            text=f"Page {self.current_category + 1}/{len(self.categories)} • Brought to you by Sumnor",
            icon_url="https://i.ibb.co/Kpsfc8Jm/jack.webp"
        )

        return embed

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
