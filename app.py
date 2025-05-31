from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash # Added send_from_directory, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime # Import datetime for timestamps
import os # Import os for path manipulation and directory creation
from werkzeug.utils import secure_filename # For securing filenames
import markdown # Import the markdown library

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///blog.db' # SQLite database file named blog.db
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False # Disable tracking modifications for performance

# --- Configuration for file uploads ---
UPLOAD_FOLDER = 'uploads' # The main folder for all uploads
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'} # Allowed image extensions
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['SECRET_KEY'] = 'your_super_secret_key_for_flash_messages' # REMEMBER TO CHANGE THIS IN PRODUCTION
# --- End upload config ---

db = SQLAlchemy(app)

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

@app.route('/new_post', methods=['GET', 'POST'])
def new_post():
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content'] # This will now be Markdown
        author = request.form.get('author', 'Anonymous')
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

# Route to serve uploaded files
@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    # Ensure that only files within the UPLOAD_FOLDER can be served
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        # Optional: Add some initial data only if the database is empty (important for existing dbs)
        # Check if the 'main_image' column exists before trying to access it if your db is old
        # if not db.inspect(Post).has_column('main_image'):
        #     print("Adding 'main_image' column to Post model...")
        #     # This would require manual migration for existing data or recreate db
        #     pass # For now, just a print, assuming db.create_all handles new setup

        if not Post.query.first():
            initial_posts = [
                Post(title='Getting Started with Flask Blog', content='Welcome to my new blog! This is my first post, now powered by SQLite.', author='Admin'),
                Post(title='Understanding Web Development', content='Web development involves front-end, back-end, and database technologies.', author='Developer')
            ]
            db.session.add_all(initial_posts)
            db.session.commit()
    app.run(debug=True)