# Discord Bot with Multiple Features

A versatile Discord bot with voice, music, conversation, and server management capabilities.

## Features

- **Conversation Management**: Chat with the bot in the "bot-chat" channel or via DMs
- **Text-to-Speech (TTS)**: Bot can read messages aloud in voice channels
- **Voice Commands**: Join voice channels and use voice-related commands
- **Music Player**: Play music from YouTube with search capabilities and various controls
- **Server Management**: Various utilities for managing server channels and roles

## Requirements

- Python 3.8+
- Discord.py 2.0+
- FFmpeg (for audio playback)
- Other dependencies listed in requirements.txt

## Setup Instructions

1. **Clone the Repository**
   ```
   git clone https://github.com/your-username/discord-bot.git
   cd discord-bot
   ```

2. **Install Dependencies**
   ```
   pip install -r requirements.txt
   ```

3. **Set Up Environment Variables**
   - Copy `.env.example` to `.env`
   - Add your Discord token to the `.env` file
   ```
   DISCORD_TOKEN=your_discord_token_here
   ```

4. **Running the Bot**
   ```
   python main.py
   ```

## Bot Commands

### General Commands
- `!talkto <user_id>`: Start a DM conversation with a user
- `!whisper <message> id:<user_id>`: Send a whisper to a specific user

### Voice Commands
- `!voicemode <on/off>`: Turn voice mode on or off

### Music Commands
- `!play <song name or URL>`: Play a song
- `!skip`: Skip the current song
- `!queue`: Show the music queue
- `!stop`: Stop the music playback
- `!leave`: Make the bot leave the voice channel
- `!nowplaying`: Show the currently playing song

### Server Management Commands
- `!clear <amount>`: Clear a number of messages
- `!ban <user>`: Ban a user
- `!unban <user_id>`: Unban a user
- Various other server management commands

## LLM Integration

The bot can integrate with a local LLM server running at http://127.0.0.1:1234. Update the model name in the configuration to match your preferred model.

## License

This project is distributed under the MIT License. See the LICENSE file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request. 