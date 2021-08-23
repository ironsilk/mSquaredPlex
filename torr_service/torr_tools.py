import PTN
from transmission_rpc import Client
import json
from settings import TORR_HOST, TORR_PORT, TORR_USER, TORR_PASS, TORR_API_HOST, TORR_API_PORT, TORR_API_PATH, \
    TORR_SEED_FOLDER, TORR_DOWNLOAD_FOLDER

transmission_client = Client(host=TORR_HOST, port=TORR_PORT, username=TORR_USER, password=TORR_PASS)


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