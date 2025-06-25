from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash # Added send_from_directory, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime # Import datetime for timestamps
import os # Import os for path manipulation and directory creation
from werkzeug.utils import secure_filename # For securing filenames
import markdown # Import the markdown library
import shutil # Import shutil for deleting directories
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user # New Flask-Login imports
from werkzeug.security import generate_password_hash, check_password_hash # New password hashing imports

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///blog.db' # SQLite database file named blog.db
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False # Disable tracking modifications for performance
app.config['SECRET_KEY'] = 'your_super_secret_key_for_flash_messages' # MAKE SURE THIS IS A LONG, RANDOM, AND SECRET STRING IN PRODUCTION

# --- Configuration for file uploads ---
UPLOAD_FOLDER = 'uploads' # The main folder for all uploads
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'} # Allowed image extensions
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
# --- End upload config ---

db = SQLAlchemy(app)
login_manager = LoginManager() # Initialize Flask-Login
login_manager.init_app(app) # Connect to the Flask app
login_manager.login_view = 'login' # Define the view Flask-Login should redirect to for login

# --- User Model for Authentication ---
class User(db.Model, UserMixin): # Inherit from UserMixin
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False) # Store hashed password
    is_admin = db.Column(db.Boolean, default=False) # Example: for admin users

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"User('{self.username}')"

# Flask-Login required user loader function
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Define the Post model (updated to include image_filename)
class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)
    author = db.Column(db.String(50), default='Anonymous') # Added default author
    date_posted = db.Column(db.DateTime, nullable=False, default=datetime.utcnow) # Automatically set current time
    # New column to store the filename of the main image for the post
    # We'll store it relative to the post's specific folder (e.g., 'my_image.jpg')
    main_image = db.Column(db.String(100), nullable=True)

    def __repr__(self):
        return f"Post('{self.title}', '{self.date_posted}')"
    
# Helper function to check allowed file extensions
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --- Helper function to process Markdown content for embedded images ---
def process_markdown_for_images(content_markdown, post_id):
    """
    Looks for Markdown image syntax and modifies paths to point to the correct
    /uploads/post_ID/ directory.
    Assumes images within the Markdown are referenced simply by filename
    e.g., ![Alt Text](my_image.jpg) becomes ![Alt Text](/uploads/POST_ID/my_image.jpg)
    """
    # Regex to find Markdown image links: ![alt text](path/to/image.jpg)
    # We capture the alt text, the path, and the title (optional)
    # This regex is simplified and might need refinement for complex cases
    import re
    # Pattern to find ![alt](image.ext) or ![alt](image.ext "title")
    # Group 1: Alt text, Group 2: Image path, Group 3: Optional title
    pattern = re.compile(r'!\[(.*?)\]\((.*?)(?: "(.*?)")?\)')

    def replace_image_path(match):
        alt_text = match.group(1)
        image_path = match.group(2)
        title = match.group(3) # This will be None if no title is present

        # If the image_path is just a filename (e.g., 'my_pic.jpg')
        # We assume it's an embedded image meant for this post's folder
        if not image_path.startswith('/') and not image_path.startswith('http'):
            # This is the original logic. For editing, if an image is removed
            # or the content changed, this simply resolves the path based on
            # what's written in the markdown. It doesn't handle deletion
            # of unreferenced images on the server.
            new_image_path = url_for('uploaded_file', filename=f"{post_id}/{image_path}")
        else:
            # If it's already an absolute path or external URL, leave it as is
            new_image_path = image_path
        
        # Reconstruct the Markdown image syntax
        if title:
            return f'![{alt_text}]({new_image_path} "{title}")'
        else:
            return f'![{alt_text}]({new_image_path})'
        
    return pattern.sub(replace_image_path, content_markdown)

# --- End helper function ---

# --- Database Initialization (Run this ONCE to create the database file) ---
# If you run your app and get errors like "no such table: post",
# you might need to run this codeblock once to create the database file and table.
# After it's run successfully, you can remove or comment it out.
# with app.app_context():
#     db.create_all()
#     # Optional: Add some initial data if the database is empty
#     if not Post.query.first():
#         initial_posts = [
#             Post(title='Getting Started with Flask Blog', content='Welcome to my new blog! This is my first post, now powered by SQLite.', author='Admin'),
#             Post(title='Understanding Web Development', content='Web development involves front-end, back-end, and database technologies.', author='Developer')
#         ]
#         db.session.add_all(initial_posts)
#         db.session.commit()
# -------------------------------------------------------------------------

