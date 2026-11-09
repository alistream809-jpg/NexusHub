# NEXUS HOST

Free, local Minecraft Java Edition server hosting for Windows 10/11. Python + PySide6 + SQLite.
Servers run on your own PC; no paid hosting.

## Get the Windows installer
Run `build_installer.bat` on a Windows PC (needs Python 3.10+; Inno Setup is installed via winget if missing).
Output: `installer_output\NexusHost-Setup-1.0.0.exe`.
No local setup? Push this folder to a GitHub repo and run the "Build Windows installer" workflow
(Actions tab); the installer is attached as a downloadable artifact.

Run from source instead: `pip install -r requirements.txt` then `python main.py`.

## Project structure
    main.py                     entry point
    nexushost/core/             Qt-free engine (fully unit-tested)
      controller.py             real process control, state machine, player tracking, auto-shutdown
      manager.py                owns all servers + database
      providers.py              Vanilla / Paper / Purpur / Spigot / Fabric / Forge installers
      provisioner.py            builds a server folder (download, eula, properties, DB record)
      javamgr.py                finds Java, downloads Temurin when needed
      db.py props.py mcping.py whitelist.py netutil.py http.py paths.py
    nexushost/ui/               PySide6 interface (theme, widgets, bridge, one file per page)
    installer/nexushost.iss     Inno Setup script
    tests/                      engine tests (fake Minecraft server) + GUI smoke test

## How it stays honest
* A server is ONLINE only after the process prints its "Done" line; player counts are confirmed
  by the server's own status ping (port really open).
* Stop = `save-all flush`, then `stop`; force-kill only after a timeout or on request.
* Auto-shutdown: last player leaves -> countdown (default 7 min, configurable per server);
  a join cancels it; at zero the world is saved and the server stops.
* Port in use, missing jar, missing Java, crashes, out-of-memory and wrong-Java errors are detected and explained.

## Notes
* Spigot is compiled locally by BuildTools (5-15 min, needs a JDK, auto-downloaded). Prefer Paper for old versions.
* Vendor download APIs (Mojang, PaperMC, Purpur, Fabric, Forge, Adoptium) are used live; if one changes, creation shows a clear error.
* Uninstalling keeps your servers in `%LOCALAPPDATA%\NexusHost`.
* Tests: `python -m unittest tests.test_core` (POSIX shell wrapper; run on Linux/macOS/WSL).
