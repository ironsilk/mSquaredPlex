## Functions:
There are two **main services** in this repo:

I. MAINSTACK

II.MOVIELIB

They are not codependent, MAINSTACK, which contains all essential services will run just fine without
MOVIELIB. Both of them maintain their own **mysql DB** instance.

### MAINSTACK

Contains the following services:

- **Telegram service** - A telegram bot which can be queried for any IMDB title, link or ID and allows
the user to download these movies if found on filelist.
  This service also implements a routine which retrieves from it's own database (which
  is updated by the followin myimdb service) any movies from the user's watchlist and allows the
  user to download these movies if they are available on filelist.
  
    This service employs a simple one-time authentication routine which will
automatically give the user acces to PLEX and to the following newsletter service.
  
- **MyIMDB service** - Watches the user's IMDB profile and keeps track of his rated movies and
watchlist. Any new movie in the Watchlist gets notifications via the Telegram service while the rated movies are used
  to filter out which new filelist movies to send via the newsletter. Each user will receive a personalised
  newsletter depending on the movies which he has seen. This also syncs with the user's PLEX activity so any 
  watched movie in plex will be recorded here also.
  
- **Newsletter service** - Gets the last 100 new filelist torrents, filters them as described in MyIMDB service and
sends them to each user via email. 
  
- **TorrAPI** - An API which receives download requests from the Telegram service or from the Newsletter service and
communicates with the Transmission docker in order to download these movies. This service also employs a routine
  which syncs torrent statuses with Transmission. This feature is used afterwards when a user tries to download a movie
  which is already downloaded.
  

### MOVIELIB

Contains the following services:

- **IMDB refresher service** - Will download the dumps from IMDB and replicate the database locally. Slow and painful
service, main reason why there are two mysql db instances. Should be ran maybe once a month.
  
- **OMDB/TMDB services** - Will look in the main IMDB mirrored databases and try to get info from OMDB/TMDB for all 
movies there.
  
The goal for this second stack is to get a local movie database which could finally be used to make recommendations 
based on the user's ratings or watch history. It also provides a faster response when searching for movies with 
telegram. When the service is not running or not even configured the MAINSTACK will get all data directly from the 
internet so no functions will be affected.

## Deployment:

1. You'll first need an .env file in the root folder. An example has been provided as **env_example**. Careful for 
   all `=` signs not to have spaces between key and value: `HOST=localhost` is ok while this is not: `HOST = localhost`.
2. Git clone repo on server
3. Run `sudo docker-compose -f docker_compose_MAINSTACK.yml up -d --build`. Flags: -d means `detached`, `--build` will 
   rebuild images from scratch.
   

## COMMANDS

1. Start all services:

`sudo docker-compose -f docker-compose_MAINSTACK.yml up -d --build --remove-orphans`

2. Stop all services:

`sudo docker-compose -f docker-compose_MAINSTACK.yml down`

3. Recreate one service

`sudo docker-compose -f docker-compose_MAINSTACK.yml up --build --force-recreate --no-deps -d imdb_sync_service`


## Known bugs:

- There might be some errors in logs when starting up for the first time, until you login into telegram yourself.
All containers are set to restart `on-failiure` so no worries.
  
- Mysql might be slow: this might help: https://phpforus.com/how-to-make-mysql-run-fast-with-ext4-on-ubuntu/
 So slow that you might need to startup the services twice on first DB initialisation.
  Might be also slow because of fking up of docker volumes so to remove unused volumes: `sudo docker volume prune`.
  The final solution for this shit is always `sudo docker system prune -a` - Attention, it removes everything (volumes,
  networks, containers) not in use by any active docker container at that time. Run it before running again
  `sudo docker-compose -f docker-compose_MAINSTACK.yml up -d --buil`
  

## TODO

- Torrents download status for each user
- notification when movie was downloaded
- Download a CSV with my database - ratings and views
- Upload Netflix view history :X and integrate it.
- Joke engine - send random jokes to random users.
- reccomend a movie
- Show my watchlist
- see if we need to manually add movies to plex
- ask user who asked for download and didnt watch the movie before deletion
  and maybe confirm in with the admin.
- add functionality to say you've watched the movie with someone else so they also get notification
to rate the movie (meh, maybe)
- fix autoscan, not working right now
  


