import discord
import re
import os
import asyncio
import socket
from datetime import datetime
from aioftp import Client
from discord import app_commands

# Use Railway-injected environment variables
TOKEN = os.environ.get("DISCORD_TOKEN")
FTP_HOST = os.environ.get("FTP_HOST")
FTP_USER = os.environ.get("FTP_USER")
FTP_PASS = os.environ.get("FTP_PASS")

# Static config
FTP_PATH = "/server-data/Logs/"
SCAN_INTERVAL = 180
CHANNEL_ID = 1236179374579912724

intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)
last_timestamp = None

async def resolve_ipv4_address(host):
    infos = await asyncio.get_event_loop().getaddrinfo(
        host, 21, family=socket.AF_INET, type=socket.SOCK_STREAM
    )
    return infos[0][4][0]  # Return the IPv4 address

async def find_chat_log_file():
    print("🔍 Scanning FTP directory for chat log files...")
    ip = await resolve_ipv4_address(FTP_HOST)
    async with Client.context(ip, FTP_USER, FTP_PASS) as ftp:
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
    channel = client.get_channel(CHANNEL_ID)
    if not channel:
        print("❌ Discord channel not found.")
        return

    try:
        ip = await resolve_ipv4_address(FTP_HOST)
        filename = await find_chat_log_file()
        if filename:
            async with Client.context(ip, FTP_USER, FTP_PASS) as ftp:
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

@tree.command(name="scan", description="Manually trigger a scan for new chat messages")
async def manual_scan(interaction: discord.Interaction):
    await interaction.response.send_message("🔄 Manual scan triggered...")
    await scan_and_post()

@client.event
async def on_ready():
    await tree.sync()
    print(f"🤖 Logged in as {client.user}")
    client.loop.create_task(auto_scan())

async def auto_scan():
    while not client.is_closed():
        await scan_and_post()
        await asyncio.sleep(SCAN_INTERVAL)

client.run(TOKEN)
