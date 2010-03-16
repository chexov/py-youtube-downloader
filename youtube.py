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

FMT_MAP = {
 5: '320x240 H.263/MP3 mono FLV',
 6: '320x240 H.263/MP3 mono FLV',
13: '176x144 3GP/AMR mono 3GP',
17: '176x144 3GP/AAC mono 3GP',

34: '320x240 H.264/AAC stereo FLV',
35: '640x480 640x360 H.264/AAC stereo FLV',

18: '480x360 480x270 H.264/AAC stereo MP4',
22: '1280x720 H.264/AAC stereo MP4',

37: '1920x1080 H.264/AAC stereo MP4',
}

FMT_MAP_PRIORITY = [37, 22, 18, 35, 34, 17, 13, 6, 5] # The coolest format is first




logging.basicConfig()
LOG = logging.getLogger("youtube.downloader")
LOG.setLevel(logging.DEBUG)

def _reporthook(numblocks, blocksize, filesize, url=None):
    base = os.path.basename(url)
    #XXX Should handle possible filesize=-1.
    try:
        percent = min((numblocks*blocksize*100)/filesize, 100)
    except:
        percent = 100
    if numblocks != 0:
        print "\r%66s %3d%%" % (base, percent) ,

def geturl(url, dst):
    LOG.debug("Video URL is '%s'" % (url) )
    LOG.info("Saving video to '%s'" % (dst) )
    if sys.stdout.isatty():
        return urllib.urlretrieve(url, dst, lambda nb, bs, fs, url=url: _reporthook(nb,bs,fs,dst))
    else:
        return urllib.urlretrieve(url, dst)

def downloadFileByUrl(url, filename=None):
    # Check if URL exists
    try:
        f = urllib2.urlopen(url)
    except urllib2.HTTPError, e:
        raise NoSuchVideo(unicode(e))

    if filename:
        # If filename is specified, download using urllib.urlretrieve
        geturl(url, filename)
        return True
    else:
        # If no filename, return data
        data = f.read()
        f.close()
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

        # Building dict() from attrs list(). It's easier to deal with dict() later...
        _attrs_dict = {}
        for attr in attrs:
            key, value = attr
            _attrs_dict[key] = value

        if _attrs_dict.get('id') and _attrs_dict.get('id').find('video-long-title') > -1:
            # We need only HREFs with 'id' == 'video-long-title.*'
            vid = self.__extract_video_id_from_uri(_attrs_dict['href'])
            self.PLAYLIST_ITEMS.append(vid)
            LOG.info("Found video id %s for %s" % (vid, _attrs_dict.get('title')) )



YOUTUBE_WATCH_URL = "http://www.youtube.com/watch?v=%(video_id)s"
YOUTUBE_GETVIDEO_URL = "http://www.youtube.com/get_video.php?video_id=%(video_id)s&fmt=%(formatcode)s&t=%(token)s"

class NoSuchVideo(Exception):
    pass

class Youtube(object):
    '''Youtube class is created to download video from youtube.com.
    '''

    def __init__(self, video_id):
        self.video_id = video_id
        self._pagesrc_cache = None

    @property
    def pagesrc(self):
        """Returns source of video page, caching it
        """
        if self._pagesrc_cache is None:
            url = YOUTUBE_WATCH_URL % {'video_id': self.video_id}
            self._pagesrc_cache = urllib2.urlopen(url).read()

        return self._pagesrc_cache

    def pageToken(self):
        """
        Extracts session token from the page.
        Session token needed for video download URL
        """
        match = re.search(r', "t": "([^&"]+)"', self.pagesrc)
        if match:
            return match.group(1)
        else:
            raise ValueError("Can't extract token from HTML page. Invalid URL or Youtube changed layout. Please, contact the author of this script")

    def title(self):
        """Returns page title (if not found, uses the video ID as title)
        """
        reg = re.compile(r"<title>(.+)</title>", re.DOTALL)
        match = reg.search(self.pagesrc)
        if match:
            title = match.group(1).decode('utf-8')
            
            # Remove newlines and "YouTube - " from the title
            title = title.replace("\n", "")
            title = re.sub("YouTube.+?- ", "", title)
            title = title.strip()
            
            return title
        else:
            return self.video_id
    
    def videoUrl(self, formatcode):
        """Returns the URL for the video in the specified format
        """
        if formatcode is not None and formatcode not in FMT_MAP.keys():
            raise ValueError("Unknown format code %s" % formatcode)
        
        token = self.pageToken()
        videourl = YOUTUBE_GETVIDEO_URL % {"video_id": self.video_id, "formatcode":formatcode, "token": token}
        return videourl


