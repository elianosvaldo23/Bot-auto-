from flask import Flask
from threading import Thread
import logging

# Configurar logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

app = Flask('')

@app.route('/')
def home():
    return "¡Bot-auto está activo!"

def run():
    try:
        app.run(host='0.0.0.0', port=8080)
    except Exception as e:
        logger.error(f"Error en el servidor web: {e}")

def start_server():
    try:
        server_thread = Thread(target=run)
        server_thread.daemon = True
        server_thread.start()
        logger.info("Servidor web iniciado correctamente")
    except Exception as e:
        logger.error(f"Error iniciando servidor web: {e}")
