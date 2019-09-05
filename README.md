# LPLmaker

This program will take ROMs and add them to a playlist for [RetroArch](https://www.retroarch.com) to use when they don't auto add.

Note the generated playlist will be automatically rewritten by RetroArch in the current format.

## Configuration

You can adjust the behaviour of the script by creating a configuration file, an example on which to base it is provided.
The script will look for a configuration file named `lplmaker.toml` on both `~/.config/` and the directory from which it is invoked, and will load both if found (`./lplmaker.toml` will be loaded after `~/.config/lplmaker.toml`, so it can be used to override some values).

For each playlist to be generated, the following fields **must** be defined:

- `RomsDir`: The directory, relative to RomsDir, where ROMs for this playlist are located.
- `CoreLib`: The library name for the appropriate core, usually `{name}_libretro.so`.
              Using `DETECT` will make RetroArch try to detect appropriate cores and let you pick.
- `CoreName`: The name of the core. Use `DETECT` to let RetroArch adjust it.
- `PlaylistName`: The name of the playlist.
                   Will be used as the filename (with `.lpl` extension) and displayed in the UI.
- `SupportedExtensions`: A list of valid extensions for this playlist.

And the following fields **can** be defined:

- `ScanZips`: (Optional) Set to 1 to look inside zip files for the extensions above.
            The core must have support for zipped ROM loading.
- `QueryMame`: (Optional) Set to 1 to query MAME for the ROM title (only makes sense on arcade ROMs).
               Requires MAME to be available.

### Zip file scanning

Zip files can be added to the playlists in two ways: either adding zip to list of extensions (SupportedExtensions), or enabling zip file scanning (ScanZips).

The latter is a better option in most cases, the exception being arcade systems.

## About

This is rewrite in Python of the Bash script created by [@jsbursik](https://github.com/jsbursik), which in turn was derived from the script written by u/ShiftyAxel on reddit.

See <https://github.com/outlyer-net/lplmaker-bash> for my initial Bash fork.

### Differences to the bash version

- **Note** Playlists' `RomsDir` was `RomDirs` in the Bash version.

