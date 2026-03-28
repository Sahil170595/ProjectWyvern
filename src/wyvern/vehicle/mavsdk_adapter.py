"""Real MAVSDK adapter for PX4 SITL / hardware.

Requires: pip install wyvern[mavsdk]
Usage: WYVERN_USE_MOCK_VEHICLE=false WYVERN_VEHICLE_ADDRESS=udpin://0.0.0.0:14540
"""

from __future__ import annotations

import asyncio

from mavsdk import System
from mavsdk.mission import MissionItem, MissionPlan

from wyvern.contracts import Health, Position, Velocity, Waypoint

_TELEMETRY_TIMEOUT_S = 5.0


class MavsdkVehicleAdapter:
    def __init__(self, system_address: str, vehicle_id: str) -> None:
        self.vehicle_id = vehicle_id
        self._system_address = system_address
        self._drone = System()
        self._connected = False

    async def connect(self) -> None:
        await self._drone.connect(system_address=self._system_address)
        async for state in self._drone.core.connection_state():
            if state.is_connected:
                self._connected = True
                break

    async def is_connected(self) -> bool:
        return self._connected

    async def arm(self) -> None:
        await self._drone.action.arm()

    async def disarm(self) -> None:
        await self._drone.action.disarm()

    async def upload_mission(self, waypoints: list[Waypoint]) -> None:
        items = []
        for wp in waypoints:
            items.append(
                MissionItem(
                    wp.lat,
                    wp.lon,
                    wp.alt_m,
                    10.0,  # speed m/s
                    wp.hold_s == 0,  # is_fly_through
                    float("nan"),  # gimbal_pitch
                    float("nan"),  # gimbal_yaw
                    MissionItem.CameraAction.NONE,
                    float(wp.hold_s) if wp.hold_s > 0 else float("nan"),
                    float("nan"),  # camera_photo_interval
                    float("nan"),  # acceptance_radius
                    float("nan"),  # yaw
                    float("nan"),  # camera_photo_distance
                    MissionItem.VehicleAction.NONE,
                )
            )
        await self._drone.mission.set_return_to_launch_after_mission(True)
        await self._drone.mission.upload_mission(MissionPlan(items))

    async def start_mission(self) -> None:
        await self._drone.mission.start_mission()

    async def pause_mission(self) -> None:
        await self._drone.mission.pause_mission()

    async def hold(self) -> None:
        await self._drone.action.hold()

    async def return_to_launch(self) -> None:
        await self._drone.action.return_to_launch()

    async def land(self) -> None:
        await self._drone.action.land()

    async def _next_from_stream(self, stream, default=None):
        """Take one value from a MAVSDK telemetry stream with timeout."""
        try:
            return await asyncio.wait_for(stream.__anext__(), timeout=_TELEMETRY_TIMEOUT_S)
        except (asyncio.TimeoutError, StopAsyncIteration):
            return default

    async def get_position(self) -> Position:
        pos = await self._next_from_stream(self._drone.telemetry.position())
        if pos is None:
            return Position(lat=0, lon=0, alt_m=0)
        return Position(
            lat=pos.latitude_deg,
            lon=pos.longitude_deg,
            alt_m=pos.relative_altitude_m,
        )

    async def get_velocity(self) -> Velocity:
        vel = await self._next_from_stream(self._drone.telemetry.velocity_ned())
        if vel is None:
            return Velocity(ground_speed_mps=0, vertical_speed_mps=0)
        ground = (vel.north_m_s ** 2 + vel.east_m_s ** 2) ** 0.5
        return Velocity(ground_speed_mps=ground, vertical_speed_mps=-vel.down_m_s)

    async def get_battery_percent(self) -> float:
        bat = await self._next_from_stream(self._drone.telemetry.battery())
        if bat is None:
            return 0.0
        return bat.remaining_percent * 100.0

    async def get_flight_mode(self) -> str:
        mode = await self._next_from_stream(self._drone.telemetry.flight_mode())
        if mode is None:
            return "unknown"
        return mode.name.lower()

    async def get_health(self) -> Health:
        battery = await self.get_battery_percent()
        gps_fix = "unknown"
        info = await self._next_from_stream(self._drone.telemetry.gps_info())
        if info is not None:
            gps_fix = f"{info.fix_type.name.lower()}_{info.num_satellites}sat"

        return Health(
            battery_percent=battery,
            gps_fix=gps_fix,
            telemetry_age_ms=0,
            link_quality=1.0,
            estimator_status="nominal",
        )

    async def is_armed(self) -> bool:
        armed = await self._next_from_stream(self._drone.telemetry.armed())
        return armed if armed is not None else False

    async def is_in_air(self) -> bool:
        in_air = await self._next_from_stream(self._drone.telemetry.in_air())
        return in_air if in_air is not None else False

    async def get_mission_progress(self) -> tuple[int, int]:
        progress = await self._next_from_stream(self._drone.telemetry.mission_progress())
        if progress is None:
            return (0, 0)
        return (progress.current, progress.total)
