# soundcloud-archive - mass-download songs from SoundCloud
You can either add single accounts or add every account followed by a particular user. It downloads 256kbps M4A files (those only accessible to SoundCloud Go+ subscribers) and falls back on the regular 128kbps MP3 files when it has to. Audio files are tagged with title, artist, description and cover art.

## Installation
Linux:
```
python3 -m pip install --user requests
python3 -m pip install --user mutagen
python3 -m pip install --user joblib

python3 manage_accounts.py <0|1>
python3 archive.py
```

## Usage
manage_accounts.py
```
Usage: python3 manage_accounts.py <0|1>
0 = Enter accounts manually
1 = Add all accounts followed by a certain user
```
archive.py
```
usage: python3 archive.py [-h] [-m] [-dd] [--debug] [-s SEGMENTS]

optional arguments:
  -h, --help                         Show this help message and exit
  -m, --metadata                     Write track metadata to a separate file
  -dd, --disable-description         Disable reading and writing of description ID3 tag /JSON
  --debug                            Show output for debugging
  -s SEGMENTS, --segments SEGMENTS   Set number of segments that will be downloaded in parallel (default = 16)
```

## Compatibility
This script has been tested on Ubuntu 19.10 and Windows 10 (1903) with WSL (Ubuntu 18.04). Mac should work too, but the installation procedure most likely needs to be adapted from Linux. I don't own a Mac so I can't test it myself

## Requirements

* Python3.6
* pip3



## Disclaimer
If a track says “NOT AVAILABLE IN YOUR COUNTRY”, then this tool can’t download the track without a VPN/Proxy/whatever and I can’t change that. Use said tools to get around this.
