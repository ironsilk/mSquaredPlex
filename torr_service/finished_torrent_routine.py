import os
import urllib.request

# api_host = os.getenv('TORR_API_HOST')
api_host = '192.168.1.15'
api_port = os.getenv('TORR_API_PORT')
api_endpoint = os.getenv('TORR_FINISHED_PATH')
api_url = "http://" + api_host + ":" + str(api_port) + api_endpoint + "?"

torr_name = os.getenv('TR_TORRENT_NAME') or ''
torr_id = os.getenv('TR_TORRENT_ID') or ''
torr_label = os.getenv('TR_TORRENT_LABELS') or ''

pkg = '&'.join([torr_id, torr_name, torr_label])
# Send request
contents = urllib.request.urlopen(api_url + pkg).read()
