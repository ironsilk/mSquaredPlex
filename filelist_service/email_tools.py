# -*- coding: utf-8 -*-
import datetime
import os
import xml.etree.ElementTree as ET
from xml.dom import minidom
from xml.etree.ElementTree import SubElement

from settings import xml_trnt_path, template_path, movie_template_path, trnt_template_path, EMAIL_USER, \
    EMAIL_PASS, EMAIL_HOSTNAME, EMAIL_TO, TORR_DOWNLOAD_URI, TORR_DOWNLOAD_FOLDER, TORR_SEED_FOLDER, setup_logger
from tmdb_omdb_tools import OMDB
from tmdb_omdb_tools import TMDB
from torr_tools import get_torr_quality

logger = setup_logger('EmailSender')

# seen_type:
'''
0 = new movie
1 = new torrent
2 = seen or dw movie
'''


class Mtls:

    def __init__(self):
        self.description = 'my tools'

    def n2d(self, x):
        if (x is None) or (x == 'N/A') or (x == 'NOT RATED'):
            newX = '-'
        else:
            newX = u'{0}'.format(x)

        return newX

    '''************************ generate_html_list ***********************************
    Genereaza item/tabel HTML pentru un film dat
    Input:	vColor - fundal film (gri pt film nou, rosu pentru filme de sters),
        vCount - crt index item/film in lista, plus alte detalii pt fiecare film in parte
    Output:	cod HTML pt un item/film
    *******************************************************************************'''

    def generate_html_list(self, vColor, vCount, vTitle, vYear, vIMDBid, vPoster, vResolution, vGenre, vRated, vCountry,
                           vRuntime, vIMDBScore, vTMDBScore, vRottenTScore, vMetaCScore, vPlot, vTrailer, vDirector,
                           vActors, vSize, vFreeL, vFLISid, vMyScore, vMyScoreDate):

        styleSScore = '<span style="color: #333333;">'  # Standard score
        styleNScore = '<span style="color: #ffffff; background-color: #ff0000;">'  # Negative score
        stylePScore = '<span style="color: #ffffff; background-color: #008000;">'  # Positive score
        styleMScore = '<span style="color: #ffffff; background-color: #000000;">'  # Personal score

        if vSize is not None:
            sSize = ('&ensp;<span style="color: #ccc;">|</span>&ensp;{0} Gb'.format(vSize))
        else:
            sSize = ''

        if vFreeL is not None:
            sFreeL = '&emsp;<img src="https://filelist.io/styles/images/tags/freeleech.png"/>'
        else:
            sFreeL = ''

        if vFLISid is not None:
            sDW = (
                f'<tr><td style="text-align: center;" colspan="2"><strong><a id="btnDw" href="{TORR_DOWNLOAD_URI}?idFlist={vFLISid}&idFolder={TORR_DOWNLOAD_FOLDER}">DOWNLOAD</a>&emsp;|&emsp;<a id="btnSd" href="{TORR_DOWNLOAD_URI}?idFlist={0}&idFolder={TORR_SEED_FOLDER}">SEED ONLY</a></strong></td></tr>')
        else:
            sDW = ''

        sGenre = vGenre
        try:
            if sGenre is not None:
                genreDict = ['Horror', 'Animation']
                for genre in genreDict:
                    if genre.lower() in sGenre.lower():
                        sGenre = sGenre.replace(genre,
                                                '<span style="color: #ff0000;"><strong>{0}</strong></span>'.format(
                                                    genre))
        except Exception as vErr:
            logger.debug('err generate_html_list - Genre bck color:', vErr)

        sCountry = vCountry
        try:
            if sCountry is not None:
                countryDict = ['India', 'Bahasa indonesia']
                for country in countryDict:
                    if country.lower() in sCountry.lower():
                        sCountry = sCountry.replace(country,
                                                    '<span style="color: #ff0000;"><strong>{0}</strong></span>'.format(
                                                        country))
        except Exception as vErr:
            logger.debug('err generate_html_list - Country bck color:', vErr)

        try:
            if float(vIMDBScore) < 5:
                SStyleIMDB = styleNScore
            elif float(vIMDBScore) >= 7:
                SStyleIMDB = stylePScore
            else:
                SStyleIMDB = styleSScore
        except:
            SStyleIMDB = styleSScore

        try:
            if float(vTMDBScore) < 5:
                SStyleTMDB = styleNScore
            elif float(vTMDBScore) >= 7:
                SStyleTMDB = stylePScore
            else:
                SStyleTMDB = styleSScore
        except:
            SStyleTMDB = styleSScore

        try:
            if int(vRottenTScore) < 60:
                SStyleRottenT = styleNScore
            elif int(vRottenTScore) >= 75:
                SStyleRottenT = stylePScore
            else:
                SStyleRottenT = styleSScore
        except:
            SStyleRottenT = styleSScore

        try:
            if int(vMetaCScore) < 40:
                SStyleMetaC = styleNScore
            elif int(vMetaCScore) > 60:
                SStyleMetaC = stylePScore
            else:
                SStyleMetaC = styleSScore
        except:
            SStyleMetaC = styleSScore

        if vMyScore is not None and vMyScoreDate is not None:
            vMyScoreHTML = '&ensp;{0}:{1}<strong>&ensp;{2}&ensp;</strong></span><span style="color: #ccc;">|</span>'.format(
                vMyScoreDate, styleMScore, self.n2d(vMyScore))
        else:
            vMyScoreHTML = ''

        if vTrailer is not None:
            vTrailerHTML = '<a href="{0}" target="_blank" rel="noopener">(vezi trailer)</a>'.format(vTrailer)
        else:
            vTrailerHTML = ''

        try:
            html = u'<table width="600"><tbody>\n'
            html = html + (
                u'\n<tr><td colspan="2" style="font-size: 20px; color: #136cb2;" bgcolor="{0}"><span style="color: #666; font-size: 13px">{1}.&ensp;</span><strong>{2}</strong>&ensp;({3}){4}</td></tr>\n'
                    .format(vColor, str(vCount), self.n2d(vTitle), self.n2d(vYear), sFreeL))
            html = html + (
                u'\n<tr><td rowspan="5"><a href="https://www.imdb.com/title/{0}" target="_blank" rel="noopener"><img src="{1}" alt="poster" height="209"/></a></td></tr>\n'
                    .format(self.n2d(vIMDBid), self.n2d(vPoster)))
            html = html + (
                u'\n<tr><td style="font-size: 11px; color: #666;">{0}&ensp;<span style="color: #ccc;">|</span>&ensp;{1}&ensp;<span style="color: #ccc;">|</span>&ensp;{2}&ensp;<span style="color: #ccc;">|</span>&ensp;{3}&ensp;<span style="color: #ccc;">|</span>&ensp;{4}{5}&ensp;<span style="color: #ccc;">|</span></td></tr>\n'
                    .format(self.n2d(vResolution), self.n2d(sGenre), self.n2d(vRated), self.n2d(sCountry),
                            self.n2d(vRuntime), sSize))
            html = html + (
                u'\n<tr><td style="font-size: 11px; color: #666;">IMDB:{0}<strong>&ensp;{1}&ensp;</strong></span><span style="color: #ccc;">|</span>&ensp;TMDB:{2}<strong>&ensp;{3}&ensp;</strong></span><span style="color: #ccc;">|</span>&ensp;Rotten T:{4}<strong>&ensp;{5}&ensp;</strong></span><span style="color: #ccc;">|</span>&ensp;Meta C:{6}<strong>&ensp;{7}&ensp;</strong></span><span style="color: #ccc;">|</span>{8}</td></tr>\n'
                    .format(SStyleIMDB, self.n2d(vIMDBScore), SStyleTMDB, self.n2d(vTMDBScore), SStyleRottenT,
                            self.n2d(vRottenTScore), SStyleMetaC, self.n2d(vMetaCScore), vMyScoreHTML))
            html = html + (u'\n<tr><td style="font-size: 10px;">{0}{1}</td></tr>\n'
                           .format(self.n2d(vPlot), vTrailerHTML))
            html = html + (
                u'\n<tr><td style="font-size: 11px; color: #666;">Director:<span style="color: #333333;"><strong>&ensp;{0}&ensp;</strong></span><span style="color: #ccc;">|</span>&ensp;Stars:<span style="color: #333333;"><strong>&ensp;{1}</strong></span></td></tr>\n'
                    .format(self.n2d(vDirector), self.n2d(vActors)))
            html = html + sDW
            html = html + u'</tbody></table><br>\n\n'

        except Exception as vErr:
            html = html + u'</tbody></table><br>\n\n'
            logger.debug('err generate_html_list - Nu am putut genera lista html: ' + str(vErr))

        return html

    def css(self):

        css = '\n'
        css = css + '<style>\n'

        css = css + '#btnSd {\n'
        css = css + 'background:    #6aa84f;\n'
        css = css + 'background:    -webkit-linear-gradient(#6aa84f, #274e13);\n'
        css = css + 'background:    linear-gradient(#6aa84f, #274e13);\n'
        css = css + 'border-radius: 5px;\n'
        css = css + 'padding:       5px 23px;\n'
        css = css + 'color:         #ffffff;\n'
        css = css + 'display:       inline-block;\n'
        css = css + 'font:          normal 700 14px/1 "Calibri", sans-serif;\n'
        css = css + 'text-align:    center;\n'
        css = css + 'text-shadow:   1px 1px #000000;\n'
        css = css + '}\n'

        css = css + '#btnDw {\n'
        css = css + 'background:    #3d85c6;\n'
        css = css + 'background:    -webkit-linear-gradient(#3d85c6, #073763);\n'
        css = css + 'background:    linear-gradient(#3d85c6, #073763);\n'
        css = css + 'border-radius: 5px;\n'
        css = css + 'padding:       5px 20px;\n'
        css = css + 'color:         #ffffff;\n'
        css = css + 'display:       inline-block;\n'
        css = css + 'font:          normal 700 14px/1 "Calibri", sans-serif;\n'
        css = css + 'text-align:    center;\n'
        css = css + 'text-shadow:   1px 1px #000000;\n'
        css = css + '}\n'

        css = css + '</style>\n'

        return css

    def send_email(self, tFromName, tFromEmail, tToList, tSubject, tBody, lFiles, tSMTP, tUser, tPass):
        try:
            import smtplib
            from email.utils import formatdate
            from email.mime.text import MIMEText
            from email.mime.image import MIMEImage
            from email.mime.multipart import MIMEMultipart
            from email.mime.application import MIMEApplication

            msg = MIMEMultipart()
            # msg.set_charset('utf8')
            msg['From'] = '{0} <{1}>'.format(tFromName, tFromEmail)
            msg['To'] = tFromEmail
            msg['Date'] = formatdate(localtime=True)
            msg['Reply-to'] = tFromEmail
            msg['Subject'] = tSubject
            msg.attach(MIMEText(tBody.encode('utf-8'), 'html', 'UTF-8'))

            for f in lFiles or []:
                with open(f, "rb") as fil:
                    ext = f.split('.')[-1:]
                    attachedfile = MIMEApplication(fil.read(), _subtype=ext)
                    attachedfile.add_header('content-disposition', 'attachment', filename=os.path.basename(f))
                msg.attach(attachedfile)

            server = smtplib.SMTP(tSMTP, 587)
            server.ehlo()
            server.starttls()
            server.login(tUser, tPass)
            server.sendmail(tFromEmail, tToList, msg.as_string())
            server.quit()

        except Exception as vErr:
            logger.debug('[send_email] Nu am putut trimite email: ', str(vErr))

    def xml_pritify(self, xml_file_path):
        try:
            tree = ET.parse(xml_file_path)
        except Exception as e:
            logger.debug('fisier XML corupt: ' + str(e))

        root = tree.getroot()

        xml_raw = b''.join(
            [s for s in ET.tostring(root).splitlines(True) if s.strip()])  # remove empty lines from string

        dom = minidom.parseString(xml_raw)
        with open(xml_file_path, 'wb') as f:
            f.write(dom.toprettyxml(encoding='utf-8', newl='', indent=''))

    def add_movie_to_xml(self, xml_file_path, id_imdb, id_filelist, **kwargs):
        if id_imdb is None:
            logger.debug('id_imdb is None')

            id_imdb = 'tt0'

        try:
            tree = ET.parse(xml_file_path)
        except Exception as e:
            logger.debug('fisier XML corupt: ' + str(e))

        root = tree.getroot()

        movie = SubElement(root, 'movie', id_imdb=id_imdb)

        for arg_label, arg_value in zip(kwargs, kwargs.values()):
            if arg_label == 'movie_data':
                for param_label, param_value in arg_value.items():
                    if type(param_value) == str:
                        param_value = param_value.replace('"', '\'')

                    exec('{0} = SubElement(movie, "{0}")'.format(param_label))
                    exec('{0}.text = "{1}"'.format(param_label, param_value))

            if arg_label == 'trnt_data':
                trnt = ET.SubElement(movie, 'trnt', id=id_filelist)
                for param_label, param_value in arg_value.items():
                    if type(param_value) == str:
                        param_value = param_value.replace('"', '\'')

                    exec('{0} = SubElement(trnt, "{0}")'.format(param_label))
                    exec('{0}.text = "{1}"'.format(param_label, param_value))

        dom = minidom.parseString(ET.tostring(root))
        with open(xml_file_path, 'wb') as f:
            f.write(dom.toprettyxml(encoding='utf-8'))

    def update_trnt_type_xml(self, xml_file_path, id_imdb, trnt_type):
        try:
            tree = ET.parse(xml_file_path)
        except Exception as e:
            logger.debug('fisier XML corupt: ' + str(e))

        root = tree.getroot()

        for target in root.findall(".//movie[@id_imdb='" + id_imdb + "']"):
            target.set('trnt_type', trnt_type)

        dom = minidom.parseString(ET.tostring(root))
        with open(xml_file_path, 'wb') as f:
            f.write(dom.toprettyxml(encoding='utf-8'))

    def update_trnt_child_xml(self, xml_file_path, id_imdb, child_name, child_value):
        if id_imdb is None:
            logger.debug('id_imdb is None')

            id_imdb = 'tt0'

        try:
            tree = ET.parse(xml_file_path)
        except Exception as e:
            logger.debug('fisier XML corupt: ' + str(e))

        root = tree.getroot()

        for target in root.findall(".//movie[@id_imdb='" + id_imdb + "']"):
            try:
                target.find(child_name).text = child_value
            except:
                # logger.debug 'lipsa child', child_name
                pass

        dom = minidom.parseString(ET.tostring(root))
        with open(xml_file_path, 'wb') as f:
            f.write(dom.toprettyxml(encoding='utf-8'))

    def find_trnt_elem_xml(self, xml_file_path, elem, attrib, value):
        try:
            tree = ET.parse(xml_file_path)
        except Exception as e:
            logger.debug('fisier XML corupt: ' + str(e))

        root = tree.getroot()

        try:
            if len(root.findall(".//" + elem + "[@" + attrib + "='" + value + "']")) > 0:
                self.find = True
            else:
                self.find = False
        except Exception as e:
            logger.debug('' + str(e))

            self.find = False

    def new_trnt_link_xml(self, xml_file_path, id_imdb, id_filelist, **kwargs):
        try:
            tree = ET.parse(xml_file_path)
        except Exception as e:
            logger.debug('fisier XML corupt: ' + str(e))

        root = tree.getroot()

        movie = root.find(".//movie[@id_imdb='" + id_imdb + "']")

        for arg_label, arg_value in zip(kwargs, kwargs.values()):
            if arg_label == 'trnt_data':
                trnt = ET.SubElement(movie, 'trnt', id=id_filelist)
                for param_label, param_value in arg_value.items():
                    if type(param_value) == str:
                        param_value = param_value.replace('"', '\'')

                    exec('{0} = SubElement(trnt, "{0}")'.format(param_label))
                    exec('{0}.text = "{1}"'.format(param_label, param_value))

        dom = minidom.parseString(ET.tostring(root))
        with open(xml_file_path, 'wb') as f:
            f.write(dom.toprettyxml(encoding='utf-8'))

    def count_xml(self, xml_file_path):
        try:
            tree = ET.parse(xml_file_path)
        except Exception as e:
            logger.debug('fisier XML corupt: ' + str(e))

        root = tree.getroot()

        logger.debug('\ntorrenti noi:', len(root.findall(".//trnt")))

        logger.debug('total filme:', len(list(root)))

        logger.debug('din care')

        new = 0
        tr = 0
        seen = 0
        list_seen = []
        for movie in root:
            if movie.find("seen_type").text == '0':
                new += 1
            elif movie.find("seen_type").text == '1':
                tr += 1
            else:
                seen += 1
                list_seen.append(movie.attrib['id_imdb'])

        logger.debug('- filme noi:', new)

        logger.debug('- torrenti noi:', tr)

        logger.debug('- vazute sau descarcate:', seen)

        self.new_movies = len(list(root))

    def empty_xml(self, xml_file_path):
        try:
            tree = ET.parse(xml_file_path)
        except Exception as e:
            logger.debug('fisier XML corupt: ' + str(e))

        root = tree.getroot()

        movie_count = len(root)
        for x in range(movie_count):
            movie = list(root)[0]
            root.remove(movie)

        dom = minidom.parseString(ET.tostring(root))
        with open(xml_file_path, 'wb') as f:
            f.write(dom.toprettyxml(encoding='utf-8'))

    def generate_movie_table(self, movie_template_path, trnt_template_path, mprm, tprm):
        # template_file = open('/home/matei/Documents/Python/MoviePediaV2/views/_movie.html', 'r')
        template_file = open(movie_template_path, 'r')
        template = template_file.read()
        template_file.close()

        # with open('/home/matei/Documents/Python/MoviePediaV2/views/movie.html', 'w+') as f:
        # 	f.write('')
        # f.close

        # replace param without values
        for key, value in mprm.items():
            if key in template:
                # 		if value != 'None' and value != 'False' and value != 'N/A' and value is not None:
                # 			key_list = ('imdb_score', 'score', 'rott_score', 'meta_score', 'my_imdb_score')
                # 			if key in key_list:
                # 				class_value = self.get_key_class(key, value)
                # 				template = template.replace('mprm_{0}'.format(key), value)
                # 				template = template.replace('class_{0}'.format(key), class_value)
                # 			template = template.replace('mprm_{0}'.format(key), value)

                # # replace all param without values with dash/'---'
                # for key, value in mprm.items():
                # 	template = template.replace('mprm_{0}'.format(key), '---')

                template = self.template_replace(template, key, value)

        template = template.replace('trnt_tbody', self.generate_trnt_table(trnt_template_path, tprm))

        # with open('/home/matei/Documents/Python/MoviePediaV2/views/movie.html', 'w+') as f:
        # 	f.write(template)
        # f.close

        return template + '\n'

    def template_replace(self, template, key, value):
        score_list = ('imdb_score', 'score', 'rott_score', 'meta_score', 'my_imdb_score')
        genre_bad_list = ('Horror', 'Animation')
        country_bad_list = ('India', 'Bahasa indonesia', 'China')

        if value != 'None' and value != 'False' and value != 'N/A' and value is not None:

            if key in score_list:
                class_value = self.get_key_class(key, value)
                template = template.replace('mprm_{0}'.format(key), value)
                template = template.replace('class_{0}'.format(key), class_value)

            elif key == 'genre':
                for genre in genre_bad_list:
                    if genre.lower() in value.lower():
                        value = value.replace(genre,
                                              '<span style="color: #ff0000;"><strong>{0}</strong></span>'.format(genre))

            elif key == 'country':
                for country in country_bad_list:
                    if country.lower() in value.lower():
                        value = value.replace(country,
                                              '<span style="color: #ff0000;"><strong>{0}</strong></span>'.format(
                                                  country))

            elif key == 'trailer':
                value = '<a href="{0}" target="_blank">WATCH TRAILER</a>'.format(value)
                template = template.replace('mprm_{0}'.format(key), value)

            template = template.replace('mprm_{0}'.format(key), value)

        else:

            if key == 'my_imdb_score' or key == 'seen_date':
                template = template.replace('mprm_{0}'.format(key), '')
                template = template.replace('class_{0}'.format(key), '')

            elif key == 'trailer':
                template = template.replace('mprm_{0}'.format(key), '')

            else:
                template = template.replace('mprm_{0}'.format(key), '---')
                template = template.replace('class_{0}'.format(key), '')

        return template

    def generate_trnt_table(self, trnt_template_path, tprm):
        # template_file = open('/home/matei/Documents/Python/MoviePediaV2/views/_torrent.html', 'r')
        template_file = open(trnt_template_path, 'r')
        template = template_file.read()
        template_file.close()

        trnt_tbody = template
        index = 0

        for key, value in tprm.items():
            if isinstance(value, dict):
                for key2, value2 in value.items():
                    trnt_tbody = trnt_tbody.replace('trnt_id_filelist', key)
                    if value2 == 'True':
                        # trnt_tbody = trnt_tbody.replace('trnt_{0}'.format(key2), 'freeleech')
                        trnt_tbody = trnt_tbody.replace('trnt_{0}'.format(key2),
                                                        '<img src="https://filelist.io/styles/images/tags/freeleech.png" alt="freeleech" />')
                    elif value2 != 'None' and value2 != 'False' and value2 != 'N/A' and value2 is not None:
                        trnt_tbody = trnt_tbody.replace('trnt_{0}'.format(key2), value2)

                # replace all param without values with dash/'---'
                for key2, value2 in value.items():
                    trnt_tbody = trnt_tbody.replace('trnt_{0}'.format(key2), '')

                index += 1
                if index < len(tprm):
                    trnt_tbody += template
            else:
                if key in template:
                    trnt_tbody = trnt_tbody.replace('trnt_id_filelist', key)
                    if value == 'True':
                        # trnt_tbody = trnt_tbody.replace('trnt_{0}'.format(key), 'freeleech')
                        trnt_tbody = trnt_tbody.replace('trnt_{0}'.format(key2),
                                                        '<img src="https://filelist.io/styles/images/tags/freeleech.png" alt="freeleech" />')
                    elif value != 'None' and value != 'False' and value != 'N/A' and value is not None:
                        trnt_tbody = template.replace('trnt_{0}'.format(key), value)

        return trnt_tbody

    def generate_email_html(self, template_path, list_new, list_trnt, list_seen, durata):
        # template_file = open('/home/matei/Documents/Python/MoviePediaV2/views/email_filelist.html', 'r')
        template_file = open(template_path, 'r')
        template = template_file.read()
        template_file.close()

        email_body = template

        if not list_new and not list_trnt and not list_seen:
            email_body = ''
        else:
            if list_new != '':
                email_body = email_body.replace('list_new', list_new)
            else:
                email_body = email_body.replace('list_new', '')

            if list_trnt != '':
                email_body = email_body.replace('list_trnt', list_trnt)
            else:
                email_body = email_body.replace('list_trnt', '')

            if list_seen != '':
                email_body = email_body.replace('list_seen', list_seen)
            else:
                email_body = email_body.replace('list_seen', '')

            email_body = email_body.replace('prm_durata', '{0}'.format(durata))

        return email_body

    def update_filelist_xml(self, xml_file_path):
        try:
            tree = ET.parse(xml_file_path)
        except Exception as e:
            logger.debug('fisier XML corupt: ' + str(e))

        root = tree.getroot()
        for movie in root:

            if movie.find("title").text is None:
                id_imdb = movie.attrib['id_imdb']
                tmdb = TMDB(id_imdb, '', '')
                tmdb.get_data()

                attrs = vars(tmdb)
                for item in attrs.items():
                    self.update_trnt_child_xml(xml_file_path, tmdb.id_imdb, '{0}'.format(item[0]),
                                               '{0}'.format(item[1]))

                omdb = OMDB(id_imdb)
                omdb.get_data()

                self.update_trnt_child_xml(xml_file_path, omdb.id_imdb, 'rated', '{0}'.format(omdb.rated))
                self.update_trnt_child_xml(xml_file_path, omdb.id_imdb, 'imdb_score', '{0}'.format(omdb.imdb_score))
                self.update_trnt_child_xml(xml_file_path, omdb.id_imdb, 'rott_score', '{0}'.format(omdb.rott_score))
                self.update_trnt_child_xml(xml_file_path, omdb.id_imdb, 'meta_score', '{0}'.format(omdb.meta_score))

        self.xml_pritify(xml_file_path)

    def read_filelist_xml(self, xml_file_path, movie_template_path, trnt_template_path):
        try:
            tree = ET.parse(xml_file_path)
        except Exception as e:
            logger.debug('fisier XML corupt: ' + str(e))

        root = tree.getroot()

        crt_new = 0
        crt_tr = 0
        crt_seen = 0

        list_new = ''
        list_trnt = ''
        list_seen = ''

        for movie in root:

            if movie.find("seen_type").text == '0':
                crt_new += 1
                all_movie = {'crt': '{0}'.format(crt_new), 'id_imdb': '{0}'.format(movie.attrib['id_imdb']),
                             'bck_color': 'F4CCCC'}
                all_trnt = {}
                for trnt in movie.iter('trnt'):
                    # logger.debug trnt.attrib['id']
                    for subelem in list(movie):
                        all_movie[subelem.tag] = subelem.text

                    one_trnt = {}
                    for subelem in list(trnt):
                        one_trnt[subelem.tag] = subelem.text
                    all_trnt[trnt.attrib['id']] = one_trnt

                list_new += self.generate_movie_table(movie_template_path, trnt_template_path, all_movie, all_trnt)

            elif movie.find("seen_type").text == '1':  # FFF2CC
                crt_tr += 1
                all_movie = {'crt': '{0}'.format(crt_tr), 'id_imdb': '{0}'.format(movie.attrib['id_imdb']),
                             'bck_color': 'FFF2CC'}
                all_trnt = {}
                for trnt in movie.iter('trnt'):
                    # logger.debug trnt.attrib['id']
                    for subelem in list(movie):
                        all_movie[subelem.tag] = subelem.text

                    one_trnt = {}
                    for subelem in list(trnt):
                        one_trnt[subelem.tag] = subelem.text
                    all_trnt[trnt.attrib['id']] = one_trnt

                list_trnt += self.generate_movie_table(movie_template_path, trnt_template_path, all_movie, all_trnt)

            else:
                crt_seen += 1  # CFE2F3
                all_movie = {'crt': '{0}'.format(crt_seen), 'id_imdb': '{0}'.format(movie.attrib['id_imdb']),
                             'bck_color': 'CFE2F3'}
                all_trnt = {}
                for trnt in movie.iter('trnt'):
                    # logger.debug trnt.attrib['id']
                    for subelem in list(movie):
                        all_movie[subelem.tag] = subelem.text

                    one_trnt = {}
                    for subelem in list(trnt):
                        one_trnt[subelem.tag] = subelem.text
                    all_trnt[trnt.attrib['id']] = one_trnt

                list_seen += self.generate_movie_table(movie_template_path, trnt_template_path, all_movie, all_trnt)

        # with open('/home/matei/Documents/Python/MoviePediaV2/views/tmp.html', 'w+') as f:
        # 	f.write(list_new + list_trnt + list_seen)
        # f.close

        if list_new:
            list_new = '<h3>FILME NOI:</h3>\n' + list_new
        if list_trnt:
            list_trnt = '<h3>TORRENTI NOI:</h3>\n' + list_trnt
        if list_seen:
            list_seen = '<h3>FILME VAZUTE / TORRENTI DESCARCATI:</h3>\n' + list_seen

        return list_new, list_trnt, list_seen

    def get_key_class(self, key, value):
        if key == 'imdb_score' or key == 'score':
            if float(value) < 5:
                new_value = 'neg'
            elif float(value) >= 7:
                new_value = 'poz'
            else:
                new_value = 'std'

        elif key == 'rott_score':
            if int(float(value)) < 60:
                new_value = 'neg'
            elif int(float(value)) >= 75:
                new_value = 'poz'
            else:
                new_value = 'std'

        elif key == 'meta_score':
            if int(float(value)) < 40:
                new_value = 'neg'
            elif int(float(value)) > 60:
                new_value = 'poz'
            else:
                new_value = 'std'

        elif key == 'my_imdb_score':
            new_value = 'prs'

        else:
            new_value = 'std'

        return new_value


