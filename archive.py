#!/usr/bin/env python3

import os
import gc
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
from joblib import Parallel, delayed
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

debugFlag = False
resumeDownloadFlag = False
premiumClientId = "GSTMg2qyKgq8Ou9wvJfkxb3jk1ONIzvy"
premiumFlag = True
metadataFlag = 0
descriptionDisableFlag = 0
segmentsParallel = 16

links = []
data = {}


def main_archive(soundcloudUrl):
    downloadSingleTrack(soundcloudUrl, "", 1, 0)
    print("Done!")

def log_debug(message):
    if debugFlag == True:
        print(message)

log_debug(f"clientId = {clientId}")
log_debug(f"premiumClientId = {premiumClientId}")
log_debug(f"appVersion = {appVersion}")

def removeReadonly(func, path, _):
    os.chmod(path, stat.S_IWRITE)
    func(path)

def downloadEmbeddedFreeDownload(trackId):
    #print("Trying")
    while True:
        try:
            r = requests.get("https://api-v2.soundcloud.com/tracks?ids={}&client_id={}&%5Bobject%20Object%5D=&app_version={}&app_locale=de".format(str(trackId), premiumClientId, appVersion),
                headers={
                "Sec-Fetch-Mode":"cors",
                "Origin": "https://soundcloud.com",
                "Authorization": "OAuth 2-290697-69920468-HvgOO5GJcVtYD39",
                "Content-Type": "application/json",
                "Accept": "application/json, text/javascript, */*; q=0.1",
                "Referer": "https://soundcloud.com/",
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/77.0.3865.90 Safari/537.36",
                "DNT": "1",
                })
        except Exception as e:
            print(e)
        #print("Status Code: {}".format(r.status_code))
        #print("Response: {}".format(r.text))
        if r.status_code == 200:
            break
        else:
            time.sleep(2)
    data = json.loads(r.text)
    print(r.text)

    if data[0]['downloadable'] == True:
        print("This track has the free download enabled!")
        if data[0]['has_downloads_left'] == False:
            print("The download has a restricted number of downloads, not available anymore :(")
            raise Exception("No free download available!")
        if data[0]['has_downloads_left'] == True:
            url = f"https://api-v2.soundcloud.com/tracks/{trackId}/download?client_id={clientId}&app_version={appVersion}&app_locale=de"
            while True:
                try:
                    '''
                    r = requests.get(data[0]['download_url'],
                    headers={
                    "Sec-Fetch-Mode":"cors",
                    "Origin": "https://soundcloud.com",
                    "Authorization": "OAuth 2-290697-69920468-HvgOO5GJcVtYD39",
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/javascript, */*; q=0.1",
                    "Referer": "https://soundcloud.com/",
                    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/77.0.3865.90 Safari/537.36",
                    "DNT": "1",
                    })
                    print(r.content)
                    '''
                    r = requests.get(url)
                    x = json.loads(r.content)
                    print(x)
                    r = requests.head(x['redirectUri'])
                    filename = re.findall("filename=\"(.+)\"", r.headers['content-disposition'])[0]
                    print("Filename: {}".format(filename))
                    print(x)
                    urllib.request.urlretrieve(x['redirectUri'], filename)

                    break
                except Exception as e:
                    print(e)
                    time.sleep(2)
    else:
        raise Exception("No free download available!")

