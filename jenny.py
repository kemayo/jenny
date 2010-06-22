#!/usr/bin/python

import urllib2
import gzip
import httplib
from urlparse import urlparse
import re
from StringIO import StringIO

__author__ = 'David Lynch (kemayo at gmail dot com)'
__version__ = '0.1'
__copyright__ = 'Copyright (c) 2009 David Lynch'
__license__ = 'New BSD License'

USER_AGENT = 'jenny/%s +http://github.com/kemayo/jenny/tree/master' % __version__

CACHE = {}
SIZECACHE = {}

def _fetch(url, cached = True, ungzip = True):
    """A generic URL-fetcher, which handles gzipped content, returns a string"""
    if cached and url in CACHE:
        return CACHE[url]
    request = urllib2.Request(url)
    request.add_header('Accept-encoding', 'gzip')
    request.add_header('User-agent', USER_AGENT)
    f = urllib2.urlopen(request)
    data = f.read()
    if ungzip and f.headers.get('content-encoding', '') == 'gzip':
        data = gzip.GzipFile(fileobj=StringIO(data)).read()
    f.close()
    CACHE[url] = data
    return data

def find_externals(html):
    scripts = re.findall(r'<script[^>]+src="([^"]+)"[^>]*>', html)
    links_raw = re.findall(r'<link[^>]+rel="stylesheet"[^>]*', html)
    links = []
    for link in links_raw:
        m = re.search(r'href="([^"]+)"', link)
        if m:
            links.append(m.group(1))
    return scripts, links

def external_size(url):
    if url in SIZECACHE:
        return SIZECACHE[url]
    o = urlparse(url, 'http')
    if not o.scheme in ('http', 'https'):
        return False
    
    # I'm doing a lot of checking of gzipped size. Apache reports content-length for the
    # non-gzipped data even when it's sending gzipped. So that's useless, isn't it?
    # Otherwise I could do this:
    #conn = httplib.HTTPConnection(o.netloc)
    #conn.request('HEAD', "%s%s%s" % (o.path, o.params and ';'+o.params, o.query and '?'+o.query))
    #response = conn.getresponse()
    #length = int(response.getheader('content-length', '0'))
    #conn.close()
    data = _fetch(url, True, False)
    length = len(data)
    
    SIZECACHE[url] = length
    return SIZECACHE[url]

def _urlsizereducer(urls):
    total = 0
    for url in urls:
        size = external_size(url)
        total = total + size
    return total

if __name__ == '__main__':
    url = 'http://www.deviantart.com'
    
    page = _fetch(url)
    sections = page.split('<body')
    
    assert len(sections) == 2
    
    head = sections[0]
    body = sections[1]
    
    head_scripts, head_links = find_externals(head)
    body_scripts, body_links = find_externals(body)
    
    blocking_js = _urlsizereducer(head_scripts)
    blocking_css = _urlsizereducer(head_links)
    nonblocking_js = _urlsizereducer(body_scripts)
    nonblocking_css = _urlsizereducer(body_links) #should really be nonexistant
    
    print url
    print "blocking js", blocking_js / 1024.0, 'kB'
    print "blocking css", blocking_css / 1024.0, 'kB'
    print "nonblocking js", nonblocking_js / 1024.0, 'kB'
    print "nonblocking css", nonblocking_css / 1024.0, 'kB'
    
    x_max = blocking_js + blocking_css + nonblocking_js + nonblocking_css
    
    chart_url = [
        'http://chart.apis.google.com/chart?cht=bvs&chco=FFA401,FFA401,679EC5,679EC5&chs=500x500&',
        # 'chds=0,', str(x_max), '&',
        'chxt=y&chxr=0,0,', str(x_max / 1024.0), '10&',
        'chd=t:',
        str(100 * blocking_js / x_max), '|',
        str(100 * blocking_css / x_max), '|',
        str(100 * nonblocking_js / x_max), '|',
        str(100 * nonblocking_css / x_max)
    ]
    
    print "Google chart:", ''.join(chart_url)
