#!/usr/bin/env python3

import os
import re
import ssl
import sys
import json
import time
import shutil
import urllib
import mutagen
import argparse
import requests
import platform
import tempfile
import subprocess
from mutagen.mp3 import EasyMP3
from mutagen.easyid3 import EasyID3
from mutagen.mp4 import MP4, MP4Cover
from pathlib import Path, PureWindowsPath
from mutagen.id3 import ID3, APIC, TIT2, TALB, TPE1, TPE2, COMM, USLT, TCOM, TCON, TDRC

'''
We have to use the client_id of another app as Soundcloud is no longer
taking requests for new user applications and therefore doesn't allow
us to create a new one that is made specifically for this program.
Instead, we have no other choice (if we don't want to keep updating the app
constantly) other than to use the client_id youtube-dl has embedded in
its source code. Can't believe I didn't think of this sooner (which is why it
kept breaking so freaking often).
'''

clientId = "iZIs9mchVcX5lhVRyQGGAYlNPVldzAoX"
appVersion = "1575626913"
lastTrackIndexFilePath = "last_track_index.txt"
lastTrackIndex = 0
ssl._create_default_https_context = ssl._create_unverified_context
if platform.system() == 'Windows':
    pathToCurlWindows = str(Path("./bin/curl.exe").absolute())

premiumFlag = 1
ffmpegPath = "ffmpeg"
metadataFlag = 0
descriptionDisableFlag = 0


def main_archive(soundcloudUrl):
    downloadSingleTrack(soundcloudUrl, "", 1, 0)
    print("Done!")

def linkDetection(soundcloudUrl):
    '''
    detects the type of link, as a fallback for a lack of playlist flag
    return 1 = single track
    return 2 = playlist
    '''
    #Fix a missing https://
    soundcloudUrl = soundcloudUrl.replace("http://", "https://")

    #Fix URL if it is a single track out of a playlist
    if '?in=' in soundcloudUrl:
        soundcloudUrl = soundcloudUrl.split('?in=')
        soundcloudUrl = soundcloudUrl[0]

    #URL is a playlist
    if '/sets' in soundcloudUrl:
        return 2, soundcloudUrl

    #URL for tracks of a user
    userReTracks1 = re.compile(r"^https:\/\/soundcloud.com\/[abcdefghijklmnopqrstuvwxyz\-_1234567890]{1,}$")
    userReTracks2 = re.compile(r"^https:\/\/soundcloud.com\/[abcdefghijklmnopqrstuvwxyz\-_1234567890]{1,25}\/tracks$")

    if (userReTracks1.match(soundcloudUrl)) or (userReTracks2.match(soundcloudUrl)):
        return 3, soundcloudUrl

    #URL for likes of a user
    userReLikes = re.compile(r"^https:\/\/soundcloud.com\/[abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ\-_1234567890]{1,}\/likes$")
    if (userReLikes.match(soundcloudUrl)):
        return 4, soundcloudUrl

    #This is a single track
    else:
        return 1, soundcloudUrl

def downloadSingleTrack(soundcloudUrl, trackTitle, hqFlag, optionalAlbum):
    '''
    If you're downloading a playlist a string containing the playlist
    name will be passed to the function as optionalAlbum, otherwise 
    it is 0 and gets replaced by simple string
    '''
    alreadyDownloaded = False
    
    if optionalAlbum != 0:
        album = optionalAlbum
    else:
        album = "SoundCloud"
    '''
    m4a premium download, only happens when both flags are set
    '''
    if premiumFlag == 1 and hqFlag == 1:
        trackId = getTrackId(soundcloudUrl)
        size = 0
        m4aFailedFlag = 0
        if not os.path.exists(str(trackTitle) + '.m4a') and not os.path.exists(str(repairFilename(trackTitle)) + '.m4a'):
            try:
                downloadPremium(trackId)
                '''
                A failed m4a download results in an empty file
                due to the lack of audio streams, so we can just
                check for the filesize to see if the download was
                successful or not :)
                '''
                size = os.path.getsize(str(trackId) + ".m4a")
                if size != 0:
                    '''
                    Set flag in case the download failed
                    '''
                    m4aFailedFlag = 0
                else:
                    m4aFailedFlag = 1
            except:
            
                '''
                The track is either not publicly available or not
                available as M4A.
                '''
                try:
                    downloadPremiumPrivate(trackId, soundcloudUrl)
                except:
                    m4aFailedFlag = 1
                    try:
                        size = os.path.getsize(str(trackId) + ".m4a")
                    except:
                        size = 0
                        if size != 0:
                            '''
                            Set flag in case the download failed
                            '''
                            m4aFailedFlag = 0
                        else:
                            m4aFailedFlag = 1
        else:
            size = 1
            alreadyDownloaded = True
            print(str(repairFilename(trackTitle)) + " Already Exists")                 

    if premiumFlag == 0 or hqFlag == 0 or size == 0:
        '''
        Takes effect when the download either failed or the premium
        option wasn't chosen, downloads the regular 128kbps file
        '''
        m4aFailedFlag = 1
        trackId = getTrackId(soundcloudUrl)
        if not os.path.exists(str(trackTitle) + '.mp3') and not os.path.exists(str(repairFilename(trackTitle)) + '.mp3'):
            try:
                downloadRegular(trackId, soundcloudUrl)
            except:
                downloadRegularPrivate(trackId, soundcloudUrl)
        else:
            size = 1
            alreadyDownloaded = True
            print(str(repairFilename(trackTitle)) + " Already Exists")      

    '''
    The tagging procedure is similar for both file types, only
    the way the tags are applied is different.
    '''
                
    if not alreadyDownloaded:          
        trackName, artist, coverFlag = getTags(soundcloudUrl)
        if descriptionDisableFlag == 0:
            description = getDescription(soundcloudUrl)
        else:
            description = ""
        
        '''
        File gets renamed differently depending on whether or not it's
        an m4a or mp3, obviously
        '''
        
        if m4aFailedFlag == 1 or hqFlag == 0:
            renameFile(trackId, trackName, 0)
        else:
            renameFile(trackId, trackName, 1)
     
        if premiumFlag ==  1 and hqFlag == 1 and m4aFailedFlag == 0:
            '''
            m4a
            '''
            addTags(trackName, artist, album, coverFlag, description, 1)
        else:
            '''
            mp3
            '''
            addTags(trackName, artist, album, coverFlag, description, 0)

    
    cleanUp(trackId, repairFilename(trackTitle))

