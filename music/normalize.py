#!/usr/bin/env python3
# -*- coding: UTF-8 -*-

import os, re
from unicodedata import normalize
from mutagen.easyid3 import EasyID3
from mutagen.oggvorbis import OggVorbis
from mutagen.mp4 import MP4

FORMAT_SINGLE = '{0:02} {1}{2}'
FORMAT_MULTI = '{0}-{1:02} {2}{3}'
FORMAT_NOTRACK = '{0}{1}'
FORBIDDEN_CHARS = dict.fromkeys(map(ord, '/\\?%:*"!|><+\x00'), None)
#FORBIDDEN_CHARS = '/\\?%:*"!|><+\x00'
STRIPSPACES = re.compile(r'\s{2,}')

def rename_songs():
    files = os.listdir('.')
    files.sort()
    for filename in files:
        (sn, ext) = os.path.splitext(filename)
        dirty = False

        if ext.lower() == '.ogg':
            meta = OggVorbis(filename)
        elif ext.lower() == '.mp3':
            meta = EasyID3(filename)
        elif ext.lower() in ('.mp4', '.m4a'):
            meta = MP4(filename)

            if '----:com.apple.iTunes:iTunNORM' in meta:
                del meta['----:com.apple.iTunes:iTunNORM']
                dirty = True
            if '----:com.apple.iTunes:iTunSMPB' in meta:
                del meta['----:com.apple.iTunes:iTunSMPB']
                dirty = True

            if dirty:
                meta.save()

            if 'disk' in meta:
                newfilename = (FORMAT_MULTI.format(meta['disk'][0][0],
                    meta['trkn'][0][0], meta['\xa9nam'][0], ext))
            else:
                newfilename = (FORMAT_SINGLE.format(meta['trkn'][0][0],
                    meta['\xa9nam'][0], ext))
            newfilename = newfilename.translate(None, FORBIDDEN_CHARS)
            newfilename = STRIPSPACES.sub(' ', newfilename)
            
            if not os.path.exists(newfilename):
                print('{0} -> {1}'.format(filename, newfilename))
                os.rename(filename, newfilename)
            continue
        else:
            if filename not in ('.', '..') and os.path.isdir(filename):
                os.chdir(filename)
                rename_songs()
                os.chdir('..')
                uf = filename
                newfilename = normalize('NFC', uf)
                if not os.path.exists(newfilename):
                    print('{0} -> {1}'.format(filename, newfilename))
                    os.rename(filename, newfilename)
            continue

        if 'discnumber' in meta and len(meta['discnumber'][0]) > 1:
            olddn = meta['discnumber'][0]
            newdn = meta['discnumber'][0][0]
            meta['discnumber'] = newdn
            print('{0} shortened to {1}'.format(olddn, newdn))
            dirty = True
        if 'tracknumber' in meta and not meta['tracknumber'][0].find('/') == -1:
            oldtn = meta['tracknumber'][0]
            newtn = meta['tracknumber'][0][:meta['tracknumber'][0].find('/')]
            meta['tracknumber'] = newtn
            print('{0} shortened to {1}'.format(oldtn, newtn))
            dirty = True
        if dirty:
            meta.save()

        if 'discnumber' in meta:
            newfilename = (FORMAT_MULTI.format(int(meta['discnumber'][0]), 
                    int(meta['tracknumber'][0]), meta['title'][0], ext.lower()))
        elif 'tracknumber' in meta:
            newfilename = (FORMAT_SINGLE.format(int(meta['tracknumber'][0]), 
                    meta['title'][0], ext.lower()))
        else:
            try:
                newfilename = (FORMAT_NOTRACK.format(meta['title'][0], ext.lower()))
            except KeyError:
                print('defective file: {0}'.format(filename))
        #newfilename = newfilename.translate(None, FORBIDDEN_CHARS)
        newfilename = newfilename.translate(FORBIDDEN_CHARS)
        newfilename = STRIPSPACES.sub(' ', newfilename)
        
        if not os.path.exists(newfilename):
            print('{0} -> {1}'.format(filename, newfilename))
            os.rename(filename, newfilename)

if __name__ == '__main__':
    rename_songs()
