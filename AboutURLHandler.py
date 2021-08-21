import urllib.request
import urllib.parse
import io
import urllib.response
from email import message_from_string
import sys
import os
import posixpath

_GEMHEADER =message_from_string("Content-Type: text/gemini\n")

class AboutHandler(urllib.request.BaseHandler):
    def __init__(self, tinysurf):
        self.browser = tinysurf
    def about_open(self, req: urllib.request.Request):
        parsed = urllib.parse.urlparse(req.full_url)
        if parsed.path == 'blank':
            return urllib.response.addinfourl(io.BytesIO(), message_from_string("Content-Type: text/plain\n"),
                                              'about:blank', None)
        elif parsed.path == 'firstrun':
            return urllib.response.addinfourl(open(os.path.join(os.path.dirname(sys.argv[0]), 'firstrun.gmi'), 'rb'),
                                              _GEMHEADER, req.full_url)
        parts = posixpath.split(parsed.path)
        if parts[0] == 'tutorial':
            tutorial_path = os.path.join(os.path.dirname(sys.argv[0]), 'tutorial')
            if parts[1] == 'back':
                # the back.gmi tutorial messes with the back.gmi button history.
                # we do this by falsifying the returned URL which will trick the renderer code into thinking
                # we got redirected, and go back.gmi to the page we got "redirected" to.
                return urllib.response.addinfourl(open(os.path.join(tutorial_path, 'back.gmi'), 'rb'), _GEMHEADER,
                                                  parsed.query)
            elif parts[1] == 'test':
                if parts[2] == 'bookmark_add':
                    if self.browser.history[-1] != self.browser.bookmarks[-1][0]:
                        return urllib.response.addinfourl(io.BytesIO(
                            b"You do, um, actually have to do it.  Don't worry, you'll delete it in the next step.\n\n"
                            b"Hit back to try again."), _GEMHEADER, req.full_url)
                    else:
                        return
            else:
                return urllib.response.addinfourl(open(os.path.join(tutorial_path, parts[1]+'.gmi'), 'rb'),
                                                  message_from_string("Content-Type: text/gemini\n"),
                                                  req.full_url)

