from flask import Flask, render_template, redirect, url_for, flash, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_mail import Mail, Message
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import threading
import time
import schedule
from plyer import notification
import json
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import io
import base64
from twilio.rest import Client
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-change-this-production'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///habits.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Email Configuration
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'your-email@gmail.com'  # Replace with your email
# Replace with app password
app.config['MAIL_PASSWORD'] = 'your-app-password'
app.config['MAIL_DEFAULT_SENDER'] = 'your-email@gmail.com'

# Twilio Configuration for SMS/WhatsApp
TWILIO_ACCOUNT_SID = 'your-twilio-account-sid'  # Get from Twilio console
TWILIO_AUTH_TOKEN = 'your-twilio-auth-token'    # Get from Twilio console
TWILIO_PHONE_NUMBER = '+1234567890'             # Your Twilio phone number

mail = Mail(app)

# Initialize Twilio client if credentials are provided
twilio_client = None
if TWILIO_ACCOUNT_SID != 'your-twilio-account-sid':
    twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Database Models


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone_number = db.Column(db.String(20))  # For SMS notifications
    password_hash = db.Column(db.String(128))
    email_notifications = db.Column(db.Boolean, default=True)
    sms_notifications = db.Column(db.Boolean, default=False)
    habits = db.relationship('Habit', backref='user', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Habit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(200))
    frequency = db.Column(db.String(20))  # daily, weekly, monthly
    reminder_time = db.Column(db.String(10))  # HH:MM format
    reminder_method = db.Column(db.String(50))  # email, sms, desktop, all
    streak = db.Column(db.Integer, default=0)
    target_streak = db.Column(db.Integer, default=30)  # Goal streak
    last_completed = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    completions = db.relationship(
        'HabitCompletion', backref='habit', lazy=True)


class HabitCompletion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    habit_id = db.Column(db.Integer, db.ForeignKey('habit.id'), nullable=False)
    completed_date = db.Column(db.DateTime, default=datetime.utcnow)
    notes = db.Column(db.String(200))
    mood = db.Column(db.Integer)  # 1-5 mood rating


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Helper Functions for Notifications


def send_email_reminder(user_email, habit_name, reminder_time):
    """Send email reminder for habit"""
    try:
        msg = Message(
            f'Habit Reminder: {habit_name}',
            recipients=[user_email]
        )
        msg.body = f"""
        Hello!

        This is a reminder to complete your habit: {habit_name}

        Reminder Time: {reminder_time}

        Keep up the great work! Every small step counts towards your goals.

        Best regards,
        IntelliHabit Tracker Team
        """
        mail.send(msg)
        print(f"Email reminder sent to {user_email} for {habit_name}")
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False


def send_sms_reminder(phone_number, habit_name):
    """Send SMS reminder using Twilio"""
    if not twilio_client or not phone_number:
        return False

    try:
        _ = twilio_client.messages.create(
            body=f"🌟 Habit Reminder: Time to complete '{habit_name}'! Stay consistent! 💪",
            from_=TWILIO_PHONE_NUMBER,
            to=phone_number
        )
        print(f"SMS sent to {phone_number} for {habit_name}")
        return True
    except Exception as e:
        print(f"Error sending SMS: {e}")
        return False


def send_whatsapp_reminder(phone_number, habit_name):
    """Send WhatsApp reminder using Twilio"""
    if not twilio_client or not phone_number:
        return False

    try:
        Message = twilio_client.messages.create(
            body=f"🎯 *Habit Reminder* 🎯\n\nTime to complete: *{habit_name}*\n\nYou've got this! 💪✨",
            from_=f'whatsapp:{TWILIO_PHONE_NUMBER}',
            to=f'whatsapp:{phone_number}'
        )
        print(f"WhatsApp message sent to {phone_number}")
        return True
    except Exception as e:
        print(f"Error sending WhatsApp: {e}")
        return False


