import asyncio
import sys
import threading
from PyQt6.QtWidgets import QApplication
from gui.main_window import MainWindow
from pathlib import Path
import configparser

# Constantes
CONFIG_FILE = Path('config/config.ini')

# Leitura de credenciais
def load_credentials():
    """Carrega as credenciais API do arquivo de configuração."""
    config = configparser.ConfigParser()
    api_id = None
    api_hash = None
    try:
        if CONFIG_FILE.exists():
            config.read(CONFIG_FILE)
            api_id = config.get('Telegram', 'API_ID', fallback=None)
            api_hash = config.get('Telegram', 'API_HASH', fallback=None)
            if api_id and api_hash:
                try:
                    api_id = int(api_id)
                except ValueError:
                    api_id = None
                    api_hash = None
            else:
                pass  # Sem aviso, apenas ignora
        else:
            pass  # Sem aviso, apenas ignora
    except Exception:
        pass  # Ignora erros de leitura
    return api_id, api_hash

# Gerenciamento do loop assíncrono
def run_async_loop(loop):
    """Executa o loop assíncrono em uma thread separada."""
    asyncio.set_event_loop(loop)
    try:
        loop.run_forever()
    except Exception:
        pass  # Ignora erros no loop

def shutdown_async_loop(loop, async_thread):
    """Encerra o loop assíncrono de forma segura."""
    try:
        loop.call_soon_threadsafe(loop.stop)
        async_thread.join(timeout=5.0)
        if async_thread.is_alive():
            pass  # Sem aviso
        if not loop.is_closed():
            loop.run_until_complete(loop.shutdown_asyncgens())
            loop.close()
    except Exception:
        pass  # Ignora erros durante o encerramento

def main():
    """Ponto de entrada principal do aplicativo."""
    # Configuração inicial (sem logging)
    api_id, api_hash = load_credentials()

    # Inicialização do loop assíncrono
    loop = asyncio.new_event_loop()
    async_thread = threading.Thread(target=run_async_loop, args=(loop,), daemon=True)
    async_thread.start()

    # Inicialização da aplicação Qt
    app = QApplication(sys.argv)
    try:
        window = MainWindow(loop, api_id=api_id, api_hash=api_hash)
        window.show()
        exit_code = app.exec()
    except Exception:
        exit_code = 1
    finally:
        shutdown_async_loop(loop, async_thread)

    sys.exit(exit_code)

if __name__ == "__main__":
    main()