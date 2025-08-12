import discord
from discord.ext import commands
from discord.ui import Button, View, Select, Modal, TextInput
import asyncio
import json
import os
import base64

ACTIVITIES = {
    "YouTube Together": "880218394199220334",
    "Chess in the Park": "832012774040141894",
    "Checkers in the Park": "832013003968348200",
    "Putt Party": "945737671220740126",
    "Sketch Heads": "902271654783242291",
    "Word Snacks": "879863976006127627",
    "Blazing 8s": "832025144389533716",
    "Land-io": "903769130790969345",
    "Poker Night": "755827207812677713",
}

class ConfigModal(Modal):
    def __init__(self, title, label, placeholder, current_value, callback):
        super().__init__(title=title)
        self.callback = callback
        self.item = TextInput(
            label=label,
            placeholder=str(placeholder),
            default=str(current_value) if current_value is not None else None,
            required=True
        )
        self.add_item(self.item)

    async def on_submit(self, interaction: discord.Interaction):
        await self.callback(interaction, self.item.value)

class ControlPanelView(View):
    def __init__(self, cog_instance):
        super().__init__(timeout=None)
        self.cog = cog_instance

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        owner_id = self.cog.get_owner_of_channel(interaction.channel_id)
        if not owner_id:
            await interaction.response.send_message("This appears to be an orphaned panel. It can no longer be used.", ephemeral=True)
            return False

        if interaction.user.id == owner_id:
            return True

        if interaction.data.get("custom_id") != "zvm:claim":
            await interaction.response.send_message("You are not the owner of this channel.", ephemeral=True)
            return False

        vc, _ = await self.get_user_channels(interaction)
        if not vc: return False

        owner = interaction.guild.get_member(owner_id)
        if owner and owner in vc.members:
            await interaction.response.send_message(f"You can only claim this channel when the owner, {owner.mention}, has left the voice channel.", ephemeral=True)
            return False

        return True

    async def get_user_channels(self, interaction: discord.Interaction):
        owner_id = self.cog.get_owner_of_channel(interaction.channel_id)
        if not owner_id: return None, None
        info = self.cog.user_channels.get(owner_id)
        if not info: return None, None
        voice_channel = interaction.guild.get_channel(info['voice_channel_id'])
        text_channel = interaction.guild.get_channel(info['text_channel_id'])
        return voice_channel, text_channel

    @discord.ui.button(emoji="🔒", style=discord.ButtonStyle.secondary, custom_id="zvm:lock", row=0)
    async def lock(self, i: discord.Interaction, b: Button):
        vc, _ = await self.get_user_channels(i)
        if vc:
            await vc.set_permissions(i.guild.default_role, connect=False)
            await i.response.send_message("🔒 Channel locked.", ephemeral=True)

    @discord.ui.button(emoji="🔓", style=discord.ButtonStyle.secondary, custom_id="zvm:unlock", row=0)
    async def unlock(self, i: discord.Interaction, b: Button):
        vc, _ = await self.get_user_channels(i)
        if vc:
            await vc.set_permissions(i.guild.default_role, connect=None)
            await i.response.send_message("🔓 Channel unlocked.", ephemeral=True)

    @discord.ui.button(emoji="👻", style=discord.ButtonStyle.secondary, custom_id="zvm:hide", row=0)
    async def hide(self, i: discord.Interaction, b: Button):
        vc, _ = await self.get_user_channels(i)
        if vc:
            await vc.set_permissions(i.guild.default_role, view_channel=False)
            await i.response.send_message("👻 Channel hidden.", ephemeral=True)

    @discord.ui.button(emoji="👁️", style=discord.ButtonStyle.secondary, custom_id="zvm:reveal", row=0)
    async def reveal(self, i: discord.Interaction, b: Button):
        vc, _ = await self.get_user_channels(i)
        if vc:
            await vc.set_permissions(i.guild.default_role, view_channel=None)
            await i.response.send_message("👁️ Channel revealed.", ephemeral=True)

    @discord.ui.button(emoji="👑", style=discord.ButtonStyle.primary, custom_id="zvm:claim", row=0)
    async def claim(self, i: discord.Interaction, b: Button):
        vc, tc = await self.get_user_channels(i)
        owner_id = self.cog.get_owner_of_channel(i.channel_id)
        owner = i.guild.get_member(owner_id)
        
        self.cog.user_channels[i.user.id] = self.cog.user_channels.pop(owner_id)
        
        await vc.set_permissions(i.user, manage_channels=True, manage_roles=True)
        await tc.set_permissions(i.user, read_messages=True)
        if owner:
            await vc.set_permissions(owner, overwrite=None)
            await tc.set_permissions(owner, overwrite=None)
            
        await i.response.send_message(f"👑 {i.user.mention} has claimed the channel!")

    @discord.ui.button(emoji="✏️", style=discord.ButtonStyle.primary, custom_id="zvm:rename", row=1)
    async def rename(self, i: discord.Interaction, b: Button):
        vc, _ = await self.get_user_channels(i)
        if not vc: return

        async def modal_callback(interaction, new_name):
            vc_rename, tc_rename = await self.get_user_channels(interaction)
            if vc_rename:
                await vc_rename.edit(name=new_name)
                panel_name = f"＃{new_name.lower().replace(' ', '-')}-panel"
                await tc_rename.edit(name=panel_name)
                await interaction.response.send_message(f"Channel renamed to '{new_name}'.", ephemeral=True)
        
        modal = ConfigModal("Rename Channel", "New Channel Name", vc.name, vc.name, modal_callback)
        await i.response.send_modal(modal)

    @discord.ui.button(emoji="🚫", style=discord.ButtonStyle.danger, custom_id="zvm:kick", row=1)
    async def kick(self, i: discord.Interaction, b: Button):
        vc, _ = await self.get_user_channels(i)
        members_to_kick = [m for m in vc.members if m.id != i.user.id]
        if not members_to_kick:
            return await i.response.send_message("There is no one else in your channel to kick.", ephemeral=True)
        options = [discord.SelectOption(label=m.display_name, value=str(m.id)) for m in members_to_kick]
        select = Select(placeholder="Select a member to kick...", options=options)
        async def select_callback(interaction: discord.Interaction):
            member_id = int(interaction.data['values'][0])
            member = i.guild.get_member(member_id)
            if member and member.voice and member.voice.channel == vc:
                await member.move_to(None, reason="Kicked by channel owner.")
                await interaction.response.send_message(f"Kicked {member.display_name}.", ephemeral=True)
            else:
                await interaction.response.send_message("Member has already left.", ephemeral=True)
            view.stop()
            await interaction.message.delete()
        select.callback = select_callback
        view = View(timeout=60)
        view.add_item(select)
        await i.response.send_message("Who would you like to kick?", view=view, ephemeral=True)

    @discord.ui.button(emoji="🎉", style=discord.ButtonStyle.primary, custom_id="zvm:activity", row=1)
    async def activity(self, i: discord.Interaction, b: Button):
        vc, _ = await self.get_user_channels(i)
        if not vc: return
        
        options = [discord.SelectOption(label=name, value=app_id) for name, app_id in ACTIVITIES.items()]
        select = Select(placeholder="Select an activity to start...", options=options)

        async def select_callback(interaction: discord.Interaction):
            app_id = interaction.data['values'][0]
            try:
                invite = await vc.create_invite(target_type=discord.InviteTarget.embedded_application, target_application_id=int(app_id))
                await interaction.response.send_message(f"Click here to start the activity: {invite}", ephemeral=True)
            except discord.HTTPException:
                 await interaction.response.send_message("Failed to create activity invite. The bot may lack permissions or the activity is unavailable.", ephemeral=True)
            
            view.stop()
            await interaction.message.delete()

        select.callback = select_callback
        view = View(timeout=60)
        view.add_item(select)
        await i.response.send_message("What activity would you like to start?", view=view, ephemeral=True)

    @discord.ui.button(emoji="➕", style=discord.ButtonStyle.secondary, custom_id="zvm:inc_limit", row=1)
    async def increase_limit(self, i: discord.Interaction, b: Button):
        vc, _ = await self.get_user_channels(i)
        if vc:
            current_limit = vc.user_limit or 0
            new_limit = min(current_limit + 1, 99)
            if new_limit == current_limit:
                return await i.response.send_message("User limit is already at maximum (99).", ephemeral=True)
            await vc.edit(user_limit=new_limit)
            await i.response.send_message(f"User limit increased to {new_limit}.", ephemeral=True)

    @discord.ui.button(emoji="➖", style=discord.ButtonStyle.secondary, custom_id="zvm:dec_limit", row=1)
    async def decrease_limit(self, i: discord.Interaction, b: Button):
        vc, _ = await self.get_user_channels(i)
        if vc and vc.user_limit > 0:
            new_limit = max(vc.user_limit - 1, 1)
            if new_limit == vc.user_limit:
                 return await i.response.send_message("User limit is already at minimum (1).", ephemeral=True)
            await vc.edit(user_limit=new_limit)
            await i.response.send_message(f"User limit decreased to {new_limit}.", ephemeral=True)

