#!/usr/bin/python

import urllib2
import gzip
import httplib
from urlparse import urlparse
import math
import re
import sys
import pprint
from StringIO import StringIO

from sequencestore import SequenceStore

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
    """Find the size of the resource at a given url
    """
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

def _url_list_to_dict(urls):
    result = {}
    for url in urls:
        result[url] = external_size(url)
    return result

# Some functions for encoding data for google charts
SIMPLE = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
def _simple_encode(values, maximum = 62):
    encoded = []
    for value in values:
        scaled = int(len(SIMPLE) * float(value) / maximum)
        encoded.append(SIMPLE[scaled])
    return ''.join(encoded)
EXTENDED = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-.'
def _extended_encode(values, maximum = 4095):
    encoded = []
    ext_max = (len(EXTENDED) ** 2)
    for value in values:
        scaled = math.floor(ext_max * float(value) / maximum)
        if scaled > ext_max - 1:
            encoded.append('..')
        elif scaled < 0:
            encoded.append('__')
        else:
            quotient = int(math.floor(scaled / len(EXTENDED)))
            remainder = int(scaled - len(EXTENDED) * quotient)
            encoded.append(EXTENDED[quotient])
            encoded.append(EXTENDED[remainder])
    return ''.join(encoded)

def fetch_data_for_url(url):
    """Find out filesizes for external CSS/JS on a given url
    """
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
    
    return {
        'head_scripts':_url_list_to_dict(head_scripts),
        'head_links':_url_list_to_dict(head_links),
        'body_scripts':_url_list_to_dict(body_scripts),
        'body_links':_url_list_to_dict(body_links),
        'blocking_js':blocking_js,
        'blocking_css':blocking_css,
        'nonblocking_js':nonblocking_js,
        'nonblocking_css':nonblocking_css,
    }

def _splitvalues(x):
    return [int(v) for v in x.split('|')]

if __name__ == '__main__':
    store = SequenceStore('data.sqlite')
    
    urls = [
        'http://www.deviantart.com',
        'http://kemayo.deviantart.com/art/Delicious-baby-131363146',
        ]
    
    action = 'fetch'
    if len(sys.argv) > 1:
        action = sys.argv[1]
    
    if action == 'store':
        for url in urls:
            data = fetch_data_for_url(url)
            
            print url
            print " blocking js:", "%.02f" % (data['blocking_js'] / 1024.0), 'kB'
            print " blocking css:", "%.02f" % (data['blocking_css'] / 1024.0), 'kB'
            print " nonblocking js:", "%.02f" % (data['nonblocking_js'] / 1024.0), 'kB'
            print " nonblocking css:", "%.02f" % (data['nonblocking_css'] / 1024.0), 'kB'
            
            store.add(url, '%d|%d|%d|%d' % (data['blocking_js'], data['blocking_css'], data['nonblocking_js'], data['nonblocking_css']))
    elif action == 'fetch':
        pp = pprint.PrettyPrinter(indent=4)
        for url in urls:
            data = fetch_data_for_url(url)
            print url
            pp.pprint(data)
            print ''
    elif action == 'graph':
        for url in urls:
            data = store.get(url, value_function = _splitvalues, order = "ASC")
            y_max = 0
            sequences = {
                'blocking js': [],
                'blocking css': [],
                'nonblocking js': [],
                'nonblocking css': [],
            }
            labels = []
            for date, values in data:
                y_max = max(y_max, sum(values))
                sequences['blocking js'].append(values[0])
                sequences['blocking css'].append(values[1])
                sequences['nonblocking js'].append(values[2])
                sequences['nonblocking css'].append(values[3])
                labels.append(str(date))
            
            chart_url = [
                'http://chart.apis.google.com/chart?cht=bvs&chco=FFA401,ef0491,679EC5,578EB5&chs=500x500&',
                'chxt=x,y&chxr=1,0,', str(int(y_max / 1024.0)), '&',
                'chxl=0:|', '|'.join(labels), '&',
                'chd=e:',
                _extended_encode(sequences['blocking js'], y_max), ',',
                _extended_encode(sequences['blocking css'], y_max), ',',
                _extended_encode(sequences['nonblocking js'], y_max), ',',
                _extended_encode(sequences['nonblocking css'], y_max),
            ]
            
            print url
            print 'Chart: ', ''.join(chart_url)