def repairFilename(trackName):
    '''
    Filenames are problematic, Windows, Linux and macOS don't
    allow certain characters. This (mess) fixes that. Basically 
    every other character, no matter how obscure, is seemingly
    supported though.
    '''

    if u"/" in trackName:
        trackName = trackName.replace(u"/", u"-")
    if u"\\" in trackName:
        trackName = trackName.replace(u"\\", u"-")
    if u"|" in trackName:
        trackName = trackName.replace(u"|", u"-")
    if u":" in trackName:
        trackName = trackName.replace(u":", u"-")
    if u"?" in trackName:
        trackName = trackName.replace(u"?", u"-")
    if u"<" in trackName:
        trackName = trackName.replace(u"<", u"-")
    if u">" in trackName:
        trackName = trackName.replace(u">", u"-")
    if u'"' in trackName:
        trackName = trackName.replace(u'"', u"-")
    if u"*" in trackName:
        trackName = trackName.replace(u"*", u"-")
    if u"..." in trackName:
        trackName = trackName.replace(u"...", u"---")

    return trackName

def renameFile(trackId, trackName, premiumFlag):
    '''
    Using the trackId as the filename saves me lots
    of trouble compared to having to deal with the
    (sometimes) problematic titles as filenames.
    That way it's easier to just rename them afterwards.
    '''
    trackName = repairFilename(trackName)
    #We're dealing with a .m4a file here
    if premiumFlag == 1:    
        oldFilename = str(trackId) + '.m4a'
        newFilename = str(trackName) + '.m4a'
    #We're dealing with a .mp3 file here
    if premiumFlag == 0:
        oldFilename = str(trackId) + '.mp3'
        newFilename = str(trackName) + '.mp3'
        
    if not os.path.exists(newFilename): 
        os.rename(oldFilename, newFilename)

def cleanUp(trackId, trackName):
    '''
    Removes all the leftover files, both the ones from the successful
    as well as the failed downloads which are basically just empty files
    '''
    if os.path.isfile("cover.jpg") == True:
        os.remove("cover.jpg")
    if os.path.isfile(str(trackId) + ".txt") == True:
        os.remove(str(trackId) + ".txt")
    if os.path.isfile(str(trackId) + ".m3u8") == True:
        os.remove(str(trackId) + ".m3u8")
    if os.path.isfile(str(trackId) + ".m4a") == True:
        os.remove(str(trackId) + ".m4a")
    if os.path.isfile(str(trackId) + ".mp3") == True:
        os.remove(str(trackId) + ".mp3")        
                
def changeDirectory(folderName):
    '''
    makes directory with the name of the album passed to it, creates it if needed
    '''
    folderName = repairFilename(folderName)
    if "/" in folderName:
        folderName.replace("/","-")
    if not os.path.exists(folderName):
        os.mkdir(folderName)
        os.chdir(folderName)
    else:
        os.chdir(folderName)

