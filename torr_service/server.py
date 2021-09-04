import atexit
import os
from wsgiref.simple_server import make_server

import falcon
from apscheduler.schedulers.background import BackgroundScheduler

from utils import torr_cypher, setup_logger, make_client, check_db_plexbuddy
from torr_service_utils import TORRAPI, TORR_FINISHED, refresher_routine

TORR_API_PORT = int(os.getenv('TORR_API_PORT'))
TORR_API_PATH = os.getenv('TORR_API_PATH')
TORR_FINISHED_PATH = os.getenv('TORR_FINISHED_PATH')
TORR_CLEAN_ROUTINE_INTERVAL = int(os.getenv('TORR_CLEAN_ROUTINE_INTERVAL'))

logger = setup_logger('TORR_API_SERVICE')

# Create scheduler for refresher routine
scheduler = BackgroundScheduler()
scheduler.add_job(func=refresher_routine, trigger="interval", seconds=60 * TORR_CLEAN_ROUTINE_INTERVAL)
scheduler.start()

# Shut down the scheduler when exiting the app
atexit.register(lambda: scheduler.shutdown())

api = falcon.App()
api.add_route('/' + TORR_API_PATH.split('/')[-1], TORRAPI(torr_cypher, logger))
api.add_route('/' + TORR_FINISHED_PATH.split('/')[-1], TORR_FINISHED(logger))

if __name__ == '__main__':
    check_db_plexbuddy()
    with make_server('', TORR_API_PORT, api) as server:
        logger.info("TORR API Service running on port {p}".format(p=TORR_API_PORT))
        # Serve until process is killed
        server.serve_forever()
