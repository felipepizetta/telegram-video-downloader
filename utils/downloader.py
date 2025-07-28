from telethon import TelegramClient
from telethon.errors import PeerIdInvalidError, ChannelInvalidError, UsernameInvalidError, RPCError
from telethon.tl.types import MessageMediaDocument, DocumentAttributeVideo, MessageMediaPhoto
from pathlib import Path
import logging
from utils.helpers import parse_size
import asyncio

class VideoDownloader:
    def __init__(self, download_folder, api_id, api_hash, gui_callback=None):
        self.download_folder = Path(download_folder)
        self.download_folder.mkdir(exist_ok=True)
        self.api_id = api_id
        self.api_hash = api_hash
        try:
            self.client = TelegramClient('session_name', api_id, api_hash)
        except Exception as e:
            logging.error(f"Failed to initialize Telegram client: {str(e)}")
            raise ValueError(f"Failed to initialize Telegram client: {str(e)}")
        self.log_callback = gui_callback
        self.progress_callback = None
        self.video_count_callback = None
        self.is_running = True  # Control flag for graceful shutdown

    def log(self, message):
        logging.info(message)
        if self.log_callback:
            self.log_callback(message)

    def stop(self):
        self.is_running = False
        self.log("Received stop signal")

    async def download_file(self, message, filename, min_size_bytes, max_total_size_bytes, total_downloaded):
        if not self.is_running:
            self.log("Download stopped by user")
            return total_downloaded, False
        if total_downloaded >= max_total_size_bytes:
            self.log("Max total size reached. Stopping download.")
            return total_downloaded, False

        if message.file and message.file.size >= min_size_bytes:
            output_path = self.download_folder / filename
            try:
                safe_filename = filename if filename else f"message_{message.id}.mp4"
                await self.client.download_media(
                    message,
                    output_path,
                    progress_callback=lambda current, total: self.progress_callback(message.id, safe_filename, (current / total) * 100) if self.progress_callback else None
                )
                self.log(f"Downloaded: {safe_filename}")
                return total_downloaded + message.file.size, True
            except Exception as e:
                self.log(f"Error downloading {safe_filename}: {str(e)}")
                return total_downloaded, True
        return total_downloaded, True

    async def run(self, groups, min_size, max_total_size):
        try:
            min_size_bytes = parse_size(min_size)
            max_total_size_bytes = parse_size(max_total_size)
        except ValueError as e:
            self.log(f"Invalid size format: {str(e)}")
            raise

        total_downloaded = 0
        continue_download = True
        total_videos = 0

        try:
            if not self.client.is_connected():
                self.log("Connecting to Telegram...")
                await self.client.connect()
            if not await self.client.is_user_authorized():
                self.log("Session is not authorized. Please re-authenticate.")
                raise ValueError("Session is not authorized. Please re-authenticate.")

            # Count total videos with a reasonable limit
            for group in groups:
                if not self.is_running:
                    break
                try:
                    group_id = f"@{group}" if group and not group.startswith(('@', '-')) else group
                    self.log(f"Counting videos in group: {group_id}")
                    entity = await self.client.get_entity(group_id)
                    video_count = 0
                    async for message in self.client.iter_messages(entity, limit=1000):  # Reduced limit for performance
                        if not self.is_running:
                            break
                        if message.media and isinstance(message.media, MessageMediaDocument):
                            for attr in getattr(message.media.document, 'attributes', []):
                                if isinstance(attr, DocumentAttributeVideo) and message.file.size >= min_size_bytes:
                                    video_count += 1
                                    break
                    total_videos += video_count
                    self.log(f"Found {video_count} videos in group {group_id} meeting size criteria.")
                except Exception as e:
                    self.log(f"Cannot count videos in group {group_id}: {str(e)}")
                    continue

            if self.video_count_callback:
                self.video_count_callback(total_videos)
            self.log(f"Total videos to download: {total_videos}")

            # Download videos
            for group in groups:
                if not continue_download or not self.is_running:
                    break
                try:
                    group_id = f"@{group}" if group and not group.startswith(('@', '-')) else group
                    self.log(f"Attempting to access group: {group_id}")
                    entity = await self.client.get_entity(group_id)
                    self.log(f"Group {group_id} is accessible.")
                    async for message in self.client.iter_messages(entity):
                        if not self.is_running:
                            break
                        if message.media and isinstance(message.media, MessageMediaDocument):
                            for attr in getattr(message.media.document, 'attributes', []):
                                if isinstance(attr, DocumentAttributeVideo):
                                    filename = f"{message.id}_{message.media.document.id}.mp4"
                                    total_downloaded, continue_download = await self.download_file(
                                        message, filename, min_size_bytes, max_total_size_bytes, total_downloaded
                                    )
                                    break
                except PeerIdInvalidError:
                    self.log(f"Error accessing group {group}: Invalid group ID or you are not a member.")
                except ChannelInvalidError:
                    self.log(f"Error accessing group {group}: Group or channel does not exist or is inaccessible.")
                except UsernameInvalidError:
                    self.log(f"Error accessing group {group}: Invalid username format.")
                except RPCError as e:
                    self.log(f"API error accessing group {group}: {str(e)}.")
                except Exception as e:
                    if "TLObject was expected" in str(e):
                        self.log(f"Error accessing group {group}: {str(e)}. Try using the numeric chat ID.")
                    else:
                        self.log(f"Unexpected error accessing group {group}: {str(e)}.")
                    await asyncio.sleep(1)
        except Exception as e:
            self.log(f"Download error: {str(e)}")
            raise
        finally:
            if self.client.is_connected():
                self.log("Disconnecting from Telegram...")
                await self.client.disconnect()