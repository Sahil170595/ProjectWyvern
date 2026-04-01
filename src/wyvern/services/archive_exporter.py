from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

from wyvern.contracts import ReplayArtifact, ReplaySummary
from wyvern.hashing import hash_model, sha256_hash
from wyvern.store import MissionRecord

logger = logging.getLogger(__name__)


class ArchiveExporter:
    def __init__(self, archive_dir: str) -> None:
        self._archive_dir = Path(archive_dir)

    async def export(self, record: MissionRecord) -> str:
        """Export mission record to disk. Returns file:// URI."""
        return await asyncio.to_thread(self._export_sync, record)

    def _export_sync(self, record: MissionRecord) -> str:
        mission_id = record.mission.mission_id
        out_dir = self._archive_dir / mission_id
        out_dir.mkdir(parents=True, exist_ok=True)

        files: dict[str, str] = {}

        # mission.json
        mission_path = out_dir / "mission.json"
        mission_bytes = record.mission.model_dump_json(indent=2).encode("utf-8")
        mission_path.write_bytes(mission_bytes)
        files["mission.json"] = sha256_hash(mission_bytes)

        # timeline.jsonl
        timeline_path = out_dir / "timeline.jsonl"
        timeline_lines = [e.model_dump_json() for e in record.timeline]
        timeline_bytes = ("\n".join(timeline_lines) + "\n").encode("utf-8") if timeline_lines else b""
        timeline_path.write_bytes(timeline_bytes)
        files["timeline.jsonl"] = sha256_hash(timeline_bytes)

        # telemetry.jsonl
        telemetry_path = out_dir / "telemetry.jsonl"
        telemetry_lines = [e.model_dump_json() for e in record.telemetry]
        telemetry_bytes = ("\n".join(telemetry_lines) + "\n").encode("utf-8") if telemetry_lines else b""
        telemetry_path.write_bytes(telemetry_bytes)
        files["telemetry.jsonl"] = sha256_hash(telemetry_bytes)

        # validation.json
        if record.validation_result is not None:
            val_path = out_dir / "validation.json"
            val_bytes = record.validation_result.model_dump_json(indent=2).encode("utf-8")
            val_path.write_bytes(val_bytes)
            files["validation.json"] = sha256_hash(val_bytes)

        # incidents.jsonl
        if record.incidents:
            incidents_path = out_dir / "incidents.jsonl"
            incident_lines = [i.model_dump_json() for i in record.incidents]
            incident_bytes = ("\n".join(incident_lines) + "\n").encode("utf-8")
            incidents_path.write_bytes(incident_bytes)
            files["incidents.jsonl"] = sha256_hash(incident_bytes)

        # replay_artifact.json
        archive_uri = out_dir.resolve().as_uri()
        operator_interventions = sum(
            1 for e in record.timeline if e.actor.startswith("operator")
        )
        constraint_violations = sum(
            1 for e in record.timeline
            if e.reason_code.startswith("degraded.") or e.reason_code.startswith("blocked.")
        )

        artifact = ReplayArtifact(
            mission_id=mission_id,
            trace_id=record.mission.trace_id,
            mission_hash=hash_model(record.mission),
            approval_hash=hash_model(record.mission.approval),
            validation_hash=hash_model(record.validation_result) if record.validation_result else "sha256:none",
            timeline_ref=f"{archive_uri}/timeline.jsonl",
            telemetry_ref=f"{archive_uri}/telemetry.jsonl",
            summary=ReplaySummary(
                terminal_state=record.state.value,
                operator_interventions=operator_interventions,
                constraint_violations=constraint_violations,
            ),
        )
        artifact_path = out_dir / "replay_artifact.json"
        artifact_bytes = artifact.model_dump_json(indent=2).encode("utf-8")
        artifact_path.write_bytes(artifact_bytes)
        files["replay_artifact.json"] = sha256_hash(artifact_bytes)

        # manifest.json
        manifest_path = out_dir / "manifest.json"
        manifest_bytes = json.dumps(files, indent=2, sort_keys=True).encode("utf-8")
        manifest_path.write_bytes(manifest_bytes)

        logger.info("Exported archive for %s to %s", mission_id, out_dir)
        return archive_uri
