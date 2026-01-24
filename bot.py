import discord
from discord import app_commands
from discord.ext import commands
import os
import aiohttp
import asyncio
import io
import random
import edge_tts
import sys
from dotenv import load_dotenv

# Fix Windows console encoding for Unicode characters
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# Add generate_lesson to path
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "generate_lesson"))

import traceback
try:
    from LLM.llm import generate_video_description
    from text_to_video import generate_text_to_video
    from text_speech import generate_speech
    from main import combine_audio_video
except ImportError as e:
    print(f"CRITICAL ERROR importing generate_lesson modules: {e}")
    traceback.print_exc()
    # Define dummy functions to prevent NameError, but command will fail
    def generate_video_description(*args): raise ImportError("Module not loaded")
    def generate_text_to_video(*args): raise ImportError("Module not loaded")
    def generate_speech(*args): raise ImportError("Module not loaded")
    def combine_audio_video(*args): raise ImportError("Module not loaded")




load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
MAGIC_HOUR_API_KEY = os.getenv("MAGIC_HOUR_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
API_BASE_URL = "https://api.magichour.ai/v1"
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
GEMINI_VEO_URL = "https://generativelanguage.googleapis.com/v1beta/models/veo-3.1-generate-preview:generateVideo"

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)


class MagicHourAPI:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

    async def _request(self, method: str, endpoint: str, data: dict = None):
        async with aiohttp.ClientSession() as session:
            url = f"{API_BASE_URL}{endpoint}"
            async with session.request(method, url, headers=self.headers, json=data) as resp:
                return await resp.json(), resp.status

    async def _poll_project_with_updates(self, project_id: str, interaction: discord.Interaction,
                                          prompt: str, project_type: str = "video"):
        """Poll until project is complete with live status updates"""
        endpoint = f"/{project_type}-projects/{project_id}"
        last_status = None
        status_msg = None

        for i in range(120):  # Max 10 minutes
            result, status = await self._request("GET", endpoint)
            if status != 200:
                return None, f"Error checking status: {result}"

            state = result.get("status")
            print(f"[Poll {i+1}] Project {project_id}: {state}", flush=True)

            # Update Discord message when status changes
            if state != last_status:
                last_status = state
                status_icons = {
                    "queued": "**Queued** - Waiting in line...",
                    "rendering": "**Rendering** - Creating your video...",
                    "complete": "**Complete** - Video ready!"
                }
                status_text = status_icons.get(state, f"{state}")

                embed = discord.Embed(
                    title="Animation in Progress",
                    description=f"**Prompt:** {prompt}\n\n{status_text}",
                    color=0xffa500 if state != "complete" else 0x00ff00
                )

                if status_msg is None:
                    status_msg = await interaction.followup.send(embed=embed)
                else:
                    await status_msg.edit(embed=embed)

            if state == "complete":
                return result, None
            elif state == "error":
                return None, f"Generation failed: {result.get('error', 'Unknown error')}"

            await asyncio.sleep(5)
        return None, "Timeout: Generation took longer than 10 minutes"

    async def download_video(self, url: str) -> bytes:
        """Download video from URL"""
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    return await resp.read()
                return None

    async def text_to_video(self, prompt: str, duration: int = 5):
        data = {
            "end_seconds": duration,
            "style": {
                "prompt": prompt
            }
        }
        result, status = await self._request("POST", "/text-to-video", data)
        if status not in [200, 201]:
            return None, f"API Error ({status}): {result.get('message', result)}"

        project_id = result.get("id")
        return await self._poll_project(project_id, "video")

    async def image_to_video(self, image_url: str, prompt: str = "", duration: int = 5):
        data = {
            "end_seconds": duration,
            "assets": {
                "image_file_path": image_url
            }
        }
        if prompt:
            data["style"] = {"prompt": prompt}
        result, status = await self._request("POST", "/image-to-video", data)
        if status not in [200, 201]:
            return None, f"API Error ({status}): {result.get('message', result)}"

        project_id = result.get("id")
        return await self._poll_project(project_id, "video")

    async def face_swap(self, video_url: str, face_image_url: str):
        data = {
            "assets": {
                "video_url": video_url,
                "face_image_url": face_image_url
            }
        }
        result, status = await self._request("POST", "/face-swap", data)
        if status not in [200, 201]:
            return None, f"API Error ({status}): {result.get('message', result)}"

        project_id = result.get("id")
        return await self._poll_project(project_id, "video")

    async def animation(self, prompt: str, interaction: discord.Interaction, image_url: str = None,
                        art_style: str = "Photograph", camera_effect: str = "Simple Zoom In",
                        duration: float = 3, fps: int = 8, audio_url: str = None):
        data = {
            "fps": fps,
            "end_seconds": duration,
            "height": 576,
            "width": 576,
            "style": {
                "art_style": art_style,
                "camera_effect": camera_effect,
                "prompt_type": "custom",
                "prompt": prompt,
                "transition_speed": 5
            },
            "assets": {
                "audio_source": "none" if not audio_url else "file",
            }
        }
        if image_url:
            data["assets"]["image_file_path"] = image_url
        if audio_url:
            data["assets"]["audio_file_path"] = audio_url
        result, status = await self._request("POST", "/animation", data)
        if status not in [200, 201]:
            return None, f"API Error ({status}): {result.get('message', result)}"

        project_id = result.get("id")
        return await self._poll_project_with_updates(project_id, interaction, prompt, "video")

    async def lip_sync(self, video_url: str, audio_url: str):
        data = {
            "assets": {
                "video_url": video_url,
                "audio_url": audio_url
            }
        }
        result, status = await self._request("POST", "/lip-sync", data)
        if status not in [200, 201]:
            return None, f"API Error ({status}): {result.get('message', result)}"

        project_id = result.get("id")
        return await self._poll_project(project_id, "video")

    async def ai_talking_photo(self, image_url: str, audio_url: str):
        data = {
            "assets": {
                "image_url": image_url,
                "audio_url": audio_url
            }
        }
        result, status = await self._request("POST", "/ai-talking-photo", data)
        if status not in [200, 201]:
            return None, f"API Error ({status}): {result.get('message', result)}"

        project_id = result.get("id")
        return await self._poll_project(project_id, "video")