def downloadSingleTrack(soundcloudUrl, trackTitle, hqFlag, optionalAlbum):
    '''
    If you're downloading a playlist a string containing the playlist
    name will be passed to the function as optionalAlbum, otherwise 
    it is 0 and gets replaced by simple string
    '''
    if resumeDownloadFlag == True:
        alreadyDownloaded = False
    
    if optionalAlbum != 0:
        album = optionalAlbum
    else:
        album = "SoundCloud"

    '''
    m4a premium download, only happens when both flags are set
    '''
    trackId = getTrackId(soundcloudUrl)
    try:
        downloadEmbeddedFreeDownload(trackId)
        return
    except:
        log_debug("No free download available!")

    if premiumFlag == 1 and hqFlag == 1:
        size = 0
        m4aFailedFlag = 0
        if resumeDownloadFlag == True:
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
        else:
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

    elif premiumFlag == 0 or hqFlag == 0 or size == 0:
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
    if resumeDownloadFlag == False:
        alreadyDownloaded = False
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
            finishedDownloadFilename = renameFile(trackId, trackName, 0)
        else:
            finishedDownloadFilename = renameFile(trackId, trackName, 1)
     
        if premiumFlag ==  1 and hqFlag == 1 and m4aFailedFlag == 0:
            '''
            m4a
            '''
            addTags(finishedDownloadFilename, trackName, artist, album, coverFlag, description, 1)
        else:
            '''
            mp3
            '''
            addTags(finishedDownloadFilename, trackName, artist, album, coverFlag, description, 0)

    
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

    log_debug(">> renameFilename()")

    trackName = repairFilename(trackName)
    #We're dealing with a .m4a file here
    if premiumFlag == 1:  
        fileExtension = ".m4a"  
        oldFilename = str(trackId) + fileExtension
        newFilename = str(trackName) + fileExtension
    #We're dealing with a .mp3 file here
    if premiumFlag == 0:
        fileExtension = ".mp3"
        oldFilename = str(trackId) + fileExtension
        newFilename = str(trackName) + fileExtension
        
    newFixedFilename = ""
    if not os.path.exists(newFilename):
        os.rename(oldFilename, newFilename)
    else:
        ii = 1
        while True:
            newFixedFilename = str(trackName) + "_" + str(ii) + fileExtension
            if not os.path.exists(newFixedFilename):
                print("File with same filename exists, renaming current file to {}".format(newFixedFilename))
                os.rename(oldFilename, newFixedFilename)
                break
            ii += 1
    if newFixedFilename != "":
        newFilename = newFixedFilename
    return newFilename

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
    log_debug(">> downloadPremium()")
    while True:
        try:
            r = requests.get("https://api-v2.soundcloud.com/tracks?ids={}&client_id={}&%5Bobject%20Object%5D=&app_version={}&app_locale=de".format(str(trackId), premiumClientId, appVersion),
                headers={
                "Sec-Fetch-Mode":"cors",
                "Origin": "https://soundcloud.com",
                "Authorization": "OAuth 2-290697-69920468-HvgOO5GJcVtYD39",
                "Content-Type": "application/json",
                "Accept": "application/json, text/javascript, */*; q=0.1",
                "Referer": "https://soundcloud.com/",
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/77.0.3865.90 Safari/537.36",
                "DNT": "1",
                })
        except Exception as e:
            print(e)
        log_debug("Status Code: {}".format(r.status_code))
        log_debug("Response: {}".format(r.text))
        if r.status_code == 200:
            break
        else:
            time.sleep(2)
    data = json.loads(r.text)
    transcoding_index = 0
    url = data[0]['media']['transcodings'][transcoding_index]['url']

    '''
    In the words of Dillon Francis' alter ego DJ Hanzel: "van deeper"
    That link to the hls stream leads to yet another link, which
    contains yet another link, which contains...
    '''
    while True:
        try:   
            r = requests.get(url,
                headers={
                    "Sec-Fetch-Mode": "cors",
                    "Referer": "https://soundcloud.com/",
                    "Origin": "https://soundcloud.com",
                    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/77.0.3865.90 Safari/537.36",
                    "Authorization": "OAuth 2-290697-69920468-HvgOO5GJcVtYD39",
                    "DNT": "1",
                })
        except Exception as e:
            print(e)
        log_debug("URL: {}".format(url))
        log_debug("Status Code: {}".format(r.status_code))
        log_debug("Response: {}".format(r.text))
        if r.status_code == 200:
            break
        if r.status_code == 500:
            log_debug("Got 500 Server-side error, trying next m3u8 playlist...")
            transcoding_index += 1
            url = data[0]['media'][transcoding_index]['url']
        else:
            time.sleep(2)

    data = json.loads(r.text)
    url = data['url']
    log_debug(f"URL: {url}")

    if transcoding_index == 1 or transcoding_index == 3:
        log_debug("Attempting to download progressive version...")
        urllib.request.urlretrieve(url, "{}.m4a".format(trackId))
        return

    '''
    Yet another really hacky solution, gets the .m3u8 file using curl,
    it basically only replicates excactly what a browser would do (go
    look at the network tab in the explore tool and see for yourself)
    '''

    while True:
        try:
            r = requests.get(url,
                headers={
                "Sec-Fetch-Mode": "cors",
                "Referer": "https://soundcloud.com",
                "Origin": "https://soundcloud.com",
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/77.0.3865.90 Safari/537.36",
                "Authorization": "OAuth 2-290697-69920468-HvgOO5GJcVtYD39",
                "DNT": "1"
                })
        except Exception as e:
            print(e)
        log_debug("Status Code: {}".format(r.status_code))
        if r.status_code == 200:
            break
        else:
            time.sleep(2)

    downloadM3U8(trackId, r.text)

