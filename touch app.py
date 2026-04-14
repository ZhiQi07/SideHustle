from flask import Flask, render_template

app = Flask(__name__)

@app.route('/')
def dashboard():
    return render_template('dashboard.html')

@app.route('/rating')
def rating():
    return render_template('rating.html')

@app.route('/earnings')
def earnings():
    return render_template('earnings.html')

@app.route('/messages')
def messages():
    return render_template('messages.html')

if __name__ == '__main__':
    app.run(debug=True)