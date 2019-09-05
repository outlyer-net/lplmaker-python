#!/usr/bin/env python
from __future__ import print_function # Python3-style print
VERSION = '2019-05-05'

"""
LPLmaker - Generate RetroArch playlists manually, for cases where i
           won't add ROMs automatically

To use this program you should create a configuration file named lplmaker.toml
and place it in ~/.config/

An example configuration is provided
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
from zipfile import ZipFile

import toml

HOME=os.path.expanduser('~')

retroarchDir = os.path.join(HOME,'.config/retroarch')
romsDir = os.path.join(HOME,'Roms')
coresDir = '/usr/lib/libretro'
mame = '/usr/games/mame'

playlists = []

def load_config():
    def load_config_file(cfgPath):
        global playlists, romsDir, coresDir, retroarchDir, mame
        # FIXME: Handle errors
        cfg = toml.load(cfgPath)
        for key in cfg['playlist']:
            playlists.append(cfg['playlist'][key])
        # TODO: Handle case
        if 'RomsDir' in cfg:
            romsDir = cfg['RomsDir']
        if 'CoresDir' in cfg:
            coresDir = cfg['CoresDir']
        if 'RetroArchDir' in cfg:
            retroarchDir = cfg['RetroarchDir']
        if 'Mame' in cfg:
            mame = cfg['Mame']
    loaded = False
    if os.path.exists('./lplmaker.toml'):
        load_config_file('./lplmaker.toml')
        loaded = True
    dotdirConf = os.path.join(os.path.join(HOME, '.config'),'lplmaker.toml')
    if os.path.exists(dotdirConf):
        load_config_file(dotdirConf)
        loaded = True
    if not loaded:
        err("No configuration file present, can't continue.")
        sys.exit(1)

def err(*args, **kwargs):
    print('ERROR:', file=sys.stderr, end=' ')
    print(*args, file=sys.stderr, **kwargs)

def get_terminal_size():
    """
    get_terminal_size() -> (int,int)

    Returns a tuple with the terminal size (columns,rows), will use
    a fallback value of (80,25) if it can't detect the size.

    As found on http://stackoverflow.com/a/566752/2646228.
    Note Python 3 has an equivalent shutil.get_terminal_size()
    """
    import os
    env = os.environ
    def ioctl_GWINSZ(fd):
        try:
            import fcntl, termios, struct, os
            cr = struct.unpack('hh', fcntl.ioctl(fd, termios.TIOCGWINSZ,
        '1234'))
        except:
            return
        return cr
    cr = ioctl_GWINSZ(0) or ioctl_GWINSZ(1) or ioctl_GWINSZ(2)
    if not cr:
        try:
            fd = os.open(os.ctermid(), os.O_RDONLY)
            cr = ioctl_GWINSZ(fd)
            os.close(fd)
        except:
            pass
    if not cr:
        cr = (env.get('LINES', 25), env.get('COLUMNS', 80))

        ### Use get(key[, default]) instead of a try/catch
        #try:
        #    cr = (env['LINES'], env['COLUMNS'])
        #except:
        #    cr = (25, 80)
    return int(cr[1]), int(cr[0])

class ProgressBar(object):
    """
    Quick and dirty CLI progress bar.
    """
    def __init__(self, maxValue=100, channel=sys.stdout):
        self.maxValue = maxValue
        self.channel = channel
        self.curValue = 0
        self.cols = get_terminal_size()[0]
        # Amount of characters guaranteed to be used in the progress bar
        # "[x/maxValue]" => '[', '/', ']' (3) + at least one for 'x' + len(maxValue)
        self.alwaysUsed = 4 + len(str(maxValue))
        self.stopped = True
    def start(self, initialValue=0):
        self.curValue = initialValue
        self._print()
        self.stopped = False
    def stop(self):
        if not self.stopped:
            print(file=self.channel)
        self.stopped = True
    def step(self, msg=''):
        self.curValue += 1
        self._print(msg)
    def _print(self, msg=''):
        # Calculate available space for message
        avail = self.cols - (self.alwaysUsed + len(str(self.curValue)) + 1)
        if msg:
            msg = ' ' + msg[0:avail-2]
        # '\r[%d/%d]%-NNs'
        formatStr = '\r[%%d/%%d]%%-%ds' % avail
        print(formatStr % (self.curValue, self.maxValue, msg), file=self.channel, end='')

def scan_roms_dir(playlist):
    """
    scan_roms_dir(dict) -> (list, list)

    Scan the ROMs directory for ROM files, returns two lists, the first one
    contains rom file names and the second one the zip file names if
    ScanZips is True for this playlist (both without path).
    """
    files = os.listdir(playlist['RomsPath'])
    # get a list of the search() results, each item is a tuple (REmatch, baseName)
    hits = [ ( playlist['SupportedExtensionsRE'].search(x), x ) for x in files ]
    zipHits = []
    if playlist['ScanZips']:
        # Repeat the same for zips
        zipRE = re.compile('\\.zip$')
        zipHits = [ ( zipRE.search(x), x ) for x in files ]
    # return the lists of (if ScanZips is True) uncompressed and compressed ROMs
    # filter out any None items (no match)
    filterNone = lambda tuple: tuple[0] != None
    # discard the RE match objects
    keepFilenames = lambda tuple: tuple[1]
    roms = map(keepFilenames, filter(filterNone, hits))
    zips = map(keepFilenames, filter(filterNone, zipHits))
    return (roms, zips)

def create_rom_entry(playlist, romPath, baseName):
    """
    create_rom_entry(dict, str, str) -> str
    Create a playlist entry.
    The format is:
     Path
     Label
     Core library path (or DETECT)
     Core name (or DETECT)
     CRC
     Database
    """
    baseNameNoExt = os.path.splitext(baseName)[0]
    if playlist['QueryMame']:
        romTitle = get_mame_rom_name(baseNameNoExt)
    else:
        romTitle = baseNameNoExt
    return ("%s\n"
            "%s\n"
            "%s\n"
            "%s\n"
            "0|crc\n"
            "%s\n") % ( romPath,
                      romTitle,
                      playlist['CoreLib'],
                      playlist['CoreName'],
                      '%s.lpl' % playlist['PlaylistName']
    )

_MAME_NAME_RE = re.compile('"(.*)"')
def get_mame_rom_name(romName):
    # Garceful fallback if there's no match
    name = romName
    # raises CalledProcessError
    try:
        output = subprocess.check_output([mame, '-listfull', romName])
        match = _MAME_NAME_RE.search(output)
        if match:
            name = match.group(1)
    except subprocess.CalledProcessError:
        pass # just go ahead
    return name

def generate_playlist(playlist):
    """
    generate_playlist(dict) -> None

    Writes the given playlist to disk.
    """
    ( roms, zipRoms ) = scan_roms_dir(playlist)
    numRoms = len(roms)+len(zipRoms)
    pbar = ProgressBar(numRoms,sys.stderr)
    tmpfile = None
    try:
        pbar.start()
        #with open(playlist['PlaylistPath'], 'w') as lpl:
        with tempfile.NamedTemporaryFile(suffix='.lpl',delete=False) as lpl:
            tmpfile = lpl.name
            for baseName in roms:
                romPath = os.path.join(playlist['RomsPath'],baseName)
                lpl.write(create_rom_entry(playlist, romPath, baseName))
                pbar.step(baseName)
            if playlist['ScanZips']:
                # Same for zips
                for baseName in zipRoms:
                    pbar.step(baseName)
                    rom = os.path.join(playlist['RomsPath'],baseName)
                    with ZipFile(rom, 'r') as zRom:
                        info = zRom.infolist()
                        for compressedFile in info:
                            if playlist['SupportedExtensionsRE'].search(compressedFile.filename):
                                romPath = "%s#%s" % ( rom, compressedFile.filename )
                                lpl.write(create_rom_entry(playlist, romPath, compressedFile.filename))
            pbar.stop()
        if (os.path.exists(playlist['PlaylistPath'])):
            print('!! WARNING: About to overwrite playlist file %s' % playlist['PlaylistName'])
            try:
                raw_input('Press [ENTER] key to continue or CTRL+C to abort...')
                shutil.copyfile(tmpfile, playlist['PlaylistPath'])
            except KeyboardInterrupt:
                # Aborted with CTRL+C
                print('\nDiscarding new playlist\n')
    finally:
        pbar.stop()
        if tmpfile:
            os.unlink(tmpfile)

def main():
    global playlists
    load_config()
    print('The following playlists will be generated\n'
          'You\'ll be asked before overwriting them in case you want to back them up\n'
          'You can abort at any time with CTRL+C'
    )
    for playlist in playlists:
        # Ensure all required fields are present
        missing = []
        for field in ( 'RomsDir', 'CoreLib', 'CoreName', 'PlaylistName', 'SupportedExtensions'):
            if field not in playlist:
                missing.append(field)
        if missing:
            err('A playlist is missing the following required option(s): %s. It will be skipped'
                % ', '.join(missing))
            playlist['Disable'] = True
            continue
        print(' - %s' % playlist['PlaylistName'])
        # Take the chance to add some fields we'll use later:
        # - Regular expression to match file extensions
        playlist['SupportedExtensionsRE'] = re.compile('\\.(?:%s)$' % '|'.join(playlist['SupportedExtensions']))
        # - Full path to the ROMs dir
        playlist['RomsPath'] = os.path.join(romsDir, playlist['RomsDir'])
        # - Target playlist file
        playlist['PlaylistPath'] = os.path.join(retroarchDir, 'playlists', '%s.lpl' % playlist['PlaylistName'])
        # - Make the CoreLib field a full path, unless it's set to DETECT
        #   NOTE os.path.join handles absolute paths gracefully
        #   TODO: Does it on Windows too?
        if playlist['CoreLib'] != 'DETECT':
            playlist['CoreLib'] = os.path.join(coresDir, playlist['CoreLib'])
        # - Fill in any missing optional fields with default values so that we can assume they're defined
        if not 'ScanZips' in playlist:
            playlist['ScanZips'] = True
        if not 'QueryMame' in playlist:
            playlist['QueryMame'] = False
    print()

    # Remove any playlist we've disabled above
    playlists = [x for x in playlists if not 'Disable' in x]

    for playlist in playlists:
        # Fail gracefully if the paths don't exist
        if (not os.path.exists(playlist['RomsPath'])):
            err('Path "%s" does not exist!' % playlist['RomsPath'])
            continue

        generate_playlist(playlist)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        # Handle CTRL+C gracefully
        sys.exit(1)
