## mSquaredPlex

Python-built telegram bot used to interact with PLEX, Transmission and a private torrent tracker.



## Services:

- **Telegram service** - A telegram bot with the following functionalities:

    - **Download a movie** -> Present IMDB id, IMDB link or movie title.
        Bot will match movie title with an IMDB id or loop through viable options until 
    it finds a match and:
        - Asks for confirmation on the match.
        - Check in user movies database if the movie was seen before. (notifies if True)
        - Check if the movie (in any resolution) is already downloaded. (notifies if True)
        - Pulls available torrents for the movie
        - If user chooses one, bot sends a download request to the transmission client
        - If user doesn't choose any resolution bot will ask if movie should be added to 
      watchlist. In this case the user will be notified if any resolution other than these already
      presented becomes available.

    - **Watchlist notification** -> When a new torrent was added for any movie in the watchlist.
    If the user accepts, torrent is set to download, else the user will receive updates only on other
    resolutions for that particular movie. These **notifications can be disabled via the /change_watchlist
      command**.

    - **Download finished notification** -> User receives notification when download is finished.

    - **Check download progress** -> Returns a list of the status of the last 10 torrents downloaded
        by the user.

    - Removed features: Upload viewing activity and Download viewing activity (deprecated in aiogram v3 rewrite)
      
    - **Rate a title** -> User can rate titles via the 
      bot.
        - Rate a new title: Similar to download movie, user provides id, link or movie name, matches
    the movie and rates it.
        - Rate seen movies: Bot picks up any unrated movies from DB (after the .csv import for example)
    and the user can rate them one by one.
        - PLEX triggered title rate: When a PLEX user finishes watching a movie, he/she will receive a
    telegram message asking if he wants to rate that movie.
        
    - **Manage users and authentication** -> User management is done through 
      telegram.
      - Initial authentication is done thorough the `SUPERADMIN_PASSWORD` which is mentioned in the
  .env file. The first user starting the chat with the bot and providing that password will be registered
  as admin.
      - `email` is used to send an invitation and register the user to PLEX.
      - `imdb id` is used to sync user's ratings and watchlist (if public)
      - The admin has access to `/generate_pass` (with the optional `-admin` flag). This command
      generates a 24-hour available token. Give the token to the person you want to join and it will 
        serve as initial one time password for him. If the `-admin` flag is used he will be able to generate
        tokens as well. **Has no effect on PLEX roles**.
      - `update_user` command is available for all users allowing them to retake the login process
        thus changing their email and/or imdb_id and other preferences.


