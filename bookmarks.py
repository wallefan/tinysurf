import csv


class BookmarksDialect(csv.Dialect):
    delimiter = '\t'
    quoting = csv.QUOTE_NONE
    escapechar = None
    lineterminator = '\n'


def load_bookmarks(f):
    d = {}
    # Each alias can be mapped to more than one site, so we must map each alias to a list of sites
    # rather than a single site.
    with open(f, 'r') as f:
        for site, *aliases in csv.reader(f, BookmarksDialect):
            for alias in aliases:
                d.setdefault(alias, []).append(site)
    return d


def save_bookmarks(d, f):
    output_d = {}
    for alias, sites in d.items():
        for site in sites:
            output_d.setdefault(site, []).append(alias)
    with open(f, 'w') as f:
        csv.writer(f, BookmarksDialect).writerows((k, *v) for k, v in output_d.items())