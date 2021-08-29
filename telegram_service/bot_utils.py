import requests

from settings import NO_POSTER_PATH
from utils import connect_mysql, close_mysql


def make_movie_reply(pkg):
    caption = ''
    # Title
    title = _title_header(pkg['title'], pkg['originalTitle'], pkg['startYear'])
    if title:
        caption += title
    # Stars
    stars = rating_stars(pkg)
    if stars:
        caption += stars
    # Description
    if pkg['ovrw']:
        caption += pkg['ovrw'] + '\n'
    # Trailer
    trailer = make_trailer(pkg['trailer_link'])
    if trailer:
        caption += trailer
    # Image
    image = get_image(pkg['poster'])
    if not caption:
        caption = 'No info about this movie, strange.'
    return caption, image


def get_image(img):
    if img:
        r = requests.get(img)
        if r.status_code == 200:
            return r.content
    return open(NO_POSTER_PATH, 'rb')


def _title_header(title, original_title, year):
    if original_title:
        return f"{title}\n({original_title})\nYear: {year}\n"
    else:
        return f"{title}\nYear: ({year})\n"


def rating_stars(pkg):
    """Transforms int rating into stars with int"""
    stars = ''
    # IMDB
    if pkg['averageRating']:
        x = int(float(pkg['averageRating']) // 2)
        rating_stars = f"🎟️ IMDB: {'⭐ ' * x} {pkg['averageRating']}"
        if pkg['numVotes']:
            rating_stars += f" 🧑‍⚖️{pkg['numVotes']:,}\n"
        else:
            rating_stars += "\n"
        stars += rating_stars
    # rott_score
    if pkg['rott_score']:
        x = int(float(pkg['rott_score']) // 20)
        rating_stars = f"🍿 ROTTEN: {'⭐ ' * x} {pkg['rott_score']}\n"
        stars += rating_stars
    # meta_score
    if pkg['meta_score']:
        x = int(float(pkg['meta_score']) // 20)
        rating_stars = f"🚽 META: {'⭐ ' * x} {pkg['meta_score']}\n"
        stars += rating_stars
    # tmdb_score
    if pkg['tmdb_score']:
        x = int(float(pkg['tmdb_score']) // 2)
        rating_stars = f"🎬 TMDB: {'⭐ ' * x} {pkg['tmdb_score']}\n"
        stars += rating_stars
    return stars


def make_trailer(link):
    if link:
        return f"🎥: {link}"
    return None


def make_trailer_shorten_url(link):
    if link:
        try:
            # construct the request headers with authorization
            headers = {"Authorization": "Bearer ce9b5c5be30a86b343630452ed990a983a2ad623"}
            guid = 'Bl8sgmRT1By'
            # make the POST request to get shortened URL for `url`
            shorten_res = requests.post("https://api-ssl.bitly.com/v4/shorten",
                                        json={"group_guid": guid, "long_url": link},
                                        headers=headers)
            if shorten_res.status_code == 200:
                # if response is OK, get the shortened URL
                link = shorten_res.json().get("link")
            else:
                # Do, nothing, return the link as it is
                pass
        except Exception as e:
            print(e)
        return f"🎥: {link}"
    return None


def get_telegram_users():
    conn, cursor = connect_mysql()
    q = """SELECT * FROM users
    """
    cursor.execute(q)
    users = cursor.fetchall()
    return {
        x['telegram_chat_id']:
        {
            'email': x['email'],
            'imdb_id': x['imdb_id'],
            'telegram_name': x['telegram_name'],
            'scan_watchlist': x['scan_watchlist'],
            'email_newsletters': x['email_newsletters'],
        }
        for x in users}


if __name__ == '__main__':
    from pprint import pprint

    link = 'https://www.youtube.com/watch?v=Sl90LWbuyVM'
    # print(make_trailer(link))
    pprint(get_telegram_users())
