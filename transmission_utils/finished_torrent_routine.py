import os
import urllib.request

api_host = os.getenv('TORR_API_HOST')
api_port = os.getenv('TORR_API_PORT')
api_endpoint = os.getenv('TORR_FINISHED_PATH')
api_url = "http://" + api_host + ":" + str(api_port) + api_endpoint + "?"

torr_name = os.getenv('TR_TORRENT_NAME') or ''
torr_hash = os.getenv('TR_TORRENT_HASH') or ''
torr_name = torr_name.replace(' ', '^')

pkg = '&&&'.join([torr_name, torr_hash])
# Send request
contents = urllib.request.urlopen(api_url + pkg).read()