def downloadSegment(segment_urls, i, trackId, correctDirectory):
    '''
    This function randomly changes directories without telling it to,
    please don't ask me why. This fixes that.
    '''
    if (os.getcwd() != correctDirectory):
        os.chdir(correctDirectory)

    if platform.system() == 'Linux':
        print("\033[K\r", "Segment: [{} / {}]".format(i + 1, len(segment_urls)), "\r", end='')

    while True:
        try:
            urllib.request.urlretrieve(segment_urls[i], "{}-{}.m4a".format(trackId, i))
            break
        except Exception as e:
            print(e)
            time.sleep(2)

def downloadM3U8(trackId, m3u8_file):
    segment_urls = []
    regex = re.compile('^.*https.*$')

    for line in m3u8_file.splitlines():
        if regex.search(line):
            line = line.replace('#EXT-X-MAP:URI=','')
            line = line.replace('"', '')
            line = line.replace('\n', '')
            segment_urls.append(line)

    Parallel(n_jobs=int(segmentsParallel))(delayed(downloadSegment)(segment_urls, i, trackId, os.getcwd()) for i in range(len(segment_urls)))

    print("\033[K\r", "                                   ", "\r", end='')

    segment_filenames = []
    for i in range(len(segment_urls)):
        segment_filenames.append("{}-{}.m4a".format(trackId, i))

    with open(str(trackId) + '.m4a', 'ab') as outfile:
        for file in segment_filenames:
            with open(file, "rb") as file2:
                outfile.write(file2.read())

    for file in segment_filenames:
        os.remove(file)

def downloadPremiumPrivate(trackId, soundcloudUrl):
    log_debug("downloadPremiumPrivate()")
    secretToken = soundcloudUrl.split("/")[5]
    log_debug(f"secretToken: {secretToken}")
    log_debug(f"trackId: {trackId}")

    while True:
        try:
            r = requests.get("https://api-mobi.soundcloud.com/tracks/soundcloud:tracks:{}?secret_token={}&client_id={}&&app_version={}&app_locale=de".format(trackId, secretToken, clientId, appVersion),
                headers={
                "Connection": "keep-alive",
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "Authorization": "OAuth 2-290697-69920468-HvgOO5GJcVtYD39",
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/78.0.3904.70 Safari/537.36",
                "DNT": "1",
                "Sec-Fetch-Site": "same-site",
                "Sec-Fetch-Mode": "cors",
                "Referer": "https://soundcloud.com/",
                "Accept-Encoding": "gzip, deflate, br",
                "Accept-Language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7"
                })
        except Exception as e:
            print(e)

        log_debug("Status Code: {}".format(r.status_code))
        if r.status_code == 200:
            break
        else:
            time.sleep(2)

    with open(str(trackId) + ".txt", 'w+') as file:
        file.write(r.text)


    file = codecs.open(str(trackId) + ".txt",'r', encoding='UTF-8')
    data = json.loads(file.readlines()[0])
    url = data['media']['transcodings'][0]['url']
    log_debug(f"URL: {url}")
    '''
    In the words of Dillon Francis' alter ego DJ Hanzel: "van deeper"
    That link to the hls stream leads to yet another link, which
    contains yet another link, which contains...
    '''
    while True:
        try:
            r = requests.get(url,
                headers={
                "Sec-Fetch-Mode": "cors",
                "Referer": "https://soundcloud.com/",
                "Origin": "https://soundcloud.com",
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/77.0.3865.90 Safari/537.36",
                "Authorization": "OAuth 2-290697-69920468-HvgOO5GJcVtYD39",
                "DNT": "1",
                })
        except Exception as e:
            print(e)

        log_debug("Status Code: {}".format(r.status_code))
        if r.status_code == 200:
            break
        else:
            time.sleep(2)

    with open(str(trackId) + ".txt", "w") as file:
        file.write(r.text)

    with open(str(trackId) + ".txt") as f:
        data = json.loads(f.read())
        url = data['url']

    '''
    Yet another really hacky solution, gets the .m3u8 file using curl,
    it basically only replicates excactly what a browser would do (go
    look at the network tab in the explore tool and see for yourself)
    '''
    while True:
        try:
            r = requests.get(url,
                headers={
                "Sec-Fetch-Mode": "cors",
                "Referer": "https://soundcloud.com/",
                "Origin": "https://soundcloud.com",
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/77.0.3865.90 Safari/537.36",
                "Authorization": "OAuth 2-290697-69920468-HvgOO5GJcVtYD39",
                "DNT": "1"
                })
        except Exception as e:
            print(e)
        log_debug("Status Code: {}".format(r.status_code))
        if r.status_code == 200:
            break
        else:
            sleep(2)

    print(r.text)
    with open(str(trackId) + ".m3u8", "w") as file:
        file.write(r.text)

    downloadM3U8(trackId)

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

    os.system("{} -y -protocol_whitelist file,http,https,tcp,tls -i {}.m3u8 -c copy {}.mp3 -loglevel panic".format(ffmpegPath, trackId, trackId))

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
    urllib.request.urlretrieve(privateMp3Url, str(trackId) + ".m3u8")

    os.system("{} -y -protocol_whitelist file,http,https,tcp,tls -i {}.m3u8 -c copy {}.mp3 -loglevel panic".format(ffmpegPath, trackId, trackId))

