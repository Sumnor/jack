import discord
from discord import app_commands
from discord.ext import commands
import io
from typing import List, Literal, Optional
import os
# Assuming these are defined and properly initialized in your settings file:
from settings.bot_instance import bot, wrap_as_prefix_command 


# --- Constants for Policy Types ---
POLICY_TOS = "Terms of Service"
POLICY_SECURITY = "Security Policy"
POLICY_LICENSE = "License"


class PolicyPaginator(discord.ui.View):
    """Pagination view for policy embeds (TOS, Security, License)"""
    
    def __init__(self, embeds: List[discord.Embed], user: discord.User, policy_type: str):
        super().__init__(timeout=300)  # 5 minute timeout
        self.embeds = embeds
        self.current_page = 0
        self.user = user
        self.policy_type = policy_type
        self.update_buttons()
    
    def update_buttons(self):
        """Enable/disable buttons based on current page"""
        is_first = self.current_page == 0
        is_last = self.current_page == len(self.embeds) - 1
        
        # Access buttons by their defined names
        self.first_page.disabled = is_first
        self.prev_page.disabled = is_first
        self.next_page.disabled = is_last
        self.last_page.disabled = is_last
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Ensure only the command user can interact"""
        if interaction.user.id != self.user.id:
            await interaction.response.send_message(
                "This menu is not for you! Run the `/policy` command to view it yourself.", ephemeral=True
            )
            return False
        return True
    
    @discord.ui.button(label="⏮️", style=discord.ButtonStyle.gray, custom_id="policy_first")
    async def first_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page = 0
        self.update_buttons()
        await interaction.response.edit_message(embed=self.embeds[self.current_page], view=self)
    
    @discord.ui.button(label="◀️", style=discord.ButtonStyle.blurple, custom_id="policy_prev")
    async def prev_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page -= 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.embeds[self.current_page], view=self)
    
    @discord.ui.button(label="▶️", style=discord.ButtonStyle.blurple, custom_id="policy_next")
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page += 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.embeds[self.current_page], view=self)
    
    @discord.ui.button(label="⏭️", style=discord.ButtonStyle.gray, custom_id="policy_last")
    async def last_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page = len(self.embeds) - 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.embeds[self.current_page], view=self)
    
    @discord.ui.button(label="🗑️ Close", style=discord.ButtonStyle.red, row=1, custom_id="policy_close")
    async def close_menu(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Clear content, embed, and attachments upon closing
        await interaction.response.edit_message(
            content=f"{self.policy_type} menu closed. You can run `/policy` again anytime.", 
            embed=None, 
            view=None,
            attachments=[] 
        )
        self.stop()


class PolicyHelper:
    """Helper class for reading and formatting policy documents"""
    
    def __init__(self):
        # Define file paths. These files MUST be present in the directory.
        self.file_paths = {
            POLICY_TOS: "README.md",  
            POLICY_SECURITY: "SECURITY.md",
            POLICY_LICENSE: "LICENSE.md"
        }
    
    def read_policy_content(self, policy_type: str) -> str:
        """Read content from the specified policy file from disk"""
        file_path = self.file_paths.get(policy_type)
        if not file_path:
            return f"**Error:** Policy type '{policy_type}' not recognized."
            
        try:
            # Read the file content from the disk
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            return content
        except FileNotFoundError:
            return f"**Error:** The required file `{file_path}` for the {policy_type} was not found on the server."
        except Exception as e:
            return f"**Error reading file:** An unexpected error occurred while reading `{file_path}`: {str(e)}"
    
    def create_embeds_from_content(self, content: str, policy_type: str) -> List[discord.Embed]:
        """Create paginated embeds from markdown content"""
        
        if content.startswith('**Error:**'):
            return [self._error_embed(content.replace('**Error:**', '').strip())]
            
        # Determine the primary separator, base title, and color
        if policy_type == POLICY_LICENSE:
            # License is often a single block, split only by length
            primary_separator = "\n\n" 
            base_title = "⚖️ " + POLICY_LICENSE
            base_color = 0x1ABC9C 
        elif policy_type == POLICY_SECURITY:
            # Security uses H1/H2 headers
            primary_separator = '## '
            base_title = "🛡️ " + POLICY_SECURITY
            base_color = 0x9B59B6 
        else: # POLICY_TOS - Assume uses H1/H2 headers
            primary_separator = '## '
            base_title = "📜 " + POLICY_TOS
            base_color = 0xFF0000 

        sections = []
        # Initialize the first section
        current_section = {"title": base_title, "content": "", "color": base_color}
        lines = content.split('\n')
        
        if policy_type == POLICY_LICENSE:
            # Simple handling for License: treat as one block for now
            license_content = "\n".join(lines)
            sections.append({
                "title": base_title,
                "content": license_content,
                "color": base_color
            })
        else:
            # Handle TOS/Security using headers as separators
            for line in lines:
                is_header = line.startswith(primary_separator)
                is_main_title = line.startswith('# ') and not line.startswith('## ')
                
                if is_header or is_main_title:
                    # Save previous section if it has content
                    if current_section["content"].strip():
                        sections.append(current_section.copy())
                        
                    # Determine new title
                    if is_header:
                        new_title = line.replace(primary_separator, '').strip()
                    elif is_main_title:
                        new_title = line.replace('# ', '').strip()
                        
                    # Start new section
                    current_section = {
                        "title": new_title,
                        "content": "",
                        "color": self._get_color_for_section(new_title, policy_type)
                    }
                else:
                    # Add to current section content
                    current_section["content"] += line + "\n"
            
            # Add final section
            if current_section["content"].strip() or not sections:
                sections.append(current_section)
        
        # Create embeds from sections, splitting content if needed
        embeds = []
        for section in sections:
            content = section["content"].strip()
            
            # Split content if it exceeds 4096 character limit
            if len(content) > 4000:
                chunks = self._split_content(content, 4000)
                for chunk_idx, chunk in enumerate(chunks):
                    title = section["title"] if chunk_idx == 0 else f"{section['title']} (cont. {chunk_idx + 1})"
                    embed = discord.Embed(
                        title=title,
                        description=chunk,
                        color=section["color"],
                        timestamp=discord.utils.utcnow()
                    )
                    embeds.append(embed)
            else:
                embed = discord.Embed(
                    title=section["title"],
                    description=content if content else "*No content*",
                    color=section["color"],
                    timestamp=discord.utils.utcnow()
                )
                embeds.append(embed)
        
        # Add page numbers to footers
        total_pages = len(embeds)
        for idx, embed in enumerate(embeds, 1):
            embed.set_footer(text=f"Page {idx}/{total_pages} • Politics and War Bot {policy_type}")
        
        return embeds if embeds else [self._error_embed(f"No content found for {policy_type}")]
    
    def _split_content(self, content: str, max_length: int) -> List[str]:
        """Split content into chunks that fit within max_length, trying to respect newlines"""
        chunks = []
        current_chunk = ""
        
        for line in content.split('\n'):
            if len(current_chunk) + len(line) + 1 > max_length:
                chunks.append(current_chunk)
                current_chunk = line + "\n"
            else:
                current_chunk += line + "\n"
        
        if current_chunk:
            chunks.append(current_chunk)
        
        return chunks
    
    def _get_color_for_section(self, header: str, policy_type: str) -> int:
        """Assign colors based on section content and policy type"""
        header_lower = header.lower()
        
        if policy_type == POLICY_SECURITY:
            if "report" in header_lower or "contact" in header_lower:
                return 0xF1C40F # Yellow
            elif "responsible disclosure" in header_lower or "best practices" in header_lower:
                return 0x2ECC71 # Green
            elif "version" in header_lower or "support" in header_lower:
                return 0x3498DB # Blue
            else:
                return 0x9B59B6 # Default Purple (from SECURITY.md)
        elif policy_type == POLICY_LICENSE:
            return 0x1ABC9C # Turquoise for License sections
        
        # Fallback to general TOS logic
        if "prohibited" in header_lower or "termination" in header_lower:
            return 0xE67E22  # Dark Orange
        elif "warranty" in header_lower or "liability" in header_lower:
            return 0xF39C12  # Orange
        elif "grant of rights" in header_lower or "licensing" in header_lower:
            return 0x1ABC9C  # Turquoise
        else:
            return 0x95A5A6  # Default Gray
    
    def _error_embed(self, message: str) -> discord.Embed:
        """Create an error embed"""
        return discord.Embed(
            title="❌ Policy Error",
            description=message,
            color=0xFF0000
        )

# Initialize helper
policy_helper = PolicyHelper()


class PolicySelect(discord.ui.Select):
    """Dropdown menu for selecting a policy document"""
    def __init__(self):
        options = [
            discord.SelectOption(
                label=POLICY_TOS, 
                description="The terms and conditions for using the bot.", 
                emoji="📜", 
                value=POLICY_TOS
            ),
            discord.SelectOption(
                label=POLICY_SECURITY, 
                description="Information on security practices and vulnerability reporting.", 
                emoji="🛡️", 
                value=POLICY_SECURITY
            ),
            discord.SelectOption(
                label=POLICY_LICENSE, 
                description="The legal license governing the bot's usage.", 
                emoji="⚖️", 
                value=POLICY_LICENSE
            )
        ]
        super().__init__(
            placeholder="Choose a policy document...", 
            min_values=1, 
            max_values=1, 
            options=options,
            custom_id="policy_select_menu"
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        selected_policy = self.values[0]
        
        # Read content from file
        policy_content = policy_helper.read_policy_content(selected_policy)
        
        # Create embeds
        embeds = policy_helper.create_embeds_from_content(policy_content, selected_policy)
        
        # Prepare file for download
        file_name_map = {
            POLICY_TOS: "Terms_of_Service.txt",
            POLICY_SECURITY: "Security_Policy.txt",
            POLICY_LICENSE: "License.txt",
        }
        file_name = file_name_map.get(selected_policy, "Policy_Document.txt")
        txt_file = io.BytesIO(policy_content.encode('utf-8'))
        txt_file.seek(0)
        
        # Check for file errors to decide if file should be attached
        if policy_content.startswith('**Error:**'):
            discord_file = None
            file_message = "File attachment failed due to an error reading the source file."
        else:
            discord_file = discord.File(txt_file, filename=file_name)
            file_message = "The complete document has been attached as a text file for your records."

        # Create paginator view
        view = PolicyPaginator(embeds, interaction.user, selected_policy)
        
        # Edit the original message to display the policy and paginator
        await interaction.edit_original_response(
            content=f"📋 **Politics and War Bot - {selected_policy}**\n\n"
                    f"Use the buttons below to navigate through the document. {file_message}",
            embed=embeds[0],
            view=view,
            # Pass the file if it exists, otherwise pass an empty list
            attachments=[discord_file] if discord_file else [],
        )
        
        # Stop the selection view once a choice is made
        if self.view:
            self.view.stop()


class PolicySelectView(discord.ui.View):
    """Initial view with the dropdown menu"""
    def __init__(self, user_id):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.add_item(PolicySelect())
        
    async def on_timeout(self):
        # Disable components on timeout and edit message if possible
        for item in self.children:
            item.disabled = True
        # NOTE: Cannot use interaction.edit_original_response here due to timeout
        
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Ensure only the command user can interact with the initial menu"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "This menu is not for you! Run the `/policy` command to make your own selection.", ephemeral=True
            )
            return False
        return True

@bot.tree.command(name="policy", description="View the bot's Terms of Service, Security Policy, or License")
async def policy_command(interaction: discord.Interaction):
    """Asks the user to select which policy they want to view"""
    
    # Send the initial message with the dropdown menu
    await interaction.response.send_message(
        "👋 **Hello! Which policy document would you like to review?**\n All the links(use `/bot_info_and_invite` for the missing ones):\n-#  **[ToS](<https://github.com/Sumnor/jack/blob/main/README.md>)** |  **[Security](<https://github.com/Sumnor/jack/blob/main/SECURITY.md>)** |  **[License](<https://github.com/Sumnor/jack/blob/main/LICENSE.md>)** | **[Invite](<https://discord.com/oauth2/authorize?client_id=1367997847978377247&permissions=8&scope=bot%20applications.commands>)** | **[Repo](<https://github.com/Sumnor/jack>)**",
        view=PolicySelectView(interaction.user.id),
        ephemeral=True
    )

# Register the slash command's callback as a prefix command using the imported wrapper
bot.command(name="policy")(wrap_as_prefix_command(policy_command.callback))