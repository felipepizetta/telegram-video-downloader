import asyncio
import sys
import threading
from PyQt6.QtWidgets import QApplication
from gui.main_window import MainWindow
from pathlib import Path
import logging
import configparser

logs_dir = Path('logs')
logs_dir.mkdir(exist_ok=True)

# Configure logging
logging.basicConfig(
    filename='logs/debug.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Read API credentials from config.ini
config = configparser.ConfigParser()
config_file = Path('config/config.ini')
api_id = None
api_hash = None
try:
    if config_file.exists():
        config.read(config_file)
        api_id = config.get('Telegram', 'API_ID', fallback=None)
        api_hash = config.get('Telegram', 'API_HASH', fallback=None)
        if api_id and api_hash:
            try:
                api_id = int(api_id)  # Ensure API_ID is an integer
            except ValueError:
                logging.error("Invalid API_ID in config.ini: must be an integer")
                api_id = None
                api_hash = None
        else:
            logging.warning("API_ID or API_HASH missing in config.ini")
    else:
        logging.warning("config.ini not found in config directory")
except Exception as e:
    logging.error(f"Error reading config.ini: {str(e)}")

def run_async_loop(loop):
    asyncio.set_event_loop(loop)
    try:
        loop.run_forever()
    except Exception as e:
        logging.error(f"Async loop error: {str(e)}")

def main():
    # Create and start async loop in a separate thread
    loop = asyncio.new_event_loop()
    async_thread = threading.Thread(target=run_async_loop, args=(loop,), daemon=True)
    async_thread.start()

    # Initialize Qt application
    app = QApplication(sys.argv)

    # Create and show main window with API credentials
    window = MainWindow(loop, api_id=api_id, api_hash=api_hash)
    window.show()

    # Run Qt event loop
    exit_code = app.exec()

    # Stop async loop
    try:
        loop.call_soon_threadsafe(loop.stop)
        # Wait for the loop to stop
        async_thread.join(timeout=5.0)
        if async_thread.is_alive():
            logging.warning("Async thread did not terminate in time")
        # Close the loop in the main thread
        if not loop.is_closed():
            loop.run_until_complete(loop.shutdown_asyncgens())
            loop.close()
    except Exception as e:
        logging.error(f"Error during loop shutdown: {str(e)}")

    sys.exit(exit_code)

if __name__ == "__main__":
    main()