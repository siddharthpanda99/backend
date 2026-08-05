"""Tests for Audit submodule — Access Reviews & Entitlement Requests.

Uses a SQLModelSession wrapper to make raw SQLAlchemy sessions work
with services that call session.exec() (SQLModel-specific).
"""


import pytest
from datetime import datetime, timedelta

# ===========================================================================
# Access Review Tests
# ===========================================================================

class TestAccessReview:
    def test_create_review(self, sqlmodel_db):
        from common_lib.modules.rbac.audit.access_reviews import AccessReviewService
        svc = AccessReviewService(sqlmodel_db)
        review = svc.create_review(name="Q1 Access Review", reviewer_id=1)
        assert review.id is not None
        assert review.name == "Q1 Access Review"
        assert review.status == "pending"

    def test_add_and_list_items(self, sqlmodel_db):
        from common_lib.modules.rbac.audit.access_reviews import AccessReviewService
        svc = AccessReviewService(sqlmodel_db)
        review = svc.create_review(name="Review", reviewer_id=1)
        svc.add_review_item(review.id, user_id=10, resource_type="project", role_name="admin")
        svc.add_review_item(review.id, user_id=11, resource_type="project", role_name="viewer")
        items = svc.list_review_items(review.id)
        assert len(items) == 2

    def test_certify_item(self, sqlmodel_db):
        from common_lib.modules.rbac.audit.access_reviews import AccessReviewService
        svc = AccessReviewService(sqlmodel_db)
        review = svc.create_review(name="Review", reviewer_id=1)
        item = svc.add_review_item(review.id, user_id=10, resource_type="project")
        certified = svc.certify_item(item.id, reviewer_id=1, comment="Looks good")
        assert certified.status == "certified"
        assert certified.reviewer_decision == "certified"

    def test_revoke_item(self, sqlmodel_db):
        from common_lib.modules.rbac.audit.access_reviews import AccessReviewService
        svc = AccessReviewService(sqlmodel_db)
        review = svc.create_review(name="Review", reviewer_id=1)
        item = svc.add_review_item(review.id, user_id=10, resource_type="project")
        revoked = svc.revoke_item(item.id, reviewer_id=1, comment="No longer needed")
        assert revoked.status == "revoked"

    def test_review_summary(self, sqlmodel_db):
        from common_lib.modules.rbac.audit.access_reviews import AccessReviewService
        svc = AccessReviewService(sqlmodel_db)
        review = svc.create_review(name="Review", reviewer_id=1)
        svc.add_review_item(review.id, user_id=10, resource_type="project")
        svc.add_review_item(review.id, user_id=11, resource_type="project")
        summary = svc.get_review_summary(review.id)
        assert summary["total_items"] == 2
        assert summary["status_counts"]["pending"] == 2

# ===========================================================================
# Entitlement Request Tests
# ===========================================================================

class TestEntitlementRequest:
    def test_create_request(self, sqlmodel_db):
        from common_lib.modules.rbac.audit.entitlement_requests import EntitlementRequestService
        svc = EntitlementRequestService(sqlmodel_db)
        req = svc.create_request(requester_id=1, entitlement_type="role_grant",
                                  role_id=5, justification="Need admin access")
        assert req.id is not None
        assert req.status == "pending"
        assert req.entitlement_type == "role_grant"

    def test_approve_request(self, sqlmodel_db):
        from common_lib.modules.rbac.audit.entitlement_requests import EntitlementRequestService
        svc = EntitlementRequestService(sqlmodel_db)
        req = svc.create_request(requester_id=1, entitlement_type="role_grant", role_id=5)
        approved = svc.approve_request(req.id, approver_id=2, comment="Approved")
        assert approved.status == "approved"
        assert approved.approver_id == 2

    def test_deny_request(self, sqlmodel_db):
        from common_lib.modules.rbac.audit.entitlement_requests import EntitlementRequestService
        svc = EntitlementRequestService(sqlmodel_db)
        req = svc.create_request(requester_id=1, entitlement_type="role_grant", role_id=5)
        denied = svc.deny_request(req.id, approver_id=2, comment="Not needed")
        assert denied.status == "denied"

    def test_cancel_request(self, sqlmodel_db):
        from common_lib.modules.rbac.audit.entitlement_requests import EntitlementRequestService
        svc = EntitlementRequestService(sqlmodel_db)
        req = svc.create_request(requester_id=1, entitlement_type="role_grant", role_id=5)
        cancelled = svc.cancel_request(req.id, requester_id=1)
        assert cancelled.status == "cancelled"

    def test_list_requests(self, sqlmodel_db):
        from common_lib.modules.rbac.audit.entitlement_requests import EntitlementRequestService
        svc = EntitlementRequestService(sqlmodel_db)
        svc.create_request(requester_id=1, entitlement_type="role_grant", role_id=5)
        svc.create_request(requester_id=1, entitlement_type="permission_grant", permission_name="project.delete")
        reqs = svc.list_requests(requester_id=1)
        assert len(reqs) == 2

    def test_requester_summary(self, sqlmodel_db):
        from common_lib.modules.rbac.audit.entitlement_requests import EntitlementRequestService
        svc = EntitlementRequestService(sqlmodel_db)
        svc.create_request(requester_id=1, entitlement_type="role_grant", role_id=5)
        svc.create_request(requester_id=1, entitlement_type="role_grant", role_id=6)
        summary = svc.get_requester_summary(requester_id=1)
        assert summary["total_requests"] == 2
        assert summary["pending"] == 2

    def test_expire_stale_requests(self, sqlmodel_db):
        from common_lib.modules.rbac.audit.entitlement_requests import EntitlementRequestService
        svc = EntitlementRequestService(sqlmodel_db)
        # Create request with old timestamp
        req = svc.create_request(requester_id=1, entitlement_type="role_grant", role_id=5)
        # Manually age the request
        from common_lib.modules.rbac.audit.entitlement_requests import EntitlementRequest
        stored = sqlmodel_db.get(EntitlementRequest, req.id)
        stored.created_at = datetime.utcnow() - timedelta(days=60)
        sqlmodel_db.add(stored)
        sqlmodel_db.commit()
        expired = svc.expire_stale_requests(max_age_days=30)
        assert expired == 1
