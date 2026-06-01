import os
from flask import Flask, render_template, redirect, url_for, flash, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_mail import Mail, Message
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import threading
import time
import schedule

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-key-change-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///habits.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Mail configuration
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_USERNAME')

mail = Mail(app)
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Database Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256))
    phone_number = db.Column(db.String(20))
    email_notifications = db.Column(db.Boolean, default=True)
    sms_notifications = db.Column(db.Boolean, default=False)
    
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
    target_value = db.Column(db.Float, default=1.0)
    current_value = db.Column(db.Float, default=0.0)
    unit = db.Column(db.String(50), default='times')
    reminder_type = db.Column(db.String(20), default='time')
    reminder_location = db.Column(db.String(200))
    reminder_time_range = db.Column(db.String(50))
    reminder_message = db.Column(db.String(500), default="Time to complete your habit!")
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
class HabitCompletion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    habit_id = db.Column(db.Integer, db.ForeignKey('habit.id'), nullable=False)
    completed_date = db.Column(db.DateTime, default=datetime.utcnow)
    notes = db.Column(db.String(200))
    mood = db.Column(db.Integer)

class PushSubscription(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    endpoint = db.Column(db.String(500), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
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
        
        user = User.query.filter_by(email=email).first()
        if user:
            flash('Email already registered')
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
    total_habits = len(habits)
    completed_today = sum(1 for h in habits if h.last_completed and h.last_completed.date() == datetime.utcnow().date())
    
    stats = {
        'total': total_habits,
        'completed_today': completed_today,
        'avg_streak': round(sum(h.streak for h in habits) / total_habits, 1) if total_habits > 0 else 0,
        'longest_streak': max([h.streak for h in habits], default=0)
    }
    
    return render_template('dashboard.html', habits=habits, stats=stats, now=datetime.utcnow())

@app.route('/add_habit', methods=['GET', 'POST'])
@login_required
def add_habit():
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        frequency = request.form.get('frequency')
        reminder_time = request.form.get('reminder_time')
        target_streak = request.form.get('target_streak', 30)
        habit_type = request.form.get('habit_type', 'boolean')
        
        habit = Habit(
            name=name,
            description=description,
            frequency=frequency,
            reminder_time=reminder_time,
            target_streak=int(target_streak),
            user_id=current_user.id
        )
        
        if habit_type == 'progress':
            habit.target_value = float(request.form.get('target_value', 1))
            habit.unit = request.form.get('unit', 'times')
            habit.current_value = 0
        
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
        
        if habit.target_value and habit.target_value > 0:
            progress_value = float(request.form.get('progress_value', 0))
            habit.current_value = min(habit.current_value + progress_value, habit.target_value)
            
            if habit.current_value >= habit.target_value:
                habit.current_value = 0
                habit.last_completed = datetime.utcnow()
                if last_completed == today - timedelta(days=1):
                    habit.streak += 1
                else:
                    habit.streak = 1
                flash(f' Target reached! {habit.streak} day streak!')
            else:
                flash(f'Progress: {habit.current_value}/{habit.target_value} {habit.unit}')
                db.session.commit()
                return redirect(url_for('dashboard'))
        else:
            if last_completed == today:
                flash('Already completed today!')
                return redirect(url_for('dashboard'))
            
            habit.last_completed = datetime.utcnow()
            if last_completed == today - timedelta(days=1):
                habit.streak += 1
            else:
                habit.streak = 1
            flash(f'Great job! {habit.streak} day streak!')
        
        db.session.commit()
        return redirect(url_for('dashboard'))
    
    return render_template('complete_habit.html', habit=habit)

@app.route('/test-email')
@login_required
def test_email():
    try:
        msg = Message('Test Email',
                      recipients=[current_user.email],
                      body='This is a test email from IntelliHabit Tracker!')
        mail.send(msg)
        flash('Test email sent! Check your inbox.')
    except Exception as e:
        flash(f'Error sending email: {str(e)}')
    return redirect(url_for('dashboard'))

@app.route('/send-reminders')
def send_reminders():
    current_time = datetime.now().strftime("%H:%M")
    habits = Habit.query.filter_by(reminder_time=current_time).all()
    
    count = 0
    for habit in habits:
        user = User.query.get(habit.user_id)
        if user and user.email_notifications:
            try:
                msg = Message(
                    f'Reminder: {habit.name}',
                    recipients=[user.email],
                    body=f"Hi {user.username},\n\nIt's time to complete your habit: {habit.name}\n\nKeep up the great work!"
                )
                mail.send(msg)
                count += 1
            except Exception as e:
                print(f"Error sending to {user.email}: {e}")
    
    return f"Sent {count} reminder emails at {current_time}"

@app.route('/test-reminder')
@login_required
def test_reminder():
    try:
        msg = Message(
            'Test Reminder',
            recipients=[current_user.email],
            body=f"Hi {current_user.username},\n\nThis is a test reminder. Your habit reminders will work like this!"
        )
        mail.send(msg)
        flash('Test reminder sent! Check your email.')
    except Exception as e:
        flash(f'Error sending reminder: {str(e)}')
    return redirect(url_for('dashboard'))

@app.route('/motivation')
@login_required
def motivation():
    return render_template('motivation.html')

@app.route('/timer')
@login_required
def timer():
    return render_template('timer.html')

@app.route('/report')
@login_required
def report():
    habits = Habit.query.filter_by(user_id=current_user.id).all()
    return render_template('report.html', habits=habits)

@app.route('/reminders')
@login_required
def reminders():
    habits = Habit.query.filter_by(user_id=current_user.id).all()
    return render_template('reminders.html', habits=habits)

@app.route('/profile')
@login_required
def profile():
    habits = Habit.query.filter_by(user_id=current_user.id).all()
    total_habits = len(habits)
    total_streak = sum(h.streak for h in habits)
    completed_today = sum(1 for h in habits if h.last_completed and h.last_completed.date() == datetime.utcnow().date())
    
    return render_template('profile.html', 
                         total_habits=total_habits, 
                         total_streak=total_streak, 
                         completed_today=completed_today)
    
@app.route('/widgets')
@login_required
def widgets():
    habits = Habit.query.filter_by(user_id=current_user.id).all()
    total_habits = len(habits)
    total_streak = sum(h.streak for h in habits)
    completed_today = sum(1 for h in habits if h.last_completed and h.last_completed.date() == datetime.utcnow().date())
    
    return render_template('widgets.html', 
                         habits=habits, 
                         total_habits=total_habits, 
                         total_streak=total_streak, 
                         completed_today=completed_today,
                         now=datetime.utcnow())
    
@app.route('/calendar')
@login_required
def calendar():
    return render_template('calendar.html', now=datetime.utcnow())

@app.route('/get_calendar_data')
@login_required
def get_calendar_data():
    habits = Habit.query.filter_by(user_id=current_user.id).all()
    completion_data = {}
    
    end_date = datetime.utcnow().date()
    start_date = end_date - timedelta(days=90)
    
    for habit in habits:
        completions = HabitCompletion.query.filter(
            HabitCompletion.habit_id == habit.id,
            HabitCompletion.completed_date >= start_date
        ).all()
        
        for comp in completions:
            date_str = comp.completed_date.strftime('%Y-%m-%d')
            if date_str not in completion_data:
                completion_data[date_str] = 0
            completion_data[date_str] += 1
    
    result = {}
    total_habits = len(habits)
    for date_str, completed_count in completion_data.items():
        if completed_count == total_habits:
            result[date_str] = 'completed'
        elif completed_count > 0:
            result[date_str] = 'partial'
        else:
            result[date_str] = 'missed'
    
    return jsonify(result)

@app.route('/get_day_habits')
@login_required
def get_day_habits():
    date_str = request.args.get('date')
    target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    
    habits = Habit.query.filter_by(user_id=current_user.id).all()
    result = []
    
    for habit in habits:
        completion = HabitCompletion.query.filter(
            HabitCompletion.habit_id == habit.id,
            HabitCompletion.completed_date >= target_date,
            HabitCompletion.completed_date < target_date + timedelta(days=1)
        ).first()
        
        if completion:
            result.append({'name': habit.name, 'status': 'completed'})
        else:
            result.append({'name': habit.name, 'status': 'missed'})
    
    return jsonify(result)

@app.route('/update_reminder_settings', methods=['POST'])
@login_required
def update_reminder_settings():
    data = request.get_json()
    habit_id = data.get('habit_id')
    habit = Habit.query.get_or_404(habit_id)
    
    if habit.user_id != current_user.id:
        return jsonify({'success': False, 'error': 'Unauthorized'})
    
    if 'time_range' in data:
        habit.reminder_time_range = data['time_range']
    if 'reminder_time' in data:
        habit.reminder_time = data['reminder_time']
    if 'reminder_type' in data:
        habit.reminder_type = data['reminder_type']
    if 'reminder_location' in data:
        habit.reminder_location = data['reminder_location']
    if 'reminder_message' in data:
        habit.reminder_message = data['reminder_message']
    
    db.session.commit()
    return jsonify({'success': True})

@app.route('/save_subscription', methods=['POST'])
@login_required
def save_subscription():
    data = request.get_json()
    
    existing = PushSubscription.query.filter_by(
        user_id=current_user.id,
        endpoint=data.get('endpoint')
    ).first()
    
    if not existing:
        subscription = PushSubscription(
            user_id=current_user.id,
            endpoint=data.get('endpoint')
        )
        db.session.add(subscription)
        db.session.commit()
    
    return {'status': 'success'}

@app.route('/test_notification')
@login_required
def test_notification():
    return render_template('test_notification.html')

@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    if request.method == 'POST':
        current_user.email_notifications = 'email_notifications' in request.form
        current_user.sms_notifications = 'sms_notifications' in request.form
        current_user.phone_number = request.form.get('phone_number')
        db.session.commit()
        flash('Settings updated successfully!')
        return redirect(url_for('settings'))
    
    return render_template('settings.html')

# Create tables
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)