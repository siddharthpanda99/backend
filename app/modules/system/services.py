import os
import configparser
from pathlib import Path
from typing import Dict, Any, List, Optional
from common_lib.core.infra_manager import InfraManager
from common_lib.paths import get_repo_root

class SystemService:
    def __init__(self):
        self.repo_root = get_repo_root()
        self.deploy_dir = self.repo_root / "deploy"
        self.config_path = self.deploy_dir / "config.ini"
        self.infra_manager = InfraManager(repo_root=self.repo_root)

    def get_raw_config(self) -> str:
        """Returns the raw content of config.ini."""
        if not self.config_path.exists():
            return ""
        return self.config_path.read_text()

    def update_raw_config(self, content: str) -> bool:
        """Saves raw content to config.ini and triggers sync."""
        try:
            # Validate it's a valid INI before saving
            parser = configparser.ConfigParser()
            parser.read_string(content)
            
            self.config_path.write_text(content)
            
            # Trigger sync to .env
            from deploy.sync_config import sync_config
            sync_config()
            return True
        except Exception as e:
            raise ValueError(f"Invalid INI format: {str(e)}")

    def get_structured_config(self) -> Dict[str, Dict[str, str]]:
        """Returns config.ini as a nested dictionary."""
        if not self.config_path.exists():
            return {}
        
        parser = configparser.ConfigParser()
        parser.read(self.config_path)
        
        result = {}
        for section in parser.sections():
            result[section] = dict(parser.items(section))
        return result

    def update_structured_config(self, data: Dict[str, Dict[str, str]]) -> bool:
        """Updates config.ini from a dictionary and triggers sync."""
        try:
            parser = configparser.ConfigParser()
            # If exists, read first to preserve sections not in data (additive)
            if self.config_path.exists():
                parser.read(self.config_path)
            
            for section, items in data.items():
                if not parser.has_section(section):
                    parser.add_section(section)
                for key, value in items.items():
                    parser.set(section, key, str(value))
            
            with open(self.config_path, 'w') as f:
                parser.write(f)
            
            # Trigger sync to .env
            from deploy.sync_config import sync_config
            sync_config()
            return True
        except Exception as e:
            raise ValueError(f"Failed to update config: {str(e)}")

    def get_services(self) -> List[Dict[str, Any]]:
        """Returns the current status of all satellite services."""
        return self.infra_manager.get_services_status()

    def toggle_service(self, service_id: str, action: str) -> bool:
        """Starts or stops a service."""
        if action == "up":
            return self.infra_manager.up(service_id)
        elif action == "down":
            return self.infra_manager.down(service_id)
        return False
