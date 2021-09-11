import urllib.request
import urllib.response
import urllib.parse
from urllib.error import URLError
import email
import socket
import io

GOPHER_TYPES = {'0': 'text/plain',
                '1': 'text/gopher; encoding=us-ascii',
                '2': 'ccso:',
                '3': 'text/plain',   # error message
                '4': 'application/binhex',
                '5': 'application/octet-stream',  # 5 corresponds to a DOS file, whatever that means
                '6': 'text/x-uuencode',
                # can't get a straight answer from the internet on what the correct mime type should be.
                '7': 'text/gopher',  # Full text search
                '8': 'telnet:',
                '9': 'application/octet-stream',
                # + for  a mirror server, handled explicitly in the below code.
                'g': 'image/gif',
                'I': 'image',
                'T': 'telnet:',
                'd': 'application/msword',
                's': 'application/x-wav',
                }


class GopherHandler(urllib.request.BaseHandler):
    def gopher_open(self, req: urllib.request.Request):
        parsed = urllib.parse.urlparse(req.full_url)
        host, _, port = req.host.partition(':')
        port = int(port) if port else 70
        if len(parsed.path) > 1:
            # parsed.path[0] is always a '/'
            gopher_type = parsed.path[1]
            path = parsed.path[2:]
        else:
            gopher_type = '1'
            path = ''
        print('GOPHER', gopher_type, path)
        conn = socket.create_connection((host, port))
        conn.sendall(path.encode('ASCII'))
        if gopher_type == '7':
            conn.sendall(b'\t')
            conn.sendall(input('Enter search query: ').encode('ascii'))
        conn.sendall(b'\r\n')
        f = conn.makefile('rb')
        conn.close()
        if '\t' in parsed.path:  # Gopher+
            first_character = f.read(1)
            if first_character not in b'+-':
                raise URLError("This server does not support Gopher+")
            length = int(f.readline().decode('ascii').strip())
            if length == -1:
                # File terminated by a period on a line by itself.
                # I'll implement this later.
                raise NotImplementedError
            elif length == -2:
                return urllib.response.addinfourl(f, email.message_from_string(
                    'Content-Type: application/octet-stream\n', req.full_url, None))
            else:
                return urllib.response.addinfourl(f, email.message_from_string("Content-Length: %d" % length))
        else:
            mimetype = GOPHER_TYPES.get(gopher_type, 'application/octet-stream')
            return urllib.response.addinfourl(f, email.message_from_string('Content-Type: %s\n'%mimetype),
                                              req.full_url, None)


EOF_STR = b'\r\n.\r\n'


class PeriodDetector(io.IOBase):
    """
    Wraps a file, and detects, and artificially produces an EOF, upon reading the sequence b'\r\n.\r\n'.
    Assumes it is not safe to read past this point, in case of exceedingly dumb servers that will transmit
    this sequence in lieu of closing the connection.

    I do not expect to encounter any such servers, but I've dealt with enough loosely defined protocols with
    seedy back-alley server implementations that barely conform to them to know you can never be too careful.
    """
    def __init__(self, f):
        super().__init__()
        self._f=f
        self._eof=False
        self._maybe_eof = 0

    def read(self, n=-1):
        if self.eof:
            return b''
        data = self.f.read(n)
        if data[-5:] == EOF_STR:
            self._eof = True
            return data[:-5]
        for i in range(4,0,-1):
            eof_portion = data[:-i]
            if eof_portion == EOF_STR[:i]:
                self._maybe_eof = 5 - i
                return data[-i:]
            # TODO FINISH ME
