import os
import logging
import asyncio
from pathlib import Path
from dotenv import load_dotenv
from telethon.sync import TelegramClient
from telethon.errors import RPCError, ChatAdminRequiredError
from utils.helpers import parse_size, parse_date, sanitize_filename

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(
    filename='logs/debug.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class VideoDownloader:
    def __init__(self, download_folder, gui_callback=None, progress_callback=None):
        """Initialize Telegram client, download folder, and GUI callbacks."""
        api_id, api_hash = self.validate_env_vars()
        self.client = TelegramClient(
            'session_name',
            api_id,
            api_hash
        )
        self.download_folder = Path(download_folder)
        self.download_folder.mkdir(exist_ok=True)
        self.max_retries = 3
        self.retry_delay = 5
        self.chunk_size = 100
        self.gui_callback = gui_callback
        self.progress_callback = progress_callback

    def validate_env_vars(self):
        """Validate required environment variables."""
        required_vars = ['API_ID', 'API_HASH']
        missing = [var for var in required_vars if not os.getenv(var)]
        if missing:
            raise ValueError(f"Missing environment variables: {', '.join(missing)}")
        
        try:
            api_id = int(os.getenv('API_ID'))
        except ValueError:
            raise ValueError("API_ID must be a valid integer")
        
        return api_id, os.getenv('API_HASH')

    async def get_eligible_videos(self, group_name, min_size):
        """Retrieve all videos from a group that meet date and size criteria."""
        videos = []
        since_date = parse_date(os.getenv('SINCE_DATE', ''))
        max_size_total = parse_size(os.getenv('MAX_TOTAL_SIZE', '10GB'))
        min_size = parse_size(min_size) if min_size else 0
        total_size = 0
        offset_id = 0
        total_messages_checked = 0

        while True:
            chunk_videos = []
            chunk_messages = []
            for attempt in range(self.max_retries):
                try:
                    async for message in self.client.iter_messages(group_name, limit=self.chunk_size, offset_id=offset_id):
                        chunk_messages.append(message)
                    break
                except (RPCError, OSError) as e:
                    msg = f"Attempt {attempt + 1} failed for {group_name}: {str(e)}"
                    logging.error(msg)
                    self.log_to_gui(msg)
                    if attempt + 1 < self.max_retries:
                        msg = f"Retrying in {self.retry_delay} seconds..."
                        logging.info(msg)
                        self.log_to_gui(msg)
                        await asyncio.sleep(self.retry_delay)
                    else:
                        msg = f"Failed to process {group_name} after {self.max_retries} attempts"
                        logging.error(msg)
                        self.log_to_gui(msg)
                        return videos
                except ChatAdminRequiredError:
                    msg = f"Permission denied for group {group_name}. Ensure the account has access."
                    logging.error(msg)
                    self.log_to_gui(msg)
                    return videos

            total_messages_checked += len(chunk_messages)
            msg = f"Checked {total_messages_checked} messages in {group_name}"
            logging.info(msg)
            self.log_to_gui(msg)

            for message in chunk_messages:
                if not message.video:
                    continue

                message_date = message.date.replace(tzinfo=None) if message.date.tzinfo else message.date
                if since_date and message_date < since_date:
                    continue

                video_size = getattr(message.video, 'size', None)
                if video_size is None:
                    msg = f"Skipping video in message {message.id} from {group_name}: No size attribute"
                    logging.warning(msg)
                    self.log_to_gui(msg)
                    continue

                if video_size < min_size:
                    msg = f"Skipping video in message {message.id} from {group_name}: Size {video_size} bytes is below minimum {min_size} bytes"
                    logging.info(msg)
                    self.log_to_gui(msg)
                    continue

                total_size += video_size
                if total_size > max_size_total:
                    msg = f"Total size limit ({max_size_total} bytes) reached for {group_name}"
                    logging.info(msg)
                    self.log_to_gui(msg)
                    return videos

                file_name = getattr(message.video, 'file_name', None)
                if file_name:
                    ext = Path(file_name).suffix or '.mp4'
                else:
                    mime_type = getattr(message.video, 'mime_type', 'video/mp4')
                    ext = '.mp4' if 'mp4' in mime_type.lower() else '.mkv' if 'matroska' in mime_type.lower() else '.webm' if 'webm' in mime_type.lower() else '.mp4'
                filename = sanitize_filename(f"{message_date.strftime('%Y-%m-%d')}_{message.id}{ext}")
                if (self.download_folder / filename).exists():
                    msg = f"Skipping video {message.id} from {group_name}: Already downloaded as {filename}"
                    logging.info(msg)
                    self.log_to_gui(msg)
                    continue

                chunk_videos.append(message)

            videos.extend(chunk_videos)
            if not chunk_messages:
                break
            offset_id = chunk_messages[-1].id

        msg = f"Found {len(videos)} eligible videos in {group_name}"
        logging.info(msg)
        self.log_to_gui(msg)
        return videos

    def log_to_gui(self, message):
        """Send log message to GUI if callback is provided."""
        if self.gui_callback:
            self.gui_callback(message)

    async def download_with_progress(self, message, filename):
        """Download a video with progress updates."""
        async def progress_callback(downloaded, total):
            if total and self.progress_callback:
                percentage = (downloaded / total) * 100
                self.progress_callback(message.id, filename, percentage)

        try:
            await message.download_media(self.download_folder / filename, progress_callback=progress_callback)
            return True
        except Exception as e:
            return str(e)

    async def run(self, groups, min_size):
        """Process groups and download eligible videos."""
        try:
            if not groups:
                raise ValueError("No groups provided")

            for attempt in range(self.max_retries):
                try:
                    if not self.client.is_connected():
                        await self.client.connect()
                    break
                except (OSError, RPCError) as e:
                    msg = f"Connection attempt {attempt + 1} failed: {str(e)}"
                    logging.error(msg)
                    self.log_to_gui(msg)
                    if attempt + 1 < self.max_retries:
                        msg = f"Retrying in {self.retry_delay} seconds..."
                        logging.info(msg)
                        self.log_to_gui(msg)
                        await asyncio.sleep(self.retry_delay)
                    else:
                        raise ConnectionError(f"Failed to connect after {self.max_retries} attempts: {str(e)}")

            for group in groups:
                msg = f"Processing group: {group}"
                logging.info(msg)
                self.log_to_gui(msg)
                videos = await self.get_eligible_videos(group, min_size)
                if not videos:
                    msg = f"No eligible videos found in {group}"
                    logging.info(msg)
                    self.log_to_gui(msg)
                    continue

                for msg in videos:
                    try:
                        file_name = getattr(msg.video, 'file_name', None)
                        if file_name:
                            ext = Path(file_name).suffix or '.mp4'
                        else:
                            mime_type = getattr(msg.video, 'mime_type', 'video/mp4')
                            ext = '.mp4' if 'mp4' in mime_type.lower() else '.mkv' if 'matroska' in mime_type.lower() else '.webm' if 'webm' in mime_type.lower() else '.mp4'
                        filename = sanitize_filename(f"{msg.date.strftime('%Y-%m-%d')}_{msg.id}{ext}")
                        result = await self.download_with_progress(msg, filename)
                        if result is True:
                            log_msg = f"Downloaded {filename} from {group}"
                            logging.info(log_msg)
                            self.log_to_gui(log_msg)
                        else:
                            log_msg = f"Failed to download video {msg.id} from {group}: {result}"
                            logging.error(log_msg)
                            self.log_to_gui(log_msg)
                        await asyncio.sleep(1)
                    except Exception as e:
                        log_msg = f"Failed to download video {msg.id} from {group}: {str(e)}"
                        logging.error(log_msg)
                        self.log_to_gui(log_msg)

        except Exception as e:
            log_msg = f"Fatal error: {str(e)}"
            logging.error(log_msg)
            self.log_to_gui(log_msg)
        finally:
            log_msg = "Download process completed"
            logging.info(log_msg)
            self.log_to_gui(log_msg)