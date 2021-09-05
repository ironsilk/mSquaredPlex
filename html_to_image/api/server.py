import atexit
import io
import os
from wsgiref.simple_server import make_server
from utils import setup_logger
import falcon
import requests

logger = setup_logger('HTMLtoSTUFF')
DOCTRON_PORT = 8080

url2image_path = f"http://127.0.0.1:{DOCTRON_PORT}/convert/html2image?u=doctron&p=lampnick&url="
url2pdf_path = f"http://127.0.0.1:{DOCTRON_PORT}/convert/html2pdf?u=doctron&p=lampnick&url="

forward = 'ceva'


class IMAGE_HANDLER:
    def on_get(self, req, resp):
        """Handles GET requests"""
        # print(req.query_string)
        pkg = req.params
        if 'url' in pkg.keys():
            r = requests.get(url=url2image_path + pkg['url'], stream=True)
            # print(r.raw)
            # resp.data = r.text
            resp.content_type = r.headers.get('Content-Type',
                                              falcon.MEDIA_HTML)
            resp.status = falcon.get_http_status(r.status_code)
            resp.stream = r.iter_content(io.DEFAULT_BUFFER_SIZE)
        else:
            resp.media = 'Specify url as a query string: http:.../url2image?url=YOUR_URL'
        return

    def on_post(self, req, resp):
        global forward
        pkg = req.params
        if 'html' in pkg.keys():
            forward = pkg['html']
            r = requests.get(url=url2image_path + "http://localhost:5431/forwarder", stream=True)
            print(url2image_path + "http://localhost:5431/forwarder")
            # resp.data = r.text
            resp.content_type = r.headers.get('Content-Type',
                                              falcon.MEDIA_HTML)
            resp.status = falcon.get_http_status(r.status_code)
            resp.stream = r.iter_content(io.DEFAULT_BUFFER_SIZE)
        else:
            resp.media = 'Specify url as a query string: http:.../url2image?url=YOUR_URL'
        return


class PDF_HANDLER:
    def on_get(self, req, resp):
        """Handles GET requests"""
        # print(req.query_string)
        pkg = req.params
        if 'url' in pkg.keys():
            r = requests.get(url=url2pdf_path + pkg['url'], stream=True)
            # print(r.raw)
            # resp.data = r.text
            resp.content_type = r.headers.get('Content-Type',
                                              falcon.MEDIA_HTML)
            resp.status = falcon.get_http_status(r.status_code)
            resp.stream = r.iter_content(io.DEFAULT_BUFFER_SIZE)
        else:
            resp.media = 'Specify url as a query string: http:.../url2image?url=YOUR_URL'
        return

    def on_post(self, req, resp):
        global forward
        return


class FORWARDER:

    def on_get(self, req, resp):
        global forward
        """Handles GET requests"""
        resp.content_type = falcon.MEDIA_HTML
        resp.status = falcon.get_http_status(200)
        resp.body = forward


api = falcon.App()
api.add_route('/url2image', IMAGE_HANDLER())  # done
api.add_route('/html2image', IMAGE_HANDLER())
api.add_route('/url2pdf', PDF_HANDLER())  # done
api.add_route('/html2pdf', PDF_HANDLER())
api.add_route('/forwarder', FORWARDER())

if __name__ == '__main__':
    with make_server('', 5431, api) as server:
        logger.info("TORR API Service running on port {p}".format(p=5431))
        # Serve until process is killed
        server.serve_forever()
