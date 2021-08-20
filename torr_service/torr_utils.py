import json
from transmission_rpc import Client
from settings import TORR_HOST, TORR_PORT, TORR_USER, TORR_PASS, TORR_DOWNLOAD_FOLDER

# maybe we'll keep it:
MAX_SIZE = 100000

try:
    transmission_client = Client(host=TORR_HOST, port=TORR_PORT, username=TORR_USER, password=TORR_PASS)
except:
    transmission_client = None


def choose_torrent(lst):
    lst = sorted([x for x in lst if x['category'] == 'Filme HD-RO' and x['size'] < MAX_SIZE],
                 key=lambda k: k['seeders'], reverse=True)
    if lst:
        return lst[0]
    else:
        return None


def send_torrent(item):
    transmission_client.add_torrent(item, download_dir=TORR_DOWNLOAD_FOLDER)


def get_remaining_torrents():
    torr = transmission_client.get_torrents()
    added_torrents = [x.name for x in torr]
    print(added_torrents)
    print("Already added: ", len(added_torrents))
    # running_torrents = [x for x in torr if x.status == 'downloading']
    with open('fl_movies.txt')as f:
        original_list = json.loads(f.read())
    original_list = [choose_torrent(x) for x in original_list]
    original_list = [x for x in original_list if x]
    # original_list_names = [x['name'] for x in original_list]
    print('Original torrents: ', len(original_list))
    remaining_torr = [x for x in original_list if x['name'] not in added_torrents]
    print('Remaining torrents: ', len(remaining_torr))
    with open('remaining.txt', 'w') as outfile:
        json.dump(remaining_torr, outfile)


if __name__ == '__main__':
    pass
