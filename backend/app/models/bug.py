import sqlalchemy as sa
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from app.db.session import Base
from app.models.enums import BugStatus, Severity, Priority


class Bug(Base):
    __tablename__ = "bugs"

    id                  = Column(Integer, primary_key=True, index=True)
    project_id          = Column(Integer, ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False, index=True)
    title               = Column(String(500), nullable=False)
    description         = Column(Text, nullable=True)
    steps_to_reproduce  = Column(Text, nullable=True)
    expected_result     = Column(Text, nullable=True)
    actual_result       = Column(Text, nullable=True)
    environment         = Column(String(200), nullable=True)
    severity            = Column(sa.Enum(Severity), nullable=False, default=Severity.MEDIUM)
    priority            = Column(sa.Enum(Priority), nullable=False, default=Priority.P2)
    status              = Column(sa.Enum(BugStatus), nullable=False, default=BugStatus.NEW, index=True)
    found_in_version_id = Column(Integer, ForeignKey("versions.id", ondelete="SET NULL"), nullable=True)
    fixed_in_version_id = Column(Integer, ForeignKey("versions.id", ondelete="SET NULL"), nullable=True)
    reporter_id         = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    assignee_id         = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    reject_reason       = Column(Text, nullable=True)
    fix_description     = Column(Text, nullable=True)
    reopen_reason       = Column(Text, nullable=True)
    created_at          = Column(DateTime(timezone=True), server_default=func.now())
    updated_at          = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    found_in_version = relationship("Version", foreign_keys=[found_in_version_id])
    fixed_in_version = relationship("Version", foreign_keys=[fixed_in_version_id])
    reporter         = relationship("User", foreign_keys=[reporter_id])
    assignee         = relationship("User", foreign_keys=[assignee_id])
    project          = relationship("Project")
    comments         = relationship("BugComment", back_populates="bug", cascade="all, delete-orphan")
    attachments      = relationship("BugAttachment", back_populates="bug", cascade="all, delete-orphan")
    history          = relationship("BugHistory", back_populates="bug", cascade="all, delete-orphan")


class BugHistory(Base):
    __tablename__ = "bug_history"

    id         = Column(Integer, primary_key=True, index=True)
    bug_id     = Column(Integer, ForeignKey("bugs.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id    = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    field_name = Column(String(50), nullable=False)
    old_value  = Column(Text, nullable=True)
    new_value  = Column(Text, nullable=True)
    comment    = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    bug  = relationship("Bug", back_populates="history")
    user = relationship("User")


class BugComment(Base):
    __tablename__ = "bug_comments"

    id         = Column(Integer, primary_key=True, index=True)
    bug_id     = Column(Integer, ForeignKey("bugs.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id    = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    content    = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    bug  = relationship("Bug", back_populates="comments")
    user = relationship("User")


class BugAttachment(Base):
    __tablename__ = "bug_attachments"

    id           = Column(Integer, primary_key=True, index=True)
    bug_id       = Column(Integer, ForeignKey("bugs.id", ondelete="CASCADE"), nullable=False, index=True)
    file_name    = Column(String(255), nullable=False)
    object_key   = Column(String(500), nullable=False)
    file_size    = Column(Integer, nullable=True)
    content_type = Column(String(100), nullable=True)
    bucket_name  = Column(String(100), nullable=False, default="bug-attachments")
    uploaded_by  = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    uploaded_at  = Column(DateTime(timezone=True), server_default=func.now())

    bug = relationship("Bug", back_populates="attachments")
