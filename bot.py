import discord
import aioftp
import re
import os
import asyncio
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
FTP_HOST = os.getenv("FTP_HOST")
FTP_USER = os.getenv("FTP_USER")
FTP_PASS = os.getenv("FTP_PASS")
FTP_PATH = "/server-data/Logs/"
SCAN_INTERVAL = 180  # seconds between scans

intents = discord.Intents.default()
client = discord.Client(intents=intents)
last_seen = set()

async def find_chat_log_file():
    async with aioftp.Client.context(FTP_HOST, FTP_USER, FTP_PASS) as ftp:
        await ftp.change_directory(FTP_PATH)
        files = await ftp.list()
        for file in files:
            if "chat" in file.name.lower() and file.name.endswith(".txt"):
                return file.name
        return None

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

async def scan_and_post():
    await client.wait_until_ready()
    channel = client.get_channel(1236179374579912724)  # Your channel ID
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
                    for msg in messages[-5:]:
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
