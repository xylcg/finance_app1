import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    # 安全配置
    SECRET_KEY = os.getenv('SECRET_KEY') or 'your-secret-key-here'
    
    # 数据库配置
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'finance.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # 分页配置
    TRANSACTIONS_PER_PAGE = 10
    
    # 货币配置
    CURRENCY = 'CNY'
    
    # 上传配置
    UPLOAD_FOLDER = os.path.join(basedir, 'uploads')
    ALLOWED_EXTENSIONS = {'csv', 'xlsx'}
    
    @staticmethod
    def init_app(app):
        # 可以在这里添加初始化逻辑
        pass

class DevelopmentConfig(Config):
    DEBUG = True

class ProductionConfig(Config):
    DEBUG = False

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}