def getTrackId(soundcloudUrl):
    '''
    Self-explanatory.
    '''
    while True:
        try:
            resolveUrl = "https://api.soundcloud.com/resolve.json?url="
            url = str(resolveUrl) + str(soundcloudUrl) + str("&client_id=") + str(clientId)
            s = requests.get(url)
            s = s.content
            trackId = json.loads(s)
            trackId = trackId["id"]
            return trackId
        except:
            time.sleep(2)
            continue
        break

def downloadPremium(trackId):
    '''
    saves the json file containing a link to the hls stream which
    contains the audio we want. I have no clue for how long this
    hacky solution will continue to work. Probably until I cancel
    my SoundCloud Go Plus subscription (or rather trial)
    '''
    if platform.system() == 'Windows':
        curlPremiumJsonUrl = pathToCurlWindows + u" \"https://api-v2.soundcloud.com/tracks?ids=" + str(trackId) + u"&client_id=GSTMg2qyKgq8Ou9wvJfkxb3jk1ONIzvy&%5Bobject%20Object%5D=&app_version=1570441876&app_locale=de\" -H \"Sec-Fetch-Mode: cors\" -H \"Origin: https://soundcloud.com\" -H \"Authorization: OAuth 2-290697-69920468-HvgOO5GJcVtYD39\" -H \"Content-Type: application/json\" -H \"Accept: application/json, text/javascript, */*; q=0.1\" -H \"Referer: https://soundcloud.com/\" -H \"User-Agent: Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/77.0.3865.90 Safari/537.36\" -H \"DNT: 1\" -k -s --compressed > " + str(trackId) + u".txt"
    else:
        curlPremiumJsonUrl = u"curl \"https://api-v2.soundcloud.com/tracks?ids=" + str(trackId) + u"&client_id=GSTMg2qyKgq8Ou9wvJfkxb3jk1ONIzvy&%5Bobject%20Object%5D=&app_version=1570441876&app_locale=de\" -H \"Sec-Fetch-Mode: cors\" -H \"Origin: https://soundcloud.com\" -H \"Authorization: OAuth 2-290697-69920468-HvgOO5GJcVtYD39\" -H \"Content-Type: application/json\" -H \"Accept: application/json, text/javascript, */*; q=0.1\" -H \"Referer: https://soundcloud.com/\" -H \"User-Agent: Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/77.0.3865.90 Safari/537.36\" -H \"DNT: 1\" -k -s --compressed > " + str(trackId) + u".txt"
    os.system(curlPremiumJsonUrl)
    jsonFilename = str(trackId) + u".txt"
    with open(jsonFilename) as f:
        data = json.loads(f.read())
        url = data[0]['media']['transcodings'][0]['url']
    url = url + "?client_id=GSTMg2qyKgq8Ou9wvJfkxb3jk1ONIzvy"

    '''
    In the words of Dillon Francis' alter ego DJ Hanzel: "van deeper"
    That link to the hls stream leads to yet another link, which
    contains yet another link, which contains...
    '''
    if platform.system() == 'Windows':
        curlPremiumm3u8 = pathToCurlWindows + " \"" + url + "\" -H \"Sec-Fetch-Mode: cors\" -H \"Referer: https://soundcloud.com/\" -H \"Origin: https://soundcloud.com\" -H \"User-Agent: Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/77.0.3865.90 Safari/537.36\" -H \"Authorization: OAuth 2-290697-69920468-HvgOO5GJcVtYD39\" -H \"DNT: 1\" -k -s --compressed > " + str(trackId) + ".txt"
    else:
        curlPremiumm3u8 = "curl \"" + url + "\" -H \"Sec-Fetch-Mode: cors\" -H \"Referer: https://soundcloud.com/\" -H \"Origin: https://soundcloud.com\" -H \"User-Agent: Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/77.0.3865.90 Safari/537.36\" -H \"Authorization: OAuth 2-290697-69920468-HvgOO5GJcVtYD39\" -H \"DNT: 1\" -k -s --compressed > " + str(trackId) + ".txt"
    os.system(curlPremiumm3u8)
    m3u8Filename = str(trackId) + ".txt"
    with open(m3u8Filename) as f:
        data = json.loads(f.read())
        url = data['url']

    '''
    Yet another really hacky solution, gets the .m3u8 file using curl,
    it basically only replicates excactly what a browser would do (go
    look at the network tab in the explore tool and see for yourself)
    '''
    if platform.system() == 'Windows':
        os.system(pathToCurlWindows + " \"" + url + "\" -H \"Sec-Fetch-Mode: cors\" -H \"Referer: https://soundcloud.com/\" -H \"Origin: https://soundcloud.com\" -H \"User-Agent: Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/77.0.3865.90 Safari/537.36\" -H \"Authorization: OAuth 2-290697-69920468-HvgOO5GJcVtYD39\" -H \"DNT: 1\" -k -s --compressed > " + str(trackId) + ".m3u8")
    else:
        os.system("curl \"" + url + "\" -H \"Sec-Fetch-Mode: cors\" -H \"Referer: https://soundcloud.com/\" -H \"Origin: https://soundcloud.com\" -H \"User-Agent: Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/77.0.3865.90 Safari/537.36\" -H \"Authorization: OAuth 2-290697-69920468-HvgOO5GJcVtYD39\" -H \"DNT: 1\" -k -s --compressed > " + str(trackId) + ".m3u8")

    '''
    Stitch the .m4a together using ffmpeg. Thank God I don't have to do this by hand.
    By the way, ffmpeg hates https so it needs to be whitelisted.
    '''
    ffmpegCommand = ffmpegPath + " -y -protocol_whitelist file,http,https,tcp,tls -i " + str(trackId) + ".m3u8 -c copy " + str(trackId) + ".m4a -loglevel panic"
    os.system(ffmpegCommand)

