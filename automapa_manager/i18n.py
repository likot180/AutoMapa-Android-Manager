"""Tłumaczenia interfejsu (polski / angielski)."""
from __future__ import annotations

import os
import sys

S: dict[str, tuple[str, str]] = {}  # klucz -> (pl, en)


def _(key: str, pl: str, en: str) -> None:
    S[key] = (pl, en)


# --- ogólne ---------------------------------------------------------------
_("app_title", "AutoMapa Android Manager", "AutoMapa Android Manager")
_("btn_yes", "Tak", "Yes")
_("btn_no", "Nie", "No")
_("nav_connection", "Połączenie", "Connection")
_("nav_backup", "Kopia zapasowa", "Backup")
_("nav_create", "Utwórz", "Create")
_("nav_restore", "Przywróć", "Restore")
_("nav_install", "Instalacja", "Install")
_("nav_settings", "Ustawienia", "Settings")
_("page_connection", "Połączenie", "Connection")
_("page_create", "Utwórz kopię zapasową", "Create a backup")
_("page_restore", "Przywróć kopię zapasową", "Restore a backup")
_("page_install", "Instalacja", "Installation")
_("page_settings", "Ustawienia", "Settings")
_("sidebar_no_device", "Brak urządzenia", "No device")
_("btn_refresh", "Odśwież", "Refresh")
_("btn_wifi", "Wi-Fi…", "Wi-Fi…")
_("btn_disable", "Wyłącz debugowanie…", "Turn off debugging…")
_("btn_browse", "Przeglądaj…", "Browse…")
_("btn_cancel", "Anuluj", "Cancel")
_("btn_close", "Zamknij", "Close")
_("btn_ok", "OK", "OK")
_("error", "Błąd", "Error")
_("info", "Informacja", "Information")
_("confirm", "Potwierdzenie", "Confirmation")

# --- stan urządzenia ------------------------------------------------------
_("st_checking", "Sprawdzanie urządzenia…", "Checking device…")
_("st_adb_missing_title", "Nie znaleziono programu adb", "adb was not found")
_("st_adb_missing_detail",
  "Umieść platform-tools w folderze tools/adb-win (Windows), tools/adb-linux lub tools/adb-darwin obok aplikacji albo dodaj adb do zmiennej PATH.",
  "Put platform-tools in the tools/adb-win (Windows), tools/adb-linux or tools/adb-darwin folder next to the app, or add adb to PATH.")
_("st_adb_error_title", "Błąd programu adb", "adb error")
_("st_nodev_title", "Nie wykryto urządzenia", "No device detected")
_("st_nodev_short",
  "Podłącz telefon kablem USB albo połącz się przez Wi-Fi, a następnie kliknij „Odśwież”.",
  "Connect the phone with a USB cable or connect over Wi-Fi, then click “Refresh”.")
_("instr_title", "Jak włączyć debugowanie USB", "How to enable USB debugging")
_("st_nodev_detail",
  "Podłącz telefon kablem USB (kabel musi przesyłać dane) i włącz debugowanie USB:\n\n"
  "1.  Ustawienia → Informacje o telefonie → dotknij 7 razy „Numer kompilacji”, aby włączyć opcje programisty.\n"
  "2.  Ustawienia → System → Opcje programisty → włącz „Debugowanie USB”.\n"
  "3.  Po podłączeniu kabla wybierz tryb USB „Przesyłanie plików” i zaakceptuj okno „Zezwolić na debugowanie USB?” "
  "(zaznacz „Zawsze zezwalaj z tego komputera”).",
  "Connect the phone with a USB cable (it must support data) and enable USB debugging:\n\n"
  "1.  Settings → About phone → tap “Build number” 7 times to enable Developer options.\n"
  "2.  Settings → System → Developer options → turn on “USB debugging”.\n"
  "3.  After connecting the cable choose the USB mode “File transfer” and accept the “Allow USB debugging?” prompt "
  "(tick “Always allow from this computer”).")
_("instr_wifi_title", "Debugowanie przez Wi-Fi (Android 11+)", "Debugging over Wi-Fi (Android 11+)")
_("st_nodev_wifi",
  "Opcje programisty → „Debugowanie bezprzewodowe”, następnie użyj przycisku „Wi-Fi…” powyżej.",
  "Developer options → “Wireless debugging”, then use the “Wi-Fi…” button above.")