api = MagicHourAPI(MAGIC_HOUR_API_KEY)


async def generate_brainrot_script(prompt: str, character_name: str) -> str:
    """Use Gemini to generate a creative brainrot-style script"""
    try:
        system_prompt = f"""You are a brainrot meme script writer. Generate a short, funny, absurdist script (2-4 sentences) in the style of Italian brainrot memes (like Tralalero Tralala, Cappuccino Assassino, etc.).

The character is: {character_name}
The topic/prompt is: {prompt}

Rules:
- Keep it short (under 50 words) for TTS
- Make it absurd and surreal
- Can include made-up Italian-sounding words
- Should be funny and chaotic
- Don't use hashtags or emojis
- Write in English but can sprinkle Italian-sounding nonsense words

Just output the script, nothing else."""

        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
            payload = {
                "contents": [{"parts": [{"text": system_prompt}]}],
                "generationConfig": {
                    "temperature": 1.0,
                    "maxOutputTokens": 150
                }
            }
            print(f"Calling Gemini API for script generation...", flush=True)
            async with session.post(
                f"{GEMINI_API_URL}?key={GEMINI_API_KEY}",
                json=payload,
                headers={"Content-Type": "application/json"}
            ) as resp:
                print(f"Gemini API response status: {resp.status}", flush=True)
                if resp.status == 200:
                    data = await resp.json()
                    if "candidates" in data and len(data["candidates"]) > 0:
                        script = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                        print(f"Gemini script: {script}", flush=True)
                        return script
                    else:
                        print(f"Gemini response missing candidates: {data}", flush=True)
                else:
                    error = await resp.text()
                    print(f"Gemini API error ({resp.status}): {error}", flush=True)
    except asyncio.TimeoutError:
        print(f"Gemini API timeout after 30 seconds", flush=True)
    except aiohttp.ClientError as e:
        print(f"Gemini API connection error: {e}", flush=True)
    except Exception as e:
        print(f"Gemini error: {e}", flush=True)

    # Fallback to original prompt if Gemini fails
    print(f"Falling back to original prompt: {prompt}", flush=True)
    return prompt


