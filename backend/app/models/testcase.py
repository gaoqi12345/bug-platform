import sqlalchemy as sa
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from app.db.session import Base
from app.models.enums import Priority, CaseRunResult


class TestCase(Base):
    __tablename__ = "test_cases"

    id          = Column(Integer, primary_key=True, index=True)
    project_id  = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    title       = Column(String(200), nullable=False)
    precondition = Column(Text, nullable=True)
    steps       = Column(Text, nullable=True)       # 富文本 HTML
    expected_result = Column(Text, nullable=True)   # 富文本 HTML
    priority    = Column(sa.Enum('P0','P1','P2','P3', name='priority', create_type=False), nullable=False, default='P2')
    is_deprecated = Column(sa.Boolean, nullable=False, default=False)
    created_by  = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at  = Column(DateTime(timezone=True), server_default=func.now())
    updated_at  = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    creator = relationship("User", foreign_keys=[created_by])
    project = relationship("Project")
    runs    = relationship("TestRun", back_populates="case", cascade="all, delete-orphan")


class TestRun(Base):
    __tablename__ = "test_runs"

    id          = Column(Integer, primary_key=True, index=True)
    case_id     = Column(Integer, ForeignKey("test_cases.id", ondelete="CASCADE"), nullable=False)
    version_id  = Column(Integer, ForeignKey("versions.id", ondelete="SET NULL"), nullable=True)
    executor_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    result      = Column(sa.Enum('passed','failed','blocked','skipped', name='caserunresult', create_type=False), nullable=False)
    actual_result = Column(Text, nullable=True)     # 富文本 HTML，失败时填写
    bug_id      = Column(Integer, ForeignKey("bugs.id", ondelete="SET NULL"), nullable=True)
    executed_at = Column(DateTime(timezone=True), server_default=func.now())

    case     = relationship("TestCase", back_populates="runs")
    executor = relationship("User", foreign_keys=[executor_id])
    version  = relationship("Version", foreign_keys=[version_id])
    bug      = relationship("Bug", foreign_keys=[bug_id])