_("st_unauth_title", "Wymagana akceptacja na urządzeniu", "Approval required on the device")
_("st_unauth_detail",
  "Odblokuj telefon i zaakceptuj okno „Zezwolić na debugowanie USB?”. Zaznacz „Zawsze zezwalaj z tego komputera”, "
  "aby nie powtarzać tego przy każdym połączeniu. Jeśli okno się nie pojawia: odłącz i podłącz kabel albo w Opcjach "
  "programisty użyj „Odwołaj autoryzacje debugowania USB”.",
  "Unlock the phone and accept the “Allow USB debugging?” prompt. Tick “Always allow from this computer” so you are "
  "not asked every time. If the prompt does not appear: replug the cable or use “Revoke USB debugging authorizations” "
  "in Developer options.")
_("st_offline_title", "Urządzenie jest offline", "Device is offline")
_("st_offline_detail",
  "Odłącz i ponownie podłącz kabel USB, a jeśli to nie pomoże, wyłącz i włącz debugowanie USB na telefonie.",
  "Replug the USB cable; if that does not help, turn USB debugging off and on again on the phone.")
_("st_perm_title", "Brak uprawnień do urządzenia", "No permission to access the device")
_("st_perm_detail",
  "Sprawdź kabel, tryb USB telefonu i (na Linuksie) reguły udev dla urządzeń Android.",
  "Check the cable, the phone's USB mode and (on Linux) the udev rules for Android devices.")
_("st_other_title", "Stan urządzenia: {state}", "Device state: {state}")
_("st_ready_title", "Połączono: {name}", "Connected: {name}")
_("st_ready_detail", "Android {release} (API {sdk}) · {transport} · {serial}", "Android {release} (API {sdk}) · {transport} · {serial}")
_("transport_usb", "USB", "USB")
_("transport_wifi", "Wi-Fi", "Wi-Fi")
_("wifi_on", "Debugowanie Wi-Fi: włączone (adres {ip}).", "Wi-Fi debugging: enabled (address {ip}).")
_("wifi_on_noip", "Debugowanie Wi-Fi: włączone.", "Wi-Fi debugging: enabled.")
_("wifi_possible",
  "Debugowanie Wi-Fi: urządzenie jest w sieci ({ip}) – użyj „Wi-Fi…”, aby połączyć się bezprzewodowo.",
  "Wi-Fi debugging: the device is on the network ({ip}) – use “Wi-Fi…” to connect wirelessly.")
_("wifi_none", "Debugowanie Wi-Fi: telefon nie jest połączony z siecią Wi-Fi.", "Wi-Fi debugging: the phone is not connected to a Wi-Fi network.")
_("device_label", "Urządzenie:", "Device:")

# --- kopia: pozycje -------------------------------------------------------
_("item_data", "Dane użytkownika", "User data")
_("item_settings", "Ustawienia", "Settings")
_("item_colors", "Kolory mapy", "Map colors")
_("item_routes", "Trasy", "Routes")
_("item_trase", "Ślady GPS", "GPS tracks")
_("item_sound", "Lektorzy", "Voices")
_("item_maps", "Mapy", "Maps")
_("item_license", "Licencja", "License")
_("size_missing", "brak", "missing")
_("size_scanning", "…", "…")

_("grp_backup", "Co skopiować", "What to copy")
_("grp_dest", "Miejsce zapisu", "Save location")
_("grp_progress", "Postęp", "Progress")
_("rb_all", "Wszystko (cały katalog AutoMapa)", "Everything (the whole AutoMapa folder)")
_("rb_selected", "Wybrane pozycje:", "Selected items:")
_("lbl_total_extra", "Dane aplikacji w pamięci Android (Android/data): {size}", "App data in Android storage (Android/data): {size}")
_("chk_extra", "Dołącz dane aplikacji z pamięci Android (jeśli dostępne)", "Include app data from Android storage (if available)")
_("extra_hint",
  "Dotyczy „Wszystko” i „Dane użytkownika”. Kopiowany jest katalog Android/data/pl.aqurat.automapa (pamięć podręczna) oraz "
  "– tylko dla aplikacji debugowalnych – prywatne dane (run-as). Android często blokuje dostęp do tych danych; brak dostępu nie przerywa kopii.",
  "Applies to “Everything” and “User data”. Copies Android/data/pl.aqurat.automapa (cache) and – for debuggable apps "
  "only – private data (run-as). Android often blocks access to this data; missing access does not abort the backup.")
_("lbl_dest", "Folder docelowy:", "Destination folder:")
_("lbl_format", "Format archiwum: {fmt} (zmiana w Ustawieniach)", "Archive format: {fmt} (change in Settings)")
_("btn_backup", "Utwórz kopię", "Create backup")
_("btn_rescan", "Odśwież rozmiary", "Refresh sizes")

