from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Worker(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)

    shifts = db.relationship('Shift', backref='worker', cascade="all, delete-orphan", passive_deletes=True)

    # Example: "Mon:9-17,Tue:12-20,Wed:off,..."
    availability = db.Column(db.String, nullable=True)

class Shift(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    worker_id = db.Column(db.Integer, db.ForeignKey('worker.id', ondelete="CASCADE"), nullable=False)