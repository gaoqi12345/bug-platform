import sqlalchemy as sa
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from app.db.session import Base
from app.models.enums import VersionStatus


class Version(Base):
    __tablename__ = "versions"

    id          = Column(Integer, primary_key=True, index=True)
    project_id  = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    name        = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    status      = Column(sa.Enum(VersionStatus), nullable=False, default=VersionStatus.PLANNING)
    start_date  = Column(DateTime(timezone=True), nullable=True)
    end_date    = Column(DateTime(timezone=True), nullable=True)
    released_at = Column(DateTime(timezone=True), nullable=True)
    created_at  = Column(DateTime(timezone=True), server_default=func.now())

    project = relationship("Project", back_populates="versions")

    __table_args__ = (
        sa.UniqueConstraint("project_id", "name", name="uq_version_project_name"),
    )