def getTags(soundcloudUrl):
    '''
    Get the big json file containing basically all the metadata using the API
    '''
    log_debug(f"getTags(soundcloudUrl = {soundcloudUrl})")
    while True:
        try:
            a = requests.get("https://api.soundcloud.com/resolve.json?url=" + soundcloudUrl + "&client_id=" + clientId)
            log_debug(f"URL: {a.url}")
            log_debug(f"Status code: {a.status_code}")
            a = a.content
            tags = json.loads(a)
            trackName = tags["title"]
        except:
            time.sleep(2)
            continue
        break

    log_debug("Got tags!")

    if(metadataFlag == 1):
        metadataFilename = repairFilename(trackName) + "_" + str(tags["id"]) + "_metadata.json"
        print("Writing metadata to file: ", metadataFilename)
        try:
            with open(metadataFilename, 'w') as json_file:
                json.dump(tags, json_file, sort_keys=True, indent=4)
        except:
            print("An error occured while writing the metadata to a file!")

    try:
        print("trackName: {}".format(trackName))
    except :
        raise
    
    artist = tags["user"]["username"]

    print("Artist: {}".format(artist))

    '''
    the json file doesn't reveal the biggest available cover art, 
    but we can fix that ourselves!
    '''
    cover = tags["artwork_url"]
    if cover != None:
        log_debug("Cover URL (large) for track present!")
        coverFlag = 1
        cover = cover.replace("large", "t500x500")
        try:
            urllib.request.urlretrieve(cover, "cover.jpg")
            log_debug("Cover URL (500x500) for track present!")
        except:
            try:
                coverFlag = 1
                cover = tags["user"]["avatar_url"]
                cover = cover.replace("large", "t500x500")
                urllib.request.urlretrieve(cover, "cover.jpg")
                log_debug("Got 500x500 cover from track!")
            except urllib.error.HTTPError:
                log_debug("An error occured while attempting to download the cover from the track! (Can be the case for ancient tracks)")
                coverFlag = 0
    else:
        '''
        some tracks don't have any kind of cover art, the
        avatar of the user is shown instead. We can implement that
        here. Once again the full size picture is not in the json file...
        '''
        log_debug("Attempting to get cover art from artist profile picture...")
        try:
            coverFlag = 1
            cover = tags["user"]["avatar_url"]
            cover = cover.replace("large", "t500x500")
            urllib.request.urlretrieve(cover, "cover.jpg")
            log_debug("Got cover art from artist!")
        except urllib.error.HTTPError:
            log_debug("Error while getting cover from artist profile picture")
            coverFlag = 0

    return trackName, artist, coverFlag

def getDescription(soundcloudUrl):
    '''
    gets the description separately
    '''
    log_debug(f">> getDescription(soundcloudUrl = {soundcloudUrl})")
    a = requests.get("https://api.soundcloud.com/resolve.json?url=" + soundcloudUrl + "&client_id=" + clientId)
    log_debug(f"URL: {a.url}")
    log_debug(f"Status code: {a.status_code}")
    a = a.content
    tags = json.loads(a)
    description = tags["description"]
    log_debug("Got description!")
    return description

def addTags(filename, trackName, artist, album, coverFlag, description, m4aFlag):
    '''
    Adds tags to the M4A file. 
    All of these are supported by iTunes and should
    therefore not cause much trouble with other media
    players. If you're downloading a playlist, then the
    album name will be the name of the playlist instead of
    "SoundCloud"
    '''
    log_debug(f"addTags(filename = {filename}, trackName = {trackName}, artist = {artist}, album = {album}, coverFlag = {coverFlag}, m4aFlag = {m4aFlag})")
    if m4aFlag == 1:
        log_debug("Tagging .m4a...")
        try:
            tags = MP4(filename).tags
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
            tags.save(filename)
        except Exception as e:
            os.rename(filename, filename[:-4] + ".mp3")
            filename = filename[:-4] + ".mp3"
            m4aFlag = 0

    if m4aFlag == 0:
        log_debug("Tagging .mp3...")
        audio = EasyMP3(filename)
        audio['title'] = trackName
        audio['artist'] = artist

        if album != 0:
            audio['album'] = album
        else:
            audio['album'] = u"SoundCloud"
        audio.save(v2_version=3)

        if coverFlag != 0:
            audio = ID3(filename)
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

