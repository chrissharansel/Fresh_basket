from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
import mysql.connector
from mysql.connector import Error
from mysql.connector.pooling import MySQLConnectionPool
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os

# Simulated database for products
products = [
    {"id": "apple", "name": "Organic Apples", "price": 299},
    {"id": "carrot", "name": "Fresh Carrots", "price": 149},
    {"id": "egg", "name": "Farm Fresh Eggs", "price": 99},
    {"id": "mango", "name": "Fresh Mangoes", "price": 199},
    {"id": "sweet-potato", "name": "Sweet Potatoes", "price": 179},
    {"id": "lettuce", "name": "Green Lettuce", "price": 89},
    {"id": "banana", "name": "Organic Bananas", "price": 59},
    {"id": "bell-pepper", "name": "Red Bell Peppers", "price": 120},
    {"id": "tomato", "name": "Fresh Tomatoes", "price": 69},
    {"id": "orange", "name": "Juicy Oranges", "price": 129},
    {"id": "pineapple", "name": "Fresh Pineapples", "price": 149},
    {"id": "grapes", "name": "Red Grapes", "price": 249},
]

app = Flask(__name__)
app.secret_key = os.urandom(24)  # Secret key for sessions and flash messages

# Database configuration
db_config = {
    'host': 'ecomdbs.c362gw2i0ox8.us-east-1.rds.amazonaws.com',
    'user': 'admin',
    'password': 'WDWawsdb05',
    'database': 'fresh'
}

# Connection pool setup
cnxpool = MySQLConnectionPool(pool_name="mypool", pool_size=5, **db_config)

# Function to establish a database connection
def get_db_connection():
    try:
        return cnxpool.get_connection()
    except Error as err:
        app.logger.error(f"Database connection error: {err}")
        return None


@app.route('/')
def home():
    return render_template('home.html')  # Render home page


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name')
        mobile = request.form.get('mobile')
        email = request.form.get('email')
        password = generate_password_hash(request.form.get('password'))
        default_address = request.form.get('default_address')

        if not default_address:
            flash('Default address is required!')
            return redirect(url_for('register'))

        conn = get_db_connection()
        if not conn:
            flash('Database connection error. Please try again later.')
            return redirect(url_for('register'))

        cursor = conn.cursor()
        try:
            cursor.execute(
                'INSERT INTO users (name, mobile, email, password, address) VALUES (%s, %s, %s, %s, %s)',
                (name, mobile, email, password, default_address)
            )
            conn.commit()
            flash('Thank you for registering! Please log in to continue.', 'success')
            return redirect(url_for('login'))  # Redirect to login page
        except Error as e:
            flash(f"Error: {e}", 'danger')
            conn.rollback()
        finally:
            cursor.close()
            conn.close()
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        conn = get_db_connection()
        if not conn:
            flash('Database connection error. Please try again later.', 'danger')
            return redirect(url_for('login'))

        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute('SELECT * FROM users WHERE email = %s', (email,))
            user = cursor.fetchone()

            if user and check_password_hash(user['password'], password):
                # Set user session
                session['user_id'] = user['id']
                session['user_name'] = user['name']
                flash('Login successful!', 'success')

                return redirect(url_for('shop'))  # Redirect to shop page
            else:
                flash('Invalid email or password. Please try again.', 'danger')
        except Error as e:
            flash(f'An error occurred: {str(e)}', 'danger')
        finally:
            cursor.close()
            conn.close()

    return render_template('login.html')


@app.route('/shop')
def shop():
    if 'user_id' not in session:
        flash('Please log in to access the shop.')
        return redirect(url_for('login'))  # Redirect to login page if not logged in
    
    return render_template('shop.html', products=products)


@app.route('/cart')
def view_cart():
    cart_items = session.get('cart', [])
    print("Cart items:", cart_items)  # Debugging the cart
    total_price = sum(item['price'] * item['quantity'] for item in cart_items)
    total_items = sum(item['quantity'] for item in cart_items)

    return render_template('cart.html', cart_items=cart_items, total_price=total_price, total_items=total_items)


@app.route('/add_to_cart', methods=['POST'])
def add_to_cart():
    item_id = request.form.get('item_id')
    item_name = request.form.get('item_name')
    item_price = float(request.form.get('item_price'))
    item_quantity = int(request.form.get('item_quantity'))

    cart = session.get('cart', [])  # Get existing cart or create an empty list

    existing_item = next((item for item in cart if item['id'] == item_id), None)

    if existing_item:
        existing_item['quantity'] += item_quantity
    else:
        cart.append({'id': item_id, 'name': item_name, 'price': item_price, 'quantity': item_quantity})

    session['cart'] = cart  # Set the updated cart back to the session
    print("Updated cart:", session.get('cart', []))  # Debugging the cart

    return redirect(url_for('view_cart'))

@app.route('/place_order', methods=['POST'])
def place_order():
    if 'user_id' not in session:
        return jsonify(success=False, message="User not logged in")

    data = request.get_json()
    delivery_address = data.get('address', 'Default Address')
    payment_method = data["payment_method"]
    items = data['items']
    total_price = data['total_price']

    conn = get_db_connection()
    if not conn:
        return jsonify(success=False, message="Database connection error.")

    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO orders (user_id, delivery_address, payment_method, status, order_date, total_price) VALUES (%s, %s, %s, %s, %s, %s)",
            (session['user_id'], delivery_address, payment_method, 'Yet to Ship', datetime.now(), total_price)
        )
        order_id = cursor.lastrowid
        for item in items:
            cursor.execute(
                'INSERT INTO order_items (order_id, item_name, quantity, price) VALUES (%s, %s, %s, %s)',
                (order_id, item['name'], item['quantity'], item['price'])
            )
        conn.commit()
        return jsonify(success=True)
    except Error as e:
        conn.rollback()
        return jsonify(success=False, message=str(e))
    finally:
        cursor.close()
        conn.close()


@app.route('/logout')
def logout():
    session.pop('user_id', None)  # Remove user session data
    session.pop('user_name', None)
    flash('You have been logged out.')
    return redirect(url_for('home'))  # Redirect to home page


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
