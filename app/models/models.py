from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Participant(Base):
    __tablename__ = "participants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    predictions: Mapped[list["Prediction"]] = relationship("Prediction", back_populates="participant")
    nominations: Mapped[list["ScorerNomination"]] = relationship("ScorerNomination", back_populates="participant")


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    external_id: Mapped[Optional[str]] = mapped_column(String(100), unique=True)
    slug: Mapped[Optional[str]] = mapped_column(String(200))

    players: Mapped[list["Player"]] = relationship("Player", back_populates="team")


class Player(Base):
    __tablename__ = "players"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    team_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("teams.id"))
    position: Mapped[Optional[str]] = mapped_column(String(10))
    external_id: Mapped[Optional[str]] = mapped_column(String(100), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    team: Mapped[Optional["Team"]] = relationship("Team", back_populates="players")
    nominations: Mapped[list["ScorerNomination"]] = relationship("ScorerNomination", back_populates="player")

    __table_args__ = (UniqueConstraint("name", "team_id"),)


class Gameweek(Base):
    __tablename__ = "gameweeks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    number: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)
    is_locked: Mapped[bool] = mapped_column(Boolean, default=False)

    fixtures: Mapped[list["Fixture"]] = relationship(
        "Fixture", back_populates="gameweek", order_by="Fixture.id"
    )
    nominations: Mapped[list["ScorerNomination"]] = relationship("ScorerNomination", back_populates="gameweek")


class Fixture(Base):
    __tablename__ = "fixtures"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    gameweek_id: Mapped[int] = mapped_column(Integer, ForeignKey("gameweeks.id"), nullable=False)
    home_team_id: Mapped[int] = mapped_column(Integer, ForeignKey("teams.id"), nullable=False)
    away_team_id: Mapped[int] = mapped_column(Integer, ForeignKey("teams.id"), nullable=False)
    kickoff_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    home_score: Mapped[Optional[int]] = mapped_column(Integer)
    away_score: Mapped[Optional[int]] = mapped_column(Integer)
    is_finished: Mapped[bool] = mapped_column(Boolean, default=False)
    external_id: Mapped[Optional[str]] = mapped_column(String(100), unique=True)

    gameweek: Mapped["Gameweek"] = relationship("Gameweek", back_populates="fixtures")
    home_team: Mapped["Team"] = relationship("Team", foreign_keys=[home_team_id])
    away_team: Mapped["Team"] = relationship("Team", foreign_keys=[away_team_id])
    predictions: Mapped[list["Prediction"]] = relationship("Prediction", back_populates="fixture")


class Prediction(Base):
    """Tip účastníka na výsledek jednoho zápasu."""
    __tablename__ = "predictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    participant_id: Mapped[int] = mapped_column(Integer, ForeignKey("participants.id"), nullable=False)
    fixture_id: Mapped[int] = mapped_column(Integer, ForeignKey("fixtures.id"), nullable=False)
    tip_home: Mapped[int] = mapped_column(Integer, nullable=False)
    tip_away: Mapped[int] = mapped_column(Integer, nullable=False)
    points: Mapped[float] = mapped_column(Float, default=0.0)
    submitted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    participant: Mapped["Participant"] = relationship("Participant", back_populates="predictions")
    fixture: Mapped["Fixture"] = relationship("Fixture", back_populates="predictions")

    __table_args__ = (UniqueConstraint("participant_id", "fixture_id"),)


class ScorerNomination(Base):
    """Nominace hráče (0-3 na účastníka a kolo), na kterého tipuje gól/asistenci."""
    __tablename__ = "scorer_nominations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    participant_id: Mapped[int] = mapped_column(Integer, ForeignKey("participants.id"), nullable=False)
    gameweek_id: Mapped[int] = mapped_column(Integer, ForeignKey("gameweeks.id"), nullable=False)
    player_id: Mapped[int] = mapped_column(Integer, ForeignKey("players.id"), nullable=False)
    goals: Mapped[int] = mapped_column(Integer, default=0)
    assists: Mapped[int] = mapped_column(Integer, default=0)
    played: Mapped[bool] = mapped_column(Boolean, default=False)
    points: Mapped[float] = mapped_column(Float, default=0.0)
    submitted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    participant: Mapped["Participant"] = relationship("Participant", back_populates="nominations")
    gameweek: Mapped["Gameweek"] = relationship("Gameweek", back_populates="nominations")
    player: Mapped["Player"] = relationship("Player", back_populates="nominations")

    __table_args__ = (UniqueConstraint("participant_id", "gameweek_id", "player_id"),)


class DataRefreshLog(Base):
    """Audit log pro každý pokus o aktualizaci dat z Livesportu."""
    __tablename__ = "data_refresh_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    records_added: Mapped[int] = mapped_column(Integer, default=0)
    records_updated: Mapped[int] = mapped_column(Integer, default=0)
    records_skipped: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    success: Mapped[bool] = mapped_column(Boolean, default=True)
