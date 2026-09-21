"""Download the Pyodide runtime the browser build needs into ``demo/pyodide/``.

    python demo/get_pyodide.py            # the pinned version
    python demo/get_pyodide.py 314.0.7    # or any other release

This is the stock ``pyodide-core`` tarball from Pyodide's GitHub releases,
unpacked and otherwise untouched - pyroquad's web build deliberately runs on an
unmodified Pyodide (see ``docs/WASM.md``). Nothing here is needed to build the
module itself; it is the runtime that loads it, plus the reference
``check_imports.py`` resolves symbols against.

The one addition is micropip: ``pyodide-core`` carries no packages, and
``index.html`` needs micropip to install pyroquad from PyPI. Its wheel is
fetched separately from the release's package set and checked against the
hash in ``pyodide-lock.json``, which is the same file Pyodide itself consults
when ``loadPackage("micropip")`` resolves it out of ``pyodide/``.

Pyodide releases are versioned after the CPython they ship: 314.0.7 is CPython
3.14.2, which is what ``--features abi_314`` targets.
"""

from __future__ import annotations

import hashlib
import io
import json
import shutil
import sys
import tarfile
import urllib.request
from pathlib import Path

DEFAULT_VERSION = "314.0.7"
WEB = Path(__file__).resolve().parent
URL = "https://github.com/pyodide/pyodide/releases/download/{v}/pyodide-core-{v}.tar.bz2"
PKG_URL = "https://cdn.jsdelivr.net/pyodide/v{v}/full/{f}"


def get_micropip(version: str, dest: Path) -> int:
    """Stage the micropip wheel named by ``dest/pyodide-lock.json``."""
    lock = json.loads((dest / "pyodide-lock.json").read_text(encoding="utf-8"))
    entry = lock["packages"]["micropip"]
    url = PKG_URL.format(v=version, f=entry["file_name"])

    print(f"downloading {url}")
    with urllib.request.urlopen(url) as response:
        blob = response.read()

    digest = hashlib.sha256(blob).hexdigest()
    if digest != entry["sha256"]:
        print(f"checksum mismatch for {entry['file_name']}", file=sys.stderr)
        print(f"  lock file expects {entry['sha256']}", file=sys.stderr)
        print(f"  download is       {digest}", file=sys.stderr)
        return 1

    (dest / entry["file_name"]).write_bytes(blob)
    print(f"  {len(blob) / 1e6:.1f} MB -> pyodide/{entry['file_name']}  (sha256 ok)")
    return 0


def main(version: str) -> int:
    dest = WEB / "pyodide"
    url = URL.format(v=version)

    print(f"downloading {url}")
    with urllib.request.urlopen(url) as response:
        blob = response.read()
    print(f"  {len(blob) / 1e6:.1f} MB")

    if dest.exists():
        print(f"replacing {dest}")
        shutil.rmtree(dest)

    print(f"extracting into {WEB}")
    with tarfile.open(fileobj=io.BytesIO(blob), mode="r:bz2") as tar:
        # The tarball's members all live under a top-level `pyodide/`, and this
        # refuses anything that tries to climb out of it.
        for member in tar.getmembers():
            target = (WEB / member.name).resolve()
            if not str(target).startswith(str(WEB)):
                raise RuntimeError(f"refusing unsafe archive path: {member.name}")
        tar.extractall(WEB)

    marker = dest / "pyodide.asm.wasm"
    if not marker.is_file():
        print(f"unexpected archive layout: {marker} is missing", file=sys.stderr)
        return 1

    if get_micropip(version, dest):
        return 1

    print(f"pyodide {version} ready in {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_VERSION))