def downloadPremiumPrivate(trackId, soundcloudUrl):
    secretToken = soundcloudUrl.split("/")[5]
    if platform.system() == 'Windows':
        curlPremiumJsonUrl = pathToCurlWindows + u" \"https://api-v2.soundcloud.com/tracks/soundcloud:tracks:" + str(trackId) + '?client_id=1SoBYKkeYLyQsSAiFMTGD0dc0ShJDKUf&secret_token=' + str(secretToken) + "&app_version=1571932339&app_locale=de\" -H \"Connection: keep-alive\" -H \"Accept: application/json, text/javascript, */*; q=0.01\" -H \"Origin: https://soundcloud.com\" -H \"Authorization: OAuth 2-290697-69920468-HvgOO5GJcVtYD39\" -H \"User-Agent: Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/78.0.3904.70 Safari/537.36\" -H \"DNT: 1\" -H \"Sec-Fetch-Site: same-site\" -H \"Sec-Fetch-Mode: cors\" -H \"Referer: https://soundcloud.com/\" -H \"Accept-Encoding: gzip, deflate, br\" -H \"Accept-Language: de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7\" -k -s --compressed > " + str(trackId) + u".txt"
    else:
        curlPremiumJsonUrl = "curl \"https://api-v2.soundcloud.com/tracks/soundcloud:tracks:" + str(trackId) + '?client_id=1SoBYKkeYLyQsSAiFMTGD0dc0ShJDKUf&secret_token=' + str(secretToken) + "&app_version=1571932339&app_locale=de\" -H \"Connection: keep-alive\" -H \"Accept: application/json, text/javascript, */*; q=0.01\" -H \"Origin: https://soundcloud.com\" -H \"Authorization: OAuth 2-290697-69920468-HvgOO5GJcVtYD39\" -H \"User-Agent: Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/78.0.3904.70 Safari/537.36\" -H \"DNT: 1\" -H \"Sec-Fetch-Site: same-site\" -H \"Sec-Fetch-Mode: cors\" -H \"Referer: https://soundcloud.com/\" -H \"Accept-Encoding: gzip, deflate, br\" -H \"Accept-Language: de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7\" -k -s --compressed > " + str(trackId) + u".txt"
    os.system(curlPremiumJsonUrl)
    jsonFilename = str(trackId) + ".txt"
    with open(jsonFilename) as f:
        data = json.loads(f.read())
        url = data['media']['transcodings'][0]['url']

    '''
    In the words of Dillon Francis' alter ego DJ Hanzel: "van deeper"
    That link to the hls stream leads to yet another link, which
    contains yet another link, which contains...
    '''
    if platform.system() == 'Windows':
        curlPremiumm3u8 = str(Path("./bin/curl.exe").absolute()) + " \"" + url + "\" -H \"Sec-Fetch-Mode: cors\" -H \"Referer: https://soundcloud.com/\" -H \"Origin: https://soundcloud.com\" -H \"User-Agent: Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/77.0.3865.90 Safari/537.36\" -H \"Authorization: OAuth 2-290697-69920468-HvgOO5GJcVtYD39\" -H \"DNT: 1\" -k -s --compressed > " + str(trackId) + ".txt"
    else:
        curlPremiumm3u8 = "curl \"" + url + "\" -H \"Sec-Fetch-Mode: cors\" -H \"Referer: https://soundcloud.com/\" -H \"Origin: https://soundcloud.com\" -H \"User-Agent: Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/77.0.3865.90 Safari/537.36\" -H \"Authorization: OAuth 2-290697-69920468-HvgOO5GJcVtYD39\" -H \"DNT: 1\" -k -s --compressed > " + str(trackId) + ".txt"
    os.system(curlPremiumm3u8)
    m3u8Filename = str(trackId) + ".txt"
    with open(m3u8Filename) as f:
        data = json.loads(f.read())
        url = data['url']

    '''
    Yet another really hacky solution, gets the .m3u8 file using curl,
    it basically only replicates excactly what a browser would do (go
    look at the network tab in the explore tool and see for yourself)
    '''
    if platform.system() == 'Windows':
        os.system(str(Path("./bin/curl.exe").absolute()) + " \"" + url + "\" -H \"Sec-Fetch-Mode: cors\" -H \"Referer: https://soundcloud.com/\" -H \"Origin: https://soundcloud.com\" -H \"User-Agent: Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/77.0.3865.90 Safari/537.36\" -H \"Authorization: OAuth 2-290697-69920468-HvgOO5GJcVtYD39\" -H \"DNT: 1\" -k -s --compressed > " + str(trackId) + ".m3u8") 
    else:
        os.system("curl \"" + url + "\" -H \"Sec-Fetch-Mode: cors\" -H \"Referer: https://soundcloud.com/\" -H \"Origin: https://soundcloud.com\" -H \"User-Agent: Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/77.0.3865.90 Safari/537.36\" -H \"Authorization: OAuth 2-290697-69920468-HvgOO5GJcVtYD39\" -H \"DNT: 1\" -k -s --compressed > " + str(trackId) + ".m3u8")

    '''
    Stitch the .m4a together using ffmpeg. Thank God I don't have to do this by hand.
    By the way, ffmpeg hates https so it needs to be whitelisted.
    '''
    ffmpegCommand = ffmpegPath + " -y -protocol_whitelist file,http,https,tcp,tls -i " + str(trackId) + ".m3u8 -c copy " + str(trackId) + ".m4a -loglevel panic"
    os.system(ffmpegCommand)