class SetupView(View):
    def __init__(self, cog_instance, author):
        super().__init__(timeout=300)
        self.cog = cog_instance
        self.author = author
        self.settings = self.cog.guild_settings.get(author.guild.id, {}).copy()
        if not self.settings:
            self.settings = {
                "category_id": None, "creator_channel_name": "➕ Join to Create",
                "default_limit": 0, "default_hidden": False
            }
        self.update_category_select()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("You are not authorized to use this menu.", ephemeral=True)
            return False
        return True

    def update_category_select(self):
        self.clear_items()
        options = [discord.SelectOption(label=c.name, value=str(c.id)) for c in self.author.guild.categories]
        if not options: return
        category_select = Select(placeholder="1. Select a Category...", options=options)
        category_select.callback = self.on_category_select
        self.add_item(category_select)
        
    def build_embed(self):
        embed = discord.Embed(title="Z-VoiceMaster Setup", color=0x7289DA)
        embed.description = "Configure the settings for your temporary voice channels."
        cat_id = self.settings.get('category_id')
        cat_obj = self.author.guild.get_channel(cat_id) if cat_id else None
        cat_name = f"✅ {cat_obj.name}" if cat_obj else "❌ Not Set"
        embed.add_field(name="Category", value=cat_name, inline=False)
        embed.add_field(name="Creator Channel Name", value=f"`{self.settings.get('creator_channel_name')}`", inline=False)
        limit = self.settings.get('default_limit', 0)
        embed.add_field(name="Default User Limit", value=f"`{limit if limit > 0 else 'Unlimited'}`", inline=True)
        hidden = "Yes" if self.settings.get('default_hidden') else "No"
        embed.add_field(name="Hidden by Default?", value=f"`{hidden}`", inline=True)
        embed.set_footer(text=base64.b64decode('TWFkZSDigJliIFRoZUhvbHlPbmVa').decode('utf-8'))
        return embed

    def update_buttons(self):
        self.clear_items()
        name_button = Button(label="Set Creator Name", style=discord.ButtonStyle.secondary, emoji="✏️")
        name_button.callback = self.on_set_name
        self.add_item(name_button)
        limit_button = Button(label="Set User Limit", style=discord.ButtonStyle.secondary, emoji="🔧")
        limit_button.callback = self.on_set_limit
        self.add_item(limit_button)
        visibility_button = Button(label=f"Visibility: {'Hidden' if self.settings.get('default_hidden') else 'Visible'}", style=discord.ButtonStyle.secondary, emoji="👁️")
        visibility_button.callback = self.on_toggle_visibility
        self.add_item(visibility_button)
        save_button = Button(label="Save & Finish", style=discord.ButtonStyle.success, emoji="✅", row=1)
        save_button.callback = self.on_save
        self.add_item(save_button)
        cancel_button = Button(label="Cancel", style=discord.ButtonStyle.danger, emoji="❌", row=1)
        cancel_button.callback = self.on_cancel
        self.add_item(cancel_button)

    async def on_category_select(self, interaction: discord.Interaction):
        self.settings['category_id'] = int(interaction.data['values'][0])
        self.update_buttons()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def on_set_name(self, interaction: discord.Interaction):
        async def modal_callback(inter, value):
            self.settings['creator_channel_name'] = value
            await inter.response.edit_message(embed=self.build_embed(), view=self)
        modal = ConfigModal("Set Creator Channel Name", "Name", "➕ Join to Create", self.settings.get('creator_channel_name'), modal_callback)
        await interaction.response.send_modal(modal)

    async def on_set_limit(self, interaction: discord.Interaction):
        async def modal_callback(inter, value):
            try:
                limit = int(value)
                if not 0 <= limit <= 99: raise ValueError
                self.settings['default_limit'] = limit
                await inter.response.edit_message(embed=self.build_embed(), view=self)
            except ValueError:
                await inter.response.send_message("Invalid input. Please enter a number between 0 and 99.", ephemeral=True)
        modal = ConfigModal("Set Default User Limit", "Limit (0 for unlimited)", 0, self.settings.get('default_limit'), modal_callback)
        await interaction.response.send_modal(modal)
        
    async def on_toggle_visibility(self, interaction: discord.Interaction):
        self.settings['default_hidden'] = not self.settings.get('default_hidden', False)
        self.update_buttons()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def on_save(self, interaction: discord.Interaction):
        guild_id = interaction.guild_id
        current_settings = self.cog.guild_settings.get(guild_id, {})
        old_creator_id = current_settings.get('creator_channel_id')
        if old_creator_id:
            try:
                old_channel = interaction.guild.get_channel(old_creator_id)
                if old_channel: await old_channel.delete()
            except (discord.NotFound, discord.Forbidden): pass
        category = interaction.guild.get_channel(self.settings['category_id'])
        creator_channel = await category.create_voice_channel(name=self.settings['creator_channel_name'])
        self.settings['creator_channel_id'] = creator_channel.id
        self.cog.guild_settings[guild_id] = self.settings
        self.cog.save_settings()
        await interaction.response.edit_message(content="✅ **Setup Complete!** Your settings have been saved.", embed=None, view=None)
        self.stop()

    async def on_cancel(self, interaction: discord.Interaction):
        await interaction.response.edit_message(content="Setup cancelled.", embed=None, view=None)
        self.stop()