# --- przywracanie ---------------------------------------------------------
_("grp_restore", "Przywróć kopię", "Restore a backup")
_("lbl_archive", "Plik kopii:", "Backup file:")
_("btn_load", "Wczytaj zawartość", "Load contents")
_("restore_hint", "Wybierz plik kopii (.7z, .zip, .tar.gz, .tar.xz), aby zobaczyć jego zawartość.", "Choose a backup file (.7z, .zip, .tar.gz, .tar.xz) to see its contents.")
_("rb_r_all", "Przywróć wszystko, co jest w kopii", "Restore everything in the backup")
_("rb_r_sel", "Przywróć wybrane pozycje:", "Restore selected items:")
_("chk_r_extra", "Przywróć także dane aplikacji (Android/data)", "Also restore app data (Android/data)")
_("chk_replace", "Zastąp istniejące katalogi (usuń przed przywróceniem)", "Replace existing folders (delete before restoring)")
_("btn_restore", "Przywróć", "Restore")
_("content_summary", "Zawartość kopii – razem: {size}", "Backup contents – total: {size}")
_("content_others", "Inne pozycje: {names}", "Other entries: {names}")
_("content_extra", "Dane aplikacji w kopii: {what}", "App data in backup: {what}")
_("content_empty", "W archiwum nie znaleziono danych AutoMapa.", "No AutoMapa data was found in the archive.")

# --- postęp i komunikaty --------------------------------------------------
_("st_idle", "Gotowe.", "Ready.")
_("p_scanning", "Sprawdzanie zawartości urządzenia…", "Checking device contents…")
_("p_pull", "Kopiowanie z urządzenia: {name} ({done} / {total})", "Copying from device: {name} ({done} / {total})")
_("p_archive", "Pakowanie: {name}", "Archiving: {name}")
_("p_extract", "Rozpakowywanie archiwum…", "Extracting archive…")
_("p_push", "Wysyłanie na urządzenie: {name} ({n}/{count})", "Sending to device: {name} ({n}/{count})")
_("p_done", "Zakończono.", "Done.")
_("p_loading", "Wczytywanie archiwum…", "Reading archive…")
_("log_pull", "Kopiowanie z urządzenia: {name}", "Copying from device: {name}")
_("log_item_missing", "Pominięto – brak na urządzeniu: {name}", "Skipped – not on the device: {name}")
_("log_archiving", "Pakowanie ({fmt})…", "Archiving ({fmt})…")
_("log_archive_done", "Utworzono archiwum: {path} ({size})", "Archive created: {path} ({size})")
_("log_extra_data", "Próba kopiowania Android/data…", "Trying to copy Android/data…")
_("log_extra_data_fail", "Android/data niedostępne ({why}).", "Android/data is not accessible ({why}).")
_("log_extra_private", "Próba kopiowania prywatnych danych aplikacji (run-as)…", "Trying to copy private app data (run-as)…")
_("log_extra_private_fail", "Prywatne dane niedostępne (aplikacja nie jest debugowalna).", "Private data is not accessible (the app is not debuggable).")
_("log_extracting", "Rozpakowywanie kopii…", "Extracting backup…")
_("log_force_stop", "Zatrzymywanie aplikacji AutoMapa na urządzeniu…", "Stopping AutoMapa on the device…")
_("log_push", "Wysyłanie: {name}", "Sending: {name}")
_("log_restore_extra_data", "Przywracanie Android/data…", "Restoring Android/data…")
_("log_restore_private", "Przywracanie prywatnych danych (run-as)…", "Restoring private data (run-as)…")
_("log_restore_extra_fail", "Nie udało się przywrócić danych dodatkowych: {why}", "Could not restore the extra data: {why}")
_("sysprefs_note", "Uwaga: ustawienia, które AutoMapa zapisuje w systemie Android (SharedPreferences), nie są objęte kopią zapasową – Android nie udostępnia ich przez ADB. Są one osobne dla każdego użytkownika Androida, więc po przywróceniu część ustawień może się różnić.", "Note: settings that AutoMapa stores in the Android system (SharedPreferences) are not part of the backup – Android does not expose them over ADB. They are separate for each Android user, so some settings may differ after a restore.")
_("err_disconnected", "Operacja przerwana. Urządzenie zostało rozłączone. Podłącz je ponownie i spróbuj jeszcze raz.", "Operation aborted. The device was disconnected. Reconnect it and try again.")
_("log_cancelled", "Operacja anulowana.", "Operation cancelled.")
_("log_failed", "Błąd: {err}", "Error: {err}")
_("op_backup", "Tworzenie kopii…", "Creating backup…")
_("op_restore", "Przywracanie…", "Restoring…")
_("done_backup", "Kopia została utworzona:\n{path}\n\nRozmiar: {size}", "The backup has been created:\n{path}\n\nSize: {size}")
_("done_restore", "Przywrócono pozycji: {n}.", "Items restored: {n}.")
_("err_no_dir", "Na urządzeniu nie ma katalogu {path}.", "The folder {path} does not exist on the device.")
_("err_nothing", "Brak pozycji do wykonania operacji.", "Nothing to process.")
_("err_space", "Za mało miejsca na dysku: potrzeba ok. {need}, wolne {free}.", "Not enough disk space: about {need} needed, {free} free.")
_("err_pull_failed", "Nie udało się skopiować: {name}.", "Could not copy: {name}.")
_("err_bad_archive", "Archiwum ma nieoczekiwaną strukturę.", "The archive has an unexpected structure.")
_("err_no_device", "Brak gotowego urządzenia. Podłącz telefon i zaakceptuj debugowanie.", "No ready device. Connect the phone and accept debugging.")
_("err_no_dest", "Wybierz folder docelowy.", "Choose a destination folder.")
_("err_no_items", "Zaznacz co najmniej jedną pozycję.", "Select at least one item.")
_("err_no_file", "Wybierz istniejący plik kopii.", "Choose an existing backup file.")
_("err_busy", "Poczekaj na zakończenie bieżącej operacji.", "Wait for the current operation to finish.")
_("confirm_restore",
  "Przywrócić dane na urządzenie {name}?\n\nPozycje: {items}\n{replace}\nAplikacja AutoMapa zostanie zatrzymana.",
  "Restore data to the device {name}?\n\nItems: {items}\n{replace}\nThe AutoMapa app will be stopped.")
