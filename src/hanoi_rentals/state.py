"""Portable, checksummed state archives for ephemeral GitHub runners."""

from hashlib import sha256
from pathlib import Path
import tarfile

ALLOWED = (
    "data/processed",
    "data/benchmark",
    "data/analysis/review_queue.csv",
    "artifacts",
    "reports/pipeline_latest.json",
    "reports/crawl_latest.json",
    "reports/state_manifest.json",
    "reports/raw_manifest_latest.json",
)


def allowed(name):
    return any(name == item or name.startswith(item + "/") for item in ALLOWED)


def export_state(root, destination):
    root, destination = Path(root).resolve(), Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(destination, "w:gz") as archive:
        for name in ALLOWED:
            path = root / name
            if path.exists():
                archive.add(path, arcname=name)
    digest = sha256(destination.read_bytes()).hexdigest()
    destination.with_suffix(destination.suffix + ".sha256").write_text(
        f"{digest}  {destination.name}\n"
    )
    return digest


def restore_state(root, source, expected_sha256=None):
    root, source = Path(root).resolve(), Path(source)
    if expected_sha256 and sha256(source.read_bytes()).hexdigest() != expected_sha256:
        raise ValueError("State archive checksum mismatch")
    with tarfile.open(source) as archive:
        for member in archive.getmembers():
            target = (root / member.name).resolve()
            if (
                ".." in Path(member.name).parts
                or Path(member.name).is_absolute()
                or not target.is_relative_to(root)
                or not allowed(member.name)
                or member.issym()
                or member.islnk()
            ):
                raise ValueError(f"Unsafe or unexpected state member: {member.name}")
        archive.extractall(root, filter="data")
