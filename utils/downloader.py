from telethon import TelegramClient
from telethon.errors import PeerIdInvalidError, ChannelInvalidError, UsernameInvalidError, RPCError
from telethon.tl.types import MessageMediaDocument, DocumentAttributeVideo, MessageMediaPhoto, PhotoSize
from pathlib import Path
import asyncio
import os

class DownloadError(Exception):
    """Exceção personalizada para erros relacionados ao download."""
    pass

class VideoDownloader:
    """Classe responsável por baixar vídeos e fotos de grupos do Telegram em pastas separadas, ignorando arquivos já baixados."""
    
    DEFAULT_SESSION_NAME = 'session_name'
    DEFAULT_LIMIT_MESSAGES = 1000
    MAX_CONCURRENT_DOWNLOADS = 5  # Limite de downloads simultâneos

    def __init__(self, download_folder, api_id, api_hash):
        """Inicializa o downloader com pasta de download e credenciais."""
        self.download_folder = Path(download_folder)
        self.video_folder = self.download_folder / "videos"
        self.photo_folder = self.download_folder / "photos"
        self.video_folder.mkdir(exist_ok=True)
        self.photo_folder.mkdir(exist_ok=True)
        self.api_id = api_id
        self.api_hash = api_hash
        # Desativa completamente o logging do Telethon
        import logging
        logging.getLogger('telethon').handlers = []  # Remove todos os handlers
        logging.getLogger('telethon').propagate = False  # Impede propagação
        logging.getLogger('telethon').setLevel(logging.CRITICAL)
        try:
            self.client = TelegramClient(self.DEFAULT_SESSION_NAME, api_id, api_hash)
        except Exception as e:
            raise DownloadError(f"Failed to initialize Telegram client: {str(e)}")
        self.progress_callback = None
        self.video_count_callback = None
        self.is_running = True
        self.semaphore = asyncio.Semaphore(self.MAX_CONCURRENT_DOWNLOADS)  # Controle de concorrência

    def stop(self):
        """Para o processo de download."""
        self.is_running = False

    async def _connect_client(self):
        """Estabelece conexão com o cliente Telegram."""
        if not self.client.is_connected():
            await self.client.connect()
        if not await self.client.is_user_authorized():
            raise DownloadError("Session is not authorized. Please re-authenticate.")

    async def _count_videos(self, group, min_size_bytes, processed_videos):
        """Conta o número de vídeos em um grupo que atendem aos critérios."""
        group_id = f"@{group}" if group and not group.startswith(('@', '-')) else group
        try:
            entity = await self.client.get_entity(group_id)
            video_count = 0
            async for message in self.client.iter_messages(entity, limit=self.DEFAULT_LIMIT_MESSAGES):
                if not self.is_running:
                    break
                if message.media and isinstance(message.media, MessageMediaDocument):
                    for attr in getattr(message.media.document, 'attributes', []):
                        if (isinstance(attr, DocumentAttributeVideo) and 
                            message.file.size >= min_size_bytes and 
                            message.id not in processed_videos):
                            video_count += 1
                            break
            return video_count
        except Exception as e:
            return 0

    async def _count_photos(self, group, min_size_bytes, processed_videos):
        """Conta o número de fotos em um grupo que atendem aos critérios."""
        group_id = f"@{group}" if group and not group.startswith(('@', '-')) else group
        try:
            entity = await self.client.get_entity(group_id)
            photo_count = 0
            async for message in self.client.iter_messages(entity, limit=self.DEFAULT_LIMIT_MESSAGES):
                if not self.is_running:
                    break
                if message.media and isinstance(message.media, MessageMediaPhoto) and message.id not in processed_videos:
                    if message.photo and message.photo.sizes:
                        largest_size = max((s for s in message.photo.sizes if isinstance(s, PhotoSize)), key=lambda x: x.w * x.h, default=None)
                        if largest_size and (largest_size.size or len(largest_size.bytes)) >= min_size_bytes:
                            photo_count += 1
            return photo_count
        except Exception as e:
            return 0

    async def _download_videos_and_photos(self, group, min_size_bytes, max_total_size_bytes, total_downloaded, processed_videos):
        """Baixa vídeos e fotos de um grupo específico com limite de concorrência em pastas separadas, ignorando arquivos já baixados."""
        group_id = f"@{group}" if group and not group.startswith(('@', '-')) else group
        download_tasks = []
        try:
            entity = await self.client.get_entity(group_id)
            async for message in self.client.iter_messages(entity):
                if not self.is_running or total_downloaded >= max_total_size_bytes:
                    break
                if message.media:
                    filename = None
                    output_path = None
                    if isinstance(message.media, MessageMediaDocument):
                        for attr in getattr(message.media.document, 'attributes', []):
                            if isinstance(attr, DocumentAttributeVideo):
                                filename = f"{message.id}_{message.media.document.id}.mp4"
                                output_path = self.video_folder / filename
                                if output_path.exists():
                                    local_size = output_path.stat().st_size
                                    if local_size == message.file.size:
                                        processed_videos[message.id] = True
                                        continue
                                    else:
                                        pass
                                if message.id not in processed_videos:
                                    task = self._download_file_with_semaphore(message, filename, min_size_bytes, max_total_size_bytes, total_downloaded, is_photo=False)
                                    download_tasks.append(task)
                                    total_downloaded += message.file.size
                                break
                    elif isinstance(message.media, MessageMediaPhoto):
                        filename = f"{message.id}_photo.jpg"
                        output_path = self.photo_folder / filename
                        if output_path.exists():
                            local_size = output_path.stat().st_size
                            if message.photo.sizes:
                                largest_size = max((s for s in message.photo.sizes if isinstance(s, PhotoSize)), key=lambda x: x.w * x.h, default=None)
                                expected_size = largest_size.size if largest_size and largest_size.size else len(largest_size.bytes) if largest_size else 0
                                if local_size == expected_size:
                                    processed_videos[message.id] = True
                                    continue
                                else:
                                    pass
                        if message.id not in processed_videos and message.photo and message.photo.sizes:
                            largest_size = max((s for s in message.photo.sizes if isinstance(s, PhotoSize)), key=lambda x: x.w * x.h, default=None)
                            if largest_size and (largest_size.size or len(largest_size.bytes)) >= min_size_bytes:
                                task = self._download_file_with_semaphore(message, filename, min_size_bytes, max_total_size_bytes, total_downloaded, is_photo=True)
                                download_tasks.append(task)
                                total_downloaded += largest_size.size if largest_size and largest_size.size else len(largest_size.bytes) if largest_size else 0
                    if filename and output_path and output_path.exists():
                        processed_videos[message.id] = True
            if download_tasks:  # Só executa gather se houver tarefas
                results = await asyncio.gather(*download_tasks, return_exceptions=True)
                for result, task in zip(results, download_tasks):
                    if isinstance(result, Exception):
                        pass
                    else:
                        total_downloaded, _ = result
            return total_downloaded, True
        except (PeerIdInvalidError, ChannelInvalidError, UsernameInvalidError, RPCError) as e:
            pass
        except Exception as e:
            pass
        return total_downloaded, True

    async def _download_file_with_semaphore(self, message, filename, min_size_bytes, max_total_size_bytes, total_downloaded, is_photo):
        """Baixa um único arquivo (vídeo ou foto) com controle de concorrência em pastas separadas."""
        async with self.semaphore:  # Limita o número de downloads simultâneos
            if not self.is_running:
                raise DownloadError("Download stopped by user")
            if total_downloaded >= max_total_size_bytes:
                raise DownloadError("Max total size reached. Stopping download.")
            output_path = (self.video_folder / filename) if not is_photo else (self.photo_folder / filename)
            try:
                await self.client.download_media(
                    message,
                    output_path,
                    progress_callback=lambda current, total: self.progress_callback(message.id, filename, (current / total) * 100) if self.progress_callback else None
                )
                size = message.file.size if not is_photo else (max((s for s in message.photo.sizes if isinstance(s, PhotoSize)), key=lambda x: x.w * x.h, default=None).size if message.photo.sizes else 0)
                return total_downloaded + (size if size else 0), True
            except Exception as e:
                return total_downloaded, False

    async def run(self, groups, min_size, max_total_size, processed_videos=None):
        """Executa o processo de download de vídeos e fotos de grupos especificados de forma paralela."""
        if processed_videos is None:
            processed_videos = {}
        try:
            min_size_bytes = parse_size(min_size)
            max_total_size_bytes = parse_size(max_total_size)
        except ValueError as e:
            raise

        total_downloaded = 0
        total_videos = 0
        total_photos = 0

        try:
            await self._connect_client()

            # Contagem total de vídeos e fotos
            for group in groups:
                if not self.is_running:
                    break
                total_videos += await self._count_videos(group, min_size_bytes, processed_videos)
                total_photos += await self._count_photos(group, min_size_bytes, processed_videos)
            total_items = total_videos + total_photos
            if self.video_count_callback:
                self.video_count_callback(total_items)

            # Download paralelo de vídeos e fotos entre grupos
            download_tasks = [self._download_videos_and_photos(group, min_size_bytes, max_total_size_bytes, total_downloaded, processed_videos) for group in groups]
            if download_tasks:
                results = await asyncio.gather(*download_tasks, return_exceptions=True)
                for result, group in zip(results, groups):
                    if isinstance(result, Exception):
                        pass
                    else:
                        total_downloaded = result[0]  # Atualiza total_downloaded com o resultado
            else:
                pass

        except DownloadError as e:
            raise
        except Exception as e:
            raise
        finally:
            if self.client.is_connected():
                await self.client.disconnect()
                self.is_running = False  # Garante que o programa pare

        return  # Explicitamente encerra a execução