_("confirm_replace_yes", "Istniejące katalogi zostaną USUNIĘTE i zastąpione.", "Existing folders will be DELETED and replaced.")
_("confirm_replace_no", "Istniejące pliki zostaną nadpisane (reszta zostanie zachowana).", "Existing files will be overwritten (the rest is kept).")
_("all_items", "wszystko z kopii", "everything in the backup")
_("confirm_close", "Trwa operacja. Zamknąć aplikację i ją przerwać?", "An operation is in progress. Close the app and abort it?")
_("confirm_close_adb",
  "Czy wyłączyć również serwer adb?\n\nTak – zamknij aplikację i wyłącz adb (zerwie to połączenia, także Wi-Fi).\n"
  "Nie – zamknij aplikację, adb zostanie uruchomiony.\nAnuluj – nie zamykaj aplikacji.",
  "Also shut down the adb server?\n\nYes – close the app and shut down adb (this drops connections, Wi-Fi ones too).\n"
  "No – close the app and leave adb running.\nCancel – do not close the app.")

# --- Wi-Fi ----------------------------------------------------------------
_("wifi_title", "Debugowanie przez Wi-Fi", "Debugging over Wi-Fi")
_("wifi_usb_head", "1. Włącz przez USB (dowolny Android)", "1. Enable via USB (any Android)")
_("wifi_usb_intro",
  "Gdy telefon jest podłączony kablem i autoryzowany, aplikacja przełączy go w tryb TCP/IP i połączy się przez Wi-Fi. "
  "Telefon i komputer muszą być w tej samej sieci.",
  "While the phone is connected by cable and authorized, the app switches it to TCP/IP mode and connects over Wi-Fi. "
  "The phone and the computer must be on the same network.")
_("wifi_usb_none", "Brak urządzenia podłączonego kablem USB.", "No device connected by USB cable.")
_("wifi_usb_ip", "Adres IP telefonu: {ip}", "Phone IP address: {ip}")
_("wifi_usb_noip", "Telefon nie ma adresu Wi-Fi – połącz go z siecią.", "The phone has no Wi-Fi address – connect it to a network.")
_("wifi_port", "Port:", "Port:")
_("wifi_enable", "Włącz i połącz", "Enable and connect")
_("wifi_conn_head", "2. Połącz z adresem (Debugowanie bezprzewodowe)", "2. Connect to an address (Wireless debugging)")
_("wifi_conn_hint", "Adres IP i port widać w Opcje programisty → Debugowanie bezprzewodowe.", "The IP address and port are shown in Developer options → Wireless debugging.")
_("wifi_connect", "Połącz", "Connect")
_("wifi_disconnect", "Rozłącz", "Disconnect")
_("wifi_pair_head", "3. Sparuj (Android 11+, jednorazowo)", "3. Pair (Android 11+, one time)")
_("wifi_pair_hint", "W „Debugowanie bezprzewodowe” wybierz „Sparuj urządzenie za pomocą kodu” i wpisz adres oraz kod.", "In “Wireless debugging” choose “Pair device with pairing code” and enter the address and code.")
_("wifi_pair_addr", "Adres parowania (IP:port):", "Pairing address (IP:port):")
_("wifi_pair_code", "Kod:", "Code:")
_("wifi_pair", "Sparuj", "Pair")
_("wifi_working", "Trwa wykonywanie…", "Working…")
_("wifi_need_addr", "Podaj adres w formacie IP:port.", "Enter an address as IP:port.")

