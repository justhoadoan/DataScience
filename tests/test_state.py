import io
import tarfile
import pytest

from hanoi_rentals.state import export_state, restore_state


def test_state_roundtrip_keeps_snapshot_and_model(tmp_path):
    root = tmp_path / "source"
    (root / "data/processed").mkdir(parents=True)
    (root / "data/processed/listings.csv").write_text("listing_id\nnt_1\n")
    archive = tmp_path / "state.tar.gz"
    checksum = export_state(root, archive)
    destination = tmp_path / "restored"
    destination.mkdir()
    restore_state(destination, archive, checksum)
    assert (destination / "data/processed/listings.csv").read_bytes() == (
        root / "data/processed/listings.csv"
    ).read_bytes()
    with pytest.raises(ValueError, match="checksum"):
        restore_state(destination, archive, "wrong")


@pytest.mark.parametrize('name', ['../escape', 'artifacts/../.git/config', 'unexpected.txt'])
def test_restore_refuses_path_escape_and_unexpected_files(tmp_path, name):
    archive = tmp_path / "evil.tar.gz"
    with tarfile.open(archive, "w:gz") as output:
        item = tarfile.TarInfo(name)
        item.size = 1
        output.addfile(item, io.BytesIO(b"x"))
    with pytest.raises(ValueError, match="Unsafe"):
        restore_state(tmp_path / "destination", archive)
