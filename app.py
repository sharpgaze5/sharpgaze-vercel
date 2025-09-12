from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime, timezone
import json
import uuid
import os

# Initialize Flask app for Vercel
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key-change-in-production')

# Enable CORS for all routes
CORS(app)

# In-memory storage (for demo - use external database in production)
products_db = [
    {"id": 1, "name": "Classic Aviators", "price": 2999, "stock": 50, "image": "🕶️"},
    {"id": 2, "name": "Modern Frames", "price": 3499, "stock": 30, "image": "👓"},
    {"id": 3, "name": "Sports Sunglasses", "price": 4199, "stock": 25, "image": "🥽"},
    {"id": 4, "name": "Vintage Collection", "price": 3799, "stock": 20, "image": "🕶️"},
    {"id": 5, "name": "Blue Light Blockers", "price": 2499, "stock": 40, "image": "👓"},
    {"id": 6, "name": "Designer Frames", "price": 5999, "stock": 15, "image": "🕶️"}
]

# In-memory cart and orders storage
cart_sessions = {}
orders_db = {}

@app.route('/')
def home():
    """API root endpoint"""
    return jsonify({
        'message': 'SharpGaze E-commerce API is running on Vercel!',
        'status': 'success',
        'endpoints': {
            'products': '/api/products',
            'cart': '/api/cart',
            'checkout': '/api/checkout',
            'orders': '/api/orders',
            'health': '/api/health'
        }
    })
    # --- Add at the top with other in-memory DBs ---
users_db = {}  # {email: {"name": str, "password": str}}

# ---------------- AUTH ENDPOINTS ----------------

# --- In-memory user DB ---
users_db = {}  # {email: {"name": str, "password": str, "mobile": str}}

# ---------------- AUTH ENDPOINTS ----------------

@app.route('/api/auth/register', methods=['POST'])
def register():
    """Register new customer"""
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'No data provided'}), 400
    
    email = data.get('email')
    password = data.get('password')
    name = data.get('name')
    mobile = data.get('mobile')

    if not email or not password or not name or not mobile:
        return jsonify({'success': False, 'error': 'All fields are required'}), 400
    
    if email in users_db:
        return jsonify({'success': False, 'error': 'User already exists'}), 400

    users_db[email] = {
        "name": name,
        "password": password,   # ⚠️ plaintext for demo, hash in real use
        "mobile": mobile
    }
    return jsonify({'success': True, 'message': 'User registered successfully'})


@app.route('/api/auth/login', methods=['POST'])
def login():
    """Login customer"""
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    user = users_db.get(email)
    if not user or user['password'] != password:
        return jsonify({'success': False, 'error': 'Invalid credentials'}), 401

    session_id = str(uuid.uuid4())
    return jsonify({'success': True, 'message': 'Login successful', 'session_id': session_id})


# ---------------- SEARCH ENDPOINT ----------------

@app.route('/api/search', methods=['GET'])
def search_products():
    """Search products by name (case-insensitive)"""
    query = request.args.get('q', '').lower()
    if not query:
        return jsonify({'success': False, 'error': 'Query is required'}), 400
    
    results = [p for p in products_db if query in p['name'].lower()]
    return jsonify({'success': True, 'results': results, 'count': len(results)})


@app.route('/api/products', methods=['GET'])
def get_products():
    """Get all products"""
    return jsonify({
        'success': True,
        'products': products_db,
        'count': len(products_db)
    })

@app.route('/api/products/<int:product_id>', methods=['GET'])
def get_product(product_id):
    """Get a specific product"""
    product = next((p for p in products_db if p['id'] == product_id), None)
    if product:
        return jsonify({'success': True, 'product': product})
    return jsonify({'success': False, 'error': 'Product not found'}), 404