def downloadRegular(trackId, soundcloudUrl):
    resolveRegularPrivateUrl = "https://api-mobi.soundcloud.com/resolve?permalink_url=" + soundcloudUrl + "&client_id=" + clientId + "&format=json&app_version=" + appVersion
    regularPrivateUrl = requests.get(resolveRegularPrivateUrl)
    regularPrivateUrl = regularPrivateUrl.content
    regularPrivateUrl = json.loads(regularPrivateUrl)
    privateMp3Url = regularPrivateUrl["media"]["transcodings"][0]["url"]
    privateMp3Url = privateMp3Url.replace("https://api-mobi.soundcloud.com","https://api-v2.soundcloud.com")
    privateMp3Url = requests.get(privateMp3Url + "?client_id=" + clientId)
    privateMp3Url = privateMp3Url.content
    privateMp3UrlJson = json.loads(privateMp3Url)
    privateMp3Url = privateMp3UrlJson["url"]
    filename = str(trackId) + ".m3u8"
    urllib.request.urlretrieve(privateMp3Url, filename)

    ffmpegCommand = ffmpegPath + " -y -protocol_whitelist file,http,https,tcp,tls -i " + str(trackId) + ".m3u8 -c copy " + str(trackId) + ".mp3 -loglevel panic"
    os.system(ffmpegCommand)

def downloadRegularPrivate(trackId, soundcloudUrl):
    resolveRegularPrivateUrl = "https://api-mobi.soundcloud.com/resolve?permalink_url=" + soundcloudUrl + "&client_id=" + clientId + "&format=json&app_version=" + appVersion
    regularPrivateUrl = requests.get(resolveRegularPrivateUrl)
    regularPrivateUrl = regularPrivateUrl.content
    regularPrivateUrl = json.loads(regularPrivateUrl)
    try:
        privateMp3Url = regularPrivateUrl["media"]["transcodings"][0]["url"]
        privateMp3Url = privateMp3Url.replace("https://api-mobi.soundcloud.com","https://api-v2.soundcloud.com")
        privateMp3Url = requests.get(privateMp3Url + "?client_id=" + clientId)
        privateMp3Url = privateMp3Url.content
        privateMp3UrlJson = json.loads(privateMp3Url)
        privateMp3Url = privateMp3UrlJson["url"]
    except:
        privateMp3Url = regularPrivateUrl["media"]["transcodings"][0]["url"] +  "&client_id=" + clientId
        privateMp3Url = privateMp3Url.replace("https://api-mobi.soundcloud.com","https://api-v2.soundcloud.com")
        privateMp3Url = requests.get(privateMp3Url)
        privateMp3Url = privateMp3Url.content
        privateMp3UrlJson = json.loads(privateMp3Url)
        privateMp3Url = privateMp3UrlJson["url"]
    filename = str(trackId) + ".m3u8"
    urllib.request.urlretrieve(privateMp3Url, filename)

    ffmpegCommand = ffmpegPath + " -y -protocol_whitelist file,http,https,tcp,tls -i " + str(trackId) + ".m3u8 -c copy " + str(trackId) + ".mp3 -loglevel panic"
    os.system(ffmpegCommand)

