# Building the Windows executable

## Automatic builds (recommended)

`.github/workflows/build-windows.yml` builds the executable on GitHub's Windows runners. On every push to a branch, every pull request, and on demand from the Actions tab, it runs the acceptance tests on Windows, builds the executable with its icon and file properties, smoke-tests it (starts it, runs the identification check and a coded-world run, downloads a template, quits), packages the release zip with the licences, documents, templates and third-party notices, and uploads the zip and its SHA-256 checksums as an artifact. On a tag such as `v1.0.0` it also creates a **draft** GitHub release with the zip attached and the notes in `packaging/release_notes/<tag>.md`. Nothing is published until the author publishes the draft, which is also what triggers the Zenodo archive.

## Icon

`packaging/jaf.ico` (16 to 256 px) and `packaging/jaf_icon.png` are drawn by `packaging/make_icon.py` (Pillow). The design follows the A-share Company Intelligence icon (a flat rounded square with a white mark) in the Rule Bench indigo: a digital-asset token assigned by a bold line to one of three jurisdictions, with fainter lines to the competing claims. The interface uses the same mark as its browser-tab icon.

## Building by hand

The executable is a single file built with PyInstaller. It starts a local web server (127.0.0.1, from port 8765) and opens the interface in the default browser. Nothing is sent over the network.

On Windows, with Python 3.12 and the requirements installed:

```
pip install pyinstaller
python packaging/version_info.py 1.0.0 version_info.txt
pyinstaller --noconfirm --onefile --console --name JAF_Rule_Bench ^
  --icon packaging/jaf.ico --version-file version_info.txt ^
  --add-data "app/ui.html;app" --add-data "app/default_result.json;app" --add-data "app/default_world_result.json;app" ^
  --hidden-import jaf.report --hidden-import jaf.experiments --hidden-import jaf.world_report --hidden-import jaf.template ^
  --hidden-import jaf.design --hidden-import jaf.measure --hidden-import jaf.estimate --hidden-import jaf.recovery ^
  --hidden-import jaf.prereg --hidden-import jaf.examples ^
  --hidden-import openpyxl --exclude-module tkinter --exclude-module matplotlib --exclude-module scipy main.py
```

The result is `dist/JAF_Rule_Bench.exe`. Builds use CPython 3.12 with NumPy 2.1.3, openpyxl 3.1.5 and PyInstaller 6.11.1 (pinned in the workflow to match the third-party notices). Builds before 1.0.0 were made under Wine.

Do not commit `dist/` or `build/`: attach the executable to a GitHub Release instead.

## Third-party notices

The executable bundles third-party components that remain under their own licences. Every release must ship `THIRD_PARTY_NOTICES.txt` alongside the executable. Regenerate it from the Python installation used for the build whenever a bundled component or its version changes:

```
python tools/make_third_party_notices.py <path-to-build-python> THIRD_PARTY_NOTICES.txt
```
