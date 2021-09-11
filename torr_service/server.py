import atexit
import os
from wsgiref.simple_server import make_server

import falcon
from apscheduler.schedulers.background import BackgroundScheduler

from utils import setup_logger, check_database
from torr_service_utils import TORRAPI, TORR_FINISHED, refresher_routine

TZ = os.getenv('TZ')
TORR_API_PORT = int(os.getenv('TORR_API_PORT'))
TORR_API_PATH = os.getenv('TORR_API_PATH')
TORR_FINISHED_PATH = os.getenv('TORR_FINISHED_PATH')
TORR_CLEAN_ROUTINE_INTERVAL = int(os.getenv('TORR_CLEAN_ROUTINE_INTERVAL'))

logger = setup_logger('TORR_API_SERVICE')

# Create scheduler for refresher routine
scheduler = BackgroundScheduler(timezone=TZ)
scheduler.add_job(func=refresher_routine, trigger="interval", seconds=60 * TORR_CLEAN_ROUTINE_INTERVAL)
scheduler.start()

# Shut down the scheduler when exiting the app
atexit.register(lambda: scheduler.shutdown())

api = falcon.App()
api.add_route('/' + TORR_API_PATH.split('/')[-1], TORRAPI(logger))
api.add_route('/' + TORR_FINISHED_PATH.split('/')[-1], TORR_FINISHED(logger))

if __name__ == '__main__':
    check_database()
    with make_server('', TORR_API_PORT, api) as server:
        logger.info("TORR API Service running on port {p}".format(p=TORR_API_PORT))
        # Serve until process is killed
        server.serve_forever()
