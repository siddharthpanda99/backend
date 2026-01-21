import yaml
import os
from sqlmodel import Session, select
from app.modules.database.service.seeder_base import BaseSeeder
from app.modules.users.models.user import User

class UserSeeder(BaseSeeder):
    key = "users"
    dependencies = ["auth"]

    def seed(self, session: Session):
        fixture_path = os.path.join(os.path.dirname(__file__), "..", "fixtures", "users.yaml")
        if not os.path.exists(fixture_path):
            print(f"Warning: Fixture file not found: {fixture_path}")
            return

        with open(fixture_path, "r") as f:
            data = yaml.safe_load(f)
            
        users_data = data.get("users", [])
        
        for u_data in users_data:
            email = u_data["email"]
            user = session.exec(select(User).where(User.email == email)).first()
            if not user:
                user = User(
                    email=email,
                    username=u_data["username"],
                    full_name=u_data.get("full_name"),
                    hashed_password="nexus_password", # Default password
                    is_active=u_data.get("is_active", True)
                )
                session.add(user)
                # Assign roles here if needed, assuming auth ran first
