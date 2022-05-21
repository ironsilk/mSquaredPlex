import datetime
import os
from itertools import groupby

import falcon

from utils import timing, setup_logger, send_torrent, compose_link, update_many, make_client, \
    check_one_against_torrents_by_torr_hash, send_message_to_bot, \
    get_tgram_user_by_email, get_torrents, Torrent, get_torrent_by_torr_id_user

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
        return


class TORR_FINISHED:

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
        torr_name, torr_hash = pkg.split('&&&')
        torr_name = torr_name.replace('^', ' ')

        # Get users who requested this torrent
        torr = check_one_against_torrents_by_torr_hash(torr_hash)
        users = [x['requested_by_id'] for x in torr]
        message = f"Your requested torrent,\n" \
                  f"{torr_name}\n" \
                  f"has been downloaded. 🏁"
        for user in users:
            resp = send_message_to_bot(user, message)
            if not resp:
                self.logger.erro(f"Failed to send message: {torr_name}, {user}")
        return


class TORR_REFRESHER:
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
def refresher_routine():
    refresher = TORR_REFRESHER()
    refresher.update_statuses()
    logger.info("Routine done, closing connections.")
    return


if __name__ == '__main__':
    x = TORR_REFRESHER(setup_logger('cacat'))
    #x.get_torrents()
    #x.update_statuses()
    refresher_routine()