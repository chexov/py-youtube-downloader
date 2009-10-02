#!/usr/bin/env python
# encoding: utf-8

import optparse
import logging
import urllib2
import urllib
import sys
import os
import re
from HTMLParser import HTMLParser

logging.basicConfig()
LOG = logging.getLogger("youtube.downloader")
LOG.setLevel(logging.DEBUG)

def _reporthook(numblocks, blocksize, filesize, url=None):
    #print "reporthook(%s, %s, %s)" % (numblocks, blocksize, filesize)
    base = os.path.basename(url)
    #base = "Progress "
    #XXX Should handle possible filesize=-1.
    try:
        percent = min((numblocks*blocksize*100)/filesize, 100)
    except:
        percent = 100
    if numblocks != 0:
        sys.stdout.write("\b"*80)
        sys.stdout.write("%-66s %3d%%" % (base, percent))


def geturl(url, dst):
    LOG.info("Downloading url '%s' to '%s'" % (url, dst) )
    if sys.stdout.isatty():
        return urllib.urlretrieve(url, dst, lambda nb, bs, fs, url=url: _reporthook(nb,bs,fs,dst))
        #sys.stdout.write('\n')
    else:
        return urllib.urlretrieve(url, dst)

def downloadFileByUrl(url, filename=None):
   data = None
   try:
       f = urllib2.urlopen(url)
       if filename:
           return geturl(url, filename)
       else:
           data = f.read()
           f.close()
   except IOError, e:
       return None
   except urllib2.HTTPError, e:
       LOG.critical("Can't process with download: %s" % e)
       return None
   finally:
       return data



class YoutubePlaylistHTMLParser(HTMLParser):
    """HTMLParser class which extract youtube video IDs
       from HTML page
    """
    PLAYLIST_ITEMS = list()
    
    def __extract_video_id_from_uri(self, uri):
        """
        GET uri like '/watch?v=AsXf9v&param=1&p=3#junk'
        RETURNS value for 'v' parameter --> 'AsXf9v'
        """
        uri = uri.replace('&', ';')
        uri = uri.replace('?', ';')
        req, params = urllib.splitattr(uri)
        for item in params:
            k, v = urllib.splitvalue(params[0])
            if k == 'v':
                return v
        raise ValueError("Can't find parameter 'v' from '%s'" % uri)
    
    def handle_starttag(self, tag, attrs):
        if not tag == 'a':
            return 1
        
        # Building dict() from attrs list(). It's easy to dealing with dict() later...
        _attrs_dict = {}
        for attr in attrs:
            key, value = attr
            _attrs_dict[key] = value
        
        if _attrs_dict.get('id') and _attrs_dict.get('id').find('video-long-title') > -1:
            # We need only HREFs with 'id' == 'video-long-title.*'
            vid = self.__extract_video_id_from_uri(_attrs_dict['href'])
            self.PLAYLIST_ITEMS.append(vid)
            LOG.info("Found video id %s for %s" % (vid, _attrs_dict.get('title')) )


