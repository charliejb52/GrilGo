from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin


db = SQLAlchemy()

class Worker(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)

    shifts = db.relationship('Shift', backref='worker', cascade="all, delete-orphan", passive_deletes=True)

    # Link to User table
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), unique=True)

    # Relationship so you can do worker.user
    user = db.relationship('User', backref=db.backref('worker', uselist=False))

    # Example: "Mon:9-17,Tue:12-20,Wed:off,..."
    availability = db.Column(db.String, nullable=True)

class Shift(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    worker_id = db.Column(db.Integer, db.ForeignKey('worker.id', ondelete="CASCADE"), nullable=False)

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    plaintext_password = db.Column(db.String(50))
    role = db.Column(db.String(20), nullable=False)  # 'employee' or 'manager'

    def set_password(self, password):
        self.password_hash = generate_password_hash(password, method='pbkdf2:sha256')
        self.plaintext_password = password

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
import secrets
import string

def generate_random_password(length=10):
    characters = string.ascii_letters + string.digits
    return ''.join(secrets.choice(characters) for _ in range(length))