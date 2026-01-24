from magic_hour import Client
import os
from dotenv import load_dotenv

from magic_hour import Client
import os
from dotenv import load_dotenv

load_dotenv()

def generate_text_to_video(prompt, output_dir="outputs"):
    """
    Generates a video from a text prompt using Magic Hour.
    """
    api_key = os.getenv("MAGIC_HOUR_API_KEY_PREMIUM") # Using PREMIUM key as seen in other files
    if not api_key:
         api_key = os.getenv("MAGIC_HOUR_API_KEY") 
         
    if not api_key:
        print("Error: MAGIC_HOUR_API_KEY_PREMIUM or MAGIC_HOUR_API_KEY is not set.")
        return None

    client = Client(token=api_key)

    print(f"Generating video for script: {prompt[:50]}...")

    try:
        video_result = client.v1.text_to_video.generate(
            end_seconds=10.0, # Increased slightly for a lesson clip
            orientation="landscape",
            style={
                "prompt": prompt,
            },
            wait_for_completion=True,
            download_outputs=True,
            download_directory=output_dir,
        )

        print(f"Video created with id {video_result.id}, spent {video_result.credits_charged} credits.")
        print(f"Video outputs saved at {video_result.downloaded_paths}")
        return video_result
    except Exception as e:
        print(f"Error generating video: {e}")
        return None

if __name__ == "__main__":
    # Test execution
    generate_text_to_video("A teacher explaining physics in a classroom.")
