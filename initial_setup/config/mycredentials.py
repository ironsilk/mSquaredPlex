import sys
sys.path.append('/home/matei/Documents/Python/MoviePediaV2/models/')
from credlib import Credential, Passkey

sys_filelist		= Credential('filelist.ro', '...........', '...........')
sys_email			= Credential('smtp.mail.yahoo.com:587', '...........', '...........')
sys_rss_filelist	= Passkey('...........')
# https://www.themoviedb.org/u/mateig
sys_tmdb			= Passkey('...........')
# https://www.omdbapi.com/apikey.aspx
sys_omdb			= Passkey('...........') 