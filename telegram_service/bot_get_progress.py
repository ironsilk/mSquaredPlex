import os

from utils import get_requested_torrents_for_tgram_user, make_client, setup_logger, get_torr_name
import tabulate


header = ['Movie Name', 'Resolution', 'DW Status', 'DW Progress', 'ETA']
HCTI_API_USER_ID = os.getenv('HTML_API_ID')
HCTI_API_KEY = os.getenv('HTML_API_KEY')

def get_torrents_for_user(user, get_next=0, logger=setup_logger("botUtils")):
    # Get torrents from my db
    torrents = get_requested_torrents_for_tgram_user(user)
    torrents = list(reversed([x for x in torrents if x['status'] != 'removed']))
    # Check if there are any
    torrents = torrents[get_next:]

    if torrents:
        # Get client torrents
        torr_client = make_client()
        client_torrents = torr_client.get_torrents()
        client_torrents = {x.name: x for x in client_torrents}

        for torrent in torrents:
            if torrent['status'] != 'seeding':
                torrent['progress'] = 'Unknown'
                torrent['date_started'] = 'Unknown'
                torrent['eta'] = 'Unknown'
                if torrent['torr_name'] in client_torrents.keys():
                    torr_resp = client_torrents[torrent['torr_name']]
                    try:
                        torrent['progress'] = 100 - ((torr_resp.left_until_done / torr_resp.total_size) * 100)
                        torrent['date_started'] = torr_resp.date_started
                        torrent['eta'] = str(torr_resp.eta.seconds // 60) + ' minutes'
                    except Exception as e:
                        logger.warning(f"Error while obtaining ETA or other data for torrent {torrent['torr_name']}: {e}")
            else:
                torrent['progress'] = 100
                torrent['date_started'] = None
                torrent['eta'] = 'Finished'
    # Return a pretty table
    rows = [[get_torr_name(x['torr_name']), x['resolution'], x['status'], x['progress'], x['eta']] for x in torrents]
    return tabulate.tabulate(rows, header, tablefmt='html', floatfmt=(".2f"))
    # return torrents









if __name__ == '__main__':
    from pprint import pprint
    torrents = get_torrents_for_user(1700079840)
    x = """
    <!DOCTYPE html>
<html>
<body>

<h1>My First Headifdfsdfsfdsfsng</h1>
<p>My first paragraph.</p>

</body>
</html>
    """
    # print(torrents)
    import requests
    import shutil
    r = requests.post(url=f"http://localhost:5431/html2image", params={'html': x}, stream=True)
    print(r.status_code)
    print(r.text)
    with open('img.png', 'wb') as out_file:
        shutil.copyfileobj(r.raw, out_file)
    '''
    import requests
    HCTI_API_ENDPOINT = "https://hcti.io/v1/image"

    data = { 'html': torrents,
             'css': ".box { color: white; background-color: #0f79b9; padding: 10px; font-family: Roboto }",
             'google_fonts': "Roboto" }

    image = requests.post(url = HCTI_API_ENDPOINT, data = data, auth=(HCTI_API_USER_ID, HCTI_API_KEY))
    print(image.json())
    print("Your image URL is: %s"%image.json()['url'])
    
    PANDAS TO THE RESCUE, AS ALWAYS
    https://stackoverflow.com/questions/35634238/how-to-save-a-pandas-dataframe-table-as-a-png
    
    
    
    '''