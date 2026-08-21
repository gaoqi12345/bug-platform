import sqlalchemy as sa
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from app.db.session import Base
from app.models.enums import TeamRole


class Team(Base):
    __tablename__ = "teams"

    id          = Column(Integer, primary_key=True, index=True)
    name        = Column(String(100), nullable=False)
    slug        = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(sa.Text, nullable=True)
    created_at  = Column(DateTime(timezone=True), server_default=func.now())

    members  = relationship("TeamMember", back_populates="team", cascade="all, delete-orphan")
    projects = relationship("Project", back_populates="team")


class TeamMember(Base):
    __tablename__ = "team_members"

    id        = Column(Integer, primary_key=True, index=True)
    team_id   = Column(Integer, ForeignKey("teams.id", ondelete="CASCADE"), nullable=False)
    user_id   = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    role      = Column(sa.Enum(TeamRole), nullable=False, default=TeamRole.MEMBER)
    joined_at = Column(DateTime(timezone=True), server_default=func.now())

    team = relationship("Team", back_populates="members")
    user = relationship("User")

    __table_args__ = (
        sa.UniqueConstraint("team_id", "user_id", name="uq_team_members"),
    )