async def generate_tts_audio(text: str, voice: str = "en-US-ChristopherNeural") -> str:
    """Generate TTS audio and upload to file hosting, returns URL"""
    try:
        # Generate TTS audio
        print(f"Generating TTS for: {text[:50]}...", flush=True)
        communicate = edge_tts.Communicate(text, voice)
        audio_data = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_data += chunk["data"]

        print(f"TTS generated, size: {len(audio_data)} bytes", flush=True)

        if len(audio_data) == 0:
            print("Error: No audio data generated", flush=True)
            return None

        async with aiohttp.ClientSession() as session:
            # Try catbox.moe (reliable for audio files)
            try:
                form = aiohttp.FormData()
                form.add_field('reqtype', 'fileupload')
                form.add_field('fileToUpload', audio_data, filename='tts.mp3', content_type='audio/mpeg')
                async with session.post('https://catbox.moe/user/api.php', data=form) as resp:
                    print(f"Catbox response status: {resp.status}", flush=True)
                    if resp.status == 200:
                        url = (await resp.text()).strip()
                        print(f"Catbox URL: {url}", flush=True)
                        if url.startswith('https://'):
                            return url
            except Exception as e:
                print(f"Catbox error: {e}", flush=True)

            # Fallback: try litterbox (temporary catbox)
            try:
                form2 = aiohttp.FormData()
                form2.add_field('reqtype', 'fileupload')
                form2.add_field('time', '1h')
                form2.add_field('fileToUpload', audio_data, filename='tts.mp3', content_type='audio/mpeg')
                async with session.post('https://litterbox.catbox.moe/resources/internals/api.php', data=form2) as resp:
                    print(f"Litterbox response status: {resp.status}", flush=True)
                    if resp.status == 200:
                        url = (await resp.text()).strip()
                        print(f"Litterbox URL: {url}", flush=True)
                        if url.startswith('https://'):
                            return url
            except Exception as e:
                print(f"Litterbox error: {e}", flush=True)

        return None
    except Exception as e:
        print(f"TTS Error: {e}", flush=True)
        return None


