import os
import uuid
from datetime import datetime

from flask import Flask, request, jsonify, session
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key-change-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'postgresql://user:password@localhost/sharpgaze_db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
migrate = Migrate(app, db)
CORS(app)

# Models

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    mobile = db.Column(db.String(20), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Product(db.Model):
    __tablename__ = 'products'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    price = db.Column(db.Integer, nullable=False)
    stock = db.Column(db.Integer, default=0)
    image = db.Column(db.String(10), default='📦')
    description = db.Column(db.Text)

class Order(db.Model):
    __tablename__ = 'orders'
    id = db.Column(db.String(50), primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    customer_name = db.Column(db.String(150))
    customer_email = db.Column(db.String(150))
    customer_phone = db.Column(db.String(20))
    total_amount = db.Column(db.Integer)
    status = db.Column(db.String(50), default='confirmed')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    items = db.relationship('OrderItem', backref='order', cascade='all, delete-orphan')

class OrderItem(db.Model):
    __tablename__ = 'order_items'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.String(50), db.ForeignKey('orders.id'))
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'))
    product_name = db.Column(db.String(200))
    price = db.Column(db.Integer)
    quantity = db.Column(db.Integer)
    total = db.Column(db.Integer)

# Routes

@app.route('/api/auth/register', methods=['POST'])
def register():
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'No data provided'}), 400

    email = data.get('email')
    password = data.get('password')
    name = data.get('name')
    mobile = data.get('mobile')

    if not all([email, password, name, mobile]):
        return jsonify({'success': False, 'error': 'All fields are required'}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({'success': False, 'error': 'User already exists'}), 400

    user = User(name=name, email=email, mobile=mobile)
    user.set_password(password)

    db.session.add(user)
    db.session.commit()

    return jsonify({'success': True, 'message': 'User registered successfully'})

@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({'success': False, 'error': 'Email and password required'}), 400

    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        return jsonify({'success': False, 'error': 'Invalid credentials'}), 401
    
    session_id = str(uuid.uuid4())
    session['user_id'] = user.id

    return jsonify({'success': True, 'message': 'Login successful', 'session_id': session_id, 'user': {'id': user.id, 'name': user.name}})

@app.route('/api/admin/customers', methods=['GET'])
def get_customers():
    # TODO: Protect this route with admin authentication
    users = User.query.all()
    results = [{
        'id': u.id,
        'name': u.name,
        'email': u.email,
        'mobile': u.mobile
    } for u in users]
    return jsonify({'success': True, 'customers': results, 'count': len(results)})

@app.route('/api/products', methods=['GET'])
def get_products():
    products = Product.query.all()
    results = [{
        'id': p.id,
        'name': p.name,
        'price': p.price,
        'stock': p.stock,
        'image': p.image,
        'description': p.description
    } for p in products]
    return jsonify({'success': True, 'products': results, 'count': len(results)})

@app.route('/api/search', methods=['GET'])
def search_products():
    query = request.args.get('q', '').lower()
    if not query:
        return jsonify({'success': False, 'error': 'Query is required'}), 400
    
    products = Product.query.filter(Product.name.ilike(f'%{query}%')).all()
    results = [{
        'id': p.id, 'name': p.name, 'price': p.price,
        'stock': p.stock, 'image': p.image, 'description': p.description
    } for p in products]
    return jsonify({'success': True, 'results': results, 'count': len(results)})

@app.route('/api/checkout', methods=['POST'])
def checkout():
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'No data provided'}), 400
    
    items = data.get('items', [])
    total = data.get('total', 0)
    customer_info = data.get('customer', {})

    if not items:
        return jsonify({'success': False, 'error': 'Cart is empty'}), 400

    calculated_total = 0
    order_items = []

    for item in items:
        product = Product.query.filter_by(id=item['id']).first()
        if not product:
            return jsonify({'success': False, 'error': f'Product {item["id"]} not found'}), 400
        if product.stock < item['quantity']:
            return jsonify({'success': False, 'error': f'Insufficient stock for {product.name}. Available: {product.stock}'}), 400
        
        item_total = product.price * item['quantity']
        calculated_total += item_total
        
        order_items.append({
            'product_id': product.id,
            'product_name': product.name,
            'price': product.price,
            'quantity': item['quantity'],
            'total': item_total
        })

    if calculated_total != total:
        return jsonify({'success': False, 'error': 'Total mismatch'}), 400

    order_id = f"SG{datetime.utcnow().strftime('%Y%m%d')}{str(uuid.uuid4())[:8].upper()}"
    
    order = Order(
        id=order_id,
        customer_email=customer_info.get('email', ''),
        customer_name=customer_info.get('name', ''),
        customer_phone=customer_info.get('phone', ''),
        total_amount=calculated_total,
        status='confirmed',
        created_at=datetime.utcnow()
    )
    db.session.add(order)
    db.session.flush()

    for oi in order_items:
        order_item = OrderItem(
            order_id=order_id,
            product_id=oi['product_id'],
            product_name=oi['product_name'],
            price=oi['price'],
            quantity=oi['quantity'],
            total=oi['total']
        )
        product = Product.query.get(oi['product_id'])
        product.stock -= oi['quantity']
        db.session.add(order_item)
    
    db.session.commit()

    return jsonify({'success': True, 'order_id': order_id, 'message': 'Order placed successfully!'})

if __name__ == '__main__':
    app.run(debug=True)
