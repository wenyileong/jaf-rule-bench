# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Wen Yi LEONG
"""Write the Windows version resource (file properties) for PyInstaller's --version-file.

Usage: python packaging/version_info.py <version, e.g. 1.0.0> <output file>
"""
import sys

TEMPLATE = """VSVersionInfo(
  ffi=FixedFileInfo(filevers=({t}), prodvers=({t}), mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('080904B0', [
      StringStruct('CompanyName', 'Wen Yi LEONG'),
      StringStruct('FileDescription', 'JAF Rule Bench'),
      StringStruct('FileVersion', '{v}'),
      StringStruct('InternalName', 'JAF_Rule_Bench'),
      StringStruct('LegalCopyright', 'Copyright (c) 2026 Wen Yi LEONG. PolyForm Noncommercial 1.0.0.'),
      StringStruct('OriginalFilename', 'JAF_Rule_Bench.exe'),
      StringStruct('ProductName', 'JAF Rule Bench'),
      StringStruct('ProductVersion', '{v}')])]),
    VarFileInfo([VarStruct('Translation', [2057, 1200])])
  ]
)
"""


def main(version, out):
    parts = [int(x) for x in version.lstrip("v").split("-")[0].split(".")]
    parts = (parts + [0, 0, 0, 0])[:4]
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(TEMPLATE.format(t=", ".join(map(str, parts)), v=version.lstrip("v")))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