# --- komunikaty adb (okno Wi-Fi) -------------------------------------------
_("adbmsg_connected", "Połączono z {addr}.", "Connected to {addr}.")
_("adbmsg_already", "Urządzenie jest już połączone: {addr}.", "The device is already connected: {addr}.")
_("adbmsg_disconnected", "Rozłączono: {addr}.", "Disconnected: {addr}.")
_("adbmsg_disconnected_all", "Rozłączono wszystkie urządzenia połączone przez sieć.", "Disconnected all network devices.")
_("adbmsg_no_such_device", "Brak urządzenia o adresie {addr} (nie jest połączone).", "No device at {addr} (not connected).")
_("adbmsg_connect_failed", "Nie udało się połączyć z {addr}.{reason}", "Could not connect to {addr}.{reason}")
_("adbmsg_reason", "Powód: {reason}", "Reason: {reason}")
_("adbmsg_auth", "Urządzenie {addr} odrzuciło połączenie – najpierw je sparuj (Android 11+) albo zaakceptuj okno debugowania na telefonie.",
  "The device {addr} rejected the connection – pair it first (Android 11+) or accept the debugging prompt on the phone.")
_("adbmsg_paired", "Sparowano z {addr}.", "Paired with {addr}.")
_("adbmsg_pair_wrong", "Parowanie nie powiodło się: nieprawidłowy kod parowania albo połączenie zostało przerwane.",
  "Pairing failed: wrong pairing code or the connection was dropped.")
_("adbmsg_pair_failed", "Parowanie nie powiodło się.{reason}", "Pairing failed.{reason}")
_("adbmsg_tcpip", "Telefon przełączony w tryb TCP/IP (port {port}).", "The phone was switched to TCP/IP mode (port {port}).")
_("adbmsg_unauthorized", "Urządzenie nie jest autoryzowane – zaakceptuj okno na telefonie („Zawsze zezwalaj”).",
  "The device is not authorized – accept the prompt on the phone (“Always allow”).")
_("adbmsg_offline", "Urządzenie jest offline.", "The device is offline.")
_("adbmsg_no_devices", "Nie wykryto żadnego urządzenia.", "No device was detected.")
_("adbmsg_many_devices", "Wykryto kilka urządzeń – wybierz jedno.", "Several devices were detected – choose one.")

# --- stopka: bieżąca operacja ----------------------------------------------
_("footer_cancel", "Anuluj", "Cancel")

# --- wyłączanie debugowania -----------------------------------------------
_("dis_title", "Wyłącz debugowanie na urządzeniu", "Turn off debugging on the device")
_("dis_intro",
  "Zmiana jest wykonywana przez ADB. Po wyłączeniu debugowania USB połączenie z komputerem zostanie utracone – "
  "aby je przywrócić, trzeba ponownie włączyć debugowanie w telefonie.",
  "The change is made through ADB. After USB debugging is turned off the connection is lost – to restore it you "
  "must enable debugging again on the phone.")
_("dis_wifi", "Wyłącz debugowanie bezprzewodowe (Wi-Fi)", "Turn off wireless (Wi-Fi) debugging")
_("dis_dev", "Wyłącz opcje programisty", "Turn off Developer options")
_("dis_usb", "Wyłącz debugowanie USB", "Turn off USB debugging")
_("dis_run", "Wyłącz", "Turn off")
_("dis_done", "Zastosowano:\n{lines}", "Applied:\n{lines}")
_("dis_none", "Zaznacz co najmniej jedną opcję.", "Select at least one option.")
_("dis_fail", "{name}: błąd {err}", "{name}: error {err}")
_("dis_ok", "{name}: wyłączono", "{name}: turned off")

