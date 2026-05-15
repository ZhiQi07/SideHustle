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

# =========================
# DATABASE CONFIG
# =========================
basedir = os.path.abspath(os.path.dirname(__file__))
db_path = os.path.join(basedir, 'database.db')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + db_path
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# =========================
# MODELS
# =========================
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    # --- Friend's Security Features ---
    email = db.Column(db.String(150), unique=True, nullable=False)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    security_question = db.Column(db.String(200), nullable=False)
    security_answer = db.Column(db.String(200), nullable=False)
    
    # --- Shared & Your Features ---
    skills = db.Column(db.Text, default="No skills listed")
    is_admin = db.Column(db.Boolean, default=False)
    credit = db.Column(db.Float, default=0.0)
    total_rating = db.Column(db.Float, default=5.0)
    review_count = db.Column(db.Integer, default=1)
    tasks_completed = db.Column(db.Integer, default=0)


    # --- Your Notification Function ---
    def count_total_unread(self, role='all'):
        if role == 'created':
            tasks = Task.query.filter_by(user=self.username).all()
        elif role == 'applied':
            tasks = Task.query.filter_by(tasker=self.username).all()
        else:
            tasks = Task.query.filter((Task.user == self.username) | (Task.tasker == self.username)).all()
        
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

    progress = db.Column(db.Integer, default=0) # Stores 0, 25, 50, 75, or 100
    urgent = db.Column(db.Boolean, default=False)

    def get_unread_count(self, current_username):
        return Message.query.filter_by(
            task_id=self.id, 
            is_read=False
        ).filter(Message.sender != current_username).count()

    def get_applicant_count(self):
            return Application.query.filter_by(task_id=self.id).count()
    
    def get_unread_count(self, current_username):
            messages = Message.query.filter_by(task_id=self.id).filter(Message.sender != current_username).all()
            count = 0
            for msg in messages:
                already_read = MessageRead.query.filter_by(message_id=msg.id, username=current_username).first()
                if not already_read:
                    count += 1
            return count
        
    def get_hired_count(self):
        return Application.query.filter_by(task_id=self.id, status='Hired').count()


class Application(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('task.id'), nullable=False)
    applicant_username = db.Column(db.String(50), nullable=False)
    intro = db.Column(db.Text)
    reason = db.Column(db.Text)
    status = db.Column(db.String(20), default='Pending')

    def get_applicant_count(self):
        return Application.query.filter_by(task_id=self.id).count()
    


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
    
    # 建立引用关系，方便获取被回复的消息内容
    replied_message = db.relationship('Message', remote_side=[id], backref='replies')