async def generate_video_with_gemini(prompt: str, image_url: str = None, interaction: discord.Interaction = None) -> tuple:
    """Generate video using Gemini Veo 3.1 API
    
    Uses the veo-3.1-generate-preview model via Gemini API.
    Note: Veo 3.1 may require preview access and might not be available
    via REST API with all API keys. If you get 404, check:
    1. Your API key has Veo access enabled in Google AI Studio
    2. Veo 3.1 preview is enabled for your account
    3. The model name is correct: veo-3.1-generate-preview
    
    Returns tuple of (result_dict, error_string)
    """
    import base64
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=300)) as session:
            # Build the request payload for Veo 3.1 (Gemini API format)
            payload = {
                "prompt": prompt
            }
            
            # If we have an image, add it as reference for image-to-video
            if image_url:
                try:
                    async with session.get(image_url) as img_resp:
                        if img_resp.status == 200:
                            img_data = await img_resp.read()
                            img_b64 = base64.b64encode(img_data).decode('utf-8')
                            payload["image"] = {
                                "bytesBase64Encoded": img_b64,
                                "mimeType": "image/png"
                            }
                except Exception as e:
                    print(f"Failed to download image for Veo: {e}", flush=True)

            print(f"Starting Gemini Veo generation for: {prompt[:50]}...", flush=True)
            print(f"Veo API URL: {GEMINI_VEO_URL}", flush=True)
            print(f"Payload keys: {list(payload.keys())}", flush=True)

            # Start the async generation
            operation_name = None
            try:
                async with session.post(
                    f"{GEMINI_VEO_URL}?key={GEMINI_API_KEY}",
                    json=payload,
                    headers={"Content-Type": "application/json"}
                ) as resp:
                    response_text = await resp.text()
                    print(f"Veo response status: {resp.status}", flush=True)
                    print(f"Veo response headers: {dict(resp.headers)}", flush=True)
                    print(f"Veo full response: {response_text[:1000]}", flush=True)

                    if resp.status != 200:
                        print(f"Veo API error (status {resp.status}): {response_text[:1000]}", flush=True)
                        # Extract more detailed error if available
                        try:
                            error_json = await resp.json()
                            print(f"Veo error JSON: {error_json}", flush=True)
                            if "error" in error_json:
                                error_detail = error_json["error"].get("message", str(error_json["error"]))
                                error_code = error_json["error"].get("code", "")
                                return None, f"Veo API Error ({resp.status}): {error_detail} (Code: {error_code})"
                        except Exception as e:
                            print(f"Failed to parse error JSON: {e}", flush=True)
                        return None, f"Veo API Error ({resp.status}): {response_text[:300]}"

                    try:
                        result = await resp.json()
                        print(f"Veo response JSON: {str(result)[:500]}", flush=True)
                    except Exception as json_err:
                        print(f"Failed to parse JSON: {json_err}, raw: {response_text[:500]}", flush=True)
                        result = {"raw": response_text}

                    # Check if it's a long-running operation
                    operation_name = result.get("name")
                    
                    # Also check for error in response
                    if "error" in result:
                        error_info = result.get("error", {})
                        error_msg = error_info.get("message", str(error_info))
                        print(f"Veo API returned error: {error_msg}", flush=True)
                        return None, f"Veo API error: {error_msg}"

                    if not operation_name:
                        # Maybe direct response with video? (Veo 3.1 format)
                        if "generatedVideos" in result or "generated_videos" in result:
                            videos = result.get("generatedVideos") or result.get("generated_videos", [])
                            if videos and len(videos) > 0:
                                video_obj = videos[0]
                                # Veo 3.1 returns video as file reference or base64
                                if "video" in video_obj:
                                    video_data = video_obj["video"]
                                    if isinstance(video_data, dict):
                                        video_b64 = video_data.get("bytesBase64Encoded")
                                        if video_b64:
                                            video_bytes = base64.b64decode(video_b64)
                                            print(f"Veo video generated directly, size: {len(video_bytes)} bytes", flush=True)
                                            return {"video_bytes": video_bytes}, None
                        # Log the full response for debugging
                        print(f"Veo unexpected response structure: {str(result)[:1000]}", flush=True)
                        return None, f"Unexpected response format. Check logs for details."

                    print(f"Veo operation started: {operation_name}", flush=True)
            except aiohttp.ClientError as conn_err:
                print(f"Veo connection error: {conn_err}", flush=True)
                return None, f"Veo connection error: {str(conn_err)}"

            if not operation_name:
                return None, "No operation name returned from Veo API"

            # Poll for completion
            # Veo 3.1 operations format: operations/{operation_id} or just the ID
            if "/" in operation_name:
                # Already has full path
                if operation_name.startswith("operations/"):
                    poll_url = f"https://generativelanguage.googleapis.com/v1beta/{operation_name}?key={GEMINI_API_KEY}"
                else:
                    poll_url = f"https://generativelanguage.googleapis.com/v1beta/{operation_name}?key={GEMINI_API_KEY}"
            else:
                # Just the operation ID
                poll_url = f"https://generativelanguage.googleapis.com/v1beta/operations/{operation_name}?key={GEMINI_API_KEY}"

            for i in range(60):  # Max 5 minutes (5 sec intervals)
                await asyncio.sleep(5)

                try:
                    async with session.get(poll_url) as poll_resp:
                        if poll_resp.status != 200:
                            print(f"[Veo Poll {i+1}] Status: {poll_resp.status}", flush=True)
                            continue

                        poll_result = await poll_resp.json()
                        done = poll_result.get("done", False)

                        print(f"[Veo Poll {i+1}] Done: {done}", flush=True)

                        if done:
                            # Check for error
                            if "error" in poll_result:
                                error = poll_result["error"]
                                return None, f"Veo generation failed: {error.get('message', str(error))}"

                            # Get the video (Veo 3.1 format)
                            response = poll_result.get("response", {})
                            videos = response.get("generatedVideos") or response.get("generated_videos", [])

                            if videos and len(videos) > 0:
                                video_obj = videos[0]
                                if "video" in video_obj:
                                    video_data = video_obj["video"]
                                    if isinstance(video_data, dict):
                                        video_b64 = video_data.get("bytesBase64Encoded")
                                        if video_b64:
                                            video_bytes = base64.b64decode(video_b64)
                                            print(f"Veo video generated, size: {len(video_bytes)} bytes", flush=True)
                                            return {"video_bytes": video_bytes}, None
                                    # If video is a file reference, we'd need to download it
                                    elif isinstance(video_data, str):
                                        # File URI - would need to download
                                        print(f"Veo returned file reference: {video_data}", flush=True)
                                        return None, "Video returned as file reference (not yet implemented)"

                            return None, "No video data in response"
                except Exception as poll_error:
                    print(f"[Veo Poll {i+1}] Error: {poll_error}", flush=True)
                    continue

            return None, "Timeout: Veo generation took too long"

    except Exception as e:
        print(f"Veo error: {e}", flush=True)
        return None, f"Veo error: {str(e)}"


