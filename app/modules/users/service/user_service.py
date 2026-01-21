from typing import List, Optional
from sqlmodel import Session, select
from app.modules.users.models.user import User
from app.modules.users.schemas.user import UserCreate, UserUpdate

class UserService:
    def __init__(self, session: Session):
        self.session = session

    def get_user(self, user_id: int) -> Optional[User]:
        return self.session.get(User, user_id)

    def get_user_by_email(self, email: str) -> Optional[User]:
        return self.session.exec(select(User).where(User.email == email)).first()

    def list_users(self, skip: int = 0, limit: int = 100) -> List[User]:
        return self.session.exec(select(User).offset(skip).limit(limit)).all()

    def create_user(self, user_in: UserCreate) -> User:
        # In a real app, hash the password here
        db_user = User(
            username=user_in.username,
            email=user_in.email,
            full_name=user_in.full_name,
            hashed_password=user_in.password, # Plaintext for prototype as requested implied by "simple"
            is_active=user_in.is_active
        )
        self.session.add(db_user)
        self.session.commit()
        self.session.refresh(db_user)
        return db_user

    def update_user(self, user_id: int, user_in: UserUpdate) -> Optional[User]:
        db_user = self.get_user(user_id)
        if not db_user:
            return None
        
        user_data = user_in.model_dump(exclude_unset=True)
        for key, value in user_data.items():
            if key == "password":
                key = "hashed_password" # Handle password update mapping
            setattr(db_user, key, value)
            
        self.session.add(db_user)
        self.session.commit()
        self.session.refresh(db_user)
        return db_user

    def delete_user(self, user_id: int) -> bool:
        db_user = self.get_user(user_id)
        if not db_user:
            return False
        
        self.session.delete(db_user)
        self.session.commit()
        return True
