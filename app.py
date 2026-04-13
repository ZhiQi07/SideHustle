from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
import os

app = Flask(__name__)

# 1. Database Configuration
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'database.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# 2. The Task Model
class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    description = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(20), default='Available')
    user = db.Column(db.String(50), default='Ali')
    rating = db.Column(db.Float, default=4.9)
    urgent = db.Column(db.Boolean, default=False)
    deadline = db.Column(db.String(50))
    capacity = db.Column(db.Integer, default=1)

# Create the database
with app.app_context():
    db.create_all()

# --- ROUTES ---

@app.route('/')
def marketplace():
    # 1. Get the search term from the URL (e.g., ?q=delivery)
    query = request.args.get('q')
    
    if query:
        # 2. Filter tasks where the title or description contains the search term
        all_tasks = Task.query.filter(
            (Task.title.contains(query)) | (Task.description.contains(query))
        ).all()
    else:
        # 3. If no search, show everything like usual
        all_tasks = Task.query.all()
        
    return render_template('marketplace.html', tasks=all_tasks)

@app.route('/post', methods=['GET', 'POST'])
def post_task():
    if request.method == 'POST':
        new_task = Task(
            title=request.form.get('title'),
            price=float(request.form.get('price')),
            description=request.form.get('description'),
            category=request.form.get('category'),
            deadline=request.form.get('deadline'),
            capacity=request.form.get('capacity'),
            urgent=True if request.form.get('urgent') else False
        )
        db.session.add(new_task)
        db.session.commit()
        return redirect(url_for('marketplace'))
    return render_template('post_task.html')

@app.route('/task/<int:task_id>')
def task_detail(task_id):
    task = Task.query.get_or_404(task_id)
    return render_template('task_detail.html', task=task)

# ADD THIS ROUTE BACK - This is likely why you got the BuildError
@app.route('/apply/<int:task_id>', methods=['GET', 'POST'])
def apply(task_id):
    task = Task.query.get_or_404(task_id)
    if request.method == 'POST':
        return redirect(url_for('marketplace'))
    return render_template('apply.html', task=task)

if __name__ == '__main__':
    app.run(debug=True)