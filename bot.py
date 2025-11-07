import discord
from discord import app_commands
import aioftp
import asyncio
import os
import re
import logging
import sys
from datetime import datetime

# Configure logging to use stdout and suppress discord.py's stderr output
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)-8s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    stream=sys.stdout,
    force=True
)

# Suppress discord.py logging or redirect it properly
logging.getLogger('discord').setLevel(logging.WARNING)
logging.getLogger('discord.gateway').setLevel(logging.WARNING)
logging.getLogger('discord.client').setLevel(logging.WARNING)

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
intents.message_content = True
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

# Track last posted timestamp
last_timestamp = None

async def find_chat_log_file():
    """Find the chat log file on the FTP server."""
    print("🔍 Scanning FTP directory for chat log files...")
    try:
        ftp_client = aioftp.Client()
        await ftp_client.connect(FTP_HOST)
        await ftp_client.login(FTP_USER, FTP_PASS)
        
        await ftp_client.change_directory(FTP_PATH)
        files = []
        async for path, info in ftp_client.list():
            files.append((path, info))
        
        await ftp_client.quit()
        
        for path, info in files:
            filename = str(path)
            if "chat" in filename.lower() and filename.endswith(".txt"):
                print(f"📄 Found chat log file: {filename}")
                return filename
        
        print("⚠️ No matching chat log file found.")
        return None
        
    except Exception as e:
        print(f"🔥 Error finding chat log file: {e}")
        import traceback
        traceback.print_exc()
        return None

def extract_new_messages(text):
    """Extract new chat messages from log text."""
    global last_timestamp
    # Fixed pattern for actual log format: [07-11-25 23:30:43.953][info] Got message:...
    pattern = r"\[(\d{2}-\d{2}-\d{2}) (\d{2}:\d{2}):\d{2}\.\d{3}\]\[info\] Got message:ChatMessage\{chat=General, author='([^']+)', text='([^']+)'\}\."
    matches = re.findall(pattern, text)
    new_messages = []
    
    for (date_str, time_str, author, message) in matches:
        timestamp_str = f"{date_str} {time_str}"
        try:
            timestamp = datetime.strptime(timestamp_str, "%m-%d-%y %H:%M")
            if last_timestamp is None or timestamp > last_timestamp:
                # Format with bold username using Discord markdown
                new_messages.append(f"{time_str} - **{author}**: {message}")
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
        
        ftp_client = aioftp.Client()
        await ftp_client.connect(FTP_HOST)
        await ftp_client.login(FTP_USER, FTP_PASS)
        
        stream = await ftp_client.download_stream(f"{FTP_PATH}{filename}")
        content = await stream.read()
        text = content.decode("utf-8")
        
        await ftp_client.quit()
        
        messages = extract_new_messages(text)
        if messages:
            print(f"📤 Posting {len(messages)} messages to Discord...")
            # Combine all messages into one with newlines
            combined_message = "\n".join(messages)
            
            # Discord has a 2000 character limit, so split if needed
            if len(combined_message) <= 2000:
                await channel.send(combined_message)
            else:
                # Split into chunks if too long
                chunks = [combined_message[i:i+1900] for i in range(0, len(combined_message), 1900)]
                for chunk in chunks:
                    await channel.send(chunk)
                    await asyncio.sleep(0.5)
        else:
            print("📭 No new messages to post.")
                
    except Exception as e:
        print(f"🔥 Error during scan: {e}")
        import traceback
        traceback.print_exc()

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
    print(f"📣 /scan command triggered by {interaction.user}")
    await interaction.response.defer(ephemeral=False)
    await scan_and_post()
    await interaction.followup.send("✅ Manual scan completed!")

@client.event
async def on_ready():
    """Bot startup event."""
    print(f"🤖 Logged in as {client.user}")
    print(f"📡 Connected to {len(client.guilds)} guild(s)")
    
    try:
        synced = await tree.sync()
        print(f"✅ Synced {len(synced)} command(s)")
        print(f"Commands available: {[cmd.name for cmd in synced]}")
    except Exception as e:
        print(f"⚠️ Failed to sync commands: {e}")
        import traceback
        traceback.print_exc()
    
    client.loop.create_task(auto_scan())

if __name__ == "__main__":
    if not TOKEN:
        print("❌ DISCORD_TOKEN not found in environment variables!")
    else:
        print("🚀 Starting bot...")
        client.run(TOKEN)
