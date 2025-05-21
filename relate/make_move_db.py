# parking_system.py

import logging
from sqlalchemy import (
    create_engine, Column, Integer, String, ForeignKey, CHAR, TIMESTAMP,
    UniqueConstraint, Index, func, text
)
from sqlalchemy.orm import relationship, sessionmaker, declarative_base
from contextlib import contextmanager
from pathlib import Path

Base = declarative_base()

# 获取当前文件所在目录
CURRENT_DIR = Path(__file__).parent
# 获取项目根目录 (假设是当前目录的上级目录)
PROJECT_ROOT = CURRENT_DIR.parent

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

# -----------------------------
# Database Setup
# -----------------------------

class ParkingSystemDatabase:
    def __init__(self, new_db_uri=None):
        if new_db_uri is None:
            # 使用相对路径定义新数据库位置
            new_db_path = CURRENT_DIR / 'db' / 'parking_system.db'
            new_db_uri = f'sqlite:///{new_db_path}'
            
        self.engine = create_engine(new_db_uri, echo=False, connect_args={"check_same_thread": False})
        self.Session = sessionmaker(bind=self.engine)
        Base.metadata.create_all(self.engine)
        logging.info("新数据库已创建或已存在。")

    @contextmanager
    def get_session(self):
        session = self.Session()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logging.error(f"Session 出现异常: {e}")
            raise
        finally:
            session.close()

    def migrate_site_configeration(self, old_db_uri=None):
        if old_db_uri is None:
            # 使用相对路径定义旧数据库位置
            old_db_path = CURRENT_DIR / 'db' / 'parking_zone.db'
            old_db_uri = f'sqlite:///{old_db_path}'
            
        old_engine = create_engine(old_db_uri)
        with old_engine.connect() as old_conn, self.get_session() as session:
            try:
                # 从旧数据库获取 SiteConfiguration 数据
                site_configs = old_conn.execute(text("SELECT * FROM site_configeration")).fetchall()
                
                for config in site_configs:
                    new_config = SiteConfigeration(
                        company_name=config.company_name if hasattr(config, 'company_name') else "My Company",
                        version=config.version if hasattr(config, 'version') else "1.0.0",
                        development_date=config.development_date if hasattr(config, 'development_date') else None,
                        name=config.name if hasattr(config, 'name') else None,
                        server=config.server if hasattr(config, 'server') else None,
                        user=config.user if hasattr(config, 'user') else None,
                        password=config.password if hasattr(config, 'password') else None,
                        send=config.send if hasattr(config, 'send') else None,
                        read=config.read if hasattr(config, 'read') else None
                    )
                    session.add(new_config)
                    logging.info(f"新增 SiteConfigeration: {new_config.company_name}")
                
                logging.info("SiteConfiguration 数据迁移完成。")
                print("站点配置数据迁移成功")
            except Exception as e:
                logging.error(f"迁移站点配置时发生错误: {e}")
                print(f"迁移过程中发生错误: {str(e)}")

    def migrate_subrouters(self, old_db_uri=None):
        if old_db_uri is None:
            old_db_path = CURRENT_DIR / 'db' / 'parking_zone.db'
            old_db_uri = f'sqlite:///{old_db_path}'
            
        """
        从旧数据库的 subrouter_ini 表迁移 SubRouter 数据到新数据库的 sub_routers 表。
        """
        old_engine = create_engine(old_db_uri)
        with old_engine.connect() as old_conn, self.get_session() as session:
            try:
                # 从旧数据库获取 SubRouter 数据
                # 确保使用英文逗号而非中文逗号
                # 假设 subrouter_ini 表中有 mac 和 name 列
                result = old_conn.execute(text("SELECT DISTINCT mac, name FROM subrouter_ini"))
                subrouters = result.mappings().all()  # 使用mappings()来获取字典形式的结果
                
                for subrouter in subrouters:
                    mac_address = subrouter['mac']
                    name = subrouter['name']
                    
                    # 检查 SubRouter 是否已存在
                    existing_subrouter = session.query(SubRouter).filter_by(address=mac_address).first()
                    if not existing_subrouter:
                        # 创建新的 SubRouter 记录
                        new_subrouter = SubRouter(address=mac_address, name=name)
                        session.add(new_subrouter)
                        logging.info(f"新增 SubRouter: {new_subrouter.address}, 名称: {new_subrouter.name}")
                    else:
                        logging.info(f"SubRouter 已存在: {existing_subrouter.address}, 名称: {existing_subrouter.name}")
                
                logging.info("SubRouter 数据迁移完成。")
                print("SubRouter 数据迁移成功")
            except Exception as e:
                logging.error(f"迁移 SubRouter 时发生错误: {e}")
                print(f"迁移过程中发生错误: {str(e)}")

    def migrate_devices(self, old_db_uri=None):
        if old_db_uri is None:
            old_db_path = CURRENT_DIR / 'db' / 'parking_zone.db'
            old_db_uri = f'sqlite:///{old_db_path}'
            
        """
        从旧数据库的 device_ini 表迁移 Sensor 数据到新数据库的 sensors 表，并关联到 SubRouter。
        """
        old_engine = create_engine(old_db_uri)
        with old_engine.connect() as old_conn, self.get_session() as session:
            try:
                result = old_conn.execute(text("SELECT DISTINCT mac_subrouter, node_mac FROM device_ini"))
                devices = result.mappings().all()  # 使用mappings()
                
                for device in devices:
                    mac_subrouter = device['mac_subrouter']
                    node_mac = device['node_mac']
                    
                    # 处理 SubRouter
                    subrouter = session.query(SubRouter).filter_by(address=mac_subrouter).first()
                    if not subrouter:
                        # 创建新的 SubRouter 记录
                        subrouter = SubRouter(address=mac_subrouter, name=f"SubRouter_{mac_subrouter}")
                        session.add(subrouter)
                        session.flush()  # 获取 subrouter.id
                        logging.info(f"新增 SubRouter: {subrouter.address}")
                    
                    # 处理 Sensor
                    existing_sensor = session.query(Sensor).filter_by(address=node_mac).first()
                    if not existing_sensor:
                        new_sensor = Sensor(address=node_mac, sub_router=subrouter)
                        session.add(new_sensor)
                        logging.info(f"新增 Sensor: {new_sensor.address} 并关联 SubRouter: {subrouter.address}")
                    else:
                        # 如果 Sensor 已存在但未关联 SubRouter，进行关联
                        if not existing_sensor.sub_router:
                            existing_sensor.sub_router = subrouter
                            logging.info(f"关联已有 Sensor: {existing_sensor.address} 至 SubRouter: {subrouter.address}")
                
                logging.info("传感器和子路由器数据迁移完成。")
                print("传感器和子路由器数据迁移成功")
            except Exception as e:
                logging.error(f"迁移传感器和子路由器时发生错误: {e}")
                print(f"迁移过程中发生错误: {str(e)}")

    def migrate_car_spaces(self, old_db_uri=None):
        if old_db_uri is None:
            old_db_path = CURRENT_DIR / 'db' / 'parking_zone.db'
            old_db_uri = f'sqlite:///{old_db_path}'
            
        """
        从旧数据库的 spot_ini 表迁移 CarSpace 数据到新数据库的 car_spaces 表。
        """
        old_engine = create_engine(old_db_uri)
        with old_engine.connect() as old_conn, self.get_session() as session:
            try:
                # 从旧数据库获取车位数据
                spots = old_conn.execute(text("SELECT DISTINCT spot_id FROM spot_ini"))
                spots = spots.mappings().all()  # 使用mappings()
                
                # 遍历并插入数据
                for spot in spots:
                    spot_id = spot['spot_id']
                    # 检查车位是否已存在
                    existing_space = session.query(CarSpace).filter_by(position_description=spot_id).first()
                    if not existing_space:
                        new_space = CarSpace(position_description=spot_id)
                        session.add(new_space)
                        logging.info(f"新增 CarSpace: {new_space.position_description}")
                
                logging.info("车位数据迁移完成。")
                print("车位数据迁移成功")
            except Exception as e:
                logging.error(f"迁移车位数据时发生错误: {e}")
                print(f"迁移车位数据时发生错误: {str(e)}")

    def migrate_guide_screens(self, old_db_uri=None):
        if old_db_uri is None:
            old_db_path = CURRENT_DIR / 'db' / 'parking_zone.db'
            old_db_uri = f'sqlite:///{old_db_path}'
            
        """
        从旧数据库的 panel_ini 表迁移 GuideScreen 数据到新数据库的 guide_screens 表。
        """
        old_engine = create_engine(old_db_uri)
        with old_engine.connect() as old_conn, self.get_session() as session:
            try:
                # 从旧数据库获取显示屏数据，包括 mac 和 name
                panels = old_conn.execute(text("SELECT DISTINCT mac, name FROM panel_ini"))
                panels = panels.mappings().all()  # 使用mappings()

                # 遍历并插入数据
                for panel in panels:
                    mac = panel['mac']
                    name = panel['name']
                    # 检查显示屏是否已存在
                    existing_screen = session.query(GuideScreen).filter_by(address=mac).first()
                    if not existing_screen:
                        new_screen = GuideScreen(
                            address=mac,
                            name=name
                        )
                        session.add(new_screen)
                        logging.info(f"新增 GuideScreen: {new_screen.address}, 名称: {new_screen.name}")
                    else:
                        logging.info(f"GuideScreen 已存在: {existing_screen.address}, 名称: {existing_screen.name}")
                
                logging.info("显示屏数据迁移完成。")
                print("显示屏数据迁移成功")
            except Exception as e:
                logging.error(f"迁移显示屏数据时发生错误: {e}")
                print(f"迁移过程中发生错误: {str(e)}")

    def migrate_sensor_car_space_mapping(self, old_db_uri=None):
        if old_db_uri is None:
            old_db_path = CURRENT_DIR / 'db' / 'parking_zone.db'
            old_db_uri = f'sqlite:///{old_db_path}'
            
        """
        使用 ORM 方式迁移传感器和车位的映射关系到 sensor_car_space_mapping 表。
        """
        logging.info("\n开始创建传感器和车位的映射关系...")
        with self.get_session() as session:
            try:
                # 清空目标表
                session.query(SensorCarSpaceMapping).delete()
                session.commit()
                logging.info("已清空 sensor_car_space_mapping 表")
                
                # 创建到旧数据库的连接并使用错误处理
                try:
                    old_engine = create_engine(old_db_uri)
                    with old_engine.connect() as old_conn:
                        # 使用 text 确保 SQL 语句正确执行
                        query = text("SELECT node_mac, spot_num, spot_l, spot_m, spot_r FROM device_ini")
                        result = old_conn.execute(query)
                        device_records = result.mappings().all()
                        
                        if not device_records:
                            logging.warning("未找到设备记录")
                            return
                            
                        logging.info(f"找到 {len(device_records)} 个设备配置")
                except Exception as e:
                    logging.error(f"连接旧数据库失败: {str(e)}")
                    return
                
                # 清理停车位ID的函数
                def clean_spot_id(spot_id):
                    if not spot_id:
                        return None
                    try:
                        # 移除可能的空格和特殊字符
                        cleaned = spot_id.strip().replace('f', '').replace(' ', '')
                        if not cleaned:
                            return None
                        # 确保是偶数长度的十六进制字符串
                        if len(cleaned) % 2 == 0:
                            return bytes.fromhex(cleaned).decode('ascii', errors='ignore')
                        return spot_id
                    except Exception as e:
                        logging.warning(f"清理车位ID失败 {spot_id}: {str(e)}")
                        return spot_id
                
                # 提交数据的函数
                def commit_data(sensor, spot, position):
                    if not spot:
                        return None
                        
                    spot = clean_spot_id(spot)
                    if not spot:
                        return None
                    
                    try:
                        # 检查车位是否存在
                        car_space = session.query(CarSpace).filter_by(position_description=spot).first()
                        if not car_space:
                            logging.warning(f"未找到编号为 {spot} 的车位")
                            return None
                        
                        # 检查映射是否已存在
                        existing_mapping = session.query(SensorCarSpaceMapping).filter_by(
                            sensor_id=sensor.id,
                            car_space_id=car_space.id
                        ).first()
                        
                        if existing_mapping:
                            logging.warning(f"映射关系已存在: {sensor.address} -> {spot}")
                            return None
                        
                        # 创建新映射
                        new_mapping = SensorCarSpaceMapping(
                            sensor_id=sensor.id,
                            sensor_position=position,
                            car_space_id=car_space.id
                        )
                        session.add(new_mapping)
                        session.flush()
                        logging.info(f"创建映射关系: Sensor {sensor.address} - Position {position} -> CarSpace {car_space.position_description}")
                        return new_mapping
                        
                    except Exception as e:
                        logging.error(f"处理映射关系时出错: {str(e)}")
                        return None
                
                # 处理每个设备记录
                for device in device_records:
                    try:
                        node_mac = device['node_mac']
                        sensor = session.query(Sensor).filter_by(address=node_mac).first()
                        
                        if not sensor:
                            logging.warning(f"未找到地址为 {node_mac} 的传感器")
                            continue
                        
                        # 处理左中右三个车位
                        spots = [
                            (device['spot_l'], 1),
                            (device['spot_m'], 2),
                            (device['spot_r'], 3)
                        ]
                        
                        for spot, position in spots:
                            if spot:
                                commit_data(sensor, spot, position)
                                
                    except Exception as e:
                        logging.error(f"处理设备 {node_mac} 时出错: {str(e)}")
                        continue
                
                session.commit()
                logging.info("传感器和车位的映射关系迁移完成")
                
            except Exception as e:
                session.rollback()
                logging.error(f"迁移过程出错: {str(e)}")
                raise

    def migrate_car_space_status(self, old_db_uri=None):
        """
        将所有 car_spaces 的 ID 迁移到 car_space_status 表中。
        """
        with self.get_session() as session:
            try:
                # 获取所有 car_spaces 的 ID
                car_spaces = session.query(CarSpace).all()
                logging.info(f"找到 {len(car_spaces)} 个车位需要迁移状态")
                print(f"找到 {len(car_spaces)} 个车位需要迁移状态")
                
                # 为每个车位创建状态记录
                for car_space in car_spaces:
                    # 检查是否已存在状态记录
                    existing_status = session.query(CarSpaceStatus).filter_by(
                        car_space_id=car_space.id
                    ).first()
                    
                    if not existing_status:
                        new_status = CarSpaceStatus(
                            car_space_id=car_space.id,
                            status='A'  # 默认状态为A
                            # license_plate 和 last_updated 会自动处理
                        )
                        session.add(new_status)
                        logging.info(f"为车位ID {car_space.id} 创建状态记录")
                        print(f"为车位ID {car_space.id} 创建状态记录")
                
                logging.info("车位状态迁移完成。")
                print("车位状态迁移完成")
            except Exception as e:
                logging.error(f"迁移车位状态时发生错误: {e}")
                print(f"迁移车位状态时发生错误: {str(e)}")

    def migrate_car_space_groups(self, old_db_uri=None):
        if old_db_uri is None:
            old_db_path = CURRENT_DIR / 'db' / 'parking_zone.db'
            old_db_uri = f'sqlite:///{old_db_path}'
            
        """
        从旧数据库的 panel_ini 表迁移数据到 car_space_groups 表。
        """
        old_engine = create_engine(old_db_uri)
        with old_engine.connect() as old_conn, self.get_session() as session:
            try:
                # 从旧数据库获取显示屏和分组数据
                panels = old_conn.execute(text("SELECT mac, section FROM panel_ini"))
                panels = panels.mappings().all()  # 使用mappings()
                
                for panel in panels:
                    mac = panel['mac']
                    section = panel['section']
                    guide_screen = session.query(GuideScreen).filter_by(address=mac).first()
                    
                    if guide_screen:
                        # 为每个 section 创建分组
                        for position in range(1, section + 1):
                            # 检查是否已存在
                            existing_group = session.query(CarSpaceGroup).filter_by(
                                guide_screen_id=guide_screen.id,
                                name=str(position)
                            ).first()
                            
                            if not existing_group:
                                # 创建新的 CarSpaceGroup 对象
                                new_group = CarSpaceGroup(
                                    name=str(position),
                                    section_number=position,  # 填充新字段
                                    guide_screen_id=guide_screen.id
                                )
                                session.add(new_group)
                                logging.info(f"为显示屏 {mac} 创建分组 {position}")
                                print(f"为显示屏 {mac} 创建分组 {position}")
                    
                logging.info("车位分组数据迁移完成。")
                print("车位分组数据迁移成功")
            except Exception as e:
                logging.error(f"迁移车位分组数据时发生错误: {e}")
                print(f"迁移车位分组数据时发生错误: {str(e)}")

    def migrate_car_space_group_mapping(self, old_db_uri=None):
        if old_db_uri is None:
            old_db_path = CURRENT_DIR / 'db' / 'parking_zone.db'
            old_db_uri = f'sqlite:///{old_db_path}'
            
        """
        从旧数据库的 match_panel 表迁移数据到 car_space_group_mapping 表。
        """
        logging.info("\n开始迁移车位组映射关系...")
        with self.get_session() as session:
            try:
                # 清空目标表
                session.query(CarSpaceGroupMapping).delete()
                session.commit()
                logging.info("已清空 car_space_group_mapping 表")
                print("已清空 car_space_group_mapping 表")
                
                old_engine = create_engine(old_db_uri)
                with old_engine.connect() as old_conn:
                    match_panels = old_conn.execute(text("SELECT mac_id, section, spot_id_id FROM match_panel"))
                    match_panels = match_panels.mappings().all()  # 使用mappings()
                    logging.info(f"找到 {len(match_panels)} 条映射记录")
                    print(f"找到 {len(match_panels)} 条映射记录")
                    
                    for match in match_panels:
                        mac_id = match['mac_id']
                        section = match['section']
                        spot_id = match['spot_id_id']
                        
                        # 查找对应的 guide_screen
                        guide_screen = session.query(GuideScreen).filter_by(address=mac_id).first()
                        if not guide_screen:
                            logging.warning(f"未找到地址为 {mac_id} 的显示屏，跳过")
                            print(f"警告：未找到地址为 {mac_id} 的显示屏，跳过")
                            continue
                        
                        # 查找对应的 car_space_group
                        car_space_group = session.query(CarSpaceGroup).filter_by(
                            guide_screen_id=guide_screen.id,
                            name=str(section)
                        ).first()
                        if not car_space_group:
                            logging.warning(f"未找到显示屏 {mac_id} 的分组 {section}，跳过")
                            print(f"警告：未找到显示屏 {mac_id} 的分组 {section}，跳过")
                            continue
                        
                        # 清理并查找对应的 car_space
                        def clean_spot_id(spot_id):
                            if not spot_id:
                                return None
                            cleaned = spot_id.replace('f', '')
                            try:
                                if len(cleaned) % 2 == 0:
                                    return bytes.fromhex(cleaned).decode('ascii')
                            except:
                                pass
                            return spot_id
                        
                        cleaned_spot_id = clean_spot_id(spot_id)
                        if not cleaned_spot_id:
                            logging.warning(f"spot_id 无法清理，原始值: {spot_id}，跳过")
                            print(f"警告：spot_id 无法清理，原始值: {spot_id}，跳过")
                            continue
                        
                        car_space = session.query(CarSpace).filter_by(position_description=cleaned_spot_id).first()
                        if not car_space:
                            logging.warning(f"未找到编号为 {cleaned_spot_id} 的车位，跳过")
                            print(f"警告：未找到编号为 {cleaned_spot_id} 的车位，跳过")
                            continue
                        
                        # 检查映射是否已存在
                        existing_mapping = session.query(CarSpaceGroupMapping).filter_by(
                            car_space_group_id=car_space_group.id,
                            car_space_id=car_space.id
                        ).first()
                        
                        if not existing_mapping:
                            new_mapping = CarSpaceGroupMapping(
                                car_space_group_id=car_space_group.id,
                                car_space_id=car_space.id
                            )
                            session.add(new_mapping)
                            logging.info(f"创建映射：显示屏组 {mac_id}-{section} -> 车位 {cleaned_spot_id}")
                            print(f"创建映射：显示屏组 {mac_id}-{section} -> 车位 {cleaned_spot_id}")
                        else:
                            logging.warning(f"映射关系已存在：显示屏组 {mac_id}-{section} -> 车位 {cleaned_spot_id}，跳过")
                            print(f"警告：映射关系已存在：显示屏组 {mac_id}-{section} -> 车位 {cleaned_spot_id}，跳过")
                
                logging.info("车位组映射关系迁移完成。")
                print("车位组映射关系迁移完成")
            except Exception as e:
                session.rollback()
                logging.error(f"迁移车位组映射关系时发生错误: {e}")
                print(f"迁移过程出错: {str(e)}")

    def migrate_check_screens(self, old_db_uri=None):
        if old_db_uri is None:
            old_db_path = CURRENT_DIR / 'db' / 'parking_zone.db'
            old_db_uri = f'sqlite:///{old_db_path}'
            
        """
        从旧数据库的 panel_ini 表迁移 CheckScreen 数据到新数据库的 check_screens 表。
        """
        old_engine = create_engine(old_db_uri)
        with old_engine.connect() as old_conn, self.get_session() as session:
            try:
                # 从旧数据库获取检查屏数据，包括 mac 和 name
                # 如果检查屏与引导屏共用 panel_ini 表，请确保区分两者
                # 这里假设 panel_ini 表中的某个字段区分类型，如果没有，则可能需要调整
                # 例如，添加一个类型字段，或者根据某种逻辑进行区分
                # 目前假设所有 panel_ini 记录既是 GuideScreen 也是 CheckScreen
                # 这可能导致重复数据，视实际需求调整
                
                panels = old_conn.execute(text("SELECT DISTINCT mac, name FROM panel_ini"))
                panels = panels.mappings().all()  # 使用mappings()
                
                for panel in panels:
                    mac = panel['mac']
                    name = panel['name']
                    # 检查 CheckScreen 是否已存在
                    existing_screen = session.query(CheckScreen).filter_by(address=mac).first()
                    if not existing_screen:
                        new_screen = CheckScreen(
                            address=mac,
                            name=name
                        )
                        session.add(new_screen)
                        logging.info(f"新增 CheckScreen: {new_screen.address}, 名称: {new_screen.name}")
                    else:
                        logging.info(f"CheckScreen 已存在: {existing_screen.address}, 名称: {existing_screen.name}")
                
                logging.info("检查屏数据迁移完成。")
                print("检查屏数据迁移成功")
            except Exception as e:
                logging.error(f"迁移检查屏数据时发生错误: {e}")
                print(f"迁移检查屏数据时发生错误: {str(e)}")

    def migrate_all(self, old_db_uri=None):
        if old_db_uri is None:
            old_db_path = CURRENT_DIR / 'db' / 'parking_zone.db'
            old_db_uri = f'sqlite:///{old_db_path}'
            
        try:
            self.migrate_site_configeration(old_db_uri)
            self.migrate_subrouters(old_db_uri)
            self.migrate_devices(old_db_uri)
            self.migrate_car_spaces(old_db_uri)
            self.migrate_guide_screens(old_db_uri)
            self.migrate_sensor_car_space_mapping(old_db_uri)
            self.migrate_car_space_status()
            self.migrate_car_space_groups(old_db_uri)
            self.migrate_car_space_group_mapping(old_db_uri)
            self.migrate_check_screens(old_db_uri)
            logging.info("所有数据迁移完成。")
            print("所有数据迁移完成")
        except Exception as e:
            logging.error(f"迁移过程中发生未处理的错误: {e}")
            print(f"迁移过程中发生未处理的错误: {str(e)}")

# -----------------------------
# Main Function
# -----------------------------

def main():
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    db = ParkingSystemDatabase()
    db.migrate_all()
    
    # 其他功能的调用...
    # 例如，查询、获取超时状态等

if __name__ == "__main__":
    main()
