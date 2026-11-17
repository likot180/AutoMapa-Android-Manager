# AutoMapa Android Manager

Desktop app for managing the data of the AutoMapa Android app (`pl.aqurat.automapa`) over ADB:
backups and restores, installing the APK and uploading maps. The interface follows the look of
Windows 11 Settings (light/dark theme, rounded sections, sidebar navigation).

Author: Piotr Deres ([likoton.pl](https://likoton.pl)). License: GNU AGPL v3 (`LICENSE`).
Polish version: [README.pl.md](README.pl.md).

## Running

- **Packaged build (Windows):** unzip `AutoMapaAndroidManager-<version>-windows.zip` and run `AutoMapa Android Manager.exe`. Python, adb and 7z support are included; nothing needs to be installed.
  The unsigned `.exe` may trigger SmartScreen ("More info" → "Run anyway").
- **From source:** Python 3.10+ (Tkinter ships with the standard installation; no other dependencies).
  - Windows: `run.bat` or `python main.py`
  - Linux / macOS: `./run.sh`. The app uses `adb` from `PATH`, or `tools/adb-linux` / `tools/adb-darwin` next to `main.py` (it also unpacks `platform-tools-latest-linux.zip` / `-darwin.zip` placed next to `main.py`).

On the phone, enable USB debugging (Developer options) and accept the "Allow USB debugging" prompt (tick "Always allow" so it is not asked again).

## Tabs

- **Connection** – device status (USB and Wi-Fi), refresh, instructions for enabling USB debugging when no device is found, **Wi-Fi…** (TCP/IP mode over USB, connect by address, Android 11+ pairing) and
  **Turn off debugging…** (USB debugging, developer options, wireless debugging).
- **Backup → Create** – "Everything" (the whole `/Android/obb/pl.aqurat.automapa/AutoMapa`) or selected items:
  Data, Settings, Colors, Routes, Trace (the old name Trase is recognised too), Sound, Maps, AutoMapa.lic, with sizes.
  Data is staged in a temporary folder, compressed (7z / zip / tar.gz / tar.xz) and the folder is removed.
  For "Everything" and "User data" you can also include data from Android storage
  (`Android/data/pl.aqurat.automapa` and private data through `run-as`, best effort).
- **Backup → Restore** – everything or selected items; folders are created or replaced
  ("Replace existing folders"). The app is stopped (`am force-stop`) before restoring.
- **Install → Program** – choose an APK and install it over the existing one
  (`adb install -r -t -d -f --user <ID>`). The install targets the user active on screen (`am get-current-user`),
  because without `--user` Android may install the app for another account and it would be missing from the app
  list. Afterwards the package is verified and, if needed, repaired with `pm install-existing --user <ID>`.
  Links to automapa.pl (official APK) and apkpure.com (older versions; after installing those, downloading maps
  from inside the app may not work).
- **Install → Maps** – choose a map ZIP (e.g. `aAM_Polska_2609_6.1774.zip`), choose the storage (internal or a
  detected memory card) and upload to `<storage>/Android/obb/pl.aqurat.automapa/AutoMapa/Maps/<Polska|Europe>`.
  The map type is recognised automatically: by the name in `version.info`, then by archive contents (a single
  `PL.all.c` = Polska, several `XX.all.c` = Europe), finally by the ZIP file name. Missing folders are created and existing map files are deleted and replaced. Official maps: https://www.automapa.pl/nawigacja/pobierz
  (On Android `/sdcard` is the internal shared storage, not a memory card.)
- **Settings** – language (system/Polish/English), theme (system/light/dark), archive format, operation log
  on/off (off by default; when on, it is hidden by default and can be shown in the progress bar).
  The configuration is stored in `%APPDATA%\AutoMapaManager\config.json` (Linux `~/.config`, macOS `~/Library/Application Support`).
- **About** – app, ADB and 7-Zip versions, author, licenses (one window: the app's AGPL, the list of bundled
  components and their full license texts), support links.

While an operation runs, a progress bar appears at the bottom of the window (next to Settings and About):
operation name, current message, percentage and Cancel. If the device is disconnected during an operation, the
operation is aborted with a short message instead of raw adb errors. Messages returned by adb in the Wi-Fi dialog are translated into the interface language. On exit the app asks whether to stop the adb server too.

## Backup archive layout

```
AutoMapa/<Colors|Data|Maps|Routes|Settings|Sound|Trace|AutoMapa.lic>
AndroidData/          (optional)
AppPrivate/run_as.tar (optional)
backup_info.json
```

## Notes

- Backups, restores and map uploads need free disk space on the computer (the temporary folder is created next to
  the archive / ZIP file).
- A running adb server prevents deleting or updating the program folder. Choose "Yes" when closing the app, or run
  `adb kill-server`.
- Turning off USB debugging disconnects the phone; it can only be turned on again on the device.
- Writing to a memory card over ADB depends on the Android version and the manufacturer; on denial the app shows an error.
- Settings that AutoMapa stores inside Android itself (SharedPreferences) are not part of the backup: Android does not expose them over ADB, and they are separate for each Android user, so some settings may differ after a restore.

## Folder contents

```
main.py, automapa_manager/   application code
tools/adb-win/               adb.exe, AdbWinApi.dll, AdbWinUsbApi.dll, NOTICE.txt (Android SDK Platform-Tools)
tools/7zr.exe                7-Zip (GNU LGPL) for the 7z format
assets/                      icons and logos
LICENSE, THIRD_PARTY_NOTICES.txt, licenses/   license information
run.bat, run.sh, requirements.txt             launchers and the optional py7zr dependency
```

For the 7z format on Linux/macOS install `p7zip`/`7zz` or `pip install py7zr`; without it zip, tar.gz and tar.xz are available.

## License

GNU Affero General Public License v3.0 – full text in `LICENSE` and in the About window.
Uses Android Debug Bridge (Google; licenses in `tools/adb-win/NOTICE.txt`) and 7-Zip (GNU LGPL). Licenses of all bundled components: `THIRD_PARTY_NOTICES.txt` and the `licenses/` folder.