@app.route('/')
def index():
    posts = Post.query.order_by(Post.date_posted.desc()).all()
    # For index page, we might just display the content as raw text or a very short excerpt
    # without full Markdown rendering for performance, or apply it if needed.
    # For now, let's keep it as is, as the full content is rendered on the post page.
    return render_template('index.html', posts=posts)

@app.route('/post/<int:post_id>')
def post(post_id):
    post = db.session.query(Post).get_or_404(post_id) # Ensure correct way to query with new model
    # Process markdown content to adjust image paths
    processed_content_markdown = process_markdown_for_images(post.content, post.id)
    # Convert processed markdown to HTML
    rendered_content_html = markdown.markdown(processed_content_markdown)

    return render_template('post.html', post=post, rendered_content=rendered_content_html) # Pass rendered HTML

# --- New User Registration Route ---
@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated: # If user is already logged in, redirect
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('Username already exists. Please choose a different one.', 'danger')
            return redirect(url_for('register')) # <<< ADD THIS LINE >>>
        else:
            new_user = User(username=username)
            new_user.set_password(password) # Hash the password
            db.session.add(new_user)
            db.session.commit()
            flash('Registration successful! You can now log in.', 'success')
            return redirect(url_for('login'))
        
    return render_template('register.html')

# --- New User Login Route ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated: # If user is already logged in, redirect
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user) # Log the user in
            flash('Logged in successfully!', 'success')
            next_page = request.args.get('next') # Redirect to original page if login was required
            return redirect(next_page or url_for('index'))
        else:
            flash('Login Unsuccessful. Please check username and password.', 'danger')
    return render_template('login.html')

# --- New User Logout Route ---
@app.route('/logout')
@login_required # User must be logged in to log out (prevents anonymous logout links)
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

# --- Protected Routes for Blog Management ---
@app.route('/new_post', methods=['GET', 'POST'])
@login_required # Only logged-in users can access this
def new_post():
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content'] # This will now be Markdown
        # Set author to current logged-in user's username
        author = current_user.username
        main_image_filename = None # Initialize image filename to None

        # Create the new Post object first, so we can get its ID for the folder name
        new_blog_post = Post(title=title, content=content, author=author)
        db.session.add(new_blog_post)
        db.session.commit() # Commit here to get the new_blog_post.id

        # Handle file upload AFTER the post is committed and has an ID
        if 'main_image' in request.files:
            file = request.files['main_image']
            if file and allowed_file(file.filename):
                # Create a unique subfolder for this post's images
                post_folder = os.path.join(app.config['UPLOAD_FOLDER'], str(new_blog_post.id))
                os.makedirs(post_folder, exist_ok=True) # Create the directory if it doesn't exist

                # Secure the filename to prevent directory traversal attacks
                filename = secure_filename(file.filename)
                # To prevent filename conflicts if multiple images are uploaded
                # (though for `main_image` it's less critical, good practice)
                # You might prepend a timestamp or UUID here if allowing multiple file inputs directly
                # For embedded images within Markdown, the user handles naming when writing Markdown.
                file_path = os.path.join(post_folder, filename)
                file.save(file_path)

                main_image_filename = filename # Store only the filename relative to its post folder
                new_blog_post.main_image = main_image_filename # Update the post object with the filename
                db.session.commit() # Commit again to save the image filename

        # Using flash for a simple success message (requires secret_key in app.config)
        flash('Your post has been created!', 'success')
        return redirect(url_for('post', post_id=new_blog_post.id))

    return render_template('new_post.html')

