import datetime
import os
from itertools import groupby

from utils import timing, setup_logger, update_many, make_client, \
    get_torrents, Torrent

TORR_KEEP_TIME = int(os.getenv('TORR_KEEP_TIME'))

logger = setup_logger('TorrUtils')


class TorrentRefresher:
    def __init__(self):
        self.logger = logger
        self.torr_client = make_client()

    def get_torrents(self):
        # Get DB torrents
        db_torrents = get_torrents()
        # Match them with client torrents
        client_torrents = self.torr_client.get_torrents()

        client_torrents = {x.hashString: x for x in client_torrents}
        for torr in db_torrents:
            if torr['torr_hash'] in client_torrents.keys():
                torr['torr_obj'] = client_torrents[torr['torr_hash']]
            else:
                torr['torr_obj'] = None
        return db_torrents

    def update_statuses(self):
        self.logger.info("Updating torrent statuses...")
        # Get torrents
        torrents = self.get_torrents()
        # Remove any duplicatd torrents by IMDB ID, keep only higher resolution
        self.logger.info("Checking for duplicate lower res movies...")
        self.remove_low_res(torrents)
        # Refresh list
        torrents = self.get_torrents()
        for torr in torrents:
            torr_response = torr.pop('torr_obj', None)
            if torr_response:
                if torr_response.status == 'seeding':
                    # Decide whether to remove it or keep it
                    if self.check_seeding_status(torr_response):
                        torr['status'] = 'seeding'
                        update_many([torr], Torrent, Torrent.id)
                    else:
                        # remove torrent and data
                        self.remove_torrent_and_files(torr['torr_id'])
                        # change status
                        torr['status'] = 'removed'
                        update_many([torr], Torrent, Torrent.id)
                elif torr_response.status == 'downloading' and torr['status'] == 'requested download':
                    torr['status'] = 'downloading'
                    update_many([torr], Torrent, Torrent.id)
            else:
                self.logger.warning("Torrent no longer in torrent client, removing from DB as well.")
                torr['status'] = 'removed'
                update_many([torr], Torrent, Torrent.id)

    def remove_low_res(self, torrents):
        torrents = [x for x in torrents if x['torr_obj']]
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
            torr_response = x.pop('torr_obj', None)
            self.remove_torrent_and_files(torr_response.id)
            x['status'] = 'removed'

        update_many(to_remove, Torrent, Torrent.id)
        if to_remove:
            self.logger.info(f"Removed {len(to_remove)} lower res movies")
        else:
            self.logger.info("None found.")
        return torrents

    def check_seeding_status(self, torr):
        if (datetime.datetime.now() - torr.date_done.replace(tzinfo=None)).days < TORR_KEEP_TIME:
            return True
        else:
            return False

    def remove_torrent(self, id):
        self.torr_client.remove_torrent(id)

    def remove_torrent_and_files(self, id):
        self.torr_client.remove_torrent(id, delete_data=True)


@timing
def sync_torrent_statuses():
    refresher = TorrentRefresher()
    refresher.update_statuses()
    logger.info("Routine done, closing connections.")
    return


if __name__ == '__main__':
    x = TorrentRefresher(setup_logger('cacat'))
    sync_torrent_statuses()