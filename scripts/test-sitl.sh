#!/usr/bin/env bash
# Run the Wyvern mission lifecycle against a running PX4 SITL.
# Prereq: PX4 SITL running on localhost:14540
#         Wyvern server running on localhost:8600 with WYVERN_USE_MOCK_VEHICLE=false
#
# Usage: bash scripts/test-sitl.sh

set -euo pipefail

BASE="http://localhost:8600/api/v1"
MISSION_FILE="tests/fixtures/sample_mission.json"

echo "=== Checking Wyvern health ==="
curl -sf "$BASE/health" | python3 -m json.tool
echo ""

echo "=== 1. Create mission ==="
RESP=$(curl -sf -X POST "$BASE/missions" \
    -H "Content-Type: application/json" \
    -d @"$MISSION_FILE")
echo "$RESP" | python3 -m json.tool
MISSION_ID=$(echo "$RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['mission_id'])")
echo "Mission ID: $MISSION_ID"
echo ""

echo "=== 2. Validate ==="
curl -sf -X POST "$BASE/missions/$MISSION_ID/validate" | python3 -m json.tool
echo ""

echo "=== 3. Approve ==="
curl -sf -X POST "$BASE/missions/$MISSION_ID/approve" | python3 -m json.tool
echo ""

echo "=== 4. Execute ==="
curl -sf -X POST "$BASE/missions/$MISSION_ID/execute" | python3 -m json.tool
echo ""

echo "=== 5. Monitoring (polling every 2s) ==="
for i in $(seq 1 30); do
    STATE=$(curl -sf "$BASE/missions/$MISSION_ID/state" | python3 -c "import sys,json; print(json.load(sys.stdin)['state'])")
    echo "  [$i] State: $STATE"

    if [ "$STATE" = "completed" ] || [ "$STATE" = "failed" ] || [ "$STATE" = "aborted" ] || [ "$STATE" = "rtl" ]; then
        break
    fi

    # Print telemetry
    TELEM=$(curl -sf "$BASE/vehicles/veh_px4_sitl_001/telemetry" 2>/dev/null || echo '{}')
    BAT=$(echo "$TELEM" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f\"  bat={d.get('health',{}).get('battery_percent','?')}% pos=({d.get('position',{}).get('lat','?')},{d.get('position',{}).get('lon','?')}) alt={d.get('position',{}).get('alt_m','?')}m\")" 2>/dev/null || true)
    echo "$BAT"

    sleep 2
done
echo ""

echo "=== 6. Timeline / Replay ==="
curl -sf "$BASE/missions/$MISSION_ID/timeline" | python3 -m json.tool
echo ""

echo "=== 7. Event history ==="
curl -sf "$BASE/missions/$MISSION_ID/events" | python3 -m json.tool
echo ""

echo "=== Done ==="
