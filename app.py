from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
import os
from flask_mail import Mail, Message
import random

app = Flask(__name__)
app.secret_key = "mmu_secret_key" #Login Sessions

# 1. Database Configuration
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'database.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'your-email@gmail.com' # Your email
app.config['MAIL_PASSWORD'] = 'your-app-password'    # Your App Password
mail = Mail(app)

db = SQLAlchemy(app)

# The User Model (LSC)
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    username = db.Column(db.String(150), nullable=False)
    password = db.Column(db.String(150), nullable=False)
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
            password=password
        )
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('login'))
    return render_template('signup.html')

@app.route('/forgot', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email').lower()
        
        # Verify if the email is in MMU database
        user = User.query.filter_by(email=email).first()
        
        if user:
            # 1. Generate a random 5-digit code
            otp = str(random.randint(10000, 99999))
            session['reset_otp'] = otp # Save code in session to check later
            session['reset_email'] = email

            # 2. Send the actual email
            msg = Message('SideHustle Password Reset Code',
                          sender='your-email@gmail.com',
                          recipients=[email])
            msg.body = f"Your verification code is: {otp}"
            mail.send(msg)

            return render_template('forgot.html', show_modal=True) 
        else:
            flash("Email not found in our records!")
            return redirect(url_for('forgot_password'))
            
    return render_template('forgot.html', show_modal=False)

@app.route('/verify_code', methods=['POST'])
def verify_code():
    # 3. Combine the 5 boxes into one string
    user_code = (request.form.get('d1') + request.form.get('d2') + 
                 request.form.get('d3') + request.form.get('d4') + 
                 request.form.get('d5'))
    
    # 4. Compare with the code we sent
    if user_code == session.get('reset_otp'):
        flash("Code verified! Check your email for the next steps.")
        return redirect(url_for('login')) #need to change to reset password
    else:
        flash("Invalid code! Please try again.")
        # Re-render with modal open if code is wrong
        return render_template('forgot.html', show_modal=True)

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