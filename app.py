from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import requests
from datetime import date
from dotenv import load_dotenv
load_dotenv()
import os

app = Flask(__name__)

# Configurations
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///project.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Secret key for werkzeug security
# Make sure secret key is not directly in the code
app.secret_key = os.getenv('SECRET_KEY',os.urandom(24))

# User database model
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(25), nullable=False)
    second_name = db.Column(db.String(25), nullable=True)
    last_name = db.Column(db.String(50), nullable=False)
    username = db.Column(db.String(50), unique=True, nullable=False)
    hashed_password = db.Column(db.String(150), nullable=False)

    def set_password(self, password):
        self.hashed_password = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.hashed_password, password)

# Model for storing quote history
class QuoteHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    quote_text = db.Column(db.String(500), nullable=False)
    author = db.Column(db.String(100), nullable=False)
    date_retrieved = db.Column(db.Date, default=date.today)
    
# Welcome page
# For login
@app.route('/')
def welcome():
    #if 'username' in session:
    #    return redirect(url_for('home'))
    return render_template('welcome.html')

@app.route('/login', methods=['POST'])
def login():
    
    # Collecting infromation from form
    username = request.form.get('username').strip()
    password = request.form.get('password').strip()

    # Ensuring both username and password is given
    if not username or not password:
        return render_template('welcome.html', error="Please fill in all fields.")
    
    else:
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            session['username'] = username
            return redirect(url_for('home'))
        return render_template('welcome.html', error="Invalid username or password.")

@app.route('/register', methods=['GET', 'POST'])
def register():
    
    if request.method == 'POST':
        # Collecting information from form
        first_name = request.form.get('first_name').strip()
        second_name = request.form.get('second_name').strip()
        last_name = request.form.get('last_name').strip()
        username = request.form.get('username').strip()
        password = request.form.get('password').strip()
        confirm_password = request.form.get('confirm_password').strip()

        # Ensuring all fields are filled
        if not first_name or not last_name or not username or not password or not confirm_password:
            return render_template('register.html', error="Please fill in all required fields.")
        
        # Ensuring password and confirm password match
        if confirm_password != password:
            return render_template('register.html', error="Passwords do not match.")
        
        # Ensuring username is unique
        user = User.query.filter_by(username=username).first()
        if user:
            return render_template('register.html', error="Username already exists. Please choose another.")
        else:
            # Creating new user
            new_user = User(
                first_name=first_name,
                second_name=second_name,
                last_name=last_name,
                username=username
            )
            new_user.set_password(password)
            db.session.add(new_user)
            db.session.commit()

            session['username'] = username
            return redirect(url_for('home'))
        
    # otherwise stay on register page
    return render_template('register.html')

@app.route('/home')
def home():
    # Check if user is logged in
    if 'username' not in session:
        return redirect(url_for('welcome'))

    current_user = User.query.filter_by(username=session['username']).first()
    today = date.today()

    # Check database: Does the user ALREADY have a quote for today?
    todays_quote = QuoteHistory.query.filter_by(user_id=current_user.id, date_retrieved=today).first()

    quote_text = None
    quote_author = None
    show_placeholder = False

    if todays_quote:
       #Quote exists in DB. Display the stored quote.
        quote_text = todays_quote.quote_text
        quote_author = todays_quote.author
        show_placeholder = False
    else:
        #No quote yet. Show the "Get Quote" placeholder/button instead of calling API.
        show_placeholder = True

    return render_template('home.html',
                           username=session['username'],
                           quote=quote_text,
                           author=quote_author,
                           show_placeholder=show_placeholder) # New variable to control the view

@app.route('/get_new_quote')
def get_new_quote():
    # This route is triggered ONLY when the user clicks the button
    if 'username' not in session:
        return redirect(url_for('welcome'))

    current_user = User.query.filter_by(username=session['username']).first()
    today = date.today()

    # Double-check: verify if they already have a quote
    existing_quote = QuoteHistory.query.filter_by(user_id=current_user.id, date_retrieved=today).first()

    if existing_quote:
        # If they already have one, flash the message and go back home
        flash("You have already received your daily quote. Please come back tomorrow!", "warning")
        return redirect(url_for('home'))

    #API CALL
    raw_api_key = 'FfqJBEMq9YNA6e45YqVXTA==GymCyiqMwoOUtgAy'
    api_key = raw_api_key.strip()
    api_url = 'https://api.api-ninjas.com/v1/quotes'

    try:
        # Fetch data from the external API
        response = requests.get(api_url, headers={'X-Api-Key': api_key})
        if response.status_code == requests.codes.ok:
            data = response.json()
            if len(data) > 0:
                quote_text = data[0]['quote']
                quote_author = data[0]['author']

                # Save to Database
                new_history = QuoteHistory(
                    user_id=current_user.id,
                    quote_text=quote_text,
                    author=quote_author,
                    date_retrieved=today
                )
                db.session.add(new_history)
                db.session.commit()

        else:
            flash("Error connecting to the quote service.", "danger")
            print(f"API Error: {response.status_code}")

    except Exception as e:
        flash("System error occurred.", "danger")
        print(f"Critical error: {e}")

    return redirect(url_for('home'))


@app.route('/previous_quotes')
def previous_quotes():
    if 'username' not in session:
        return redirect(url_for('welcome'))

    current_user = User.query.filter_by(username=session['username']).first()

    #history for current user, ordered by date
    history = QuoteHistory.query.filter_by(user_id=current_user.id).order_by(QuoteHistory.date_retrieved.desc()).all()

    return render_template('previous_quotes.html', history=history)

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('welcome'))

if __name__=='__main__':
    with app.app_context():
        db.create_all()

    app.run(debug=True)