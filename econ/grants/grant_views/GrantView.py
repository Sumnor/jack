import discord
import re
from settings.initializer_functions.resource_prices import ALL_RESOURCES
from discord.ui import View, button
from settings.settings_multi import get_banking_role
from offshore.offshore_utils.initialize import safekeep_db, pnw_api
from econ.grants.auto_grant import is_auto_grant_enabled

class GrantView(View):
    def __init__(self):
        super().__init__(timeout=None)

    async def is_government_member(self, interaction):
        BANKER = get_banking_role(interaction)
        if BANKER:
            return (
            any(role.name == BANKER for role in interaction.user.roles)
            )
        else:
            return None

    def parse_grant_embed(self, embed: discord.Embed):
        """Parse the grant request embed to extract nation_id, alliance_id, and resources"""
        description = embed.description
        
        # Extract nation_name and nation_id from the link text
        # Pattern: [Nation Name](https://politicsandwar.com/nation/id=123456)
        nation_name_match = re.search(r"\[([^\]]+)\]\(https://politicsandwar\.com/nation/id=(\d+)\)", description)
        nation_name = nation_name_match.group(1) if nation_name_match else None
        nation_id = int(nation_name_match.group(2)) if nation_name_match else None
        
        # Fallback: try to extract nation_id from plain text patterns
        if not nation_id:
            nation_match = re.search(r"Nation ID:\s*(\d+)", description)
            nation_id = int(nation_match.group(1)) if nation_match else None
        
        # Extract alliance_id
        alliance_match = re.search(r"Alliance ID:\s*(\d+)", description)
        alliance_id = int(alliance_match.group(1)) if alliance_match else None
        
        # If alliance_id not found and we have nation_id, try to look it up from database
        if not alliance_id and nation_id:
            try:
                safekeep_record = safekeep_db.get_safekeep_by_nation_id(nation_id)
                if safekeep_record:
                    alliance_id = safekeep_record.get('alliance_id')
                    print(f"[INFO] Looked up alliance_id {alliance_id} for nation {nation_id}")
            except Exception as e:
                print(f"[WARN] Could not lookup alliance_id for nation {nation_id}: {e}")
        
        # Extract discord mention for user_id
        user_mention_match = re.search(r"<@(\d+)>", description)
        discord_id = user_mention_match.group(1) if user_mention_match else None
        
        # Extract resources from description text (for grants where resources are in description)
        resources = {}
        # Look for patterns like "Uranium: 1" or "Money: 1,000,000" in the description
        resource_pattern = r"([A-Za-z]+):\s*([\d,]+)"
        for match in re.finditer(resource_pattern, description):
            resource_name = match.group(1).lower()
            amount_str = match.group(2).replace(",", "")
            try:
                amount = float(amount_str)
                if resource_name in ALL_RESOURCES and amount > 0:
                    resources[resource_name] = amount
            except ValueError:
                continue
        
        # Also check embed fields for resources (backup method)
        for field in embed.fields:
            field_lower = field.name.lower()
            for resource in ALL_RESOURCES:
                if resource in field_lower:
                    value_str = field.value.replace(",", "").replace("$", "").strip()
                    try:
                        amount = float(value_str)
                        if amount > 0:
                            # Only add if not already found in description
                            if resource not in resources:
                                resources[resource] = amount
                    except ValueError:
                        continue
                    break
        
        return {
            'nation_id': nation_id,
            'nation_name': nation_name,
            'alliance_id': alliance_id,
            'discord_id': discord_id,
            'resources': resources
        }

    @button(label="✅ Sent", style=discord.ButtonStyle.green, custom_id="grant_approve")
    async def approve_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        if not await self.is_government_member(interaction):
            BANKER = get_banking_role(interaction)
            if BANKER:
                try:
                    await interaction.followup.send("❌ You need the 'Banker' role to approve grant requests.", ephemeral=True)
                except discord.NotFound:
                    pass  
                return

        try:
            embed = interaction.message.embeds[0]
            
            auto_send_enabled = is_auto_grant_enabled(interaction.guild_id)
            
            if auto_send_enabled:
                # AUTO MODE: Parse and send automatically
                grant_data = self.parse_grant_embed(embed)
                
                print(f"[DEBUG] Parsed grant data: {grant_data}")
                
                if not grant_data['nation_id']:
                    await interaction.followup.send("❌ Could not extract nation ID from grant request.", ephemeral=True)
                    return
                
                if not grant_data['alliance_id']:
                    await interaction.followup.send(
                        f"❌ Could not extract or lookup alliance ID for nation {grant_data['nation_id']}. "
                        "Please ensure the nation is registered in the safekeep database.",
                        ephemeral=True
                    )
                    return
                
                if not grant_data['resources']:
                    await interaction.followup.send("❌ No resources found in grant request.", ephemeral=True)
                    return
                
                # Get AA balance
                aa_sheet = safekeep_db.get_or_create_aa_sheet(
                    grant_data['alliance_id'], 
                    interaction.guild_id
                )
                
                if not aa_sheet:
                    await interaction.followup.send("❌ Could not fetch AA balance sheet.", ephemeral=True)
                    return
                
                # Check if AA has sufficient resources
                insufficient = []
                for resource, amount in grant_data['resources'].items():
                    aa_balance = float(aa_sheet.get(resource, 0))
                    if aa_balance < amount:
                        insufficient.append(f"{resource.capitalize()}: Need {amount:,.0f}, Have {aa_balance:,.0f}")
                
                if insufficient:
                    error_msg = "❌ Insufficient AA balance:\n" + "\n".join(insufficient)
                    await interaction.followup.send(error_msg, ephemeral=True)
                    return
                
                # Deduct from AA balance first
                deduct_success = safekeep_db.update_aa_sheet(
                    alliance_id=grant_data['alliance_id'],
                    guild_id=interaction.guild_id,
                    resources=grant_data['resources'],
                    operation='subtract'
                )
                
                if not deduct_success:
                    await interaction.followup.send("❌ Failed to deduct from AA balance.", ephemeral=True)
                    return
                
                # Execute the withdrawal using PnW API
                withdrawal_success = pnw_api.withdraw_to_nation(
                    nation_id=grant_data['nation_id'],
                    resources=grant_data['resources'],
                    note="Grant approved via Discord"
                )
                
                if not withdrawal_success:
                    # If withdrawal fails, we should add the resources back
                    safekeep_db.update_aa_sheet(
                        alliance_id=grant_data['alliance_id'],
                        guild_id=interaction.guild_id,
                        resources=grant_data['resources'],
                        operation='add'
                    )
                    await interaction.followup.send(
                        "❌ Failed to execute withdrawal through PnW API. AA balance restored.", 
                        ephemeral=True
                    )
                    return
                
                # Update embed
                embed.color = discord.Color.green()
                embed.description += f"\n**Status:** ✅ **GRANT SENT (AUTO)**"
                embed.description += f"\n**Approved by:** {interaction.user.mention}"
                
                # Add resource summary
                resource_summary = "\n".join([f"• {k.capitalize()}: {v:,.0f}" for k, v in grant_data['resources'].items()])
                embed.add_field(name="📦 Resources Sent", value=resource_summary, inline=False)

                # Add nation name if available
                nation_display = grant_data['nation_name'] or f"Nation {grant_data['nation_id']}"
                
                # Notify user if discord_id found
                user_mention = f"<@{grant_data['discord_id']}>" if grant_data['discord_id'] else "Recipient"

                try:
                    await interaction.followup.send(
                        f"✅ Grant approved and sent to **{nation_display}**! {user_mention}\n"
                        f"Resources deducted from AA balance.",
                        ephemeral=False
                    )
                except discord.NotFound:
                    await interaction.channel.send(
                        f"✅ Grant approved and sent to **{nation_display}**! {user_mention}\n"
                        f"Resources deducted from AA balance."
                    )
            else:
                # MANUAL MODE: Just mark as sent without processing
                embed.color = discord.Color.green()
                embed.description += f"\n**Status:** ✅ **GRANT SENT (MANUAL)**"
                embed.description += f"\n**Approved by:** {interaction.user.mention}"

                lines = embed.description.splitlines()
                user_mention = "@someone"
                for line in lines:
                    if line.startswith("**Requested by:**"):
                        user_mention = line.split("**Requested by:**")[1].strip()
                        break

                try:
                    await interaction.followup.send(
                        f"✅ Grant request has been marked as sent! {user_mention}\n"
                        f"⚠️ Auto-send is disabled. Process manually through PnW.",
                        ephemeral=False
                    )
                except discord.NotFound:
                    await interaction.channel.send(
                        f"✅ Grant request has been marked as sent! {user_mention}\n"
                        f"⚠️ Auto-send is disabled. Process manually through PnW."
                    )

            image_url = "https://i.ibb.co/Kpsfc8Jm/jack.webp"
            embed.set_footer(text="Brought to you by Sumnor", icon_url=image_url)
            await interaction.edit_original_response(embed=embed, view=None)

        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            print(f"[ERROR] Grant approval failed: {error_trace}")
            try:
                await interaction.followup.send(f"❌ Error processing grant: `{e}`", ephemeral=True)
            except discord.NotFound:
                await interaction.channel.send(f"❌ Error processing grant: `{e}`")


    @button(label="🕒 Delay", style=discord.ButtonStyle.primary, custom_id="grant_delay")
    async def delay_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        if not await self.is_government_member(interaction):
            BANKER = get_banking_role(interaction)
            if BANKER:
                try:
                    await interaction.followup.send("❌ You need the 'Banker' role to approve grant requests.", ephemeral=True)
                except discord.NotFound:
                    pass  
                return

        try:
            embed = interaction.message.embeds[0]
            embed.color = discord.Color.orange()
            embed.description += f"\n**Status:** 🕒 **DELAYED**"
            embed.description += f"\n**Delayed by:** {interaction.user.mention}"
            image_url = "https://i.ibb.co/Kpsfc8Jm/jack.webp"
            embed.set_footer(text=f"Brought to you by Sumnor", icon_url=image_url)

            new_view = GrantView()
            new_view.remove_item(new_view.children[1]) 

            await interaction.edit_original_response(embed=embed, view=new_view)
            await interaction.message.pin()
            await interaction.followup.send("✅ Grant delayed and message pinned.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Error: `{e}`", ephemeral=True)

    @button(label="❌ Deny", style=discord.ButtonStyle.red, custom_id="grant_denied")
    async def deny_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        if not await self.is_government_member(interaction):
            BANKER = get_banking_role(interaction)
            if BANKER:
                try:
                    await interaction.followup.send("❌ You need the 'Banker' role to approve grant requests.", ephemeral=True)
                except discord.NotFound:
                    pass  
                return
        try:
            embed = interaction.message.embeds[0]
            
            grant_data = self.parse_grant_embed(embed)
            
            embed.color = discord.Color.red()
            embed.description += f"\n**Status:** ❌ **GRANT DENIED**"
            embed.description += f"\n**Denied by:** {interaction.user.mention}"
            image_url = "https://i.ibb.co/Kpsfc8Jm/jack.webp"
            embed.set_footer(text=f"Brought to you by Sumnor", icon_url=image_url)
            await interaction.edit_original_response(embed=embed, view=None)

            if grant_data['discord_id']:
                user_mention = f"<@{grant_data['discord_id']}>"
                nation_display = grant_data['nation_name'] or f"nation {grant_data['nation_id']}"
                try:
                    await interaction.followup.send(
                        f"❌ Grant request for **{nation_display}** denied. {user_mention}", 
                        ephemeral=False
                    )
                except:
                    pass
                    
        except Exception as e:
            await interaction.followup.send(f"❌ Error: `{e}`", ephemeral=True)