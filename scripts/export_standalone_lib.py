"""Script to export standalone agenda-sime-md library for PyPI publication.

Usage:
    python scripts/export_standalone_lib.py [target_directory]
"""

import os
import shutil
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
LIB_SRC = os.path.join(ROOT, "custom_components", "agenda_sime_md", "agenda_sime_md")
LIB_DIR = os.path.join(ROOT, "lib")


def export_library(dest_dir: str | None = None) -> None:
    """Copy self-contained library files into destination directory."""
    if dest_dir is None:
        dest_dir = os.path.join(ROOT, "dist_standalone")

    pkg_dest = os.path.join(dest_dir, "agenda_sime_md")
    os.makedirs(pkg_dest, exist_ok=True)

    # Copy pure python package files
    for fname in ["__init__.py", "auth.py", "client.py", "exceptions.py", "models.py", "parser.py"]:
        src_file = os.path.join(LIB_SRC, fname)
        if os.path.exists(src_file):
            shutil.copy2(src_file, os.path.join(pkg_dest, fname))
            print(f"  Copied {fname} -> {pkg_dest}/")

    # Copy packaging metadata from lib/ and root
    shutil.copy2(os.path.join(LIB_DIR, "pyproject.toml"), os.path.join(dest_dir, "pyproject.toml"))
    shutil.copy2(os.path.join(LIB_DIR, "README.md"), os.path.join(dest_dir, "README.md"))
    shutil.copy2(os.path.join(ROOT, "LICENSE"), os.path.join(dest_dir, "LICENSE"))

    print(f"\nSuccessfully prepared standalone library at: {dest_dir}")
    print("To publish to PyPI from target directory:")
    print("  cd", dest_dir)
    print("  python -m build")
    print("  twine upload dist/*")


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else None
    export_library(target)
