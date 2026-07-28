from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from sip.capture import CapturePackage, PolyformImporter, create_synthetic_room_capture
from sip.errors import ValidationError


@pytest.mark.unit
def test_capcscp_001_deterministic_canonical_capture_hashes_frames_and_assets(tmp_path: Path) -> None:
    one = create_synthetic_room_capture(tmp_path / "one.sipcapture", seed=42, frame_count=8)
    two = create_synthetic_room_capture(tmp_path / "two.sipcapture", seed=42, frame_count=8)
    assert one["root_hash"] == two["root_hash"]
    assert CapturePackage.validate(tmp_path / "one.sipcapture")["frame_count"] == 8


@pytest.mark.unit
def test_capcscp_rejects_tampered_and_future_schema_packages(tmp_path: Path) -> None:
    source = tmp_path / "source.sipcapture"
    create_synthetic_room_capture(source)
    tampered = tmp_path / "tampered.sipcapture"
    with zipfile.ZipFile(source) as read, zipfile.ZipFile(tampered, "w") as write:
        for info in read.infolist():
            payload = read.read(info.filename)
            if info.filename.endswith("rgb.bin"):
                payload += b"tamper"
            write.writestr(info.filename, payload)
    with pytest.raises(ValidationError) as error:
        CapturePackage.validate(tampered)
    assert error.value.code == "CAPTURE_ASSET_INTEGRITY"


@pytest.mark.unit
def test_cappoly_001_polyform_adapter_preserves_native_and_corrected_streams(tmp_path: Path) -> None:
    root = tmp_path / "polyform"
    for folder in ["cameras", "corrected_cameras", "images", "corrected_images", "depth", "confidence"]:
        (root / "keyframes" / folder).mkdir(parents=True)
    camera = {"fx": 100, "fy": 100, "cx": 50, "cy": 40, "width": 100, "height": 80, "blur_score": 0.1}
    for row in range(3):
        for col in range(4):
            camera[f"t_{row}{col}"] = 1.0 if row == col else 0.0
    corrected = {**camera, "t_03": 0.25}
    for timestamp in [1000000, 2000000]:
        (root / "keyframes/cameras" / f"{timestamp}.json").write_text(json.dumps(camera))
        (root / "keyframes/corrected_cameras" / f"{timestamp}.json").write_text(json.dumps(corrected))
        (root / "keyframes/images" / f"{timestamp}.jpg").write_bytes(b"native" + str(timestamp).encode())
        (root / "keyframes/corrected_images" / f"{timestamp}.jpg").write_bytes(b"corrected" + str(timestamp).encode())
        (root / "keyframes/depth" / f"{timestamp}.png").write_bytes(b"depth" + str(timestamp).encode())
        (root / "keyframes/confidence" / f"{timestamp}.png").write_bytes(b"confidence" + str(timestamp).encode())
    result = PolyformImporter().convert(root, tmp_path / "converted.sipcapture")
    assert result["conversion_report"]["optimized_frames"] == 2
    manifest = CapturePackage.inspect(tmp_path / "converted.sipcapture")["manifest"]
    assert all(frame["pose_stream"] == "polycam_corrected_optimized" for frame in manifest["frames"])
    assert all(frame["native_camera_to_world"] != frame["camera_to_world"] for frame in manifest["frames"])
