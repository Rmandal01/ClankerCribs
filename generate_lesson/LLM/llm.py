import os
from dotenv import load_dotenv
import google.generativeai as genai

# Load environment variables from a .env file if it exists
load_dotenv()

def generate_text(prompt, api_key=None):
    """
    Generates text using the Google Gemini API.
    
    Args:
        prompt (str): The text prompt to send to the model.
        api_key (str, optional): The Gemini API key. If not provided, 
                                 it will attempt to look for 'GEMINI_API_KEY' environment variable.
    
    Returns:
        str: The generated text response.
    """
    
    # key configuration
    if not api_key:
        api_key = os.environ.get('GEMINI_API_KEY')
    
    if not api_key:
        raise ValueError("API Key is required. Please provide it as an argument or set 'GEMINI_API_KEY' environment variable.")

    genai.configure(api_key=api_key)

    # Use the gemini-1.5-flash model (efficient and fast)
    model = genai.GenerativeModel('gemini-2.0-flash-exp')
    
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Error generating text: {str(e)}"

def generate_video_description(user_input, api_key=None):
    """
    Wraps the user input in a specific prompt for video motion description
    and generates the response using Gemini.
    """
    ai_prompt = f"""
    You are an expert teacher creating short educational scripts for text-to-video generation.

I will give you a topic (a word, phrase, or short sentence).

Generate a clear, engaging teaching script that lasts at most 30 seconds when spoken.

Rules:

at most 

Use simple, clear language

Write short, natural sentences for voice narration

Explain ideas step by step

No emojis, bullet points, or markdown

Do NOT say “this video” or address the viewer directly

No camera, scene, or sound directions

Output plain text only

Structure:

Brief hook or introduction

Core explanation (main idea)

One simple example if helpful

Short summary or takeaway

Topic: {user_input}
"""
    return generate_text(ai_prompt, api_key)

if __name__ == "__main__":
    # Example usage code for testing
    print("Testing Gemini API integration...")
    
    # ------------------------------------------------------------------
    # TODO: PASTE YOUR API KEY BELOW IF IT'S NOT IN YOUR ENVIRONMENT VARIABLES
    # ------------------------------------------------------------------
    # my_api_key = "PASTE_YOUR_KEY_HERE"
    # os.environ['GEMINI_API_KEY'] = my_api_key 

    while True:
        try:
            print("\n" + "="*50)
            user_input = input("Type your prompt here (or 'quit' to exit): ")
            AI_PROMPT = f"""
Role: You are a video motion descriptor for image-to-video generation.

Task:
The user provides a visual subject.
You must describe ONLY how that subject is animated over time.

Rules (MANDATORY):
- Do NOT add new objects, characters, environments, or background elements
- Do NOT introduce story or narrative
- Do NOT explain or interpret meaning
- ONLY describe motion, camera movement, lighting, and subtle changes
- Assume the image already contains everything mentioned

Output format (EXACT):

START:
Describe the initial camera view and lighting of the subject.

MIDDLE:
Describe gradual motion or visual changes applied to the same subject.

END:
Describe the final camera position and stabilized appearance of the subject.

User input:
{user_input}


"""
            if user_input.lower() in ['quit', 'exit']:
                break
            
            if not user_input.strip():
                continue
                
            print(f"\nGenerative response...")
            result = generate_video_description(user_input)
            print("-" * 20)
            print(result)
            print("-" * 20)
        except Exception as e:
            print(f"Error: {e}")
            break
