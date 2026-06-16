# 🚀 CHOOSE THIS NEW ASYNC-SAFE STARTUP BLOCK:
import eventlet
eventlet.monkey_patch()  # 🛡️ MUST BE THE FIRST EXECUTED OPERATIONS LINE ON THE SERVER!

from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_socketio import SocketIO, emit, join_room
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func, text
import os
from datetime import datetime
from sqlalchemy import or_
from datetime import timezone, timedelta
my8 = timezone(timedelta(hours=8))
import re
# 🚀 Added for cloud support
from dotenv import load_dotenv

app = Flask(__name__)
app.secret_key = "mmu_secret_key"
socketio = SocketIO(app, cors_allowed_origins="*")

# 🚀 Safe environment variable checker config loop
load_dotenv()
database_url = os.getenv('DATABASE_URL')
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url or 'sqlite:///' + os.path.join(os.path.abspath(os.path.dirname(__file__)), 'database.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- Your models (class User, class Task, etc.) continue normally right below here ---

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    username = db.Column(db.String(150), unique=True, nullable=False)
    display_name = db.Column(db.String(150), nullable=True)
    password = db.Column(db.String(150), nullable=False)
    security_question = db.Column(db.String(200), nullable=False)
    security_answer = db.Column(db.String(200), nullable=False)
    bio = db.Column(db.Text, default="No bio currently")
    avatar = db.Column(db.String(200), nullable=True)
    
    # --- Shared & Your Features ---
    skills = db.Column(db.Text, default="No skills listed")
    is_admin = db.Column(db.Boolean, default=False)
    credit = db.Column(db.Float, default=0.0)
    total_rating = db.Column(db.Float, default=5.0)
    review_count = db.Column(db.Integer, default=1)
    tasks_completed = db.Column(db.Integer, default=0)

    def count_total_unread(self, role='all'):
        if role == 'created':
            tasks = Task.query.filter_by(user=self.username).all()
        elif role == 'applied':
            hired_apps = Application.query.filter_by(
                applicant_username=self.username, status='Hired'
            ).all()
            task_ids = [a.task_id for a in hired_apps]
            tasks = Task.query.filter(Task.id.in_(task_ids)).all()
        else:
            created_tasks = Task.query.filter_by(user=self.username).all()
            hired_apps = Application.query.filter_by(
                applicant_username=self.username, status='Hired'
            ).all()
            task_ids = {task.id for task in created_tasks}
            task_ids.update(a.task_id for a in hired_apps)
            tasks = Task.query.filter(Task.id.in_(task_ids)).all()
        total = 0
        for task in tasks:
            total += task.get_unread_count(self.username)
        return total


class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    description = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(20), default='Available')
    user = db.Column(db.String(50))
    tasker = db.Column(db.String(50))
    deadline = db.Column(db.String(50))
    capacity = db.Column(db.Integer, default=1)
    progress = db.Column(db.Integer, default=0)
    urgent = db.Column(db.Boolean, default=False)
    is_negotiable = db.Column(db.Boolean, default=False)
    is_pinned = db.Column(db.Boolean, default=False)

    def get_applicant_count(self):
        return Application.query.filter_by(task_id=self.id).count()

    # FIX: 删掉重复的，只保留精确版本
    def get_unread_count(self, current_username):
        messages = Message.query.filter_by(task_id=self.id).filter(
            Message.sender != current_username
        ).all()
        count = 0
        for msg in messages:
            already_read = MessageRead.query.filter_by(
                message_id=msg.id, username=current_username
            ).first()
            if not already_read:
                count += 1
        return count

    def get_hired_count(self):
        return Application.query.filter_by(task_id=self.id, status='Hired').count()

    def get_hired_usernames(self):
        hired_apps = Application.query.filter_by(task_id=self.id, status='Hired').all()
        return [app.applicant_username for app in hired_apps]


class Application(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('task.id'), nullable=False)
    applicant_username = db.Column(db.String(50), nullable=False)
    intro = db.Column(db.Text)
    reason = db.Column(db.Text)
    status = db.Column(db.String(20), default='Pending')


class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('task.id'), nullable=False)
    sender = db.Column(db.String(50), nullable=False)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=db.func.now())
    is_read = db.Column(db.Boolean, default=False)
    is_edited = db.Column(db.Boolean, default=False)
    is_deleted = db.Column(db.Boolean, default=False)
    reply_to_id = db.Column(db.Integer, db.ForeignKey('message.id'), nullable=True)
    replied_message = db.relationship('Message', remote_side=[id], backref='replies')

class DirectMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_username = db.Column(db.String(50), nullable=False)
    receiver_username = db.Column(db.String(50), nullable=False)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=db.func.now())
    is_read = db.Column(db.Boolean, default=False)

class Earning(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    activity = db.Column(db.String(150), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    timestamp = db.Column(db.DateTime, default=db.func.now())
class Report(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('task.id'), nullable=False)
    reporter_username = db.Column(db.String(50), nullable=False)
    reason = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=db.func.now())


class Rating(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('task.id'), nullable=False)
    reviewer_username = db.Column(db.String(50), nullable=False)
    target_username = db.Column(db.String(50), nullable=False)
    score = db.Column(db.Integer, nullable=False)
    review_content = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=db.func.now())
    task = db.relationship('Task', backref='ratings')


class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    task_id = db.Column(db.Integer, db.ForeignKey('task.id'))
    message = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(20), default='unread')
    timestamp = db.Column(db.DateTime, default=db.func.now())