# --- ustawienia -----------------------------------------------------------
_("grp_appearance", "Wygląd", "Appearance")
_("lbl_language", "Język:", "Language:")
_("lbl_theme", "Motyw:", "Theme:")
_("opt_system", "Systemowy", "System")
_("opt_pl", "Polski", "Polski")
_("opt_en", "English", "English")
_("theme_light", "Jasny", "Light")
_("theme_dark", "Ciemny", "Dark")
_("grp_archive", "Kopia zapasowa", "Backup")
_("set_language_desc", "Język interfejsu aplikacji", "Language of the app interface")
_("set_theme_desc", "Wygląd okna aplikacji", "Appearance of the app window")
_("set_format_desc", "Format archiwum tworzonej kopii zapasowej", "Archive format of the created backup")

# --- instalacja APK -------------------------------------------------------
_("inst_official_text", "Oficjalny plik instalacyjny programu AutoMapa (APK) znajduje się na stronie:",
  "The official AutoMapa installation file (APK) is available at:")
_("inst_older_text", "Starsze wersje są dostępne na stronie:", "Older versions are available at:")
_("inst_older_warning",
  "Uwaga: po zainstalowaniu starszej wersji może nie być dostępna możliwość pobrania mapy z poziomu aplikacji.",
  "Note: after installing an older version, downloading a map from within the app may not be available.")
_("inst_apk", "Plik instalacyjny (APK):", "Installation file (APK):")
_("inst_choose", "Wybierz plik APK, aby go zainstalować na urządzeniu.", "Choose an APK file to install it on the device.")
_("inst_file_info", "{name} · {size}", "{name} · {size}")
_("inst_command", "Polecenie: {cmd}", "Command: {cmd}")
_("inst_overwrite",
  "Zainstalowana wersja zostanie nadpisana (dozwolone także obniżenie wersji); dane aplikacji pozostają na urządzeniu.",
  "The installed version will be overwritten (downgrades are allowed too); app data stays on the device.")
_("btn_install", "Zainstaluj", "Install")
_("op_install", "Instalowanie…", "Installing…")
_("p_install", "Instalowanie: {name}", "Installing: {name}")
_("done_install", "Instalacja zakończona powodzeniem.", "Installation completed successfully.")
_("err_apk", "Wybierz istniejący plik z rozszerzeniem .apk.", "Choose an existing file with the .apk extension.")
_("err_install", "Instalacja nie powiodła się:\n{out}", "Installation failed:\n{out}")
_("confirm_install", "Zainstalować {name} na urządzeniu {dev}?\n\nIstniejąca wersja AutoMapy zostanie nadpisana.",
  "Install {name} on the device {dev}?\n\nThe existing version of the app will be overwritten.")
_("log_install_user", "Instalacja dla bieżącego użytkownika Androida (ID {user}).",
  "Installing for the current Android user (ID {user}).")
_("log_install_existing", "Aplikacja nie jest widoczna dla użytkownika {user} – dodaję ją (pm install-existing).",
  "The app is not visible to user {user} – adding it (pm install-existing).")
_("err_install_not_visible",
  "Pakiet został zainstalowany, ale nie jest dostępny dla bieżącego użytkownika Androida (ID {user}), więc nie pojawi się na liście aplikacji. "
  "Sprawdź w Ustawieniach telefonu, czy nie ma ograniczeń instalacji aplikacji (konta, profil służbowy).",
  "The package was installed but is not available to the current Android user (ID {user}), so it will not appear in the app list. "
  "Check the phone settings for app installation restrictions (accounts, work profile).")
_("inst_hint_signature",
  "Podpis tej wersji różni się od zainstalowanej. Aby ją zainstalować, trzeba najpierw odinstalować obecną AutoMapę "
  "(dane w pamięci urządzenia w katalogu Android/obb mogą zostać usunięte – zrób kopię zapasową).",
  "This version is signed differently from the installed one. To install it you must first uninstall the current app "
  "(data in Android/obb may be deleted – make a backup first).")
_("inst_hint_downgrade", "System nie zezwala na obniżenie wersji tej aplikacji.", "The system does not allow downgrading this app.")
_("inst_hint_storage", "Brak miejsca w pamięci urządzenia.", "Not enough storage on the device.")
_("inst_hint_parse", "Plik APK jest uszkodzony lub niepełny.", "The APK file is damaged or incomplete.")
_("inst_hint_sdk", "Ta wersja wymaga nowszego Androida.", "This version requires a newer Android.")
_("inst_hint_restricted", "Instalacja przez USB jest zablokowana na telefonie – włącz „Zezwalaj na instalację przez USB” w Opcjach programisty.",
  "Installation over USB is blocked on the phone – enable “Install via USB” in Developer options.")
