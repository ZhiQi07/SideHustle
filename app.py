from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_socketio import SocketIO, emit, join_room
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func, text
import os

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
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    skills = db.Column(db.Text, default="No skills listed")
    is_admin = db.Column(db.Boolean, default=False)
    # --- 新增的 Dashboard 字段 ---
    credit = db.Column(db.Float, default=0.0)
    total_rating = db.Column(db.Float, default=5.0)
    review_count = db.Column(db.Integer, default=1)
    tasks_completed = db.Column(db.Integer, default=0)

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    description = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(20), default='Available') # Available, In Progress, Completed
    user = db.Column(db.String(50)) # 发布者
    tasker = db.Column(db.String(50)) # 执行者
    deadline = db.Column(db.String(50))
    capacity = db.Column(db.Integer, default=1)
    urgent = db.Column(db.Boolean, default=False)
    progress = db.Column(db.Integer, default=0)

    def get_applicant_count(self):
        return Application.query.filter_by(task_id=self.id).count()

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

class Earning(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    activity = db.Column(db.String(150), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    timestamp = db.Column(db.DateTime, default=db.func.now())

# =========================
# INIT DB
# =========================
with app.app_context():
    db.create_all()

# =========================
# ROUTES
# =========================

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username, password=password).first()
        if user:
            session['user_id'] = user.id
            return redirect(url_for('marketplace'))
        flash("Invalid credentials!")
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if User.query.filter_by(username=username).first():
            flash("Username exists!")
            return redirect(url_for('signup'))
        new_user = User(username=username, password=password)
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('login'))
    return render_template('signup.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = db.session.get(User, session['user_id'])
    
    # 自动计算平均分
    avg_rating = round(user.total_rating / user.review_count, 1) if user.review_count > 0 else 0.0
    
    # 获取正在进行中的任务（Tasks Tracking）
    tracking_list = Task.query.filter_by(tasker=user.username).filter(Task.status == 'In Progress').all()
    
    return render_template(
        'dashboard.html',
        total_credit=user.credit,
        average_rating=avg_rating,
        tasks_done=user.tasks_completed,
        tracking_list=tracking_list,
        user=user
    )

@app.route('/earnings')
def earnings():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = db.session.get(User, session['user_id'])
    # 查找该用户所有的收入记录
    earnings_list = Earning.query.filter_by(user_id=user.id).order_by(Earning.timestamp.desc()).all()
    
    return render_template(
        'earnings.html',
        earnings_list=earnings_list,
        total_credit=user.credit
    )


@app.route('/marketplace')
def marketplace():
    tasks = Task.query.filter_by(status='Available').all()
    user = db.session.get(User, session.get('user_id')) if 'user_id' in session else None
    return render_template('marketplace.html', tasks=tasks, user=user)

@app.route('/post', methods=['GET', 'POST'])
def post_task():
    if 'user_id' not in session: return redirect(url_for('login'))
    if request.method == 'POST':
        user = db.session.get(User, session['user_id'])
        new_task = Task(
            title=request.form.get('title'),
            price=float(request.form.get('price')),
            description=request.form.get('description'),
            category=request.form.get('category'),
            user=user.username,
            deadline=request.form.get('deadline'),
            urgent=True if request.form.get('urgent') else False
        )
        db.session.add(new_task)
        db.session.commit()
        return redirect(url_for('marketplace'))
    return render_template('post_task.html')


def patch_database():
    with db.engine.connect() as conn:
        # 检查 User 表缺少的字段并补上
        user_cols = [row[1] for row in conn.execute(text("PRAGMA table_info(user)")).fetchall()]
        
        if "credit" not in user_cols:
            conn.execute(text("ALTER TABLE user ADD COLUMN credit FLOAT DEFAULT 0.0"))
        if "total_rating" not in user_cols:
            conn.execute(text("ALTER TABLE user ADD COLUMN total_rating FLOAT DEFAULT 5.0"))
        if "review_count" not in user_cols:
            conn.execute(text("ALTER TABLE user ADD COLUMN review_count INTEGER DEFAULT 1"))
        if "tasks_completed" not in user_cols:
            conn.execute(text("ALTER TABLE user ADD COLUMN tasks_completed INTEGER DEFAULT 0"))
        
        # 检查 Task 表是否缺少 tasker 字段
        task_cols = [row[1] for row in conn.execute(text("PRAGMA table_info(task)")).fetchall()]
        if "tasker" not in task_cols:
            conn.execute(text("ALTER TABLE task ADD COLUMN tasker VARCHAR(50)"))
        
        conn.commit()
        print("✅ Database columns patched successfully!")



@app.route('/task/<int:task_id>')
def task_detail(task_id): # <--- 确保这里叫 task_detail
    task = Task.query.get_or_404(task_id)
    return render_template('task_detail.html', task=task)


# 只是为了占位，不准报 BuildError！
@app.route('/task_tracking/<int:task_id>')
def task_tracking(task_id):
    # 暂时只返回一句话，不影响你其他的逻辑
    return f"This is tracking page for Task {task_id}. Developing..."


@app.route('/my_task')
def my_task():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = db.session.get(User, session['user_id'])
    view = request.args.get('view', 'created')
    
    # 1. 我创建的任务 (我作为 Tasker/Client 发布出去的)
    created = Task.query.filter_by(user=user.username).all()
    
    # 2. 我申请的任务 (核心修改点)
    # 第一步：去 Application 表里查：这个用户申请了哪些任务的 ID
    user_applications = Application.query.filter_by(applicant_username=user.username).all()
    
    # 第二步：根据这些 ID，去 Task 表里把对应的任务对象找出来
    applied_task_ids = [app.task_id for app in user_applications]
    applied = Task.query.filter(Task.id.in_(applied_task_ids)).all() if applied_task_ids else []
    
    return render_template(
        'my_task.html', 
        created=created, 
        applied=applied, 
        view=view, 
        user=user
    )


@app.route('/view_applicants/<int:task_id>')
def view_applicants(task_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    task = Task.query.get_or_404(task_id)
    # 查找所有申请这个任务的人
    apps = Application.query.filter_by(task_id=task_id).all()
    return render_template('view_applicants.html', task=task, apps=apps)


@app.route('/apply/<int:task_id>', methods=['GET', 'POST'])
def apply(task_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    task = Task.query.get_or_404(task_id)
    user = db.session.get(User, session['user_id'])

    if request.method == 'POST':
        new_app = Application(
            task_id=task.id,
            applicant_username=user.username,
            intro=request.form.get('intro'),
            reason=request.form.get('reason')
        )
        db.session.add(new_app)
        db.session.commit()
        flash("Application submitted!")
        return redirect(url_for('marketplace'))
    
    return render_template('apply.html', task=task)




@app.route('/chat/<int:task_id>')
def chat(task_id):
    if 'user_id' not in session: return redirect(url_for('login'))
    task = Task.query.get_or_404(task_id)
    user = db.session.get(User, session['user_id'])
    history = Message.query.filter_by(task_id=task_id).order_by(Message.timestamp.asc()).all()
    return render_template('chat.html', task=task, user=user, history=history)

# --- 任务完成自动结账逻辑 ---
@app.route('/complete_task/<int:task_id>')
def complete_task(task_id):
    task = Task.query.get_or_404(task_id)
    if task.status != 'Completed':
        task.status = 'Completed'
        # 给做任务的人加钱
        worker = User.query.filter_by(username=task.tasker).first()
        if worker:
            worker.credit += task.price
            worker.tasks_completed += 1
            # 记录一笔账单
            new_earning = Earning(user_id=worker.id, activity=f"Completed: {task.title}", amount=task.price)
            db.session.add(new_earning)
        db.session.commit()
    return redirect(url_for('dashboard'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# --- SocketIO ---
@socketio.on('join')
def on_join(data):
    join_room(data['room'])

@socketio.on('send_message')
def handle_send_message(data):
    new_msg = Message(task_id=data['room'], sender=data['username'], content=data['message'])
    db.session.add(new_msg)
    db.session.commit()
    emit('receive_message', data, room=data['room'])

@app.route('/reset-db')
def reset_db():
    with app.app_context():
        db.drop_all()   # 删掉所有表
        db.create_all() # 重新按新模型建表
    return "Database has been reset! Please sign up a new account."


if __name__ == '__main__':
    socketio.run(app, debug=True, port=8000)