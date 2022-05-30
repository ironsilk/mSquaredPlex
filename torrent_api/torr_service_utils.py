import os

import falcon

from utils import setup_logger, send_torrent, compose_link, update_many, check_one_against_torrents_by_torr_hash, \
    send_message_to_bot, \
    Torrent, get_torrent_by_torr_id_user

TORR_KEEP_TIME = int(os.getenv('TORR_KEEP_TIME'))

logger = setup_logger('TorrUtils')


def gtfo(resp):
    pkg = {
        'Instructions': (
            "Provide the key, or g t f o"
        ),
    }
    resp.media = pkg
    resp.status = falcon.HTTP_500
    return


class TORRAPI:

    def __init__(self):
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
            # Cypher alternative
            # pkg = torr_cypher.decrypt(unquote(pkg))
            # No cypher
            pkg = req.params
        except Exception as e:
            self.logger.error(e)
            return gtfo(resp)
        try:
            torr_response = send_torrent(compose_link(pkg['torr_id']))
        except Exception as e:
            self.logger.error(e)
            resp.media = f"Torrent download error for torr with id {pkg['torr_id']}, check logs"
            resp.status = falcon.HTTP_500
            return
        # Update in torrents DB
        db_torrent = get_torrent_by_torr_id_user(pkg['torr_id'], int(pkg['requested_by']))
        db_torrent['status'] = 'requested download'
        db_torrent['torr_hash'] = torr_response.hashString
        update_many([db_torrent], Torrent, Torrent.id)

        # Give response
        resp.media = 'Torrent successfully queued for download.'
        self.logger.info(f"Torrent with id {pkg['torr_id']} and torr_name {torr_response.name} successfully queued for "
                         f"download.")



if __name__ == '__main__':
    pass
