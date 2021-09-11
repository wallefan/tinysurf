import getpass
import urllib.request
import urllib.parse
import posixpath
import ssl
import socket
import warnings
import urllib.error
from urllib.response import addinfourl
import email


# WHY DOES GEMINI'S URL PARSER HAVE TO BE SO F**KING REBELLIOUS!?
# this function is buggy and bad and i don't understand why it doesn't work
def gemini_urljoin(old, new):
    print(old, new)
    old_parsed = urllib.parse.urlparse(old)
    new_parsed = list(urllib.parse.urlparse(new))
    if ':' not in new and new[0] != '/':  # relative directory.
        if old_parsed.path not in ('', '/'):
            new_parsed = [old_parsed.scheme, old_parsed.netloc,
                          posixpath.join(posixpath.dirname(old_parsed.path), new), '', '', '']
        else:
            new_parsed = [old_parsed.scheme, old_parsed.netloc, new, '', '', '']
    elif new[0] == '/':
        if len(new) > 1 and new[1] == '/':
            return 'gemini:' + new
        new_parsed = [old_parsed.scheme, old_parsed.netloc, new, '', '', '']
    else:
        if not new_parsed[0]:
            new_parsed[0] = old_parsed[0]
            if not new_parsed[1]:
                new_parsed[1] = old_parsed[1]
    if './' in new_parsed[2]:
        new_parsed[2] = posixpath.normpath('/'+new_parsed[2])[1:]
    return urllib.parse.urlunparse(new_parsed)


class GeminiWarning(Warning):
    pass


class GeminiHandler(urllib.request.BaseHandler):
    __slots__ = ('sslcontext',)

    def __init__(self, ctx=None, input=input, sensitive_input=getpass.getpass):
        self.sslcontext = ctx or ssl.SSLContext()
        self.input = input
        self.sensitive_input = sensitive_input

    def gemini_open(self, req: urllib.request.Request):
        host, _, port = req.host.partition(':')
        port = int(port) if port else 1965
        s = self.sslcontext.wrap_socket(socket.create_connection((host, port)), server_hostname=host)
        s.sendall(req.full_url.encode('ascii'))
        s.sendall(b'\r\n')
        f = s.makefile('rb')
        s.close()  # iorefcount will keep the socket open.
        status = f.read(2).decode()
        meta = f.readline().decode()
        # So far, I have only encountered one gemini capsule that uses a tab instead of a space in the status line,
        # but support it I shall
        if meta[0] != ' ' or meta[-2:] != '\r\n':
            # Having this as a warning instead of an error *technically* causes this to fail conman.org test #10.
            warnings.warn(GeminiWarning("Gemini protocol violation re: status line format."))
            print(repr(meta))
        meta = meta.strip()
        if status[0] == '2':
            headers = email.message_from_string('Content-Type: %s\n' % meta)
            if headers.get_content_charset() is None:
                headers.set_charset('utf8')
            print('GEMINI OK')
            return addinfourl(f, headers, req.full_url, int(status))
        f.close()  # non-2x status will never return a body
        error_handler = getattr(self.parent, 'gemini_error_%sx' % status[0], None)
        if not error_handler:
            error_handler = getattr(self, 'gemini_error_%sx' % status[0], None)
            if not error_handler:
                raise urllib.error.URLError(meta)
        return error_handler(status, meta, req)

    def gemini_error_3x(self, error, dest_url, req):
        if dest_url.startswith('//'):
            dest_url = 'gemini:' + dest_url
        print('GEMINI REDIRECTING', dest_url)
        new_req = urllib.request.Request(gemini_urljoin(req.full_url, dest_url))
        redirs = getattr(req, 'redirs', set())
        if dest_url in redirs:
            raise urllib.error.URLError("infinite redirect loop")
        if len(redirs) > 25:
            raise urllib.error.URLError("Too many redirects (25)")
        redirs.add(dest_url)
        new_req.redirs = redirs
        return self.parent.open(new_req)

    def gemini_error_1x(self, error, prompt, req):
        if error == '11':
            user_input = self.sensitive_input(prompt)
        else:
            user_input = self.input(prompt)
        import urllib.parse
        parsed = list(urllib.parse.urlparse(req.full_url))
        parsed[4] = urllib.parse.quote(user_input)
        unparsed = urllib.parse.urlunparse(parsed)
        return self.parent.open(unparsed)