def send_desktop_notification(habit_name):
    """Send desktop notification"""
    try:
        notification.notify(
            title='IntelliHabit Reminder',
            message=f'Time to work on: {habit_name}!',
            app_name='IntelliHabit Tracker',
            timeout=10
        )
        return True
    except Exception as e:
        print(f"Error sending desktop notification: {e}")
        return False


def send_habit_reminder(habit_id, habit_name, user_id, reminder_time):
    """Send reminders based on user preferences"""
    with app.app_context():
        user = User.query.get(user_id)
        habit = Habit.query.get(habit_id)

        if not user or not habit:
            return

        # Send email reminder
        if user.email_notifications and habit.reminder_method in ['email', 'all']:
            send_email_reminder(user.email, habit_name, reminder_time)

        # Send SMS/WhatsApp reminder
        if user.sms_notifications and user.phone_number and habit.reminder_method in ['sms', 'all']:
            send_sms_reminder(user.phone_number, habit_name)
            if 'whatsapp' in habit.reminder_method:
                send_whatsapp_reminder(user.phone_number, habit_name)

        # Send desktop notification
        if habit.reminder_method in ['desktop', 'all']:
            send_desktop_notification(habit_name)


def schedule_reminder(habit_id, habit_name, reminder_time, user_id):
    """Schedule a reminder for a habit"""
    schedule.every().day.at(reminder_time).do(
        send_habit_reminder, habit_id, habit_name, user_id, reminder_time
    )

# Chart Generation Functions


def generate_habit_chart(habit_id):
    """Generate matplotlib chart for habit progress"""
    habit = Habit.query.get(habit_id)
    completions = HabitCompletion.query.filter_by(habit_id=habit_id).all()

    # Prepare data
    dates = []
    moods = []
    for completion in completions[-30:]:  # Last 30 days
        dates.append(completion.completed_date.date())
        moods.append(completion.mood if completion.mood else 3)

    if not dates:
        return None

    # Create figure
    plt.figure(figsize=(10, 6))
    sns.set_style("darkgrid")

    # Plot completion trend
    plt.subplot(2, 1, 1)
    plt.plot(dates, range(len(dates)), marker='o', linewidth=2, markersize=6)
    plt.title(f'{habit.name} - Completion Trend')
    plt.xlabel('Date')
    plt.ylabel('Completions')
    plt.xticks(rotation=45)

    # Plot mood trend
    if moods:
        plt.subplot(2, 1, 2)
        plt.bar(dates, moods, alpha=0.7, color='skyblue')
        plt.title('Mood Trend (1=Bad, 5=Great)')
        plt.xlabel('Date')
        plt.ylabel('Mood Rating')
        plt.ylim(0, 6)
        plt.xticks(rotation=45)

    plt.tight_layout()

    # Save to base64 string
    img = io.BytesIO()
    plt.savefig(img, format='png', dpi=100)
    img.seek(0)
    plot_url = base64.b64encode(img.getvalue()).decode()
    plt.close()

    return plot_url

# Routes


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        phone_number = request.form.get('phone_number')
        password = request.form.get('password')

        user = User.query.filter_by(username=username).first()
        if user:
            flash('Username already exists')
            return redirect(url_for('register'))

        user = User.query.filter_by(email=email).first()
        if user:
            flash('Email already registered')
            return redirect(url_for('register'))

        new_user = User(
            username=username,
            email=email,
            phone_number=phone_number if phone_number else None
        )
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

    # Calculate statistics
    total_habits = len(habits)
    completed_today = 0
    current_streaks = []
    completed_habits = []

    for habit in habits:
        today = datetime.utcnow().date()
        last_completed = habit.last_completed.date() if habit.last_completed else None

        if last_completed == today:
            completed_today += 1
            completed_habits.append(habit.name)
        if habit.streak > 0:
            current_streaks.append(habit.streak)

    avg_streak = sum(current_streaks) / \
                     len(current_streaks) if current_streaks else 0
    completion_rate = (completed_today / total_habits *
                       100) if total_habits > 0 else 0

    # Generate overall progress chart
    chart_data = []
    for i in range(7):
        date = datetime.utcnow().date() - timedelta(days=i)
        daily_completions = sum(
            1 for habit in habits if habit.last_completed and habit.last_completed.date() == date)
        chart_data.append({
            'date': date.strftime('%Y-%m-%d'),
            'completions': daily_completions
        })

    stats = {
        'total': total_habits,
        'completed_today': completed_today,
        'avg_streak': round(avg_streak, 1),
        'total_streaks': sum(current_streaks),
        'completion_rate': round(completion_rate, 1),
        'longest_streak': max(current_streaks) if current_streaks else 0
    }

    return render_template('dashboard.html',
                         habits=habits,
                         stats=stats,
                         chart_data=json.dumps(chart_data),
                         completed_habits=completed_habits)


