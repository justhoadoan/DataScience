"""Export/restore state locally or inside GitHub Actions, with SHA-256 verification."""

import argparse
from pathlib import Path
from hanoi_rentals.state import export_state, restore_state

parser = argparse.ArgumentParser()
parser.add_argument("action", choices=["export", "restore"])
parser.add_argument("archive", type=Path)
parser.add_argument("--root", type=Path, default=Path.cwd())
args = parser.parse_args()
if args.action == "export":
    print(export_state(args.root, args.archive))
else:
    checksum = args.archive.with_suffix(args.archive.suffix + ".sha256")
    if not checksum.exists():
        raise FileNotFoundError("Missing state checksum")
    restore_state(args.root, args.archive, checksum.read_text().split()[0])