def send_email(items):
    if items:
        logger.info("Starting emailing routine")
        mtls = Mtls()
        mtls.empty_xml(xml_trnt_path)

        for item in items:
            mtls = prepare_item_for_email(item, mtls)

        mtls.update_filelist_xml(xml_trnt_path)
        mtls.count_xml(xml_trnt_path)

        list_new, list_trnt, list_seen = mtls.read_filelist_xml(xml_trnt_path, movie_template_path,
                                                                trnt_template_path)
        email_body = mtls.generate_email_html(template_path, list_new, list_trnt, list_seen, datetime.datetime.now())

        if mtls.new_movies == 1:
            mail_subject = 'Film nou pe FileList'
        elif mtls.new_movies > 1:
            mail_subject = '{0} filme noi pe FileList'.format(mtls.new_movies)
        else:
            mail_subject = 'Nou pe FileList'

        with open('../test.html', 'w') as f:
            f.write(email_body)

        if email_body:
            logger.info('Sending email')
            mtls.send_email('TeleCinemateca', EMAIL_USER, EMAIL_TO, mail_subject, email_body, '',
                            EMAIL_HOSTNAME, EMAIL_USER, EMAIL_PASS)
            return
    logger.info('Nothing left to send')


def prepare_item_for_email(item, mtls):
    # Change here for seen types
    if item['hit_tmdb'] == 0:
        item['seen_type'] = 0
    else:
        item['seen_type'] = 1
    if item['already_in_db']:
        item['seen_type'] = 2

    item['size'] = "%.1f" % (item['size'] / 1000000000)
    item['year'] = item['startYear']
    item['genre'] = item['genres']
    item['runtime'] = item['runtimeMinutes']
    item['imdb_score'] = item['averageRating']
    item['director'] = 'DIRECTOR'  # TODO
    item['cast'] = 'CAST'  # TODO
    item['poster'] = None  # TODO
    item['my_imdb_score'] = None  # TODO
    item['seen_date'] = None  # TODO

    item['resolution'] = get_torr_quality(item['name'])
    item['trend'] = ''  # TODO
    item['id'] = str(item['id'])

    mtls.find_trnt_elem_xml(xml_trnt_path, 'movie', 'id_imdb', item['imdb'])
    if mtls.find is False:
        mtls.add_movie_to_xml(xml_trnt_path, item['imdb'], item['id'], movie_data=item,
                              trnt_data=item)
    elif mtls.find is True:
        mtls.find_trnt_elem_xml(xml_trnt_path, 'trnt', 'id', item['id'])
        if mtls.find is False:
            mtls.new_trnt_link_xml(xml_trnt_path, item['imdb'], item['id'],
                                   trnt_data=item)
    mtls.xml_pritify(xml_trnt_path)
    return mtls


