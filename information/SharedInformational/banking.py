import discord
from databases.sql.data_puller import get_bank_data_sql_by_everything
from information.alliance_info.control_buttons import PrevButton, NextButton, BackAAButton, CloseAAButton
from information.SharedInformational.control_buttons import PrevPageButton, NextPageButton, BackButton, CloseButton

class BankView(discord.ui.View):
    def __init__(self, nation_id, original_embed, transaction_blocks, original_view_instance, transactions_per_page, is_nation):
        super().__init__(timeout=180)
        self.nation_id = nation_id
        self.transaction_blocks = transaction_blocks
        self.transactions_per_page = transactions_per_page
        self.is_nation = is_nation
        self.current_page = 0
        self.original_embed = original_embed
        self.original_view_instance = original_view_instance
        self.pages = [transaction_blocks[i:i + transactions_per_page] for i in range(0, len(transaction_blocks), transactions_per_page)]

    async def show_first_page(self, message):
        embed = self.build_embed_for_page()
        if self.is_nation:
            self.add_item(PrevPageButton())
            self.add_item(NextPageButton())
            self.add_item(BackButton(self.original_embed, self.original_view_instance))
            self.add_item(CloseButton())
        else:
            self.add_item(PrevButton())
            self.add_item(NextButton())
            self.add_item(BackAAButton(self.original_embed, self.original_view_instance))
            self.add_item(CloseAAButton())
        await message.edit(embed=embed, view=self)

    async def show_current_page(self, interaction: discord.Interaction):
        embed = self.build_embed_for_page()
        print(self.original_view_instance)
        await interaction.response.edit_message(embed=embed)
        if self.is_nation:
            self.add_item(PrevPageButton())
            self.add_item(NextPageButton())
            self.add_item(BackButton(self.original_embed, self.original_view_instance))
            self.add_item(CloseButton())
        else:
            self.add_item(PrevButton())
            self.add_item(NextButton())
            self.add_item(BackAAButton(self.original_embed, self.original_view_instance))
            self.add_item(CloseAAButton())
    
    def build_embed_for_page(self):
        embed = discord.Embed(
            title=f"TRANSACTIONS FOR {self.nation_id} (Page {self.current_page + 1}/{len(self.pages)})",
            colour=discord.Colour.dark_grey()
        )
        
        for transaction_str in self.pages[self.current_page]:
            embed.add_field(
                name=f"--------------------------------------------------------------------------",
                value=transaction_str,
                inline=False
            )
        
        return embed


class BankModal(discord.ui.Modal, title="Nation/AA Name or Link to filter(`/` for all)"):

    def __init__(self, nation_id, original_embed, original_view_instance, channel_id, message_id, is_nation): 
        super().__init__(timeout=None)
        self.nation_id = nation_id
        self.original_embed = original_embed
        self.original_view_instance = original_view_instance 
        self.channel_id = channel_id
        self.message_id = message_id
        self.is_nation = is_nation

        self.user_input = discord.ui.TextInput(
            label="Neprito, 680627, ...",
            style=discord.TextStyle.short,
        )
        self.add_item(self.user_input)

    async def on_submit(self, interaction: discord.Interaction):
        pull = self.user_input.value
        transactions_per_page = 10
        
        await interaction.response.send_message(f"🔍 Fetching bank transactions, please be patient...", ephemeral=True)
        channel = interaction.client.get_channel(self.channel_id)
        message = await channel.fetch_message(self.message_id)
        fetching_embed = discord.Embed(
            title=self.original_embed.title,
            description=f"🔍 **Fetching Bank Transaction History...**\nFilter: **{pull}**",
            colour=discord.Colour.orange()
        )
        await message.edit(embed=fetching_embed, view=None)
        
        if pull == '/':
            transactions = get_bank_data_sql_by_everything(None, self.nation_id, pull)
        else:
            if "https://politicsandwar.com/nation/id=" in pull:
                pull = pull.replace("https://politicsandwar.com/nation/id=", "")
            if "https://politicsandwar.com/alliance/id=" in pull:
                pull = pull.replace("https://politicsandwar.com/alliance/id=", "")
            transactions = get_bank_data_sql_by_everything(self.user_input.value, self.nation_id, pull)

        if not transactions or len(transactions) == 0:
            no_transactions_embed = discord.Embed(
                title=f"TRANSACTIONS FOR {self.nation_id}",
                description="No transaction history found with the given filter.",
                colour=discord.Colour.dark_grey()
            )
            await message.edit(embed=no_transactions_embed, view=self.original_view_instance)
            return

        transaction_blocks = []
        
        for transaction in transactions:
            transaction_id = transaction.get('id')
            money = transaction.get('money')
            food = transaction.get('food')
            uranium = transaction.get('uranium')
            iron = transaction.get('iron')
            coal = transaction.get('coal')
            bauxite = transaction.get('bauxite')
            oil = transaction.get('oil')
            lead = transaction.get('lead')
            steel = transaction.get('steel')
            aluminum = transaction.get('aluminum')
            munitions = transaction.get('munitions')
            gasoline = transaction.get('gasoline')
            accept = transaction.get('accepted')

            sender_id = transaction.get('sender_id')
            sender_type = transaction.get('sender_type')

            receiver_type = transaction.get('receiver_type')
            receiver_id = transaction.get('receiver_id')

            message_format = ""
            if sender_type == 1 and receiver_type == 1:
                continue
            elif sender_type == 1 and receiver_type == 2:
                message_format = f"Transaction: [{transaction_id}](https://politicsandwar.com/alliance/id={receiver_id}&display=bank) | Sender: [{sender_id}](https://politicsandwar.com/nation/id={sender_id}) | Receiver: [{receiver_id}](https://politicsandwar.com/alliance/id={receiver_id})\n```md\nMoney: {money} | Food: {food} | Uranium: {uranium} | Lead: {lead} | Bauxite: {bauxite} | Oil: {oil} | Iron: {iron} | Coal: {coal} | Munitions: {munitions} | Steel: {steel} | Gasoline: {gasoline} | Aluminum: {aluminum}```"
            elif sender_type == 2 and receiver_type == 1:
                message_format = f"Transaction: [{transaction_id}](https://politicsandwar.com/alliance/id={sender_id}&display=bank) | Sender: [{sender_id}](https://politicsandwar.com/alliance/id={sender_id}) | Receiver: [{receiver_id}](https://politicsandwar.com/nation/id={receiver_id})\n```md\nMoney: {money} | Food: {food} | Uranium: {uranium} | Lead: {lead} | Bauxite: {bauxite} | Oil: {oil} | Iron: {iron} | Coal: {coal} | Munitions: {munitions} | Steel: {steel} | Gasoline: {gasoline} | Aluminum: {aluminum}```"
            
            if message_format:
                transaction_blocks.append(message_format)
        transaction_view = BankView(self.nation_id, self.original_embed, transaction_blocks, self.original_view_instance, transactions_per_page, self.is_nation)
        if self.is_nation:
            self.add_item(PrevPageButton())
            self.add_item(NextPageButton())
            self.add_item(BackButton(self.original_embed, self.original_view_instance))
            self.add_item(CloseButton())
        else:
            self.add_item(PrevButton())
            self.add_item(NextButton())
            self.add_item(BackAAButton(self.original_embed, self.original_view_instance))
            self.add_item(CloseAAButton())


        await transaction_view.show_first_page(message)