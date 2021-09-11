import email
import urllib.request
import urllib.parse
import socket
from urllib.response import addinfourl

class Finger(urllib.request.BaseHandler):
    def finger_open(self, req:urllib.request.Request):
        parsed = urllib.parse.urlparse(req.full_url)
        host, sep, port = parsed.hostname.partition(':')
        if sep:
            port = int(port)
        else:
            port = 79
        s = socket.create_connection((host, port))
        s.sendall(parsed.path[1:].encode('ascii'))
        s.sendall(b'\r\n')
        return addinfourl(s.makefile('rb'), email.message_from_string("Content-Type: text/plain"), req.full_url, None)