class Earning(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    activity = db.Column(db.String(150), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    timestamp = db.Column(db.DateTime, default=db.func.now())


class Rating(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('task.id'), nullable=False)
    reviewer_username = db.Column(db.String(50), nullable=False)
    target_username = db.Column(db.String(50), nullable=False)
    score = db.Column(db.Integer, nullable=False)
    review_content = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=db.func.now())


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


# =========================
# INIT DB
# =========================
with app.app_context():
    db.create_all()


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
                SELECT COUNT(*) FROM message 
                WHERE is_read = 0 
                AND sender != :uname
                AND task_id IN (
                    SELECT id FROM task 
                    WHERE user = :uname OR tasker = :uname
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
            user_notifications = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.id.desc()).limit(5).all()
            return dict(notifications=user_notifications)
        else:
            session.pop('user_id', None)
    return dict(notifications=[])


# =========================
# ROUTES
# =========================
with app.app_context():
    db.create_all()

def cleanup_expired_tasks():
    # 1. Get today's date in YYYY-MM-DD format to match the database
    today = datetime.now().strftime('%Y-%m-%d')
    
    # 2. Find Available tasks that are past their deadline
    expired_tasks = Task.query.filter(
        Task.deadline != "", 
        Task.deadline < today, 
        Task.status == 'Available'
    ).all()
    
    for task in expired_tasks:
        # 3. Only proceed if 0 people have applied
        if task.get_applicant_count() == 0:
            # 4. Notify the creator before deleting
            owner = User.query.filter_by(username=task.user).first()
            if owner:
                expired_note = Notification(
                    user_id=owner.id,
                    message=f"System: Your task '{task.title}' has expired and was removed due to 0 applicants.",
                    status='unread'
                )
                db.session.add(expired_note)
            
            # 5. Remove the task from the marketplace
            db.session.delete(task)
            
    db.session.commit()
        
# --- Add this first so the main URL works ---
@app.route('/')
def index():
    return redirect(url_for('login'))

def home():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Grab email and password directly
        email = request.form.get('email', '').lower()
        password = request.form.get('password')

        # Security check
        if not email.endswith('@student.mmu.edu.my'):
            flash("Only MMU student emails are allowed to log in!")
            return redirect(url_for('login'))

        # Search by email
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
    cleanup_expired_tasks()

    query = request.args.get('q')
    category = request.args.get('cat')

    tasks_filter = Task.query.filter_by(status='Available')

    if query:
        tasks_filter = tasks_filter.filter((Task.title.contains(query)) | (Task.description.contains(query)))
    
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
    
    # 1. 获取我被雇佣（Applied & Hired）的所有任务 ID
    hired_apps = Application.query.filter_by(
        applicant_username=user.username, 
        status='Hired'
    ).all()
    hired_task_ids = [app.task_id for app in hired_apps]

    # --- 核心修复：只查我被雇佣的任务，不包含我发布的任务 ---
    # 这样 Task Tracking 就只会显示你正在为别人做的任务了
    tracking_list = Task.query.filter(
        Task.id.in_(hired_task_ids)
    ).all()
    # -----------------------------------------------

    # 2. 计算平均分 (保留你原有的逻辑)
    avg_rating = round(user.total_rating / user.review_count, 1) if user.review_count > 0 else 5.0
    
    return render_template(
        'dashboard.html',
        username=user.username,
        total_credit=user.credit,
        average_rating=avg_rating,
        tasks_done=user.tasks_completed,
        tracking_list=tracking_list  # 现在这个 list 只包含你申请的任务
    )


@app.route('/update_progress/<int:task_id>', methods=['POST'])
def update_progress(task_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    new_progress = int(request.form.get('progress', 0))
    task = db.session.get(Task, task_id)
    
    # 当进度达到 100% 且任务还没结算过时
    if new_progress == 100 and task.status != 'Completed':
        task.status = 'Completed'
        
        # --- 核心修复逻辑：给所有被雇佣的人结算 ---
        # 1. 找到所有该任务下状态为 'Hired' 的申请
        hired_applications = Application.query.filter_by(task_id=task.id, status='Hired').all()
        
        for app_record in hired_applications:
            # 2. 根据用户名找到对应的 User 对象
            worker = User.query.filter_by(username=app_record.applicant_username).first()
            
            if worker:
                # 3. 更新每个人的 Credit 和 Tasks Completed
                if worker.tasks_completed is None:
                    worker.tasks_completed = 0
                worker.tasks_completed += 1
                
                if hasattr(task, 'price') and task.price:
                    if worker.credit is None:
                        worker.credit = 0.0
                    worker.credit += task.price
                    
                    # 4. 为每个人生成一条收入记录
                    new_earning = Earning(
                        user_id=worker.id,
                        activity=f"Completed Task: {task.title}",
                        amount=task.price,
                        timestamp=datetime.now()
                    )
                    db.session.add(new_earning)
                
                print(f"SUCCESS: 为成员 {worker.username} 结算成功！")
        # ---------------------------------------

    task.progress = new_progress
    db.session.commit()
    
    return redirect(url_for('my_task', view='applied'))


@app.route('/earnings')
def earnings():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = db.session.get(User, session['user_id'])
    earnings_list = Earning.query.filter_by(user_id=user.id).order_by(Earning.timestamp.desc()).all()
    
    return render_template(
        'earnings.html',
        earnings_list=earnings_list,
        total_credit=user.credit
    )


@app.route('/post', methods=['GET', 'POST'])
def post_task():
    if 'user_id' not in session:
        flash("Please login to post a task!")
        return redirect(url_for('login'))

    if request.method == 'POST':
        current_user = User.query.get(session['user_id'])

        new_task = Task(
            title=request.form.get('title'),
            price=float(request.form.get('price')),
            description=request.form.get('description'),
            category=request.form.get('category'),
            deadline=request.form.get('deadline'),
            capacity=request.form.get('capacity'),
            urgent=True if request.form.get('urgent') else False,
            user=current_user.username 
        )
        db.session.add(new_task)
        db.session.commit()
        
        return redirect(url_for('my_task')) 
        
    return render_template('post_task.html')

@app.route('/edit_task/<int:task_id>', methods=['GET', 'POST'])
def edit_task(task_id):
    task = Task.query.get_or_404(task_id)
    user = User.query.get(session.get('user_id'))

    # Security: Only the creator can edit
    if not user or task.user != user.username:
        flash("You are not authorized to edit this task!")
        return redirect(url_for('my_task'))

    if request.method == 'POST':
        task.title = request.form.get('title')
        task.price = float(request.form.get('price'))
        task.category = request.form.get('category')
        task.description = request.form.get('description')
        task.deadline = request.form.get('deadline')
        
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

    # 1. Logic Check: Cannot delete if anyone is already HIRED
    if task.get_hired_count() > 0:
        flash("Cannot delete a task that has active hired help!")
        return redirect(url_for('my_task'))

    # 2. Notify PENDING applicants before deletion
    pending_apps = Application.query.filter_by(task_id=task.id, status='Pending').all()
    for app_record in pending_apps:
        applicant = User.query.filter_by(username=app_record.applicant_username).first()
        if applicant:
            deletion_note = Notification(
                user_id=applicant.id,
                message=f"Alert: The task '{task.title}' you applied for was deleted by the owner.",
                status='unread'
            )
            db.session.add(deletion_note)

    # 3. Clean up associated records (Applications) to avoid Foreign Key errors
    Application.query.filter_by(task_id=task.id).delete()
    
    # 4. Finally delete the task
    db.session.delete(task)
    db.session.commit()
    
    flash("Task deleted successfully. Pending applicants have been notified.")
    return redirect(url_for('my_task'))

def patch_database():
    with db.engine.connect() as conn:
        user_cols = [row[1] for row in conn.execute(text("PRAGMA table_info(user)")).fetchall()]
        if "email" not in user_cols:
            conn.execute(text("ALTER TABLE user ADD COLUMN email VARCHAR(150)"))
        if "security_question" not in user_cols:
            conn.execute(text("ALTER TABLE user ADD COLUMN security_question VARCHAR(200)"))
        if "security_answer" not in user_cols:
            conn.execute(text("ALTER TABLE user ADD COLUMN security_answer VARCHAR(200)"))
        if "credit" not in user_cols:
            conn.execute(text("ALTER TABLE user ADD COLUMN credit FLOAT DEFAULT 0.0"))
        if "total_rating" not in user_cols:
            conn.execute(text("ALTER TABLE user ADD COLUMN total_rating FLOAT DEFAULT 5.0"))
        if "review_count" not in user_cols:
            conn.execute(text("ALTER TABLE user ADD COLUMN review_count INTEGER DEFAULT 1"))
        if "tasks_completed" not in user_cols:
            conn.execute(text("ALTER TABLE user ADD COLUMN tasks_completed INTEGER DEFAULT 0"))
        
        task_cols = [row[1] for row in conn.execute(text("PRAGMA table_info(task)")).fetchall()]
        if "urgent" not in task_cols:
            conn.execute(text("ALTER TABLE task ADD COLUMN urgent BOOLEAN DEFAULT 0"))
        
        # --- 3. 新增：检查 Message 表 (修复 bug 的关键) ---
       # --- 检查 Message 表是否存在 (防御性检查) ---
        table_check = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='message'")).fetchone()

        if table_check:
            # 获取所有列名
            message_cols = [row[1] for row in conn.execute(text("PRAGMA table_info(message)")).fetchall()]
            
            # 如果没有 is_read 列，则添加
            if "is_read" not in message_cols:
                conn.execute(text("ALTER TABLE message ADD COLUMN is_read BOOLEAN DEFAULT 0"))
                conn.commit()
                print("✅ Message table 'is_read' column patched successfully!")
        else:
            # 如果表还没建好，跳过不报错
            print("ℹ️ Message table doesn't exist yet, skipping patch.")


@app.route('/task/<int:task_id>')
def task_detail(task_id):
    task = Task.query.get_or_404(task_id)
    return render_template('task_detail.html', task=task)


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

        # 1. Prevent Self-Application
        if task.user == current_user.username:
            flash("You cannot apply for a task you created!")
            return redirect(url_for('marketplace'))

        # 2. Prevent Duplicate Applications
        existing_app = Application.query.filter_by(
            task_id=task.id, 
            applicant_username=current_user.username
        ).first()
        
        if existing_app:
            flash("You have already applied for this task!")
            return redirect(url_for('marketplace'))
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
    cleanup_expired_tasks()

    if 'user_id' not in session:
        return redirect(url_for('login'))
    current_user = User.query.get(session['user_id'])

    if not current_user:
        session.clear()
        return redirect(url_for('login'))

    view = request.args.get('view', 'created')
    created_tasks = Task.query.filter_by(user=current_user.username).all()

    # 为每个 created task 找第一个未被 rate 的 tasker
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
    my_applications = Application.query.filter_by(
        applicant_username=current_user.username
    ).all()

    applied_tasks = []

    for app in my_applications:
        task = Task.query.get(app.task_id)
        applied_tasks.append({
            'app': app,
            'task': task
        })

    # 这里可以添加一些逻辑，比如对 applied_tasks 进行处理

    return render_template('my_task.html',
                           created=created_tasks,
                           applied=applied_tasks,
                           view=view,
                           user=current_user,
                           Task=Task,
                           Rating=Rating,
                           first_unrated=first_unrated)


# --- 请找到 app.py 里的这部分并替换 ---

# --- 1. 修复查看申请人的路由 ---
@app.route('/view_applicants/<int:task_id>')
def view_applicants(task_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    task = Task.query.get_or_404(task_id)
    # 关键：获取该 task 下的所有申请记录
    apps = Application.query.filter_by(task_id=task_id).all()
    
    # 调试：在黑窗口看看查到了几个人
    print(f"DEBUG: Task {task_id} has {len(apps)} applicants.")
    
    user = User.query.get(session['user_id'])
    # 注意：这里的变量名是 apps，对应 HTML 里的 {% for app in apps %}
    return render_template('view_applicants.html', task=task, apps=apps, user=user)


# --- 2. 修复雇佣人的路由 (确保 GET 请求也能跑通) ---
@app.route('/hire_applicant/<int:app_id>')
def hire_applicant(app_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    application = Application.query.get_or_404(app_id)
    task = Task.query.get(application.task_id)

    # --- BUG 修复 1: 检查该申请人是否已经处于 'Hired' 状态 ---
    if application.status == 'Hired':
        flash(f"{application.applicant_username} is already hired!")
        return redirect(url_for('view_applicants', task_id=task.id))

    # --- BUG 修复 2: 再次确认任务人数是否已满 ---
    if task.get_hired_count() < task.capacity:
        application.status = 'Hired'
        
        # 处理任务状态逻辑
        if task.capacity == 1:
            task.tasker = application.applicant_username
            task.status = 'In Progress'
        else:
            # 如果是多人任务，检查雇佣当前这个人后是否满员
            if task.get_hired_count() >= task.capacity:
                task.status = 'In Progress'
                # 如果没有主要负责人，就把第一个雇佣的人设为 tasker
                if not task.tasker:
                    task.tasker = application.applicant_username

        # 发送通知
        applicant_user = User.query.filter_by(username=application.applicant_username).first()
        if applicant_user:
            new_note = Notification(
                user_id=applicant_user.id,
                task_id=task.id,
                message=f"You have been HIRED for the task: {task.title}!"
            )
            db.session.add(new_note)
        
        db.session.commit()
        flash(f"Successfully hired {application.applicant_username}!")
    else:
        flash("Task is already at full capacity!")

    # 修复后跳转回查看申请人页面，这样你可以继续看剩下的人
    return redirect(url_for('view_applicants', task_id=task.id))






@app.route('/reject_applicant/<int:app_id>')
def reject_applicant(app_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    application = Application.query.get_or_404(app_id)
    application.status = 'Rejected'
    db.session.commit()

    flash("Applicant has been rejected.")
    return redirect(url_for('view_applicants', task_id=application.task_id))

# --- Add this helper function ---

@app.route('/chat/<int:task_id>')
def chat(task_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    task = Task.query.get_or_404(task_id)
    user = User.query.get(session['user_id'])

    unread_messages = Message.query.filter_by(task_id=task_id, is_read=False).filter(Message.sender != user.username).all()
    if unread_messages:
        for msg in unread_messages:
            msg.is_read = True
            already_read = MessageRead.query.filter_by(message_id=msg.id, username=user.username).first()
            if not already_read:
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

    unread_messages = Message.query.filter_by(task_id=task_id, is_read=False).filter(Message.sender != user.username).all()
    if unread_messages:
        for msg in unread_messages:
            # is_read 保留，同时记录每个人独立的已读
            already_read = MessageRead.query.filter_by(message_id=msg.id, username=user.username).first()
            if not already_read:
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

    # 1. 只要评的不是自己，就放行
    if c_name == t_name:
        flash("You cannot rate yourself!")
        return redirect(url_for('my_task'))

    # 2. 检查是不是已经评过【这个人】了
    already = Rating.query.filter_by(task_id=task_id, reviewer_username=c_name, target_username=t_name).first()
    if already:
        flash(f"You already rated {t_name}!")
        return redirect(url_for('my_task'))

    # 3. 角色判断只为了前端显示 (Client 评 Tasker)
    role = 'tasker' if c_name == task.user else 'client'

    # --- 这里就是你最珍贵的 Next Target 逻辑，保留它 ---
    next_target = None
    if role == 'tasker':
        hired_apps = Application.query.filter_by(task_id=task_id, status='Hired').all()
        rated_list = [r.target_username for r in Rating.query.filter_by(task_id=task_id, reviewer_username=c_name).all()]
        for app in hired_apps:
            if app.applicant_username != t_name and app.applicant_username not in rated_list:
                next_target = app.applicant_username
                break

    return render_template('rate_user.html', task=task, task_id=task_id, target_user=t_name, role=role, next_target=next_target)


@app.route('/submit_rating/<int:task_id>/<target_user>', methods=['POST'])
def submit_rating(task_id, target_user):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    current_user = db.session.get(User, session['user_id'])

    already_rated = Rating.query.filter_by(
        task_id=task_id,
        reviewer_username=current_user.username
    ).first()
    if already_rated:
        flash("You have already rated this task.")
        return redirect(url_for('my_task'))

    rating_val = int(request.form.get('rating', 5))
    review_text = request.form.get('review', '')

    new_rating = Rating(
    task_id=task_id,
    reviewer_username=current_user.username,
    target_username=target_user,
    score=rating_val,
    review_content=review_text,
    timestamp=datetime.now(my8)
    )
    db.session.add(new_rating)

    user_to_rate = User.query.filter_by(username=target_user).first()
    if user_to_rate:
        user_to_rate.total_rating += rating_val
        user_to_rate.review_count += 1
        db.session.commit()

    flash("Rating submitted successfully!")
    return redirect(url_for('dashboard'))


@app.route('/view_ratings')
def view_ratings():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = db.session.get(User, session['user_id'])
    real_reviews = Rating.query.filter_by(target_username=user.username).order_by(Rating.timestamp.desc()).all()
    avg_rating = round(user.total_rating / user.review_count, 1) if user.review_count > 0 else 5.0

    return render_template('view_ratings.html', 
                           user=user, 
                           reviews=real_reviews,
                           avg_rating=avg_rating)


# =========================
# SOCKET IO
# =========================

@socketio.on('join')
def on_join(data):
    username = data['username']
    room = data['room']
    join_room(room)
    print(f"用户 {username} 加入了房间 {room}")

@socketio.on('send_message')
def handle_message(data):
    room = data['room']
    sender_name = data['username']
    
    # 1. 广播消息内容（让大家在聊天窗口看到文字）
    emit('receive_message', data, room=room)
    
    # 2. 存入数据库
    new_msg = Message(
        task_id=int(room), 
        sender=sender_name, 
        content=data['message'],
        reply_to_id=data.get('reply_to_id')
    )
    db.session.add(new_msg)
    db.session.commit()
    emit('receive_message', data, room=data['room'])

    # 3. --- 群聊红点广播逻辑 (WhatsApp/WeChat Style) ---
    task = db.session.get(Task, int(room))
    if task:
        # 找出这个 task 所有 hired 的人 + creator
        all_members = set()
        all_members.add(task.user)  # creator
        hired_apps = Application.query.filter_by(task_id=int(room), status='Hired').all()
        for app in hired_apps:
            all_members.add(app.applicant_username)
        
        # 通知除了发送者以外的所有人
        for username in all_members:
            if username != data['username']:
                member = User.query.filter_by(username=username).first()
                if member:
                    # 判断这个人的 role 来决定红点亮哪个 tab
                    role = 'created' if username == task.user else 'applied'
                    socketio.emit('new_unread', {
                        'task_id': int(room),
                        'role': role
                    }, room=str(member.id))
            print(f"群发红点：已通知成员 {username}")


# --- 编辑消息 ---
@socketio.on('edit_message')
def handle_edit(data):
    msg_id = data.get('message_id')
    new_content = data.get('new_content')
    msg = Message.query.get(msg_id)    # 只有发送者本人能编辑
    if msg and msg.sender == session.get('user_username'):
        msg.content = new_content
        msg.is_edited = True
        db.session.commit()
        # 广播给所有人：哪条消息变了，新内容是什么
        emit('message_edited', {
            'message_id': msg.id,
            'new_content': msg.content
        }, room=str(msg.task_id))

# --- 删除消息 ---
@socketio.on('delete_message')
def handle_delete(data):
    msg_id = data.get('message_id')
    # 先拿到当前登录的用户对象
    current_user = User.query.get(session.get('user_id'))
    
    msg = db.session.get(Message, msg_id)
    if msg and current_user:
        # 用名字字符串进行对比
        if msg.sender == current_user.username:
            msg.is_deleted = True
            db.session.commit()
            emit('message_deleted', {'message_id': msg_id}, room=str(msg.task_id))



@socketio.on('connect')
def handle_connect():
    if 'user_id' in session:
        join_room(str(session['user_id']))
        print(f"User {session['user_id']} connected to their private room.")


if __name__ == '__main__':
    with app.app_context():
        
        # 按照你写好的新 Message 类重新建表
        db.create_all()
        print("!!! Database has been reset with NEW columns !!!")
        
    socketio.run(app, debug=True, port=8000)