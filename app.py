from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import os

# --------------------
# APP CONFIG
# --------------------
app = Flask(__name__)
app.config["SECRET_KEY"] = "your-secret-key-here"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# --------------------
# SQLITE (RENDER SAFE)
# --------------------
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
db_path = os.path.join(BASE_DIR, "todos.db")
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + db_path

db = SQLAlchemy(app)

# --------------------
# MODEL
# --------------------
class Todo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    completed = db.Column(db.Boolean, default=False)
    priority = db.Column(db.String(20), default="medium")
    category = db.Column(db.String(50), default="general")
    due_date = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "completed": self.completed,
            "priority": self.priority,
            "category": self.category,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "is_overdue": (
                self.due_date and
                self.due_date < datetime.utcnow() and
                not self.completed
            )
        }

# --------------------
# ROUTES
# --------------------
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/todos", methods=["GET"])
def get_todos():
    filter_by = request.args.get("filter", "all")
    category = request.args.get("category", "all")
    sort_by = request.args.get("sort", "created_at")

    query = Todo.query

    if filter_by == "completed":
        query = query.filter_by(completed=True)
    elif filter_by == "pending":
        query = query.filter_by(completed=False)
    elif filter_by == "overdue":
        query = query.filter(
            Todo.due_date < datetime.utcnow(),
            Todo.completed.is_(False)
        )

    if category != "all":
        query = query.filter_by(category=category)

    if sort_by == "priority":
        priority_order = {"high": 1, "medium": 2, "low": 3}
        todos = query.all()
        todos.sort(key=lambda x: priority_order.get(x.priority, 4))
    elif sort_by == "due_date":
        todos = query.order_by(Todo.due_date.asc().nullslast()).all()
    else:
        todos = query.order_by(Todo.created_at.desc()).all()

    return jsonify([todo.to_dict() for todo in todos])

@app.route("/api/todos", methods=["POST"])
def create_todo():
    data = request.get_json()

    due_date = None
    if data.get("due_date"):
        due_date = datetime.fromisoformat(
            data["due_date"].replace("Z", "+00:00")
        )

    todo = Todo(
        title=data["title"],
        description=data.get("description", ""),
        priority=data.get("priority", "medium"),
        category=data.get("category", "general"),
        due_date=due_date
    )

    db.session.add(todo)
    db.session.commit()

    return jsonify(todo.to_dict()), 201

@app.route("/api/todos/<int:todo_id>", methods=["PUT"])
def update_todo(todo_id):
    todo = Todo.query.get_or_404(todo_id)
    data = request.get_json()

    todo.title = data.get("title", todo.title)
    todo.description = data.get("description", todo.description)
    todo.completed = data.get("completed", todo.completed)
    todo.priority = data.get("priority", todo.priority)
    todo.category = data.get("category", todo.category)

    if data.get("due_date"):
        todo.due_date = datetime.fromisoformat(
            data["due_date"].replace("Z", "+00:00")
        )
    elif "due_date" in data:
        todo.due_date = None

    db.session.commit()
    return jsonify(todo.to_dict())

@app.route("/api/todos/<int:todo_id>", methods=["DELETE"])
def delete_todo(todo_id):
    todo = Todo.query.get_or_404(todo_id)
    db.session.delete(todo)
    db.session.commit()
    return "", 204

@app.route("/api/stats", methods=["GET"])
def stats():
    total = Todo.query.count()
    completed = Todo.query.filter_by(completed=True).count()
    overdue = Todo.query.filter(
        Todo.due_date < datetime.utcnow(),
        Todo.completed.is_(False)
    ).count()

    return jsonify({
        "total": total,
        "completed": completed,
        "pending": total - completed,
        "overdue": overdue
    })

# --------------------
# DATABASE INIT (RUNS ON GUNICORN)
# --------------------
with app.app_context():
    db.create_all()

    if Todo.query.count() == 0:
        sample_todos = [
            Todo(title="Welcome!", description="Your Todo App is live 🎉", priority="high"),
            Todo(title="Learn Flask", completed=True),
            Todo(title="Deploy on Render", priority="medium")
        ]
        db.session.add_all(sample_todos)
        db.session.commit()

# --------------------
# LOCAL DEV ONLY
# --------------------
if __name__ == "__main__":
    app.run()