@bot.event
async def on_ready():
    print(f"Bot is ready! Logged in as {bot.user}", flush=True)
    try:
        # Sync to all guilds for instant command visibility
        for guild in bot.guilds:
            bot.tree.copy_global_to(guild=guild)
            await bot.tree.sync(guild=guild)
            print(f"Synced commands to {guild.name}", flush=True)
        print(f"Synced commands to {len(bot.guilds)} server(s)", flush=True)
    except Exception as e:
        print(f"Failed to sync commands: {e}", flush=True)


@bot.tree.command(name="text2video", description="Generate a video from a text prompt")
@app_commands.describe(prompt="Describe the video you want to generate", duration="Video duration in seconds (default: 5)")
async def text2video(interaction: discord.Interaction, prompt: str, duration: int = 5):
    await interaction.response.defer(thinking=True)

    result, error = await api.text_to_video(prompt, duration)

    if error:
        await interaction.followup.send(f"Failed to generate video: {error}")
        return

    video_url = result.get("downloads", [{}])[0].get("url") or result.get("video_url") or result.get("output", {}).get("url")
    if video_url:
        embed = discord.Embed(title="Text to Video", description=f"**Prompt:** {prompt}", color=0x00ff00)
        embed.add_field(name="Video", value=f"[Download Video]({video_url})")
        await interaction.followup.send(embed=embed)
    else:
        await interaction.followup.send(f"Video generated but couldn't get download URL. Response: {result}")


@bot.tree.command(name="img2video", description="Convert an image to a video")
@app_commands.describe(image_url="URL of the image", prompt="Optional motion description", duration="Video duration in seconds (default: 5)")
async def img2video(interaction: discord.Interaction, image_url: str, prompt: str = "", duration: int = 5):
    await interaction.response.defer(thinking=True)

    result, error = await api.image_to_video(image_url, prompt, duration)

    if error:
        await interaction.followup.send(f"Failed to generate video: {error}")
        return

    video_url = result.get("downloads", [{}])[0].get("url") or result.get("video_url") or result.get("output", {}).get("url")
    if video_url:
        embed = discord.Embed(title="Image to Video", color=0x00ff00)
        embed.set_thumbnail(url=image_url)
        embed.add_field(name="Video", value=f"[Download Video]({video_url})")
        await interaction.followup.send(embed=embed)
    else:
        await interaction.followup.send(f"Video generated but couldn't get download URL. Response: {result}")


@bot.tree.command(name="faceswap", description="Swap a face in a video")
@app_commands.describe(video_url="URL of the video", face_image_url="URL of the face image to swap in")
async def faceswap(interaction: discord.Interaction, video_url: str, face_image_url: str):
    await interaction.response.defer(thinking=True)

    result, error = await api.face_swap(video_url, face_image_url)

    if error:
        await interaction.followup.send(f"Failed to swap face: {error}")
        return

    output_url = result.get("downloads", [{}])[0].get("url") or result.get("video_url") or result.get("output", {}).get("url")
    if output_url:
        embed = discord.Embed(title="Face Swap", color=0x00ff00)
        embed.add_field(name="Video", value=f"[Download Video]({output_url})")
        await interaction.followup.send(embed=embed)
    else:
        await interaction.followup.send(f"Face swap completed but couldn't get download URL. Response: {result}")


