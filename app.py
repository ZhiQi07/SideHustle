from flask import Flask, render_template
import sqlite3

app = Flask(__name__)

def init_db():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        percent INTEGER NOT NULL,
        due_date TEXT NOT NULL
    )
    """)

    conn.commit()
    conn.close()

def insert_sample_data():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM tasks")
    count = cursor.fetchone()[0]

    if count == 0:
        cursor.execute("""
        INSERT INTO tasks (title, percent, due_date)
        VALUES (?, ?, ?)
        """, ("Arrange table in room C-206", 67, "20 Apr 2026"))

        cursor.execute("""
        INSERT INTO tasks (title, percent, due_date)
        VALUES (?, ?, ?)
        """, ("Task name / information", 76, "25 Apr 2026"))

    conn.commit()
    conn.close()

@app.route("/")
def dashboard():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM tasks")
    tasks = cursor.fetchall()

    conn.close()

    return render_template("dashboard.html", tasks=tasks)

@app.route("/earnings")
def earnings():
    return render_template("earnings.html")

@app.route("/task-tracking")
def task_tracking():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM tasks")
    tasks = cursor.fetchall()

    conn.close()

    return render_template("task_tracking.html", tasks=tasks)

init_db()
insert_sample_data()

if __name__ == "__main__":
    app.run(debug=True)