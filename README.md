# ProjectWyvern

Constitutional aerial autonomy platform. Governed mission execution for unmanned aerial systems with safety-first authority hierarchies, operator oversight, and cryptographic replay.

## What This Is

Wyvern is the **autonomy plane** in the Chimera ecosystem. It sits between the Chimera control plane (identity, policy, approvals, operator workflows) and the flight controller (PX4/ArduPilot). Wyvern owns mission validation, command arbitration, execution, telemetry normalization, and replay packaging.

The core principle: AI assists planning, but never bypasses deterministic safety or operator authority.

```
Chimera Control Plane (policy, approvals, operator sessions)
    |
    |  HTTP / OpenAPI
    v
ChimeraWyvern (this repo — mission lifecycle, safety, replay)
    |
    |  MAVSDK / MAVLink / ROS 2
    v
PX4 / ArduPilot (deterministic flight control)
```

## Architecture

### Separation of Powers

| Layer | Owns | Does NOT Own |
|-------|------|--------------|
| **Chimera** | Identity, policy, approval workflows, operator sessions, fleet governance, trace linking | Mission execution, vehicle control, telemetry |
| **Wyvern** | Mission validation, command arbitration, execution, telemetry normalization, replay | Identity, policy decisions, operator UX |
| **Flight Controller** | Low-level flight, estimator, built-in failsafes, manual control | Mission semantics, approval, replay |

### Authority Hierarchy

Highest to lowest. No lower layer may override a higher layer.

1. Onboard flight-controller failsafes
2. Manual pilot / RC override
3. Operator safety commands (abort, RTL, pause)
4. Wyvern mission executor
5. Chimera planning / AI recommendation layer

### Mission State Machine

```
draft -> validated -> awaiting_approval -> approved -> staging -> executing -> completed

Control branches:
  executing -> paused -> resuming -> executing
  executing -> rtl -> completed | failed
  executing -> aborted | failed
  validated -> rejected
  approved -> expired
  staging -> failed
  paused -> aborted | rtl
  manual_handover -> paused
```

Every state transition records: prior state, next state, actor, timestamp, trace ID, reason code.

## Specs and Contracts

| Document | Path |
|----------|------|
| TDD-006: Constitutional Aerial Autonomy | `docs/tdd/TDD006.md` |
| TDD-007: Embodied Semantic Cognition | `docs/tdd/TDD007.md` |
| Mission API (OpenAPI 3.1) | `docs/contracts/wyvern.openapi.json` |
| Mission Schema | `docs/schemas/wyvern.mission.v1.schema.json` |
| Telemetry Schema | `docs/schemas/wyvern.telemetry.v1.schema.json` |
| Replay Schema | `docs/schemas/wyvern.replay.v1.schema.json` |

## Reference Stack

| Component | Choice |
|-----------|--------|
| Autopilot | PX4 (primary), ArduPilot (secondary) |
| Autonomy framework | ROS 2 Jazzy |
| High-level vehicle API | MAVSDK |
| Simulation | Gazebo Harmonic |
| Edge compute (reference) | Jetson Orin Nano |

## Roadmap

| Phase | Description | Status |
|-------|-------------|--------|
| 0 | Specs and contracts | Complete |
| 1 | SIM-ONLY MVP: one vehicle, mission lifecycle, safety gates, replay | In progress |
| 2 | Chimera integration: control room, approval workflows, trace continuity | Planned |
| 3 | Hardware MVP: real vehicle, geofence, operator override, battery/link-loss | Planned |
| 4 | Autonomy expansion: ROS 2 services, VIO, behavior trees, obstacle avoidance | Planned |
| 5 | Field ops maturity: docking, fleet replay, staging-to-field release | Planned |

## Performance Targets

| Metric | Target |
|--------|--------|
| Mission validation latency | < 2s P95 |
| Operator safety-command acknowledgement | < 250ms P95 |
| Telemetry freshness | <= 1.5s before execution blocks |
| Replay completeness | 100% of mission-critical transitions |
| Unsafe autonomous commands outside authority | 0 |

## Related Repositories

- [BanterPacks](https://github.com/Sahil170595/BanterPacks) — Chimera ecosystem monorepo (JARVIS, TDD002, Chimera, TDD005)
- Chimeradroid — Unity companion client
- Banterhearts — Training and MLOps

## License

Proprietary. All rights reserved.