@bot.tree.command(name="animate", description="Create an animated video from a prompt")
@app_commands.describe(
    prompt="Describe what you want to animate",
    image_url="Optional: URL of starting image",
    art_style="Art style (default: Photograph)",
    duration="Video duration in seconds (default: 3)"
)
@app_commands.choices(art_style=[
    app_commands.Choice(name="Photograph", value="Photograph"),
    app_commands.Choice(name="3D Render", value="3D Render"),
    app_commands.Choice(name="Cyberpunk", value="Cyberpunk"),
    app_commands.Choice(name="Studio Ghibli", value="Studio Ghibli Film Still"),
    app_commands.Choice(name="Oil Painting", value="Oil Painting"),
    app_commands.Choice(name="Pixel Art", value="Pixel Art"),
    app_commands.Choice(name="Anime", value="Futuristic Anime"),
    app_commands.Choice(name="Fantasy", value="Fantasy"),
])
async def animate(interaction: discord.Interaction, prompt: str, image_url: str = None,
                  art_style: str = "Photograph", duration: int = 3):
    await interaction.response.defer()

    result, error = await api.animation(prompt, interaction, image_url, art_style, "Simple Zoom In", duration)

    if error:
        await interaction.followup.send(f"Failed to animate: {error}")
        return

    video_url = result.get("downloads", [{}])[0].get("url") or result.get("video_url") or result.get("output", {}).get("url")
    if video_url:
        # Download and upload video directly
        video_data = await api.download_video(video_url)
        if video_data:
            file = discord.File(io.BytesIO(video_data), filename="animation.mp4")
            embed = discord.Embed(
                title="Animation Complete!",
                description=f"**Prompt:** {prompt}\n**Style:** {art_style}",
                color=0x00ff00
            )
            await interaction.followup.send(embed=embed, file=file)
        else:
            embed = discord.Embed(title="Animation", description=f"**Prompt:** {prompt}", color=0x00ff00)
            embed.add_field(name="Video", value=f"[Download Video]({video_url})")
            await interaction.followup.send(embed=embed)
    else:
        await interaction.followup.send(f"Animation completed but couldn't get download URL. Response: {result}")


@bot.tree.command(name="lipsync", description="Sync lips in a video to audio")
@app_commands.describe(video_url="URL of the video", audio_url="URL of the audio file")
async def lipsync(interaction: discord.Interaction, video_url: str, audio_url: str):
    await interaction.response.defer(thinking=True)

    result, error = await api.lip_sync(video_url, audio_url)

    if error:
        await interaction.followup.send(f"Failed to lip sync: {error}")
        return

    output_url = result.get("downloads", [{}])[0].get("url") or result.get("video_url") or result.get("output", {}).get("url")
    if output_url:
        embed = discord.Embed(title="Lip Sync", color=0x00ff00)
        embed.add_field(name="Video", value=f"[Download Video]({output_url})")
        await interaction.followup.send(embed=embed)
    else:
        await interaction.followup.send(f"Lip sync completed but couldn't get download URL. Response: {result}")


@bot.tree.command(name="talkingphoto", description="Make a photo talk with audio")
@app_commands.describe(image_url="URL of the image (should contain a face)", audio_url="URL of the audio file")
async def talkingphoto(interaction: discord.Interaction, image_url: str, audio_url: str):
    await interaction.response.defer(thinking=True)

    result, error = await api.ai_talking_photo(image_url, audio_url)

    if error:
        await interaction.followup.send(f"Failed to create talking photo: {error}")
        return

    video_url = result.get("downloads", [{}])[0].get("url") or result.get("video_url") or result.get("output", {}).get("url")
    if video_url:
        embed = discord.Embed(title="Talking Photo", color=0x00ff00)
        embed.set_thumbnail(url=image_url)
        embed.add_field(name="Video", value=f"[Download Video]({video_url})")
        await interaction.followup.send(embed=embed)
    else:
        await interaction.followup.send(f"Talking photo created but couldn't get download URL. Response: {result}")


