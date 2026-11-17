# AutoMapa Android Manager

Aplikacja desktopowa do zarządzania danymi AutoMapa (`pl.aqurat.automapa`) na urządzeniu z Androidem
przez ADB: kopie zapasowe i ich przywracanie, instalacja programu (APK) i wgrywanie map.
Interfejs jest wzorowany na Ustawieniach Windows 11 (jasny i ciemny motyw, zaokrąglone sekcje,
pasek boczny z zakładkami).

Autor: Piotr Deres ([likoton.pl](https://likoton.pl)). Licencja: GNU AGPL v3 (plik `LICENSE`).
English version: [README.md](README.md).

## Uruchamianie

- **Gotowa paczka (Windows):** rozpakuj `AutoMapaAndroidManager-<wersja>-windows.zip` i uruchom
  `AutoMapa Android Manager.exe`. Paczka zawiera Pythona, adb i obsługę 7z – nic nie trzeba doinstalowywać.
  Niepodpisany plik .exe może wywołać ostrzeżenie SmartScreen („Więcej informacji” → „Uruchom mimo to”).
- **Ze źródeł:** Python 3.10+ (Tkinter jest w standardowej instalacji; brak innych zależności).
  - Windows: `run.bat` albo `python main.py`
  - Linux / macOS: `./run.sh`. Aplikacja używa `adb` z `PATH` albo `tools/adb-linux` / `tools/adb-darwin` obok `main.py`
    (rozpakuje też `platform-tools-latest-linux.zip` / `-darwin.zip` umieszczone obok `main.py`).

Na telefonie włącz debugowanie USB (Opcje programisty) i zaakceptuj komunikat „Zezwolić na debugowanie USB?”
(zaznacz „Zawsze zezwalaj”, żeby nie pytało ponownie).

## Zakładki

- **Połączenie** – status urządzenia (USB i Wi-Fi), odświeżanie, instrukcja włączenia debugowania USB (gdy nie
  wykryto urządzenia), okno **Wi-Fi…** (tryb TCP/IP przez USB, połączenie z adresem, parowanie Android 11+)
  i **Wyłącz debugowanie…** (USB, opcje programisty, debugowanie bezprzewodowe).
- **Kopia zapasowa → Utwórz** – „Wszystko” (cały `/Android/obb/pl.aqurat.automapa/AutoMapa`) albo wybrane
  pozycje: Data, Settings, Colors, Routes, Trace, Sound, Maps, AutoMapa.lic – z rozmiarami. Dane trafiają do katalogu tymczasowego, są pakowane (7z/zip/tar.gz/tar.xz) i katalog tymczasowy jest usuwany. Dla „Wszystko” i „Dane użytkownika” można dołączyć dane z pamięci Androida (`Android/data/pl.aqurat.automapa` oraz, o ile to możliwe, prywatne dane przez `run-as` – best effort).
- **Kopia zapasowa → Przywróć** – całość lub wybrane pozycje; katalogi są tworzone albo zastępowane
  (opcja „Zastąp istniejące katalogi”). Przed przywracaniem aplikacja jest zatrzymywana (`am force-stop`).
- **Instalacja → Program** – wybór pliku APK i instalacja z nadpisaniem (`adb install -r -t -d -f --user <ID>`).
  Instalacja idzie jawnie dla użytkownika aktywnego na ekranie (`am get-current-user`), bo bez `--user` Android
  potrafi zainstalować aplikację dla innego konta i wtedy nie ma jej na liście aplikacji. Po instalacji aplikacja sprawdza widoczność pakietu i w razie potrzeby wykonuje `pm install-existing --user <ID>`. Odnośniki do automapa.pl (oficjalny APK) i apkpure.com (starsze wersje – po ich instalacji pobieranie map z poziomu aplikacji może nie działać).
- **Instalacja → Mapy** – wybór pliku ZIP z mapą (np. `aAM_Polska_2609_6.1774.zip`), wybór nośnika (pamięć
  wewnętrzna lub wykryta karta pamięci) i wgranie do `<nośnik>/Android/obb/pl.aqurat.automapa/AutoMapa/Maps/<Polska|Europe>`. Rodzaj mapy aplikacja rozpoznaje sama: najpierw po nazwie w pliku `version.info`, potem po zawartości archiwum (jeden plik `PL.all.c` = Polska, wiele plików `XX.all.c` = Europe), na końcu po nazwie pliku ZIP. Brakujące katalogi są tworzone, a istniejące pliki mapy – usuwane i wgrywane od nowa. Mapy oficjalne: https://www.automapa.pl/nawigacja/pobierz (W Androidzie `/sdcard` to wewnętrzna pamięć współdzielona, a nie karta pamięci.)
- **Ustawienia** – język (systemowy/polski/angielski), motyw (systemowy/jasny/ciemny), format archiwum, dziennik operacji włączony/wyłączony (domyślnie wyłączony; po włączeniu jest domyślnie ukryty i można go pokazać w pasku postępu). Konfiguracja: `%APPDATA%\AutoMapaManager\config.json` (Linux `~/.config`, macOS `~/Library/Application Support`).
- **O programie** – wersje aplikacji, ADB i 7-Zip, autor, licencje (jedno okno: AGPL aplikacji, wykaz dołączonych  składników i pełne teksty ich licencji), linki do wsparcia.

Gdy trwa operacja, na dole okna (obok przycisków Ustawienia i O programie) pojawia się pasek postępu: nazwa
operacji, bieżący komunikat, procenty i przycisk Anuluj. Jeśli urządzenie zostanie rozłączone w trakcie operacji, jest ona przerywana krótkim komunikatem zamiast surowych błędów adb. Komunikaty adb w oknie Wi-Fi są tłumaczone na język interfejsu. Przy zamykaniu aplikacja pyta, czy wyłączyć też serwer adb.

## Struktura archiwum kopii

```
AutoMapa/<Colors|Data|Maps|Routes|Settings|Sound|Trace|AutoMapa.lic>
AndroidData/          (opcjonalnie)
AppPrivate/run_as.tar (opcjonalnie)
backup_info.json
```

## Uwagi

- Podczas kopii, przywracania i wgrywania map potrzeba wolnego miejsca na dysku komputera (katalog tymczasowy powstaje obok archiwum / pliku ZIP).
- Uruchomiony serwer adb blokuje usunięcie lub aktualizację folderu programu – wybierz „Tak” przy zamykaniu albo wykonaj `adb kill-server`.
- Wyłączenie debugowania USB rozłącza telefon – ponowne włączenie jest możliwe tylko na urządzeniu.
- Zapis na kartę pamięci przez ADB zależy od wersji Androida i producenta; przy odmowie dostępu aplikacja pokaże błąd.
- Ustawienia, które AutoMapa zapisuje w samym systemie Android (SharedPreferences), nie są objęte kopią: Android nie udostępnia ich przez ADB, a są osobne dla każdego użytkownika Androida, więc po przywróceniu część ustawień może się różnić.

## Zawartość folderu

```
main.py, automapa_manager/   kod aplikacji
tools/adb-win/               adb.exe, AdbWinApi.dll, AdbWinUsbApi.dll, NOTICE.txt (Android SDK Platform-Tools)
tools/7zr.exe                7-Zip (GNU LGPL) dla formatu 7z
assets/                      ikony i logotypy
LICENSE, THIRD_PARTY_NOTICES.txt, licenses/   informacje licencyjne
run.bat, run.sh, requirements.txt             skrypty uruchomieniowe i opcjonalna zależność py7zr
```

Format 7z na Linuksie/macOS: zainstaluj `p7zip`/`7zz` lub `pip install py7zr`; bez tego dostępne są zip, tar.gz i tar.xz.

## Licencja

GNU Affero General Public License v3.0 – pełny tekst w pliku `LICENSE` oraz w oknie „O programie”.
Wykorzystuje Android Debug Bridge (Google; licencje w `tools/adb-win/NOTICE.txt`) i 7-Zip (GNU LGPL). Licencje wszystkich dołączonych składników: `THIRD_PARTY_NOTICES.txt` i folder `licenses/`.
