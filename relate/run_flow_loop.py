import time
import logging
from mqtt_connect_loop import get_mqtt_service_instance
import re
import random
import threading
from sqlalchemy import ( 
    create_engine, Column, Integer, String, ForeignKey, 
    CHAR, TIMESTAMP, UniqueConstraint, Index, func, select, inspect, text,
    Table, MetaData, event
)
from sqlalchemy.orm import relationship, sessionmaker, scoped_session, declarative_base
from collections import defaultdict
from contextlib import contextmanager
from pathlib import Path


Base = declarative_base()

# 获取当前文件所在目录
CURRENT_DIR = Path(__file__).parent

# -----------------------------
# ORM Models
# -----------------------------

class SiteConfigeration(Base):
    __tablename__ = 'SiteConfigeration'  # 保持与旧数据库一致，如果拼写有误，请修正
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    company_name = Column(String(255), unique=True, default="My Company")
    version = Column(String(20), default="1.0.0")
    development_date = Column(String(20), nullable=True)
    name = Column(String(255), nullable=True)
    server = Column(String(255), nullable=True)
    user = Column(String(255), nullable=True)
    password = Column(String(255), nullable=True)
    send = Column(String(255), nullable=True)
    read = Column(String(255), nullable=True)

class SubRouter(Base):
    __tablename__ = 'sub_routers'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    address = Column(String, unique=True, nullable=False)
    name = Column(String(255), nullable=False)  # 描述子路由器的位置
    
    # Relationships
    sensors = relationship('Sensor', back_populates='sub_router', cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('idx_sub_routers_address', 'address', unique=True),
    )


class Sensor(Base):
    __tablename__ = 'sensors'
    id = Column(Integer, primary_key=True)
    address = Column(String, unique=True, nullable=False)
    
    # 新增的外键列
    sub_router_id = Column(Integer, ForeignKey('sub_routers.id', ondelete='SET NULL'), nullable=True)
    
    # Relationships
    car_space_mappings = relationship(
        'SensorCarSpaceMapping',
        back_populates='sensor',
        cascade="all, delete-orphan"
    )
    sub_router = relationship('SubRouter', back_populates='sensors')
    
    __table_args__ = (
        Index('idx_sensors_address', 'address', unique=True),
        Index('idx_sensors_sub_router_id', 'sub_router_id'),
    )


class CarSpace(Base):
    __tablename__ = 'car_spaces'
    id = Column(Integer, primary_key=True)
    position_description = Column(String, unique=True, nullable=False)

    # Relationships
    status = relationship(
        'CarSpaceStatus',
        back_populates='car_space',
        uselist=False,
        cascade="all, delete-orphan"
    )
    sensor_mapping = relationship(
        'SensorCarSpaceMapping',
        back_populates='car_space',
        uselist=False,
        cascade="all, delete-orphan"
    )
    group_mappings = relationship(
        'CarSpaceGroupMapping',
        back_populates='car_space',
        cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index('idx_car_spaces_position_description', 'position_description', unique=True),
    )


class SensorCarSpaceMapping(Base):
    __tablename__ = 'sensor_car_space_mapping'
    sensor_id = Column(
        Integer,
        ForeignKey('sensors.id', ondelete='CASCADE'),
        primary_key=True
    )
    sensor_position = Column(Integer, primary_key=True, nullable=False)  # 1-3为共同主键
    car_space_id = Column(
        Integer,
        ForeignKey('car_spaces.id', ondelete='CASCADE'),
        nullable=False,
        unique=True  # 确保每个车位只能映射一次
    )

    # Relationships
    sensor = relationship('Sensor', back_populates='car_space_mappings')
    car_space = relationship('CarSpace', back_populates='sensor_mapping')

    __table_args__ = (
        UniqueConstraint('car_space_id', name='_car_space_id_uc'),  # 确保每个车位只能映射一次
    )


class CarSpaceStatus(Base):
    __tablename__ = 'car_space_status'
    car_space_id = Column(
        Integer,
        ForeignKey('car_spaces.id', ondelete='CASCADE'),
        primary_key=True
    )
    license_plate = Column(String, nullable=True)
    position = Column(String, nullable=True)
    status = Column(CHAR(1), nullable=False, default='A')  # 'A' or 'B'
    last_updated = Column(
        TIMESTAMP,
        server_default=func.now(),
        onupdate=func.now()
    )

    # Relationships
    car_space = relationship('CarSpace', back_populates='status')

    __table_args__ = (
        Index('idx_car_space_status_license_plate', 'license_plate'), #新加的索引，用于查询车牌号优化
        Index('idx_car_space_status_status', 'status'),
    )