# Brainrot meme characters (local files)
BRAINROT_CHARACTERS = {
    "cappuccino": ("Cappuccino Assassino", "memes_ref/Cappuccino-Assassino-Viral-TikTok.png"),
    "chimpanzini": ("Chimpanzini Bananini", "memes_ref/Chimpanzini-Bananini-Viral-TikTok-Meme.png"),
    "broccoli": ("Broccoli Assassini", "memes_ref/Brainrot-Character-Broccoli-Assassini-6153.png"),
    "frigo": ("Frigo Camelo", "memes_ref/Frigo-Camelo-Brainrot-9951.png"),
    "orangutini": ("Orangutini Ananasini", "memes_ref/Orangutini-Ananasini-Brainrot-Meme.png"),
    "cocofanto": ("Cocofanto Elefanto", "memes_ref/Cocofanto-Elefanto-Brainrot-Meme-Elephant-Coconut-1758.png"),
    "lirili": ("Lirili Larila", "memes_ref/Lirili-Larila-Elephant-in-a-Cactus-Meme-TikTok-Brainrot.png"),
    "sahur": ("Ta Ta Ta Sahur", "memes_ref/Ta-Ta-Ta-Sahur-TikTok-Viral-Character-5520.png"),
}

# Cache for uploaded character images
CHARACTER_IMAGE_URLS = {}


async def upload_character_image(character_key: str) -> str:
    """Upload a character image to catbox and cache the URL"""
    if character_key in CHARACTER_IMAGE_URLS:
        return CHARACTER_IMAGE_URLS[character_key]

    _, filepath = BRAINROT_CHARACTERS[character_key]
    full_path = os.path.join(os.path.dirname(__file__), filepath)

    try:
        with open(full_path, 'rb') as f:
            image_data = f.read()

        async with aiohttp.ClientSession() as session:
            form = aiohttp.FormData()
            form.add_field('reqtype', 'fileupload')
            form.add_field('fileToUpload', image_data, filename=os.path.basename(filepath), content_type='image/png')
            async with session.post('https://catbox.moe/user/api.php', data=form) as resp:
                if resp.status == 200:
                    url = (await resp.text()).strip()
                    if url.startswith('https://'):
                        CHARACTER_IMAGE_URLS[character_key] = url
                        print(f"Uploaded {character_key}: {url}", flush=True)
                        return url
    except Exception as e:
        print(f"Failed to upload character image: {e}", flush=True)
    return None


@bot.tree.command(name="brainrot_v2", description="Generate brainrot-style AI video (5 sec)")
@app_commands.describe(
    prompt="What brainrot content do you want to generate?",
    intensity="How unhinged should it be? (default: medium)"
)
@app_commands.choices(
    intensity=[
        app_commands.Choice(name="mild", value="mild"),
        app_commands.Choice(name="medium", value="medium"),
        app_commands.Choice(name="unhinged", value="unhinged"),
    ]
)
async def brainrot(interaction: discord.Interaction, prompt: str, intensity: str = "medium"):
    await interaction.response.defer()

    # Randomly select a brainrot character first
    character = random.choice(list(BRAINROT_CHARACTERS.keys()))
    character_name, _ = BRAINROT_CHARACTERS[character]

    # Status update
    status_msg = await interaction.followup.send(f"{character_name} is preparing...")

    await status_msg.edit(content=f"Loading {character_name}...")
    image_url = await upload_character_image(character)
    if not image_url:
        await status_msg.edit(content="Failed to upload character, continuing without image...")
        image_url = None

    await status_msg.edit(content="Creating 5s video with Magic Hour...")

    # Use Magic Hour image-to-video
    # We pass the prompt as the style prompt
    full_prompt = f"{prompt}, Italian brainrot meme style, surreal absurdist comedy, colorful vibrant animation, exaggerated expressions, chaotic energy"
    
    result, error = await api.image_to_video(image_url, full_prompt, duration=5)

    if error:
        await status_msg.edit(content=f"Magic Hour failed: {error}")
        return
    
    # Magic Hour returns download URL in result
    video_url = result.get("downloads", [{}])[0].get("url") or result.get("video_url") or result.get("output", {}).get("url")

    if video_url:
        embed = discord.Embed(
            title="BRAINROT GENERATED",
            description=f"**Prompt:** {prompt}\n**Character:** {character_name}",
            color=0xff00ff
        )
        embed.add_field(name="Video", value=f"[Download Video]({video_url})")
        await status_msg.delete()
        await interaction.followup.send(embed=embed)
    else:
        await status_msg.edit(content=f"Video generated but couldn't get download URL. Response: {result}")


