from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
import json


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
    unavailable_days = db.Column(db.Text, default='[]')  # JSON string like {"2025-08-05": true, "2025-08-13": true}

    # specialization flags
    is_cart_staff = db.Column(db.Boolean, default=False)
    is_turn_grill_staff = db.Column(db.Boolean, default=False)

    def get_unavailable_dates(self):
        return json.loads(self.unavailable_dates or "[]")

    def set_unavailable_dates(self, dates_list):
        self.unavailable_dates = json.dumps(dates_list)

class Shift(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)

    # normal, cart, or turn-grill
    role_type = db.Column(db.String(20), default="normal")  
    # could be: "normal", "cart", "turn_grill"

    worker_id = db.Column(db.Integer, db.ForeignKey('worker.id', ondelete="CASCADE"), nullable=True)

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
    
class ShiftTemplate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)   # e.g. "Opener"
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    role_type = db.Column(db.String(20), default="normal")  
    # normal, cart, turn_grill

import secrets
import string

def generate_random_password(length=10):
    characters = string.ascii_letters + string.digits
    return ''.join(secrets.choice(characters) for _ in range(length))