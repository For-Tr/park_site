from pathlib import Path
import os
import random
import string
import threading
import queue
import time
import paho.mqtt.client as mqtt
import logging
from datetime import datetime
from sqlalchemy import create_engine, Column, String, Table, MetaData, text
from sqlalchemy.orm import sessionmaker
import yaml

# 获取当前文件所在目录
CURRENT_DIR = Path(__file__).parent

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 全局变量保存实例
_mqtt_service_instance = None

def get_mqtt_service_instance():
    global _mqtt_service_instance
    if _mqtt_service_instance is None:
        _mqtt_service_instance = MQTTService()
    return _mqtt_service_instance

class MQTTService:
    def __init__(self):
        self.queue = {'parking':queue.Queue(),'check_screen':queue.Queue()}
        self.publish_queue = queue.Queue()
        self.is_running = True
        self.is_mqtt_connected = False
        self.lock = threading.Lock()

        # 只在初始化时读取一次配置
        self.config = self._load_config()

        self.client_id = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
        self.port = 1883
        self.qos = 1
        self.keepalive = 30

        # 初始化 MQTT 客户端
        self.client = mqtt.Client(client_id=self.client_id, transport="tcp")
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.on_message = self.on_message

        # 设置自动重连延迟
        self.client.reconnect_delay_set(min_delay=1, max_delay=120)

        # 线程管理
        self.threads = {}
        self.thread_functions = {
            'publish_thread': self.publish_thread_func
        }

    def _load_config(self):
        # 配置加载逻辑
        try:
            # 使用相对路径定义配置文件位置
            config_path = CURRENT_DIR / 'db' / 'config.yml'
            
            # 明确指定使用UTF-8编码打开文件
            with open(config_path, 'r', encoding='utf-8') as file:
                config = yaml.safe_load(file)
            
            # 获取配置值
            self.broker = self.clean_string(config['mqtt']['server'])
            self.subscribe_topic = self.clean_string(config['mqtt']['topics']['read'])
            self.publish_topic = self.clean_string(config['mqtt']['topics']['send'])
            
            logging.info(f"从YAML获取的配置信息_loop: broker={self.broker}, "
                        f"subscribe_topic={self.subscribe_topic}, "
                        f"publish_topic={self.publish_topic}")
                
        except Exception as e:
            logging.error(f"致命错误：加载配置失败: {e}")
            logging.error("无法继续运行，程序将退出")
            os._exit(1)
        return config

    def clean_string(self, s):
        """清理字符串中的无效字符"""
        # 移除所有空白字符和不可见字符
        return ''.join(c for c in s if c.isprintable()).strip()

    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            with self.lock:
                self.is_mqtt_connected = True
            logging.info("MQTT Connected successfully!")
            self.client.subscribe(self.subscribe_topic, qos=self.qos)
            logging.info(f"订阅主题: {self.subscribe_topic}")
        else:
            with self.lock:
                self.is_mqtt_connected = False
            logging.error(f"MQTT failed to connect, return code {rc}")

    def on_disconnect(self, client, userdata, rc):
        with self.lock:
            self.is_mqtt_connected = False
        if rc != 0:
            logging.warning("MQTT 连接意外断开。")
        else:
            logging.info("MQTT 连接已断开。")

    def on_message(self, client, userdata, msg):
        hex_data = msg.payload.hex()
        # logging.info(f"接收到消息: {hex_data}")
        self.handle_data(hex_data)

    def handle_data(self, hex_data):
        while "7e" in hex_data:
            start_index = hex_data.index("7e")
            if "0d" not in hex_data[start_index:]:
                logging.warning(f"在索引 {start_index} 后未找到 0d")
                break

            try:
                expected_length = int(hex_data[start_index + 2:start_index + 4], 16) * 2 + 8
            except ValueError:
                logging.error(f"无法解析长度字段: {hex_data[start_index + 2:start_index + 4]}")
                hex_data = hex_data[start_index + 2:]
                continue

            if len(hex_data) >= (start_index + expected_length):
                complete_packet = hex_data[start_index:(start_index + expected_length)]
                if complete_packet[-2:] == '0d':
                    self.process_data(complete_packet)  # 处理完整的数据包
                    hex_data = hex_data[(start_index + expected_length):]
                else:
                    logging.warning(f"完整包的结束标志错误: {complete_packet[-2:]}, 期待 '0d'")
                    hex_data = hex_data[(start_index + 2):]
            else:
                logging.warning("数据不完整，等待更多数据")
                break

    def process_data(self, data):
        timestamp = datetime.now()
        data_type = data[4:6].lower()
        if data_type == '9f':
            self.add_to_queue('parking', data, timestamp)
        elif data_type == '86':
            self.add_to_queue('check_screen', data, timestamp)
        else:
            pass
            # logging.warning(f"未知的数据类型: {data_type}")

    def add_to_queue(self, queue_name, data, timestamp):
        q = self.queue.get(queue_name)
        if q is not None:
            with self.lock:
                if q.full():
                    q.get()  # 如果队列满了，移除最旧的项目
                q.put((data, timestamp))
            # logging.info(f"添加数据到队列 {queue_name}: {data}")
        else:
            logging.warning(f"未找到队列: {queue_name}")

    def publish_message(self, message):
        with self.lock:
            self.publish_queue.put(message)

    def publish_thread_func(self):
        while self.is_running:
            if not self.publish_queue.empty() and self.is_mqtt_connected:
                message = self.publish_queue.get()
                retry_count = 0
                max_retries = 3  # 最大重试次数
                while retry_count < max_retries:
                    try:
                        # 将十六进制字符串转换为字节再发布
                        byte_message = bytes.fromhex(message)
                        # print(f"发布消息: {message}，{byte_message}")
                        result, mid = self.client.publish(self.publish_topic, byte_message, qos=self.qos)
                        if result == mqtt.MQTT_ERR_SUCCESS:
                            logging.info(f"消息{message}发布成功！")
                            break
                        else:
                            logging.error(f"消息{message}发布失败，返回码: {result}")
                            retry_count += 1
                    except ValueError as e:
                        logging.error(f"消息{message}发布失败 (十六进制字符串转换为字节时出错): {e}")
                        break
                    except Exception as e:
                        logging.error(f"消息{message}发布失败: {e}")
                        retry_count += 1
                    time.sleep(0.5)  # 重试前等待
            else:
                time.sleep(0.5)  # 避免过高的 CPU 占用

    def run(self):
        # 连接到 MQTT Broker
        try:
            logging.info(f"尝试连接到 broker: {self.broker}:{self.port}")
            self.client.connect(self.broker, self.port, self.keepalive)
        except Exception as e:
            logging.error(f"连接到 MQTT Broker 失败: {e}")
            self.is_mqtt_connected = False

        # 启动发布线程
        for name, func in self.thread_functions.items():
            print(f"启动线程: {name},{func}")
            thread = threading.Thread(target=func, name=name, daemon=True)
            print(f"启动线程a: {name},{thread}")
            self.threads[name] = thread
            thread.start()

        # 启动 MQTT 客户端的网络循环
        self.client.loop_start()
        logging.info("MQTT 网络循环已启动。")

    def start(self):
        self.run()

    def stop(self):
        self.is_running = False
        self.client.disconnect()
        self.client.loop_stop()
        logging.info("MQTT 服务已停止")

    def send_message(self, message):
        """发送消息到 MQTT"""
        self.publish_message(message)

    def read_queue(self, queue_name):
        """
        读取指定队列中的数据
        :param queue_name: 队列名称 ('node', 'panel', 'sub_router', 'parking')
        :return: (data, timestamp) 如果队列为空返回 (None, None)
        """
        if queue_name in self.queue:
            q = self.queue[queue_name]
            if not q.empty():
                return q.get()  # 返回 (data, timestamp)
        return None, None

    def clean_queue(self, queue_name=None):
        """
        清空指定队列或所有队列
        :param queue_name: 队列名称 ('node', 'panel', 'sub_router')，如果为 None 则清空所有队列
        """
        with self.lock:  # 使用锁确保线程安全
            if queue_name is None:
                # 清空所有队列
                for q_name in self.queue:
                    while not self.queue[q_name].empty():
                        self.queue[q_name].get()
                logging.info("所有队列已清空")
            elif queue_name in self.queue:
                # 清空指定队列
                while not self.queue[queue_name].empty():
                    self.queue[queue_name].get()
                logging.info(f"队列 {queue_name} 已清空")
            else:
                logging.warning(f"未找到队列: {queue_name}")

if __name__ == "__main__":
   
   
    mqtt_service = get_mqtt_service_instance()
    mqtt_service.start()
    try:
        mqtt_service.run()
        
        last_send_time = 0
        check_interval = 0.5  # 每0.5秒检查一次队列
        send_interval = 30    # 每30秒发送一次消息
        
        while mqtt_service.is_running:
            current_time = time.time()
            
            # 每30秒发送一次消息
            # if current_time - last_send_time >= send_interval:
            #     mqtt_service.send_message('7e0d1fffffffffffffffffffffffff000d')
            #     last_send_time = current_time
            
            # 检查所有队列的数据
            for queue_name in ['node', 'panel', 'sub_router', 'parking']:
                while True:
                    data, timestamp = mqtt_service.read_queue(queue_name)
                    if not data:
                        break
                    print(f"从队列 {queue_name} 中获取数据: {data}, 时间戳: {timestamp}")
                    logging.info(f"从队列 {queue_name} 中获取数据: {data}, 时间戳: {timestamp}")
            
            time.sleep(check_interval)
                
    except KeyboardInterrupt:
        mqtt_service.stop()
        logging.info("程序已退出")
