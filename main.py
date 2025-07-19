import os
import sys
import locale
from datetime import datetime
from dotenv import load_dotenv
from telethon.sync import TelegramClient
from tqdm import tqdm
from utils.logger import setup_logger
from utils.helpers import parse_size, parse_date

# Configura encoding para Windows
if sys.platform == "win32":
    locale.setlocale(locale.LC_ALL, '')
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# Configuração inicial
load_dotenv()
logger = setup_logger()

class VideoDownloader:
    def __init__(self):
        self.client = TelegramClient(
            'session_name', 
            int(os.getenv('API_ID')), 
            os.getenv('API_HASH')
        )
        self.download_folder = "downloads"
        os.makedirs(self.download_folder, exist_ok=True)

    async def get_eligible_videos(self, group_name):
        videos = []
        since_date = parse_date(os.getenv('SINCE_DATE'))
        min_size = parse_size(os.getenv('MIN_VIDEO_SIZE', '0MB'))
        
        async for message in self.client.iter_messages(group_name):
            if not message.video:
                continue

            # Corrige comparação de timezone
            message_date = message.date.replace(tzinfo=None) if message.date.tzinfo else message.date
            
            if since_date and message_date < since_date:
                continue
                
            if message.video.size < min_size:
                continue

            videos.append(message)
            if len(videos) >= int(os.getenv('MAX_DOWNLOADS', 100)):
                break
        return videos

    async def run(self):
        try:
            with open('config/groups.txt', 'r', encoding='utf-8') as f:
                groups = [line.strip() for line in f if line.strip()]

            for group in groups:
                try:
                    logger.info(f"Processando grupo: {group}")
                    videos = await self.get_eligible_videos(group)
                    
                    for msg in tqdm(videos, desc=f"Baixando de {group}"):
                        filename = f"{msg.date.strftime('%Y-%m-%d')}_{msg.id}.mp4"
                        await msg.download_media(os.path.join(self.download_folder, filename))

                except Exception as e:
                    logger.error(f"Erro em {group}: {str(e)}")

        except Exception as e:
            logger.error(f"Erro fatal: {str(e)}")
        finally:
            logger.info("Processo concluído")

if __name__ == "__main__":
    downloader = VideoDownloader()
    with downloader.client:
        downloader.client.loop.run_until_complete(downloader.run())