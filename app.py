from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///schedule.db'
db = SQLAlchemy(app)

class Worker(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50))

class Shift(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.String(10))
    start_time = db.Column(db.String(5))
    end_time = db.Column(db.String(5))
    worker_id = db.Column(db.Integer, db.ForeignKey('worker.id'))
    worker = db.relationship('Worker')

@app.route('/')
def show_schedule():
    shifts = Shift.query.all()
    print("Shifts found:", shifts)  # DEBUG LINE
    return render_template('schedule.html', shifts=shifts)

if __name__ == '__main__':
    app.run(debug=True, host="0.0.0.0", port=5001)