def getTags(soundcloudUrl):
    '''
    Get the big json file containing basically all the metadata using the API
    '''
    resolveUrl = u"https://api.soundcloud.com/resolve.json?url="
    while True:
        try:
            a = requests.get(str(resolveUrl) + str(soundcloudUrl) + u"&client_id=" + str(clientId))
            a = a.content
            tags = json.loads(a)
            trackName = tags["title"]
        except:
            time.sleep(2)
            continue
        break

    if(metadataFlag == 1):
        metadataFilename = repairFilename(trackName) + "_" + str(tags["id"]) + "_metadata.json"
        print("Writing metadata to file: ", metadataFilename)
        try:
            with open(metadataFilename, 'w') as json_file:
                json.dump(tags, json_file, sort_keys=True, indent=4)
        except:
            print("!!! An error occured while writing the metadata to a file!")

    try:
        print("trackName: {}".format(trackName))
    except :
        raise
    
    artist = tags["user"]["username"]

    print("artist: {}".format(artist))

    '''
    the json file doesn't reveal the biggest available cover art, 
    but we can fix that ourselves!
    '''
    cover = tags["artwork_url"]
    if cover != None:
        coverFlag = 1
        cover = cover.replace("large", "t500x500")
        try:
            urllib.request.urlretrieve(cover, "cover.jpg")
        except:
            try:
                coverFlag = 1
                cover = tags["user"]["avatar_url"]
                cover = cover.replace("large", "t500x500")
                urllib.request.urlretrieve(cover, "cover.jpg")
            except urllib.error.HTTPError:
                coverFlag = 0
    else:
        '''
        some tracks don't have any kind of cover art, the
        avatar of the user is shown instead. We can implement that
        here. Once again the full size picture is not in the json file...
        '''
        try:
            coverFlag = 1
            cover = tags["user"]["avatar_url"]
            cover = cover.replace("large", "t500x500")
            urllib.request.urlretrieve(cover, "cover.jpg")
        except urllib.error.HTTPError:
            coverFlag = 0


    return trackName, artist, coverFlag

def getDescription(soundcloudUrl):
    '''
    gets the description separately
    '''
    resolveUrl = "https://api.soundcloud.com/resolve.json?url="
    a = requests.get(resolveUrl + soundcloudUrl + "&client_id=" + clientId)
    a = a.content
    tags = json.loads(a)
    description = tags["description"]
    return description

def addTags(trackName, artist, album, coverFlag, description, m4aFlag):
    '''
    Adds tags to the M4A file. 
    All of these are supported by iTunes and should
    therefore not cause much trouble with other media
    players. If you're downloading a playlist, then the
    album name will be the name of the playlist instead of
    "SoundCloud"
    '''
    if m4aFlag == 1:
        repairedFilename = repairFilename(trackName)
        tags = MP4(repairedFilename + ".m4a").tags
        if description != None:
            tags["desc"] = description
        tags["\xa9nam"] = trackName
        if album != 0:
            tags["\xa9alb"] = album
        else:
            tags["\xa9alb"] = "SoundCloud"
        tags["\xa9ART"] = artist

        with open("cover.jpg", "rb") as f:
            tags["covr"] = [
                MP4Cover(f.read(), imageformat=MP4Cover.FORMAT_JPEG)
            ]
        tags.save(repairedFilename + ".m4a")



    if m4aFlag == 0:
        repairedFilename = repairFilename(trackName)
        audio = EasyMP3(repairedFilename + ".mp3")
        audio['title'] = trackName
        audio['artist'] = artist

        if album != 0:
            audio['album'] = album
        else:
            audio['album'] = u"SoundCloud"
        audio.save(v2_version=3)

        if coverFlag != 0:
            audio = ID3(str(repairedFilename) + u".mp3")
            if description != None:
                audio.add(
                USLT(
                    encoding=3,
                    lang=u'eng',
                    desc=u'desc',
                    text=description
                    )
                )
            with open('cover.jpg', 'rb') as albumart:    
                audio.add(
                APIC(
                    encoding=3,
                    mime='image/jpeg',
                    type=3,
                    desc='Cover',
                    data=albumart.read()
                    )
                )
            audio.save(v2_version=3)

def downloadPlaylist(soundcloudUrl, hqFlag):
    playlistId = getPlaylistId(soundcloudUrl)
    print("Playlist ID: {}".format(playlistId))
    permalinkUrl, trackId, trackName, album, trackCount = getPlaylistTracks(playlistId)
    if descriptionDisableFlag == 0:
        description = getPlaylistDescriptions(playlistId)
    else:
        description = ""

    changeDirectory(album)
    
    if not os.path.exists(lastTrackIndexFilePath):
        lastTrackIndexFile = open(lastTrackIndexFilePath, 'w+')
        lastTrackIndex = 0
        lastTrackIndexFile.write(str(lastTrackIndex))
    else:
        lastTrackIndexFile = open(lastTrackIndexFilePath, 'r')
        lastTrackIndex = int(lastTrackIndexFile.read())
    
    for index in range(lastTrackIndex, trackCount):
        downloadSingleTrack(permalinkUrl[index], trackName[index], hqFlag, album)
        lastTrackIndexFile = open(lastTrackIndexFilePath, 'w')
        lastTrackIndexFile.write(str(index))
        lastTrackIndexFile.close()