- **MyIMDB service** - Background routine with the following 
   functions:
    - Syncs IMDB ratings given by the user with our database.
    - Syncs IMDB watchlist with our database.
    - Syncs PLEX user activity / ratings with our database.
    - Syncs transmission client torrent status wih our database.
    - Sends notifications regarding seen PLEX movies via telegram.(after watching a movie on PLEX, the user
       receives a notification to rate the title)
    - Sends notifications regarding watchlist via telegram.(when a watchlist movie becomes available on 
       filelist, the user receives a notification asking if he wants to download the movie. If not, he 
       will continue to receive notifications for the movie **except** for the movie quality that he rejected.
    - Sends notification if a torrent is seeding for more than (grace_time, default 60 days). User
      can choose to delete it and the files, keep (for another grace_time period) or to keep
      it forever and not ask. If user chooses none, he will be pinged daily.
    - Defaults to 1 minute routine, can be changed via the .env variables.


- **Newsletter service** - Gets the last 100 new filelist torrents, filters out any seen movies (for each user),
    pulls data from IMDB, TMDB and OMDB and sends the newsletter. All torrents sent out are stored in a database
    such as when a new torrent for an already newsletter-sent movie appears it will figure in another category.
  

- **TorrAPI** - An API which receives download requests from the Telegram service or from the Newsletter service and
communicates with the Transmission docker in order to download these movies.


## Deployment:

Requirements:
- make sure you have `docker` and `docker-compose` installed.  

1. Assign a local static ip to your server.
2. (PLEX, NEWSLETTER) Get a static public domain name (free on RDS from account).
3. (NEWSLETTER) open port 9092.
4. (PLEX) open port 32400.
5. (PLEX) get PLEX token: https://digiex.net/threads/plex-guide-step-by-step-getting-plex-token.15402/
6. OMDB and TMDB API keys(are both free).
7. Clone repo on server
8. If you're not planning to use PLEX:
   - Delete plex service from docker-compose.yml
9. If you don't want the NEWSLETTER function at all:
   - Delete the newsletter service from docker-compose.yml
10. Create a .env file in the root folder. A template has been provided as **env_example**. Careful for 
   all `=` signs not to have spaces between key and value: `HOST=localhost` is ok while this is not: `HOST = localhost`.
   Fill in everything.
11. Run `sudo docker-compose up -d --build`. Flags: -d means `detached`, `--build` will 
   rebuild images from scratch.
12. Docker-compose also contains PgAdmin (to check out the database). It can be removed.
13. Recommend using Portrainer to manage docker containers.


   

## COMMANDS

1. Start all services (rebuild them):

`sudo docker-compose up -d --build --remove-orphans`

2. Stop all services:

`sudo docker-compose down`

3. Recreate one service

`sudo docker-compose up --build --force-recreate --no-deps -d filelist_service`
`sudo docker-compose up --build --force-recreate --no-deps -d postgres_db`





## Telegram service (aiogram v3) – Usage, Commands, and Environment

Overview:
- The Telegram service has been rewritten using aiogram v3 (async-first).
- Kept features: Download a movie, Check download progress, Rate a title.
- Immediate notifications when a torrent completes (seeding/100%).
- Removed features: Upload viewing activity (CSV) and Download viewing activity (CSV).

Run locally:
1. Ensure Python 3.10+ and a proper virtualenv.
2. Install dependencies:
   - pip install -r [telegram_service/requirements.txt](telegram_service/requirements.txt:1)
3. Set required env:
   - TELEGRAM_TOKEN (required)
   - NO_POSTER_PATH (e.g. path to a default poster image used by [python.get_image()](telegram_service/bot_utils.py:44))
   - Optional images used in registration UX: TELEGRAM_AUTH_TEST_PATH, TELEGRAM_AUTH_APPROVE, TELEGRAM_IMDB_RATINGS
   - Transmission/DB credentials as per utils (already covered in your .env)
4. Start the bot:
   - python [python](telegram_service/app.py:78)

Docker:
- The Telegram service image is built using [Dockerfile_telegram](Dockerfile_telegram:1) and runs [python](telegram_service/app.py:78) as the entrypoint.
- docker-compose service “telegram_service” uses that Dockerfile. Ensure TELEGRAM_TOKEN is provided via .env.

Main entrypoint and routers:
- App entrypoint: [python.main()](telegram_service/app.py:55)
- Routers registered in app:
  - Misc (/help, /reset): [python](telegram_service/routers/misc_router.py:12)
  - Auth (/register, preference toggles, admin token): [python](telegram_service/routers/auth_router.py:1)
  - Download flow (FSM + callbacks): [python](telegram_service/routers/download_router.py:1)
  - Progress rendering: [python](telegram_service/routers/progress_router.py:11)
  - Rating flows (single + bulk): [python](telegram_service/routers/rating_router.py:72)
- Background notifier (immediate completion alerts):
  - Scheduled in [python.main()](telegram_service/app.py:71)
  - Logic: [python.start_notifier()](telegram_service/services/notifier_service.py:18)

Telegram commands (aiogram v3):
- /start – Show the main menu [python.start_handler()](telegram_service/app.py:36)
- /help – Show help and preferences [python.help_command()](telegram_service/routers/misc_router.py:12)
- /reset – Reset conversation [python.reset_command()](telegram_service/routers/misc_router.py:28)
- /register – Begin registration (email + optional IMDB ID) [python.register_start()](telegram_service/routers/auth_router.py:28)
- /change_watchlist – Toggle watchlist monitoring [python.change_watchlist()](telegram_service/routers/auth_router.py:132)
- /change_newsletter – Toggle newsletter emails [python.change_newsletter()](telegram_service/routers/auth_router.py:140)
- /generate_pass – Generate a one-time token (admin only) [python.generate_password()](telegram_service/routers/auth_router.py:148)

Feature flows

1) Download a movie
- Entry: Main menu “📥 Download a movie” [python.prompt_movie_query()](telegram_service/routers/download_router.py:23)
- Input options:
  - IMDB id (ttNNNNNNN, e.g. tt0133093)
  - IMDB URL (https://www.imdb.com/title/tt0133093/)
  - Title text (“The Matrix”)
- Resolution and send to Transmission:
  - Movie info + poster displayed via [python.make_movie_reply()](telegram_service/bot_utils.py:19)
  - Inline torrent list, selection handled by [python.torrent_selection()](telegram_service/routers/download_router.py:113)
  - Transmission request and DB update via [python.perform_download()](telegram_service/services/download_service.py:75)

2) Check download progress
- Entry: Main menu “📈 Check download progress”
- Handler: [python.check_download_progress()](telegram_service/routers/progress_router.py:11)
- Data from [python.get_progress()](telegram_service/bot_get_progress.py:107) with TorrentName, Resolution, Status, Progress, ETA

3) Rate a title
- Entry: Main menu “🌡️ Rate a title”
- Single title:
  - Input IMDB id/link/title, present movie info and rating keyboard
  - Persist rating and show IMDB link: [python.rate_submit_single()](telegram_service/routers/rating_router.py:127)
- Bulk unrated:
  - Process user’s unrated queue: [python.rate_choose_mode()](telegram_service/routers/rating_router.py:83), [python._rate_next_in_bulk()](telegram_service/routers/rating_router.py:175)
  - Actions: 1–10 score, Skip this movie., Exit rating process.

Notifications on completion:
- Background task polls Transmission/DB every 60s: [python.start_notifier()](telegram_service/services/notifier_service.py:18)
- On completion, sends a “✅ Download completed!” message and marks the torrent as “user notified (telegram)”

Environment variables summary:
- Required:
  - TELEGRAM_TOKEN (token of the Telegram bot)
- Optional UX images:
  - TELEGRAM_AUTH_TEST_PATH – image used for auth prompt (legacy UX, optional)
  - TELEGRAM_AUTH_APPROVE – image used on approval (optional)
  - TELEGRAM_IMDB_RATINGS – image used to guide IMDB profile (optional)
  - NO_POSTER_PATH – fallback poster image path for [python.get_image()](telegram_service/bot_utils.py:44)
- Transmission/DB:
  - Managed by existing .env used across services; see docker-compose service envs and [python.utils](utils.py:1)

Removed/deprecated:
- Upload viewing activity (CSV) and Download viewing activity (CSV) are deprecated in the new aiogram v3 bot; references remain only in legacy [python](telegram_service/bot.py:1) and are not used by the new entrypoint [python](telegram_service/app.py:78)

Verification checklist:
- Local:
  - Export TELEGRAM_TOKEN, run python [python](telegram_service/app.py:78)
  - In Telegram, use /start, then try Download/Progress/Rating flows
- Docker:
  - Ensure TELEGRAM_TOKEN in .env
  - docker-compose up -d --build telegram_service
  - Confirm the bot responds and that completion notifications arrive when torrents finish
