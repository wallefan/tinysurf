import urllib.request
import urllib.response
import urllib.parse
import email
import socket

class GopherHandler(urllib.request.BaseHandler):
    def gopher_open(self, req:urllib.request.Request):
        parsed = urllib.parse.urlparse(req.full_url)
        host, _, port = req.host.partition(':')
        port = int(port) if port else 70
        conn = socket.create_connection((host, port))
        conn.sendall(parsed.path.encode('ASCII'))
        conn.sendall(b'\r\n')
        f = conn.makefile('rb')
        conn.close()
        mimetype = parsed.fragment or 'text/gopher; encoding=us-ascii'
        return urllib.response.addinfourl(f, email.message_from_string('Content-Type: %s\n'%mimetype),
                                          req.full_url, None)