# --- New Route for Editing Posts ---
@app.route('/post/<int:post_id>/edit', methods=['GET', 'POST'])
@login_required # Only logged-in users can access this
def edit_post(post_id):
    post = db.session.query(Post).get_or_404(post_id)

    # Optional: Add authorization to only allow the original author to edit
    if post.author != current_user.username and not current_user.is_admin:
        flash('You are not authorized to edit this post.', 'danger')
        return redirect(url_for('post', post_id=post.id))

    if request.method == 'POST':
        post.title = request.form['title']
        post.content = request.form['content']
        post.author = request.form.get('author', current_user.username) # Default to logged-in user if not provided

        # Handle main_image update
        if 'main_image' in request.files:
            file = request.files['main_image']
            if file.filename != '': # Check if a new file was actually selected
                if file and allowed_file(file.filename):
                    # Define the post's dedicated image folder
                    post_folder = os.path.join(app.config['UPLOAD_FOLDER'], str(post.id))
                    os.makedirs(post_folder, exist_ok=True) # Ensure folder exists

                    # Delete old main image if it exists
                    if post.main_image:
                        old_image_path = os.path.join(post_folder, post.main_image)
                        if os.path.exists(old_image_path):
                            os.remove(old_image_path)
                            print(f"Deleted old main image: {old_image_path}")

                    filename = secure_filename(file.filename)
                    file_path = os.path.join(post_folder, filename)
                    file.save(file_path)
                    post.main_image = filename # Update with new filename
                else:
                    flash('Invalid image file type for main image.', 'warning')
            # Else, if filename is empty, user didn't select a new file, so keep existing post.main_image

        # Handle removing the main image (e.g., if a checkbox was added for 'delete_main_image')
        # For simplicity, we're not adding a "delete main image" checkbox right now.
        # If you want this, you'd add <input type="checkbox" name="delete_main_image">
        # and handle it here:
        # if 'delete_main_image' in request.form and request.form['delete_main_image'] == 'on':
        #    if post.main_image:
        #        old_image_path = os.path.join(post_folder, post.main_image)
        #        if os.path.exists(old_image_path):
        #            os.remove(old_image_path)
        #        post.main_image = None

        db.session.commit()
        flash('Your post has been updated!', 'success')
        return redirect(url_for('post', post_id=post.id))

    # GET request: render the edit form with existing post data
    return render_template('edit_post.html', post=post)

# --- New Route for Deleting Posts ---
@app.route('/post/<int:post_id>/delete', methods=['POST']) # Use POST method for deletion for security
def delete_post(post_id):
    post = db.session.query(Post).get_or_404(post_id)

    # Optional: Add authorization to only allow the original author to delete
    if post.author != current_user.username and not current_user.is_admin:
        flash('You are not authorized to delete this post.', 'danger')
        return redirect(url_for('post', post_id=post.id))

    # Delete associated image folder and its contents
    post_folder_path = os.path.join(app.config['UPLOAD_FOLDER'], str(post.id))
    if os.path.exists(post_folder_path):
        try:
            shutil.rmtree(post_folder_path) # Recursively delete the directory
            print(f"Deleted post image folder: {post_folder_path}")
        except Exception as e:
            print(f"Error deleting post image folder {post_folder_path}: {e}")
            flash(f"Error deleting associated images: {e}", 'danger')

    # Delete post from database
    db.session.delete(post)
    db.session.commit()
    flash('Your post has been deleted!', 'success')
    return redirect(url_for('index'))          

# Route to serve uploaded files
@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    # Ensure that only files within the UPLOAD_FOLDER can be served
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    # Initial setup for a default user if database is empty
    with app.app_context():
        db.create_all()
        # Create an initial user if no users exist
        if not User.query.first():
            admin_user = User(username='admin', is_admin=True)
            admin_user.set_password('p@ssw0rd') # CHANGE THIS PASSWORD IN PRODUCTION
            db.session.add(admin_user)
            db.session.commit()
            print("Created default admin user: 'admin' with password 'password'")
        
        if not Post.query.first():
            initial_posts = [
                Post(title='Getting Started with Flask Blog', content='Welcome to my new blog! This is my first post, now powered by SQLite.', author='Admin'),
                Post(title='Understanding Web Development', content='Web development involves front-end, back-end, and database technologies.', author='Developer')
            ]
            db.session.add_all(initial_posts)
            db.session.commit()
    app.run(debug=True)