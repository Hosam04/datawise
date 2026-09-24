from abc import ABC, abstractmethod
from backend.utils.logger import setup_logger

class BaseAgent(ABC):
    def __init__(self, name: str):
        self.logger = setup_logger(name)
        self.name = name

    def log_execution(self, session_id: str):
        self.logger.info("Executing %s for session: %s", self.name, session_id)

    @abstractmethod
    def run(self, state):
        pass