from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_socketio import SocketIO, emit, join_room
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func, text
import os
from datetime import datetime

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
    credit = db.Column(db.Float, default=0.0)
    total_rating = db.Column(db.Float, default=5.0)
    review_count = db.Column(db.Integer, default=1)
    tasks_completed = db.Column(db.Integer, default=0)

    # --- 把下面这个函数粘贴在这里 ---
    # 确保 def 前面有 4 个空格，不要套在别的函数里
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
    status = db.Column(db.String(20), default='Available') # Available, In Progress, Completed
    user = db.Column(db.String(50)) # 发布者
    tasker = db.Column(db.String(50)) # 执行者
    deadline = db.Column(db.String(50))
    capacity = db.Column(db.Integer, default=1)
    tasker = db.Column(db.String(50)) # Stores the username of the person hired
    progress = db.Column(db.Integer, default=0) # Stores 0, 25, 50, 75, or 100
    urgent = db.Column(db.Boolean, default=False)

    def get_applicant_count(self):
        # This counts how many applications have this task's ID
        return Application.query.filter_by(task_id=self.id).count()
    
    def get_unread_count(self, current_username):
        # 统计该任务下：1.未读的 2.发送者不是当前用户 的消息数量
        return Message.query.filter_by(task_id=self.id, is_read=False).filter(Message.sender != current_username).count()



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


