from flask import Flask, render_template, request, redirect, url_for
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

@app.route('/add', methods=['GET', 'POST'])
def add_shift():
    workers = Worker.query.all()

    if request.method == 'POST':
        date = request.form['date']
        start_time = request.form['start_time']
        end_time = request.form['end_time']
        worker_id = request.form['worker_id']

        new_shift = Shift(date=date, start_time=start_time, end_time=end_time, worker_id=worker_id)
        db.session.add(new_shift)
        db.session.commit()
        return redirect(url_for('show_schedule'))

    return render_template('add_shift.html', workers=workers)

print(app.url_map)

if __name__ == '__main__':
    app.run(debug=True, host="0.0.0.0", port=5001)


