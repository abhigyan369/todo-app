from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///todos.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Todo model
class Todo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    completed = db.Column(db.Boolean, default=False)
    priority = db.Column(db.String(20), default='medium')  # low, medium, high
    category = db.Column(db.String(50), default='general')
    due_date = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'completed': self.completed,
            'priority': self.priority,
            'category': self.category,
            'due_date': self.due_date.isoformat() if self.due_date else None,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'is_overdue': self.due_date and self.due_date < datetime.utcnow() and not self.completed
        }

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/todos', methods=['GET'])
def get_todos():
    filter_by = request.args.get('filter', 'all')
    category = request.args.get('category', 'all')
    sort_by = request.args.get('sort', 'created_at')
    
    query = Todo.query
    
    # Apply filters
    if filter_by == 'completed':
        query = query.filter_by(completed=True)
    elif filter_by == 'pending':
        query = query.filter_by(completed=False)
    elif filter_by == 'overdue':
        query = query.filter(Todo.due_date < datetime.utcnow(), Todo.completed == False)
    
    if category != 'all':
        query = query.filter_by(category=category)
    
    # Apply sorting
    if sort_by == 'priority':
        priority_order = {'high': 1, 'medium': 2, 'low': 3}
        todos = query.all()
        todos.sort(key=lambda x: priority_order.get(x.priority, 4))
    elif sort_by == 'due_date':
        query = query.order_by(Todo.due_date.asc().nullslast())
        todos = query.all()
    else:
        query = query.order_by(Todo.created_at.desc())
        todos = query.all()
    
    return jsonify([todo.to_dict() for todo in todos])

@app.route('/api/todos', methods=['POST'])
def create_todo():
    data = request.get_json()
    
    due_date = None
    if data.get('due_date'):
        due_date = datetime.fromisoformat(data['due_date'].replace('Z', '+00:00'))
    
    todo = Todo(
        title=data['title'],
        description=data.get('description', ''),
        priority=data.get('priority', 'medium'),
        category=data.get('category', 'general'),
        due_date=due_date
    )
    
    db.session.add(todo)
    db.session.commit()
    
    return jsonify(todo.to_dict()), 201

@app.route('/api/todos/<int:todo_id>', methods=['PUT'])
def update_todo(todo_id):
    todo = Todo.query.get_or_404(todo_id)
    data = request.get_json()
    
    todo.title = data.get('title', todo.title)
    todo.description = data.get('description', todo.description)
    todo.completed = data.get('completed', todo.completed)
    todo.priority = data.get('priority', todo.priority)
    todo.category = data.get('category', todo.category)
    
    if data.get('due_date'):
        todo.due_date = datetime.fromisoformat(data['due_date'].replace('Z', '+00:00'))
    elif 'due_date' in data and data['due_date'] is None:
        todo.due_date = None
    
    todo.updated_at = datetime.utcnow()
    db.session.commit()
    
    return jsonify(todo.to_dict())

@app.route('/api/todos/<int:todo_id>', methods=['DELETE'])
def delete_todo(todo_id):
    todo = Todo.query.get_or_404(todo_id)
    db.session.delete(todo)
    db.session.commit()
    
    return '', 204

@app.route('/api/stats', methods=['GET'])
def get_stats():
    total = Todo.query.count()
    completed = Todo.query.filter_by(completed=True).count()
    pending = total - completed
    overdue = Todo.query.filter(Todo.due_date < datetime.utcnow(), Todo.completed == False).count()
    
    categories = db.session.query(Todo.category, db.func.count(Todo.id)).group_by(Todo.category).all()
    category_stats = {cat: count for cat, count in categories}
    
    return jsonify({
        'total': total,
        'completed': completed,
        'pending': pending,
        'overdue': overdue,
        'categories': category_stats
    })

@app.route('/api/todos/bulk', methods=['POST'])
def bulk_action():
    data = request.get_json()
    action = data.get('action')
    todo_ids = data.get('todo_ids', [])
    
    todos = Todo.query.filter(Todo.id.in_(todo_ids)).all()
    
    if action == 'complete':
        for todo in todos:
            todo.completed = True
    elif action == 'delete':
        for todo in todos:
            db.session.delete(todo)
    elif action == 'set_priority':
        priority = data.get('priority', 'medium')
        for todo in todos:
            todo.priority = priority
    
    db.session.commit()
    return jsonify({'success': True})

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        
        # Add sample data if database is empty
        if Todo.query.count() == 0:
            sample_todos = [
                Todo(title="Welcome to your Todo App!", description="This is a sample todo item", priority="high", category="getting-started"),
                Todo(title="Complete project proposal", description="Write and submit the Q4 project proposal", priority="high", category="work", due_date=datetime.utcnow() + timedelta(days=3)),
                Todo(title="Buy groceries", description="Milk, bread, eggs, vegetables", priority="medium", category="personal"),
                Todo(title="Call dentist", description="Schedule cleaning appointment", priority="low", category="health", due_date=datetime.utcnow() + timedelta(days=7)),
                Todo(title="Learn Flask", description="Complete the Flask tutorial", priority="medium", category="learning", completed=True)
            ]
            
            for todo in sample_todos:
                db.session.add(todo)
            db.session.commit()
    
    app.run(debug=True)