class Youtube(object):
    '''Youtube class is created to download video from youtube.com.
    '''
    @staticmethod
    def retriveYoutubePageToken(ID, htmlpage=None):
        """
        Magick method witch extract session token from 'htmlpage'.
        Session token needed for video download URL
        """
        if not htmlpage:
            url = "http://www.youtube.com/watch?v=%s" % ID
            #htmlpage="var fullscreenUrl = '/watch_fullscreen?fs=1&fexp=900142%2C900030%2C900162&iv_storage_server=http%3A%2F%2Fwww.google.com%2Freviews%2Fy%2F&creator=amiablewalker&sourceid=r&video_id=VJyTA4VlZus&l=353&sk=QtBR18Y95jsDyLXHgv9jbMu0ghb3MxoSU&fmt_map=34%2F0%2F9%2F0%2F115%2C5%2F0%2F7%2F0%2F0&t=vjVQa1PpcFPt0HhU0HkTG6A75-QxhAiV6WuMqB2a4r4%3D&hl=en&plid=AARnlkLz-d6cbsVe&vq=None&iv_module=http%3A%2F%2Fs.ytimg.com%2Fyt%2Fswf%2Fiv_module-vfl89178.swf&cr=US&sdetail=p%253Afriendfeed.com%2Feril&title=How To Learn Any Accent Part 1';"
            htmlpage = urllib2.urlopen(url).read()
        match = re.search(r', "t": "([^&"]+)"', htmlpage)
        if match:
            token = match.group(1)
        else:
            raise ValueError("Can't extract token from HTML page. Youtube changed layout. Please, contact to the author of this script")
        return token
    
    @staticmethod
    def retriveYoutubePageTitle(ID, htmlpage=None, clean=False):
        title = ID
        if not htmlpage:
            url = "http://www.youtube.com/watch?v=%s" % ID
            htmlpage = urllib2.urlopen(url).read()
        match = re.search(r"<title>(.+)</title>", htmlpage)
        if match:
            title = match.group(1)
            if clean:
                title = re.sub("[^a-z.0-9A-Z:-]", "_", title.strip().lower())
        return title
    
    @staticmethod
    def getHDVideourlByID(ID):
        videourl = None
        token = Youtube.retriveYoutubePageToken(ID)
        if token:
            videourl = "http://www.youtube.com/get_video.php?video_id=%s&fmt=22&t=%s" % (ID, token)
        return videourl

    @staticmethod
    def getHQVideourlByID(ID):
        videourl = None
        token = Youtube.retriveYoutubePageToken(ID)
        if token:
            videourl = "http://www.youtube.com/get_video.php?video_id=%s&fmt=18&t=%s" % (ID, token)
        return videourl
        
    @staticmethod
    def run(youtube_id, outFilePath=None):
        """
        GET youtube video ID 'youtube_id'
        RETURNS True is file properly downloaded and saved to local disk
                False in case of error
        """
        url = "http://www.youtube.com/watch?v=%s" % youtube_id
        htmlpage = None
        if not outFilePath:
            htmlpage = urllib2.urlopen(url).read()
            title = Youtube.retriveYoutubePageTitle(youtube_id, htmlpage, clean=True)
            outFolder = os.getcwd()
            outFilePath = os.path.join(os.getcwd(), title + '.mp4')
        
        outFilePath_tmp = outFilePath + ".part"
        data = None
        finished = False
        
        # if file exist on local node, do not download FLV one more.
        if os.path.isfile(outFilePath):
            LOG.warning("We already have %s. Not retrieving" % (outFilePath))
            finished = True
            return finished
        
        LOG.debug("Trying to get HD video")
        url = Youtube.getHDVideourlByID(youtube_id)
        if not url:
            LOG.debug("Can't get HD video url")
        else:
            #LOG.debug("Downloading %s -> %s" % (url, outFilePath))
            if not downloadFileByUrl(url, outFilePath_tmp):
                LOG.debug("HD Video not found '%s'" % url)
        
        LOG.debug("Trying to get HQ video")
        url = Youtube.getHQVideourlByID(youtube_id)
        if not url:
            LOG.debug("Can't get HQ video url")
        else:
            #LOG.debug("Downloading %s -> %s" % (url, outFilePath))
            if not downloadFileByUrl(url, outFilePath_tmp):
                LOG.debug("HQ video not found '%s'" % url)
        
        if finished:
            os.rename(outFilePath_tmp, outFilePath)
        else:
            os.remove(outFilePath_tmp)
        return finished
    
    
    @staticmethod
    def get_playlist_video_ids(playlist_id, html=None):
        """
        GET playlist_id
        RETURNS list() of all video ids from that playlist
        
        Explanation:
          for the URL http://www.youtube.com/view_play_list?p=8EE54070B382E73A
          'playlist_id' shold be '8EE54070B382E73A'
        """
        playlist_url = "http://www.youtube.com/view_play_list?p=%s" % playlist_id
        
        if not html:
            LOG.info('Downloading playlist %s from "%s"' % (playlist_id, playlist_url))
            html = urllib2.urlopen(playlist_url).read()
            #html = open('youtube.playlist.example.html').read()
        ypp = YoutubePlaylistHTMLParser()
        ypp.feed(html)
        return ypp.PLAYLIST_ITEMS



if __name__ == "__main__":
    LOG.setLevel(logging.DEBUG)
    usage = "usage: %prog <youtube-video-id> [youtube-video-id,..]\n       %prog -p <playlist id>"
    parser = optparse.OptionParser(usage=usage)
    parser.add_option("-p", "--playlist", dest="playlist",
            help="Download all playlist videos to the current directory", default=None)
    
    (options, args) = parser.parse_args()
    try:
        if options.playlist:
            for vID in Youtube.get_playlist_video_ids(options.playlist):
                Youtube.run(vID)
        elif len(args) > 0:
            for vID in args:
                Youtube.run(vID)
        else:
            parser.print_help()
    except KeyboardInterrupt:
        print "\nThank you for flying with youtube.py. Bye-bye."
        sys.exit(1)
    
