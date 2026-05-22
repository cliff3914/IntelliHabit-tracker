import os
from flask import Flask, render_template, redirect, url_for, flash, request
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import threading
import time
import schedule

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-key-change-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///habits.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Database Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Habit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(200))
    frequency = db.Column(db.String(20))
    reminder_time = db.Column(db.String(10))
    streak = db.Column(db.Integer, default=0)
    target_streak = db.Column(db.Integer, default=30)
    last_completed = db.Column(db.DateTime)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        if user:
            flash('Username already exists')
            return redirect(url_for('register'))
        
        new_user = User(username=username, email=email)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        
        flash('Registration successful! Please login.')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            flash('Login successful!')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out')
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    habits = Habit.query.filter_by(user_id=current_user.id).all()
    
    stats = {
        'total': len(habits),
        'completed_today': 0,
        'avg_streak': 0,
        'longest_streak': 0
    }
    
    return render_template('dashboard.html', habits=habits, stats=stats)

@app.route('/add_habit', methods=['GET', 'POST'])
@login_required
def add_habit():
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        frequency = request.form.get('frequency')
        reminder_time = request.form.get('reminder_time')
        target_streak = request.form.get('target_streak', 30)
        
        habit = Habit(
            name=name,
            description=description,
            frequency=frequency,
            reminder_time=reminder_time,
            target_streak=int(target_streak),
            user_id=current_user.id
        )
        
        db.session.add(habit)
        db.session.commit()
        
        flash('Habit added successfully!')
        return redirect(url_for('dashboard'))
    
    return render_template('add_habit.html')

@app.route('/complete_habit/<int:habit_id>', methods=['GET', 'POST'])
@login_required
def complete_habit(habit_id):
    habit = Habit.query.get_or_404(habit_id)
    
    if habit.user_id != current_user.id:
        flash('Unauthorized access')
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        today = datetime.utcnow().date()
        last_completed = habit.last_completed.date() if habit.last_completed else None
        
        if last_completed == today - timedelta(days=1):
            habit.streak += 1
        elif last_completed != today:
            habit.streak = 1
        
        habit.last_completed = datetime.utcnow()
        db.session.commit()
        
        flash(f'Great job! You completed {habit.name}!')
        return redirect(url_for('dashboard'))
    
    return render_template('complete_habit.html', habit=habit)

@app.route('/test-email')
@login_required
def test_email():
    from flask_mail import Message
    msg = Message('Test Email',
                  recipients=[current_user.email],
                  body='This is a test!')
    mail.send(msg)
    return 'Email sent! Check your inbox.'

# Create tables
with app.app_context():
    db.create_all()
    
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