def getPlaylistId(soundcloudUrl):
    '''
    The name says it all, that's really al there is to it.
    '''
    resolveUrl = u"https://api-mobi.soundcloud.com/resolve?permalink_url=" + soundcloudUrl + u"&client_id=" + clientId + u"&format=json&app_version=" + appVersion
    playlistIdRequest = requests.get(resolveUrl).content
    playlistIdRequest = json.loads(playlistIdRequest)
    return playlistIdRequest["id"]

def getPlaylistTracks(playlistId):
    '''
    Gets the links to all the tracks in a playlist together with their
    names as well as their IDs, all of which are necessary to download
    the track seamlessly.
    '''
    playlistApiUrl = "http://api.soundcloud.com/playlists/" + str(playlistId) + "?client_id=" + str(clientId)
    playlistUrls = requests.get(playlistApiUrl)
    permalinkUrls = json.loads(playlistUrls.content)
    album = permalinkUrls["title"]
    print("Album: {}".format(album))
    permalinkUrl = []
    trackId = []
    trackTitle = []
    trackCount = int(permalinkUrls["track_count"])

    for i in range(trackCount):
        try:
            permalinkUrl.append(i)
            trackId.append(i)
            trackTitle.append(i)
            permalinkUrl[i] = permalinkUrls["tracks"][i]["permalink_url"]
            trackId[i] = permalinkUrls["tracks"][i]["id"]
            trackTitle[i] = permalinkUrls["tracks"][i]["title"]
        except IndexError:
            missingTracks = trackCount - i
            print("Sorry, {} of the tracks in this playlist are not available".format(str(missingTracks)),
                "in your country and can therefore not be downloaded.",
                "Please use a VPN.")
            trackCount = i
            break

    return permalinkUrl, trackId, trackTitle, album, trackCount 

def getPlaylistDescriptions(playlistId):
    '''
    Get individual descriptions for all the track in a playlist.
    I have yet to figure out why the getTags function refuses
    to pass the description string as an argument but this 
    seprate function works just fine for the time being. Sure,
    it's not efficient but one more API request on top of countless
    other ones won't hurt.
    '''
    playlistApiUrl = "http://api.soundcloud.com/playlists/" + str(playlistId) + "?client_id=" + str(clientId)
    playlistUrls = requests.get(playlistApiUrl)
    permalinkUrls = json.loads(playlistUrls.content)
    description = []
    trackCount = int(permalinkUrls["track_count"])

    for i in range(trackCount):
        try:
            description.append(i)
            description[i] = permalinkUrls["tracks"][i]["description"]
        except IndexError:
            break

    return description

def parseStuff():
    '''
    Checks for two arguments, --pl for a playlist link and
    -p for the m4a download. If the playlist flag isn't present
    it just uses a simple regex as a fallback. If the premium flag
    isn't present scdl will simply download the 128kbps MP3 available
    for everyone else that isn't a SCG+ subscriber.
    '''
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-p','--premium',
        help="Use to download 256kbps M4A files",
        action="store_true",
        dest="premium",
        )
    parser.add_argument(
        '-pl','--playlist',
        help="Download a playlist instead of a single track",
        action="store_true",
        dest="playlistFlag",
        )
    parser.add_argument(
        '-m','--metadata',
        help="Write track metadata to a separate file",
        action="store_true",
        dest="metadataArg",
        )
    parser.add_argument(
        '-dd','--disable-description',
        help="Disable reading and writing of description ID3 tag / JSON",
        action="store_true",
        dest="descriptionFlag"
        )
    parser.add_argument(
        '-f','--ffmpeg-location',
        help="Path to ffmpeg. Can be the containing directory or ffmpeg executable itself",
        action="store",
        dest="ffmpegPath"
    )

    args = parser.parse_args()

    if args.descriptionFlag is True:
        global descriptionDisableFlag
        descriptionDisableFlag = 1
        print("Description disabled!")
    else:
        global descriptionFlag
        descriptionDisableFlag = 0
    if args.premium is True:
        global premiumFlag
        premiumFlag = 1
        print("Premium flag set!")
    else:
        premiumFlag = 0
    if args.metadataArg is True:
        global metadataFlag
        metadataFlag = 1
        print("Metadata flag set!")
    else:
        metadataFlag = 0
    if args.playlistFlag is True:
        global playlistFlag
        playlistFlag = 1
        print("Downloading a playlist!")
    if args.playlistFlag is False:
        playlistFlag = 0
    global ffmpegPath
    if args.ffmpegPath:
        ffmpegPath = os.path.abspath(args.ffmpegPath)
        if os.path.exists(ffmpegPath):
            if os.path.isdir(ffmpegPath):
                ffmpegPath = os.path.join(ffmpegPath, "ffmpeg")
        else:
            print("ffmpeg-location is incorrect - path \"" + ffmpegPath + "\" does not exist")
            exit()
    else:
        ffmpegPath = "ffmpeg"


