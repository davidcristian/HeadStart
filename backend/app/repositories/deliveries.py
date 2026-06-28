"""Data access for DeliveryLog."""

from sqlalchemy.orm import Session

from app.models.delivery_log import DeliveryLog


class DeliveryLogRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, log: DeliveryLog) -> DeliveryLog:
        self.session.add(log)
        self.session.flush()
        return log
