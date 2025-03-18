# Discord Bot with Multiple Features

A versatile Discord bot with voice, music, conversation, and server management capabilities powered by local LLM integration.

## Features

- **Conversation Management**: Chat with the bot in the "bot-chat" channel or via DMs
- **Text-to-Speech (TTS)**: Bot can read messages aloud in voice channels
- **Voice Commands**: Join voice channels and use voice-related commands
- **Music Player**: Play music from YouTube with search capabilities and various controls
- **Server Management**: Various utilities for managing server channels and roles
- **Local LLM Integration**: Connect to your own LLM running locally for AI-powered responses

## Requirements

- Python 3.8+
- Discord.py 2.0+
- FFmpeg (for audio playback)
- A local LLM server (like LM Studio, llama.cpp, or any OpenAI API compatible server)
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

4. **LLM Setup**
   - Install and run a local LLM server (such as [LM Studio](https://lmstudio.ai/))
   - Configure your server to run on http://127.0.0.1:1234
   - In `discord_bot.py`, modify the model name in the `call_local_llm` function:
     ```python
     "model": "llm-model", # Replace with your preferred LLM model
     ```

5. **Running the Bot**
   ```
   python main.py
   ```

## LLM Integration Details

The bot connects to a local LLM server running on http://127.0.0.1:1234 which should be compatible with the OpenAI API format. Here's how it works:

### How Models Are Used

The bot uses different system prompts for different contexts:
- `system_prompt.txt`: Used for regular chat in the "bot-chat" channel
- `system_prompt2.txt`: Used for private DMs with users
- `system_prompt_whisper.txt`: Used for the whisper command

### Configuration

In `discord_bot.py`, you can modify these parameters:
```python
url = "http://127.0.0.1:1234/v1/chat/completions"  # Your LLM server URL
payload = {
    "model": "llm-model",  # Your model name
    "temperature": 0.7,    # Control randomness (0.0-1.0)
    "max_tokens": 100,     # Maximum length of generated response
    "min_tokens": 10       # Minimum length of generated response
}
```

### Compatible LLM Servers

- [LM Studio](https://lmstudio.ai/) - Recommended for easy setup
- [llama.cpp](https://github.com/ggerganov/llama.cpp) with OpenAI API compatibility
- [LocalAI](https://localai.io/)
- Any server that implements OpenAI's chat completions API

## Bot Commands

### General Commands
- `!talkto <user_id>`: Start a DM conversation with a user
- `!whisper <message> id:<user_id>`: Send a whisper to a specific user
- `!photo <filename> id:<user_id>`: Send an image to a user from the images directory

### Voice Commands
- `!voicemode <on/off>`: Turn voice mode on or off (bot will read messages in voice channel)

### Music Commands
- `!play <song name or URL>`: Play a song
- `!skip`: Skip the current song
- `!queue`: Show the music queue
- `!shuffle`: Shuffle the current queue
- `!pause`: Pause the current playback
- `!resume`: Resume the paused playback
- `!volume <0-100>`: Set the playback volume
- `!stop`: Stop the music playback
- `!leave`: Make the bot leave the voice channel
- `!nowplaying`: Show the currently playing song
- `!seek <seconds>`: Seek to a specific position in the current track

### Server Management Commands
- `!clear <amount>`: Clear a number of messages
- `!ban <user> [reason]`: Ban a user with optional reason
- `!unban <user_id>`: Unban a user by ID
- `!kick <user> [reason]`: Kick a user with optional reason
- `!mute <user> [duration]`: Mute a user for an optional duration
- `!unmute <user>`: Unmute a user
- `!list_tools`: List all available server management tools
- `!manual_tool <tool_json>`: Manually execute a server tool using JSON input
- `!execute_tool <tool_json>`: Execute a tool call with JSON input

### Administrative Tools
The bot can also perform server administrative actions through tool calls:
- Change channel names
- Change user nicknames
- Update channel topics
- Get list of server members
- Get list of server channels

## Customizing the Bot

### System Prompts
You can customize the bot's behavior by editing the system prompt files:
- `system_prompt.txt`: Controls behavior in the bot-chat channel
- `system_prompt2.txt`: Controls behavior in private DMs
- `system_prompt_whisper.txt`: Controls behavior for whisper commands

### TTS (Text-to-Speech)
The bot uses the Coqui TTS engine. You can change the TTS model in `discord_bot.py`:
```python
class CoquiTTS:
    def __init__(self, model_name="tts_models/en/ljspeech/tacotron2-DDC"):
        # Change the model_name parameter to use a different TTS model
```

## License

This project is distributed under the MIT License. See the LICENSE file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request. 