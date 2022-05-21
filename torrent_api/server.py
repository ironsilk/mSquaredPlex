import atexit
import os
from wsgiref.simple_server import make_server

import falcon

from utils import setup_logger, check_database
from torr_service_utils import TORRAPI, TORR_FINISHED

TZ = os.getenv('TZ')
TORR_API_PORT = int(os.getenv('TORR_API_PORT'))
TORR_API_PATH = os.getenv('TORR_API_PATH')
TORR_FINISHED_PATH = os.getenv('TORR_FINISHED_PATH')
TORR_CLEAN_ROUTINE_INTERVAL = int(os.getenv('TORR_CLEAN_ROUTINE_INTERVAL'))


logger = setup_logger('TORR_API_SERVICE')

api = falcon.App()
api.add_route('/' + TORR_API_PATH.split('/')[-1], TORRAPI())
api.add_route('/' + TORR_FINISHED_PATH.split('/')[-1], TORR_FINISHED())

if __name__ == '__main__':
    check_database()
    with make_server('', TORR_API_PORT, api) as server:
        logger.info("TORR API Service running on port {p}".format(p=TORR_API_PORT))
        # Serve until process is killed
        server.serve_forever()
