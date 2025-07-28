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
        self.log_callback = gui_callback  # For log messages
        self.progress_callback = None  # For progress updates

    def log(self, message):
        logging.info(message)
        if self.log_callback:
            self.log_callback(message)

    async def download_file(self, message, filename, min_size_bytes, max_total_size_bytes, total_downloaded):
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

        try:
            # Ensure fresh connection
            if self.client.is_connected():
                await self.client.disconnect()
            self.log("Connecting to Telegram...")
            await self.client.connect()
            if not await self.client.is_user_authorized():
                self.log("Session is not authorized. Please re-authenticate.")
                raise ValueError("Session is not authorized. Please re-authenticate.")

            for group in groups:
                if not continue_download:
                    break
                try:
                    # Normalize group identifier
                    group_id = f"@{group}" if group and not group.startswith(('@', '-')) else group
                    self.log(f"Attempting to access group: {group_id}")

                    # Revalidate group access and message iteration
                    try:
                        entity = await self.client.get_entity(group_id)
                        self.log(f"Entity resolved for {group_id}: {entity.__class__.__name__} (ID: {entity.id})")
                        # Check for video messages
                        video_found = False
                        async for message in self.client.iter_messages(entity, limit=10):
                            if message.media:
                                if isinstance(message.media, MessageMediaDocument):
                                    for attr in getattr(message.media.document, 'attributes', []):
                                        if isinstance(attr, DocumentAttributeVideo):
                                            video_found = True
                                            self.log(f"Video found in message {message.id} in {group_id}")
                                            break
                                # Handle potential video in other media types
                                elif isinstance(message.media, MessageMediaPhoto):
                                    self.log(f"Photo found in message {message.id} in {group_id}, skipping")
                                else:
                                    self.log(f"Unknown media type in message {message.id} in {group_id}: {type(message.media)}")
                            if video_found:
                                break
                        if not video_found:
                            self.log(f"No videos found in group {group_id} within the first 10 messages. Ensure videos exist and are accessible.")
                            continue
                        self.log(f"Group {group_id} is accessible and contains videos.")
                    except Exception as e:
                        self.log(f"Validation failed for group {group_id}: {str(e)}. Ensure the group exists and your account has permission to view messages.")
                        continue

                    # Proceed with downloading videos
                    async for message in self.client.iter_messages(entity):
                        if message.media and isinstance(message.media, MessageMediaDocument):
                            for attr in getattr(message.media.document, 'attributes', []):
                                if isinstance(attr, DocumentAttributeVideo):
                                    filename = f"{message.id}_{message.media.document.id}.mp4"
                                    total_downloaded, continue_download = await self.download_file(
                                        message, filename, min_size_bytes, max_total_size_bytes, total_downloaded
                                    )
                                    break
                except PeerIdInvalidError:
                    self.log(f"Error accessing group {group}: Invalid group ID or you are not a member. Check if the group exists and your account has access.")
                except ChannelInvalidError:
                    self.log(f"Error accessing group {group}: Group or channel does not exist or is inaccessible. Verify the group name or ID.")
                except UsernameInvalidError:
                    self.log(f"Error accessing group {group}: Invalid username format. Use @username or a numeric chat ID.")
                except RPCError as e:
                    self.log(f"API error accessing group {group}: {str(e)}. If session-related, try deleting session_name.session and re-authenticating.")
                except Exception as e:
                    if "TLObject was expected" in str(e):
                        self.log(f"Error accessing group {group}: {str(e)}. This likely indicates a private group, restricted permissions, or a session issue. Try using the numeric chat ID (e.g., -100123456789), re-authenticating, or checking group permissions.")
                    else:
                        self.log(f"Unexpected error accessing group {group}: {str(e)}. Ensure the group exists, is accessible, and your account has permission to view messages.")
                    # Pause to avoid rate limits
                    await asyncio.sleep(1)
        except Exception as e:
            self.log(f"Download error: {str(e)}")
            raise
        finally:
            if self.client.is_connected():
                self.log("Disconnecting from Telegram...")
                await self.client.disconnect()