import falcon
from urllib.parse import unquote
from settings import PASSKEY
from torr_service.torr_tools import send_torrent
from utils import update_many


def gtfo(resp):
    pkg = {
        'Instructions': (
            "Provide the key, or g t f o"
        ),
    }
    resp.media = pkg
    resp.status = falcon.HTTP_500
    return


def compose_link(id):
    return f'https://filelist.io/download.php?id={id}&passkey={PASSKEY}'


class TORRAPI:

    def __init__(self, cypher, torr_client,logger):
        self.cy = cypher
        self.torr = torr_client
        self.logger = logger

    @classmethod
    def get_classname(cls):
        return cls.__name__

    def on_get(self, req, resp):
        """Handles GET requests"""
        pkg = req.query_string
        if not pkg:
            return gtfo(resp)

        # Try to decrypt
        try:
            pkg = self.cy.decrypt(unquote(pkg))
        except Exception as e:
            self.logger.error(e)
            return gtfo(resp)

        # Send to torrent daemon
        # 'https://filelist.io/download.php?id=748320&passkey=f5684696415b6f98834f1872bd03a8c1',
        try:
            torr_response = send_torrent(compose_link(pkg['id']))
        except Exception as e:
            self.logger.error(e)
            resp.media = f"Torrent download error for torr with id {pkg['id']}, check logs"
            resp.status = falcon.HTTP_500
            return

        # Update in DB
        update_many([{
            'torr_id': pkg['id'],
            'torr_client_id': torr_response.id,
            'status': 'requested download',
        }],
            'my_torrents')

        # Give response
        resp.media = 'Torrent successfully queued for download.'
        self.logger.info(f"Torrent with id {pkg['id']} and torr_client_id {torr_response.id} successfully queued for "
                         f"download.")
        return