def download(video_id, outFilePath, formatcode = None):
    """Downloads the specified video id to the specified path
    """
    if formatcode is not None:
        LOG.debug("Getting video URL for video (%s, format: %s)" % (video_id, FMT_MAP.get(formatcode)))
        totry = [formatcode]
    else:
        # Try all formats, in reverse order
        LOG.debug("Getting video URL for video (%s, format: largest)" % video_id)
        totry = FMT_MAP_PRIORITY
    
    video = Youtube(video_id)
    for curcode in totry:
        url = video.videoUrl(curcode)
        try:
            LOG.info("Trying %s format (%s)" % (FMT_MAP.get(curcode), curcode) )
            return downloadFileByUrl(url, outFilePath)
        except NoSuchVideo, e:
            LOG.info("Formatcode %s did not exist" % curcode)
    else:
        raise NoSuchVideo("Tried following formatcodes: %s. Non existed" % ", ".join(str(x) for x in totry))


def run(self, outFilePath=None, formatcode=None):
    """
    GET youtube video ID 'youtube_id'
    RETURNS True is file properly downloaded and saved to local disk
            False in case of error
    """
    url = "http://www.youtube.com/watch?v=%s" % youtube_id
    htmlpage = None
    if not outFilePath:
        htmlpage = urllib2.urlopen(url).read()
        title = Youtube.retrieveYoutubePageTitle(youtube_id, htmlpage, clean=True)
        outFolder = os.getcwd()
        outFilePath = os.path.join(os.getcwd(), title + '.mp4')
    
    outFilePath_tmp = outFilePath + ".part"
    data = None
    finished = False
    
    if formatcode not in FMT_MAP.keys():
        finished = Youtube.downloadYoutubeVideo(youtube_id, '22', outFilePath_tmp)
        if not finished:
            finished = Youtube.downloadYoutubeVideo(youtube_id, '18', outFilePath_tmp)
    else:
        finished = Youtube.downloadYoutubeVideo(youtube_id, formatcode, outFilePath_tmp)
    
    # if file exists locally, do not download FLV again.
    if os.path.isfile(outFilePath):
        LOG.warning("We already have %s. Not retrieving" % (outFilePath))
        finished = True
        return finished
    
    if finished:
        os.rename(outFilePath_tmp, outFilePath)
    else:
        try:
            os.remove(outFilePath_tmp)
        except OSError:
            pass
    return finished


def get_playlist_video_ids(playlist_id, html=None):
    """
    GET playlist_id
    RETURNS list() of Youtube instances for each video

    Explanation:
      for the URL http://www.youtube.com/view_play_list?p=8EE54070B382E73A
      'playlist_id' should be '8EE54070B382E73A'
    """
    playlist_url = "http://www.youtube.com/view_play_list?p=%s" % playlist_id

    if not html:
        LOG.info('Downloading playlist %s from "%s"' % (playlist_id, playlist_url))
        html = urllib2.urlopen(playlist_url).read()
    ypp = YoutubePlaylistHTMLParser()
    ypp.feed(html)
    return ypp.PLAYLIST_ITEMS



if __name__ == "__main__":
    LOG.setLevel(logging.DEBUG)
    formats = ""
    for k,v in FMT_MAP.items():
        formats = "%s %s -- %s\n" % (formats, k,v)
    
    usage = "usage: %prog <youtube-video-id> [youtube-video-id,..]\n" + \
            "%prog -p <playlist id>\n\nKnown video format codes:\n" + formats
    parser = optparse.OptionParser(usage=usage)
    parser.add_option("-o", "--outfile", dest="outfilepath",
            help="Override default output file name. Works for ", default=None)
    parser.add_option("-p", "--playlist", dest="playlist",
            help="Download all playlist's videos into the current directory", default=None)
    parser.add_option("-f", "--formatcode", dest="formatcode", default=None, type="int",
            help="Download video of the specific format")
    
    (options, args) = parser.parse_args()
    
    if options.formatcode and options.formatcode not in FMT_MAP:
        LOG.critical("Unknown code format %s. Please, check videoformats codes" % options.formatcode)
        sys.exit(1)
    
    try:
        if options.playlist:
            for vID in get_playlist_video_ids(options.playlist):
                download(vID, outFilePath=None, formatcode=options.formatcode)
        elif len(args) > 0:
            for vID in args:
                download(vID, outFilePath=None, formatcode=options.formatcode)
        else:
            parser.print_help()
    except KeyboardInterrupt:
        print "\nThank you for flying with youtube.py. Bye-bye."
        sys.exit(1)

