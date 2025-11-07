import discord
from discord import app_commands
import aioftp
import asyncio
import socket
import os
import re
from datetime import datetime

# Load environment variables from Railway
TOKEN = os.environ.get("DISCORD_TOKEN")
FTP_HOST = os.environ.get("FTP_HOST")
FTP_USER = os.environ.get("FTP_USER")
FTP_PASS = os.environ.get("FTP_PASS")

print(f"🔧 Environment loaded - FTP_HOST={FTP_HOST}, FTP_USER={FTP_USER}")

# Static configuration
FTP_PATH = "/server-data/Logs/"
SCAN_INTERVAL = 180  # seconds
CHANNEL_ID = 1236179374579912724

# Discord client setup
intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

# Track last posted timestamp
last_timestamp = None

async def resolve_ipv4_address(host):
    """Resolve hostname to IPv4 address."""
    try:
        infos = await asyncio.get_event_loop().getaddrinfo(
            host, 21, family=socket.AF_INET, type=socket.SOCK_STREAM
        )
        return infos[0][4][0]
    except Exception as e:
        print(f"⚠️ Failed to resolve {host}: {e}")
        return host

async def find_chat_log_file():
    """Find the chat log file on the FTP server."""
    print("🔍 Scanning FTP directory for chat log files...")
    try:
        resolved_host = await resolve_ipv4_address(FTP_HOST)
        async with aioftp.Client.context(resolved_host, FTP_USER, FTP_PASS) as ftp:
            await ftp.change_directory(FTP_PATH)
            files = await ftp.list()
            for file in files:
                if "chat" in file.name.lower() and file.name.endswith(".txt"):
                    print(f"📄 Found chat log file: {file.name}")
                    return file.name
            print("⚠️ No matching chat log file found.")
            return None
    except Exception as e:
        print(f"🔥 Error finding chat log file: {e}")
        return None

def extract_new_messages(text):
    """Extract new chat messages from log text."""
    global last_timestamp
    pattern = r"\[(\d{2}-\d{2}-\d{2} (\d{2}:\d{2}))\]\n\[info\]\n Got message:ChatMessage\{chat=General, author='([^']+)', text='([^']+)'\}"
    matches = re.findall(pattern, text)
    new_messages = []
    
    for (date_str, time_str, author, message) in matches:
        timestamp_str = f"{date_str} {time_str}"
        try:
            timestamp = datetime.strptime(timestamp_str, "%m-%d-%y %H:%M")
            if last_timestamp is None or timestamp > last_timestamp:
                new_messages.append(f"{time_str} - {author}: {message}")
                last_timestamp = timestamp
        except ValueError as e:
            print(f"⚠️ Failed to parse timestamp '{timestamp_str}': {e}")
    
    if not new_messages:
        print("🕵️ No new messages found since last scan.")
    else:
        print(f"✅ Extracted {len(new_messages)} new messages.")
    
    return new_messages

async def scan_and_post():
    """Scan FTP for new chat messages and post to Discord."""
    channel = client.get_channel(CHANNEL_ID)
    if not channel:
        print("❌ Discord channel not found.")
        return
    
    try:
        filename = await find_chat_log_file()
        if not filename:
            print("🚫 No chat log file to scan.")
            return
        
        resolved_host = await resolve_ipv4_address(FTP_HOST)
        async with aioftp.Client.context(resolved_host, FTP_USER, FTP_PASS) as ftp:
            stream = await ftp.download_stream(f"{FTP_PATH}{filename}")
            content = await stream.read()
            text = content.decode("utf-8")
            
            messages = extract_new_messages(text)
            if messages:
                print(f"📤 Posting {len(messages)} messages to Discord...")
                for msg in messages:
                    await channel.send(msg)
                    await asyncio.sleep(0.5)  # Small delay to avoid rate limits
            else:
                print("📭 No new messages to post.")
                
    except Exception as e:
        print(f"🔥 Error during scan: {e}")

async def auto_scan():
    """Automatically scan FTP on an interval."""
    await client.wait_until_ready()
    print(f"🤖 Auto-scan started. Scanning every {SCAN_INTERVAL} seconds.")
    
    while not client.is_closed():
        await scan_and_post()
        await asyncio.sleep(SCAN_INTERVAL)

@tree.command(name="scan", description="Manually trigger a chat log scan")
async def manual_scan(interaction: discord.Interaction):
    """Slash command to manually trigger a scan."""
    await interaction.response.defer()
    await scan_and_post()
    await interaction.followup.send("✅ Manual scan completed!")

@client.event
async def on_ready():
    """Bot startup event."""
    print(f"🤖 Logged in as {client.user}")
    print(f"📡 Connected to {len(client.guilds)} guild(s)")
    
    # Sync slash commands
    try:
        synced = await tree.sync()
        print(f"✅ Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"⚠️ Failed to sync commands: {e}")
    
    # Start auto-scanning
    client.loop.create_task(auto_scan())

# Run the bot
if __name__ == "__main__":
    if not TOKEN:
        print("❌ DISCORD_TOKEN not found in environment variables!")
    else:
        print("🚀 Starting bot...")
        client.run(TOKEN)
