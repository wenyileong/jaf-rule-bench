# Building the Windows executable

The executable is a single file built with PyInstaller. It starts a local web server (127.0.0.1, from port 8765) and opens the interface in the default browser. Nothing is sent over the network.

On Windows, with Python 3.12 and the requirements installed:

```
pip install pyinstaller
pyinstaller --noconfirm --onefile --console --name JAF_Rule_Bench ^
  --add-data "app/ui.html;app" --add-data "app/default_result.json;app" --add-data "app/default_world_result.json;app" ^
  --hidden-import jaf.report --hidden-import jaf.experiments --hidden-import jaf.world_report --hidden-import jaf.template ^
  --hidden-import jaf.design --hidden-import jaf.measure --hidden-import jaf.estimate --hidden-import jaf.recovery ^
  --hidden-import jaf.prereg --hidden-import jaf.examples ^
  --hidden-import openpyxl --exclude-module tkinter --exclude-module matplotlib --exclude-module scipy main.py
```

The result is `dist/JAF_Rule_Bench.exe`. Releases to date were built with CPython 3.12.9, NumPy 2.1.3, openpyxl 3.1.5 and PyInstaller 6.11.1, under Wine. They have not yet been tested on a Windows machine.

Do not commit `dist/` or `build/`: attach the executable to a GitHub Release instead.