@app.route('/add_habit', methods=['GET', 'POST'])
@login_required
def add_habit():
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        frequency = request.form.get('frequency')
        reminder_time = request.form.get('reminder_time')
        reminder_method = request.form.get('reminder_method')
        target_streak = request.form.get('target_streak', 30)

        habit = Habit(
            name=name,
            description=description,
            frequency=frequency,
            reminder_time=reminder_time,
            reminder_method=reminder_method,
            target_streak=int(target_streak),
            user_id=current_user.id
        )

        db.session.add(habit)
        db.session.commit()

        # Schedule reminder if time is set
        if reminder_time:
            schedule_reminder(habit.id, name, reminder_time, current_user.id)

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
        notes = request.form.get('notes')
        mood = request.form.get('mood')

        today = datetime.utcnow().date()
        last_completed = habit.last_completed.date() if habit.last_completed else None

        # Add completion record
        completion = HabitCompletion(
            habit_id=habit.id,
            notes=notes,
            mood=int(mood) if mood else None
        )
        db.session.add(completion)

        # Update streak
        if last_completed == today - timedelta(days=1):
            habit.streak += 1
        elif last_completed != today:
            habit.streak = 1

        habit.last_completed = datetime.utcnow()
        db.session.commit()

        # Check if achieved target streak
        if habit.streak >= habit.target_streak:
            flash(
                f'🎉 Amazing! You achieved your target streak of {habit.target_streak} days for {habit.name}! 🎉')
            # Send achievement notification
            send_email_reminder(current_user.email,
                                habit.name, "Achievement Unlocked!")

        flash(f'Great job! You completed {habit.name}!')
        return redirect(url_for('dashboard'))

    return render_template('complete_habit.html', habit=habit)


@app.route('/habit_analytics/<int:habit_id>')
@login_required
def habit_analytics(habit_id):
    habit = Habit.query.get_or_404(habit_id)

    if habit.user_id != current_user.id:
        flash('Unauthorized access')
        return redirect(url_for('dashboard'))
    # Generate chart
    chart_url = generate_habit_chart(habit_id)
    
    # Get completions data
    completions = HabitCompletion.query.filter_by(habit_id=habit_id).order_by(HabitCompletion.completed_date.desc()).all()
    
    # Calculate stats
    total_completions = len(completions)
    avg_mood = sum(c.mood for c in completions if c.mood) / len([c for c in completions if c.mood]) if completions else 0
    best_streak = habit.streak
    
    analytics = {
        'habit': habit,
        'total_completions': total_completions,
        'avg_mood': round(avg_mood, 1),
        'best_streak': best_streak,
        'completions': completions[:20],  # Last 20 completions
        'chart_url': chart_url
    }
    
    return render_template('habit_analytics.html', analytics=analytics)

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

# Reminder Scheduler Thread
def run_scheduler():
    while True:
        schedule.run_pending()
        time.sleep(1)

# Start scheduler thread
scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
scheduler_thread.start()

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, host='0.0.0.0', port=5000)


  