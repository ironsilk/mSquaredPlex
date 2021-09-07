import os

from utils import get_requested_torrents_for_tgram_user, make_client, setup_logger, get_torr_name
import tabulate
import PIL as pil


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
    # return tabulate.tabulate(rows, header, tablefmt='html', floatfmt=(".2f"))
    return torrents









if __name__ == '__main__':
    from pprint import pprint
    import pandas as pd
    torrents = get_torrents_for_user(1700079840)
    # https://stackoverflow.com/questions/35634238/how-to-save-a-pandas-dataframe-table-as-a-png

    pprint(torrents)
    df = pd.DataFrame(torrents)
    import dataframe_image as dfi
    import seaborn as sns


    def color_negative_red(value):
        """
        Colors elements in a dateframe
        green if positive and red if
        negative. Does not color NaN
        values.
        """

        if value < 0:
            color = 'red'
        elif value > 0:
            color = 'green'
        else:
            color = 'black'

        return 'color: %s' % color

    # Set colormap equal to seaborns light green color palette
    cm = sns.light_palette("green", as_cmap=True)
    # Set CSS properties for th elements in dataframe
    th_props = [
        ('font-size', '11px'),
        ('text-align', 'center'),
        ('font-weight', 'bold'),
        ('color', '#6d6d6d'),
        ('background-color', '#f7f7f9')
    ]

    # Set CSS properties for td elements in dataframe
    td_props = [
        ('font-size', '11px')
    ]

    # Set table styles
    styles = [
        dict(selector="th", props=th_props),
        dict(selector="td", props=td_props)
    ]

    (df.style
     .applymap(color_negative_red, subset=['total_amt_usd_diff', 'total_amt_usd_pct_diff'])
     .format({'total_amt_usd_pct_diff': "{:.2%}"})
     .set_table_styles(styles))

    (df.style
     .background_gradient(cmap=cm, subset=['total_amt_usd_diff', 'total_amt_usd_pct_diff'])
     .highlight_max(subset=['total_amt_usd_diff', 'total_amt_usd_pct_diff'])
     .set_caption('This is a custom caption.')
     .format({'total_amt_usd_pct_diff': "{:.2%}"})
     .set_table_styles(styles))
    dfi.export(df, "mytable.png", table_conversion='matplotlib')
    exit()


    import weasyprint as wsp


    def trim(source_filepath, target_filepath=None, background=None):
        if not target_filepath:
            target_filepath = source_filepath
        img = pil.Image.open(source_filepath)
        if background is None:
            background = img.getpixel((0, 0))
        border = pil.Image.new(img.mode, img.size, background)
        diff = pil.ImageChops.difference(img, border)
        bbox = diff.getbbox()
        img = img.crop(bbox) if bbox else img
        img.save(target_filepath)


    img_filepath = 'table1.png'
    css = wsp.CSS(string='''
    @page { size: 2048px 2048px; padding: 0px; margin: 0px; }
    table, td, tr, th { border: 1px solid black; }
    td, th { padding: 4px 8px; }
    ''')
    html = wsp.HTML(string=df.to_html())
    html.write_png(img_filepath, stylesheets=[css])
    trim(img_filepath)






























