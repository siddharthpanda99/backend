from abc import ABC, abstractmethod
from sqlmodel import Session

class BaseSeeder(ABC):
    key: str = ""
    dependencies: list[str] = []

    @abstractmethod
    def seed(self, session: Session):
        pass
