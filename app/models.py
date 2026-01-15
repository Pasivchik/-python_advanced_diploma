import os
from typing import Any, Dict

from dotenv import load_dotenv
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship

load_dotenv()
db = SQLAlchemy()

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT"),
    "database": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
}

DATABASE_URL = (
    f"postgresql+psycopg2://"
    f"{DB_CONFIG['user']}:{DB_CONFIG['password']}@"
    f"{DB_CONFIG['host']}:{DB_CONFIG['port']}/"
    f"{DB_CONFIG['database']}"
)


tweet_media = db.Table(
    "tweet_media",
    db.Column(
        "tweet_id",
        db.Integer,
        db.ForeignKey("tweets.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    db.Column(
        "media_id",
        db.Integer,
        db.ForeignKey("media.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(50), nullable=False)
    api_key = db.Column(db.String(100), nullable=False, unique=True)

    tweets = db.relationship(
        "Tweet", back_populates="users", cascade="all, delete-orphan"
    )
    likes = db.relationship(
        "Like", back_populates="users", cascade="all, delete-orphan"
    )

    subscribers = db.relationship(
        "Subscribe",
        back_populates="subscribers",
        cascade="all, delete-orphan",
        foreign_keys="Subscribe.subscriber_id",
    )
    targets = db.relationship(
        "Subscribe",
        back_populates="targets",
        cascade="all, delete-orphan",
        foreign_keys="Subscribe.target_id",
    )

    def __repr__(self):
        return f"Пользователь №{self.id}\nИмя: {self.name}"

    def to_json(self) -> Dict[str, Any]:
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}


class Tweet(db.Model):
    __tablename__ = "tweets"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    tweet_data = db.Column(db.String, nullable=False)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE")
    )

    likes = db.relationship(
        "Like", back_populates="tweets", cascade="all, delete-orphan"
    )
    users = db.relationship("User", back_populates="tweets")

    medias = relationship(
        "Media", secondary=tweet_media, back_populates="tweets"
    )

    def __repr__(self):
        return f"Твит №{self.id}"

    def to_json(self) -> Dict[str, Any]:
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}


class Like(db.Model):
    __tablename__ = "likes"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    tweet_id = db.Column(
        db.Integer, db.ForeignKey("tweets.id", ondelete="CASCADE")
    )
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE")
    )

    __table_args__ = (
        db.UniqueConstraint("tweet_id", "user_id", name="uq_like"),
        db.Index("idx_tweet", "tweet_id"),
        db.Index("idx_user", "user_id"),
    )

    tweets = db.relationship("Tweet", back_populates="likes")
    users = db.relationship("User", back_populates="likes")

    def __repr__(self):
        return f"Лайк №{self.id}"

    def to_json(self) -> Dict[str, Any]:
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}


class Subscribe(db.Model):
    __tablename__ = "subscribes"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    subscriber_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE")
    )
    target_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE")
    )

    __table_args__ = (
        db.UniqueConstraint(
            "subscriber_id", "target_id", name="uq_subscriber_target"
        ),
        db.Index("idx_subscriber", "subscriber_id"),
        db.Index("idx_target", "target_id"),
    )

    subscribers = db.relationship(
        "User", foreign_keys=[subscriber_id], back_populates="subscribers"
    )
    targets = db.relationship(
        "User", foreign_keys=[target_id], back_populates="targets"
    )

    def __repr__(self):
        return (
            f"Follow("
            f"subscriber_id={self.subscriber_id}, "
            f"target_id={self.target_id})"
        )

    def to_json(self) -> Dict[str, Any]:
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}


class Media(db.Model):
    __tablename__ = "media"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    file_name = db.Column(db.String, nullable=False)
    file_path = db.Column(db.String, nullable=False)

    tweets = relationship(
        "Tweet", secondary=tweet_media, back_populates="medias"
    )

    def __repr__(self):
        return f"Файл №{self.id}"

    def to_json(self) -> Dict[str, Any]:
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}
