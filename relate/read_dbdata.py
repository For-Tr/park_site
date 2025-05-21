import logging
from sqlalchemy import ( 
    create_engine, Column, Integer, String, ForeignKey, 
    CHAR, TIMESTAMP, UniqueConstraint, Index, func
)
from sqlalchemy.orm import relationship, sessionmaker, declarative_base
from contextlib import contextmanager
from pathlib import Path
from sqlalchemy import event
from datetime import datetime, timedelta
import yaml
from pathlib import Path

Base = declarative_base()

# -----------------------------
# ORM Models
# -----------------------------

class SiteConfigeration(Base):
    __tablename__ = 'SiteConfigeration'
    
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
    name = Column(String, nullable=True)

    # Relationships
    car_space_groups = relationship(
        'CarSpaceGroup',
        back_populates='guide_screen',
        cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index('idx_guide_screens_address', 'address', unique=True),
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

class CarSpaceGroup(Base):
    __tablename__ = 'car_space_groups'
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    section_number = Column(Integer, nullable=False) 

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

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class DBReader:
    def __init__(self):
        # 加载配置
        self.config = self._load_config()
        
        # 获取当前文件所在目录
        CURRENT_DIR = Path(__file__).parent

        # 使用相对路径创建数据库连接
        db_path = CURRENT_DIR / 'db' / 'parking_system.db'
        self.engine = create_engine(
            f'sqlite:///{db_path}',
            echo=False
        )
        
        # 添加 WAL 模式优化
        @event.listens_for(self.engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            # 启用 WAL 模式
            cursor.execute("PRAGMA journal_mode=DELETE")
            # 设置页缓存大小（默认为-2000，可根据内存调整）
            cursor.execute("PRAGMA page_size=4096")
            cursor.execute("PRAGMA cache_size=-2000")
            # 同步设置
            cursor.execute("PRAGMA synchronous=NORMAL")  # 在WAL模式下可以使用NORMAL
            # 设置繁忙超时
            cursor.execute("PRAGMA busy_timeout=5000")
            # 设置内存映射限制
            cursor.execute("PRAGMA mmap_size=67108864")
            cursor.close()
            
        self.Session = sessionmaker(bind=self.engine)

    def _load_config(self):
        """加载配置文件"""
        try:
            config_path = Path(__file__).parent / 'db' / 'config.yml'
            with open(config_path, 'r', encoding='utf-8') as file:
                return yaml.safe_load(file)
        except Exception as e:
            logging.error(f"加载配置文件失败: {e}")
            # 使用默认值
            return {'timeout': {'node_hours': 8}}

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
            session.close()

    def get_guide_screen_status(self):
        """获取每个引导屏及其关联车位组的状态统计"""
        with self.get_session() as session:
            guide_screens = session.query(GuideScreen).all()
            result = []
            
            for screen in guide_screens:
                screen_info = {
                    'guide_screen_address': screen.address,
                    'guide_screen_name': screen.name if screen.name else '',
                    'groups': []
                }
                
                for group in screen.car_space_groups:
                    # 获取该组所有车位ID
                    car_space_ids = [mapping.car_space_id for mapping in group.car_space_mappings]
                    
                    # 查询这些车位的状态和描述
                    statuses = (session.query(CarSpaceStatus, CarSpace.position_description)
                              .join(CarSpace, CarSpace.id == CarSpaceStatus.car_space_id)
                              .filter(CarSpaceStatus.car_space_id.in_(car_space_ids))
                              .all())
                    
                    # 统计A和B状态的数量
                    status_a_count = sum(1 for s, _ in statuses if s.status == 'A')
                    status_b_count = sum(1 for s, _ in statuses if s.status == 'B')
                    
                    # 获取A状态车位的描述
                    status_details = {
                        'A': [desc for status, desc in statuses if status.status == 'A']
                    }
                    
                    group_info = {
                        'group_name': group.name,
                        'section_number': group.section_number,
                        'total_spaces': len(car_space_ids),
                        'available_spaces': status_a_count,
                        'occupied_spaces': status_b_count,
                        'status_details': status_details
                    }
                    screen_info['groups'].append(group_info)
                
                # 打印每个屏幕的状态详情
                # print(f"\n屏幕 {screen.address} 的状态详情:")
                # for group in screen_info['groups']:
                #     print(f"  组 {group['group_name']}:")
                #     print(f"    空闲车位(A): {group['status_details']['A']}")
                
                result.append(screen_info)
            
            return result
        
    def get_timeout_status(self, timeout_hours=None):
        """获取超时状态"""
        # 使用配置文件中的值，如果没有提供参数的话
        if timeout_hours is None:
            timeout_hours = self.config.get('timeout', {}).get('node_hours', 8)
            # logging.info(f"使用配置文件中的超时时间: {timeout_hours} 小时")
            
        with self.get_session() as session:
            result = {
                'current_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'panel': []
            }
            
            # 检查显示屏超时（原有代码）
            panels_query = session.query(
                CheckScreen.id,
                CheckScreen.address,
                CheckScreen.name,
                CheckScreen.last_updated
            ).filter(
                CheckScreen.last_updated < func.datetime('now', f'-{timeout_hours*3600} seconds')
            ).order_by(
                CheckScreen.last_updated.desc()
            )

            timeout_screens = panels_query.all()
            
            # 添加超时显示屏到结果中
            for screen in timeout_screens:
                # 处理时间戳，加8小时
                if screen.last_updated:
                    adjusted_time = screen.last_updated + timedelta(hours=8)
                    formatted_time = adjusted_time.strftime('%Y-%m-%d %H:%M:%S')
                else:
                    formatted_time = ''

                result['panel'].append({
                    'sort': 'panel',
                    'address': screen.address,
                    'name': screen.name if screen.name else '未命名',
                    'last_updated': formatted_time
                })

            # 新增：检查节点设备超时
            nodes_query = session.query(
                CarSpaceStatus.car_space_id,
                CarSpaceStatus.last_updated,
                CarSpace.position_description.label('position'),
                Sensor.address.label('sensor_address'),
                Sensor.id.label('sensor_id'),
                SubRouter.name.label('sub_router_name'),
                SubRouter.id.label('sub_router_id'),
                SubRouter.address.label('sub_router_address')
            ).join(
                SensorCarSpaceMapping,
                SensorCarSpaceMapping.car_space_id == CarSpaceStatus.car_space_id
            ).join(
                Sensor,
                Sensor.id == SensorCarSpaceMapping.sensor_id
            ).join(
                SubRouter,
                SubRouter.id == Sensor.sub_router_id
            ).join(
                CarSpace,
                CarSpace.id == CarSpaceStatus.car_space_id
            ).filter(
                CarSpaceStatus.last_updated < func.datetime('now', f'-{timeout_hours*3600} seconds')
            ).order_by(
                CarSpaceStatus.last_updated.desc()
            )

            timeout_nodes = nodes_query.all()
            
            # 添加超时节点到结果中，对传感器地址去重
            processed_sensors = set()  # 用于跟踪已处理的传感器地址
            
            for node in timeout_nodes:
                # 检查传感器地址是否已经处理过
                if node.sensor_address in processed_sensors:
                    # 跳过已处理的传感器地址
                    continue
                
                # 将当前传感器地址添加到已处理集合
                processed_sensors.add(node.sensor_address)
                
                # 处理时间戳，加8小时
                if node.last_updated:
                    adjusted_time = node.last_updated + timedelta(hours=8)
                    formatted_time = adjusted_time.strftime('%Y-%m-%d %H:%M:%S')
                else:
                    formatted_time = ''

                # 添加到结果中
                result['panel'].append({
                    'sort': 'node',
                    'position': node.position,
                    'address': node.sensor_address,
                    'address1': node.sub_router_address,
                    'name': node.sub_router_name if node.sub_router_name else '未命名',
                    'last_updated': formatted_time,
                })
            
            return result

    def search_by_partial_plate(self, partial_plate):
        """通过部分 license_plate 查询，返回相关信息
        支持使用?作为单字符通配符
        例如: '1n?1' 可以匹配 '粤B1NK10' 等
        """
        # 将?和？转换为SQL的单字符通配符_
        sql_pattern = partial_plate.replace('?', '_').replace('？', '_')
        # 在模式前后添加%以匹配任意位置
        sql_pattern = f"%{sql_pattern}%"
        
        with self.get_session() as session:
            # 使用LIKE进行模糊查询，支持通配符
            results = (
                session.query(CarSpaceStatus.license_plate, CarSpace.position_description, CarSpaceStatus.position)
                .join(CarSpace, CarSpace.id == CarSpaceStatus.car_space_id)
                .filter(CarSpaceStatus.license_plate.ilike(sql_pattern))
                .all()
            )
            
            # 添加打印语句
            logging.info(f"查询结果: {results}")
            
            # 组织结果为字典列表
            return [
                {
                    'license_plate': license_plate,
                    'position_description': position_description,
                    'position': position
                }
                for license_plate, position_description, position in results
            ]

def main():
    reader = DBReader()

    # 获取超时状态
    check_screen_status = reader.get_timeout_status()
    print(f"Check screen status: {check_screen_status}")  # 添加调试信息
    
    # 获取引导屏状态统计
    guide_screen_stats = reader.get_guide_screen_status()
    
    # 打印引导屏状态统计
    for screen in guide_screen_stats:
        print(f"\n引导屏地址: {screen['guide_screen_address']}")
        for group in screen['groups']:
            print(f"  车位组: {group['group_name']} (段号: {group['section_number']})")
            print(f"    总车位数: {group['total_spaces']}")
            print(f"    空闲车位(A): {group['available_spaces']}")
            print(f"    占用车位(B): {group['occupied_spaces']}")



if __name__ == "__main__":
    main()
