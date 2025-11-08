import discord

class HelpView(discord.ui.View):
    def __init__(self, user_id: str, is_gov: bool, called_with_prefix: bool = False):
        super().__init__(timeout=300)
        self.user_id = user_id
        self.is_gov = is_gov
        self.called_with_prefix = called_with_prefix
        self.current_category = 0

        self.base_categories = [
            {
                "name": "Basic Commands",
                "commands": {
                    "register": "Register yourself to use the bot's features.\nUsage: `/register nation_id: 680627` or `<@1367997847978377247> !register -n 680627`",
                    "info": "Shows general nation/AA info.\nUsage: `/info who: @sumnor_the_lazy` or `<@1367997847978377247> !info -w @sumnor_the_lazy`",
                    "bot_info_and_invite": "Displays bot information, invite links, and support server.\nUsage: `/bot_info_and_invite` or `<@1367997847978377247> !bot_info_and_invite`",
                    "policy": "View the bot’s current policy and usage rules.\nUsage: `/policy` or `<@1367997847978377247> !policy`"
                }
            },
            {
                "name": "MA Commands",
                "commands": {
                    "war_losses": "Get war details for your last few wars.\nUsage: `/war_losses nation_id: 680627 wars_count: 20` or `<@1367997847978377247> !war_losses -n 680627 -w 20`",
                    "war_losses_alliance": "Alliance war losses.\nUsage: `/war_losses_alliance alliance_id: 10259 war_count: 150` or `!war_losses_alliance -a 10259 -w 150`",
                    "see_report": "Find warchest of a registered nation.\nUsage: `/see_report nation: Neprito` or `<@1367997847978377247> !see_report -n Neprito`",
                    "list_reports": "See all logged nations.\nUsage: `/list_reports` or `<@1367997847978377247> !list_reports`",
                    "alliance_militarisation": "Displays militarisation graph for alliance by cities.\nUsage: `/alliance_militarisation alliance: MyAA` or `<@1367997847978377247> !alliance_militarisation -a MyAA`",
                    "nation_militarisation": "Displays militarisation for a nation by MMR.\nUsage: `/nation_militarisation nation_id: 12345` or `<@1367997847978377247> !nation_militarisation -n 12345`",
                    "calculate_military_cost": "Calculate the cost of militarisation.\nUsage: `/calculate_military_cost` or `<@1367997847978377247> !calculate_military_cost`",
                    "filter_nations": "Find suitable raid or target nations.\nUsage: `/filter_nations` or `<@1367997847978377247> !filter_nations`",
                    "toggle_war_rooms": "Toggle automatic war room creation.\nUsage: `/toggle_war_rooms` or `<@1367997847978377247> !toggle_war_rooms`"
                }
            },
            {
                "name": "EA Commands",
                "commands": {
                    "request_warchest": "Calculate/request warchest.\nUsage: `/request_warchest percent: 50%` or `<@1367997847978377247> !request_warchest -p 50%`",
                    "request_city": "Approximate city costs.\nUsage: `/request_city current_city: 10 target_city: 15` or `<@1367997847978377247> !request_city -c 10 -t 15`",
                    "request_infra_grant": "Approx infra costs.\nUsage: `/request_infra_cost current_infra: 10 target_infra: 1500 city_amount: 10` or `<@1367997847978377247> !request_infra_cost -c 10 -t 1500 -a 10`",
                    "request_project": "Calculate/request project costs.\nUsage: `/request_project project: Moon Landing` or `<@1367997847978377247> !request_project -p Moon Landing`",
                    "request_miscellaneous": "Request materials.\nUsage: `/request_grant food: 18mil uranium: 6k reason: Production` or `<@1367997847978377247> !request_grant -f 18mil -u 6k -r Production`",
                    "auto_resources_for_prod_req": "Repeat resource request.\nUsage: `/auto_resources_for_prod_req coal: 100 period: 7` or `<@1367997847978377247> !auto_resources_for_prod_req -c 100 -p 7`",
                    "disable_auto_request": "Disable automatic requests.\nUsage: `/disable_auto_request` or `<@1367997847978377247> !disable_auto_request`",
                    "auto_week_summary": "Summary of all requests.\nUsage: `/auto_week_summary` or `<@1367997847978377247> !auto_week_summary`"
                }
            },
            {
                "name": "IA Commands",
                "commands": {
                    "assign_quota": "Assign a quota to a specific auditor.\nUsage: `/assign_quota auditor: @user quota: 10` or `<@1367997847978377247> !assign_quota -a @user -q 10`",
                    "assign_all": "Automatically assign quotas to all auditors.\nUsage: `/assign_all amount: 10` or `<@1367997847978377247> !assign_all -a 10`",
                    "add_auditor": "Add an auditor to the auditors list.\nUsage: `/add_auditor user: Sumnor` or `<@1367997847978377247> !add_auditor -u Sumnor`",
                    "remove_auditor": "Remove an auditor from the auditors list.\nUsage: `/remove_auditor user: Sumnor` or `<@1367997847978377247> !remove_auditor -u Sumnor`",
                    "excuse_auditor": "Excuse an auditor from current duties.\nUsage: `/excuse_auditor auditor: @user` or `<@1367997847978377247> !excuse_auditor -a @user`",
                    "unexcuse_auditor": "Unexcuse a previously excused auditor.\nUsage: `/unexcuse_auditor auditor: @user` or `<@1367997847978377247> !unexcuse_auditor -a @user`",
                    "audit_targets": "List all audit targets for your server.\nUsage: `/audit_targets` or `<@1367997847978377247> !audit_targets`",
                    "audits": "Audit a nation and log findings.\nUsage: `/audits nation_id: 12345` or `<@1367997847978377247> !audits -n 12345`",
                    "audits_stats": "View overall audit progress.\nUsage: `/audits_stats` or `<@1367997847978377247> !audits_stats`",
                    "quota_display": "Show quota progress; IA Head creates a live message.\nUsage: `/quota_display` or `<@1367997847978377247> !quota_display`",
                    "audits_setup": "Setup audit targets for AA or individual.\nUsage: `/audits_setup aa: MyAA` or `<@1367997847978377247> !audits_setup -a MyAA`",
                    "export_auditor_quotas": "Export all auditor quotas to Excel.\nUsage: `/export_auditor_quotas` or `<@1367997847978377247> !export_auditor_quotas`",
                    "set_quota_due": "Set when audit quotas are due.\nUsage: `/set_quota_due date: YYYY-MM-DD` or `<@1367997847978377247> !set_quota_due -d YYYY-MM-DD`"
                }
            },
            {
                "name": "Offshore Commands",
                "commands": {
                    "balance": "Check your safekeep balance.\nUsage: `/balance` or `<@1367997847978377247> !balance`",
                    "ebo": "Send resources to the offshore.\nUsage: `/ebo resources: money=1` or `<@1367997847978377247> !ebo -r money=1`",
                    "withdraw": "Withdraw resources from offshore.\nUsage: `/withdraw resources: money=1` or `<@1367997847978377247> !withdraw -r money=1`",
                    "ebo_setkey": "Set your AA white key for offshore linking.\nUsage: `/ebo_setkey aa_id: 14207 white_key: XXXXXXXXXXXX` or `<@1367997847978377247> !ebo_setkey -a 14207 -k XXXXXXXXXXXX`",
                    "aabalance": "View your AA’s total safekeep balance.\nUsage: `/aabalance` or `<@1367997847978377247> !aabalance`",
                    "create_safekeep_account": "Create safekeep account linked to your nation.\nUsage: `/create_safekeep_account nation_id: 12345` or `<@1367997847978377247> !create_safekeep_account -n 12345`"
                }
            }
        ]

        self.gov_categories = [
            {
                "name": "Government Commands",
                "commands": {
                    "send_message_to_channels": "Send a message to channels.\nUsage: `/send_message_to_channels channels: #channel message: Hi!` or `!send_message_to_channels -c #channel -m Hi!`",
                    "dm_user": "Send a DM to a user.\nUsage: `/dm_user who: @user message: Hello` or `!dm_user -w @user -m Hello`"
                }
            },
            {
                "name": "Analytics",
                "commands": {
                    "member_activity": "Pie chart of member activity.\nUsage: `/member_activity` or `!member_activity`",
                    "res_details_for_alliance": "Detailed resources & money.\nUsage: `/res_details_for_alliance` or `!res_details_for_alliance`"
                }
            },
            {
                "name": "Server Settings",
                "commands": {
                    "register_server_aa": "Register server for alliance features.\nUsage: `/register_server_aa` or `!register_server_aa`",
                    "set_setting": "Set server settings.\nUsage: `/set_setting key: GOV_ROLE value: High Gov` or `!set_setting -k GOV_ROLE -v 'High Gov'`",
                    "set_internal_settings": "Adjust internal IA configuration.\nUsage: `/set_internal_settings key: IA_ROLE value: Auditor` or `<@1367997847978377247> !set_internal_settings -k IA_ROLE -v Auditor`",
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
        embed = discord.Embed(
            title=f"{category['name']}",
            color=discord.Color.purple() if self.is_gov else discord.Color.blue(),
            description="Here are the available commands in this category:"
        )

        for command, description in category["commands"].items():
            if self.called_with_prefix:
                usage = description.replace("Usage: `/", "Usage: `!")
                usage = usage.replace("` or `!member_activity`", "` (or use `!member_activity`)")
                embed.add_field(name=f"`{command.replace('/', '!')}`", value=usage, inline=False)
            else:
                embed.add_field(name=f"`{command}`", value=description, inline=False)
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
