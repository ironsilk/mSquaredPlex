import io
import os

import dataframe_image as dfi
import pandas as pd
# import tabulate

from utils import make_client, setup_logger, get_torr_name, get_requested_torrents_for_tgram_user

header = ['Movie Name', 'Resolution', 'DW Status', 'DW Progress', 'ETA']
HCTI_API_USER_ID = os.getenv('HTML_API_ID')
HCTI_API_KEY = os.getenv('HTML_API_KEY')


def get_torrents_for_user(user, get_next=0, logger=setup_logger("botUtils")):
    # Get torrents from my db
    torrents = get_requested_torrents_for_tgram_user(user)
    if torrents:
        torrents = list(reversed([x for x in torrents if x['status'] not in ['removed', 'user notified (email)']]))
        # Check if there are any
        torrents = torrents[get_next:]
        # Get client torrents
        torr_client = make_client()
        client_torrents_raw = torr_client.get_torrents()
        client_torrents = {x.hashString: x for x in client_torrents_raw}
        client_torrents_names = {x.hashString: x.name for x in client_torrents_raw}

        for torrent in torrents:
            if torrent['status'] != 'seeding':
                torrent['progress'] = 'Unknown'
                torrent['date_started'] = 'Unknown'
                torrent['eta'] = 'Unknown'
                if torrent['torr_hash'] in client_torrents.keys():
                    torr_resp = client_torrents[torrent['torr_hash']]
                    try:
                        torrent['progress'] = str(100 - ((torr_resp.left_until_done /
                                                          torr_resp.total_size) * 100))[:5] + '% '
                        torrent['date_started'] = torr_resp.date_started
                        torrent['eta'] = str(torr_resp.eta.seconds // 60) + ' minutes'
                    except Exception as e:
                        logger.warning(
                            f"Error while obtaining ETA or other data for torrent {torrent['torr_hash']}: {e}")
            else:
                torrent['progress'] = '100%'
                torrent['date_started'] = None
                torrent['eta'] = 'Finished'
        torrents = [{
            "TorrentName": get_torr_name(client_torrents_names[x['torr_hash']])
            if x['torr_hash'] in client_torrents_names.keys() else None,
            "Resolution": x['resolution'],
            "Status": x['status'],
            "Progress": x['progress'],
            "ETA": x['eta'],
        } for x in torrents]
        return torrents


def df_as_image(df, path=False, selected_cols=None, remove_index=True):
    """
    Transforms a pandas DF into a PNG
    :param df:
    :param path: If not provided, will return io.Bytes
    :param selected_cols:
    :param remove_index:
    :return:
    """
    if remove_index:
        df.reset_index(drop=True, inplace=True)
    if selected_cols:
        df = df[selected_cols]

    df_styled = df.style.background_gradient()  # adding a gradient based on values in cell
    df_styled = df.style.hide_index()
    if not path:
        # Create an in-memory file
        f = io.BytesIO()
        dfi.export(df_styled, f, table_conversion='matplotlib')
        # Pointer is at the end of the file so reset it to 0.
        f.seek(0)
        return f
    else:
        return dfi.export(df_styled, path, table_conversion='matplotlib')


def df_as_pretty_text(df, selected_cols=None, remove_index=True):
    """
    Transforms a pandas DF into a nicely formated string.
    :param df:
    :param selected_cols:
    :param remove_index:
    :return:
    """
    if remove_index:
        df.reset_index(drop=True, inplace=True)
        cols = df.columns
    else:
        cols = ["Index"]
    if selected_cols:
        df = df[selected_cols]
        cols = selected_cols

    rows = df.values.tolist()
    # return tabulate.tabulate(rows, cols, tablefmt='fancy_grid', floatfmt=(".2f"))


def get_progress(user, get_next=0, logger=setup_logger("botUtils")):
    torrents = get_torrents_for_user(user, get_next, logger)
    if torrents:
        df = pd.DataFrame(torrents)
        return df_as_image(df)


if __name__ == '__main__':
    t = get_torrents_for_user(1700079840)
    dff = pd.DataFrame(t)
    print(t)
    x = df_as_image(dff, path='test.png')
    print(df_as_pretty_text(dff))
