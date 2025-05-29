# 使用 django 最新版本作为基础镜像
FROM python:3.8-slim

# 设置工作目录
WORKDIR /www

# 安装系统依赖
RUN apt-get update -y && \
    apt-get install -y --no-install-recommends \
        python3-dev \
        sqlite3 \
        procps \
        supervisor \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 复制 requirements.txt 并安装 Python 依赖
COPY requirements.txt /www/
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -i https://mirrors.aliyun.com/pypi/simple -r requirements.txt

# 复制应用代码到工作目录
COPY . /www/
RUN python3 manage.py collectstatic --noinput

# 创建日志目录并设置权限
RUN mkdir -p /var/log/supervisor && \
    chmod 755 /var/log/supervisor && \
    chown root:root /var/log/supervisor

COPY parking.conf /etc/supervisor/conf.d/parking.conf

# 复制并设置启动脚本权限
# COPY run_mqtt.sh /www/
RUN chmod +x /www/run_mqtt.sh

# 设置环境变量
ENV PYTHONUNBUFFERED=1
ENV DJANGO_SETTINGS_MODULE=backend_try.settings

# 暴露端口（Django 和 MQTT）
EXPOSE 5000 1883

# 使用 supervisor 启动服务
CMD ["/usr/bin/supervisord", "-n", "-c", "/etc/supervisor/conf.d/parking.conf"]

