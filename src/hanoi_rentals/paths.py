"""Repository paths and source files shared by training and model provenance."""

from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_ROOT.parents[1]


def source_files():
    """Include the complete package so moved modules remain fingerprinted and archived."""
    files = {
        path.relative_to(PACKAGE_ROOT).as_posix(): path
        for path in sorted(PACKAGE_ROOT.rglob("*.py"))
    }
    return files
