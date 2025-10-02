import os
from wsgiref.simple_server import make_server

from utils import setup_logger, check_database
from app import create_app

logger = setup_logger('TORR_API_SERVICE')

if __name__ == '__main__':
    # Note: This is a development-only server. For production use Gunicorn:
    #   gunicorn -c gunicorn.conf.py --bind 0.0.0.0:${TORR_API_PORT:-9092} wsgi:app
    check_database()
    port = int(os.getenv('TORR_API_PORT', '9092'))
    app = create_app()
    logger.info(f"TORR API (dev server) running on 0.0.0.0:{port}")
    with make_server('', port, app) as server:
        server.serve_forever()