class GuideScreen(Base):
    __tablename__ = 'guide_screens'
    id = Column(Integer, primary_key=True)
    address = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=True)  # 新增字段，用于显示器命名

    # Relationships
    car_space_groups = relationship(
        'CarSpaceGroup',
        back_populates='guide_screen',
        cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index('idx_guide_screens_address', 'address', unique=True),
    )


class CarSpaceGroup(Base):
    __tablename__ = 'car_space_groups'
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    section_number = Column(Integer, nullable=False)  # 新增字段，表示引导屏的段编号

    # 新增的外键列
    guide_screen_id = Column(
        Integer,
        ForeignKey('guide_screens.id', ondelete='CASCADE'),
        nullable=False
    )

    # Relationships
    guide_screen = relationship('GuideScreen', back_populates='car_space_groups')
    car_space_mappings = relationship(
        'CarSpaceGroupMapping',
        back_populates='car_space_group',
        cascade="all, delete-orphan"
    )


class CarSpaceGroupMapping(Base):
    __tablename__ = 'car_space_group_mapping'
    car_space_group_id = Column(
        Integer,
        ForeignKey('car_space_groups.id', ondelete='CASCADE'),
        primary_key=True
    )
    car_space_id = Column(
        Integer,
        ForeignKey('car_spaces.id', ondelete='CASCADE'),
        primary_key=True
    )

    # Relationships
    car_space_group = relationship('CarSpaceGroup', back_populates='car_space_mappings')
    car_space = relationship('CarSpace', back_populates='group_mappings')

    __table_args__ = (
        Index('idx_car_space_group_mapping_car_space_id', 'car_space_id'),
        Index('idx_car_space_group_mapping_car_space_group_id', 'car_space_group_id'),
    )