def parseStuff():
    parser = argparse.ArgumentParser()
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
        '--debug',
        help="Show output for debugging",
        action="store_true",
        dest="debugFlag"
        )
    parser.add_argument(
        '-s', '--segments',
        help="Set number of segments that will be downloaded in parallel (default = 16)",
        action="store",
        dest="SEGMENTS"
        )

    args = parser.parse_args()

    global debugFlag
    if args.debugFlag is True:
        debugFlag = True
    else:
        debugFlag = False

    global descriptionDisableFlag
    if args.descriptionFlag is True:
        descriptionDisableFlag = True
    else:
        descriptionDisableFlag = False

    global metadataFlag
    if args.metadataArg is True:
        metadataFlag = True
    else:
        metadataFlag = False

    global segmentsParallel
    if args.SEGMENTS:
        segmentsParallel = args.SEGMENTS

    log_debug(f"debugFlag = {debugFlag}")
    log_debug(f"descriptionDisableFlag = {descriptionDisableFlag}")
    log_debug(f"metadataFlag =  {metadataFlag}")
    log_debug(f"segmentsParallel = {segmentsParallel}")

def get_user_id(profile_url):
    resolve_url = "https://api-mobi.soundcloud.com/resolve?permalink_url=" + profile_url + "&client_id=iZIs9mchVcX5lhVRyQGGAYlNPVldzAoX&format=json&app_version=1582537945"
    r = requests.get(resolve_url)
    r = r.content
    x = json.loads(r)
    return x["id"]

def get_tracks_account(link):
    resolve_url = "https://api-mobi.soundcloud.com/users/" + str(get_user_id(link)) + "/profile?client_id=iZIs9mchVcX5lhVRyQGGAYlNPVldzAoX&format=json&app_version=1582537945"
    tracks = get_tracks_account_rec(resolve_url)
    return tracks

def get_tracks_account_rec(resolve_url):
    r = requests.get(resolve_url)
    r = r.content
    x = json.loads(r)
    songs = []
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
            return songs + get_tracks_account_rec(re.sub(r'limit=', r'limit=100', x["posts"]["next_href"])  + "&client_id=iZIs9mchVcX5lhVRyQGGAYlNPVldzAoX&format=json&app_version=1582537945")
    except:
        if x["next_href"] is not None:
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

    try:
        main_archive(link)
        os.chdir(os.path.dirname(os.getcwd()))
    except Exception as e: 
        print(e)
        os.chdir(os.path.dirname(os.getcwd()))

def check_account(accounts, i):
    sub_list = []
    global links
    global data

    print("\033[K\r", "Account [{} / {}]".format(i + 1, len(accounts)), "\r", end='')
    data['{}'.format(accounts[i]['name'])] = []

    while True:
        try:
            account_tracks = get_tracks_account(accounts[i]['account'])
            break
        except:
            time.sleep(2)

    for x in account_tracks:
        data['{}'.format(accounts[i]['name'])].append(x)
        sub_list.append(x)
    links.extend(sub_list)

def main():
    global data
    global links
    parseStuff()
    accounts = {}
    downloaded_links = []
    try:
        with open('downloaded_links.json', 'r') as dl_file:
            downloaded_links = json.load(dl_file)
    except:
        with open('downloaded_links.json', 'w+') as f:
            f.close()

    while True:
        with open('accounts.json', 'r') as json_file:
            accounts = json.load(json_file)

        with open('downloaded_links.json', 'r') as dl_file:
            try:
                downloaded_links = json.load(dl_file)
            except:
                downloaded_links = []

        print("Number of accounts: {}".format(len(accounts['accounts'])))
        
        Parallel(n_jobs=16, backend="threading")(delayed(check_account)(accounts['accounts'], i) for i in range(len(accounts['accounts'])))

        for i in links:
            if i not in downloaded_links:
                try:
                    download(i)
                    downloaded_links.append(i)
                    with open('downloaded_links.json', 'w') as links_txt:
                        json.dump(downloaded_links, links_txt)
                except:
                    print("Couldn't download {}".format(i))
                gc.collect()

        time.sleep(60)

if __name__ == '__main__':
    main()