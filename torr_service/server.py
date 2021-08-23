from wsgiref.simple_server import make_server
from torr_service import TORRAPI
from settings import TORR_API_PORT, TORR_API_PATH,setup_logger
from crypto_tools import torr_cypher
from torr_service.torr_tools import transmission_client

import falcon

# https://stackoverflow.com/questions/21214270/how-to-schedule-a-function-to-run-every-hour-on-flask

logger = setup_logger('TORR_API_SERVICE')

api = falcon.App()
api.add_route('/' + TORR_API_PATH.split('/')[-1], TORRAPI(torr_cypher, transmission_client,logger))

if __name__ == '__main__':
    with make_server('', TORR_API_PORT, api) as server:
        logger.info("TORR API Service running on port {p}".format(p=TORR_API_PORT))
        # Serve until process is killed
        server.serve_forever()
