import discord
from databases.sql.data_puller import get_trade_data_sql_by_everything
from information.SharedInformational.control_buttons import PrevPageButton, NextPageButton, BackButton

class TradeHistoryView(discord.ui.View):
    def __init__(self, nation_id, original_embed, trade_blocks, original_view_instance, trades_per_page):
        super().__init__(timeout=180)
        self.nation_id = nation_id
        self.trade_blocks = trade_blocks 
        self.trades_per_page = trades_per_page
        self.current_page = 0
        self.original_embed = original_embed
        self.original_view_instance = original_view_instance
        self.pages = [trade_blocks[i:i + trades_per_page] for i in range(0, len(trade_blocks), trades_per_page)]
        
        self.add_item(PrevPageButton())
        self.add_item(NextPageButton())
        self.add_item(BackButton(self.original_embed, self.original_view_instance))

    async def show_first_page(self, message):
        embed = self.build_embed_for_page()
        await message.edit(embed=embed, view=self)

    async def show_current_page(self, interaction: discord.Interaction):
        embed = self.build_embed_for_page()
        await interaction.response.edit_message(embed=embed, view=self)
    
    def build_embed_for_page(self):
        embed = discord.Embed(
            title=f"TRADES FOR {self.nation_id} (Page {self.current_page + 1}/{len(self.pages)})",
            colour=discord.Colour.dark_grey()
        )
        
        for trade_str in self.pages[self.current_page]:
            embed.add_field(
                name=f"--------------------------------------------------------------------------",
                value=trade_str,
                inline=False
            )
        
        return embed


class TradeModal(discord.ui.Modal, title="Nation Name or Link to filter(`/` for all)"):

    def __init__(self, nation_id, original_embed, original_view_instance, channel_id, message_id): 
        super().__init__(timeout=None)
        self.nation_id = nation_id
        self.original_embed = original_embed
        self.original_view_instance = original_view_instance 
        self.channel_id = channel_id
        self.message_id = message_id

        self.user_input = discord.ui.TextInput(
            label="Neprito, 680627, ...",
            style=discord.TextStyle.short,
        )
        self.add_item(self.user_input)

    async def on_submit(self, interaction: discord.Interaction):
        pull = self.user_input.value
        trades_per_page = 10
        await interaction.response.send_message(f"🔍 Fetching trades...", ephemeral=True)

        channel = interaction.client.get_channel(self.channel_id)
        message = await channel.fetch_message(self.message_id)
        
        fetching_embed = discord.Embed(
            title=self.original_embed.title,
            description=f"🔍 **Fetching Trade History...**\nFilter: **{pull}**",
            colour=discord.Colour.orange()
        )
        await message.edit(embed=fetching_embed, view=None)
        
        if pull == '/':
            trades = get_trade_data_sql_by_everything(None, self.nation_id, pull)
        else:
            if "https://politicsandwar.com/nation/id=" in pull:
                pull = pull.replace("https://politicsandwar.com/nation/id=", "")
            trades = get_trade_data_sql_by_everything(self.user_input.value, self.nation_id, pull)

        print(f"DEBUG MODAL: Total trades fetched: {len(trades) if trades else 0}")

        if not trades or len(trades) == 0:
            no_trades_embed = discord.Embed(
                title=f"TRADES FOR {self.nation_id}",
                description="No trade history found with the given filter.",
                colour=discord.Colour.dark_grey()
            )
            await message.edit(embed=no_trades_embed, view=self.original_view_instance)
            return

        trade_blocks = []
        
        for trade in trades:
            trade_id = trade.get('id')
            resource = trade.get('offer_resource')
            amount = trade.get('offer_amount')
            ppu = trade.get('price')
            bos = trade.get('buy_or_sell')
            accept = trade.get('accepted')

            sender_id = trade.get('sender_id')
            receiver_id = trade.get('receiver_id')

            current_bos = bos
            if str(receiver_id) == str(self.nation_id):
                if bos == "buy":
                    current_bos = "sell"
                elif bos == "sell":
                    current_bos = "buy"

            message_format = ""

            if int(receiver_id) != int(0):
                if current_bos == "buy":
                    seller = f"[{receiver_id}](https://politicsandwar.com/nation/id={receiver_id})"
                    buyer = f"[{sender_id}](https://politicsandwar.com/nation/id={sender_id})"
                elif current_bos == "sell":
                    seller = f"[{sender_id}](https://politicsandwar.com/nation/id={sender_id})"
                    buyer = f"[{receiver_id}](https://politicsandwar.com/nation/id={receiver_id})"
                
                message_format = f"[Trade: {trade_id}](https://politicsandwar.com/nation/id={self.nation_id}&display=trade) | Type: {current_bos} | Resource: {amount} {resource} | Price: {int(amount*ppu)}@{ppu} | Seller: {seller} | Buyer: {buyer} | Accepted: {accept}"
            else:
                if current_bos == "buy":
                    buyer = f"[{sender_id}](https://politicsandwar.com/nation/id={sender_id})"
                    message_format = f"[Trade: {trade_id}](https://politicsandwar.com/nation/id={self.nation_id}&display=trade) | Type: {current_bos} | Resource: {amount} {resource} | Price: {int(amount*ppu)}@{ppu} | Buyer: {buyer} | Accepted: {accept}"
                elif current_bos == "sell":
                    seller = f"[{sender_id}](https://politicsandwar.com/nation/id={sender_id})"
                    message_format = f"[Trade: {trade_id}](https://politicsandwar.com/nation/id={self.nation_id}&display=trade) | Type: {current_bos} | Resource: {amount} {resource} | Price: {int(amount*ppu)}@{ppu} | Seller: {seller} | Accepted: {accept}"
            
            if message_format:
                trade_blocks.append(message_format)

        trade_view = TradeHistoryView(self.nation_id, self.original_embed, trade_blocks, self.original_view_instance, trades_per_page)
        await trade_view.show_first_page(message)