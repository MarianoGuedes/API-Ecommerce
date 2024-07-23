from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from flask_login import UserMixin, login_user, LoginManager, login_required, logout_user, current_user
from datetime import datetime
from sqlalchemy import event
from functools import wraps

app = Flask(__name__)
app.config['SECRET_KEY'] = "my_key_0115"
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///ecommerce.db'

CORS(app)
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False, unique=True)
    password = db.Column(db.String(80), nullable=True)
    shopping_cart = db.relationship('CartItem', backref=db.backref('User'), lazy=True)


class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    price = db.Column(db.Float, nullable=False)
    description = db.Column(db.Text, nullable=True)
    created = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated = db.Column(db.DateTime, nullable=True, default=None, onupdate=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user = db.relationship('User', backref=db.backref('products', lazy=True))


class CartItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    car_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    name = db.Column(db.String(80), nullable=False)
    description = db.Column(db.Text, nullable=True)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@app.route('/login', methods=["POST"])
def login():
    data = request.json
    user = User.query.filter_by(username=data.get("username")).first()

    if user and data.get("password") == user.password:
        login_user(user)
        return jsonify({
            "message": f"Logged in successfully, welcome {user.username}"
        }), 200

    return jsonify({
        "message": "Unauthorized. Invalid username or password"
    }), 401


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify({
                "message": "Unauthorized. Please log in."
            }), 401
        return f(*args, **kwargs)

    return decorated_function


@app.route('/logout', methods=["POST"])
@login_required
def logout():
    logout_user()
    return jsonify({
        "message": "Logout successfully"
    }), 200


@app.route('/api/products/add', methods=["POST"])
@login_required
def add_product():
    data = request.json
    missing_fields = []

    if 'name' not in data:
        missing_fields.append('name')
    if 'price' not in data:
        missing_fields.append('price')

    if not missing_fields:
        existing_product = Product.query.filter_by(name=data["name"]).first()
        if existing_product:
            return jsonify({
                "message": "For existing products, be sure to enter a new name.",
                "error": f"Product with name '{data['name']}' already exists"
            }), 400

        product = Product(
            name=data["name"],
            price=data["price"],
            description=data.get("description", ""),
            user_id=current_user.id
        )
        db.session.add(product)
        db.session.commit()
        return jsonify({
            "message": "Product added successfully",
            "product": {
                "id": product.id,
                "name": product.name,
                "price": product.price,
                "description": product.description,
            }
        }), 201
    else:
        return jsonify({
            "message": "Invalid product data",
            "missing_fields": missing_fields
        }), 400


@app.route('/api/products/delete/<int:product_id>', methods=["DELETE"])
@login_required
def delete_product(product_id):
    product = Product.query.get(product_id)

    if product:
        db.session.delete(product)
        db.session.commit()
        return jsonify({
            "message": "Product deleted successfully",
            "product": {
                "id": product.id,
                "name": product.name,
                "price": product.price,
                "description": product.description,
            }
        }), 200
    else:
        return jsonify({
            "message": "Product not found"
        }), 404


@app.route('/api/products', methods=["POST"])
def get_product_details():
    data = request.json
    product_id = data.get('id')
    product_name = data.get('name')

    if product_id is not None:
        if isinstance(product_id, int):
            product = Product.query.get(product_id)
            if product:
                return jsonify({
                    "id": product.id,
                    "name": product.name,
                    "price": product.price,
                    "description": product.description
                }), 200
            else:
                return jsonify({
                    "message": "Product not found",
                    "error": f"No product found with ID {product_id}"
                }), 404
        else:
            return jsonify({
                "message": "Invalid ID format",
                "error": "ID should be an integer"
            }), 400

    if product_name is not None:
        products = Product.query.filter_by(name=product_name).all()
        if products:
            product_list = [{
                "id": product.id,
                "name": product.name,
                "price": product.price,
                "description": product.description
            } for product in products]
            return jsonify(product_list), 200
        else:
            return jsonify({
                "message": "No products found",
                "error": f"No products found with name '{product_name}'"
            }), 404

    return jsonify({
        "message": "Please provide either 'id' or 'name' to search for products"
    }), 400


@app.route('/api/products/update/<int:product_id>', methods=["PUT"])
@login_required
def update_product(product_id):
    product = Product.query.get(product_id)
    if not product:
        return jsonify({
            "message": "No products found",
            "error": f"No products found with ID {product_id}"
        }), 404

    data = request.json
    updated = False

    if 'name' in data:
        if data['name'] != product.name:
            product.name = data['name']
            updated = True

    if 'price' in data:
        if data['price'] != product.price:
            product.price = data['price']
            updated = True

    if 'description' in data:
        if data['description'] != product.description:
            product.description = data['description']
            updated = True

    if updated:
        db.session.commit()
        return jsonify({'message': 'Product updated successfully', 'product': {
            "id": product.id,
            "name": product.name,
            "price": product.price,
            "description": product.description,
            "updated": product.updated
        }}), 200

    return jsonify({
        'message': 'No changes detected'
    }), 200


@app.route('/api/products', methods=['GET'])
def get_products():
    products = Product.query.all()
    product_list = []
    for product in products:
        product_data = {
            "id": product.id,
            "name": product.name,
            "price": product.price,
            "description": product.description,
            "created": product.created,
        }
        product_list.append(product_data)

    return jsonify(product_list), 200


@app.route('/api/cart/add/<int:product_id>', methods=['POST'])
@login_required
def add_cart_product(product_id):
    user = User.query.get(current_user.id)
    product = Product.query.get(product_id)

    if not product:
        return jsonify({
            "message": "Failed to add product to cart",
            "error": f"Product with ID {product_id} not found"
        }), 400

    cart_item = CartItem(car_user_id=user.id, product_id=product.id, name=product.name, description=product.description)
    db.session.add(cart_item)
    db.session.commit()

    return jsonify({
        "message": "Product added to cart successfully",
        "product": {
            "id": product.id,
            "name": product.name,
            "price": product.price,
            "description": product.description,
        }
    }), 201


@app.route('/api/cart/remove/<int:cart_item_id>', methods=['DELETE'])
@login_required
def remove_cart_product(cart_item_id):
    cart_item = CartItem.query.get(cart_item_id)

    if cart_item and cart_item.car_user_id == current_user.id:
        product = Product.query.get(cart_item.product_id)

        db.session.delete(cart_item)
        db.session.commit()
        return jsonify({
            "message": "Product removed from cart successfully",
            "product": {
                "id": product.id,
                "name": product.name,
                "price": product.price,
                "description": product.description,
            }
        }), 200
    else:
        return jsonify({
            "message": "Cart item not found or you are not authorized to delete it"
        }), 404


@app.route('/api/cart', methods=['GET'])
@login_required
def get_cart_products():
    cart_items = CartItem.query.filter_by(car_user_id=current_user.id).all()
    cart_product_list = []

    for cart_item in cart_items:
        product = Product.query.get(cart_item.product_id)
        if product:
            cart_product_data = {
                "cart_item_id": cart_item.id,
                "product": {
                    "name": product.name,
                    "price": product.price,
                    "description": product.description,
                }
            }
            cart_product_list.append(cart_product_data)

    if cart_product_list:
        return jsonify(cart_product_list), 200
    else:
        return jsonify({
            "message": "No products in the cart"
        }), 404


@app.route('/api/cart/checkout', methods=["POST"])
@login_required
def checkout():
    user = User.query.get(int(current_user.id))
    cart_items = user.shopping_cart
    for cart_item in cart_items:
        db.session.delete(cart_item)
    db.session.commit()
    return jsonify({
        "message": 'Checkout successful, cart has been cleared.'
    }), 200


if __name__ == "__main__":
    app.run(debug=True)