_("lbl_arch_format", "Format archiwum:", "Archive format:")
_("fmt_auto", "Automatycznie ({fmt})", "Automatic ({fmt})")
_("grp_adb", "ADB", "ADB")
_("lbl_adb_path", "Używany adb:", "adb in use:")
_("adb_not_found", "(nie znaleziono)", "(not found)")
_("err_busy_settings", "Zmiany wyglądu są możliwe po zakończeniu operacji.", "Appearance changes are possible once the operation finishes.")


# --- nawigacja: podstrony, O programie ------------------------------------
_("nav_install_prog", "Program", "App")
_("nav_install_maps", "Mapy", "Maps")
_("nav_about", "O programie", "About")
_("page_prog", "Instalacja programu", "Install the app")
_("page_maps", "Wgrywanie map", "Upload maps")
_("page_about", "O programie", "About")

# --- O programie ----------------------------------------------------------
_("about_version", "Wersja aplikacji", "App version")
_("about_adb", "Wersja ADB", "ADB version")
_("about_7zip", "Wersja 7-Zip", "7-Zip version")
_("about_author", "Autor", "Author")
_("about_source", "Kod źródłowy", "Source code")
_("about_license", "Licencje", "Licenses")
_("about_license_name", "GNU AGPL v3 i licencje składników", "GNU AGPL v3 and component licenses")
_("btn_read_license", "Przeczytaj licencje", "Read the licenses")
_("about_donate",
  "Jeśli podoba Ci się to, co robię, rozważ niewielką darowiznę, aby wesprzeć dalszy rozwój:",
  "If you like what I do, please consider a small donation to support further development:")
_("about_thanks", "Dziękuję!", "Thank you!")
_("about_third",
  "Wykorzystuje: Android Debug Bridge (Google) i 7-Zip (GNU LGPL).",
  "Uses: Android Debug Bridge (Google) and 7-Zip (GNU LGPL).")
_("license_title", "Licencje", "Licenses")
_("license_missing", "Nie znaleziono pliku licencji. Tekst licencji: https://www.gnu.org/licenses/agpl-3.0.txt",
  "The license file was not found. License text: https://www.gnu.org/licenses/agpl-3.0.txt")

# --- konsola --------------------------------------------------------------
_("set_console", "Dziennik operacji", "Operation log")
_("set_console_desc", "Pokazuje szczegółowy przebieg operacji pod paskiem postępu", "Shows the detailed course of operations below the progress bar")
_("opt_on", "Włączony", "Enabled")
_("opt_off", "Wyłączony", "Disabled")
_("console_hide", "Ukryj dziennik", "Hide log")
_("console_show", "Pokaż dziennik", "Show log")

# --- wgrywanie map --------------------------------------------------------
_("maps_official", "Oficjalne mapy Polski i Europy są dostępne do pobrania na stronie:",
  "Official maps of Poland and Europe can be downloaded at:")
_("maps_compat_note", "Uwaga: nie każda mapa jest kompatybilna z zainstalowaną wersją programu AutoMapa. Starsza wersja programu może nie otworzyć nowszej mapy (i odwrotnie) – w razie problemów zainstaluj wersję programu odpowiednią dla mapy.", "Note: not every map is compatible with the installed version of AutoMapa. An older app version may not open a newer map (and vice versa) – if you run into problems, install the app version that matches the map.")
_("maps_link_text", "automapa.pl/nawigacja/pobierz", "automapa.pl/nawigacja/pobierz")
_("maps_file", "Plik mapy (ZIP):", "Map file (ZIP):")
_("maps_choose", "Wybierz plik ZIP z mapą, np. aAM_Polska_2609_6.1774.zip lub aAM_Europe_2609_6.1776.zip.",
  "Choose a ZIP file with the map, e.g. aAM_Polska_2609_6.1774.zip or aAM_Europe_2609_6.1776.zip.")
_("maps_zip_error", "Nie można odczytać archiwum ZIP: {err}", "Cannot read the ZIP archive: {err}")
_("maps_storage", "Nośnik instalacji", "Installation storage")
_("storage_internal", "Pamięć wewnętrzna (wolne: {free})", "Internal storage (free: {free})")
_("storage_sd", "Karta pamięci {id} (wolne: {free})", "Memory card {id} (free: {free})")
_("storage_where_internal", "Pamięć wewnętrzna", "Internal storage")
_("storage_where_sd", "Karta pamięci {id}", "Memory card {id}")
_("storage_loading", "Pamięć wewnętrzna", "Internal storage")
_("storage_no_sd", "Karta pamięci nie została wykryta lub nie jest dostępna – użyta zostanie pamięć wewnętrzna.",
  "No memory card was detected or it is not available – internal storage will be used.")
