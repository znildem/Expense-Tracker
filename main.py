from flask import Flask, render_template, redirect, url_for, request, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash

# Import this at the top
from datetime import datetime

import matplotlib.pyplot as plt
import seaborn as sns
import io
import base64
from collections import defaultdict
import os

app = Flask(__name__)

# SQLite Database
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///./users.db'

# Required for session security
app.config['SECRET_KEY'] = 'your_secret_key'

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)

# Redirects unauthorized users to login page
login_manager.login_view = "login"

# User model
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key = True)
    username = db.Column(db.String(150), unique = True, nullable = False)
    password = db.Column(db.String(150), nullable = False)

# Adding the Expense class below the user model
class Expense(db.Model):
    id = db.Column(db.Integer, primary_key = True)

    # Link expense to the user
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable = False) 

    amount = db.Column(db.Float, nullable = False)
    category = db.Column(db.String(50), nullable = False)
    description = db.Column(db.String(150), nullable = False)

    # Auto set the date
    date = db.Column(db.String(10), nullable =False)

    # Relationship with User
    user = db.relationship('User', backref = db.backref('expenses', lazy = True))

# --- User Loader ---
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- Routes ---
@app.route('/add_expense', methods = ['POST'])
@login_required
def add_expense():
    try:
        description = request.form['description']
        amount = float(request.form['amount'])
        date = request.form['date']
        category = request.form['category']
            
        new_expense = Expense (
            user_id = current_user.id,
            amount = amount,
            category = category,
            description = description,
            date = date
        )
        db.session.add(new_expense)
        db.session.commit()

        flash("Expense added successfully!", "success")
        return redirect(url_for('dashboard')) 
    except Exception as e: print(f"Error adding expense: {e}")
    print(f"Error adding expense: {e}")
    return "Something went wrong", 400

@app.route('/delete_expense/<int:expense_id>')
@login_required
def delete_expense(expense_id):
    expense = Expense.query.filter_by(id = expense_id, user_id = current_user.id).first()
    if expense:
        db.session.delete(expense)
        db.session.commit()
        flash("Expense deleted.", "info")
    return redirect(url_for('dashboard'))

@app.route('/expense_chart')
@login_required
def expense_chart():
    expenses = Expense.query.filter_by(user_id = current_user.id).all()

    if not expenses:
        flash("No expenses to display.", "warning")
        return redirect(url_for('dashboard'))
    
    # Extract data
    categories = [expense.category for expense in expenses]
    amounts = [expense.amount for expense in expenses]

    # Create a Pie Chart
    plt.figure(figsize = (6, 6))
    sns.set_style("whitegrid")
    plt.pie(amounts, labels = categories, autopct = '%1.1f%%', startangle = 140, colors = sns.color_palette("pastel"))
    plt.title(f"Expense Breakdown for {current_user.username}")

    # Save the plot to a BytesIO object
    img = io.BytesIO()
    plt.savefig(img, format = 'png')
    img.seek(0)
    plot_url = base64.b64encode(img.getvalue()).decode()

    dates = [e.date.strftime('%Y-%m-%d') for e in expenses]
    plt.figure(figsize = (8, 5))
    sns.barplot(x = dates, y = amounts, palette = "viridis")
    plt.xticks(rotation = 45)
    plt.title("Expenses Ove Time")
    bar_img = io.BytesIO()
    plt.savefig(bar_img, format = 'png')
    bar_img.seek(0)
    bar_chart_url = base64.b64encode(bar_img.getvalue()).decode()

    return render_template('expense_chart.html', plot_url = plot_url, bar_chart_url = bar_chart_url)

@app.route('/monthly_summary')
@login_required
def monthly_summary():
    expenses = Expense.query.filter_by(user_id = current_user.id).all()
    if not expenses:
        flash("No data to summarize.", "warning")
        return redirect(url_for('dashboard'))
    
    monthly_totals = defaultdict(float)
    for e in expenses:
        key = e.date.strftime('%Y-%m')
        monthly_totals[key] += e.amount

    months = sorted(monthly_totals)
    totals = [monthly_totals[month] for month in months]

    plt.figure(figsize = (8, 5))
    sns.barplot(x = months, y = totals, palette = "Blues_d")
    plt.xticks(rotation = 45)
    plt.title("Monthly Expenses Summary")
    plt.xlabel("Month")
    plt.ylabel("Total Spent")
    img = io.BytesIO()
    plt.savefig(img, format = 'png')
    img.seek(0)
    chart_url = base64.b64encode(img.getvalue()).decode()

    return render_template('monthly_summary.html', chart_url = chart_url)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
def home():
    # Redirects the homepage to the login page
    return redirect(url_for('login'))

# Allows users to create an account with hashed passwords
@app.route('/register', methods = ['GET', 'POST'])
def register():
    if request.method == 'POST':
        if 'username' not in request.form or 'password' not in request.form:
            flash("Invalid form submission.", "danger")
            return redirect(url_for('register'))

        # Make sure this matches the form filed
        username = request.form['username']

        password = request.form['password']
        hashed_password = generate_password_hash(password, method = 'pbkdf2:sha256')

        # Check if username already exists
        existing_user = User.query.filter_by(username = username).first()
        if existing_user:
            flash("Username already exists. Choose a different one.", "danger")
            return redirect(url_for('register'))
        
        new_user = User(username = username, password = hashed_password)
        db.session.add(new_user)
        db.session.commit()
        flash("Account created successfully! Please log in.", "success")
        return redirect(url_for('login'))
    
    return render_template('register.html')

# Lets users log in securely
@app.route('/login', methods = ['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username =username).first()

        if user and check_password_hash(user.password, password):
            login_user(user)
            flash("Login successful!", "success")
            return redirect(url_for('dashboard'))
        else:
            flash("Invalid credentials. Try again.", "danger")
    return render_template('login.html')

# A protected page that requires login
@app.route('/dashboard')
@login_required
def dashboard():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    category = request.args.get('category')

    expenses_query = Expense.query.filter_by(user_id = current_user.id)
    if start_date:
        expenses_query = expenses_query.filter(Expense.date >= start_date)
    if end_date:
        expenses_query = expenses_query.filter(Expense.date <= end_date)
    if category:
        expenses_query = expenses_query.filter_by(category = category)

    expenses = expenses_query.order_by(Expense.date.desc()).all()
    return render_template('dashboard.html', username = current_user.username)

# Logs out users
@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for('login'))

if __name__ == '__main__':
    with app.app_context():
        if not os.path.exists('users.db'):
            # Create database tables
            db.create_all()
    app.run(debug = True, host = '0.0.0.0')