@bot.tree.command(name="magichelp", description="Show all available Magic Hour commands")
async def magichelp(interaction: discord.Interaction):
    embed = discord.Embed(title="Magic Hour Video Bot Commands", color=0x9b59b6)

    commands_list = [
        ("`/brainrot`", "Generate brainrot-style chaotic AI video"),
        ("`/text2video`", "Generate video from text prompt"),
        ("`/img2video`", "Convert image to video"),
        ("`/faceswap`", "Swap face in a video"),
        ("`/animate`", "Animate a static image"),
        ("`/lipsync`", "Sync video lips to audio"),
        ("`/talkingphoto`", "Make a photo talk with audio"),
    ]

    for cmd, desc in commands_list:
        embed.add_field(name=cmd, value=desc, inline=False)

    embed.set_footer(text="Powered by Magic Hour AI")
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="generate_lesson", description="Generate an educational video lesson")
@app_commands.describe(topic="The lesson topic (e.g., 'Photosynthesis', 'Gravity')")
async def generate_lesson(interaction: discord.Interaction, topic: str):
    await interaction.response.defer(thinking=True)

    status_msg = await interaction.followup.send(f"[1/4] Generating script for: **{topic}**...")

    async def safe_edit(content):
        """Safely edit status message, ignoring errors if message was deleted"""
        try:
            await status_msg.edit(content=content)
        except discord.NotFound:
            pass  # Message was deleted, ignore
        except Exception:
            pass  # Other error, ignore

    loop = asyncio.get_running_loop()
    os.makedirs("outputs", exist_ok=True)

    try:
        # Step 1: Generate Script
        print(f"Generating script for {topic}...")
        script = await loop.run_in_executor(None, generate_video_description, topic)
        if not script:
            await safe_edit("Error: Failed to generate script")
            return

        await safe_edit(f"[2/4] Generating audio narration for: **{topic}**...")

        # Step 2: Generate Audio
        print("Generating audio...")
        audio_path = await loop.run_in_executor(None, generate_speech, script)
        if not audio_path:
            await safe_edit("Error: Failed to generate audio")
            return

        await safe_edit(f"[3/4] Generating video visuals for: **{topic}**... (this takes the longest)")

        # Step 3: Generate Video
        print("Generating video visual...")
        video_prompt = f"Educational video, clear visualization. {script}"
        video_result = await loop.run_in_executor(None, generate_text_to_video, video_prompt)

        if not video_result or not video_result.downloaded_paths:
            await safe_edit("Error: Failed to generate video")
            return

        video_path = video_result.downloaded_paths[0]

        await safe_edit(f"[4/4] Combining audio and video for: **{topic}**...")

        # Step 4: Combine
        print("Combining audio and video...")
        final_filename = f"outputs/final_lesson_{topic.replace(' ', '_')}_{random.randint(1000,9999)}.mp4"
        final_path = await loop.run_in_executor(None, combine_audio_video, video_path, audio_path, final_filename)

        if final_path and os.path.exists(final_path):
            file_size = os.path.getsize(final_path)
            # Discord limit: 8MB for standard servers
            if file_size > 8 * 1024 * 1024:
                await safe_edit(f"Video generated but it's too large to upload ({file_size/1024/1024:.1f}MB). Saved locally as `{final_path}`")
            else:
                file = discord.File(final_path)
                embed = discord.Embed(title=f"Lesson: {topic}", description=f"{script[:200]}...", color=0x3498db)
                try:
                    await status_msg.delete()
                except discord.NotFound:
                    pass
                await interaction.followup.send(embed=embed, file=file)
                print(f"Lesson video sent successfully: {final_path}")
        else:
            await safe_edit("Error: Video file was not created.")

    except Exception as e:
        print(f"Error in generate_lesson: {e}")
        await safe_edit(f"An error occurred: {str(e)}")



if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
