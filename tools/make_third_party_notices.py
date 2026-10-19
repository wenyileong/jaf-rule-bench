"""Assemble THIRD_PARTY_NOTICES.txt for the Windows executable from the build environment.

Usage: python tools/make_third_party_notices.py <python-dir> [output]
<python-dir> is the CPython installation used for the PyInstaller build (it contains LICENSE.txt and
Lib/site-packages). Re-run whenever a bundled component or its version changes.
"""
import os, sys

HEADER = """JAF Rule Bench: third-party notices
====================================

The Windows executable (JAF_Rule_Bench.exe) bundles the third-party components listed
below. Each remains under its own licence, reproduced in full in this file. The licence
of JAF Rule Bench itself (see README.md) covers only its own code and documents, not
these components. The source code repository does not contain these components; they
are installed separately (requirements.txt).

Component                                   Version   Licence
------------------------------------------  --------  -----------------------------------------
CPython (python312.dll and standard library) {py:<8}  PSF License Version 2, with the licences
                                                      of its bundled parts (including bzip2;
                                                      libffi, MIT; OpenSSL 3, Apache-2.0)
NumPy                                       {np:<8}  BSD-3-Clause, with the licences of its
                                                      bundled parts (including OpenBLAS,
                                                      BSD-3-Clause; LAPACK,
                                                      BSD-3-Clause-Attribution; GCC runtime
                                                      library, GPL-3.0 with the GCC Runtime
                                                      Library Exception)
openpyxl                                    {ox:<8}  MIT
et_xmlfile                                  {et:<8}  MIT (with portions under the PSF License)
PyInstaller bootloader                      {pi:<8}  GPL-2.0-or-later with the Bootloader
                                                      Exception, which permits distribution of
                                                      the bundled program under any terms
Microsoft Visual C++ runtime                          Microsoft Visual C++ Redistributable
(vcruntime140.dll, vcruntime140_1.dll,                licence terms (redistribution permitted)
msvcp140.dll)

"""


def section(title, path, origin):
    with open(path, encoding="utf-8", errors="replace") as fh:
        body = fh.read().strip()
    bar = "=" * 78
    return f"\n{bar}\n{title}\n(reproduced from {origin})\n{bar}\n\n{body}\n"


def version(sp, name):
    for d in os.listdir(sp):
        if d.lower().startswith(name.lower() + "-") and d.endswith(".dist-info"):
            return d[len(name) + 1:-len(".dist-info")]
    return "?"


def main(pydir, out):
    sp = os.path.join(pydir, "Lib", "site-packages")
    di = lambda n: os.path.join(sp, f"{n}-{version(sp, n)}.dist-info")
    pyver = "?"
    for f in os.listdir(pydir):
        if f.startswith("python3") and f.endswith(".dll") and f != "python3.dll":
            pyver = f"3.{f[7:-4]}"
    text = HEADER.format(py=os.environ.get("PYVER", pyver), np=version(sp, "numpy"), ox=version(sp, "openpyxl"),
                         et=version(sp, "et_xmlfile"), pi=version(sp, "pyinstaller"))
    text += section("CPython: licence and the licences of its bundled components", os.path.join(pydir, "LICENSE.txt"), "the LICENSE.txt of the CPython Windows distribution")
    text += section("NumPy: licence and the licences of its bundled components", os.path.join(di("numpy"), "LICENSE.txt"), "the LICENSE.txt of the NumPy wheel")
    text += section("openpyxl", os.path.join(di("openpyxl"), "LICENCE.rst"), "the LICENCE.rst of the openpyxl package")
    text += section("et_xmlfile", os.path.join(di("et_xmlfile"), "LICENCE.rst"), "the LICENCE.rst of the et_xmlfile package")
    text += section("et_xmlfile: portions under the PSF License", os.path.join(di("et_xmlfile"), "LICENCE.python"), "the LICENCE.python of the et_xmlfile package")
    text += section("PyInstaller: licence, including the Bootloader Exception", os.path.join(di("pyinstaller"), "COPYING.txt"), "the COPYING.txt of the PyInstaller package")
    text += ("\n" + "=" * 78 + "\nMicrosoft Visual C++ runtime\n" + "=" * 78 + "\n\n"
             "vcruntime140.dll, vcruntime140_1.dll and msvcp140.dll, and the Microsoft Distributable\n"
             "Code linked into the CPython and NumPy binaries, are Copyright (c) Microsoft Corporation\n"
             "and are distributed under the Microsoft Visual C++ Redistributable licence terms.\n\n"
             "As those terms require, anyone who uses or further distributes this executable agrees\n"
             "not to: alter any copyright, trademark or patent notice in Microsoft's Distributable\n"
             "Code; use Microsoft's trademarks in a way that suggests the program comes from or is\n"
             "endorsed by Microsoft; distribute Microsoft's Distributable Code to run on a platform\n"
             "other than Microsoft operating systems, run-time technologies or application\n"
             "platforms; or include it in malicious, deceptive or unlawful programs. See the\n"
             "'Additional Conditions for this Windows binary build' in the CPython section above.\n")
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    print(f"Wrote {out} ({len(text.splitlines())} lines)")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "THIRD_PARTY_NOTICES.txt")
