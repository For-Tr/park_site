from gunicorn.app.base import BaseApplication
import os
import sys

# 添加项目根目录到 Python 路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 设置 Django 环境变量
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend_try.settings')

# 导入 Django WSGI 应用
from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()

class GunicornApplication(BaseApplication):
    def __init__(self, app, options=None):
        self.options = options or {}
        self.application = app
        super().__init__()

    def load_config(self):
        for key, value in self.options.items():
            self.cfg.set(key, value)

    def load(self):
        return self.application

if __name__ == '__main__':
    # gunicorn 配置
    options = {
        'bind': '0.0.0.0:5000',
        'workers': 3,              # (2 × CPU核心数) + 1
        'worker_class': 'sync',    
        'preload_app': True,
        'reload': False,
        'timeout': 60,            # 工作进程超时时间
        'keepalive': 2,          # keep-alive 连接超时
        'max_requests': 1000,    # 工作进程处理多少请求后重启
        'max_requests_jitter': 50 # 添加随机性防止同时重启
    }
    
    # 启动 gunicorn
    GunicornApplication(application, options).run()
