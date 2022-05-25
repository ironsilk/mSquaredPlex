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

    - **Upload viewing activity** -> User can upload a .csv file with his viewing activity. 
      - Table format should be `Title`, `Date` which is the default export file from Netflix. 
      - Only movies will be picked 
    up from the file. 
      - For any unrated movie the user will be or not (depending on his answer to the Y/N choice) prompted 
    to rate that specific title after the import. 
      - If he wishes to import already rated titles the user can 
    choose to add another column with ratings, `Ratings`. (scale 1-10). These will be automatically picked up. 
      - Any ratings and seen dates will be overwritten. 
      - IMDB ratings and PLEX seen dates do have prevalence and will
    not be overwritten.
      - User gets notified when the process is finished and how many of the entries were movies, how many
    were soap series and how many were already in the database.
    
    - **Download viewing activity** -> Downloads a .csv with all user activity (imdb ids, titles, seen dates,
      and ratings)
    
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



  
- **MyIMDB service** - Watches the user's IMDB profile and keeps track of his rated movies and
watchlist. For any new movie in the Watchlist the user gets notifications via the Telegram service 
while the rated movies are used to filter out which new filelist movies to send via the newsletter. 
Each user will receive a personalised newsletter depending on the movies which he has seen. 
This also syncs with the user's PLEX activity so any watched movie in plex will be taken into account.
  

- **Newsletter service** - Gets the last 100 new filelist torrents, filters them as described in MyIMDB service and
sends them to each user via email. 
  

- **TorrAPI** - An API which receives download requests from the Telegram service or from the Newsletter service and
communicates with the Transmission docker in order to download these movies. This service also employs a routine
which syncs torrent statuses from Transmission to the postgres database.


## TODO

- ask user who asked for download and didnt watch the movie before deletion and maybe confirm in with the admin.
- Show my watchlist.
- Telegram roles reflect PLEX roles


## Wishlist
- recommend a movie - later stages, complex.
- Favorite a director/actor whatever and receive notifications when a new movie of his/hers is available.


## Deployment:

1. You'll first need an .env file in the root folder. An example has been provided as **env_example**. Careful for 
   all `=` signs not to have spaces between key and value: `HOST=localhost` is ok while this is not: `HOST = localhost`.
2. Git clone repo on server
3. Run `sudo docker-compose -f docker_compose_MAINSTACK.yml up -d --build`. Flags: -d means `detached`, `--build` will 
   rebuild images from scratch.
4. Haven't yet found a better way... These changes will persist during the next docker restarts but we need
   to make them manually right now. Need to stop the `transmission container`, go where you've defined
 `TRANSMISSION_FILES_LOCATION` environment variable and change the following settings in `settings.json`:
   - "script-torrent-done-enabled" -> true
   - "script-torrent-done-filename" -> "/torr_finished_routine.sh"'
   - "incomplete-dir-enabled" -> false
    
     
   

## COMMANDS

1. Start all services:

`sudo docker-compose -f docker-compose_MAINSTACK.yml up -d --build --remove-orphans`

2. Stop all services:

`sudo docker-compose -f docker-compose_MAINSTACK.yml down`

3. Recreate one service

`sudo docker-compose up --build --force-recreate --no-deps -d filelist_service`


## Known bugs:

- There might be some errors in logs when starting up for the first time, until you login into telegram yourself.
All containers are set to restart `on-failiure` so no worries.




### In order to solve TRANSMISSION configuration problem:

This is not gonna be easy. https://github.com/linuxserver/docker-mods 

1. Create a public repo on dockerhub, mine is mikael6/just_fun:transmission_mod
2. `docker build -t mikael6/just_fun:transmission_mod` when you're in the folder `transmission_mod`
3. `docker push mikael6/just_fun:transmission_mod`
4. So right now you have a mod which is going to change the `defaults.json` used by transmission on
startup.
5. You need to create this container:

`docker create --name=test -e PUID=1000 -e PGID=1000 -e DOCKER_MODS=mikael6/just_fun:transmission_mod --restart unless-stopped linuxserver/transmission`
It will return a container ID
6. `docker start {ID}` that ID. You can open a CLI into the container and use `cat defaults/settings.json` and `cat config/settings.json` to see that
your configs have been saved.



  


