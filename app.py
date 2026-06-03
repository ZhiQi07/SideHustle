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

app = Flask(__name__)
app.secret_key = "mmu_secret_key"
socketio = SocketIO(app, cors_allowed_origins="*")

basedir = os.path.abspath(os.path.dirname(__file__))
db_path = os.path.join(basedir, 'database.db')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + db_path
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

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


class MessageRead(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    message_id = db.Column(db.Integer, db.ForeignKey('message.id'), nullable=False)
    username = db.Column(db.String(50), nullable=False)

with app.app_context():
    db.create_all()


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
    query = request.args.get('q')
    category = request.args.get('cat')
    tasks_filter = Task.query.filter_by(status='Available')
    if query:
        tasks_filter = tasks_filter.filter(
            (Task.title.contains(query)) | (Task.description.contains(query))
        )
    if category:
        tasks_filter = tasks_filter.filter(Task.category == category)
    all_tasks = tasks_filter.all()
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
        
        # --- NEW PRICE SAFE LOCK CHECK ---
        # Only update the price if NO helper matches active hired tracking values
        if task.get_hired_count() == 0:
            task.price = float(request.form.get('price', task.price))
        else:
            # If someone tries to hack the disabled HTML input, force keep the database price
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


@app.route('/apply/<int:task_id>', methods=['GET', 'POST'])
def apply(task_id):
    if 'user_id' not in session:
        flash("Please login to apply!")
        return redirect(url_for('login'))
    task = Task.query.get_or_404(task_id)
    current_user = User.query.get(session['user_id'])
    if request.method == 'POST':
        if task.user == current_user.username:
            flash("You cannot apply for a task you created!")
            return redirect(url_for('marketplace'))
        if Application.query.filter_by(task_id=task.id, applicant_username=current_user.username).first():
            flash("You have already applied for this task!")
            return redirect(url_for('marketplace'))
        db.session.add(Application(
            task_id=task.id,
            applicant_username=current_user.username,
            intro=request.form.get('intro'),
            reason=request.form.get('reason')
        ))
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
    created_tasks = Task.query.filter_by(user=current_user.username).all()

    first_unrated = {}
    for task in created_tasks:
        if task.progress == 100:
            hired_apps = Application.query.filter_by(task_id=task.id, status='Hired').all()
            rated_list = [r.target_username for r in Rating.query.filter_by(
                task_id=task.id, reviewer_username=current_user.username).all()]
            for app in hired_apps:
                if app.applicant_username not in rated_list:
                    first_unrated[task.id] = app.applicant_username
                    break

    my_applications = Application.query.filter_by(applicant_username=current_user.username).all()
    applied_tasks = []
    for app in my_applications:
        task = Task.query.get(app.task_id)
        print(f"DEBUG: app status={app.status}, task={task.title if task else 'NONE'}, task_id={app.task_id}")

        applied_tasks.append({'app': app, 'task': task})

    print(f"DEBUG FINAL: view={view}, applied_tasks count={len(applied_tasks)}")

    return render_template('my_task.html',
        created=created_tasks, applied=applied_tasks,
        view=view, user=current_user,
        Task=Task, Rating=Rating, first_unrated=first_unrated)


@app.route('/view_applicants/<int:task_id>')
def view_applicants(task_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    task = Task.query.get_or_404(task_id)
    user = User.query.get(session['user_id'])
    if task.user != user.username:
        flash("You are not authorized to view these applicants.")
        return redirect(url_for('my_task'))
    apps = Application.query.filter_by(task_id=task_id).all()
    return render_template('view_applicants.html', task=task, apps=apps, user=user)


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
    room_id = str(data['room'])
    user = db.session.get(User, session.get('user_id'))
    
    if not user:
        return

    # 💬 NEW: Handle real-time Private Messaging Room joins
    if room_id.startswith("private_"):
        # Security: Only let the user join if their username is part of the room string title
        if user.username in room_id:
            join_room(room_id)
            print(f"🔒 User {user.username} successfully entered private secure room: {room_id}")
            
    # 👥 Handle your teammate's existing Task Group Chat Room joins
    else:
        task = db.session.get(Task, int(room_id))
        if task and user_can_access_task_chat(task, user):
            join_room(room_id)
            print(f"👥 User {user.username} entered task group room: {room_id}")


@socketio.on('send_message')
def handle_message(data):
    room = data['room']
    task = db.session.get(Task, int(room))
    current_user = db.session.get(User, session.get('user_id'))
    if not task or not user_can_access_task_chat(task, current_user):
        return

    message = Message(
        task_id=int(room),
        sender=current_user.username,
        content=data['message'],
        reply_to_id=data.get('reply_to_id')
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
    # 1. 统一用 user_id 从数据库获取当前登录的完整用户对象
    current_user = db.session.get(User, session.get('user_id'))
    msg = db.session.get(Message, data.get('message_id'))
    
    # 2. 修复核心：用 current_user.username 代替 session.get('user_username')
    if msg and current_user and msg.sender == current_user.username:
        msg.content = data.get('new_content')
        msg.is_edited = True
        db.session.commit()
        
        # 3. 广播给房间所有人
        room_id = str(msg.task_id)
        emit('message_edited', {
            'message_id': msg.id, 
            'new_content': msg.content
        }, room=room_id)
    else:
        print("DEBUG: Edit failed. Check if user matches sender.")

@socketio.on('delete_message')
def handle_delete(data):
    current_user = User.query.get(session.get('user_id'))
    msg = db.session.get(Message, data.get('message_id'))
    if msg and current_user and msg.sender == current_user.username:
        msg.is_deleted = True
        db.session.commit()
        emit('message_deleted', {'message_id': msg.id}, room=str(msg.task_id))


@socketio.on('connect')
def handle_connect():
    if 'user_id' in session:
        join_room(str(session['user_id']))
        print(f"User {session['user_id']} connected to their private room.")


@app.route('/private_inbox')
def private_inbox():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    current_user = User.query.get(session['user_id'])
    
    # Fetch all unique users that the current user has exchanged private messages with
    sent_msgs = DirectMessage.query.filter_by(sender_username=current_user.username).all()
    rcvd_msgs = DirectMessage.query.filter_by(receiver_username=current_user.username).all()
    
    chat_partners = set()
    for msg in sent_msgs:
        chat_partners.add(msg.receiver_username)
    for msg in rcvd_msgs:
        chat_partners.add(msg.sender_username)
        
    return render_template('private_inbox.html', chat_partners=list(chat_partners), user=current_user)


@app.route('/private_chat/<username>', methods=['GET', 'POST'])
def private_chat(username):
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    current_user = User.query.get(session['user_id'])
    target_user = User.query.filter_by(username=username).first_or_404()
    
    if request.method == 'POST':
        msg_content = request.form.get('content')
        if msg_content:
            new_dm = DirectMessage(
                sender_username=current_user.username,
                receiver_username=target_user.username,
                content=msg_content
            )
            db.session.add(new_dm)
            db.session.commit()
            
            # Emit socket event for real-time updates (matches your teammate's setup)
            socketio.emit('receive_private_message', {
                'sender': current_user.username,
                'message': msg_content
            }, room=f"private_{min(current_user.username, target_user.username)}_{max(current_user.username, target_user.username)}")
            
        return redirect(url_for('private_chat', username=username))
        
    # Fetch conversation history between these two specific users
    history = DirectMessage.query.filter(
        ((DirectMessage.sender_username == current_user.username) & (DirectMessage.receiver_username == target_user.username)) |
        ((DirectMessage.sender_username == target_user.username) & (DirectMessage.receiver_username == current_user.username))
    ).order_by(DirectMessage.timestamp.asc()).all()
    
    return render_template('private_chat.html', target_user=target_user, user=current_user, history=history)

@app.context_processor
def inject_notifications():
    if 'user_id' in session:
        # 1. Try to find the user in the database
        current_user = User.query.get(session['user_id'])
        
        # 2. Check if the user ACTUALLY exists (is not None)
        if current_user:
            user_notifications = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.id.desc()).limit(5).all()
            return dict(notifications=user_notifications)
        else:
            # 3. If the user doesn't exist (DB deleted), clear the ghost session
            session.pop('user_id', None)
            
    return dict(notifications=[])

if __name__ == '__main__':
    with app.app_context():
        patch_database()  # Runs your columns update checks
        db.create_all()   # Builds any completely brand-new tables from scratch
        print("!!! Database has been patched and initialized with new columns !!!")
        
    socketio.run(app, debug=True, port=8000)
