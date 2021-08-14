#************************************* GLOBAL **************************************
# Directorul in care se stocheaza filmele
folder_path = '/disks/2TB/Movies-New/'

# Lista adrese mail destinatari
email_list_debug = 'gsmatei@gmail.com'

# Extensiile fisierelor video
movie_ext = ['.mkv', '.mp4', '.avi', '.ts']

# Extensiile fisierelor de sters
oth_ext  = ['.nfo', '.txt', '.md5']

# Google Drive Cred file
google_cred = '/home/matei/Documents/Python/MoviePediaV2/config/client_secret.json'



#************************************* filelist.py **************************************
# my IMDB Profile ID
imdb_profile = 30152272

# fl feed url - HD RO
filelist_rss_url = 'https://filelist.io/rss.php?feed=dl&cat=19&passkey='
# filelist_rss_url = 'https://filelist.io/rss.php?feed=dl&cat=6&passkey='

# Google Sheet Name
gsheet_name = 'FileList vs IMDB V3'

# results link
gsheet_url = 'http://bit.ly/2Hj6DHZ'

# dupa cate feed-uri existente opreste rularea (minim 1, maxim 100)
feed_limit = 100

# DB cu filme downloadate
db_path = '/home/matei/Documents/Python/MoviePediaV2/db/newMovies.xml'

# xml pt genereare email
xml_trnt_path = '/home/matei/Documents/Python/MoviePediaV2/db/new_trnt.xml'

# views path
template_path 		= '/home/matei/Documents/Python/MoviePediaV2/views/email_filelist.html'
movie_template_path = '/home/matei/Documents/Python/MoviePediaV2/views/_movie.html'
trnt_template_path 	= '/home/matei/Documents/Python/MoviePediaV2/views/_torrent.html'


#************************************* just4seed.py **************************************
#URL Filelist de verificat
filelist_url = 'https://filelist.io/browse.php?cat=19'

# Primele x torrente din lista de verificat
firstX  = 3

# Threshold medie ref trimitere mail
threshold = 10

# Adrese mail destinatari
email_list_j4s = ['gsmatei@gmail.com']



#************************************* movieFolder.py **************************************
# Durata seed-ului in ore
seed_hours = 120



#************************************* newMovies.py **************************************
# Dupa cate zile un film intra pe lista de stergere
days_old = 60

# Adrese mail destinatari
email_list_nm = ['gsmatei@gmail.com', 'mihai.vlad6@gmail.com']

# Quick Tips
quick_tip = ['Daca vrei sa iti apara automat subtitrarea in limba romana, intra <a href="https://app.plex.tv/desktop#!/account/audio-subtitle" target="_blank">aici</a> si seteaza "romana" la "PREFERRED SUBTITLE LANGUAGE".', 'Daca subtitrarea in limba romana nu se afiseaza corect din cauza diacriticelor, alege (daca exista) subtitrarea in Esperanto care este subtitrarea in limba romana fara diacritice.']

# views path
new_template_path 		= '/home/matei/Documents/Python/MoviePediaV2/views/email_new_movies.html'
new_movie_template_path = '/home/matei/Documents/Python/MoviePediaV2/views/_new_movie.html'