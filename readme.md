## Services:


- **Telegram service** - A telegram bot which can be queried for any IMDB title, link or ID and allows
the user to download these movies if found on filelist.
  This service also implements a routine which retrieves from its own database (which
  is updated by the following myimdb service) any movies from the user's watchlist and allows the
  user to download these movies if they are available on filelist.
  
    This service employs a simple one-time authentication routine which will
automatically give the user acces to PLEX and to the following newsletter service.
    

    TODO rewrite the bot, logic is a bit tangled.
    
    TODO make another authentication system, use the built-in telegram method.

  
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



  


