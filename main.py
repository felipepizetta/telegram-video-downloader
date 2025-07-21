import os
import sys
import locale
import io
import re
import asyncio
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from telethon.sync import TelegramClient
from telethon.errors import RPCError, ChatAdminRequiredError
from tqdm import tqdm
from utils.helpers import parse_size, parse_date, sanitize_filename

# Configure encoding for Windows
if sys.platform == "win32":
    locale.setlocale(locale.LC_ALL, '')
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    except AttributeError:
        os.environ['PYTHONIOENCODING'] = 'utf-8'

# Load environment variables
load_dotenv()

class VideoDownloader:
    def __init__(self):
        """Initialize Telegram client and download folder."""
        api_id, api_hash = self.validate_env_vars()
        self.client = TelegramClient(
            'session_name',
            api_id,
            api_hash
        )
        self.download_folder = Path("downloads")
        self.download_folder.mkdir(exist_ok=True)
        self.max_retries = 3
        self.retry_delay = 5  # Seconds to wait between retries
        self.chunk_size = 100  # Process messages in chunks to manage API load

    def validate_env_vars(self):
        """Validate required environment variables and return their values."""
        required_vars = ['API_ID', 'API_HASH']
        missing = [var for var in required_vars if not os.getenv(var)]
        if missing:
            raise ValueError(f"Missing environment variables: {', '.join(missing)}")
        
        api_id = os.getenv('API_ID')
        api_hash = os.getenv('API_HASH')
        
        try:
            api_id = int(api_id)  # Convert to int and validate
        except ValueError:
            raise ValueError("API_ID must be a valid integer")
        
        return api_id, api_hash

    async def get_eligible_videos(self, group_name):
        """Retrieve all videos from a group that meet size and date criteria."""
        videos = []
        since_date = parse_date(os.getenv('SINCE_DATE', ''))
        min_size = parse_size(os.getenv('MIN_VIDEO_SIZE', '0MB'))
        max_size_total = parse_size(os.getenv('MAX_TOTAL_SIZE', '10GB'))
        total_size = 0
        offset_id = 0  # For pagination
        total_messages_checked = 0

        while True:
            chunk_videos = []
            chunk_messages = []
            for attempt in range(self.max_retries):
                try:
                    async for message in self.client.iter_messages(group_name, limit=self.chunk_size, offset_id=offset_id):
                        chunk_messages.append(message)
                    break  # Success, exit retry loop
                except (RPCError, OSError) as e:
                    print(f"Attempt {attempt + 1} failed for {group_name}: {str(e)}")
                    if attempt + 1 < self.max_retries:
                        print(f"Retrying in {self.retry_delay} seconds...")
                        await asyncio.sleep(self.retry_delay)
                    else:
                        print(f"Failed to process {group_name} after {self.max_retries} attempts")
                        return videos
                except ChatAdminRequiredError:
                    print(f"Permission denied for group {group_name}. Ensure the account has access.")
                    return videos

            total_messages_checked += len(chunk_messages)
            print(f"Checked {total_messages_checked} messages in {group_name}")

            for message in chunk_messages:
                if not message.video:
                    continue

                # Ensure naive datetime for comparison
                message_date = message.date.replace(tzinfo=None) if message.date.tzinfo else message.date

                if since_date and message_date < since_date:
                    continue

                # Check if video has a size attribute
                video_size = getattr(message.video, 'size', None)
                if video_size is None:
                    print(f"Skipping video in message {message.id} from {group_name}: No size attribute")
                    continue

                if video_size < min_size:
                    continue

                total_size += video_size
                if total_size > max_size_total:
                    print(f"Total size limit ({max_size_total} bytes) reached for {group_name}")
                    return videos  # Exit early if size limit reached

                # Check if video already downloaded
                file_name = getattr(message.video, 'file_name', None)
                if file_name:
                    ext = Path(file_name).suffix or '.mp4'
                else:
                    mime_type = getattr(message.video, 'mime_type', 'video/mp4')
                    ext = '.mp4' if 'mp4' in mime_type.lower() else '.mkv' if 'matroska' in mime_type.lower() else '.webm' if 'webm' in mime_type.lower() else '.mp4'
                filename = sanitize_filename(f"{message_date.strftime('%Y-%m-%d')}_{message.id}{ext}")
                if (self.download_folder / filename).exists():
                    print(f"Skipping video {message.id} from {group_name}: Already downloaded as {filename}")
                    continue

                chunk_videos.append(message)

            videos.extend(chunk_videos)
            if not chunk_messages:  # No more messages to fetch
                break
            offset_id = chunk_messages[-1].id  # Update offset for next chunk

        print(f"Found {len(videos)} eligible videos in {group_name}")
        return videos

    async def run(self):
        """Process groups and download eligible videos."""
        try:
            groups_file = Path('config/groups.txt')
            if not groups_file.exists():
                raise FileNotFoundError("config/groups.txt not found")

            with groups_file.open('r', encoding='utf-8') as f:
                groups = [line.strip() for line in f if line.strip()]
            if not groups:
                raise ValueError("No valid groups found in config/groups.txt")

            # Ensure client is connected
            for attempt in range(self.max_retries):
                try:
                    if not self.client.is_connected():
                        await self.client.connect()
                    break
                except (OSError, RPCError) as e:
                    print(f"Connection attempt {attempt + 1} failed: {str(e)}")
                    if attempt + 1 < self.max_retries:
                        print(f"Retrying connection in {self.retry_delay} seconds...")
                        await asyncio.sleep(self.retry_delay)
                    else:
                        raise ConnectionError(f"Failed to connect after {self.max_retries} attempts: {str(e)}")

            for group in groups:
                print(f"Processing group: {group}")
                videos = await self.get_eligible_videos(group)
                if not videos:
                    print(f"No eligible videos found in {group}")
                    continue

                for msg in tqdm(videos, desc=f"Downloading from {group} ({len(videos)} videos, {sum(getattr(v.video, 'size', 0)/1024**2 for v in videos):.2f} MB)"):
                    try:
                        # Determine file extension from file_name or mime_type
                        file_name = getattr(msg.video, 'file_name', None)
                        if file_name:
                            ext = Path(file_name).suffix or '.mp4'
                        else:
                            mime_type = getattr(msg.video, 'mime_type', 'video/mp4')
                            ext = '.mp4' if 'mp4' in mime_type.lower() else '.mkv' if 'matroska' in mime_type.lower() else '.webm' if 'webm' in mime_type.lower() else '.mp4'

                        filename = sanitize_filename(f"{msg.date.strftime('%Y-%m-%d')}_{msg.id}{ext}")
                        await msg.download_media(self.download_folder / filename)
                        print(f"Downloaded {filename} from {group}")
                        await asyncio.sleep(1)  # Delay to avoid API rate limits
                    except Exception as e:
                        print(f"Failed to download video {msg.id} from {group}: {str(e)}")

        except Exception as e:
            print(f"Fatal error: {str(e)}")
        finally:
            print("Download process completed")

if __name__ == "__main__":
    downloader = VideoDownloader()
    with downloader.client:
        downloader.client.loop.run_until_complete(downloader.run())