class MessageRead(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    message_id = db.Column(db.Integer, db.ForeignKey('message.id'), nullable=False)
    username = db.Column(db.String(50), nullable=False)

with app.app_context():
    db.create_all()

@app.context_processor
def inject_user():
    """This makes the 'user' variable available in every template"""
    user = None
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
    return dict(user=user)

def get_task_member_usernames(task):
    members = {task.user}
    for app_record in Application.query.filter_by(task_id=task.id, status='Hired').all():
        members.add(app_record.applicant_username)
    return members


def user_can_access_task_chat(task, user):
    return user and user.username in get_task_member_usernames(task)


def user_can_rate_target(task, reviewer_username, target_username):
    hired_usernames = set(task.get_hired_usernames())
    if reviewer_username == task.user:
        return target_username in hired_usernames
    if reviewer_username in hired_usernames:
        return target_username == task.user
    return False


@app.template_filter('money_amount')
def money_amount(value):
    amount = round(float(value or 0), 2)
    if amount.is_integer():
        return f"{amount:,.0f}"
    return f"{amount:,.2f}"

# 🚀 PASTE THIS NEW RELATIVE TIME CONVERTER FILTER INTO APP.PY:
@app.template_filter('time_ago')
def time_ago(value):
    if not value:
        return "Just Now"
    
    now = datetime.now()
    # Handle timezone differences safely if your database uses naive timestamps
    diff = now - value
    
    second_diff = diff.seconds
    day_diff = diff.days

    if day_diff < 0:
        return "Just Now"

    if day_diff == 0:
        if second_diff < 10:
            return "Just Now"
        if second_diff < 60:
            return f"{second_diff} seconds ago"
        if second_diff < 120:
            return "a minute ago"
        if second_diff < 3600:
            return f"{second_diff // 60} minutes ago"
        if second_diff < 7200:
            return "an hour ago"
        if second_diff < 86400:
            return f"{second_diff // 3600} hours ago"
            
    if day_diff == 1:
        return "Yesterday"
    if day_diff < 7:
        return f"{day_diff} days ago"
    if day_diff < 31:
        return f"{day_diff // 7} weeks ago"
        
    return value.strftime('%b %d, %Y')

@app.context_processor
def inject_global_unread():
    if 'user_id' not in session:
        return {"global_unread_count": 0}
    try:
        user = db.session.get(User, session['user_id'])
        if not user:
            return {"global_unread_count": 0}
        count = db.session.execute(
            text("""
                SELECT COUNT(*)
                FROM message m
                WHERE m.sender != :uname
                AND m.task_id IN (
                    SELECT id FROM task WHERE user = :uname
                    UNION
                    SELECT task_id FROM application
                    WHERE applicant_username = :uname AND status = 'Hired'
                )
                AND NOT EXISTS (
                    SELECT 1 FROM message_read mr
                    WHERE mr.message_id = m.id AND mr.username = :uname
                )
            """),
            {"uname": user.username}
        ).scalar()
        return {"global_unread_count": count or 0}
    except:
        return {"global_unread_count": 0}


@app.context_processor
def inject_notifications():
    if 'user_id' in session:
        current_user = User.query.get(session['user_id'])
        if current_user:
            user_notifications = Notification.query.filter_by(
                user_id=current_user.id
            ).order_by(Notification.id.desc()).limit(5).all()
            return dict(notifications=user_notifications)
        else:
            session.pop('user_id', None)
    return dict(notifications=[])

@app.context_processor
def inject_user_globally():
    if 'user_id' in session:
        current_user = db.session.get(User, session['user_id'])
        if current_user:
            return dict(user=current_user)
    return dict(user=None)

def cleanup_expired_tasks():
    today = datetime.now().strftime('%Y-%m-%d')
    expired_tasks = Task.query.filter(
        Task.deadline != "",
        Task.deadline < today,
        Task.status == 'Available'
    ).all()
    for task in expired_tasks:
        if task.get_applicant_count() == 0:
            owner = User.query.filter_by(username=task.user).first()
            if owner:
                db.session.add(Notification(
                    user_id=owner.id,
                    message=f"System: Your task '{task.title}' has expired and was removed due to 0 applicants.",
                    status='unread'
                ))
            db.session.delete(task)
    db.session.commit()

@app.route('/clear_notifications', methods=['POST'])
def clear_notifications():
    if 'user_id' not in session:
        return {"status": "unauthorized"}, 401
        
    # Delete or change status of notifications belonging to this user
    Notification.query.filter_by(user_id=session['user_id']).delete()
    db.session.commit()
    return {"status": "success"}, 200

@app.route('/')
def index():
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').lower()
        password = request.form.get('password')
        if not email.endswith('@student.mmu.edu.my'):
            flash("Only MMU student emails are allowed to log in!")
            return redirect(url_for('login'))
        user = User.query.filter_by(email=email, password=password).first()
        if user:
            session['user_id'] = user.id
            return redirect(url_for('marketplace'))
        flash("Invalid email or password!")
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
        if User.query.filter_by(email=email).first():
            flash("This MMU email is already registered. Please log in!")
            return redirect(url_for('signup'))
        if not email.endswith('@student.mmu.edu.my'):
            flash("Only MMU student emails are allowed!")
            return redirect(url_for('signup'))
        if password != confirm_password:
            flash("Passwords do not match!")
            return redirect(url_for('signup'))
        db.session.add(User(
            email=email, username=username, password=password,
            security_question=sec_question, security_answer=sec_answer
        ))
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
    flash("Incorrect answer. Please try again.")
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
    if not re.match(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d|.*[@$!%*?&]).{8,}$", new_password):
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

@app.route('/profile')
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user = db.session.get(User, session['user_id'])
    return render_template('profile.html', user=user)

@app.route('/update_profile', methods=['POST'])
def update_profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = db.session.get(User, session['user_id'])
    field = request.form.get('field')
    value = request.form.get('value')

    if field == 'displayname':
        user.display_name = value
    elif field == 'username':
        user.username = value
    elif field == 'bio':
        user.bio = value
    elif field == 'skills':
        user.skills = value
    elif field == 'avatar':
        file = request.files.get('avatar')
        if file and file.filename != '':

            upload_folder = os.path.join(basedir, 'static', 'uploads')
            os.makedirs(upload_folder, exist_ok=True)
            
            filename = f"user_{user.id}_{file.filename}"
            file.save(os.path.join(upload_folder, filename))
            
            user.avatar = filename
        
    elif field == 'remove_avatar':
        user.avatar = None

    db.session.commit()
    return redirect(url_for('profile'))

@app.route('/update_security', methods=['POST'])
def update_security():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    user = db.session.get(User, session['user_id'])
    field = request.form.get('field')
    value1 = request.form.get('value1')
    value2 = request.form.get('value2')

    if field == 'password':
        if value1 and len(value1) >= 8: # Basic processing validation rule
            user.password = value1
    elif field == 'security_question':
        user.security_question = value1
        if value2:
            user.security_answer = value2.strip().lower()

    db.session.commit()
    return '', 200

@app.route('/delete_account', methods=['POST'])
def delete_account():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    user = db.session.get(User, session['user_id'])
    if user:
        db.session.delete(user)
        db.session.commit()
        
    session.clear()
    flash("Your account has been permanently deleted.")
    return redirect(url_for('login'))

@app.route('/marketplace')
def marketplace():
    cleanup_expired_tasks()
    
    # 1. Gather all incoming parameters from the URL first
    query = request.args.get('q')
    category = request.args.get('cat')
    min_price = request.args.get('min_p')
    max_price = request.args.get('max_p')
    
    # 2. Setup base filter query
    tasks_filter = Task.query.filter_by(status='Available')
    
    # 3. Apply Text Search Filter
    if query:
        tasks_filter = tasks_filter.filter(
            (Task.title.contains(query)) | (Task.description.contains(query))
        )
        
    # 4. Apply Category Selection Filter
    if category:
        tasks_filter = tasks_filter.filter(Task.category == category)

    # 5. Apply Budget Pricing Range Filters safely
    if min_price and min_price.strip():
        tasks_filter = tasks_filter.filter(Task.price >= float(min_price))
    if max_price and max_price.strip():
        tasks_filter = tasks_filter.filter(Task.price <= float(max_price))
        
    # 6. Execute database retrieval
    all_tasks = tasks_filter.all()
    
    # 7. Check authentication session
    current_user = None
    if 'user_id' in session:
        current_user = db.session.get(User, session['user_id'])
        
    return render_template('marketplace.html', tasks=all_tasks, user=current_user)


@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = db.session.get(User, session['user_id'])
    hired_apps = Application.query.filter_by(applicant_username=user.username, status='Hired').all()
    hired_task_ids = [app.task_id for app in hired_apps]
    # 只查询进度小于 100% 且你被录用了的任务
    tracking_list = Task.query.filter(
        Task.id.in_(hired_task_ids),
        Task.progress < 100
    ).all()
    avg_rating = round(user.total_rating / user.review_count, 1) if user.review_count > 0 else 5.0
    return render_template('dashboard.html',
        username=user.username, total_credit=user.credit,
        average_rating=avg_rating, tasks_done=user.tasks_completed,
        tracking_list=tracking_list)


@app.route('/update_progress/<int:task_id>', methods=['POST'])
def update_progress(task_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    new_progress = int(request.form.get('progress', 0))
    task = db.session.get(Task, task_id)
    user = db.session.get(User, session['user_id'])
    if not task or not user_can_rate_target(task, user.username, task.user):
        flash("Only hired taskers can update this task progress.")
        return redirect(url_for('my_task'))
    if new_progress == 100 and task.status != 'Completed':
        task.status = 'Completed'
        owner = User.query.filter_by(username=task.user).first()
        if owner:
            db.session.add(Notification(
                user_id=owner.id,
                task_id=task.id,
                message=f"Milestone Alert: @{user.username} marked your task '{task.title}' as 100% complete!"
            ))
        socketio.emit('new_unread', {'task_id': task.id, 'role': 'created'}, room=str(owner.id))
        for app_record in Application.query.filter_by(task_id=task.id, status='Hired').all():
            worker = User.query.filter_by(username=app_record.applicant_username).first()
            if worker:
                if worker.tasks_completed is None:
                    worker.tasks_completed = 0
                worker.tasks_completed += 1
                if task.price:
                    if worker.credit is None:
                        worker.credit = 0.0
                    worker.credit += task.price
                    db.session.add(Earning(
                        user_id=worker.id,
                        activity=f"Completed Task: {task.title}",
                        amount=task.price,
                        timestamp=datetime.now()
                    ))
    task.progress = new_progress
    db.session.commit()
    return redirect(url_for('my_task', view='applied'))


@app.route('/earnings')
def earnings():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = db.session.get(User, session['user_id'])
    earnings_list = Earning.query.filter_by(user_id=user.id).order_by(Earning.timestamp.desc()).all()
    return render_template('earnings.html', earnings_list=earnings_list, total_credit=user.credit)


@app.route('/post', methods=['GET', 'POST'])
def post_task():
    if 'user_id' not in session:
        flash("Please login to post a task!")
        return redirect(url_for('login'))

    if request.method == 'POST':
        current_user = User.query.get(session['user_id'])
        capacity = request.form.get('capacity') or 1

        # 1. 💡 Store the new Task instance inside the 'new_task' variable first
        new_task = Task(
            title=request.form.get('title'),
            price=float(request.form.get('price')),
            description=request.form.get('description'),
            category=request.form.get('category'),
            deadline=request.form.get('deadline'),
            capacity=max(1, int(capacity)),
            urgent=True if request.form.get('urgent') else False,
            user=current_user.username,
            is_negotiable=True if request.form.get('is_negotiable') else False
        )
        # 2. ✅ Pass that variable to your session handlers cleanly
        db.session.add(new_task)
        db.session.commit()
        
        return redirect(url_for('my_task')) 
        
    return render_template('post_task.html')


@app.route('/edit_task/<int:task_id>', methods=['GET', 'POST'])
def edit_task(task_id):
    task = Task.query.get_or_404(task_id)
    user = User.query.get(session.get('user_id'))
    if not user or task.user != user.username:
        flash("You are not authorized to edit this task!")
        return redirect(url_for('my_task'))
        
    if request.method == 'POST':
        task.title = request.form.get('title')
        task.category = request.form.get('category')
        task.description = request.form.get('description')
        task.deadline = request.form.get('deadline')
        
        # 🔗 ✅ FIX: Extract and save the new helper capacity value
        new_capacity = request.form.get('capacity')
        if new_capacity:
            # max() fallback ensures employers can't pass numbers lower than already hired teams
            task.capacity = max(task.get_hired_count(), int(new_capacity))
        
        # --- NEW PRICE SAFE LOCK CHECK ---
        if task.get_hired_count() == 0:
            task.price = float(request.form.get('price', task.price))
        else:
            print(f"🔒 Price change blocked for Task {task.id} because a team member is already hired.")

        db.session.commit()
        flash("Task updated successfully!")
        return redirect(url_for('my_task'))
        
    return render_template('edit_task.html', task=task)

@app.route('/delete_task/<int:task_id>')
def delete_task(task_id):
    task = Task.query.get_or_404(task_id)
    user = User.query.get(session.get('user_id'))
    if not user or task.user != user.username:
        flash("Unauthorized action!")
        return redirect(url_for('my_task'))
    if task.get_hired_count() > 0:
        flash("Cannot delete a task that has active hired help!")
        return redirect(url_for('my_task'))
    for app_record in Application.query.filter_by(task_id=task.id, status='Pending').all():
        applicant = User.query.filter_by(username=app_record.applicant_username).first()
        if applicant:
            db.session.add(Notification(
                user_id=applicant.id,
                message=f"Alert: The task '{task.title}' you applied for was deleted by the owner.",
                status='unread'
            ))
    Application.query.filter_by(task_id=task.id).delete()
    db.session.delete(task)
    db.session.commit()
    flash("Task deleted successfully. Pending applicants have been notified.")
    return redirect(url_for('my_task'))

@app.route('/report_task/<int:task_id>', methods=['POST'])
def report_task(task_id):
    if 'user_id' not in session:
        flash("Please login to report a task!")
        return redirect(url_for('login'))
        
    current_user = User.query.get(session['user_id'])
    task = Task.query.get_or_404(task_id)
    
    reason = request.form.get('reason')
    description = request.form.get('description')
    
    if not reason or not description:
        flash("Please fill in all fields to submit a report.")
        return redirect(url_for('task_detail', task_id=task.id))
        
    # Prevent self-reporting (Optional but recommended for demo)
    if task.user == current_user.username:
        flash("You cannot report your own task!")
        return redirect(url_for('task_detail', task_id=task.id))

    new_report = Report(
        task_id=task.id,
        reporter_username=current_user.username,
        reason=reason,
        description=description
    )
    
    db.session.add(new_report)
    db.session.commit()
    
    flash("Thank you. The task has been reported to an admin for review.")
    return redirect(url_for('task_detail', task_id=task.id))

# 🚀 UPDATE THIS TOGGLE_PIN ROUTE IN APP.PY:
@app.route('/toggle_pin/<int:task_id>')
def toggle_pin(task_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    task = Task.query.get_or_404(task_id)
    user = User.query.get(session['user_id'])
    
    is_owner = (task.user == user.username)
    is_hired = Application.query.filter_by(task_id=task.id, applicant_username=user.username, status='Hired').first()
    
    if not is_owner and not is_hired:
        flash("You are not authorized to pin this item!")
        return redirect(url_for('my_task'))
        
    task.is_pinned = not task.is_pinned
    db.session.commit()
    
    # 🔗 ✅ FIX: Dynamically match the active tab view string format parameter
    view_type = request.args.get('redirect_view', 'created')
    flash("Task priority updated successfully!")
    return redirect(url_for('my_task', view=view_type))

def patch_database():
    with db.engine.connect() as conn:
        # 1. 检查 User 表
        user_cols = [row[1] for row in conn.execute(text("PRAGMA table_info(user)")).fetchall()]
        if "credit" not in user_cols:
            conn.execute(text("ALTER TABLE user ADD COLUMN credit FLOAT DEFAULT 0.0"))
        if "total_rating" not in user_cols:
            conn.execute(text("ALTER TABLE user ADD COLUMN total_rating FLOAT DEFAULT 5.0"))
        if "review_count" not in user_cols:
            conn.execute(text("ALTER TABLE user ADD COLUMN review_count INTEGER DEFAULT 1"))
        if "tasks_completed" not in user_cols:
            conn.execute(text("ALTER TABLE user ADD COLUMN tasks_completed INTEGER DEFAULT 0"))
        
        # 2. 检查 Task 表
        task_cols = [row[1] for row in conn.execute(text("PRAGMA table_info(task)")).fetchall()]
        if "urgent" not in task_cols:
            conn.execute(text("ALTER TABLE task ADD COLUMN urgent BOOLEAN DEFAULT 0"))
        # --- NEW CODE: Dynamically patches and creates the is_negotiable column column on your disk database ---
        if "is_negotiable" not in task_cols:
            conn.execute(text("ALTER TABLE task ADD COLUMN is_negotiable BOOLEAN DEFAULT 0"))
            print("✅ Task table patched with is_negotiable column!")
        
        # 3. 检查 Message 表
        table_check = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='message'")).fetchone()

        if table_check:
            message_cols = [row[1] for row in conn.execute(text("PRAGMA table_info(message)")).fetchall()]
            if "is_read" not in message_cols:
                conn.execute(text("ALTER TABLE message ADD COLUMN is_read BOOLEAN DEFAULT 0"))
                print("✅ Message table patched!")
        else:
            print("ℹ️ Message table doesn't exist yet, skipping patch.")



@app.route('/task/<int:task_id>')
def task_detail(task_id):
    task = Task.query.get_or_404(task_id)
    current_user = User.query.get(session['user_id'])
    return render_template('task_detail.html', task=task, user=current_user)


@app.route('/task_tracking/<int:task_id>')
def task_tracking(task_id):
    return f"This is tracking page for Task {task_id}. Developing..."


# 🚀 REPLACE WITH THIS SECURE COMBINED FLOW:
@app.route('/apply/<int:task_id>', methods=['GET', 'POST'])
def apply(task_id):
    # 1. Ensure user is logged in
    if 'user_id' not in session:
        flash("Please login to apply!")
        return redirect(url_for('login'))
        
    task = Task.query.get_or_404(task_id)
    current_user = User.query.get(session['user_id'])
    
    # 2. 🛡️ GLOBAL SECURITY BARRIER: Kick out creators on BOTH GET and POST requests instantly!
    if task.user == current_user.username:
        flash("Access Denied: You cannot apply for a task you created yourself!")
        return redirect(url_for('marketplace'))
        
    # 3. Double application checker fallback
    if Application.query.filter_by(task_id=task.id, applicant_username=current_user.username).first():
        flash("You have already submitted an application for this task!")
        return redirect(url_for('marketplace'))

    # 4. Handle form submission
    if request.method == 'POST':
        db.session.add(Application(
            task_id=task.id,
            applicant_username=current_user.username,
            intro=request.form.get('intro'),
            reason=request.form.get('reason')
        ))
        
        owner = User.query.filter_by(username=task.user).first()
        if owner:
            db.session.add(Notification(
                user_id=owner.id,
                task_id=task.id,
                message=f"New Applicant: @{current_user.username} applied for your task: {task.title}!"
            ))
            socketio.emit('new_unread', {'task_id': task.id, 'role': 'created'}, room=str(owner.id))
            
        db.session.commit()
        flash("Application submitted successfully!")
        return redirect(url_for('marketplace'))
        
    return render_template('apply.html', task=task)


@app.route('/my_task')
def my_task():
    cleanup_expired_tasks()
    if 'user_id' not in session:
        return redirect(url_for('login'))
    current_user = User.query.get(session['user_id'])
    if not current_user:
        session.clear()
        return redirect(url_for('login'))

    view = request.args.get('view', 'created')
    
    # Fetch all tasks related to the user
    all_created_tasks = Task.query.filter_by(user=current_user.username).order_by(Task.is_pinned.desc(), Task.id.desc()).all()
    # For your applications, we sort them after assembly using Python's list sort mechanism
    my_all_applications = Application.query.filter_by(applicant_username=current_user.username).all()

    # Containers for Active vs Completed Archive lists
    active_created = []
    completed_created = []
    
    active_applied = []
    completed_applied = []

    # 1. Sort Created Tasks based on mutual rating completion states
    for task in all_created_tasks:
        is_fully_rated = False
        if task.progress == 100:
            hired_apps = Application.query.filter_by(task_id=task.id, status='Hired').all()
            # Check if employer rated all workers
            employer_reviews = [r.target_username for r in Rating.query.filter_by(task_id=task.id, reviewer_username=current_user.username).all()]
            employer_done = all(app.applicant_username in employer_reviews for app in hired_apps) if hired_apps else False
            
            # Check if all workers rated the employer
            workers_done = True
            for app in hired_apps:
                worker_rated = Rating.query.filter_by(task_id=task.id, reviewer_username=app.applicant_username, target_username=current_user.username).first()
                if not worker_rated:
                    workers_done = False
                    break
            
            if employer_done and workers_done:
                is_fully_rated = True

        if is_fully_rated:
            completed_created.append(task)
        else:
            active_created.append(task)

    # 2. Extract unrated target helper variables for the active created views
    first_unrated = {}
    for task in active_created:
        if task.progress == 100:
            hired_apps = Application.query.filter_by(task_id=task.id, status='Hired').all()
            rated_list = [r.target_username for r in Rating.query.filter_by(task_id=task.id, reviewer_username=current_user.username).all()]
            for app in hired_apps:
                if app.applicant_username not in rated_list:
                    first_unrated[task.id] = app.applicant_username
                    break

    # 3. Sort Applied Tasks based on mutual rating completion states
    for app in my_all_applications:
        task = Task.query.get(app.task_id)
        if task:
            is_fully_rated = False
            if task.progress == 100 and app.status == 'Hired':
                # Check if this worker rated the employer
                worker_rated_owner = Rating.query.filter_by(task_id=task.id, reviewer_username=current_user.username, target_username=task.user).first()
                # Check if the employer rated this specific worker
                owner_rated_worker = Rating.query.filter_by(task_id=task.id, reviewer_username=task.user, target_username=current_user.username).first()
                
                if worker_rated_owner and owner_rated_worker:
                    is_fully_rated = True
            
            if is_fully_rated:
                completed_applied.append({'app': app, 'task': task})
            else:
                active_applied.append({'app': app, 'task': task})

    active_applied.sort(key=lambda x: x['task'].is_pinned, reverse=True)

    return render_template('my_task.html',
        created=active_created, 
        applied=active_applied,
        completed_created=completed_created,
        completed_applied=completed_applied,
        view=view, user=current_user,
        Task=Task, Rating=Rating, first_unrated=first_unrated)


@app.route('/hire-applicant/<int:app_id>')
def hire_applicant(app_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    application = Application.query.get_or_404(app_id)
    task = Task.query.get(application.task_id)

    # 🔒 Teammate's Security Checks
    user = User.query.get(session['user_id'])
    if not task or task.user != user.username:
        flash("You are not authorized to hire for this task.")
        return redirect(url_for('my_task'))
        
    if application.status == 'Hired':
        flash(f"{application.applicant_username} is already hired!")
        return redirect(url_for('view_applicants', task_id=task.id))

    # 👥 Hiring & Capacity Logic
    if task.get_hired_count() < task.capacity:
        application.status = 'Hired'
        
        # Force commit right here so get_hired_count() updates accurately on disk
        db.session.commit() 
        
        if task.capacity == 1:
            task.tasker = application.applicant_username
            task.status = 'In Progress'
        else:
            # Checked after disk sync to handle multiple slots correctly
            if task.get_hired_count() >= task.capacity:
                task.status = 'In Progress'
                if not task.tasker:
                    task.tasker = application.applicant_username

        # 🔔 Notifications Setup
        applicant_user = User.query.filter_by(username=application.applicant_username).first()
        if applicant_user:
            db.session.add(Notification(
                user_id=applicant_user.id,
                task_id=task.id,
                message=f"You have been HIRED for the task: {task.title}!"
            ))
        
        if task.get_hired_count() >= task.capacity:
            # 1. Find all other pending applications for this task
            excess_applications = Application.query.filter_by(task_id=task.id, status='Pending').all()
            
            for excess_app in excess_applications:
                # 2. Change their status to Rejected
                excess_app.status = 'Rejected'
                
                # 3. Send a system notification to each rejected applicant
                excess_user = User.query.filter_by(username=excess_app.applicant_username).first()
                if excess_user:
                    db.session.add(Notification(
                        user_id=excess_user.id,
                        task_id=task.id,
                        message=f"The task '{task.title}' has reached full capacity, and your application was automatically released."
                    ))
                    
                    # 4. Optional: Send a live socket alert so their browser updates instantly
                    socketio.emit('new_unread', {'task_id': task.id, 'role': 'applied'}, room=str(excess_user.id))

        # --- Existing Commit & Flash ---
        db.session.commit()
        flash(f"You have hired {application.applicant_username}!")
    else:
        flash("Task is already at full capacity!")

    return redirect(url_for('my_task', view='created'))


@app.route('/reject_applicant/<int:app_id>')
def reject_applicant(app_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    application = Application.query.get_or_404(app_id)
    task = Task.query.get(application.task_id)
    user = User.query.get(session['user_id'])
    if not task or task.user != user.username:
        flash("You are not authorized to reject applicants for this task.")
        return redirect(url_for('my_task'))
    application.status = 'Rejected'
    db.session.commit()
    flash("Applicant has been rejected.")
    return redirect(url_for('view_applicants', task_id=application.task_id))


@app.route('/view_applicants/<int:task_id>')
def view_applicants(task_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    user = db.session.get(User, session['user_id'])
    task = Task.query.get_or_404(task_id)
    
    # Security Check: Only the task owner is allowed to review candidates!
    if task.user != user.username:
        flash("You are not authorized to view applicants for this task.")
        return redirect(url_for('my_task'))
        
    # Fetch all applications filed for this specific task listing campaign
    apps = Application.query.filter_by(task_id=task.id).all()
    
    return render_template('view_applicants.html', task=task, apps=apps, user=user)


@app.route('/withdraw_application/<int:app_id>')
def withdraw_application(app_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    user = db.session.get(User, session['user_id'])
    application = Application.query.get_or_404(app_id)
    
    # Security check: Make sure this application actually belongs to the logged-in user
    if application.applicant_username != user.username:
        flash("Unauthorized action!")
        return redirect(url_for('my_task', view='applied'))
        
    # Security check: They can only cancel if it hasn't been processed yet
    if application.status != 'Pending':
        flash("Cannot withdraw an application that has already been hired or rejected!")
        return redirect(url_for('my_task', view='applied'))
        
    # Run the database removal sweep
    db.session.delete(application)
    db.session.commit()
    
    flash("Your application has been successfully withdrawn.")
    return redirect(url_for('my_task', view='applied'))

@app.route('/chat/<int:task_id>')
def chat(task_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    task = Task.query.get_or_404(task_id)
    user = User.query.get(session['user_id'])
    if not user_can_access_task_chat(task, user):
        flash("You are not part of this task chat.")
        return redirect(url_for('my_task'))
    for msg in Message.query.filter_by(task_id=task_id, is_read=False).filter(Message.sender != user.username).all():
        msg.is_read = True
        if not MessageRead.query.filter_by(message_id=msg.id, username=user.username).first():
            db.session.add(MessageRead(message_id=msg.id, username=user.username))
    db.session.commit()
    socketio.emit('clear_unread', {'task_id': task_id}, room=str(session['user_id']))
    history = Message.query.filter_by(task_id=task_id).order_by(Message.timestamp.asc()).all()
    return render_template('chat.html', task=task, user=user, history=history)


@app.route('/group_chat/<int:task_id>')
def group_chat(task_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    task = Task.query.get_or_404(task_id)
    user = User.query.get(session['user_id'])
    if not user_can_access_task_chat(task, user):
        flash("You are not part of this task chat.")
        return redirect(url_for('my_task'))
    for msg in Message.query.filter_by(task_id=task_id, is_read=False).filter(Message.sender != user.username).all():
        if not MessageRead.query.filter_by(message_id=msg.id, username=user.username).first():
            db.session.add(MessageRead(message_id=msg.id, username=user.username))
    db.session.commit()
    socketio.emit('clear_unread', {'task_id': task_id}, room=str(session['user_id']))
    history = Message.query.filter_by(task_id=task_id).order_by(Message.timestamp.asc()).all()
    return render_template('chat.html', task=task, user=user, history=history)


@app.route('/rate_user/<int:task_id>/<target_user>')
def rate_user(task_id, target_user):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    current_user = db.session.get(User, session['user_id'])
    task = Task.query.get_or_404(task_id)
    t_name = target_user.strip()
    c_name = current_user.username.strip()
    if c_name == t_name:
        flash("You cannot rate yourself!")
        return redirect(url_for('my_task'))
    if not user_can_rate_target(task, c_name, t_name):
        flash("You can only rate people you worked with on this task.")
        return redirect(url_for('my_task'))
    if Rating.query.filter_by(task_id=task_id, reviewer_username=c_name, target_username=t_name).first():
        flash(f"You already rated {t_name}!")
        return redirect(url_for('my_task'))
    role = 'tasker' if c_name == task.user else 'client'
    next_target = None
    if role == 'tasker':
        hired_apps = Application.query.filter_by(task_id=task_id, status='Hired').all()
        rated_list = [r.target_username for r in Rating.query.filter_by(
            task_id=task_id, reviewer_username=c_name).all()]
        for app in hired_apps:
            if app.applicant_username != t_name and app.applicant_username not in rated_list:
                next_target = app.applicant_username
                break
    return render_template('rate_user.html', task=task, task_id=task_id,
                           target_user=t_name, role=role, next_target=next_target)


@app.route('/submit_rating/<int:task_id>/<target_user>', methods=['POST'])
def submit_rating(task_id, target_user):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    current_user = db.session.get(User, session['user_id'])
    task = Task.query.get_or_404(task_id)
    t_name = target_user.strip()
    c_name = current_user.username.strip()
    if c_name == t_name:
        flash("You cannot rate yourself!")
        return redirect(url_for('my_task'))
    if not user_can_rate_target(task, c_name, t_name):
        flash("You can only rate people you worked with on this task.")
        return redirect(url_for('my_task'))
    if Rating.query.filter_by(task_id=task_id, reviewer_username=c_name, target_username=t_name).first():
        flash(f"You already rated {t_name}!")
        return redirect(url_for('my_task'))
    rating_val = int(request.form.get('rating', 5))
    db.session.add(Rating(
        task_id=task_id,
        reviewer_username=c_name,
        target_username=t_name,
        score=rating_val,
        review_content=request.form.get('review', ''),
        timestamp=datetime.now(my8)
    ))
    user_to_rate = User.query.filter_by(username=t_name).first()
    if user_to_rate:
        user_to_rate.total_rating += rating_val
        user_to_rate.review_count += 1
    db.session.commit()
    flash("Rating submitted successfully!")

    if c_name == task.user:
        rated_targets = {
            r.target_username for r in Rating.query.filter_by(
                task_id=task_id, reviewer_username=c_name
            ).all()
        }
        for hired_username in task.get_hired_usernames():
            if hired_username not in rated_targets:
                return redirect(url_for('rate_user', task_id=task_id, target_user=hired_username))

    return redirect(url_for('my_task'))


@app.route('/view_ratings')
def view_ratings():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = db.session.get(User, session['user_id'])
    real_reviews = Rating.query.filter_by(
        target_username=user.username
    ).order_by(Rating.timestamp.desc()).all()
    avg_rating = round(user.total_rating / user.review_count, 1) if user.review_count > 0 else 5.0
    return render_template('view_ratings.html', user=user, reviews=real_reviews, avg_rating=avg_rating)

@app.route('/completed_tasks')
def completed_tasks():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    user = db.session.get(User, session['user_id'])
    
    hired_apps = Application.query.filter_by(
        applicant_username=user.username, status='Hired'
    ).all()
    hired_task_ids = [app_record.task_id for app_record in hired_apps]
    done_tasks = Task.query.filter(
        Task.id.in_(hired_task_ids),
        Task.status == 'Completed'
    ).all()
    
    for task in done_tasks:
        # 去 Earning 表里找这个任务对应的进账记录
        earning_record = Earning.query.filter_by(
            user_id=user.id,
            activity=f"Completed Task: {task.title}"
        ).first()
        
        if earning_record:
            # 格式化好时间
            task.completed_time = earning_record.timestamp.strftime('%Y-%m-%d %H:%M')
        else:
            task.completed_time = "Recently"
        hired_usernames = task.get_hired_usernames()
        task.finish_with_usernames = [
            username for username in hired_usernames
            if username != user.username
        ] if len(hired_usernames) > 1 else []

    return render_template('completed_tasks.html', user=user, tasks=done_tasks)


# =========================
# SOCKET IO
# =========================
@socketio.on('join')
def on_join(data):
    room_id = str(data.get('room', ''))
    user = db.session.get(User, session.get('user_id'))
    
    if not user or not room_id:
        return

    # 💬 Handle real-time Private Messaging Room joins
    if room_id.startswith("private_"):
        # Security: Split room names to ensure exact username match (prevents username spoofing)
        room_parts = room_id.replace("private_", "").split("_")
        if user.username in room_parts:
            join_room(room_id)
            print(f"🔒 User {user.username} successfully entered private secure room: {room_id}")
        return

    # 👥 Handle Task Group Chat Room joins
    try:
        task = db.session.get(Task, int(room_id))
        if task and user_can_access_task_chat(task, user):
            join_room(room_id)
            print(f"👥 User {user.username} entered task group room: {room_id}")
    except (ValueError, TypeError):
        # Prevents crash if room_id is not a valid integer ID
        pass


@socketio.on('send_message')
def handle_combined_message(data):
    room = str(data.get('room', ''))
    msg_content = data.get('message') or data.get('content')
    current_user = db.session.get(User, session.get('user_id'))

    if not room or not msg_content or not current_user:
        return

    # 🌟 通道 A：1对1 私信发送与实时广播
    if "private_" in room:
        room_parts = room.replace("private_", "").split("_")
        if len(room_parts) < 2:
            return
        receiver_username = room_parts[1] if room_parts[0] == current_user.username else room_parts[0]

        # 存入私信表 DirectMessage
        new_dm = DirectMessage(
            sender_username=current_user.username,
            receiver_username=receiver_username,
            content=msg_content
        )
        db.session.add(new_dm)
        db.session.commit()

        # 双通道并发广播，保证前端 100% 能够抓取到刷新信号
        emit('receive_message', {
            'room': room,
            'username': current_user.username,
            'sender': current_user.username,
            'message': msg_content
        }, room=room)
        
        emit('receive_private_message', {
            'room': room,
            'sender': current_user.username,
            'message': msg_content
        }, room=room)
        return

    # 🌟 通道 B：常规群聊
    task = db.session.get(Task, int(room))
    if not task or not user_can_access_task_chat(task, current_user):
        return

    reply_id = data.get('reply_to_id')
    if not reply_id or reply_id == "null" or reply_id == "":
        reply_id = None
    else:
        try:
            reply_id = int(reply_id)
        except (ValueError, TypeError):
            reply_id = None

    message = Message(
        task_id=int(room),
        sender=current_user.username,
        content=msg_content,
        reply_to_id=reply_id
    )
    db.session.add(message)
    db.session.commit()

    emit('receive_message', {
        'room': room,
        'username': current_user.username,
        'message': message.content,
        'reply_to_id': message.reply_to_id
    }, room=room)

    for username in get_task_member_usernames(task):
        if username != current_user.username:
            member = User.query.filter_by(username=username).first()
            if member:
                role = 'created' if username == task.user else 'applied'
                socketio.emit('new_unread', {'task_id': int(room), 'role': role}, room=str(member.id))


@socketio.on('edit_message')
def handle_edit(data):
    current_user = db.session.get(User, session.get('user_id'))
    msg_id = data.get('message_id')
    new_content = data.get('new_content')
    room_id = str(data.get('room', ''))

    if not current_user or not msg_id or not new_content:
        return

    # 💡 强力修复：强制转换为整型以对齐数据库主键类型，清除类型判断误差
    try:
        msg_id = int(msg_id)
    except (ValueError, TypeError):
        return

    # 🌟 通道 A：如果房间名带有 private_，去私信表修改
    if "private_" in room_id:
        dm_msg = db.session.get(DirectMessage, msg_id)
        if dm_msg and dm_msg.sender_username == current_user.username:
            dm_msg.content = new_content
            db.session.commit()
            emit('message_edited', {'message_id': msg_id, 'new_content': new_content}, room=room_id)
            emit('private_message_edited', {'message_id': msg_id, 'new_content': new_content}, room=room_id)
        return

    # 🌟 通道 B：任务大群聊修改
    msg = db.session.get(Message, msg_id)
    if msg and msg.sender == current_user.username:
        msg.content = new_content
        msg.is_edited = True
        db.session.commit()
        emit('message_edited', {'message_id': msg.id, 'new_content': msg.content}, room=room_id)


@socketio.on('delete_message')
def handle_delete(data):
    current_user = db.session.get(User, session.get('user_id'))
    msg_id = data.get('message_id')
    room_id = str(data.get('room', ''))

    if not current_user or not msg_id:
        return

    try:
        msg_id = int(msg_id)
    except (ValueError, TypeError):
        return

    # 🌟 通道 A：如果房间名带有 private_，去私信表抹除
    if "private_" in room_id:
        dm_msg = db.session.get(DirectMessage, msg_id)
        if dm_msg and dm_msg.sender_username == current_user.username:
            db.session.delete(dm_msg)
            db.session.commit()
            emit('message_deleted', {'message_id': msg_id}, room=room_id)
            emit('private_message_deleted', {'message_id': msg_id}, room=room_id)
        return

    # 🌟 通道 B：群聊表软删除
    msg = db.session.get(Message, msg_id)
    if msg and msg.sender == current_user.username:
        msg.is_deleted = True
        db.session.commit()
        emit('message_deleted', {'message_id': msg.id}, room=room_id)


@socketio.on('connect')
def handle_connect():
    if 'user_id' in session:
        join_room(str(session['user_id']))
        print(f"User {session['user_id']} connected to their private room.")


# =========================
# HTTP ROUTES & APPS
# =========================


@app.route('/private_inbox')
def private_inbox():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    current_user = User.query.get(session['user_id'])
    
    sent_msgs = DirectMessage.query.filter_by(sender_username=current_user.username).all()
    rcvd_msgs = DirectMessage.query.filter_by(receiver_username=current_user.username).all()
    
    chat_partners = set()
    for msg in sent_msgs:
        chat_partners.add(msg.receiver_username)
    for msg in rcvd_msgs:
        chat_partners.add(msg.sender_username)
        
    inbox_data = []
    for partner_username in chat_partners:
        # 💡 查询这个人发给我、且我还没读的真实消息条数
        unread_count = DirectMessage.query.filter_by(
            sender_username=partner_username,
            receiver_username=current_user.username,
            is_read=False
        ).count()
        
        inbox_data.append({
            'username': partner_username,
            'unread_count': unread_count  # 💡 传给前端具体数字
        })
        
    # 用于顶部导航栏判断是否有未读
    total_unread = DirectMessage.query.filter_by(
        receiver_username=current_user.username,
        is_read=False
    ).count()
        
    return render_template('private_inbox.html', inbox_data=inbox_data, user=current_user, total_unread=total_unread)


@app.route('/private_chat/<username>', methods=['GET', 'POST'])
def private_chat(username):
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    current_user = User.query.get(session['user_id'])
    target_user = User.query.filter_by(username=username).first_or_404()
    
    usernames = sorted([current_user.username, target_user.username])
    room_name = f"private_{usernames[0]}_{usernames[1]}"
    
    # 进入聊天室，洗成已读
    unread_msgs = DirectMessage.query.filter_by(
        sender_username=target_user.username,
        receiver_username=current_user.username,
        is_read=False
    ).all()
    if unread_msgs:
        for msg in unread_msgs:
            msg.is_read = True
        db.session.commit()
    
    if request.method == 'POST':
        msg_content = request.form.get('content')
        if msg_content:
            new_dm = DirectMessage(
                sender_username=current_user.username,
                receiver_username=target_user.username,
                content=msg_content,
                is_read=False
            )
            db.session.add(new_dm)
            db.session.commit()
            
            socketio.emit('receive_private_message', {
                'room': room_name,
                'sender': current_user.username,
                'message': msg_content
            }, room=room_name)

            # 💡 【核心修复点】：直接用全局 socketio.emit 发射全站实时未读通知通知！
            socketio.emit('new_private_notification', {
                'sender': current_user.username,
                'receiver': target_user.username
            })
            
            # 2. 🚀 ✅ ADDED: Reach them globally across other app hooks to trigger real-time toasts
            socketio.emit('receive_private_message', {
                'sender': current_user.username,
                'message': msg_content
            }, room=str(target_user.id))
            
        return redirect(url_for('private_chat', username=username))
        
    history = DirectMessage.query.filter(
        ((DirectMessage.sender_username == current_user.username) & (DirectMessage.receiver_username == target_user.username)) |
        ((DirectMessage.sender_username == target_user.username) & (DirectMessage.receiver_username == current_user.username))
    ).order_by(DirectMessage.timestamp.asc()).all()
    
    return render_template('private_chat.html', target_user=target_user, user=current_user, history=history)
# 💡 核心：全局未读数注入锁。有了它，Marketplace、Dashboard、Profile 都能完美显示红点
@app.context_processor
def inject_global_private_unread_count():
    if 'user_id' in session:
        # 这里用 try-except 防止在还没跑完 DB 迁移或者未登录时挂掉
        try:
            current_user = User.query.get(session['user_id'])
            if current_user:
                # 统计所有发给当前用户的、还没读的私聊消息总数
                count = DirectMessage.query.filter_by(
                    receiver_username=current_user.username, 
                    is_read=False
                ).count()
                return dict(total_unread=count)
        except Exception:
            pass
    return dict(total_unread=0)

# app.py 里的 Socket 监听区域追加：

@socketio.on('new_private_notification')
def handle_private_notification(data):
    # 💡 收到前端发来的私聊通知信号后，立刻将其以全站广播形式砸向所有页面
    socketio.emit('new_private_notification', {
        'sender': data.get('sender'),
        'receiver': data.get('receiver')
    })


if __name__ == '__main__':
    with app.app_context():
        # Only run the SQLite patch engine if we are NOT using PostgreSQL/Neon
        if 'postgresql' not in app.config['SQLALCHEMY_DATABASE_URI']:
            try:
                patch_database()
            except Exception as e:
                print(f"⚠️ Skipping SQLite patch due to architecture variant: {e}")
        else:
            print("☁️ Neon Cloud PostgreSQL detected. Skipping legacy SQLite local patches.")
            
        # Rebuild all database object mappings safely in the cloud
        db.create_all()   
        print("!!! Database connection initialized cleanly !!!")
        
    socketio.run(app, host='0.0.0.0', port=8000, debug=True)