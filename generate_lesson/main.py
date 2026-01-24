import os
import sys

# Ensure we can find the LLM module
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from LLM.llm import generate_video_description
from text_to_video import generate_text_to_video
from text_speech import generate_speech
from moviepy import VideoFileClip, AudioFileClip, vfx

def combine_audio_video(video_path, audio_path, output_path="outputs/final_video.mp4"):
    """
    Combines video and audio files into a single video file.
    """
    try:
        print(f"Combining video ({video_path}) and audio ({audio_path})...")
        
        video_clip = VideoFileClip(video_path)
        audio_clip = AudioFileClip(audio_path)
        
        # In MoviePy v2, use with_effects([vfx.Loop(...)])
        final_video = video_clip.with_effects([vfx.Loop(duration=audio_clip.duration)])
        
        final_video = final_video.with_audio(audio_clip)
        
        final_video.write_videofile(output_path, codec="libx264", audio_codec="aac")
        print(f"Final video saved to: {output_path}")
        return output_path
    except Exception as e:
        print(f"Error combining video and audio: {e}")
        return None

def main():
    print("Welcome to the AI Video Teacher!")
    print("----------------------------------")
    
    while True:
        print("\n" + "="*50)
        user_input = input("Enter a lesson topic (e.g., 'Photosynthesis', 'Gravity'): ")
        
        if user_input.lower() in ['quit', 'exit']:
            print("Exiting...")
            break
            
        if not user_input.strip():
            continue

        try:
            # Step 1: Generate Lesson Script using Gemini
            print(f"\n[1/2] Generating lesson script for '{user_input}'...")
            lesson_script = generate_video_description(user_input)
            
            print("\nGenerated Script:")
            print("-" * 20)
            print(lesson_script)
            print("-" * 20)
            
            confirm = input("\nProceed with video generation? (y/n): ")
            if confirm.lower() != 'y':
                print("Skipping video generation.")
                continue

            # Step 2: Generate Audio using Magic Hour (Text-to-Speech)
            print("\n[2/4] Generating Audio for script...")
            audio_path = generate_speech(lesson_script)
            if not audio_path:
                print("Failed to generate audio. Stopping.")
                continue

            # Step 3: Generate Video using Magic Hour (Text-to-Video)
            print("\n[3/4] Generating Video visual for script...")
            
            # We can optionally prepend a style instruction to the script for the video generator
            # or just pass the script as is. Since we want an educational video:
            video_prompt = f"Educational video, clear visualization. {lesson_script}"
            
            video_result = generate_text_to_video(video_prompt)
            if not video_result or not video_result.downloaded_paths:
                print("Failed to generate video. Stopping.")
                continue
            
            video_path = video_result.downloaded_paths[0]

            # Step 4: Combine
            print("\n[4/4] Combining Audio and Video...")
            final_output = f"outputs/final_lesson_{user_input.replace(' ', '_')}.mp4"
            combine_audio_video(video_path, audio_path, final_output)
            
        except Exception as e:
            print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()
