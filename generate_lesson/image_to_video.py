from magic_hour import Client
import os
from dotenv import load_dotenv

load_dotenv()

def generate_video(prompt, image_path="input/image.png", output_dir="outputs"):
    """
    Generates a video from an image and a text prompt using Magic Hour.
    """
    api_key = os.getenv("MAGIC_HOUR_API_KEY_PREMIUM")
    if not api_key:
        print("Error: MAGIC_HOUR_API_KEY_PREMIUM is not set.")
        return None

    client = Client(token=api_key)

    print(f"Generating video with prompt: {prompt[:50]}...")
    
    try:
        video_result = client.v1.image_to_video.generate(
            assets={
                "image_file_path": image_path
            },
            end_seconds=30,
            style={
                "prompt": prompt
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
    test_prompt = "A simple camera pan."
    generate_video(test_prompt)
