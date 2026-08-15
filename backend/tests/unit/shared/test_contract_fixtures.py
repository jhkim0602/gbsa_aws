from tests.fixtures.shared.factories import (
    criterion_fixture,
    invitation_fixture,
    report_fixture,
    session_fixture,
    strategy_fixture,
    tenant_fixture,
)


def test_cross_lane_fixtures_share_tenant_and_contract_references() -> None:
    tenant = tenant_fixture()
    criterion = criterion_fixture(tenant)
    invitation = invitation_fixture(tenant, criterion)
    strategy = strategy_fixture(tenant, invitation, criterion)
    session = session_fixture(tenant, invitation, strategy)
    report = report_fixture(tenant, session, criterion)

    fixture_company_ids = {
        fixture["company_id"] for fixture in (criterion, invitation, strategy, session, report)
    }

    assert fixture_company_ids == {tenant["company_id"]}
    assert strategy["criterion_version_id"] == criterion["criterion_version_id"]
    assert session["strategy_id"] == strategy["strategy_id"]
    assert report["interview_session_id"] == session["interview_session_id"]
