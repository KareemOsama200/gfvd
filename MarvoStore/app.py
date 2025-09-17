from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from flask_wtf.csrf import CSRFProtect
from wtforms import StringField, TextAreaField, DecimalField, IntegerField, SelectField, FileField, SubmitField, HiddenField, PasswordField, BooleanField, EmailField
from wtforms.validators import DataRequired, NumberRange, Email, Length, EqualTo
from werkzeug.utils import secure_filename
from PIL import Image
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import os
import json
import uuid
from datetime import datetime
import secrets
import string

app = Flask(__name__)

# إنشاء مجلد instance بمسار مطلق
os.makedirs(app.instance_path, exist_ok=True)

# Require SECRET_KEY in production
if os.environ.get('FLASK_ENV') == 'production' and not os.environ.get('SESSION_SECRET'):
    raise RuntimeError("SESSION_SECRET environment variable is required in production")
app.config['SECRET_KEY'] = os.environ.get('SESSION_SECRET', 'dev-key-change-in-production')
db_path = os.path.join(app.instance_path, 'marvo_store.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# CSRF Protection
csrf = CSRFProtect(app)

# Login Manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'يرجى تسجيل الدخول للوصول لهذه الصفحة'
login_manager.login_message_category = 'info'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

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

# نموذج المستخدم
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    first_name = db.Column(db.String(50))
    last_name = db.Column(db.String(50))
    phone = db.Column(db.String(15))
    address = db.Column(db.Text)
    city = db.Column(db.String(50))
    governorate = db.Column(db.String(50))
    points = db.Column(db.Integer, default=0)
    referral_code = db.Column(db.String(10), unique=True)
    referred_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def generate_referral_code(self):
        if not self.referral_code:
            self.referral_code = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8))
            return self.referral_code

    def get_full_name(self):
        return f"{self.first_name or ''} {self.last_name or ''}".strip() or self.username

# نموذج الطلب
class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    order_number = db.Column(db.String(20), unique=True, nullable=False)
    total_amount = db.Column(db.Float, nullable=False)
    donation_amount = db.Column(db.Float, default=0)  # مبلغ التبرع
    payment_method = db.Column(db.String(20), default='cod')  # cash on delivery
    status = db.Column(db.String(20), default='pending')  # pending, confirmed, shipped, delivered, cancelled
    shipping_address = db.Column(db.Text)
    phone = db.Column(db.String(15))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    confirmed_at = db.Column(db.DateTime)
    shipped_at = db.Column(db.DateTime)
    delivered_at = db.Column(db.DateTime)

    user = db.relationship('User', backref=db.backref('orders', lazy=True))

    def generate_order_number(self):
        if not self.order_number:
            timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
            self.order_number = f"MRV{timestamp}"

# عناصر الطلب
class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Float, nullable=False)  # السعر وقت الطلب
    size = db.Column(db.String(20))
    color = db.Column(db.String(50))

    order = db.relationship('Order', backref=db.backref('items', lazy=True))
    product = db.relationship('Product')

# نموذج التقييمات
class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    rating = db.Column(db.Integer, nullable=False)  # من 1 إلى 5
    comment = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('reviews', lazy=True))
    product = db.relationship('Product', backref=db.backref('reviews', lazy=True))

# نموذج مقارنة المنتجات
class Comparison(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('comparisons', lazy=True))
    product = db.relationship('Product')

# نموذج نقاط المستخدم
class UserPoints(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    points = db.Column(db.Integer, nullable=False)
    reason = db.Column(db.String(100))  # order, referral, review
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('points_history', lazy=True))
    order = db.relationship('Order')

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

# فورمات المستخدمين
class LoginForm(FlaskForm):
    email = EmailField('البريد الإلكتروني', validators=[DataRequired(), Email()])
    password = PasswordField('كلمة المرور', validators=[DataRequired()])
    remember_me = BooleanField('تذكرني')
    submit = SubmitField('تسجيل الدخول')

