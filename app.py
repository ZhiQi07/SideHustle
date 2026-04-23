from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func, text
import os
import random
from flask_socketio import SocketIO, emit, join_room

# 初始化 SocketIO
# cors_allowed_origins="*" 是为了防止调试时出现跨域错误
socketio = SocketIO(app, cors_allowed_origins="*")


app = Flask(__name__)
app.secret_key = "mmu_secret_key"

# =========================
# DATABASE CONFIG
# =========================
basedir = os.path.abspath(os.path.dirname(__file__))
db_path = os.path.join(basedir, 'database.db')

print("📂 DATABASE PATH:", db_path)

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


class Earning(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    activity = db.Column(db.String(150), nullable=False)
    amount = db.Column(db.Float, nullable=False)


class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    score = db.Column(db.Float, nullable=False)


class TaskTracking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    task_title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, default="No description")
    progress = db.Column(db.Integer, default=0)
    due_date = db.Column(db.String(50))


# =========================
# SAFE FIX FOR OLD DATABASE
# 自动补缺少的 column
# 不用删 database
# =========================
def safe_add_missing_columns():
    with db.engine.connect() as conn:
        tables = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()
        table_names = [row[0] for row in tables]

        if "task_tracking" in table_names:
            result = conn.execute(text("PRAGMA table_info(task_tracking)"))
            existing_columns = [row[1] for row in result]

            if "description" not in existing_columns:
                conn.execute(text(
                    "ALTER TABLE task_tracking ADD COLUMN description TEXT DEFAULT 'No description'"
                ))
                conn.commit()
                print("✅ Added missing column: description")

            if "progress" not in existing_columns:
                conn.execute(text(
                    "ALTER TABLE task_tracking ADD COLUMN progress INTEGER DEFAULT 0"
                ))
                conn.commit()
                print("✅ Added missing column: progress")

            if "due_date" not in existing_columns:
                conn.execute(text(
                    "ALTER TABLE task_tracking ADD COLUMN due_date TEXT"
                ))
                conn.commit()
                print("✅ Added missing column: due_date")


# =========================
# DEMO DATA
# 只给完全没有 user 的情况看
# 有 user 后就不显示 demo
# 不写进 database
# =========================
def use_demo_data():
    return User.query.count() == 0


def get_demo_earnings():
    return [
        {"id": 1, "activity": "Payment for task: Poster design for club", "amount": 50.0},
        {"id": 2, "activity": "Payment for task: Arrange table in room C-206", "amount": 30.0},
        {"id": 3, "activity": "Payment for task: Edit club promo video", "amount": 45.0},
    ]


def get_demo_tracking():
    return [
        {
            "id": 1,
            "task_title": "Arrange table in room C-206",
            "description": "Help arrange the tables and chairs before the event starts.",
            "progress": 67,
            "due_date": "20 Apr 2026"
        },
        {
            "id": 2,
            "task_title": "Poster design for club",
            "description": "Create a simple A4 promotional poster for the student club event.",
            "progress": 76,
            "due_date": "18 Apr 2026"
        }
    ]


def get_demo_tasks():
    return [
        {
            "id": 1,
            "title": "Arrange table in room C-206",
            "price": 30.0,
            "description": "Help arrange tables before event starts",
            "category": "Event",
            "user": "Ali",
            "rating": 4.9,
            "urgent": False
        },
        {
            "id": 2,
            "title": "Poster design for club",
            "price": 50.0,
            "description": "Need a simple A4 poster design",
            "category": "Design",
            "user": "Sarah",
            "rating": 4.8,
            "urgent": True
        },
        {
            "id": 3,
            "title": "Edit short promo reel",
            "price": 45.0,
            "description": "Need a short 30-second promotional video for Instagram.",
            "category": "Editing",
            "user": "Client A",
            "rating": 4.7,
            "urgent": False
        }
    ]


# =========================
# INIT
# =========================
with app.app_context():
    db.create_all()
    safe_add_missing_columns()


# =========================
# ROUTES
# =========================


