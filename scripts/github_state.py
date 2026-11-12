"""Persist verified model/data state as release assets; 404 alone permits bootstrap."""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import tarfile
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from hanoi_rentals.registry import write_json
from hanoi_rentals.state import export_state, restore_state


def release_exists(repository, tag):
    request = Request(
        f"https://api.github.com/repos/{repository}/releases/tags/{tag}",
        headers={
            "Authorization": "Bearer " + os.environ["GH_TOKEN"],
            "Accept": "application/vnd.github+json",
        },
    )
    try:
        with urlopen(request, timeout=30) as response:
            return response.status == 200
    except HTTPError as exc:
        if exc.code == 404:
            return False
        raise


def gh(*arguments):
    subprocess.run(["gh", *arguments], check=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["restore", "save"])
    parser.add_argument("--tag", default="rental-state")
    args = parser.parse_args()
    root = Path.cwd()
    repository = os.environ["GITHUB_REPOSITORY"]
    folder = root / ".work/state-transfer"
    folder.mkdir(parents=True, exist_ok=True)
    archive = folder / "state.tar.gz"
    if args.action == "restore":
        if not release_exists(repository, args.tag):
            if args.tag != "rental-state":
                raise FileNotFoundError(
                    f"Required versioned state release missing: {args.tag}"
                )
            print(
                "No state release yet; bootstrap from the checked-in snapshot and registry."
            )
            return
        gh(
            "release",
            "download",
            args.tag,
            "--repo",
            repository,
            "--pattern",
            "state.tar.gz*",
            "--dir",
            str(folder),
            "--clobber",
        )
        checksum = archive.with_suffix(".gz.sha256")
        restore_state(root, archive, checksum.read_text().split()[0])
        print("Verified state restored from", args.tag)
        return
    if args.tag == "rental-state":
        raise ValueError(
            "Save needs an immutable per-run tag; the latest pointer is updated afterwards."
        )
    manifest = {
        "source_commit": os.environ["GITHUB_SHA"],
        "state_release": args.tag,
        "saved_utc": datetime.now(timezone.utc).isoformat(),
    }
    write_json(root / "reports/state_manifest.json", manifest)
    export_state(root, archive)
    notes = folder / "notes.md"
    notes.write_text(
        "Versioned apartment/room dataset and evaluated model registry.\n\n"
        + json.dumps(manifest, indent=2)
    )
    for tag in [args.tag, "rental-state"]:
        if not release_exists(repository, tag):
            gh(
                "release",
                "create",
                tag,
                "--repo",
                repository,
                "--target",
                os.environ["GITHUB_SHA"],
                "--title",
                tag,
                "--notes-file",
                str(notes),
                "--prerelease",
                "--latest=false",
            )
        gh(
            "release",
            "upload",
            tag,
            str(archive),
            str(archive.with_suffix(".gz.sha256")),
            "--repo",
            repository,
            "--clobber",
        )
    reports = folder / "reports.tar.gz"
    with tarfile.open(reports, "w:gz") as output:
        output.add(root / "reports", arcname="reports")
    gh("release", "upload", args.tag, str(reports), "--repo", repository, "--clobber")
    print("State saved:", args.tag)


if __name__ == "__main__":
    main()
