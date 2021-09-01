import datetime
import os
from itertools import groupby
from urllib.parse import unquote

import falcon

from utils import timing, setup_logger, send_torrent, compose_link, update_many, \
    connect_mysql, close_mysql, make_client

TORR_KEEP_TIME = int(os.getenv('TORR_KEEP_TIME'))


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

    def __init__(self, cypher, torr_client, logger):
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

        # Update in torrents DB
        update_many([{
            'torr_id': pkg['id'],
            'torr_client_id': torr_response.id,
            'imdb_id': pkg['imdb_id'],
            'resolution': pkg['resolution'],
            'status': 'requested download',
            'requested_by': pkg['requested_by']
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
        self.torr_client = make_client()
        self.conn, self.cursor = connect_mysql()

    def close(self):
        close_mysql(self.conn, self.cursor)

    def get_torrents(self):
        q = "SELECT * FROM my_torrents WHERE status != 'removed'"
        self.cursor.execute(q)
        results = self.cursor.fetchall()
        results = [x for x in results if x['torr_client_id']]
        return results

    def update_statuses(self):
        self.logger.info("Updating torrent statuses...")
        # Get torrents
        torrents = self.get_torrents()
        # Remove any duplicatd torrents by IMDB ID, keep only higher resolution
        self.logger.info("Checking for duplicate lower res movies...")
        torrents = self.remove_low_res(torrents)
        for torr in torrents:
            torr_response = self.torr_client.get_torrent(torr['torr_client_id'])
            if torr_response.status == 'seeding':
                # Decide whether to remove it or keep it
                if self.check_seeding_status(torr_response):
                    if torr['status'] == 'requested download':
                        torr['status'] = 'seeding'
                        update_many([torr], 'my_torrents')
                else:
                    # remove torrent and data
                    self.remove_torrent_and_files(torr['torr_client_id'])
                    # change status
                    torr['status'] = 'removed'
                    update_many([torr], 'my_torrents')
            elif torr_response.status == 'downloading' and torr['status'] == 'requested download':
                torr['status'] = 'downloading'
                update_many([torr], 'my_torrents')

    def remove_low_res(self, torrents):
        to_remove = []
        # Sort
        torrents = sorted(torrents, key=lambda x: x['imdb_id'])
        for k, v in groupby(torrents, key=lambda x: x['imdb_id']):
            items = list(v)
            if len(items) > 1:
                resolutions = sorted(items, key=lambda x: x['resolution'])
                to_remove.extend([x for x in resolutions[:-1]])
        torrents = [x for x in torrents if x not in to_remove]
        # Remove those torrents / update status in DB
        for x in to_remove:
            self.remove_torrent_and_files(x['torr_id'])
            x['status'] = 'removed'
        update_many(to_remove, 'my_torrents')
        if to_remove:
            self.logger.info(f"Removed {len(to_remove)} lower res movies")
        else:
            self.logger.info("None found.")
        return torrents

    def check_seeding_status(self, torr):
        # TODO PLEX check here if it was seen in plex and mb change logic, mb go after seed ratio
        # need third state here, 2 - for torrent and data removal.
        if (datetime.datetime.now() - torr.date_done.replace(tzinfo=None)).days < TORR_KEEP_TIME:
            return True
        else:
            return False

    def remove_torrent(self, id):
        self.torr_client.remove_torrent(id)
        print('here')
        pass

    def remove_torrent_and_files(self, id):
        self.torr_client.remove_torrent(id, delete_data=True)


@timing
def refresher_routine():
    logger = setup_logger('TorrRefresher')
    refresher = TORR_REFRESHER(logger=logger)
    refresher.update_statuses()
    logger.info("Routine done, closing connections.")
    refresher.close()
    return