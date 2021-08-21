import urllib.request
import urllib.parse
import posixpath  # for processing Gemini URLs.
import io
import gemini, gopher
import sys
import textwrap
import csv  # for gopher.
from AboutURLHandler import AboutHandler
import os
import configparser
import atexit


class BookmarksDialect(csv.Dialect):
    """CSV dialect compatible with the official Gemini bookmark list interchange format."""
    delimiter = '\t'
    quoting = csv.QUOTE_NONE
    escapechar = None
    lineterminator = '\n'


def download(f, fout):
    readinto = getattr(f, 'readinto1', None)
    if not readinto:
        readinto = f.readinto
    write = fout.write
    total = 0
    size = 1024 * 1024
    buf = bytearray(size)
    n = readinto(buf)
    while n:
        if n == size:
            write(buf)
        else:
            write(buf[:n])
        total += n
        sys.stdout.write('\rDOWNLOADING %d' % total)
        n = f.readinto(buf)


class Tinysurf:
    def __init__(self):
        self.opener = urllib.request.build_opener(gemini.GeminiHandler, gopher.GopherHandler, AboutHandler(self))
        self.history = []
        self.forward = []
        self.last_links = []
        self.config = configparser.ConfigParser({'zebra': '240', 'link_color': '',
                                                 'bookmarks_location': '~/.config/tinysurf/bookmarks.txt',
                                                 'unwrap': 'off'})
        self.config.read([os.path.expanduser('~/.config/tinysurf.ini')])
        try:
            with open(os.path.expanduser(self.config['DEFAULT']['bookmarks_location'])) as f:
                self.bookmarks = list(csv.reader(f, BookmarksDialect))
        except FileNotFoundError:
            self.bookmarks = [['about:firstrun', 'home']]
        atexit.register(self.save_bookmarks)

    def main(self):
        for url, *aliases in self.bookmarks:
            if 'home' in aliases:
                # after exiting this loop, url will be set to the correct URL.
                break
        else:
            url = 'about:firstrun'
        while True:
            try:
                self.show_page(url)
            except urllib.error.URLError as e:
                print('***', e.reason)
            except OSError as e:
                print('***', e)
            url = self.interactive_prompt()
            while url is None:
                url = self.interactive_prompt()
            url = gemini.gemini_urljoin(self.history[-1], url)
            print('NAVIGATING', url)

    def interactive_prompt(self):
        response = input('[>] ')
        if not response:
            if len(self.links) == 1:
                return self.links[0]
            elif not self.links:
                self.history.pop()  # pop the page we just loaded
                return self.history.pop()
            else:
                print("PLEASE CHOOSE A LINK")
        elif response.isnumeric():
            response = int(response) - 1
            if response >= len(self.links):
                if not self.links:
                    print("There are no links on this page, please enter a URL or command")
                else:
                    print("Please enter a link number from 1 to %d" % len(self.links))
                return
            return self.links[response]
        elif response == '-/':
            print('-/ = quit.  See you next time!')
        elif response[0] in '-+':
            if response[0] == '+':
                past = self.history
                future = self.forward
                present = None
            else:
                past = self.forward
                future = self.history
                present = self.history.pop()  # the last element in history is the page we just loaded.
            if not response[1:]:
                n = 1
            else:
                if not response[1:].isnumeric():
                    print("Please provide an integer number of pages to go {}"
                          .format('back' if response[0]=='-' else 'forward'))
                    return
                else:
                    n = int(response[1:])
                    if n > len(future):
                        print("Can't go {} that far".format('back' if response[0] == '-' else 'forward'))
                        return
            for _ in range(n):
                if present:
                    past.append(present)
                present = future.pop()
            return present
        elif response[0] == '*':
            # bookmarks
            bookmark = response[1:]
            if not bookmark or bookmark == '.':
                if not self.bookmarks:
                    print("YOU DO NOT HAVE  ANY BOOKMARKS")
                    return
                include_urls = bookmark == '.'
                for i, (url, *aliases) in enumerate(self.bookmarks):
                    print('[%d] %s' % (i + 1,
                                       url if not aliases else
                                       '%s <%s>' % (aliases[0], url) if include_urls else aliases[0]
                                       ))
            elif bookmark == '*':
                self.bookmark_manager()
                return
            elif bookmark[0] == '+':
                # add bookmark
                bookmarkname = bookmark[1:]
                if not bookmarkname:
                    print("Please provide a bookmark name, e.g. *+Wally's World")
                    print("Alternatively, use *++ to create a bookmark without a name")
                elif bookmarkname == '+':
                    idx = self.add_bookmark(self.history[-1])
                    print("%s is now bookmark #%d." % (self.history[-1], idx+1))
                elif bookmarkname[0] == '+':
                    print("Bookmark names may not start with a plus sign.")
                    return
                else:
                    idx = self.add_bookmark(self.history[-1], bookmarkname)
                    print('"%s" (%s) is now bookmark #%d.' % (bookmarkname, self.history[-1], idx+1))
            elif bookmark[0] == '/':
                bookmark = bookmark[1:]
                possible_urls = []
                for url, *aliases in self.bookmarks:
                    if bookmark in aliases:
                        possible_urls.append(url)
                if not possible_urls:
                    print("No bookmarks with that name")
                    return
                elif len(possible_urls) == 1:
                    return possible_urls[0]
                else:
                    print('Multiple bookmarks with that name, did you mean:')
                    for i, possible_url in enumerate(possible_urls):
                        print(' %d. %s' % (i + 1, possible_url))
                    while True:
                        i = input('? ')
                        if not i.isnumeric():
                            print('Integer please')
                            continue
                        i = int(i) - 1
                        if i < 0 or i >= len(possible_urls):
                            print('In range, please')
                            continue
                        return possible_urls[i]
            elif bookmark.isnumeric():
                bookmark = int(bookmark) - 1
                if bookmark >= len(self.bookmarks):
                    print("you only have %d bookmarks" % len(self.bookmarks))
                    return
                return self.bookmarks[bookmark][0]
            else:
                return
        elif ':' in response or '/' in response or response == '..':
            return response


    def show_page(self, url):
        w=None
        iterator=None
        with self.opener.open(url) as f:
            if f.headers.get_content_maintype() == 'text':
                w = io.TextIOWrapper(f, f.headers.get_content_charset('utf8'))
                if f.headers.get_content_subtype() == 'gemini':
                    iterator = render_gemini(w)
                elif f.headers.get_content_subtype() == 'gopher':
                    iterator = render_gopher(w)
                elif f.headers.get_content_subtype() == 'html':
                    print("NOT RENDERING HTML YET")
                    iterator = []
                else:
                    iterator = ((line.rstrip(),) for line in w)
            elif f.headers.get_content_maintype() == 'audio':
                import subprocess
                proc = subprocess.Popen(['ffmpeg', '-i', '-', '-f', 'pulse', urllib.parse.urlparse(url).path],
                                        stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
                try:
                    download(f, proc.stdin)
                except KeyboardInterrupt:
                    proc.kill()
                proc.stdin.close()
                proc.wait()
                iterator = None
            elif f.headers.get_content_type() == 'application/zip':
                import tempfile, zipfile
                with tempfile.TemporaryFile() as fout:
                    download(f, fout)
                    with zipfile.ZipFile(fout) as zf:
                        zf.extractall('.')
                iterator = None
            else:
                # just treat everything that isn't text as an octet-stream
                w = None
                print(f.headers.get_content_type())
                with open(posixpath.basename(urllib.parse.urlparse(url).path), 'wb') as fout:
                    download(f, fout)
                    print()
                iterator = None
            if iterator is not None:
                if self.config['DEFAULT'].getboolean('unwrap'):
                    iterator = unwrap(iterator)
                new_links = render(iterator)
                self.history.append(f.geturl())
                if new_links:
                    self.links = new_links
            if w:
                w.close()

    def add_bookmark(self, url, alias=None):
        for i, (test_url, *aliases) in enumerate(self.bookmarks):
            if test_url == url:
                if alias and alias not in aliases:
                    self.bookmarks[i].append(alias)
                return i
        if alias:
            self.bookmarks.append([url, alias])
        else:
            self.bookmarks.append([url])
        return len(self.bookmarks)-1

    def save_bookmarks(self):
        bookmarks_path = os.path.expanduser(self.config['DEFAULT']['bookmarks_location'])
        os.makedirs(os.path.dirname(bookmarks_path), exist_ok=True)
        with open(bookmarks_path, 'w') as f:
            csv.writer(f, BookmarksDialect).writerows(self.bookmarks)
        exit()

    def bookmark_manager(self):
        while True:
            for i, (url, *aliases) in enumerate(self.bookmarks):
                print('[{}] {}'.format(i, url) + (' {}'.format(', '.join(aliases)) if aliases else ''))



def render(iterator):
    new_links = []
    gray = False
    for t in iterator:
        text = t[0]
        if len(t) == 1:
            target = None
        elif len(t) == 2:
            target = t[1]
            gray = False
        else:
            print('asdfasfeavduibiaetfuissdfoawe', t)
            continue
        if gray:
            sys.stdout.write('\x1b[48;5;237m')
        if text.strip():  # don't toggle on blank lines.
            gray = not gray  # alternate lines to make it easier to read.
        if target:
            new_links.append(target)
            # XXX this might throw off word wrap.
            sys.stdout.write('\x1b[94m[%d]\x1b[99m ' % len(new_links))
        for output_line in textwrap.wrap(text, 155):
            print(output_line)
        sys.stdout.write('\x1b[0m')
    return new_links


def render_gemini(gemini_doc):
    for line in gemini_doc:
        s_line = line.strip()
        if s_line.startswith('=>'):
            split = s_line[2:].strip().split(None, 1)
            if len(split) == 2:
                target = split[0]
                link_text = split[1]
            elif len(split) == 1:
                link_text = target = split[0]
            else:  # there is no link -- torture test #32 and #33
                yield '\x1b[31m[MALFORMED HYPERLINK]',
                continue
            yield link_text, target
            # print(line)
        elif s_line.startswith('#'):
            # header
            # this renders all headers identically.
            # TODO treat different header levels differently, maybe with different colors?
            yield '\x1b[4m'+s_line.lstrip('#').strip(),
        else:
            yield line,


class GopherDialect(csv.Dialect):
    delimiter = '\t'
    quoting = csv.QUOTE_NONE
    escapechar = None
    lineterminator = '\r\n'


GOPHER_TYPES = {'0': 'text/plain',
                '1': 'text/gopher',
                '2': 'ccso:',
                '3': 'text/plain',
                '4': 'application/binhex',
                '5': 'application/octet-stream',  # 5 corresponds to a DOS file, whatever that means
                '6': 'text/x-uuencode',
                # can't get a straight answer from the internet on what the correct mime type should be.
                '7': 'text/gopher',  # Full text search, however that works
                '8': 'telnet:',
                '9': 'application/octet-stream',
                # + for  a mirror server, handled explicitly in the below code.
                'g': 'image/gif',
                'i': 'image',
                'T': 'telnet:',
                'd': 'application/msword',
                's': 'application/x-wav',
                }


def render_gopher(w):
    links = []
    for row in csv.reader(w, GopherDialect):
        if row == ['.']:
            return
        if len(row) != 4:
            print("GOPHER FORMAT ERRROR")
            print(row)
            continue
        name, path, host, port = row
        link_type = name[0]
        name = name[1:]
        if link_type == '3':
            raise urllib.error.URLError(name)
        if link_type == 'i':  # informational message.  Link goes nowhere.
            yield name,
            continue
        elif link_type == 'h' and path.startswith('URL:'):
            yield name, path[4:]
        else:
            parsed = ['gopher', '%s:%s' % (host, port), path, '', '', '']
            mimetype = GOPHER_TYPES.get(link_type)
            if mimetype is None:
                # give up
                yield '\x1b[91,40mUnknown link type %s' % link_type,
                continue
            if mimetype[-1] == ':':
                parsed[0] = mimetype[:-1]  # set the URL scheme
            elif not port and host.isnumeric():
                # some malformed gopher sites omit the host parameter and spec a relative url.
                # that's annoying, but we can handle it.
                yield
            else:
                parsed[5] = mimetype  # my urllib gopher implementation will take the fragment as a mimetype.

            yield name, urllib.parse.urlunparse(parsed)


def unwordwrap(lines):
    outputline = ''
    for line in lines:
        line = line.rstrip()
        if not line:
            yield outputline,
            outputline = ''
        else:
            outputline += line + ' '

def unwrap(iterator):
    line = ''
    for thing in iterator:
        if len(thing) != 1:
            if line:
                yield line,
                line = ''
            yield thing
        else:
            thing = thing[0]
            if thing:
                line += thing.strip() + ' '
            else:
                yield line,
                line=''


if __name__ == '__main__':
    Tinysurf().main()
