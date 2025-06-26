from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from models import db, User, Category, Transaction
from config import config
from datetime import datetime
from werkzeug.utils import secure_filename
import os


def create_app(config_name='default'):
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    config[config_name].init_app(app)

    # 初始化数据库
    db.init_app(app)

    login_manager = LoginManager(app)
    login_manager.login_view = 'login'
    login_manager.login_message = '请登录以访问此页面。'

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # 创建上传文件夹
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])

    # 路由和视图
    @app.route('/')
    @login_required
    def index():
        # 获取最近的交易记录
        recent_transactions = Transaction.query.filter_by(user_id=current_user.id) \
            .order_by(Transaction.date.desc()).limit(5).all()

        # 计算总计
        total_income = db.session.query(db.func.sum(Transaction.amount)) \
                           .filter_by(user_id=current_user.id, type='income').scalar() or 0
        total_expense = db.session.query(db.func.sum(Transaction.amount)) \
                            .filter_by(user_id=current_user.id, type='expense').scalar() or 0
        balance = total_income - total_expense

        return render_template('index.html',
                               recent_transactions=recent_transactions,
                               total_income=total_income,
                               total_expense=total_expense,
                               balance=balance)

    @app.route('/transactions')
    @login_required
    def transactions():
        page = request.args.get('page', 1, type=int)
        type_filter = request.args.get('type')
        start_date_filter = request.args.get('start_date')
        end_date_filter = request.args.get('end_date')

        query = Transaction.query.filter_by(user_id=current_user.id)

        if type_filter:
            query = query.filter(Transaction.type == type_filter)

        if start_date_filter:
            start_date = datetime.strptime(start_date_filter, '%Y-%m-%d')
            query = query.filter(Transaction.date >= start_date)

        if end_date_filter:
            end_date = datetime.strptime(end_date_filter, '%Y-%m-%d')
            query = query.filter(Transaction.date <= end_date)

        transactions = query.order_by(Transaction.date.desc()) \
            .paginate(page=page, per_page=app.config['TRANSACTIONS_PER_PAGE'], error_out=False)

        return render_template('transactions.html', transactions=transactions)

    @app.route('/add_transaction', methods=['GET', 'POST'])
    @login_required
    def add_transaction():
        from datetime import datetime
        today = datetime.today().strftime('%Y-%m-%d')  # 获取当前日期

        if request.method == 'POST':
            amount = float(request.form['amount'])
            description = request.form['description']
            type_ = request.form['type']
            category_id = request.form.get('category_id')
            date = datetime.strptime(request.form['date'], '%Y-%m-%d')

            transaction = Transaction(
                amount=amount,
                description=description,
                type=type_,
                date=date,
                user_id=current_user.id,
                category_id=category_id if category_id else None
            )

            db.session.add(transaction)
            db.session.commit()
            flash('交易已添加', 'success')
            return redirect(url_for('transactions'))

        # 获取用户的分类
        categories = Category.query.filter_by(user_id=current_user.id).all()
        return render_template('add_transaction.html', categories=categories, today=today)

    @app.route('/categories')
    @login_required
    def categories():
        income_categories = Category.query.filter_by(
            user_id=current_user.id, type='income').all()
        expense_categories = Category.query.filter_by(
            user_id=current_user.id, type='expense').all()
        return render_template('categories.html',
                               income_categories=income_categories,
                               expense_categories=expense_categories)

    @app.route('/add_category', methods=['POST'])
    @login_required
    def add_category():
        name = request.form['name']
        type_ = request.form['type']

        if not name:
            flash('分类名称不能为空', 'danger')
            return redirect(url_for('categories'))

        category = Category(name=name, type=type_, user_id=current_user.id)
        db.session.add(category)
        db.session.commit()
        flash('分类已添加', 'success')
        return redirect(url_for('categories'))

    @app.route('/delete_category/<int:id>')
    @login_required
    def delete_category(id):
        category = Category.query.get_or_404(id)
        if category.user_id != current_user.id:
            flash('无权删除此分类', 'danger')
            return redirect(url_for('categories'))

        db.session.delete(category)
        db.session.commit()
        flash('分类已删除', 'success')
        return redirect(url_for('categories'))

    @app.route('/reports')
    @login_required
    def reports():
        # 按分类统计支出
        expense_by_category = db.session.query(
            Category.name,
            db.func.sum(Transaction.amount)
        ).join(Transaction) \
            .filter(Transaction.user_id == current_user.id,
                    Transaction.type == 'expense') \
            .group_by(Category.name).all()

        # 月度统计
        monthly_stats = db.session.query(
            db.func.strftime('%Y-%m', Transaction.date).label('month'),
            db.func.sum(db.case([(Transaction.type == 'income', Transaction.amount)], else_=0)).label('income'),
            db.func.sum(db.case([(Transaction.type == 'expense', Transaction.amount)], else_=0)).label('expense')
        ).filter(Transaction.user_id == current_user.id) \
            .group_by('month') \
            .order_by('month').all()

        return render_template('reports.html',
                               expense_by_category=expense_by_category,
                               monthly_stats=monthly_stats)

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for('index'))

        if request.method == 'POST':
            username = request.form['username']
            password = request.form['password']
            remember = request.form.get('remember', False)

            user = User.query.filter_by(username=username).first()
            if user and user.check_password(password):
                login_user(user, remember=remember)
                next_page = request.args.get('next')
                return redirect(next_page or url_for('index'))
            else:
                flash('用户名或密码无效', 'danger')

        return render_template('login.html')

    @app.route('/logout')
    def logout():
        logout_user()
        return redirect(url_for('login'))

    @app.route('/register', methods=['GET', 'POST'])
    def register():
        if current_user.is_authenticated:
            return redirect(url_for('index'))

        if request.method == 'POST':
            username = request.form['username']
            email = request.form['email']
            password = request.form['password']
            confirm_password = request.form['confirm_password']

            if password != confirm_password:
                flash('两次输入的密码不一致', 'danger')
                return redirect(url_for('register'))

            if User.query.filter_by(username=username).first():
                flash('用户名已存在', 'danger')
                return redirect(url_for('register'))

            if User.query.filter_by(email=email).first():
                flash('邮箱已存在', 'danger')
                return redirect(url_for('register'))

            user = User(username=username, email=email)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()

            # 创建默认分类
            default_categories = [
                ('工资', 'income'),
                ('奖金', 'income'),
                ('投资收益', 'income'),
                ('餐饮', 'expense'),
                ('交通', 'expense'),
                ('购物', 'expense'),
                ('娱乐', 'expense'),
                ('住房', 'expense'),
                ('医疗', 'expense')
            ]

            for name, type_ in default_categories:
                category = Category(name=name, type=type_, user_id=user.id)
                db.session.add(category)

            db.session.commit()

            flash('注册成功，请登录。', 'success')
            return redirect(url_for('login'))

        return render_template('register.html')

    # 错误处理
    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('404.html'), 404

    @app.errorhandler(500)
    def internal_server_error(e):
        return render_template('500.html'), 500

    return app


if __name__ == '__main__':
    app = create_app()
    with app.app_context():
        db.create_all()
    app.run(debug=True)