import discord
import aioftp
import re
import os
import asyncio
from dotenv import load_dotenv
from datetime import datetime
from discord.ext import commands

# Load environment variables
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
FTP_HOST = os.getenv("FTP_HOST")
FTP_USER = os.getenv("FTP_USER")
FTP_PASS = os.getenv("FTP_PASS")
FTP_PATH = "/server-data/Logs/"
SCAN_INTERVAL = 180
CHANNEL_ID = 1236179374579912724

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)
last_timestamp = None

async def find_chat_log_file():
    print("🔍 Scanning FTP directory for chat log files...")
    async with aioftp.Client.context(FTP_HOST, FTP_USER, FTP_PASS) as ftp:
        await ftp.change_directory(FTP_PATH)
        files = await ftp.list()
        for file in files:
            if "chat" in file.name.lower() and file.name.endswith(".txt"):
                print(f"📄 Found chat log file: {file.name}")
                return file.name
        print("⚠️ No matching chat log file found in FTP directory.")
        return None

def extract_new_messages(text):
    global last_timestamp
    pattern = r"\[(\d{2}-\d{2}-\d{2} (\d{2}:\d{2}))\]\n\[info\]\n Got message:ChatMessage\{chat=General, author='([^']+)', text='([^']+)'\}"
    matches = re.findall(pattern, text)
    new_messages = []
    for (date_str, time_str, author, message) in matches:
        timestamp_str = f"{date_str} {time_str}"
        timestamp = datetime.strptime(timestamp_str, "%m-%d-%y %H:%M")
        if last_timestamp is None or timestamp > last_timestamp:
            new_messages.append(f"{time_str}-{author}: {message}")
            last_timestamp = timestamp
    if not new_messages:
        print("🕵️ No new messages found since last timestamp.")
    else:
        print(f"✅ Extracted {len(new_messages)} new messages.")
    return new_messages

async def scan_and_post():
    channel = bot.get_channel(CHANNEL_ID)
    if not channel:
        print("❌ Discord channel not found.")
        return
    try:
        filename = await find_chat_log_file()
        if filename:
            async with aioftp.Client.context(FTP_HOST, FTP_USER, FTP_PASS) as ftp:
                stream = await ftp.download_stream(f"{FTP_PATH}{filename}")
                content = await stream.read()
                text = content.decode("utf-8")
                messages = extract_new_messages(text)
                if messages:
                    print(f"📤 Posting {len(messages)} new messages to Discord...")
                    for msg in messages:
                        await channel.send(msg)
                else:
                    print("📭 No messages to post.")
        else:
            print("🚫 Skipping scan — no chat log file found.")
    except Exception as e:
        print(f"🔥 Error during scan: {e}")

@bot.command(name="scan")
async def manual_scan(ctx):
    await ctx.send("🔄 Manual scan triggered...")
    await scan_and_post()

@bot.event
async def on_ready():
    print(f"🤖 Logged in as {bot.user}")
    bot.loop.create_task(auto_scan())

async def auto_scan():
    while not bot.is_closed():
        await scan_and_post()
        await asyncio.sleep(SCAN_INTERVAL)

bot.run(TOKEN)
