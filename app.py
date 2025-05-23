from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime # Import datetime for timestamps

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///blog.db' # SQLite database file named blog.db
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False # Disable tracking modifications for performance

db = SQLAlchemy(app)

# Define the Post model (this will be our database table)
class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)
    author = db.Column(db.String(50), default='Anonymous') # Added default author
    date_posted = db.Column(db.DateTime, nullable=False, default=datetime.utcnow) # Automatically set current time

    def __repr__(self):
        return f"Post('{self.title}', '{self.date_posted}')"

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
    posts = Post.query.order_by(Post.date_posted.desc()).all() # Fetch all posts, ordered by date
    return render_template('index.html', posts=posts)

@app.route('/post/<int:post_id>')
def post(post_id):
    post = Post.query.get_or_404(post_id) # Get post by ID, or return 404
    return render_template('post.html', post=post)

@app.route('/new_post', methods=['GET', 'POST'])
def new_post():
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        # For now, author is fixed. In a real app, this would come from logged-in user
        author = request.form.get('author', 'Anonymous') # Allow user to input author name

        new_blog_post = Post(title=title, content=content, author=author)
        db.session.add(new_blog_post)
        db.session.commit()
        return redirect(url_for('post', post_id=new_blog_post.id))
    return render_template('new_post.html')

if __name__ == '__main__':
    with app.app_context(): # Ensure app context is pushed for db operations outside routes
        db.create_all() # Create tables if they don't exist
        # Optional: Add some initial data if the database is empty
        if not Post.query.first():
            initial_posts = [
                Post(title='Getting Started with Flask Blog', content='Welcome to my new blog! This is my first post, now powered by SQLite.', author='Admin'),
                Post(title='Understanding Web Development', content='Web development involves front-end, back-end, and database technologies.', author='Developer')
            ]
            db.session.add_all(initial_posts)
            db.session.commit()
    app.run(debug=True)