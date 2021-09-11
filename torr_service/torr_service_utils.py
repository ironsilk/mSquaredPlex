import datetime
import os
from itertools import groupby
from urllib.parse import unquote

import falcon

from utils import timing, setup_logger, send_torrent, compose_link, update_many, make_client, \
    check_one_against_torrents_by_torr_id, check_one_against_torrents_by_torr_name, send_message_to_bot, \
    get_tgram_user_by_email, get_torrents, Torrent

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

    def __init__(self, cypher, logger):
        self.cy = cypher
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
            'torr_name': torr_response.name,
            'imdb_id': pkg['imdb_id'],
            'resolution': pkg['resolution'],
            'status': 'requested download',
            'requested_by': pkg['requested_by']
        }],
            Torrent, Torrent.torr_id)

        # Give response
        resp.media = 'Torrent successfully queued for download.'
        self.logger.info(f"Torrent with id {pkg['id']} and torr_name {torr_response.name} successfully queued for "
                         f"download.")
        return


class TORR_FINISHED:

    def __init__(self, logger):
        self.logger = logger

    @classmethod
    def get_classname(cls):
        return cls.__name__

    def on_get(self, req, resp):
        """Handles GET requests"""
        pkg = req.query_string
        if not pkg:
            return gtfo(resp)
        torr_id, torr_name, torr_labels = pkg.split('&&&')
        torr_name = torr_name.replace('^', ' ')
        # Get users who requested this torrent
        torr = check_one_against_torrents_by_torr_name(torr_name)
        users = torr['requested_by'].split(',')
        message = f"Your requested torrent,\n" \
                  f"{torr_name}\n" \
                  f"has been downloaded. 🏁"
        for user in users:
            resp = send_message_to_bot(get_tgram_user_by_email(user)['telegram_chat_id'], message)
            if not resp:
                self.logger.erro(f"Failed to send message: {torr_name}, {user}")
        return


class TORR_REFRESHER:
    def __init__(self, logger):
        self.logger = logger
        self.torr_client = make_client()

    def get_torrents(self):
        # Get DB torrents
        db_torrents = get_torrents()
        # Match them with client torrents
        client_torrents = self.torr_client.get_torrents()
        client_torrents = {x.name: x for x in client_torrents}
        for torr in db_torrents:
            if torr['torr_name'] in client_torrents.keys():
                torr['torr_obj'] = client_torrents[torr['torr_name']]
            else:
                torr['id'] = None
        return db_torrents

    def update_statuses(self):
        self.logger.info("Updating torrent statuses...")
        # Get torrents
        torrents = self.get_torrents()
        # Remove any duplicatd torrents by IMDB ID, keep only higher resolution
        self.logger.info("Checking for duplicate lower res movies...")
        torrents = self.remove_low_res(torrents)
        for torr in torrents:
            torr_response = torr.pop('torr_obj', None)
            if torr_response:
                if torr_response.status == 'seeding':
                    # Decide whether to remove it or keep it
                    if self.check_seeding_status(torr_response):
                        if torr['status'] == 'requested download':
                            torr['status'] = 'seeding'
                            update_many([torr], Torrent, Torrent.torr_id)
                    else:
                        # remove torrent and data
                        self.remove_torrent_and_files(torr['torr_id'])
                        # change status
                        torr['status'] = 'removed'
                        update_many([torr], Torrent, Torrent.torr_id)
                elif torr_response.status == 'downloading' and torr['status'] == 'requested download':
                    torr['status'] = 'downloading'
                    update_many([torr], Torrent, Torrent.torr_id)
            else:
                self.logger.warning("Torrent no longer in torrent client, removing from DB as well.")
                torr['status'] = 'removed'
                del torr['id']
                update_many([torr], Torrent, Torrent.torr_id)

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
        update_many(to_remove, Torrent, Torrent.torr_id)
        if to_remove:
            self.logger.info(f"Removed {len(to_remove)} lower res movies")
        else:
            self.logger.info("None found.")
        return torrents

    def check_seeding_status(self, torr):
        # TODO maybe send delete notification to users?
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
    logger = setup_logger('TorrRefresher')
    refresher = TORR_REFRESHER(logger=logger)
    refresher.update_statuses()
    logger.info("Routine done, closing connections.")
    return


if __name__ == '__main__':
    x = TORR_REFRESHER(setup_logger('cacat'))
    x.update_statuses()