_("storage_sd_found", "Wykryto kartę pamięci – możesz ją wybrać jako nośnik.", "A memory card was detected – you can choose it as the storage.")
_("maps_dest", "Katalog docelowy", "Target folder")
_("maps_file_info", "Plików: {count} · po rozpakowaniu {size}", "Files: {count} · unpacked {size}")
_("maps_recognized", "Rozpoznano mapę: {name} (na podstawie: {source})", "Recognized map: {name} (based on: {source})")
_("maps_src_version", "pliku version.info", "version.info")
_("maps_src_files", "zawartości archiwum", "archive contents")
_("maps_src_filename", "nazwy pliku", "file name")
_("maps_not_recognized",
  "Nie rozpoznano rodzaju mapy (Polska / Europe) na podstawie pliku version.info, zawartości archiwum ani nazwy pliku. "
  "Wybierz oficjalny plik mapy ze strony automapa.pl.",
  "The map type (Polska / Europe) could not be recognized from version.info, the archive contents or the file name. "
  "Choose an official map file from automapa.pl.")
_("err_map_name", "Nie rozpoznano rodzaju mapy – nie można ustalić katalogu docelowego.",
  "The map type was not recognized – the target folder cannot be determined.")
_("maps_target", "Cel: {path}", "Target: {path}")
_("maps_target_label", "Katalog docelowy mapy:", "Map target folder:")
_("maps_replace_warn", "Jeśli katalog już istnieje, jego zawartość zostanie usunięta i zastąpiona nową.",
  "If the folder already exists, its contents will be deleted and replaced with the new ones.")
_("btn_maps_install", "Wgraj mapę", "Upload map")
_("op_maps", "Wgrywanie mapy…", "Uploading the map…")
_("p_map_extract", "Rozpakowywanie mapy…", "Extracting the map…")
_("p_map_push", "Wysyłanie mapy na urządzenie ({done} / {total})", "Sending the map to the device ({done} / {total})")
_("log_map_remove", "Usuwanie poprzedniej wersji: {path}", "Removing the previous version: {path}")
_("log_map_push", "Wysyłanie do: {path}", "Sending to: {path}")
_("log_map_done", "Wysłano {count} plików ({size}).", "Sent {count} files ({size}).")
_("done_maps", "Mapa została wgrana do:\n{path}", "The map has been uploaded to:\n{path}")
_("err_map_zip", "Wybierz istniejący plik ZIP z mapą.", "Choose an existing ZIP file with the map.")
_("err_map_empty", "Archiwum ZIP jest puste.", "The ZIP archive is empty.")
_("err_map_space_dev", "Za mało miejsca na urządzeniu: potrzeba {need}, dostępne {free}.",
  "Not enough space on the device: {need} needed, {free} available.")
_("err_map_storage", "Nie można zapisać na wybranym nośniku: {err}", "Cannot write to the selected storage: {err}")
_("err_map_verify", "Po wysłaniu na urządzeniu jest {got}, a oczekiwano {need}. Spróbuj ponownie.",
  "After sending, the device holds {got} but {need} was expected. Try again.")
_("confirm_maps",
  "Wgrać mapę {name} na urządzenie {dev}?\n\nCel: {path}\nIstniejące pliki w tym katalogu zostaną usunięte, a aplikacja AutoMapa zatrzymana.",
  "Upload the map {name} to the device {dev}?\n\nTarget: {path}\nExisting files in this folder will be deleted and the AutoMapa app stopped.")


class I18n:
    def __init__(self, language: str = "system"):
        self.set_language(language)

    def set_language(self, language: str) -> None:
        self.code = system_language() if language == "system" else language
        self._idx = 1 if self.code == "en" else 0

    @property
    def decimal_comma(self) -> bool:
        return self.code == "pl"

    def t(self, key: str, **kw) -> str:
        pair = S.get(key)
        text = pair[self._idx] if pair else key
        return text.format(**kw) if kw else text


def system_language() -> str:
    try:
        if sys.platform.startswith("win"):
            import ctypes

            lang_id = ctypes.windll.kernel32.GetUserDefaultUILanguage()
            return "pl" if (lang_id & 0xFF) == 0x15 else "en"
        for var in ("LC_ALL", "LC_MESSAGES", "LANG"):
            val = os.environ.get(var, "")
            if val:
                return "pl" if val.lower().startswith("pl") else "en"
        if sys.platform == "darwin":
            import subprocess

            out = subprocess.run(
                ["defaults", "read", "-g", "AppleLanguages"], capture_output=True, text=True
            ).stdout
            return "pl" if '"pl' in out else "en"
    except Exception:
        pass
    return "en"
