import datetime
import json
from urllib.parse import unquote

import PTN
import falcon
from transmission_rpc import Client

from db_tools import connect_mysql, close_mysql
from settings import PASSKEY, TORR_KEEP_TIME, setup_logger
from settings import TORR_HOST, TORR_PORT, TORR_USER, TORR_PASS, TORR_API_HOST, TORR_API_PORT, TORR_API_PATH, \
    TORR_SEED_FOLDER, TORR_DOWNLOAD_FOLDER
from utils import timing
from utils import update_many


transmission_client = Client(host=TORR_HOST, port=TORR_PORT, username=TORR_USER, password=TORR_PASS)


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


class TORR_REFRESHER:
    def __init__(self, logger):
        self.logger = logger
        self.torr_client = transmission_client
        self.conn, self.cursor = connect_mysql()

    def close(self):
        close_mysql(self.conn, self.cursor)

    def get_torrents(self):
        q = "SELECT * FROM my_torrents WHERE status != 'closed'"
        self.cursor.execute(q)
        results = self.cursor.fetchall()
        return results

    def update_statuses(self):
        self.logger.info("Updating torrent statuses...")
        # Get torrents
        torrents = self.get_torrents()
        for torr in torrents:
            torr['torr_client_id'] = 57
            torr_response = self.torr_client.get_torrent(torr['torr_client_id'])
            if torr_response.status == 'seeding':
                # Decide whether to remove it or keep it
                if self.check_seeding_status(torr_response):
                    # keep it
                    pass
                else:
                    # remove it
                    self.remove_torrent(torr['torr_client_id'])
                    # change status
                    torr['status'] = 'closed'
                    update_many([torr], 'my_torrents')
            elif torr_response.status == 'downloading' and torr['status'] == 'requested download':
                torr['status'] = 'downloading'
                update_many([torr], 'my_torrents')

    def check_seeding_status(self, torr):
        # TODO PLEX check here if it was seen in plex and mb change logic, mb go after seed ratio
        if (datetime.datetime.now() - torr.date_done.replace(tzinfo=None)).days < TORR_KEEP_TIME:
            return True
        else:
            return False

    def remove_torrent(self, id):
        self.torr_client.remove_torrent(id)
        print('here')
        pass

    def remove_torrent_and_files(self, id):
        raise NotImplementedError
        self.torr_client.remove_torrent(id, delete_data=True)


@timing
def refresher_routine():
    logger = setup_logger('TorrRefresher')
    refresher = TORR_REFRESHER(logger=logger)
    refresher.update_statuses()
    logger.info("Routine done, closing connections.")
    refresher.close()
    return


def generate_torr_links(item, cypher):
    def compose_link(pkg):
        pkg = cypher.encrypt(json.dumps(pkg))
        return f"http://{TORR_API_HOST}:{TORR_API_PORT}{TORR_API_PATH}?{pkg}"

    seed = {
        'id': item['id'],
        'folder': TORR_SEED_FOLDER
    }
    download = {
        'id': item['id'],
        'folder': TORR_DOWNLOAD_FOLDER
    }
    return compose_link(seed), compose_link(download)


def send_torrent(item):
    return transmission_client.add_torrent(item, download_dir=TORR_DOWNLOAD_FOLDER)


def parse_torr_name(name):
    return PTN.parse(name)


def get_torr_quality(name):
    return int(PTN.parse(name)['resolution'][:-1])