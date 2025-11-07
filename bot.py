import discord
import aioftp
import re
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

FTP_HOST = "38.58.177.88"
FTP_USER = "zoUjiYlb0cQy"
FTP_PASS = "RyoHyXlrCjtj"  # If there's no password, leave this blank
FTP_PATH = "/server-data/Logs/"


# Set up Discord client
intents = discord.Intents.default()
client = discord.Client(intents=intents)

# FTP + Regex logic
async def fetch_and_parse_file(filename, pattern):
    async with aioftp.Client.context(FTP_HOST, FTP_USER, FTP_PASS) as ftp:
        stream = await ftp.download_stream(filename)
        content = await stream.read()
        text = content.decode("utf-8")
        matches = re.findall(pattern, text)
        return matches

# Bot events
@client.event
async def on_ready():
    print(f"Logged in as {client.user}")

@client.event
async def on_message(message):
    if message.author.bot:
        return

    if message.content.startswith("!scanlog"):
        parts = message.content.split(" ", 2)
        if len(parts) < 3:
            await message.channel.send("Usage: `!scanlog filename regex`")
            return

        filename, pattern = parts[1], parts[2]
        try:
            results = await fetch_and_parse_file(filename, pattern)
            if results:
                preview = "\n".join(results[:10])
                await message.channel.send(f"**Matches found:**\n```{preview}```")
            else:
                await message.channel.send("No matches found.")
        except Exception as e:
            await message.channel.send(f"Error: `{e}`")

# Run the bot
client.run(TOKEN)
