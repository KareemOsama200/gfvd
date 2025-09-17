from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from flask_wtf.csrf import CSRFProtect
from wtforms import StringField, TextAreaField, DecimalField, IntegerField, SelectField, FileField, SubmitField, HiddenField
from wtforms.validators import DataRequired, NumberRange
from werkzeug.utils import secure_filename
from PIL import Image
import os
import json
import uuid
from datetime import datetime

app = Flask(__name__)

# إنشاء مجلد instance بمسار مطلق
os.makedirs(app.instance_path, exist_ok=True)

app.config['SECRET_KEY'] = os.environ.get('SESSION_SECRET', 'dev-key-change-in-production')
db_path = os.path.join(app.instance_path, 'marvo_store.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# CSRF Protection
csrf = CSRFProtect(app)

# Allowed file extensions for images
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

# إنشاء مجلدات التحميل إذا لم تكن موجودة
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_uploaded_image(file):
    if file and allowed_file(file.filename):
        # Generate unique filename
        file_extension = file.filename.rsplit('.', 1)[1].lower()
        filename = f"{uuid.uuid4().hex}.{file_extension}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        try:
            # Verify it's actually an image using Pillow
            img = Image.open(file)
            img.verify()
            
            # Reset file pointer and save
            file.seek(0)
            file.save(filepath)
            return filename
        except Exception as e:
            flash('ملف الصورة غير صالح', 'error')
            return None
    return None

db = SQLAlchemy(app)

# نموذج المنتج
class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    price = db.Column(db.Float, nullable=False)
    image_url = db.Column(db.String(200), nullable=True)
    category = db.Column(db.String(50), nullable=False)
    size_options = db.Column(db.Text, nullable=True)  # JSON string
    color_options = db.Column(db.Text, nullable=True)  # JSON string
    stock = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def get_sizes(self):
        if self.size_options:
            return json.loads(self.size_options)
        return []
    
    def get_colors(self):
        if self.color_options:
            return json.loads(self.color_options)
        return []

# نموذج سلة التسوق
class CartItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(100), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    size = db.Column(db.String(20), nullable=True)
    color = db.Column(db.String(50), nullable=True)
    added_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    product = db.relationship('Product', backref=db.backref('cart_items', lazy=True))

# نماذج WTForms
class ProductForm(FlaskForm):
    name = StringField('اسم المنتج', validators=[DataRequired()])
    description = TextAreaField('الوصف', validators=[DataRequired()])
    price = DecimalField('السعر', validators=[DataRequired(), NumberRange(min=0)])
    category = SelectField('الفئة', choices=[
        ('shirts', 'قمصان'),
        ('pants', 'بناطيل'),
        ('shoes', 'أحذية'),
        ('accessories', 'إكسسوارات')
    ], validators=[DataRequired()])
    stock = IntegerField('الكمية في المخزون', validators=[DataRequired(), NumberRange(min=0)])
    image = FileField('صورة المنتج')
    sizes = StringField('الأحجام (مفصولة بفاصلة)')
    colors = StringField('الألوان (مفصولة بفاصلة)')
    submit = SubmitField('حفظ المنتج')

class AddToCartForm(FlaskForm):
    product_id = HiddenField(validators=[DataRequired()])
    quantity = IntegerField('الكمية', default=1, validators=[DataRequired(), NumberRange(min=1)])
    size = SelectField('الحجم', choices=[])
    color = SelectField('اللون', choices=[])
    submit = SubmitField('إضافة للسلة')

class DeleteForm(FlaskForm):
    submit = SubmitField('حذف')

# الصفحة الرئيسية
@app.route('/')
def index():
    products = Product.query.all()
    return render_template('index.html', products=products)

# صفحة المنتج
@app.route('/product/<int:id>')
def product_detail(id):
    product = Product.query.get_or_404(id)
    return render_template('product_detail.html', product=product)

# إضافة للسلة
@app.route('/add_to_cart', methods=['POST'])
def add_to_cart():
    if 'session_id' not in session:
        session['session_id'] = os.urandom(24).hex()
    
    try:
        product_id = int(request.form.get('product_id', 0))
        quantity = int(request.form.get('quantity', 1))
    except (ValueError, TypeError):
        flash('بيانات غير صالحة', 'error')
        return redirect(url_for('index'))
    
    # التحقق من وجود المنتج والمخزون
    product = Product.query.get(product_id)
    if not product:
        flash('المنتج غير موجود', 'error')
        return redirect(url_for('index'))
    
    if product.stock < quantity:
        flash('الكمية المطلوبة غير متوفرة', 'error')
        return redirect(url_for('product_detail', id=product_id))
    
    size = request.form.get('size')
    color = request.form.get('color')
    
    # البحث عن عنصر موجود
    existing_item = CartItem.query.filter_by(
        session_id=session['session_id'],
        product_id=product_id,
        size=size,
        color=color
    ).first()
    
    if existing_item:
        if product.stock < existing_item.quantity + quantity:
            flash('الكمية المطلوبة غير متوفرة', 'error')
            return redirect(url_for('product_detail', id=product_id))
        existing_item.quantity += quantity
    else:
        cart_item = CartItem()
        cart_item.session_id = session['session_id']
        cart_item.product_id = product_id
        cart_item.quantity = quantity
        cart_item.size = size
        cart_item.color = color
        db.session.add(cart_item)
    
    db.session.commit()
    flash('تم إضافة المنتج للسلة بنجاح!', 'success')
    return redirect(url_for('cart'))

# عرض السلة
@app.route('/cart')
def cart():
    if 'session_id' not in session:
        session['session_id'] = os.urandom(24).hex()
    
    cart_items = CartItem.query.filter_by(session_id=session['session_id']).all()
    total = sum(item.product.price * item.quantity for item in cart_items)
    return render_template('cart.html', cart_items=cart_items, total=total)

# حذف من السلة
@app.route('/remove_from_cart/<int:id>', methods=['POST'])
def remove_from_cart(id):
    cart_item = CartItem.query.get_or_404(id)
    if cart_item.session_id == session.get('session_id'):
        db.session.delete(cart_item)
        db.session.commit()
        flash('تم حذف المنتج من السلة', 'success')
    return redirect(url_for('cart'))

# لوحة الإدارة
@app.route('/admin')
def admin():
    products = Product.query.all()
    return render_template('admin.html', products=products)

# إضافة منتج جديد
@app.route('/admin/add_product', methods=['GET', 'POST'])
def add_product():
    form = ProductForm()
    if form.validate_on_submit():
        # معالجة الصورة
        image_url = None
        if form.image.data:
            filename = save_uploaded_image(form.image.data)
            if filename:
                image_url = f"uploads/{filename}"
        
        # معالجة الأحجام والألوان
        sizes = [s.strip() for s in form.sizes.data.split(',')] if form.sizes.data else []
        colors = [c.strip() for c in form.colors.data.split(',')] if form.colors.data else []
        
        product = Product()
        product.name = form.name.data
        product.description = form.description.data
        product.price = float(form.price.data) if form.price.data else 0.0
        product.category = form.category.data
        product.stock = form.stock.data
        product.image_url = image_url
        product.size_options = json.dumps(sizes)
        product.color_options = json.dumps(colors)
        
        db.session.add(product)
        db.session.commit()
        flash('تم إضافة المنتج بنجاح!', 'success')
        return redirect(url_for('admin'))
    
    return render_template('add_product.html', form=form)

# حذف منتج
@app.route('/admin/delete_product/<int:id>', methods=['POST'])
def delete_product(id):
    product = Product.query.get_or_404(id)
    
    # حذف صورة المنتج إن وجدت
    if product.image_url:
        image_path = os.path.join(app.config['UPLOAD_FOLDER'], product.image_url)
        if os.path.exists(image_path):
            try:
                os.remove(image_path)
            except OSError:
                pass
    
    db.session.delete(product)
    db.session.commit()
    flash('تم حذف المنتج بنجاح!', 'success')
    return redirect(url_for('admin'))

# تقديم الصور المرفوعة
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=5000, debug=True)