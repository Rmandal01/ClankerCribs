import discord
from discord import app_commands
from discord.ext import commands
import os
import aiohttp
import asyncio
import io
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
MAGIC_HOUR_API_KEY = os.getenv("MAGIC_HOUR_API_KEY")
API_BASE_URL = "https://api.magichour.ai/v1"

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

        for i in range(60):  # Max 5 minutes
            result, status = await self._request("GET", endpoint)
            if status != 200:
                return None, f"Error checking status: {result}"

            state = result.get("status")
            print(f"[Poll {i+1}] Project {project_id}: {state}", flush=True)

            # Update Discord message when status changes
            if state != last_status:
                last_status = state
                status_icons = {
                    "queued": "🕐 **Queued** - Waiting in line...",
                    "rendering": "🎬 **Rendering** - Creating your video...",
                    "complete": "✅ **Complete** - Video ready!"
                }
                status_text = status_icons.get(state, f"⏳ {state}")

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
        return None, "Timeout: Generation took longer than 5 minutes"

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
                        duration: float = 3, fps: int = 8):
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
                "audio_source": "none"
            }
        }
        if image_url:
            data["assets"]["image_file_path"] = image_url
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


@bot.event
async def on_ready():
    print(f"Bot is ready! Logged in as {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"Failed to sync commands: {e}")


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
        await interaction.followup.send(f"❌ Failed to animate: {error}")
        return

    video_url = result.get("downloads", [{}])[0].get("url") or result.get("video_url") or result.get("output", {}).get("url")
    if video_url:
        # Download and upload video directly
        video_data = await api.download_video(video_url)
        if video_data:
            file = discord.File(io.BytesIO(video_data), filename="animation.mp4")
            embed = discord.Embed(
                title="✨ Animation Complete!",
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


@bot.tree.command(name="magichelp", description="Show all available Magic Hour commands")
async def magichelp(interaction: discord.Interaction):
    embed = discord.Embed(title="Magic Hour Video Bot Commands", color=0x9b59b6)

    commands_list = [
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


if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