class RegisterForm(FlaskForm):
    username = StringField('اسم المستخدم', validators=[DataRequired(), Length(min=4, max=20)])
    email = EmailField('البريد الإلكتروني', validators=[DataRequired(), Email()])
    password = PasswordField('كلمة المرور', validators=[DataRequired(), Length(min=6)])
    password2 = PasswordField('تأكيد كلمة المرور', validators=[DataRequired(), EqualTo('password')])
    first_name = StringField('الاسم الأول', validators=[DataRequired()])
    last_name = StringField('اسم العائلة', validators=[DataRequired()])
    phone = StringField('رقم الهاتف', validators=[DataRequired()])
    address = TextAreaField('العنوان', validators=[DataRequired()])
    city = StringField('المدينة', validators=[DataRequired()])
    governorate = SelectField('المحافظة', choices=[
        ('cairo', 'القاهرة'),
        ('giza', 'الجيزة'),
        ('alexandria', 'الإسكندرية'),
        ('qalyubia', 'القليوبية'),
        ('sharqia', 'الشرقية'),
        ('dakahlia', 'الدقهلية'),
        ('beheira', 'البحيرة'),
        ('kafr_el_sheikh', 'كفر الشيخ'),
        ('gharbia', 'الغربية'),
        ('menoufia', 'المنوفية'),
        ('damietta', 'دمياط'),
        ('port_said', 'بورسعيد'),
        ('ismailia', 'الإسماعيلية'),
        ('suez', 'السويس'),
        ('north_sinai', 'شمال سيناء'),
        ('south_sinai', 'جنوب سيناء'),
        ('beni_suef', 'بني سويف'),
        ('fayyum', 'الفيوم'),
        ('minya', 'المنيا'),
        ('assiut', 'أسيوط'),
        ('sohag', 'سوهاج'),
        ('qena', 'قنا'),
        ('luxor', 'الأقصر'),
        ('aswan', 'أسوان'),
        ('red_sea', 'البحر الأحمر'),
        ('new_valley', 'الوادي الجديد'),
        ('matrouh', 'مطروح')
    ], validators=[DataRequired()])
    referral_code = StringField('كود الإحالة (اختياري)')
    submit = SubmitField('إنشاء حساب')

class CheckoutForm(FlaskForm):
    shipping_address = TextAreaField('عنوان الشحن', validators=[DataRequired()])
    phone = StringField('رقم الهاتف', validators=[DataRequired()])
    notes = TextAreaField('ملاحظات (اختياري)')
    donation = BooleanField('أضف 1 جنيه للتبرع الخيري ❤️')
    submit = SubmitField('تأكيد الطلب')

class ReviewForm(FlaskForm):
    rating = SelectField('التقييم', choices=[(5, '5 نجوم - ممتاز'), (4, '4 نجوم - جيد جداً'), (3, '3 نجوم - جيد'), (2, '2 نجوم - مقبول'), (1, '1 نجمة - سيء')], coerce=int, validators=[DataRequired()])
    comment = TextAreaField('التعليق')
    submit = SubmitField('إرسال التقييم')

class SearchForm(FlaskForm):
    query = StringField('البحث عن المنتجات...')
    category = SelectField('الفئة', choices=[('', 'كل الفئات'), ('shirts', 'قمصان'), ('pants', 'بناطيل'), ('shoes', 'أحذية'), ('accessories', 'إكسسوارات')])
    min_price = DecimalField('أقل سعر')
    max_price = DecimalField('أعلى سعر')
    submit = SubmitField('بحث')

# helper functions للعملة
@app.template_filter('currency')
def currency_filter(amount):
    return f"{amount:.2f} ج.م"

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