@app.route('/chat/<int:task_id>')
def chat(task_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    task = Task.query.get_or_404(task_id)
    current_user = User.query.get(session['user_id'])
    
    return render_template('chat.html', task=task, user=current_user)


# LOGIN
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        user = User.query.filter_by(username=username, password=password).first()

        if user:
            session['user_id'] = user.id
            session['is_admin'] = user.is_admin
            return redirect(url_for('marketplace'))
        else:
            flash("Invalid credentials!")

    return render_template('login.html')


# SIGNUP
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash("Username already exists!")
            return redirect(url_for('signup'))

        new_user = User(
            username=username,
            password=password
        )
        db.session.add(new_user)
        db.session.commit()

        return redirect(url_for('login'))

    return render_template('signup.html')


# MARKETPLACE
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

    current_user = None
    if 'user_id' in session:
        current_user = db.session.get(User, session['user_id'])

    return render_template('marketplace.html', tasks=all_tasks, user=current_user)


# DASHBOARD
@app.route('/dashboard')
def dashboard():
    demo_mode = use_demo_data()

    if demo_mode:
        demo_earnings = get_demo_earnings()
        demo_tracking = get_demo_tracking()

        total_credit = sum(item["amount"] for item in demo_earnings)
        average_rating = round(random.uniform(4.5, 5.0), 1)
        tasks_done = 2
        tracking_list = demo_tracking

    else:
        total_credit = db.session.query(
            func.coalesce(func.sum(Earning.amount), 0)
        ).scalar()

        # ✅ 只改 rating（安全 + 每次随机）
        reviews = Review.query.all()

        if len(reviews) > 0:
            sample_size = random.randint(1, len(reviews))
            random_reviews = random.sample(reviews, sample_size)

            avg_rating = sum(r.score for r in random_reviews) / sample_size
            average_rating = round(avg_rating, 1)
        else:
            average_rating = 0.0

        # ❗这些保持原本逻辑（没动）
        tasks_done = Task.query.filter_by(status='Completed').count()
        tracking_list = TaskTracking.query.order_by(TaskTracking.id.desc()).limit(2).all()

    current_user = None
    if 'user_id' in session:
        current_user = db.session.get(User, session['user_id'])

    return render_template(
        'dashboard.html',
        total_credit=total_credit,
        average_rating=average_rating,
        tasks_done=tasks_done,
        tracking_list=tracking_list,
        username=current_user.username if current_user else 'Qing'
    )


# EARNINGS / CREDIT PAGE
@app.route('/earnings')
def earnings():
    demo_mode = use_demo_data()

    if demo_mode:
        earnings_list = get_demo_earnings()
        total_credit = sum(item["amount"] for item in earnings_list)
    else:
        earnings_list = Earning.query.order_by(Earning.id.desc()).all()
        total_credit = db.session.query(
            func.coalesce(func.sum(Earning.amount), 0)
        ).scalar()

    return render_template(
        'earnings.html',
        earnings_list=earnings_list,
        total_credit=total_credit
    )


# TASK TRACKING PAGE
@app.route('/task-tracking')
def task_tracking():
    demo_mode = use_demo_data()

    if demo_mode:
        tracking_list = get_demo_tracking()
    else:
        tracking_list = TaskTracking.query.order_by(TaskTracking.id.desc()).all()

    return render_template('task_tracking.html', tracking_list=tracking_list)


# POST TASK
@app.route('/post', methods=['GET', 'POST'])
def post_task():
    # 1. Safety Check: Make sure the user is actually logged in
    if 'user_id' not in session:
        flash("Please login to post a task!")
        return redirect(url_for('login'))

    if request.method == 'POST':
        capacity_value = request.form.get('capacity')

        new_task = Task(
            title=request.form.get('title'),
            price=float(request.form.get('price')),
            description=request.form.get('description'),
            category=request.form.get('category'),
            deadline=request.form.get('deadline'),
            capacity=int(capacity_value) if capacity_value else 1,
            urgent=True if request.form.get('urgent') else False
        )

        db.session.add(new_task)
        db.session.commit()

        return redirect(url_for('marketplace'))

    return render_template('post_task.html')


# TASK DETAIL
@app.route('/task/<int:task_id>')
def task_detail(task_id):
    demo_mode = use_demo_data()

    if demo_mode:
        task = next((t for t in get_demo_tasks() if t["id"] == task_id), None)
        if not task:
            return redirect(url_for('marketplace'))
        return render_template('task_detail.html', task=task)

    task = Task.query.get_or_404(task_id)
    return render_template('task_detail.html', task=task)


# APPLY
@app.route('/apply/<int:task_id>', methods=['GET', 'POST'])
def apply(task_id):
    demo_mode = use_demo_data()

    if demo_mode:
        task = next((t for t in get_demo_tasks() if t["id"] == task_id), None)
        if not task:
            return redirect(url_for('marketplace'))
        if request.method == 'POST':
            return redirect(url_for('marketplace'))
        return render_template('apply.html', task=task)

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


# =========================
# SAMPLE DATABASE ROUTES
# =========================

@app.route('/add-sample-earnings')
def add_sample_earnings():
    sample_earnings = [
        Earning(activity="Payment for task: Poster design for club", amount=50.0),
        Earning(activity="Payment for task: Arrange table in room C-206", amount=30.0),
        Earning(activity="Payment for task: Edit club promo video", amount=45.0),
    ]

    db.session.add_all(sample_earnings)
    db.session.commit()
    return redirect(url_for('earnings'))


@app.route('/add-sample-reviews')
def add_sample_reviews():
    sample_reviews = [
    Review(score=3.5),
    Review(score=5.0),
    Review(score=4.0),
    Review(score=2.8),
]

    db.session.add_all(sample_reviews)
    db.session.commit()
    return redirect(url_for('dashboard'))


@app.route('/add-sample-tracking')
def add_sample_tracking():
    sample_tracking = [
        TaskTracking(
            task_title="Arrange table in room C-206",
            description="Help arrange the tables and chairs before the event starts.",
            progress=67,
            due_date="20 Apr 2026"
        ),
        TaskTracking(
            task_title="Poster design for club",
            description="Create a simple A4 promotional poster for the student club event.",
            progress=76,
            due_date="18 Apr 2026"
        ),
    ]

    db.session.add_all(sample_tracking)
    db.session.commit()
    return redirect(url_for('dashboard'))


@app.route('/add-sample-completed-tasks')
def add_sample_completed_tasks():
    sample_tasks = [
        Task(
            title="Arrange table in room C-206",
            price=30.0,
            description="Help arrange tables before event starts",
            category="Event",
            status="Completed",
            user="Ali",
            rating=4.9,
            urgent=False,
            deadline="20 Apr 2026",
            capacity=1
        ),
        Task(
            title="Poster design for club",
            price=50.0,
            description="Need a simple A4 poster design",
            category="Design",
            status="Completed",
            user="Sarah",
            rating=4.8,
            urgent=True,
            deadline="18 Apr 2026",
            capacity=1
        ),
    ]

    db.session.add_all(sample_tasks)
    db.session.commit()
    return redirect(url_for('dashboard'))


@app.route('/clear-earnings')
def clear_earnings():
    Earning.query.delete()
    db.session.commit()
    return redirect(url_for('earnings'))


@app.route('/clear-reviews')
def clear_reviews():
    Review.query.delete()
    db.session.commit()
    return redirect(url_for('dashboard'))


@app.route('/clear-tracking')
def clear_tracking():
    TaskTracking.query.delete()
    db.session.commit()
    return redirect(url_for('dashboard'))


@app.route('/view-db')
def view_db():
    tasks = Task.query.all()
    earnings = Earning.query.all()
    reviews = Review.query.all()
    tracking_list = TaskTracking.query.all()

    return render_template(
        'view_db.html',
        tasks=tasks,
        earnings=earnings,
        reviews=reviews,
        tracking_list=tracking_list
    )


# LOGOUT
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


# =========================
# RUN
# =========================
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


@socketio.on('join')
def on_join(data):
    room = data['room']
    join_room(room)
    print(f"用户进入了房间: {room}")

@socketio.on('send_message')
def handle_send_message(data):
    room = data['room']
    # 发送消息给同一个房间（room）里的所有人
    emit('receive_message', data, room=room)



if __name__ == '__main__':
    # 这样写
    socketio.run(app, debug=True, port=8000)