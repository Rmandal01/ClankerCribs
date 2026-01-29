# MAGIC HOUR VIDEO BOT

A Discord bot powered by Magic Hour AI and Gemini that generates various types of AI videos, animations, and educational content.
Check it out here: https://devpost.com/software/clankercribs
### FEATURES

- Text to Video (/text2video): Generate a video from a text prompt.
- Image to Video (/img2video): Convert a static image into a video.
- Face Swap (/faceswap): Swap a face in a video with another face.
- Animate Image (/animate): Animate a static image with various styles (Cyberpunk, Studio Ghibli, etc.).
- Lip Sync (/lipsync): Sync lips in a video to an audio track.
- Talking Photo (/talkingphoto): Make a photo talk using an audio file.
- Brainrot Generator (/brainrot_v2): Generate chaotic, brainrot-style memes with specific characters.
- Educational Lessons (/generate_lesson): Create educational video lessons on a given topic.

### PREREQUISITES

- Python 3.8+
- FFmpeg (https://ffmpeg.org/download.html) installed and added to system PATH (required for video processing).

### INSTALLATION

1.  Clone the repository:
    git clone <repository-url>
    cd MagicAIbot

2.  Install dependencies:
    pip install -r requirements.txt

3.  Environment Setup:
    Create a .env file in the root directory and add your API keys:
    DISCORD_TOKEN=your_discord_bot_token
    MAGIC_HOUR_API_KEY=your_magic_hour_api_key
    GEMINI_API_KEY=your_gemini_api_key

### USAGE

1.  Run the bot:
    python bot.py

2.  Discord Commands:
    Use /magichelp in Discord to see a full list of available commands.

### TROUBLESHOOTING

-   Encoding Issues: The bot automatically reconfigures sys.stdout for UTF-8 on Windows to handle special characters.
-   Import Errors: Ensure all submodules like generate_lesson are present and dependencies are installed.
-   FFmpeg: If video generation fails, ensure FFmpeg is correctly installed and accessible from the terminal.
