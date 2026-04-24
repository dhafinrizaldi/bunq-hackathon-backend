from datetime import datetime, timezone

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///mydb.db"
db = SQLAlchemy(app)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    split_sessions = db.relationship(
        "SplitSession", back_populates="user"
    )  # one-to-many

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class SplitSession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    user_id = db.Column(
        db.Integer, db.ForeignKey("user.id"), nullable=False
    )  # no unique=True
    user = db.relationship("User", back_populates="split_sessions")
    receipt = db.relationship("Receipt", back_populates="split_session", uselist=False)


class Receipt(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    store = db.Column(db.String, nullable=False)
    total = db.Column(db.Float, nullable=False)
    split_session_id = db.Column(
        db.Integer, db.ForeignKey("split_session.id"), unique=True, nullable=False
    )
    split_session = db.relationship("SplitSession", back_populates="receipt")


with app.app_context():
    db.create_all()