def get_user_id(profile_url):
    resolve_url = "https://api-mobi.soundcloud.com/resolve?permalink_url=" + profile_url + "&client_id=iZIs9mchVcX5lhVRyQGGAYlNPVldzAoX&format=json&app_version=1582537945"
    r = requests.get(resolve_url)
    r = r.content
    x = json.loads(r)
    return x["id"]

def get_tracks_account(link):
    resolve_url = "https://api-mobi.soundcloud.com/users/" + str(get_user_id(link)) + "/profile?client_id=iZIs9mchVcX5lhVRyQGGAYlNPVldzAoX&format=json&app_version=1582537945"
    #print(resolve_url)
    tracks = get_tracks_account_rec(resolve_url)
    return tracks

def get_tracks_account_rec(resolve_url):
    r = requests.get(resolve_url)
    r = r.content
    x = json.loads(r)
    songs = []
    #print(x)
    #print(json.dumps(x, indent=4))
    try:
        for i in x["posts"]["collection"]:
            try:
                if i["type"] == "track":
                    songs.append(i["track"]["permalink_url"])
            except:
                pass
    except:
        pass

    try:
        for i in x["collection"]:
            try:
                if i["type"] == "track":
                    songs.append(i["track"]["permalink_url"])
            except:
                pass
    except:
        pass
    try:
        if x["posts"]["next_href"] is not None:
            #print(x["posts"]["next_href"])
            return songs + get_tracks_account_rec(re.sub(r'limit=', r'limit=100', x["posts"]["next_href"])  + "&client_id=iZIs9mchVcX5lhVRyQGGAYlNPVldzAoX&format=json&app_version=1582537945")
    except:
        if x["next_href"] is not None:
            #print(x["next_href"])
            return songs + get_tracks_account_rec(re.sub(r'limit=', r'limit=100', x["next_href"])  + "&client_id=iZIs9mchVcX5lhVRyQGGAYlNPVldzAoX&format=json&app_version=1582537945")

    return songs

def get_account_name(link):
    resolve_url = "https://api-mobi.soundcloud.com/resolve?permalink_url=" + link + "&client_id=iZIs9mchVcX5lhVRyQGGAYlNPVldzAoX&format=json&app_version=1582537945"
    r = requests.get(resolve_url)
    r = r.content
    x = json.loads(r)
    return x["user"]["permalink"]   

def download(link):
    folder_name = get_account_name(link)
    if not os.path.exists(folder_name):
        os.mkdir(folder_name)
        os.chdir(folder_name)
    else:
        os.chdir(folder_name)
    print("Need to download: {}".format(link))
    try:
        main_archive(link)
        os.chdir('..')
    except Exception as e: 
        print(e)
        os.chdir('..')

def main():
    accounts = {}
    data = {}
    links = []
    downloaded_links = []
    try:
        with open('downloaded_links.json', 'r') as dl_file:
            downloaded_links = json.load(dl_file)
            dl_file.close()
    except:
        with open('downloaded_links.json', 'w+') as f:
            f.close()

    while (True):
        json_file = open('accounts.json', 'r')
        accounts = json.load(json_file)
        json_file.close()
        dl_file = open('downloaded_links.json', 'r')
        try:
            downloaded_links = json.load(dl_file)
        except:
            downloaded_links = []
        dl_file.close()

        print("Number of accounts {}".format(len(accounts['accounts'])))
        for acc in accounts['accounts']:
            data['{}'.format(acc['name'])] = []
            print('{}'.format(acc['name']))
            #print
            account_tracks = get_tracks_account(acc['account'])
            for i in account_tracks:
                    data['{}'.format(acc["name"])].append(i)
                    links.append(i)
        #print(links)
        for i in links:
            #print(i)
            if i not in downloaded_links:
                try:
                    download(i)
                    downloaded_links.append(i)
                    links_txt = open('downloaded_links.json', 'w')
                    json.dump(downloaded_links, links_txt)
                    links_txt.close()
                except:
                    print("Couldn't download {}".format(i))

        time.sleep(60)

if __name__ == '__main__':
    main()