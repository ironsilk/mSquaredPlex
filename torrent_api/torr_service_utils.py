import hashlib
import hmac
import os
import time
import uuid

import falcon

from utils import setup_logger, send_torrent, compose_link, update_many, Torrent, get_torrent_by_torr_id_user

TORR_KEEP_TIME = int(os.getenv('TORR_KEEP_TIME')) if os.getenv('TORR_KEEP_TIME') else 60
TORR_API_HMAC_SECRET = os.getenv('TORR_API_HMAC_SECRET')

logger = setup_logger('TorrUtils')


def gtfo(resp, message="Provide required parameters"):
    pkg = {
        'error': 'bad_request',
        'message': message,
    }
    resp.media = pkg
    resp.status = falcon.HTTP_400
    return


def forbidden(resp, message="forbidden"):
    resp.media = {'error': 'forbidden', 'message': message}
    resp.status = falcon.HTTP_403
    return


class TORRAPI:

    def __init__(self):
        self.logger = logger

    @classmethod
    def get_classname(cls):
        return cls.__name__

    def on_get(self, req, resp):
        """Handles GET requests"""
        rid = getattr(req.context, 'request_id', str(uuid.uuid4()))
        start = time.time()

        # Basic presence of query string
        if not req.query_string:
            return gtfo(resp, "Missing query string parameters")

        # Parse params safely
        try:
            params = req.params
        except Exception as e:
            self.logger.error(f"[{rid}] param parsing error: {e}")
            return gtfo(resp, "Invalid query parameters")

        # Validate required params
        torr_id = params.get('torr_id')
        requested_by = params.get('requested_by')
        if torr_id is None or requested_by is None:
            return gtfo(resp, "Required parameters: torr_id and requested_by")

        try:
            torr_id_int = int(torr_id)
            requested_by_int = int(requested_by)
        except Exception:
            return gtfo(resp, "Parameters torr_id and requested_by must be integers")

        # Verify HMAC signature + expiry (public endpoint protection). Signed by the
        # newsletter over the canonical string "torr_id:requested_by:exp".
        if TORR_API_HMAC_SECRET:
            exp = params.get('exp')
            sig = params.get('sig')
            if not exp or not sig:
                self.logger.warning(f"[{rid}] missing signature for torr_id={torr_id_int}")
                return forbidden(resp, "Missing signature")
            try:
                if int(exp) < int(time.time()):
                    self.logger.warning(f"[{rid}] expired link for torr_id={torr_id_int}")
                    return forbidden(resp, "Link expired")
            except Exception:
                return forbidden(resp, "Invalid expiry")
            expected = hmac.new(
                TORR_API_HMAC_SECRET.encode(),
                f"{torr_id}:{requested_by}:{exp}".encode(),
                hashlib.sha256,
            ).hexdigest()
            if not hmac.compare_digest(expected, sig):
                self.logger.warning(f"[{rid}] invalid signature for torr_id={torr_id_int}")
                return forbidden(resp, "Invalid signature")
        else:
            self.logger.warning(f"[{rid}] TORR_API_HMAC_SECRET unset; serving unauthenticated request")

        # Attempt torrent queueing
        try:
            torr_response = send_torrent(compose_link(torr_id_int))
        except Exception as e:
            self.logger.error(f"[{rid}] Torrent download error for torr_id={torr_id_int}: {e}")
            resp.media = f"Torrent download error for torr with id {torr_id_int}, check logs"
            resp.status = falcon.HTTP_500
            return

        # Update in torrents DB
        try:
            db_torrent = get_torrent_by_torr_id_user(torr_id_int, requested_by_int)
            if not db_torrent:
                raise ValueError("Torrent not found in DB for given torr_id and requested_by")
            db_torrent['status'] = 'requested download'
            db_torrent['torr_hash'] = getattr(torr_response, 'hashString', None)
            update_many([db_torrent], Torrent, Torrent.id)
        except Exception as e:
            self.logger.error(f"[{rid}] DB update error for torr_id={torr_id_int}: {e}")
            resp.media = f"Internal error updating database for torr_id {torr_id_int}"
            resp.status = falcon.HTTP_500
            return

        # Give response + structured logging
        latency_ms = int((time.time() - start) * 1000)
        resp.media = 'Torrent successfully queued for download.'
        self.logger.info(
            f"[{rid}] Torrent queued torr_id={torr_id_int} "
            f"torr_name={getattr(torr_response, 'name', None)} "
            f"hash={getattr(torr_response, 'hashString', None)} "
            f"latency={latency_ms}ms"
        )


if __name__ == '__main__':
    pass
