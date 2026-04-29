from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
import os
import re

app = Flask(__name__)
app.secret_key = "mmu_secret_key" #Login Sessions

# 1. Database Configuration
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'database.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# The User Model (LSC)
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    username = db.Column(db.String(150), nullable=False)
    password = db.Column(db.String(150), nullable=False)
    security_question = db.Column(db.String(200), nullable=False)
    security_answer = db.Column(db.String(200), nullable=False)
    skills = db.Column(db.Text, default="No skills listed") #Profile Setup feature
    is_admin = db.Column(db.Boolean, default=False) #Admin Dashboard feature

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

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email').lower()
        password = request.form.get('password')

        if not email.endswith('@student.mmu.edu.my'):
            flash("Only MMU student emails are allowed to log in!")
            return redirect(url_for('login'))

        #Look for user in the database
        user = User.query.filter_by(email=email, password=password).first()

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
        email = request.form.get('email').lower()
        username = request.form.get('username')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        sec_question = request.form.get('security_question')
        sec_answer = request.form.get('security_answer').strip().lower()

        user_exists = User.query.filter_by(email=email).first()
        if user_exists:
            flash("This MMU email is already registered. Please log in!")
            return redirect(url_for('signup'))

        if not email.endswith('@student.mmu.edu.my'):
            flash("Only MMU student emails are allowed!")
            return redirect(url_for('signup'))
        
        if password != confirm_password:
            flash("Passwords do not match!")
            return redirect(url_for('signup'))
        
        new_user = User(
            email=email,
            username=username,
            password=password,
            security_question=sec_question,
            security_answer=sec_answer
        )
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('login'))
    return render_template('signup.html')

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email').lower()

        if not email.endswith('@student.mmu.edu.my'):
            flash("Only MMU student emails are allowed!")
            return redirect(url_for('forgot_password'))
        
        user = User.query.filter_by(email=email).first()
        if user:
            session['reset_email'] = email
            return render_template('forgot_password.html', show_modal=True, question=user.security_question)
        else:
            flash("Email not found!")
    return render_template('forgot_password.html', show_modal=False)

@app.route('/verify-secret', methods=['POST'])
def verify_secret():
    email = session.get('reset_email')

    if not email:
        return redirect(url_for('forgot_password'))
    
    user = User.query.filter_by(email=email).first()
    answer = request.form.get('security_answer').strip().lower()

    if answer == user.security_answer:
        return redirect(url_for('reset_password_page'))
    else:
        flash("Incorrect answer. Please try again.")
        # Re-render with the popup open if they get it wrong
        return render_template('forgot_password.html', show_modal=True, question=user.security_question)
    
@app.route('/reset-password-page')
def reset_password_page():
    if 'reset_email' not in session:
        return redirect(url_for('forgot_password'))
    return render_template('reset_password.html')

@app.route('/update-password', methods=['POST'])
def update_password():
    email = session.get('reset_email')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_new_password')

    if not email:
        return redirect(url_for('forgot_password'))
    
    password_pattern = r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d|.*[@$!%*?&]).{8,}$"
    if not re.match(password_pattern, new_password):
        flash("Password does not meet requirements!")
        return redirect(url_for('reset_password_page'))

    if new_password != confirm_password:
        flash("Passwords do not match!")
        return redirect(url_for('reset_password_page'))

    user = User.query.filter_by(email=email).first()
    if user:
        user.password = new_password
        db.session.commit()
        session.pop('reset_email', None)
        flash("Password updated! Please login with your new password.")
        return redirect(url_for('login'))
    
    return redirect(url_for('forgot_password'))

@app.route('/marketplace')
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

    #Search logged-in user exxist (LSC)
    current_user = None
    if 'user_id' in session:
        current_user = User.query.get(session['user_id'])
        
    #Pass both tasks and the user to the HTML
    return render_template('marketplace.html', tasks=all_tasks, user=current_user)

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