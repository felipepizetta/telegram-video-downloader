import asyncio
import sys
import threading
from PyQt6.QtWidgets import QApplication
from gui.main_window import MainWindow
from pathlib import Path
import logging

logs_dir = Path('logs')
logs_dir.mkdir(exist_ok=True)

# Configure logging
logging.basicConfig(
    filename='logs/debug.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

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

    # Create and show main window
    window = MainWindow(loop)
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