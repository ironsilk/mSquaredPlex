import atexit
import os
from wsgiref.simple_server import make_server

import falcon

from utils import setup_logger, check_database
from torr_service_utils import TORRAPI

TZ = os.getenv('TZ')
TORR_API_PORT = int(os.getenv('TORR_API_PORT')) if os.getenv('TORR_API_PORT') else 9092
TORR_API_PATH = os.getenv('TORR_API_PATH')


logger = setup_logger('TORR_API_SERVICE')

api = falcon.App()
api.add_route('/' + TORR_API_PATH.split('/')[-1], TORRAPI())

if __name__ == '__main__':
    check_database()
    with make_server('', TORR_API_PORT, api) as server:
        logger.info("TORR API Service running on port {p}".format(p=TORR_API_PORT))
        # Serve until process is killed
        server.serve_forever()