@app.route('/api/cart', methods=['POST'])
def update_cart():
    """Update cart session"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        
        session_id = request.headers.get('Session-ID') or data.get('session_id', str(uuid.uuid4()))
        cart_data = data.get('cart', [])
        
        # Store cart in memory (use Redis/Database in production)
        cart_sessions[session_id] = {
            'cart': cart_data,
            'updated_at': datetime.now(timezone.utc).isoformat()
        }
        
        return jsonify({
            'success': True,
            'session_id': session_id,
            'message': 'Cart updated successfully',
            'cart': cart_data
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/cart/<session_id>', methods=['GET'])
def get_cart(session_id):
    """Get cart for session"""
    cart_session = cart_sessions.get(session_id)
    if cart_session:
        return jsonify({
            'success': True,
            'cart': cart_session['cart'],
            'session_id': session_id
        })
    return jsonify({'success': True, 'cart': [], 'session_id': session_id})

@app.route('/api/checkout', methods=['POST'])
def checkout():
    """Process checkout"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
            
        items = data.get('items', [])
        total = data.get('total', 0)
        customer_info = data.get('customer', {})
        
        if not items:
            return jsonify({'success': False, 'error': 'Cart is empty'}), 400
        
        # Generate order ID
        order_id = f"SG{datetime.now().strftime('%Y%m%d')}{str(uuid.uuid4())[:8].upper()}"
        
        # Validate stock and calculate total
        calculated_total = 0
        order_items = []
        
        for item in items:
            product = next((p for p in products_db if p['id'] == item['id']), None)
            if not product:
                return jsonify({'success': False, 'error': f'Product {item["id"]} not found'}), 400
            
            if product['stock'] < item['quantity']:
                return jsonify({
                    'success': False, 
                    'error': f'Insufficient stock for {product["name"]}. Available: {product["stock"]}'
                }), 400
            
            item_total = product['price'] * item['quantity']
            calculated_total += item_total
            
            order_items.append({
                'product_id': product['id'],
                'product_name': product['name'],
                'price': product['price'],
                'quantity': item['quantity'],
                'total': item_total
            })
            
            # Update stock
            product['stock'] -= item['quantity']
        
        # Create order
        order = {
            'order_id': order_id,
            'items': order_items,
            'customer_email': customer_info.get('email', ''),
            'customer_name': customer_info.get('name', ''),
            'customer_phone': customer_info.get('phone', ''),
            'total_amount': calculated_total,
            'status': 'confirmed',
            'created_at': datetime.now(timezone.utc).isoformat()
        }
        
        # Store order
        orders_db[order_id] = order
        
        return jsonify({
            'success': True,
            'order_id': order_id,
            'message': 'Order placed successfully!',
            'order': order,
            'total': calculated_total
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/orders', methods=['GET'])
def get_orders():
    """Get all orders (admin endpoint)"""
    orders_list = list(orders_db.values())
    orders_list.sort(key=lambda x: x['created_at'], reverse=True)
    
    return jsonify({
        'success': True,
        'orders': orders_list,
        'count': len(orders_list)
    })

@app.route('/api/orders/<order_id>', methods=['GET'])
def get_order(order_id):
    """Get specific order details"""
    order = orders_db.get(order_id)
    if order:
        return jsonify({'success': True, 'order': order})
    return jsonify({'success': False, 'error': 'Order not found'}), 404

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'version': '1.0.0',
        'platform': 'Vercel',
        'products_count': len(products_db),
        'orders_count': len(orders_db),
        'cart_sessions': len(cart_sessions)
    })

@app.route('/api/admin/products', methods=['POST'])
def add_product():
    """Add new product (admin endpoint)"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        
        # Generate new product ID
        new_id = max([p['id'] for p in products_db], default=0) + 1
        
        product = {
            'id': new_id,
            'name': data['name'],
            'price': data['price'],
            'stock': data.get('stock', 0),
            'image': data.get('image', '📦'),
            'description': data.get('description', '')
        }
        
        products_db.append(product)
        
        return jsonify({
            'success': True,
            'message': 'Product added successfully',
            'product': product
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/admin/reset', methods=['POST'])
def reset_data():
    """Reset all data (demo purposes)"""
    global products_db, cart_sessions, orders_db
    
    # Reset to original products
    products_db = [
        {"id": 1, "name": "Classic Aviators", "price": 2999, "stock": 50, "image": "🕶️"},
        {"id": 2, "name": "Modern Frames", "price": 3499, "stock": 30, "image": "👓"},
        {"id": 3, "name": "Sports Sunglasses", "price": 4199, "stock": 25, "image": "🥽"},
        {"id": 4, "name": "Vintage Collection", "price": 3799, "stock": 20, "image": "🕶️"},
        {"id": 5, "name": "Blue Light Blockers", "price": 2499, "stock": 40, "image": "👓"},
        {"id": 6, "name": "Designer Frames", "price": 5999, "stock": 15, "image": "🕶️"}
    ]
    
    cart_sessions.clear()
    orders_db.clear()
    
    return jsonify({
        'success': True,
        'message': 'Data reset successfully'
    })

# Handle CORS preflight requests
@app.before_request
def handle_preflight():
    if request.method == "OPTIONS":
        response = jsonify({'success': True})
        response.headers.add("Access-Control-Allow-Origin", "*")
        response.headers.add('Access-Control-Allow-Headers', "*")
        response.headers.add('Access-Control-Allow-Methods', "*")
        return response

# Error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({'success': False, 'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'success': False, 'error': 'Internal server error'}), 500

# Vercel requires this to be the default export
if __name__ == '__main__':
    app.run(debug=True)

# For Vercel deployment
def handler(request):
    return app(request)
