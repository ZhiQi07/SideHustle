from flask import Flask, render_template, request, redirect, url_for

app = Flask(__name__)

# This is a temporary list to store tasks until we set up the database
# We call this "Mock Data"
tasks = [
    {'title': 'Pet Sitting', 'price': 20, 'description': 'Watch my cat for 2 hours'},
    {'title': 'Python Tutoring', 'price': 50, 'description': 'Help with basic loops'}
]

@app.route('/')
def marketplace():
    # This sends our list of tasks to the marketplace.html page
    return render_template('marketplace.html', tasks=tasks)

@app.route('/post', methods=['GET', 'POST'])
def post_task():
    if request.method == 'POST':
        # This part catches the data from your HTML form
        title = request.form.get('title')
        price = request.form.get('price')
        desc = request.form.get('description')
        cat = request.form.get('category') # NEW
        
        # Add everything to our list
        tasks.append({'title': title, 'price': price, 'description': desc, 'category': cat})
        
        return redirect(url_for('marketplace'))
    
    return render_template('post_task.html')

if __name__ == '__main__':
    app.run(debug=True)