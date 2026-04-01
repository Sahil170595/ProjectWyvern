import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from wyvern.contracts import Mission, TimelineEntry, ValidationCheck, ValidationResult
from wyvern.services.archive_exporter import ArchiveExporter
from wyvern.state_machine import MissionState
from wyvern.store import MissionRecord

FIXTURES = Path(__file__).parent / "fixtures"


def _load_mission() -> Mission:
    data = json.loads((FIXTURES / "sample_mission.json").read_text())
    return Mission(**data)


def _make_record() -> MissionRecord:
    mission = _load_mission()
    record = MissionRecord(mission=mission, state=MissionState.COMPLETED)
    record.timeline.append(TimelineEntry(
        timestamp=datetime.now(timezone.utc),
        prior_state=None,
        next_state="draft",
        actor="api",
        trace_id=mission.trace_id,
        reason_code="mission.created",
    ))
    record.timeline.append(TimelineEntry(
        timestamp=datetime.now(timezone.utc),
        prior_state="executing",
        next_state="completed",
        actor="wyvern_executor",
        trace_id=mission.trace_id,
        reason_code="mission.completed",
    ))
    record.validation_result = ValidationResult(
        mission_id=mission.mission_id,
        trace_id=mission.trace_id,
        passed=True,
        checks=[ValidationCheck(name="geofence", status="passed")],
    )
    return record


@pytest.mark.asyncio
async def test_export_creates_expected_files(tmp_path):
    exporter = ArchiveExporter(archive_dir=str(tmp_path))
    record = _make_record()
    ref = await exporter.export(record)

    out_dir = tmp_path / "mis_test_001"
    assert out_dir.exists()
    assert (out_dir / "mission.json").exists()
    assert (out_dir / "timeline.jsonl").exists()
    assert (out_dir / "telemetry.jsonl").exists()
    assert (out_dir / "validation.json").exists()
    assert (out_dir / "replay_artifact.json").exists()
    assert (out_dir / "manifest.json").exists()


@pytest.mark.asyncio
async def test_timeline_jsonl_line_count(tmp_path):
    exporter = ArchiveExporter(archive_dir=str(tmp_path))
    record = _make_record()
    await exporter.export(record)

    lines = (tmp_path / "mis_test_001" / "timeline.jsonl").read_text().strip().split("\n")
    assert len(lines) == 2  # 2 timeline entries


@pytest.mark.asyncio
async def test_timeline_jsonl_valid_json(tmp_path):
    exporter = ArchiveExporter(archive_dir=str(tmp_path))
    record = _make_record()
    await exporter.export(record)

    for line in (tmp_path / "mis_test_001" / "timeline.jsonl").read_text().strip().split("\n"):
        parsed = json.loads(line)
        assert "next_state" in parsed


@pytest.mark.asyncio
async def test_manifest_has_sha256(tmp_path):
    exporter = ArchiveExporter(archive_dir=str(tmp_path))
    record = _make_record()
    await exporter.export(record)

    manifest = json.loads((tmp_path / "mis_test_001" / "manifest.json").read_text())
    assert "mission.json" in manifest
    assert all(v.startswith("sha256:") for v in manifest.values())


@pytest.mark.asyncio
async def test_replay_artifact_has_file_refs(tmp_path):
    exporter = ArchiveExporter(archive_dir=str(tmp_path))
    record = _make_record()
    await exporter.export(record)

    artifact = json.loads((tmp_path / "mis_test_001" / "replay_artifact.json").read_text())
    assert "file:///" in artifact["timeline_ref"]
    assert artifact["summary"]["terminal_state"] == "completed"