class CheckScreen(Base):
    __tablename__ = 'check_screens'
    id = Column(Integer, primary_key=True)
    address = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=True)  # 显示器命名
    last_updated = Column(
        TIMESTAMP,
        server_default=func.now(),
        onupdate=func.now()
    )

    __table_args__ = (
        Index('idx_check_screens_address', 'address', unique=True),
    )

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class MQTTMonitor:
    def __init__(self):
        self.mqtt_service = get_mqtt_service_instance()
        self.init_sent = True
        self.is_running = True
        self.update_interval = 5
        self.new_display_data = []
        self.updated_car_space_ids = set()
        self.lock = threading.Lock()

        # 在初始化时读取消息发送配置，默认为True除非明确设置为False
        self.enable_send = self.mqtt_service.config.get('mqtt', {}).get('message_control', {}).get('enable_send', True)
        logging.info(f"消息发送状态: {'启用' if self.enable_send else '禁用'}")

        # 使用相对路径创建数据库连接
        db_path = CURRENT_DIR / 'db' / 'parking_system.db'
        self.new_engine = create_engine(
            f'sqlite:///{db_path}',
            echo=False,
            connect_args={
                "check_same_thread": False,  # 允许多线程访问
                "timeout": 20               # 设置超时时间（秒）
            },
            # pool_size=20,          # 连接池大小
            # max_overflow=10,       # 允许的最大溢出连接数
            # pool_timeout=30,       # 获取连接的超时时间
            # pool_recycle=1800     # 连接回收时间（秒）
        )
        self.Session = scoped_session(sessionmaker(bind=self.new_engine))

        # 设置 SQLite 优化参数
        @event.listens_for(self.new_engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            # 使用 DELETE 模式代替 WAL 模式，更安全但性能稍低
            cursor.execute("PRAGMA journal_mode=DELETE")
            # 设置页缓存大小（默认为-2000，可根据内存调整）
            cursor.execute("PRAGMA page_size=4096")
            cursor.execute("PRAGMA cache_size=-2000")
            # 使用 FULL 同步以确保数据完整性
            cursor.execute("PRAGMA synchronous=NORMAL")
            # 设置繁忙超时
            cursor.execute("PRAGMA busy_timeout=5000")
            # 设置合理的内存映射限制（例如 64MB）
            cursor.execute("PRAGMA mmap_size=67108864")
            cursor.close()

        # 启动定期处理线程
        self.processing_thread = threading.Thread(target=self.process_updates_periodically, daemon=True)
        self.processing_thread.start()
        
    @contextmanager
    def get_session(self):
        session = self.Session()
        try:
            yield session
            session.commit()
        except Exception as e:
            logging.error(f"Session 出现异常: {e}")
            session.rollback()
            raise
        finally:
            self.Session.remove()

    def start(self):
        """启动MQTT监控"""
        try:
            logging.info("启动MQTT监控服务...")
            # 启动MQTT服务
            self.mqtt_service.start()
            self.init_sent = True
            # 启动一个独立线程来处理队列
            queue_thread = threading.Thread(target=self.monitor_queues, daemon=True)
            queue_thread.start()
            
            # 主循环
            while self.is_running:
                try:
                    if self.init_sent:
                        # 发送心跳消息
                        self.mqtt_service.send_message('7e0d1fffffffffffffffffffffffff000d') #先注释掉
                        self.init_sent = False 
                        
                except Exception as e:
                    logging.error(f"监控过程中出现错误: {e}")
                    time.sleep(5)  # 发生错误时等待5秒后继续
                    
        except Exception as e:
            logging.error(f"启动监控服务失败: {e}")
        finally:
            self.stop()

    def monitor_queues(self):
        """监控并处理MQTT消息队列"""
        queue_names = ['parking','check_screen']  # 后续可以添加更多队列
        while self.is_running:
            try:
                for queue_name in queue_names:
                    while True:
                        data, timestamp = self.mqtt_service.read_queue(queue_name)
                        if not data:
                            break
                        
                        # 添加打印语句显示读取到的数据
                        # logging.info(f"从队列 {queue_name} 读取数据: {data}... (长度: {len(data)})")
                        
                        if queue_name == 'parking':
                            self.handle_parking_data(data, timestamp)
                        elif queue_name == 'check_screen':
                            self.handle_check_screen_data(data,timestamp)
            except Exception as e:
                logging.error(f"监控队列过程中出现错误: {e}")
            time.sleep(1)  # 防止CPU占用过高
                
    def handle_check_screen_data(self, data,timestamp):
        """更新检查屏幕的最后更新时间"""
        with self.get_session() as session:
            address = data[6:18]
            # 直接执行更新操作
            session.query(CheckScreen).filter_by(address=address).update(
                {"last_updated": timestamp}
            )
            # logging.info(f"更新检查屏幕 {address} 的最后更新时间为 {timestamp}")
            session.commit()    

    def handle_parking_data(self, data, timestamp):
        """处理接收到的停车数据并更新数据库"""
        with self.get_session() as session:
            xa=(data[124:126]+data[122:124])
            xb=(data[128:130]+data[126:128])
            xc=(data[132:134]+data[130:132])
            xd=(data[136:138]+data[134:136])
            xe=(data[140:142]+data[138:140])
            xf=(data[144:146]+data[142:144])
            ya = 0 if int(xa,16) > 800 else int(xa,16)
            yb = 0 if int(xb,16) > 800 else int(xb,16)
            yc = 0 if int(xc,16) > 800 else int(xc,16)
            yd = 0 if int(xd,16) > 800 else int(xd,16)
            ye = 0 if int(xe,16) > 800 else int(xe,16)
            yf = 0 if int(xf,16) > 800 else int(xf,16)
            data_dict = {
                'timestamp': timestamp,
                'node': data[18:30],
                'pl': self.d_hex(data[32:62]),
                'pm': self.d_hex(data[62:92]),
                'pr': self.d_hex(data[92:122]),
                'xl': f'{ya}，{yb}',
                'xm': f'{yc}，{yd}',
                'xr': f'{ye}，{yf}'    
            }
            # 只打印关键信息
            logging.info({
                'node': data_dict['node'],
                '位置1': data_dict['pl'],
                '位置2': data_dict['pm'],
                '位置3': data_dict['pr']
            })

            upload_data = []
            # 左侧车位
            spot_l = (data_dict['node'], 1, data_dict['pl'], 'B' if data_dict['pl'] else 'A', data_dict['xl'])
            upload_data.append(spot_l)

            # 中间车位
            spot_m = (data_dict['node'], 2, data_dict['pm'], 'B' if data_dict['pm'] else 'A', data_dict['xm'])
            upload_data.append(spot_m)

            # 右侧车位
            spot_r = (data_dict['node'], 3, data_dict['pr'], 'B' if data_dict['pr'] else 'A', data_dict['xr'])
            upload_data.append(spot_r)

            self.process_daily_upload(upload_data, session)

    def map_group_to_section(self, group_name):
        """将群组名称映射到段编号"""
        try:
            return int(group_name)
        except ValueError:
            logging.warning(f"群组名称无法映射到段编号: {group_name}")
            return None
    
    def process_daily_upload(self, upload_data, session):
        """
        处理日常上传数据。

        upload_data: List of tuples，每个元组包含：
            - sensor_address: 传感器地址
            - sensor_position: 传感器管理的车位位置（1, 2, 3）
            - license_plate: 车牌号
            - status: 'A' 或 'B'
            - position: 位置信息
        """
        try:
            for record in upload_data:
                sensor_address, sensor_position, license_plate, status, position = record
                # logging.info(f"处理记录: sensor_address={sensor_address}, position={sensor_position}")

                # 查找传感器
                sensor = session.query(Sensor).filter_by(address=sensor_address).first()
                #logging.info(f"查询传感器结果: sensor={sensor}")
                if not sensor:
                    logging.warning(f"传感器地址 {sensor_address} 未找到。")
                    continue

                # 查找车位映射
                try:
                    mapping = session.query(SensorCarSpaceMapping).filter_by(
                        sensor_id=sensor.id,
                        sensor_position=sensor_position
                    ).first()
                    # logging.info(f"查询映射结果: mapping={mapping}, "
                    #             f"sensor_id={sensor.id if sensor else 'None'}, "
                    #             f"sensor_position={sensor_position}")
                except Exception as e:
                    logging.error(f"查询映射时出错: {e}, sensor={sensor}")
                    continue

                if not mapping:
                    logging.info(f"传感器 {sensor_address} 位置 {sensor_position} 没有车位。")
                    continue

                car_space = mapping.car_space
                # logging.info(f"获取到车位: car_space={car_space}")

                if not car_space:
                    logging.warning(f"映射 {mapping.id} 对应的车位不存在。")
                    continue

                # 更新车位状态
                try:
                    car_space_status = session.query(CarSpaceStatus).filter_by(
                        car_space_id=car_space.id
                    ).first()
                    # logging.info(f"查询车位状态结果: car_space_status={car_space_status}, "
                    #            f"car_space_id={car_space.id if car_space else 'None'}")
                except Exception as e:
                    logging.error(f"查询车位状态时出错: {e}, car_space={car_space}")
                    continue

                if car_space_status:
                    # old_status = car_space_status.status
                    # old_license = car_space_status.license_plate
                    
                    # 更新对象属性
                    car_space_status.status = status
                    car_space_status.license_plate = license_plate if status == 'B' else None
                    car_space_status.position = position
                    car_space_status.last_updated = func.now()
                    
                    # 添加打印语句跟踪更新
                    # if old_status != status or old_license != car_space_status.license_plate:
                    #     logging.info(f"更新车位状态: 车位ID={car_space.id}, 位置={car_space.position_description}")
                    #     logging.info(f"  状态: {old_status} -> {status}")
                    #     logging.info(f"  车牌: {old_license} -> {car_space_status.license_plate}")
                    #     logging.info(f"  位置信息: {position}")
                else:
                    logging.info(f"创建新的车位状态: car_space_id={car_space.id}, "
                               f"status={status}, license_plate={license_plate}")
                    car_space_status = CarSpaceStatus(
                        car_space_id=car_space.id,
                        status=status,
                        license_plate=license_plate if status == 'B' else None,
                        position=position
                    )
                    session.add(car_space_status)

                # 记录已更新的车位ID
                with self.lock:
                    self.updated_car_space_ids.add(car_space.id)
                    # logging.info(f"添加更新的车位ID: {car_space.id}")

        except Exception as e:
            logging.error(f"处理日常上传数据时出现错误: {e}")
            session.rollback()
            raise

    def process_updates_periodically(self):
        """定期处理累积的更新并更新引导屏"""
        while self.is_running:
            time.sleep(self.update_interval)
            with self.lock:
                if not self.updated_car_space_ids:
                    continue  # 无更新需要处理

                affected_car_space_ids = list(self.updated_car_space_ids)
                self.updated_car_space_ids.clear()

            try:
                # 开始事务
                # logging.info("开始处理更新...")

                with self.get_session() as session:
                    # 查找受影响的群组
                    affected_group_ids = session.query(CarSpaceGroupMapping.car_space_group_id).filter(
                        CarSpaceGroupMapping.car_space_id.in_(affected_car_space_ids)
                    ).distinct().all()
                    affected_group_ids = [gid for (gid,) in affected_group_ids]

                    if not affected_group_ids:
                        logging.info("更新未影响任何引导屏。")
                        continue

                    # 查找受影响的引导屏
                    affected_guide_screens = session.query(GuideScreen).join(GuideScreen.car_space_groups).filter(
                        CarSpaceGroup.id.in_(affected_group_ids)
                    ).distinct().all()

                    if not affected_guide_screens:
                        logging.info("未找到受影响的引导屏。")
                        continue

                    # 准备显示数据
                    display_data_by_address = defaultdict(lambda: {"address": "", "sections": []})

                    for guide_screen in affected_guide_screens:
                        display_data_by_address[guide_screen.address]["address"] = guide_screen.address
                        for group in guide_screen.car_space_groups:
                            # 获取群组内所有车位ID
                            car_space_ids = [mapping.car_space_id for mapping in group.car_space_mappings]
                            
                            # 获取这些车位的状态
                            car_spaces = session.query(CarSpaceStatus).filter(
                                CarSpaceStatus.car_space_id.in_(car_space_ids)
                            ).all()

                            # 计算空闲车位数量
                            if len(car_space_ids) > 1:
                                empty = sum(1 for cs in car_spaces if cs.status == 'A')
                            else:
                                empty = 1 if car_spaces and car_spaces[0].status == 'A' else 0

                            # 获取段编号
                            section_num = group.section_number

                            if section_num:
                                display_data_by_address[guide_screen.address]["sections"].append({
                                    "section": section_num,
                                    "empty": empty
                                })
                            else:
                                logging.warning(f"群组 {group.name} 没有有效的段编号。")

                    # 转换为列表格式
                    self.new_display_data = list(display_data_by_address.values())

                    # 发送更新到引导屏
                    self.send_updates_to_guides(self.new_display_data)

                    # logging.info("更新处理完成。")

            except Exception as e:
                logging.error(f"process_updates_periodically 发生未捕获的错误: {e}")

    def send_updates_to_guides(self, data_list):
        # 将输入数据转换为更易处理的格式
        formatted_data = []
        section_map = {1: 'sum_l', 2: 'sum_m', 3: 'sum_r'}

        for item in data_list:
            # 创建基础数据结构
            panel_info = {
                'mac': item['address'],
                'sum_l': 0,  # section 1
                'sum_m': 0,  # section 2
                'sum_r': 0   # section 3
            }
            
            # 填充空位数据
            for section in item.get('sections', []):
                section_num = section.get('section')
                key = section_map.get(section_num)
                if key:
                    panel_info[key] += section.get('empty', 0)
                    
            formatted_data.append(panel_info)

        logging.info(f"格式化后的显示数据: {formatted_data}")
        # 每5个一组处理数据
        for i in range(0, len(formatted_data), 5):
            panel_data = ''
            # 处理当前组的数据(最多5个)
            current_group = formatted_data[i:i+5]
            
            for panel in current_group:
                # 构建每个面板的数据字符串
                h1 = (panel['mac'] + '7' + 
                    self.add_hex(panel['sum_l']) +
                    self.add_hex(panel['sum_m']) +
                    self.add_hex(panel['sum_r']))
                panel_data += h1
                
            # 计算版本号和随机序列号
            ver = format(int(len(panel_data)/2) + 2, '02x')
            se = format(random.randint(0, 254), '02x')
            
            # 构建最终发送数据
            sent_data = '7e' + ver + '06' + se + panel_data + '000d'
            
            if self.enable_send:
                self.mqtt_service.send_message(sent_data)
            else:
                logging.info(f"消息发送已禁用，跳过发送: {sent_data}")

    def add_hex(self, value):
        try:
            if value is None:
                return 'fff'
            return format(int(value), '03x')
        except (TypeError, ValueError):
            return 'fff'
    
    def d_hex(self, data):
        hex_data = re.sub(r'^[Ff]+', '', data)
        try:
            tt = bytes.fromhex(hex_data).decode('utf-8')
        except UnicodeDecodeError as e:
            tt = ''
        return tt  
    
    def stop(self):
        """停止监控服务"""
        self.is_running = False
        self.mqtt_service.stop()
        self.Session.remove()
        logging.info("MQTT监控服务已停止")

def main():
    monitor = MQTTMonitor()
    try:
        monitor.start()
    except KeyboardInterrupt:
        logging.info("收到停止信号，正在关闭服务...")
        monitor.stop()

if __name__ == "__main__":
    main()