if __name__ == '__main__':
    # test package
    x = {
        'already_in_db': False,
        # Daca e sau nu in baza de date my_movies - adica alea vazute (prin intermediul serviciului astuia)
        'averageRating': 5.4,
        'awards': '3 nominations',
        'better_quality': False,
        'category': 'Filme HD-RO',
        'comments': 0,
        'country': 'Italy',
        'doubleup': 0,
        'download_link': 'https://filelist.io/download.php?id=748320&passkey=f5684696415b6f98834f1872bd03a8c1',
        'endYear': None,
        'files': 1,
        'freeleech': 0,
        'genres': 'Comedy,Drama,Romance',
        'hit_omdb': 1,  # Daca am gasit sau nu pe omdb date
        'hit_tmdb': 1,  # Daca am gasit sau nu pe tmdb date
        'id': 748320,
        'imdb': 'tt11154906',
        'imdb_id': 11154906,
        'internal': 0,
        'isAdult': 0,
        'lang': 'Italian',
        'last_update_omdb': datetime.datetime(2021, 8, 18, 15, 19, 56),
        'last_update_tmdb': datetime.datetime(2021, 8, 18, 15, 19, 55),
        'leechers': 0,
        'meta_score': None,
        'moderated': 1,
        'name': 'Out.of.My.League.2020.720p.WEB-DL.DD+5.1.H.264-NAISU',
        'numVotes': 338,
        'originalTitle': 'Sul più bello',
        'ovrw': 'Marta may be an orphan, and she may be affected by a lethal '
                'illness, yet she is the most positive person one can meet. She '
                'wants a boy to fall for her. Not any boy - the most handsome of '
                'them all. One day, she may have found her match.',
        'primaryTitle': 'Out of My League',
        'rated': None,
        'rott_score': None,
        'runtimeMinutes': 91,
        'score': None,
        'seeders': 20,
        'size': 1340928446,
        'small_description': 'Comedy, Drama, Romance',
        'startYear': 2020,
        't_soundex': 'O3154',
        'tconst': 11154906,
        'times_completed': 28,
        'title': 'Sul più bello',
        'titleType': 'movie',
        'torr_already_seen': False,  # Daca torrentul a fost procesat pana acum si trimis prin email
        'trailer_link': 'https://www.youtube.com/watch?v=PQM54p9IKZs',
        'upload_date': '2021-08-18 11:30:23'
    }
    send_email([x])
