from __future__ import annotations

from wyvern.contracts import Health, Position, Velocity, Waypoint


class MockVehicleAdapter:
    """Deterministic mock vehicle for testing without PX4 SITL."""

    def __init__(self, vehicle_id: str = "veh_mock_001") -> None:
        self.vehicle_id = vehicle_id
        self._connected = False
        self._armed = False
        self._in_air = False
        self._flight_mode = "idle"
        self._waypoints: list[Waypoint] = []
        self._current_waypoint = 0
        self._mission_started = False
        self._paused = False

        # Telemetry state
        self._position = Position(lat=42.3000, lon=-71.1000, alt_m=0.0)
        self._velocity = Velocity(ground_speed_mps=0.0, vertical_speed_mps=0.0)
        self._battery_percent = 90.0
        self._gps_fix = "3d"
        self._link_quality = 0.95
        self._estimator_status = "nominal"

        # Configurable rates
        self._drain_rate = 0.5  # percent per telemetry poll
        self._advance_on_poll = True

    # --- Configuration for tests ---

    def set_battery(self, percent: float) -> None:
        self._battery_percent = percent

    def set_drain_rate(self, rate: float) -> None:
        self._drain_rate = rate

    def set_gps_fix(self, fix: str) -> None:
        self._gps_fix = fix

    def set_link_quality(self, quality: float) -> None:
        self._link_quality = quality

    def set_estimator_status(self, status: str) -> None:
        self._estimator_status = status

    # --- Adapter interface ---

    async def connect(self) -> None:
        self._connected = True

    async def is_connected(self) -> bool:
        return self._connected

    async def arm(self) -> None:
        self._armed = True
        self._flight_mode = "armed"

    async def disarm(self) -> None:
        self._armed = False
        self._flight_mode = "idle"

    async def upload_mission(self, waypoints: list[Waypoint]) -> None:
        self._waypoints = list(waypoints)
        self._current_waypoint = 0

    async def start_mission(self) -> None:
        self._mission_started = True
        self._paused = False
        self._in_air = True
        self._flight_mode = "mission"
        self._velocity = Velocity(ground_speed_mps=5.0, vertical_speed_mps=0.5)

    async def pause_mission(self) -> None:
        self._paused = True
        self._flight_mode = "hold"
        self._velocity = Velocity(ground_speed_mps=0.0, vertical_speed_mps=0.0)

    async def hold(self) -> None:
        self._paused = True
        self._flight_mode = "hold"
        self._velocity = Velocity(ground_speed_mps=0.0, vertical_speed_mps=0.0)

    async def return_to_launch(self) -> None:
        self._flight_mode = "rtl"
        self._paused = False
        self._velocity = Velocity(ground_speed_mps=3.0, vertical_speed_mps=-1.0)
        # RTL completes immediately in mock -- set to landed state
        self._in_air = False
        self._armed = False

    async def land(self) -> None:
        self._flight_mode = "land"
        self._in_air = False
        self._armed = False
        self._velocity = Velocity(ground_speed_mps=0.0, vertical_speed_mps=0.0)

    async def get_position(self) -> Position:
        # Advance position toward current waypoint if flying
        if self._mission_started and not self._paused and self._waypoints:
            if self._current_waypoint < len(self._waypoints):
                wp = self._waypoints[self._current_waypoint]
                self._position = Position(lat=wp.lat, lon=wp.lon, alt_m=wp.alt_m)
        return self._position

    async def get_velocity(self) -> Velocity:
        return self._velocity

    async def get_battery_percent(self) -> float:
        if self._in_air:
            self._battery_percent = max(0.0, self._battery_percent - self._drain_rate)
        return self._battery_percent

    async def get_flight_mode(self) -> str:
        return self._flight_mode

    async def get_health(self) -> Health:
        return Health(
            battery_percent=self._battery_percent,
            gps_fix=self._gps_fix,
            telemetry_age_ms=50,
            link_quality=self._link_quality,
            estimator_status=self._estimator_status,
        )

    async def is_armed(self) -> bool:
        return self._armed

    async def is_in_air(self) -> bool:
        return self._in_air

    async def get_mission_progress(self) -> tuple[int, int]:
        total = len(self._waypoints)
        if not self._mission_started or self._paused or total == 0:
            return (self._current_waypoint, total)

        # Advance one waypoint per poll
        if self._advance_on_poll and self._current_waypoint < total:
            self._current_waypoint += 1

        # If completed all waypoints, land
        if self._current_waypoint >= total:
            self._in_air = False
            self._armed = False
            self._flight_mode = "landed"
            self._velocity = Velocity(ground_speed_mps=0.0, vertical_speed_mps=0.0)

        return (self._current_waypoint, total)
