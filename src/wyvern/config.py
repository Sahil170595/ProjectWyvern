from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class WyvernSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="WYVERN_")

    host: str = "0.0.0.0"
    port: int = 8600
    vehicle_address: str = "udpin://0.0.0.0:14540"
    vehicle_id: str = "veh_px4_sitl_001"
    use_mock_vehicle: bool = True
    telemetry_interval_ms: int = 500
    replay_dir: str = "./replay_artifacts"
    # Phase 2: Chimera integration
    chimera_url: str | None = None
    chimera_timeout_s: float = 5.0
    archive_dir: str = "./replay_archives"
    archive_on_completion: bool = True
    compliance_enabled: bool = True
    ws_event_buffer_size: int = 100
