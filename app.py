from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
import os

app = Flask(__name__)
app.secret_key = "mmu_secret_key" #Login Sessions

# Database Configuration
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'database.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Task Model
# The User Model (Add this back!)
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    skills = db.Column(db.Text, default="No skills listed")
    is_admin = db.Column(db.Boolean, default=False)
    
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
    tasker = db.Column(db.String(50)) # Stores the username of the person hired
    progress = db.Column(db.Integer, default=0) # Stores 0, 25, 50, 75, or 100

    def get_applicant_count(self):
        # This counts how many applications have this task's ID
        return Application.query.filter_by(task_id=self.id).count()

class Application(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('task.id'), nullable=False)
    applicant_username = db.Column(db.String(50), nullable=False)
    intro = db.Column(db.Text)
    reason = db.Column(db.Text)
    status = db.Column(db.String(20), default='Pending')

with app.app_context():
    db.create_all()

# ROUTES

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        #Look for user in the database
        user = User.query.filter_by(username=username, password=password).first()

        if user: 
            session['user_id'] = user.id
            session['is_admin'] = user.is_admin
            return redirect(url_for('marketplace'))
        else:
            flash("Invalid credentials!")
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        new_user = User(
            username=request.form.get('username'),
            password=request.form.get('password')
        )
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('login'))
    return render_template('signup.html')

@app.route('/marketplace')
def marketplace():
    query = request.args.get('q')
    category = request.args.get('cat')

    tasks_filter = Task.query

    if query:
        tasks_filter = tasks_filter.filter((Task.title.contains(query)) | (Task.description.contains(query)))
    
    if category:
        tasks_filter = tasks_filter.filter(Task.category == category)

    all_tasks = tasks_filter.all()

    #Search logged-in user exxist (LSC)
    current_user = None
    if 'user_id' in session:
        current_user = User.query.get(session['user_id'])
        
    #Pass both tasks and the user to the HTML
    return render_template('marketplace.html', tasks=all_tasks, user=current_user)

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

# ✅ 新加这个，Credit 会连来这里
@app.route('/earnings')
def earnings():
    return render_template('earnings.html')

@app.route('/post', methods=['GET', 'POST'])
def post_task():
    # 1. Safety Check: Make sure the user is actually logged in
    if 'user_id' not in session:
        flash("Please login to post a task!")
        return redirect(url_for('login'))

    if request.method == 'POST':
        # 2. Get the actual user object from the database using the session ID
        current_user = User.query.get(session['user_id'])

        new_task = Task(
            title=request.form.get('title'),
            price=float(request.form.get('price')),
            description=request.form.get('description'),
            category=request.form.get('category'),
            deadline=request.form.get('deadline'),
            capacity=request.form.get('capacity'),
            urgent=True if request.form.get('urgent') else False,
            # 3. FIX: Assign the logged-in username to the 'user' field
            user=current_user.username 
        )
        db.session.add(new_task)
        db.session.commit()
        
        # After posting, go see it in My Task!
        return redirect(url_for('my_task')) 
        
    return render_template('post_task.html')

@app.route('/task/<int:task_id>')
def task_detail(task_id):
    task = Task.query.get_or_404(task_id)
    return render_template('task_detail.html', task=task)

@app.route('/apply/<int:task_id>', methods=['GET', 'POST'])
def apply(task_id):
    if 'user_id' not in session:
        flash("Please login to apply!")
        return redirect(url_for('login'))

    task = Task.query.get_or_404(task_id)
    current_user = User.query.get(session['user_id'])

    if request.method == 'POST':
        # Create a new Application record in the database
        new_app = Application(
            task_id=task.id,
            applicant_username=current_user.username,
            intro=request.form.get('intro'),
            reason=request.form.get('reason')
        )
        db.session.add(new_app)
        db.session.commit()
        
        flash("Application submitted successfully!")
        return redirect(url_for('marketplace'))

    return render_template('apply.html', task=task)

@app.route('/my_task')
def my_task():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    current_user = User.query.get(session['user_id'])
    
    # NEW: Get the 'view' from the URL. Default is 'created'
    view = request.args.get('view', 'created')

    # Fetch data same as before
    created_tasks = Task.query.filter_by(user=current_user.username).all()
    applications = Application.query.filter_by(applicant_username=current_user.username).all()
    applied_tasks = [Task.query.get(app.task_id) for app in applications]

    return render_template('my_task.html', 
                           created=created_tasks, 
                           applied=applied_tasks, 
                           view=view, # Pass 'view' to HTML
                           user=current_user)

@app.route('/view-applicants/<int:task_id>')
def view_applicants(task_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    task = Task.query.get_or_404(task_id)
    # This searches the Application table for any record matching this task's ID
    apps = Application.query.filter_by(task_id=task_id).all()
    
    return render_template('view_applicants.html', task=task, apps=apps)

@app.route('/hire-applicant/<int:app_id>')
def hire_applicant(app_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    # 1. Find the application and the task
    application = Application.query.get_or_404(app_id)
    task = Task.query.get(application.task_id)

    # 2. Update the Task: Hire the user and change status
    task.status = 'Assigned'
    task.tasker = application.applicant_username
    
    # 3. Update the Application status
    application.status = 'Hired'
    
    db.session.commit()
    
    flash(f"You have hired {application.applicant_username}!")
    return redirect(url_for('my_task', view='created'))

if __name__ == '__main__':
    app.run(debug=True)