class ZVoiceMasterCog(commands.Cog, name="Z-VoiceMaster"):
    def __init__(self, bot):
        self.bot = bot
        self.user_channels = {}
        self.settings_file = "data/z-voicemaster.json"
        os.makedirs(os.path.dirname(self.settings_file), exist_ok=True)
        self.guild_settings = self.load_settings()
        self.bot.add_view(ControlPanelView(self))
    
    def load_settings(self):
        try:
            with open(self.settings_file, 'r') as f:
                return {int(k): v for k, v in json.load(f).items()}
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def save_settings(self):
        with open(self.settings_file, 'w') as f:
            json.dump(self.guild_settings, f, indent=4)

    def get_owner_of_channel(self, channel_id: int):
        for owner_id, info in self.user_channels.items():
            if channel_id in (info.get('voice_channel_id'), info.get('text_channel_id')):
                return owner_id
        return None

    @commands.Cog.listener()
    async def on_ready(self):
        print("Z-VoiceMaster Cog is online and ready.")

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member.bot: return
        guild = member.guild
        settings = self.guild_settings.get(guild.id)
        if not settings or 'creator_channel_id' not in settings: return
        creator_channel_id = settings['creator_channel_id']
        
        if after.channel:
            owner_id = self.get_owner_of_channel(after.channel.id)
            if owner_id and member.id != owner_id:
                info = self.user_channels.get(owner_id)
                if info:
                    tc = guild.get_channel(info['text_channel_id'])
                    if tc: await tc.set_permissions(member, read_messages=True)
            elif after.channel.id == creator_channel_id:
                await self.create_user_channel(member, settings)

        if before.channel:
            owner_id = self.get_owner_of_channel(before.channel.id)
            if owner_id:
                info = self.user_channels.get(owner_id)
                if info:
                    tc = guild.get_channel(info['text_channel_id'])
                    if tc and member.id != owner_id:
                        await tc.set_permissions(member, overwrite=None)
                if not before.channel.members:
                    await asyncio.sleep(1)
                    if not before.channel.members:
                        await self.delete_user_channel(before.channel)

    async def create_user_channel(self, member: discord.Member, settings: dict):
        guild = member.guild
        if member.id in self.user_channels:
            try:
                info = self.user_channels[member.id]
                vc = guild.get_channel(info['voice_channel_id'])
                if vc: await member.move_to(vc)
                return
            except (discord.NotFound, discord.HTTPException):
                del self.user_channels[member.id]
        
        category = guild.get_channel(settings.get('category_id'))
        if not category: return
        try:
            voice_overwrites = { member: discord.PermissionOverwrite(manage_channels=True, manage_roles=True) }
            if settings.get('default_hidden', False):
                voice_overwrites[guild.default_role] = discord.PermissionOverwrite(view_channel=False)
            vc = await guild.create_voice_channel(
                name=f"{member.display_name}'s Channel", category=category,
                overwrites=voice_overwrites, user_limit=settings.get('default_limit', 0)
            )
            tc = await guild.create_text_channel(
                name=f"＃{member.display_name.lower().replace(' ', '-')}-panel", category=category,
                overwrites={ guild.default_role: discord.PermissionOverwrite(read_messages=False), member: discord.PermissionOverwrite(read_messages=True) }
            )
            await member.move_to(vc)
            embed = discord.Embed(title="Z-VoiceMaster Interface", color=0x2F3136)
            embed.set_author(name=f"{member.display_name}'s Control Panel", icon_url=member.display_avatar)
            embed.set_thumbnail(url=self.bot.user.avatar.url)
            description = (
                "**Button Usage**\n\n"
                "🔒 — Lock the voice channel\n"
                "🔓 — Unlock the voice channel\n"
                "👻 — Hide the voice channel\n"
                "👁️ — Reveal the voice channel\n"
                "👑 — Claim the voice channel\n\n"
                "✏️ — Rename the channel\n"
                "🚫 — Disconnect a member\n"
                "🎉 — Start an activity\n"
                "➕ — Increase the user limit\n"
                "➖ — Decrease the user limit\n"
            )
            embed.description = description
            embed.set_footer(text=base64.b64decode('TWFkZSDigJxiIFRoZUhvbHlPbmVa').decode('utf-8'))
            view = ControlPanelView(self)
            msg = await tc.send(embed=embed, view=view)
            self.user_channels[member.id] = {
                'voice_channel_id': vc.id, 'text_channel_id': tc.id,
                'control_message_id': msg.id, 'guild_id': guild.id
            }
        except discord.HTTPException as e:
            print(f"Error creating channel for {member.display_name}: {e}")

    async def delete_user_channel(self, channel: discord.VoiceChannel):
        owner_id = self.get_owner_of_channel(channel.id)
        if not owner_id: return
        info = self.user_channels.pop(owner_id, None)
        if not info: return
        try:
            vc = self.bot.get_channel(info['voice_channel_id']) or await self.bot.fetch_channel(info['voice_channel_id'])
            if vc: await vc.delete(reason="Temp channel empty.")
        except (discord.NotFound, discord.HTTPException): pass
        try:
            tc = self.bot.get_channel(info['text_channel_id']) or await self.bot.fetch_channel(info['text_channel_id'])
            if tc: await tc.delete(reason="Temp channel empty.")
        except (discord.NotFound, discord.HTTPException): pass

    @commands.command(name="setup-zvoicemaster", aliases=["setup-voicemaster"])
    @commands.has_permissions(manage_channels=True)
    async def setup_zvoicemaster(self, ctx: commands.Context):
        view = SetupView(self, ctx.author)
        embed = view.build_embed()
        if not view.children:
            await ctx.send("❌ This server has no categories. Please create one before running setup.", ephemeral=True)
            return
        await ctx.send(embed=embed, view=view, ephemeral=True)

async def setup(bot):
    await bot.add_cog(ZVoiceMasterCog(bot))

# Made By TheHolyOneZ


