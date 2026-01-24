from magic_hour import Client
from os import getenv
import os
from dotenv import load_dotenv

load_dotenv()

def generate_speech(text, output_dir="outputs"):
    # Try to get the premium key first, then fallback to standard
    api_key = getenv("MAGIC_HOUR_API_KEY_PREMIUM") or getenv("MAGIC_HOUR_API_KEY")

    if not api_key:
        print("[ERROR] MAGIC_HOUR_API_KEY_PREMIUM or MAGIC_HOUR_API_KEY is missing from environment/env file.")
        return None

    client = Client(token=api_key)

    try:
        print("Sending request to Magic Hour Voice Generator...")
        result = client.v1.ai_voice_generator.generate(
            style={
                "prompt": text,
                "voice_name": "Morgan Freeman"
            },
            name="Voice Generator audio",
            wait_for_completion=True,
            download_outputs=True,
            download_directory=output_dir
        )

        if result.status == "complete":
            print(f"[OK] Voice generation complete!")
            # print(f"Credits charged: {result.credits_charged}")
            if result.downloaded_paths and len(result.downloaded_paths) > 0:
                print(f"Downloaded to: {result.downloaded_paths[0]}")
                return result.downloaded_paths[0]
            return None
        else:
            print(f"[ERROR] Job failed with status: {result.status}")
            print(f"Result details: {result}")
            return None

    except Exception as e:
        print(f"\n[ERROR] An API error occurred:")
        print(f"{e}")
        if hasattr(e, 'body'):
            print(f"Error Body: {e.body}")
        return None

if __name__ == "__main__":
    generate_speech("Testing voice generation.")