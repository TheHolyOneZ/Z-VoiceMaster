# Z-VoiceMaster
Z-VoiceMaster is a Discord bot that allows users to create their own temporary voice channels, giving them full control over their private space.

Z-VoiceMaster
A Discord bot for creating and managing temporary voice channels. When a user joins a designated "Join to Create" channel, the bot automatically creates a new voice channel and a private text channel for them, giving them full control.

Features
Automatic Channel Creation: Creates a temporary voice and text channel when a user joins a specific voice channel.
Channel Control Panel: Each channel owner gets a dedicated control panel in their private text channel to manage their voice channel.
Channel Management:
Lock/Unlock the channel to control who can join.
Hide/Reveal the channel from the server list.
Rename the channel.
Kick members from the channel.
Adjust the user limit.
Discord Activities: Start activities like YouTube Together, Chess, and more directly in your voice channel.
Channel Claiming: If the original owner leaves, another user in the channel can claim ownership.
Automatic Cleanup: Channels are automatically deleted when they become empty.
Main Command
The primary command is for setting up the bot on your server. You must have Manage Channels permissions to use it.

!setup-zvoicemaster
This command initiates an interactive setup menu to configure the category for new channels, the name of the "Join to Create" channel, and default channel settings.
