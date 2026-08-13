"""
Tests for Secrets Manager Kubernetes submodule (SSOT 10).

Tests K8s auth configs, CSI drivers, operator configs, external secrets.
"""

from __future__ import annotations

from common_lib.modules.secrets_manager.kubernetes.service import KubernetesService


class TestKubernetesService:
    """Test K8s integration configuration management."""

    def test_create_auth_config(self, db):
        svc = KubernetesService(session=db)
        result = svc.create_auth_config(
            name="prod-cluster", cluster_name="prod-eks", namespace="secrets-ns"
        )
        assert result["name"] == "prod-cluster"
        assert result["cluster_name"] == "prod-eks"

    def test_list_auth_configs(self, db):
        svc = KubernetesService(session=db)
        svc.create_auth_config(name="cluster-a", cluster_name="eks-a")
        svc.create_auth_config(name="cluster-b", cluster_name="eks-b")
        cfgs = svc.list_auth_configs()
        assert len(cfgs) >= 2

    def test_create_csi_driver(self, db):
        svc = KubernetesService(session=db)
        result = svc.create_csi_driver(
            name="secrets-store", driver_name="secrets-store.csi.k8s.io"
        )
        assert result["name"] == "secrets-store"
        assert result["driver_name"] == "secrets-store.csi.k8s.io"

    def test_list_csi_drivers(self, db):
        svc = KubernetesService(session=db)
        svc.create_csi_driver(name="csi-1")
        svc.create_csi_driver(name="csi-2")
        drivers = svc.list_csi_drivers()
        assert len(drivers) >= 2

    def test_create_operator_config(self, db):
        svc = KubernetesService(session=db)
        result = svc.create_operator_config(name="sync-operator", operator_type="sync")
        assert result["name"] == "sync-operator"
        assert result["operator_type"] == "sync"

    def test_list_operator_configs(self, db):
        svc = KubernetesService(session=db)
        svc.create_operator_config(name="op-1")
        svc.create_operator_config(name="op-2")
        ops = svc.list_operator_configs()
        assert len(ops) >= 2

    def test_create_external_secret(self, db):
        svc = KubernetesService(session=db)
        result = svc.create_external_secret(name="aws-rds", provider="aws")
        assert result["name"] == "aws-rds"
        assert result["provider"] == "aws"

    def test_list_external_secrets(self, db):
        svc = KubernetesService(session=db)
        svc.create_external_secret(name="ext-1", provider="aws")
        svc.create_external_secret(name="ext-2", provider="gcp")
        secrets = svc.list_external_secrets()
        assert len(secrets) >= 2
