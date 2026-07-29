from __future__ import annotations

import stat
import zipfile
from pathlib import Path

import pytest

from sip.archive_safety import validate_zip_members
from sip.construction import ConstructionService
from sip.errors import ValidationError
from sip.liveforever import LiveForeverService


def _zip(path: Path, members: list[tuple[zipfile.ZipInfo, bytes]]) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        for info, payload in members:
            archive.writestr(info, payload)


def _info(name: str, *, mode: int = stat.S_IFREG | 0o644) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.external_attr = mode << 16
    info.compress_type = zipfile.ZIP_DEFLATED
    return info


@pytest.mark.unit
def test_vertical_package_member_validation_rejects_traversal_backslash_drive_symlink_and_duplicates(tmp_path: Path) -> None:
    """REQ: CONHAND-006, LIFPRESV-001 open vertical packages reject unsafe or ambiguous archive members before reading payloads."""
    for members in [
        [(_info("../escape"), b"x")],
        [(_info("dir\\escape"), b"x")],
        [(_info("C:/escape"), b"x")],
        [(_info("link", mode=stat.S_IFLNK | 0o777), b"target")],
        [(_info("same"), b"a"), (_info("same"), b"b")],
    ]:
        path = tmp_path / f"unsafe-{len(list(tmp_path.iterdir()))}.zip"
        _zip(path, members)
        with zipfile.ZipFile(path) as archive, pytest.raises(ValidationError):
            validate_zip_members(archive.infolist(), code_prefix="VERTICAL")


@pytest.mark.unit
def test_handoff_and_liveforever_verifiers_reject_unsafe_packages(tmp_path: Path) -> None:
    """REQ: CONHAND-006, LIFPRESV-001 package-specific verifiers apply the shared fail-closed archive policy."""
    for index, verifier in enumerate((ConstructionService.verify_owner_handoff, LiveForeverService.verify_preservation_release)):
        path = tmp_path / f"unsafe-package-{index}.zip"
        _zip(path, [(_info("../outside.txt"), b"x")])
        with pytest.raises(ValidationError):
            verifier(path)
