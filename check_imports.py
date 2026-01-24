import sys
import os

# Add generate_lesson to path (same as bot.py)
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "generate_lesson"))

print(f"Path: {sys.path}")
print(f"CWD: {os.getcwd()}")

try:
    print("Attempting to import LLM.llm...")
    from LLM.llm import generate_video_description
    print("Success: LLM.llm")

    print("Attempting to import text_to_video...")
    from text_to_video import generate_text_to_video
    print("Success: text_to_video")

    print("Attempting to import text_speech...")
    from text_speech import generate_speech
    print("Success: text_speech")

    print("Attempting to import main...")
    from main import combine_audio_video
    print("Success: main")

except ImportError as e:
    print(f"ImportError: {e}")
except Exception as e:
    print(f"Error: {e}")
