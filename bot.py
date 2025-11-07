import discord
import aioftp
import re
import os
import asyncio
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
FTP_HOST = os.getenv("38.58.177.88")
FTP_USER = os.getenv("zoUjiYlb0cQy")
FTP_PASS = os.getenv("RyoHyXlrCjtj")
FTP_PATH = "/server-data/Logs/"
SCAN_INTERVAL = 180  # seconds between scans

# Discord setup
intents = discord.Intents.default()
client = discord.Client(intents=intents)

# Track last seen messages to avoid duplicates
last_seen = set()

# Find the latest chat log file
async def find_chat_log_file():
    async with aioftp.Client.context(FTP_HOST, FTP_USER, FTP_PASS) as ftp:
        await ftp.change_directory(FTP_PATH)
        files = await ftp.list()
        for file in files:
            if "chat" in file.name.lower() and file.name.endswith(".txt"):
                return file.name
        return None

# Parse General chat messages
def extract_general_chat(text):
    pattern = r"\[(\d{2}-\d{2}-\d{2} (\d{2}:\d{2}))\]\n\[info\] Got message:ChatMessage\{chat=General, author='([^']+)', text='([^']+)'\}"
    matches = re.findall(pattern, text)
    results = []
    for (_, time, author, message) in matches:
        key = f"{time}-{author}-{message}"
        if key not in last_seen:
            last_seen.add(key)
            results.append(f"{time}-{author}: {message}")
    return results

# Scan and post to Discord
async def scan_and_post():
    await client.wait_until_ready()
    channel = discord.utils.get(client.get_all_channels(), name="general")  # Change to your channel name
    if not channel:
        print("Channel not found.")
        return

    while not client.is_closed():
        try:
            filename = await find_chat_log_file()
            if filename:
                async with aioftp.Client.context(FTP_HOST, FTP_USER, FTP_PASS) as ftp:
                    stream = await ftp.download_stream(f"{FTP_PATH}{filename}")
                    content = await stream.read()
                    text = content.decode("utf-8")
                    messages = extract_general_chat(text)
                    for msg in messages[-5:]:  # Send last 5 new messages
                        await channel.send(msg)
            else:
                print("No chat log file found.")
        except Exception as e:
            print(f"Error during scan: {e}")
        await asyncio.sleep(SCAN_INTERVAL)

@client.event
async def on_ready():
    print(f"Logged in as {client.user}")
    client.loop.create_task(scan_and_post())

client.run(TOKEN)
