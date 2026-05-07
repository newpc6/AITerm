from sqlalchemy import Column, Integer, String, Text, ForeignKey

from app.db.base import Base


class ScheduledTaskModel(Base):
    __tablename__ = "scheduled_tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, default="")
    agent_id = Column(Integer, ForeignKey("agents.id"), nullable=True)
    input_message = Column(Text, nullable=False)
    enabled = Column(Integer, default=1)
    cron_expression = Column(String(100), nullable=False)
    node_id = Column(Integer, ForeignKey("nodes.id"), nullable=True)
    max_retries = Column(Integer, default=0)
    timeout_seconds = Column(Integer, default=300)
    last_run_at = Column(String(50), nullable=True)
    last_result = Column(String(50), nullable=True)
    next_run_at = Column(String(50), nullable=True)
    created_at = Column(String(50), nullable=False)
    updated_at = Column(String(50), nullable=False)


class ScheduledTaskLogModel(Base):
    __tablename__ = "scheduled_task_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(Integer, ForeignKey("scheduled_tasks.id"), nullable=False)
    status = Column(String(20), nullable=False)
    output = Column(Text, default="")
    error = Column(Text, default="")
    started_at = Column(String(50), nullable=False)
    finished_at = Column(String(50), nullable=True)
    created_at = Column(String(50), nullable=False)
