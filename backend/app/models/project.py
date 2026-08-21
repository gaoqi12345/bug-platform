import sqlalchemy as sa
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from app.db.session import Base


class Project(Base):
    __tablename__ = "projects"

    id          = Column(Integer, primary_key=True, index=True)
    team_id     = Column(Integer, ForeignKey("teams.id", ondelete="RESTRICT"), nullable=False)
    name        = Column(String(200), nullable=False)
    slug        = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    status      = Column(String(20), nullable=False, default="active")
    created_at  = Column(DateTime(timezone=True), server_default=func.now())

    team     = relationship("Team", back_populates="projects")
    versions = relationship("Version", back_populates="project", cascade="all, delete-orphan")

    __table_args__ = (
        sa.UniqueConstraint("team_id", "slug", name="uq_project_team_slug"),
    )


class ProjectMembership(Base):
    __tablename__ = "project_memberships"

    id         = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    user_id    = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    role       = Column(String(20), nullable=False)
    granted_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        sa.UniqueConstraint("project_id", "user_id", name="uq_project_membership"),
    )
