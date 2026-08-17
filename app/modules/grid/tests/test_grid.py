# Grid Tests
import pytest
from uuid import uuid4

from common_lib.modules.data_storage.grid.models import GridConfig
from common_lib.modules.data_storage.grid.service import grid_service, NotFoundError
from common_lib.modules.data_storage.database.connection import get_session


class TestGridService:
    """Integration tests for GridService"""

    def test_save_grid_config(self, test_session):
        config = GridConfig(name="test-grid", config_json={"cols": 4})
        result = grid_service.save_grid_config(test_session, config)
        assert result.name == "test-grid"
        assert result.config_json == {"cols": 4}

    def test_list_grid_configs(self, test_session):
        configs = grid_service.list_grid_configs(test_session)
        assert isinstance(configs, list)

    def test_toggle_favorite(self, test_session):
        config = GridConfig(name="fav-test", config_json={}, is_favorite=False)
        grid_service.save_grid_config(test_session, config)

        result = grid_service.toggle_favorite(test_session, "fav-test", True)
        assert result.is_favorite == True

    def test_delete_grid_config(self, test_session):
        config = GridConfig(name="delete-test", config_json={})
        grid_service.save_grid_config(test_session, config)

        grid_service.delete_grid_config(test_session, "delete-test")
        configs = grid_service.list_grid_configs(test_session)
        names = [c.name for c in configs]
        assert "delete-test" not in names

    def test_update_existing_config(self, test_session):
        config = GridConfig(name="update-test", config_json={"cols": 2})
        grid_service.save_grid_config(test_session, config)

        updated = GridConfig(name="update-test", config_json={"cols": 6})
        result = grid_service.save_grid_config(test_session, updated)
        assert result.config_json == {"cols": 6}

    def test_toggle_favorite_raises_not_found(self, test_session):
        with pytest.raises(NotFoundError):
            grid_service.toggle_favorite(test_session, "nonexistent", True)


class TestGridModels:
    """Unit tests for Grid models"""

    def test_grid_config_creation(self):
        config = GridConfig(name="test", config_json={"x": 1})
        assert config.name == "test"
        assert config.config_json == {"x": 1}
        assert config.is_favorite == False

    def test_grid_config_defaults(self):
        config = GridConfig(name="default-test")
        assert config.config_json == {}
        assert config.metadata_json == {}
        assert config.is_favorite == False

    def test_grid_config_json_field(self):
        config = GridConfig(
            name="json-test", config_json={"rows": 3, "cols": 4, "cellSize": 100}
        )
        assert config.config_json["rows"] == 3
        assert config.config_json["cols"] == 4
        assert config.config_json["cellSize"] == 100


class TestGridServiceUnit:
    """Unit tests for Grid service methods"""

    def test_grid_service_has_required_methods(self):
        assert hasattr(grid_service, "save_grid_config")
        assert hasattr(grid_service, "list_grid_configs")
        assert hasattr(grid_service, "delete_grid_config")
        assert hasattr(grid_service, "toggle_favorite")

    def test_list_grid_configs_favorite_only(self, test_session):
        config = GridConfig(name="fav-only", config_json={}, is_favorite=True)
        grid_service.save_grid_config(test_session, config)

        fav_configs = grid_service.list_grid_configs(test_session, favorite_only=True)
        assert all(c.is_favorite for c in fav_configs)


@pytest.fixture
def test_session():
    with get_session() as session:
        yield session
