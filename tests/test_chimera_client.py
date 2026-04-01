import pytest

from wyvern.contracts import ChimeraApprovalRequest, RequestedBy
from wyvern.services.chimera_client import (
    ChimeraClient,
    HttpChimeraClient,
    MockChimeraClient,
)


def _make_request() -> ChimeraApprovalRequest:
    return ChimeraApprovalRequest(
        mission_id="mis_test_001",
        trace_id="trc_test_001",
        vehicle_id="veh_test_001",
        mission_type="point_inspection",
        requested_by=RequestedBy(principal_id="usr_op_1", role="operator"),
    )


@pytest.mark.asyncio
async def test_mock_auto_approves():
    client = MockChimeraClient()
    resp = await client.request_approval(_make_request())
    assert resp.status == "approved"
    assert resp.approved_by is not None
    assert resp.approval_id.startswith("apr_")
    assert resp.chimera_trace_id is not None


@pytest.mark.asyncio
async def test_mock_rejects_when_configured():
    client = MockChimeraClient()
    client.set_rejection_reason("policy_violation")
    resp = await client.request_approval(_make_request())
    assert resp.status == "rejected"
    assert resp.reason == "policy_violation"


@pytest.mark.asyncio
async def test_mock_records_events():
    client = MockChimeraClient()
    await client.notify_mission_event(
        "mission.approved", "mis_1", "trc_1", {"key": "value"}
    )
    events = client.get_events()
    assert len(events) == 1
    assert events[0]["event_type"] == "mission.approved"
    assert events[0]["mission_id"] == "mis_1"


def test_mock_satisfies_protocol():
    client = MockChimeraClient()
    assert isinstance(client, ChimeraClient)


def test_http_satisfies_protocol():
    client = HttpChimeraClient(url="http://localhost:9999")
    assert isinstance(client, ChimeraClient)