class Earning(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    activity = db.Column(db.String(150), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    timestamp = db.Column(db.DateTime, default=db.func.now())



class Rating(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('task.id'), nullable=False)
    reviewer_username = db.Column(db.String(50), nullable=False) # 谁写的评价
    target_username = db.Column(db.String(50), nullable=False)   # 评价谁
    score = db.Column(db.Integer, nullable=False)               # 分数 (1-5)
    review_content = db.Column(db.Text)                         # 评价文字
    timestamp = db.Column(db.DateTime, default=db.func.now())

# 记得在 app.app_context() 里面运行 db.create_all() 以创建这张表

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

@app.route('/marketplace')
def marketplace():
    query = request.args.get('q')
    category = request.args.get('cat')

    # 核心修改：默认只查询状态为 'Available' 的任务，防止显示已领取的任务
    tasks_filter = Task.query.filter_by(status='Available')

    if query:
        tasks_filter = tasks_filter.filter((Task.title.contains(query)) | (Task.description.contains(query)))
    
    if category:
        tasks_filter = tasks_filter.filter(Task.category == category)

    all_tasks = tasks_filter.all()

    # 获取当前登录用户信息，用于页面顶部的欢迎语
    current_user = None
    if 'user_id' in session:
        current_user = db.session.get(User, session['user_id'])
        
    return render_template('marketplace.html', tasks=all_tasks, user=current_user)



@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = db.session.get(User, session['user_id'])
    avg_rating = round(user.total_rating / user.review_count, 1) if user.review_count > 0 else 5.0
    
    # --- 修改这里：删掉 .filter(Task.status != 'Completed') ---
    # 这样无论是进行中还是已完成的任务，都会显示在 Tracking 列表里
    tracking_list = Task.query.filter_by(tasker=user.username).all()
    
    return render_template(
        'dashboard.html',
        username=user.username,
        total_credit=user.credit,
        average_rating=avg_rating,
        tasks_done=user.tasks_completed,
        tracking_list=tracking_list # 现在的列表包含所有你接过手的任务
    )


@app.route('/update_progress/<int:task_id>', methods=['POST'])
def update_progress(task_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    new_progress = int(request.form.get('progress', 0))
    task = db.session.get(Task, task_id)
    user = db.session.get(User, session['user_id'])
    
    # 核心结算逻辑
    if new_progress == 100 and task.status != 'Completed':
        task.status = 'Completed'
        
        if user.tasks_completed is None:
            user.tasks_completed = 0
        user.tasks_completed += 1
        
        if hasattr(task, 'price') and task.price:
            if user.credit is None:
                user.credit = 0.0
            user.credit += task.price
            
            # --- 修复后的部分：使用 activity 而不是 description ---
            new_earning = Earning(
                user_id=user.id,
                activity=f"Completed Task: {task.title}", # 对应模型中的 activity 字段
                amount=task.price,
                timestamp=datetime.now()
            )
            db.session.add(new_earning)
            # --------------------------------------------------
            
        print(f"SUCCESS: {user.username} 结算成功！任务：{task.title}")

    task.progress = new_progress
    db.session.commit()
    
    return redirect(url_for('my_task', view='applied'))




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
        
        # --- 3. 新增：检查 Message 表 (修复 bug 的关键) ---
        message_cols = [row[1] for row in conn.execute(text("PRAGMA table_info(message)")).fetchall()]
        if "is_read" not in message_cols:
            conn.execute(text("ALTER TABLE message ADD COLUMN is_read BOOLEAN DEFAULT 0"))
        
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
    view = request.args.get('view', 'created')

    created_tasks = Task.query.filter_by(user=current_user.username).all()
    
    # FIX: Send the Application objects so we can see the status (Pending/Hired/Rejected)
    my_applications = Application.query.filter_by(applicant_username=current_user.username).all()

    return render_template('my_task.html', 
                           created=created_tasks, 
                           applied=my_applications, # This is now a list of Applications
                           view=view, 
                           user=current_user,
                           Task=Task)

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

@app.route('/reject_applicant/<int:app_id>')
def reject_applicant(app_id):
    # 1. Security: Ensure the user is logged in
    if 'user_id' not in session:
        return redirect(url_for('login'))

    # 2. Find the application using its ID
    application = Application.query.get_or_404(app_id)
    
    # 3. Update the status to 'Rejected'
    application.status = 'Rejected'
    
    # 4. Save the change to the database
    db.session.commit()

    flash("Applicant has been rejected.")
    
    # 5. Redirect back to the list so you can see the update
    return redirect(url_for('view_applicants', task_id=application.task_id))




@app.route('/chat/<int:task_id>')
def chat(task_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    task = Task.query.get_or_404(task_id)
    user = User.query.get(session['user_id'])
    
    # 1. 找到未读消息
    unread_messages = Message.query.filter_by(task_id=task_id, is_read=False).filter(Message.sender != user.username).all()
    
    if unread_messages:
        for msg in unread_messages:
            msg.is_read = True
        db.session.commit()
        
        # 2. 【核心新增】发送一个 Socket 信号给当前用户，告诉前端“这个任务的消息已经读过了”
        # 这里建议发给当前用户的个人 room
        socketio.emit('clear_unread', {'task_id': task_id}, room=str(session['user_id'])) 
    
    history = Message.query.filter_by(task_id=task_id).order_by(Message.timestamp.asc()).all()
    return render_template('chat.html', task=task, user=user, history=history)

@app.route('/rate_user/<int:task_id>/<target_user>')
def rate_user(task_id, target_user):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    current_user = db.session.get(User, session['user_id'])

    # ← 已经 rate 过，直接跳走
    already_rated = Rating.query.filter_by(
        task_id=task_id,
        reviewer_username=current_user.username
    ).first()
    if already_rated:
        flash("You have already rated this task.")
        return redirect(url_for('my_task'))

    task = Task.query.get_or_404(task_id)
    role = 'tasker' 

    # 3. 这里的参数一定要补全：把 task 和 role 都传进去
    return render_template('rate_user.html', 
                           task_id=task_id, 
                           target_user=target_user, 
                           task=task,    # 修复 UndefinedError 的关键
                           role=role)    # 修复角色判断的关键


@app.route('/submit_rating/<int:task_id>/<target_user>', methods=['POST'])
def submit_rating(task_id, target_user):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    current_user = db.session.get(User, session['user_id'])

    # ← 加这个检查：已经 rate 过就直接跳走
    already_rated = Rating.query.filter_by(
        task_id=task_id,
        reviewer_username=current_user.username
    ).first()
    if already_rated:
        flash("You have already rated this task.")
        return redirect(url_for('my_task'))

    rating_val = int(request.form.get('rating', 5))
    review_text = request.form.get('review', '')

    # 1. 保存到 Rating 表
    new_rating = Rating(
        task_id=task_id,
        reviewer_username=current_user.username,
        target_username=target_user,
        score=rating_val,
        review_content=review_text
    )
    db.session.add(new_rating)

    # 2. 更新被评价人的 User 表数据（用于计算平均分）
    user_to_rate = User.query.filter_by(username=target_user).first()
    if user_to_rate:
        # 如果是第一次评价，把默认的 5.0 和 1 次计数重置掉（可选逻辑）
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
    
    # --- 核心修改：从数据库查询真正的评价 ---
    real_reviews = Rating.query.filter_by(target_username=user.username).order_by(Rating.timestamp.desc()).all()
    
    avg_rating = round(user.total_rating / user.review_count, 1) if user.review_count > 0 else 5.0

    return render_template('view_ratings.html', 
                           user=user, 
                           reviews=real_reviews, # 传给前端真正的数据库记录
                           avg_rating=avg_rating)






@socketio.on('join')
def on_join(data):
    username = data['username']
    room = data['room']
    join_room(room)
    print(f"用户 {username} 加入了房间 {room}")[cite: 11]

@socketio.on('send_message')
def handle_message(data):
    room = data['room']
    emit('receive_message', data, room=room)
    
    new_msg = Message(
        task_id=int(room), 
        sender=data['username'], 
        content=data['message']
    )
    db.session.add(new_msg)
    db.session.commit()

    # 找出这个 task 的另一方，推送通知给他
    task = db.session.get(Task, int(room))
    if task:
        recipient = None
        if task.user == data['username']:
            # 发送者是 creator，收件人是 tasker
            recipient = User.query.filter_by(username=task.tasker).first()
        elif task.tasker == data['username']:
            # 发送者是 tasker，收件人是 creator
            recipient = User.query.filter_by(username=task.user).first()
        
        if recipient:
            socketio.emit('new_unread', {'task_id': int(room)}, room=str(recipient.id))


@socketio.on('connect')
def handle_connect():
    if 'user_id' in session:
        # 用户一连接，就让他加入以自己 ID 命名的房间
        join_room(str(session['user_id']))
        print(f"User {session['user_id']} connected to their private room.")




if __name__ == '__main__':
    with app.app_context():
        # 在启动前先修补数据库结构
        patch_database() 
    socketio.run(app, debug=True, port=8000)