# رووتات المستخدمين
@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    form = RegisterForm()
    if form.validate_on_submit():
        # التحقق من عدم وجود المستخدم
        if User.query.filter_by(username=form.username.data).first():
            flash('اسم المستخدم موجود بالفعل', 'error')
            return render_template('register.html', form=form)
        
        if User.query.filter_by(email=form.email.data).first():
            flash('البريد الإلكتروني مسجل بالفعل', 'error')
            return render_template('register.html', form=form)
        
        # إنشاء المستخدم الجديد
        user = User()
        user.username = form.username.data
        user.email = form.email.data
        user.set_password(form.password.data)
        user.first_name = form.first_name.data
        user.last_name = form.last_name.data
        user.phone = form.phone.data
        user.address = form.address.data
        user.city = form.city.data
        user.governorate = form.governorate.data
        user.generate_referral_code()
        
        # معالجة كود الإحالة
        if form.referral_code.data:
            referrer = User.query.filter_by(referral_code=form.referral_code.data).first()
            if referrer:
                user.referred_by = referrer.id
                # إضافة نقاط للمُحيل
                referrer.points += 50
        
        db.session.add(user)
        db.session.commit()
        
        flash('تم إنشاء حسابك بنجاح!', 'success')
        login_user(user)
        return redirect(url_for('index'))
    
    return render_template('register.html', form=form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and user.check_password(form.password.data):
            login_user(user, remember=form.remember_me.data)
            next_page = request.args.get('next')
            if not next_page or not next_page.startswith('/'):
                next_page = url_for('index')
            return redirect(next_page)
        flash('بريد إلكتروني أو كلمة مرور خاطئة', 'error')
    
    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('تم تسجيل الخروج بنجاح', 'success')
    return redirect(url_for('index'))

@app.route('/profile')
@login_required
def profile():
    orders = Order.query.filter_by(user_id=current_user.id).order_by(Order.created_at.desc()).all()
    return render_template('profile.html', user=current_user, orders=orders)

# Checkout محدث
@app.route('/checkout', methods=['GET', 'POST'])
@login_required
def checkout():
    if 'session_id' not in session:
        flash('سلة التسوق فارغة', 'error')
        return redirect(url_for('cart'))
    
    cart_items = CartItem.query.filter_by(session_id=session['session_id']).all()
    if not cart_items:
        flash('سلة التسوق فارغة', 'error')
        return redirect(url_for('cart'))
    
    form = CheckoutForm()
    form.shipping_address.data = current_user.address
    form.phone.data = current_user.phone
    
    if form.validate_on_submit():
        # حساب المجموع
        total = sum(item.product.price * item.quantity for item in cart_items)
        donation = 1.0 if form.donation.data else 0.0
        
        # إنشاء الطلب
        order = Order()
        order.user_id = current_user.id
        order.generate_order_number()
        order.total_amount = total
        order.donation_amount = donation
        order.shipping_address = form.shipping_address.data
        order.phone = form.phone.data
        order.notes = form.notes.data
        
        db.session.add(order)
        db.session.flush()  # للحصول على order.id
        
        # إضافة عناصر الطلب
        for item in cart_items:
            order_item = OrderItem()
            order_item.order_id = order.id
            order_item.product_id = item.product_id
            order_item.quantity = item.quantity
            order_item.price = item.product.price
            order_item.size = item.size
            order_item.color = item.color
            db.session.add(order_item)
        
        # حذف عناصر السلة
        for item in cart_items:
            db.session.delete(item)
        
        # إضافة نقاط للمستخدم (نقطة واحدة لكل جنيه)
        points = int(total)
        current_user.points += points
        user_points = UserPoints()
        user_points.user_id = current_user.id
        user_points.points = points
        user_points.reason = 'order'
        user_points.order_id = order.id
        db.session.add(user_points)
        
        db.session.commit()
        
        flash(f'تم تأكيد طلبك رقم {order.order_number} بنجاح!', 'success')
        return redirect(url_for('order_tracking', order_number=order.order_number))
    
    total = sum(item.product.price * item.quantity for item in cart_items)
    return render_template('checkout.html', form=form, cart_items=cart_items, total=total)

@app.route('/order_tracking/<order_number>')
@login_required
def order_tracking(order_number):
    order = Order.query.filter_by(order_number=order_number, user_id=current_user.id).first_or_404()
    return render_template('order_tracking.html', order=order)

# Initialize database tables on startup
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug)