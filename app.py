from flask import Flask, redirect, url_for, session, request, render_template, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_session import Session
from Queries import AddUser
import msal
import requests
import os
import logging

# Initialize Flask app
app = Flask(__name__, template_folder='docs', static_folder='docs')
app.secret_key = "sWanRivEr"  # Required for session management

# Azure AD configuration
CLIENT_ID = "7fbeba40-e221-4797-8f8a-dc364de519c7"
CLIENT_SECRET = "x2T8Q~yVzAOoC~r6FYtzK6sqCJQR_~RCVH5-dcw8"
TENANT_ID = "170bbabd-a2f0-4c90-ad4b-0e8f0f0c4259"
AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"
REDIRECT_URI = 'https://swan-river-group-project.azurewebsites.net/auth/callback'
SCOPE = ['User.Read']

# Secure configuration settings
app.config['SESSION_TYPE'] = 'filesystem'  # Prevents session loss in Azure
app.config['SESSION_COOKIE_SECURE'] = True  # Forces HTTPS session cookies
app.config['SESSION_COOKIE_HTTPONLY'] = True  # Prevents JavaScript from accessing cookies
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # Allows cross-domain authentication

# Debugging: Print the database URL
database_url = os.getenv('DATABASE_URL')
if not database_url:
    logger.error("DATABASE_URL is not set. Ensure it is configured in Azure.")
else:
    logger.info(f"Database URL: {database_url}")  # Log it safely without credentials

# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize database and session
db = SQLAlchemy(app)
Session(app)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# User Model
class User(db.Model):
     id = db.Column(db.Integer, primary_key=True)
     name = db.Column(db.String(100), nullable=False)
     email = db.Column(db.String(100), unique=True, nullable=False)
     role = db.Column(db.String(50), default="basicuser")
     status = db.Column(db.String(20), default="active")

# Function to initialize database
# def setup_db():
#     with app.app_context():
#         db.create_all()

# Home page
@app.route('/')
def index():
    return render_template('index.html')

# Login page
@app.route('/login')
def login():
    return render_template('login.html')

# Initiate Microsoft 365 login
@app.route('/azure_login')
def azure_login():
    session['state'] = 'random_state'  # Use a random state for security
    auth_url = _build_auth_url(scopes=SCOPE, state=session['state'])
    print("Authorization URL:", auth_url)  # Debugging
    return redirect(auth_url)

# Callback route after Microsoft 365 login
@app.route('/auth/callback')
def authorized():
    try:
        token = _get_token_from_code(request.args.get('code'))
        if not token:
            return redirect(url_for('index'))

        user_info = _get_user_info(token)
        if not user_info:
            return redirect(url_for('index'))

        # Determine email and name
        user_email = user_info.get('mail') or user_info.get('userPrincipalName')
        user_name = user_info.get('displayName')

        # Query the database for an existing user
        user = User.query.filter_by(email=user_email).first()
        if not user:
            # Create a new user if not found
            user = User(name=user_name, email=user_email, role="basicuser", status="active")
            db.session.add(user)
            db.session.commit()

        # Store the user's details in session for later use
        session['user'] = {
            'displayName': user.name,
            'email': user.email,
            'role': user.role,
            'status': user.status
        }

        # Redirect based on role
        if 'admin' in user_info.get('roles', []):
            return redirect(url_for('admin_home'))
        else:
            return redirect(url_for('basic_user_home'))
    except Exception as e:
        print(f"Error in callback route: {e}")
        return redirect(url_for('index'))


# Admin home page
@app.route('/admin_home')
def admin_home():
    if not session.get('user') or 'admin' not in session['user'].get('roles', []):
        return redirect(url_for('index'))
    user_name = session['user']['displayName']
    return render_template('admin.html', user_name=user_name)

# Basic user home page
@app.route('/basic_user_home')
def basic_user_home():
    print("Basic user home route called")  # Debugging
    if not session.get('user'):
        return redirect(url_for('index'))
    user_name = session['user']['displayName']
    return render_template('basic_user_home.html', user_name=user_name)

# Retrieve user profile
@app.route('/user/profile', methods=['GET'])
def get_user_profile():
    if 'user' not in session:
        return jsonify({"error": "User not authenticated"}), 401

# Use the email from the session to fetch the user record from the database
    user_email = session['user']['email']
    user = User.query.filter_by(email=user_email).first()
    if not user:
        return jsonify({"error": "User not found"}), 404

    return jsonify({
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "status": user.status
    })

# New routes for basic user functionalities
@app.route('/basic_user_view')
def basic_user_view():
    if not session.get('user'):
        return redirect(url_for('index'))
    user_name = session['user']['displayName']
    return render_template('basic_user_view.html', user_name=user_name)

@app.route('/basic_user_edit')
def basic_user_edit():
    if not session.get('user'):
        return redirect(url_for('index'))
    user_name = session['user']['displayName']
    return render_template('basic_user_edit.html', user_name=user_name)

# Other routes for admin functionalities
@app.route('/admin-view-profile')
def admin_view_profile():
    if not session.get('user'):
        return redirect(url_for('index'))
    user_name = session['user']['displayName']
    return render_template('admin-view-profile.html', user_name=user_name)

@app.route('/admin-edit-profile')
def admin_edit_profile():
    if not session.get('user'):
        return redirect(url_for('index'))
    user_name = session['user']['displayName']
    return render_template('admin-edit-profile.html', user_name=user_name)

@app.route('/admin-create-user')
def admin_create_user():
    if not session.get('user'):
        return redirect(url_for('index'))
    user_name = session['user']['displayName']
    return render_template('admin-create-user.html', user_name=user_name)

@app.route('/admin-view-user')
def admin_view_user():
    if not session.get('user'):
        return redirect(url_for('index'))
    user_name = session['user']['displayName']
    return render_template('admin-view-user.html', user_name=user_name)

@app.route('/admin-update-user')
def admin_update_user():
    if not session.get('user'):
        return redirect(url_for('index'))
    user_name = session['user']['displayName']
    return render_template('admin-update-user.html', user_name=user_name)

@app.route('/admin-delete-user')
def admin_delete_user():
    if not session.get('user'):
        return redirect(url_for('index'))
    user_name = session['user']['displayName']
    return render_template('admin-delete-user.html', user_name=user_name)

@app.route('/admin/create-user', methods=['GET', 'POST'])
def create_user():
    if (request.method == 'POST' and request.headers.get('Content-Type') == 'application/json'):
        AddUser(request.data)
    return redirect(url_for('admin-create-user.html'))
    

# Logout route
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

# Helper function to build the authorization URL
def _build_auth_url(scopes=None, state=None):
    return msal.PublicClientApplication(
        CLIENT_ID, authority=AUTHORITY).get_authorization_request_url(
        scopes, state=state, redirect_uri=REDIRECT_URI)

# Helper function to get the access token
def _get_token_from_code(code):
    try:
        # Initialize the MSAL client
        client = msal.ConfidentialClientApplication(
            CLIENT_ID, authority=AUTHORITY, client_credential=CLIENT_SECRET)

        # Acquire the token using the authorization code
        result = client.acquire_token_by_authorization_code(
            code, scopes=SCOPE, redirect_uri=REDIRECT_URI)

        # Check if the token was acquired successfully
        if "access_token" in result:
            print("Access token acquired successfully")  # Debugging
            return result["access_token"]
        else:
            print("Failed to acquire access token. Response:", result)  # Debugging
            return None

    except Exception as e:
        print(f"Error acquiring token: {e}")  # Debugging
        return None

def _get_user_info(token):
    # Fetch basic user info
    graph_data = requests.get(
        'https://graph.microsoft.com/v1.0/me',
        headers={'Authorization': 'Bearer ' + token}
    ).json()

    # Fetch app roles assigned to the user
    roles_response = requests.get(
        'https://graph.microsoft.com/v1.0/me/appRoleAssignments',
        headers={'Authorization': 'Bearer ' + token}
    ).json()

    # Extract role values
    roles = []
    for assignment in roles_response.get('value', []):
        roles.append(assignment['appRoleId'])  # Use the role value (e.g., 'admin')

    graph_data['roles'] = roles  # Add roles to user info
    return graph_data

if __name__ == '__main__':
#   setup_db()  # Initialize database tables
    app.run(host='0.0.0.0', port=5000)

# Automatically create tables
with app.app_context():
    db.create_all()

