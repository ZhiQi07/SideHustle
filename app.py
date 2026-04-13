from flask import Flask, render_template, request, redirect, url_for

app = Flask(__name__)

# Updated mock data to include the new fields
tasks = [
    {
        'id': 1, 'title': 'Moving Hostel Luggage', 'price': 20, 
        'description': 'Need help moving 3 boxes from HB4 to HB1.', 
        'category': 'Moving & Lifting', 'status': 'Available',
        'deadline': '2026-04-20', 'capacity': 2, 'urgent': True,
        'user': 'Ali', 'rating': 4.9
    }
]

@app.route('/')
def marketplace():
    return render_template('marketplace.html', tasks=tasks)

@app.route('/post', methods=['GET', 'POST'])
def post_task():
    if request.method == 'POST':
        # Capturing the new fields from the form
        new_task = {
            'id': len(tasks) + 1,
            'title': request.form.get('title'),
            'price': request.form.get('price'),
            'description': request.form.get('description'),
            'category': request.form.get('category'),
            'deadline': request.form.get('deadline'),
            'capacity': request.form.get('capacity'),
            'urgent': True if request.form.get('urgent') else False,
            'status': 'Available',
            'user': 'Student_User',
            'rating': 5.0
        }
        tasks.append(new_task)
        return redirect(url_for('marketplace'))
    return render_template('post_task.html')

@app.route('/task/<int:task_id>')
def task_detail(task_id):
    task = next((t for t in tasks if t['id'] == task_id), None)
    return render_template('task_detail.html', task=task)

@app.route('/apply/<int:task_id>', methods=['GET', 'POST'])
def apply(task_id):
    task = next((t for t in tasks if t['id'] == task_id), None)
    if request.method == 'POST':
        return redirect(url_for('marketplace'))
    return render_template('apply.html', task=task)

if __name__ == '__main__':
    app.run(debug=True)