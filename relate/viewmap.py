import geopandas as gpd
import os
from shapely.geometry import Polygon, MultiPolygon, LineString, MultiLineString, Point
import numpy as np
from shapely.ops import nearest_points
import networkx as nx
import logging
from datetime import datetime
from dataclasses import dataclass
from typing import List, Dict, Optional
from logging.handlers import RotatingFileHandler

@dataclass
class LayerConfig:
    """图层配置类，用于管理GeoJSON图层信息"""
    name: str  # 图层名称
    file_path: str  # GeoJSON文件路径
    color: str  # 图层颜色
    is_base: bool = False  # 是否为基础图层
    is_marker: bool = False  # 是否为标记图层
    is_navigation: bool = False  # 是否为导航图层
    
    @classmethod
    def get_default_configs(cls, script_dir: str) -> List['LayerConfig']:
        """获取默认的图层配置"""
        return [
            cls(
                name="0-DP3",
                file_path=os.path.join(script_dir, "map", "0-DP3.geojson"),
                color="#444444",
                is_base=True
            ),
            cls(
                name="0-BH",
                file_path=os.path.join(script_dir, "map", "0-BH.geojson"),
                color="#964B00",
                is_marker=True
            ),
            cls(
                name="0-DP2",
                file_path=os.path.join(script_dir, "map", "0-DP2.geojson"),
                color="#FF0000",
                is_marker=True
            ),
            cls(
                name="0-CW",
                file_path=os.path.join(script_dir, "map", "0-CW.geojson"),
                color="#0000FF",
                is_base=True
            )
        ]

# 配置日志
def setup_logger():
    # 获取项目根目录的绝对路径
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    # 使用项目根目录下的logs目录
    log_dir = os.path.join(root_dir, 'logs')
    os.makedirs(log_dir, exist_ok=True)
    
    # 固定日志文件名
    log_file = os.path.join(log_dir, 'viewmap.log')
    
    # 创建logger实例
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    
    # 清除已有的handlers
    if logger.handlers:
        logger.handlers.clear()
    
    # 创建轮转文件处理器（10MB，最多保留5个旧文件）
    file_handler = RotatingFileHandler(log_file, maxBytes=10*1024*1024, backupCount=5, encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    
    # 创建控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    
    # 创建格式化器
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    # 添加处理器到logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    # 记录日志文件路径
    logger.info(f"日志文件路径: {log_file}")
    
    return logger

# 获取logger实例
logger = setup_logger()

# 获取脚本所在目录的绝对路径
script_dir = os.path.dirname(os.path.abspath(__file__))

def convert_3d_to_2d(geom):
    """将3D几何图形转换为2D"""
    if geom.is_empty:
        return geom
    
    if geom.geom_type == 'LineString':
        return LineString([(c[0], c[1]) for c in geom.coords])
    elif geom.geom_type == 'MultiLineString':
        return MultiLineString([LineString([(c[0], c[1]) for c in line.coords]) for line in geom.geoms])
    elif geom.geom_type == 'Polygon':
        shell = [(c[0], c[1]) for c in geom.exterior.coords]
        holes = [[(c[0], c[1]) for c in interior.coords] for interior in geom.interiors]
        return Polygon(shell, holes)
    elif geom.geom_type == 'MultiPolygon':
        polys = []
        for poly in geom.geoms:
            shell = [(c[0], c[1]) for c in poly.exterior.coords]
            holes = [[(c[0], c[1]) for c in interior.coords] for interior in poly.interiors]
            polys.append(Polygon(shell, holes))
        return MultiPolygon(polys)
    return geom

def transform_geom(geom):
    """
    将几何图形的坐标转换为合理的经纬度范围
    假设输入坐标是北京地区的本地坐标系统
    """
    if geom.geom_type == 'LineString':
        coords = np.array(geom.coords)
        # 计算相对于中心点的偏移
        center_x = 116.4  # 北京市中心经度
        center_y = 39.9   # 北京市中心纬度
        
        # 将坐标值缩放到合适的范围（假设原始坐标单位是米）
        scale_factor = 0.00001  # 适当的缩放因子
        new_coords = coords.copy()
        new_coords[:, 0] = center_x + (coords[:, 0] - np.mean(coords[:, 0])) * scale_factor
        new_coords[:, 1] = center_y + (coords[:, 1] - np.mean(coords[:, 1])) * scale_factor
        
        return LineString(new_coords)
    elif geom.geom_type == 'MultiLineString':
        new_lines = [transform_geom(line) for line in geom.geoms]
        return MultiLineString(new_lines)
    elif geom.geom_type == 'Polygon':
        coords = np.array(geom.exterior.coords)
        new_coords = coords.copy()
        center_x = 116.4
        center_y = 39.9
        scale_factor = 0.00001
        new_coords[:, 0] = center_x + (coords[:, 0] - np.mean(coords[:, 0])) * scale_factor
        new_coords[:, 1] = center_y + (coords[:, 1] - np.mean(coords[:, 1])) * scale_factor
        return Polygon(new_coords)
    return geom

def find_nearest_point_in_dp3(point, dp3_polygon, step=1.0):
    """找到DP3区域内距离给定点最近的点，优先调整数值较大的坐标"""
    if dp3_polygon.contains(point):
        return point
    
    # 获取DP3的边界
    boundary = dp3_polygon.boundary
    nearest_boundary_point = nearest_points(point, boundary)[1]
    
    # 计算到边界的距离
    distance = point.distance(nearest_boundary_point)
    
    # 确定哪个坐标值更大
    dx = abs(point.x - nearest_boundary_point.x)
    dy = abs(point.y - nearest_boundary_point.y)
    
    # 优先调整数值较大的坐标
    if dx > dy:
        # x坐标变化更大，优先调整x
        new_x = nearest_boundary_point.x
        # 计算y坐标，保持与原始点的比例关系
        ratio = dy / dx if dx != 0 else 0
        new_y = point.y + (nearest_boundary_point.x - point.x) * ratio
    else:
        # y坐标变化更大，优先调整y
        new_y = nearest_boundary_point.y
        # 计算x坐标，保持与原始点的比例关系
        ratio = dx / dy if dy != 0 else 0
        new_x = point.x + (nearest_boundary_point.y - point.y) * ratio
    
    new_point = Point(new_x, new_y)
    
    # 如果新点在DP3内，返回新点
    if dp3_polygon.contains(new_point):
        return new_point
    
    # 如果新点不在DP3内，返回边界点
    return nearest_boundary_point

def create_grid_points(polygon, grid_size):
    """在DP3多边形内创建网格点"""
    bounds = polygon.bounds
    minx, miny, maxx, maxy = bounds
    
    points = []
    x = minx
    while x <= maxx:
        y = miny
        while y <= maxy:
            point = Point(x, y)
            if polygon.contains(point):
                points.append(point)
            y += grid_size
        x += grid_size
    
    return points

def get_neighbors(point, grid_points, max_dist=None):
    """获取点的邻居节点"""
    if max_dist is None:
        # 根据点的分布自动计算合适的最大距离
        coords = np.array([(p.x, p.y) for p in grid_points])
        if len(coords) > 1:
            distances = np.sqrt(np.sum((coords[1:] - coords[0])**2, axis=1))
            max_dist = np.median(distances) * 2
    
    neighbors = []
    for p in grid_points:
        if p != point and point.distance(p) <= max_dist:
            neighbors.append(p)
    return neighbors

def heuristic(a, b):
    """启发式函数：计算两点间的欧氏距离"""
    return ((a.x - b.x) ** 2 + (a.y - b.y) ** 2) ** 0.5

def build_graph_from_dp3(dp3_polygon, grid_size=None):
    """从DP3多边形构建导航网络图"""
    if grid_size is None:
        bounds = dp3_polygon.bounds
        width = bounds[2] - bounds[0]
        height = bounds[3] - bounds[1]
        grid_size = min(width, height) / 30  # 使用更合理的网格密度

    # 创建网格点
    grid_points = create_grid_points(dp3_polygon, grid_size)
    print(f"生成了 {len(grid_points)} 个网格点")
    
    # 构建图
    G = nx.Graph()
    
    # 添加节点
    for i, p1 in enumerate(grid_points):
        node1 = (p1.x, p1.y)
        G.add_node(node1)
        
        # 连接到临近节点
        for p2 in grid_points[i+1:]:
            node2 = (p2.x, p2.y)
            distance = p1.distance(p2)
            # 如果距离在合理范围内，添加边
            if distance < grid_size * 2:  # 使用更合理的连接范围
                # 检查连线是否在多边形内
                line = LineString([node1, node2])
                if dp3_polygon.contains(line):
                    G.add_edge(node1, node2, weight=distance)
    
    print(f"构建了包含 {len(G.nodes)} 个节点和 {len(G.edges)} 条边的导航网络")
    return G, grid_points

def find_nearest_node(G, target_point):
    """找到图中最近的节点"""
    return min(G.nodes, key=lambda node: Point(node).distance(Point(target_point.x, target_point.y)))

def smooth_path_line(path_line, dp3_polygon):
    """平滑路径线"""
    if not path_line:
        return None
        
    # 将路径转换为更密集的点
    densified_coords = []
    coords = list(path_line.coords)
    for i in range(len(coords) - 1):
        p1 = coords[i]
        p2 = coords[i + 1]
        # 在两点之间插入额外的点
        for t in np.linspace(0, 1, 5):
            x = p1[0] * (1-t) + p2[0] * t
            y = p1[1] * (1-t) + p2[1] * t
            densified_coords.append((x, y))
    densified_coords.append(coords[-1])
    
    # 应用平滑
    smoothed_coords = []
    window_size = 5
    for i in range(len(densified_coords)):
        # 获取窗口内的点
        start = max(0, i - window_size // 2)
        end = min(len(densified_coords), i + window_size // 2 + 1)
        window = densified_coords[start:end]
        
        # 计算加权平均
        weights = np.exp(-np.arange(len(window)) ** 2 / (2 * (window_size/4) ** 2))
        weights = weights / np.sum(weights)
        
        x = sum(p[0] * w for p, w in zip(window, weights))
        y = sum(p[1] * w for p, w in zip(window, weights))
        
        # 确保平滑后的点仍在多边形内
        point = Point(x, y)
        if dp3_polygon.contains(point):
            smoothed_coords.append((x, y))
        else:
            smoothed_coords.append(densified_coords[i])
    
    return LineString(smoothed_coords)

def load_and_plot_geojson(layer_configs: List[LayerConfig], simplify_tolerance=0.1, output_html="map.html", navigation_points=None):
    try:
        # 定义与QGIS匹配的颜色
        layer_colors = {config.name: config.color for config in layer_configs}
        
        all_layers = []
        all_bounds = []
        cw_boxes = {}  # 用于存储CW方框的大小信息 {box_id: (width, height)}
        
        # 存储DP3多边形和导航点信息
        dp3_polygon = None
        start_point = None
        end_point = None
        navigation_path = None
        
        # 第一遍循环：收集所有图层的边界，并存储CW层的多边形信息
        for config in layer_configs:
            # logger.info(f"\n开始处理文件: {config.file_path}")
            gdf = gpd.read_file(config.file_path)
            # logger.info(f"- 读取到 {len(gdf)} 个要素")
            # logger.info(f"- 坐标系统: {gdf.crs}")
            
            if gdf.crs is None:
                logger.info("- 设置默认坐标系统 EPSG:2435")
                gdf.set_crs("EPSG:2435", inplace=True)
            
            # 存储DP3多边形
            if config.name == '0-DP3':
                for idx, row in gdf.iterrows():
                    geom = row.geometry
                    if geom is not None and not geom.is_empty:
                        if hasattr(geom, 'has_z'):
                            geom = convert_3d_to_2d(geom)
                        dp3_polygon = geom
                        break
            
            # 存储导航起点和终点
            if config.name == '0-BH' and navigation_points:
                # logger.info(f"\n正在查找导航点...")
                # logger.info(f"起点: {navigation_points[0]}")
                # logger.info(f"终点: {navigation_points[1]}")
                
                for idx, row in gdf.iterrows():
                    if 'Text' in row and row['Text'].upper() in [p.upper() for p in navigation_points]:
                        point = row.geometry
                        if point is not None and not point.is_empty:
                            if navigation_points[0].upper() == row['Text'].upper():
                                start_point = point
                                logger.info(f"找到起点: {row['Text']} 坐标: ({point.x}, {point.y})")
                            elif navigation_points[1].upper() == row['Text'].upper():
                                end_point = point
                                logger.info(f"找到终点: {row['Text']} 坐标: ({point.x}, {point.y})")
            
            # 如果是CW层，记录每个方框的大小
            if config.name == '0-CW':
                for idx, row in gdf.iterrows():
                    geom = row.geometry
                    if geom is not None and not geom.is_empty:
                        if hasattr(geom, 'has_z'):
                            geom = convert_3d_to_2d(geom)
                        # 计算多边形的中心点
                        centroid = geom.centroid
                        cw_boxes[idx] = {
                            'geometry': geom,
                            'centroid': centroid
                        }
            
            bounds = gdf.total_bounds
            print(f"- 边界范围: {bounds}")
            all_bounds.append(bounds)
        
        # 计算所有图层的总边界
        if all_bounds:
            min_x = min(bound[0] for bound in all_bounds)
            min_y = min(bound[1] for bound in all_bounds)
            max_x = max(bound[2] for bound in all_bounds)
            max_y = max(bound[3] for bound in all_bounds)
            total_width = max_x - min_x
            total_height = max_y - min_y
            
            view_width = 1600
            view_height = 1200
            base_scale = min(view_width / total_width, view_height / total_height)
            
            # logger.info(f"\n总体信息:")
            # logger.info(f"- 总边界: ({min_x}, {min_y}, {max_x}, {max_y})")
            # logger.info(f"- 总宽度: {total_width}")
            # logger.info(f"- 总高度: {total_height}")
            # logger.info(f"- 基础缩放比例: {base_scale}")
        
        # 在找到起点和终点后，计算导航路径的显示范围
        nav_scale = base_scale
        if start_point and end_point:
            # 计算起点和终点的坐标差值
            dx = abs(end_point.x - start_point.x)
            dy = abs(end_point.y - start_point.y)
            
            # 添加20%的边距
            margin = 0.2
            dx = dx * (1 + margin)
            dy = dy * (1 + margin*1.5)
            
            # 计算比例
            target_width = 1600
            target_height = 1200
            target_ratio = target_width / target_height  # 4:3
            path_ratio = dx / dy if dy != 0 else float('inf')
            
            # logger.info(f"\n计算显示范围:")
            # logger.info(f"- 路径x轴差值: {dx}")
            # logger.info(f"- 路径y轴差值: {dy}")
            # logger.info(f"- 路径宽高比: {path_ratio:.2f}")
            # logger.info(f"- 目标宽高比: {target_ratio:.2f}")
            
            # 根据比例决定缩放参考
            if path_ratio > target_ratio:
                # x轴差值较大，以x轴为基准
                nav_scale = target_width / dx
                # logger.info("- 使用x轴作为缩放参考")
            else:
                # y轴差值较大，以y轴为基准
                nav_scale = target_height / dy
                # logger.info("- 使用y轴作为缩放参考")
            # logger.info(f"nav_scale: {nav_scale}")
            # 计算中心点
            center_x = (start_point.x + end_point.x) / 2
            center_y = (start_point.y + end_point.y) / 2
            
            # 计算显示范围
            view_width = target_width / nav_scale
            view_height = target_height / nav_scale
            
            # 更新边界值
            min_x = center_x - view_width / 2
            max_x = center_x + view_width / 2
            min_y = center_y - view_height / 2
            max_y = center_y + view_height / 2
            
            # logger.info(f"- 导航缩放比例: {nav_scale:.2f}")
            # logger.info(f"- 显示范围: ({min_x:.2f}, {min_y:.2f}, {max_x:.2f}, {max_y:.2f})")
            
            # 更新SVG视图大小
            view_width = target_width
            view_height = target_height
            
            # 计算缩放比率
            scale_ratio = nav_scale / base_scale
            # logger.info(f"- 缩放比率: {scale_ratio:.2f}")
        
        else:
            # 如果没有导航点，使用原来的计算方式
            min_x = min(bound[0] for bound in all_bounds)
            min_y = min(bound[1] for bound in all_bounds)
            max_x = max(bound[2] for bound in all_bounds)
            max_y = max(bound[3] for bound in all_bounds)
            total_width = max_x - min_x
            total_height = max_y - min_y
            
            view_width = 1600
            view_height = 1200
            nav_scale = min(view_width / total_width, view_height / total_height)
        
        # 如果有导航需求且找到了所有必要的点
        if dp3_polygon and navigation_points:
            try:
                # logger.info("\n开始处理导航路径...")
                start_point = None
                end_point = None
                
                # 遍历所有图层找到BH点
                for config in layer_configs:
                    if config.name == '0-BH':
                        # logger.info(f"在 {config.file_path} 中查找导航点: {navigation_points}")
                        gdf = gpd.read_file(config.file_path)
                        for idx, row in gdf.iterrows():
                            if 'Text' in row and row['Text'] in navigation_points:
                                point = row.geometry
                                if point is not None and not point.is_empty:
                                    if navigation_points[0] == row['Text']:
                                        start_point = point
                                        # logger.info(f"找到起点: {row['Text']} 坐标: ({point.x}, {point.y})")
                                    elif navigation_points[1] == row['Text']:
                                        end_point = point
                                        # logger.info(f"找到终点: {row['Text']} 坐标: ({point.x}, {point.y})")
                
                if start_point and end_point:
                    # logger.info("开始生成导航路径...")
                    # 确保起点和终点在DP3范围内
                    if not dp3_polygon.contains(start_point):
                        start_point = find_nearest_point_in_dp3(start_point, dp3_polygon)
                        # logger.info(f"调整起点到DP3范围内: ({start_point.x}, {start_point.y})")
                    if not dp3_polygon.contains(end_point):
                        end_point = find_nearest_point_in_dp3(end_point, dp3_polygon)
                        # logger.info(f"调整终点到DP3范围内: ({end_point.x}, {end_point.y})")
                    
                    # 构建导航网络
                    G, grid_points = build_graph_from_dp3(dp3_polygon)
                    
                    # 找到最近的网络节点
                    start_node = find_nearest_node(G, start_point)
                    end_node = find_nearest_node(G, end_point)
                    
                    # logger.info(f"起点对应的网络节点: {start_node}")
                    # logger.info(f"终点对应的网络节点: {end_node}")
                    
                    try:
                        # 使用Dijkstra算法找到最短路径
                        path_nodes = nx.shortest_path(G, start_node, end_node, weight="weight")
                        # logger.info("找到路径，节点数量: %d", len(path_nodes))
                        
                        # 转换为LineString并确保在DP3范围内
                        path_line = LineString(path_nodes)
                        if not dp3_polygon.contains(path_line):
                            path_line = path_line.intersection(dp3_polygon)

                        # 假设 path_line 已经是 LineString，start_point 是 Point
                        coords = list(path_line.coords)

                        # 检查 start_point 是否已经是第一个点（避免重复添加）
                        if (start_point.x, start_point.y) != coords[0]:
                            coords.insert(0, (start_point.x, start_point.y))
                        if (end_point.x, end_point.y) != coords[-1]:
                            coords.append((end_point.x, end_point.y))

                        # 重新生成 LineString
                        path_line = LineString(coords)

                        # 平滑路径
                        navigation_path = smooth_path_line(path_line, dp3_polygon)
                        # logger.info("路径平滑完成")
                        
                        # 将导航路径添加到新图层
                        nav_layer = {
                            'name': 'navigation',
                            'color': '#FFD700',  # 金色
                            'paths': [],
                            'texts': []
                        }
                        
                        # 转换路径坐标
                        coords = list(navigation_path.coords)
                        nav_path = f"M {(coords[0][0]-min_x)*nav_scale} {(max_y-coords[0][1])*nav_scale}"
                        for x, y in coords[1:]:
                            nav_path += f" L {(x-min_x)*nav_scale} {(max_y-y)*nav_scale}"
                        
                        nav_layer['paths'].append({
                            'd': nav_path,
                            'fill': False,
                            'class': 'navigation-path',
                            'extra_svg': 'stroke-dasharray="12,8"'
                        })
                        
                        all_layers.append(nav_layer)
                        # logger.info("添加了导航图层")
                        
                    except nx.NetworkXNoPath:
                        # logger.warning("未找到有效路径")
                        pass
                else:
                    # logger.warning(f"未找到导航点: {navigation_points}")
                    pass
                    if not start_point:
                        # logger.warning(f"- 未找到起点: {navigation_points[0]}")
                        pass
                    if not end_point:
                        # logger.warning(f"- 未找到终点: {navigation_points[1]}")
                        pass
            except Exception as e:
                # logger.error(f"导航路径生成错误: {str(e)}")
                import traceback
                # logger.error(traceback.format_exc())
        
        # 第二遍循环：处理每个图层
        for i, config in enumerate(layer_configs):
            # logger.info(f"\n处理图层 {config.file_path} 的几何图形")
            gdf = gpd.read_file(config.file_path)
            
            # 生成SVG路径和文本
            svg_paths = []
            svg_texts = []
            # 获取图层名称
            layer_name = config.name
            # logger.info(f"layer_name: {layer_name}")

            base_size = 52
            text_size = base_size * nav_scale * 22  # 默认字体大小 20px
            # logger.info(f"text_size: {text_size}")

            for idx, row in gdf.iterrows():
                geom = row.geometry
                if geom is None or geom.is_empty:
                    continue
                
                try:
                    # 确保几何图形是2D的
                    if hasattr(geom, 'has_z'):
                        geom = convert_3d_to_2d(geom)                    
 
                    # 对于BH层的点，找到对应的CW多边形中心点，要怎么找中心点？
                    if layer_name == '0-BH' and geom.geom_type == 'Point':
                        if 'Text' in row:
                            # 找到最近的CW多边形
                            min_dist = float('inf')
                            nearest_centroid = None
                            nearest_polygon = None
                            
                            for cw_info in cw_boxes.values():
                                cw_geom = cw_info['geometry']
                                if cw_geom.contains(geom):
                                    nearest_centroid = cw_info['centroid']
                                    nearest_polygon = cw_geom
                                    break
                                dist = geom.distance(cw_info['centroid'])
                                if dist < min_dist:
                                    min_dist = dist
                                    nearest_centroid = cw_info['centroid']
                                    nearest_polygon = cw_geom
                            
                            if nearest_centroid and nearest_polygon:
                                x = (nearest_centroid.x - min_x) * nav_scale
                                y = (max_y - nearest_centroid.y) * nav_scale
                                
                                # 计算多边形的方向
                                bounds = nearest_polygon.bounds
                                width = bounds[2] - bounds[0]
                                height = bounds[3] - bounds[1]
                                # 如果高度大于宽度，说明是竖直的框
                                rotation = 90 if height > width * 1.2 else 0                                

                                svg_texts.append({
                                    'x': x,
                                    'y': y,
                                    'text': row['Text'],
                                    'size': text_size,
                                    'rotation': rotation
                                })
                        continue
                    
                    if geom.geom_type == 'LineString':
                        coords = list(geom.coords)
                        if len(coords) < 2:
                            continue
                        path = f"M {(coords[0][0]-min_x)*nav_scale} {(max_y-coords[0][1])*nav_scale}"
                        for x, y, *_ in coords[1:]:
                            path += f" L {(x-min_x)*nav_scale} {(max_y-y)*nav_scale}"
                        svg_paths.append({'d': path, 'fill': False})
                    elif geom.geom_type == 'MultiLineString':
                        for line in geom.geoms:
                            coords = list(line.coords)
                            if len(coords) < 2:
                                continue
                            path = f"M {(coords[0][0]-min_x)*nav_scale} {(max_y-coords[0][1])*nav_scale}"
                            for x, y, *_ in coords[1:]:
                                path += f" L {(x-min_x)*nav_scale} {(max_y-y)*nav_scale}"
                            svg_paths.append({'d': path, 'fill': False})
                    elif geom.geom_type == 'Polygon':
                        # 处理外部轮廓
                        coords = list(geom.exterior.coords)
                        if len(coords) < 3:
                            continue
                        path = f"M {(coords[0][0]-min_x)*nav_scale} {(max_y-coords[0][1])*nav_scale}"
                        for x, y, *_ in coords[1:]:
                            path += f" L {(x-min_x)*nav_scale} {(max_y-y)*nav_scale}"
                        path += " Z"
                        
                        # 处理内部孔洞
                        if layer_name == '0-DP3':
                            # logger.info(f"处理DP3多边形的孔洞，共有 {len(list(geom.interiors))} 个孔洞")
                            pass
                        for interior in geom.interiors:
                            coords = list(interior.coords)
                            if len(coords) < 3:
                                continue
                            # 确保孔洞的点是逆时针方向
                            path += f" M {(coords[0][0]-min_x)*nav_scale} {(max_y-coords[0][1])*nav_scale}"
                            for x, y, *_ in coords[1:]:
                                path += f" L {(x-min_x)*nav_scale} {(max_y-y)*nav_scale}"
                            path += " Z"
                            
                        # 为DP3层添加填充属性
                        if layer_name == '0-DP3':
                            svg_paths.append({
                                'd': path,
                                'fill': True,
                                'fill-rule': 'evenodd'  # 使用evenodd规则处理孔洞
                            })
                        else:
                            svg_paths.append({'d': path, 'fill': False})
                    elif geom.geom_type == 'MultiPolygon':
                        for polygon in geom.geoms:
                            # 处理外部轮廓
                            coords = list(polygon.exterior.coords)
                            if len(coords) < 3:
                                continue
                            path = f"M {(coords[0][0]-min_x)*nav_scale} {(max_y-coords[0][1])*nav_scale}"
                            for x, y, *_ in coords[1:]:
                                path += f" L {(x-min_x)*nav_scale} {(max_y-y)*nav_scale}"
                            path += " Z"
                            
                            # 处理内部孔洞
                            if layer_name == '0-DP3':
                                # logger.info(f"处理DP3 MultiPolygon的孔洞，共有 {len(list(polygon.interiors))} 个孔洞")
                                pass
                            for interior in polygon.interiors:
                                coords = list(interior.coords)
                                if len(coords) < 3:
                                    continue
                                # 确保孔洞的点是逆时针方向
                                path += f" M {(coords[0][0]-min_x)*nav_scale} {(max_y-coords[0][1])*nav_scale}"
                                for x, y, *_ in coords[1:]:
                                    path += f" L {(x-min_x)*nav_scale} {(max_y-y)*nav_scale}"
                                path += " Z"
                                
                            # 为DP3层添加填充属性
                            if layer_name == '0-DP3':
                                svg_paths.append({
                                    'd': path,
                                    'fill': True,
                                    'fill-rule': 'evenodd'  # 使用evenodd规则处理孔洞
                                })
                            else:
                                svg_paths.append({'d': path, 'fill': False})
                except Exception as e:
                    # logger.warning(f"警告: 处理第 {idx} 个几何图形时出错: {str(e)}")
                    continue
            
            # 获取文件名作为图层名称
            layer_name = config.name
            layer_color = layer_colors.get(layer_name, '#000000')  # 默认黑色
            
            all_layers.append({
                'name': layer_name,
                'color': layer_color,
                'paths': svg_paths,
                'texts': svg_texts
            })
            # logger.info(f"- 完成处理: {layer_name}, 路径数量: {len(svg_paths)}, 文本数量: {len(svg_texts)}")
        
        # 生成图层内容
        layers_content = ""
        for i, layer in enumerate(all_layers):
            layers_content += f'<g id="layer_{i}" class="layer">'
            
            # 添加路径
            for path in layer['paths']:
                fill_attr = f'fill="{layer["color"]}" fill-rule="{path.get("fill-rule", "nonzero")}" class="dp3-path"' if path.get("fill", False) else 'fill="none"'
                dash = ''
                if path.get('class') == 'navigation-path':
                    dash = 'stroke-dasharray="12,8"'
                layers_content += f'<path d="{path["d"]}" stroke="{layer["color"]}" {fill_attr} {dash}/>'
                
            # 添加文本
            for text in layer['texts']:
                class_attr = 'class="nav-point"' if text.get("is_nav_point") else ''
                container_class = 'nav-point-container' if text.get("is_nav_point") else 'text-container'
                display_text = text.get("nav_text") if text.get("is_nav_point") else text["text"]
                layers_content += f'<g class="{container_class}"><text x="{text["x"]}" y="{text["y"]}" transform="rotate({text["rotation"]}, {text["x"]}, {text["y"]})" {class_attr} style="font-size: {text_size}px">{display_text}</text></g>'
            
            # 如果是导航图层，添加起点和终点标记
            if layer['name'] == 'navigation' and layer['paths']:
                # 直接用LineString的第一个和最后一个点
                nav_coords = None
                if 'paths' in layer and layer['paths'] and hasattr(navigation_path, 'coords'):
                    nav_coords = list(navigation_path.coords)
                if nav_coords and len(nav_coords) > 1:
                    start_coord = nav_coords[0]
                    end_coord = nav_coords[-1]
                    # 圆心直接用start_point和end_point的坐标
                    start_x = (start_point.x - min_x) * nav_scale
                    start_y = (max_y - start_point.y) * nav_scale
                    end_x = (end_point.x - min_x) * nav_scale
                    end_y = (max_y - end_point.y) * nav_scale
                    # 起点图标（白底，绿色细描边，黑色大字，字符居中）
                    layers_content += f'''
                    <g class="nav-label-container" transform-origin="center">
                        <circle cx="{start_x}" cy="{start_y}" r="{text_size}" fill="#fff" stroke="#43c463" stroke-width="10"/>
                        <text x="{start_x}" y="{start_y}" text-anchor="middle" font-size="{text_size*1.5}" font-weight="bold" fill="#111" dominant-baseline="middle">起</text>
                    </g>
                    '''
                    # 终点图标（白底，蓝色细描边，黑色大字，字符居中）
                    layers_content += f'''
                    <g class="nav-label-container" transform-origin="center">
                        <circle cx="{end_x}" cy="{end_y}" r="{text_size}" fill="#fff" stroke="#1e90ff" stroke-width="10"/>
                        <text x="{end_x}" y="{end_y}" text-anchor="middle" font-size="{text_size*1.5}" font-weight="bold" fill="#111" dominant-baseline="middle">终</text>
                    </g>
                    '''
            
            layers_content += '</g>'

        # 生成图层控制内容
        base_layers_controls = ""
        marker_layers_controls = ""
        navigation_layers_controls = ""
        
        for i, layer in enumerate(all_layers):
            config = next((c for c in layer_configs if c.name == layer["name"]), None)
            if config:
                if config.is_base:
                    base_layers_controls += f'<label><input type="checkbox" checked onchange="toggleLayer({i})"> {layer["name"]}</label>'
                elif config.is_marker:
                    marker_layers_controls += f'<label><input type="checkbox" checked onchange="toggleLayer({i})"> {layer["name"]}</label>'
                elif config.is_navigation:
                    navigation_layers_controls += f'<label><input type="checkbox" checked onchange="toggleLayer({i})"> {layer["name"]}</label>'

        # 读取模板文件
        template_path = os.path.join(script_dir, "map_template.html")
        with open(template_path, 'r', encoding='utf-8') as f:
            template_content = f.read()

        # 替换模板中的变量
        html_content = template_content.format(
            view_width=view_width,
            view_height=view_height,
            layers_content=layers_content,
            base_layers_controls=base_layers_controls,
            marker_layers_controls=marker_layers_controls,
            navigation_layers_controls=navigation_layers_controls
        )

        # 不再写入文件，直接返回 SVG/HTML 字符串
        # with open(output_html, 'w', encoding='utf-8') as f:
        #     f.write(html_content)
        logger.info(f"\n✅ 已生成导航SVG内容")
        return html_content
        
    except Exception as e:
        logger.error(f"\n❌ 加载或绘制失败：{str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def viewmap_main(position=None, start_point="B1-001", layer_configs: Optional[List[LayerConfig]] = None):
    # 如果没有提供图层配置，使用默认配置
    if layer_configs is None:
        layer_configs = LayerConfig.get_default_configs(script_dir)
    
    # 设置默认起点和动态终点，确保都是大写
    default_start = start_point.upper() if start_point else "B1-001"
    if position:
        # 如果传入了终点位置，使用传入的位置（转换为大写）
        navigation_points = [default_start, position.upper()]
        # logger.info(f"\n开始处理导航请求:")
        # logger.info(f"- 起点: {default_start}")
        # logger.info(f"- 终点: {position.upper()}")
    else:
        # 如果没有传入终点位置，使用默认值
        navigation_points = [default_start, "B1-190"]
        # logger.info(f"\n使用默认导航点:")
        # logger.info(f"- 起点: {default_start}")
        # logger.info(f"- 终点: B1-190")
    
    #logger.info(f"- 图层配置: {[config.name for config in layer_configs]}")
    
    # 获取当前脚本所在目录的上级目录
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # 构建输出路径
    output_path = os.path.join(parent_dir, "static", "navigation_map.html")
    
    # 确保输出目录存在
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # 显示多图层地图，包含导航路径
    result = load_and_plot_geojson(
        layer_configs,
        simplify_tolerance=1.0,
        output_html=output_path,
        navigation_points=navigation_points
    )
    
    return result  # result 就是 SVG 字符串（或 False）

# 示例用法
if __name__ == "__main__":
    # 使用默认配置
    # viewmap_main()
    
    # 使用 B1 区域地图文件的配置
    b1_configs = [
        LayerConfig(
            name="0-DP3",  # 保持原有图层名称
            file_path=os.path.join(script_dir, "map", "0-DP3_B2.geojson"),  # 使用 B1 区域文件
            color="#444444",
            is_base=True
        ),
        LayerConfig(
            name="0-BH",  # 保持原有图层名称
            file_path=os.path.join(script_dir, "map", "0-BH_B2.geojson"),  # 使用 B1 区域文件
            color="#964B00",
            is_marker=True
        ),
        LayerConfig(
            name="0-DP2",  # 保持原有图层名称
            file_path=os.path.join(script_dir, "map", "0-DP2_B2.geojson"),  # 使用 B1 区域文件
            color="#FF0000",
            is_marker=True
        ),
        LayerConfig(
            name="0-CW",  # 保持原有图层名称
            file_path=os.path.join(script_dir, "map", "0-CW_B2.geojson"),  # 使用 B1 区域文件
            color="#0000FF",
            is_base=True
        )
    ]
    
    # 使用 B1 区域配置生成导航地图
    viewmap_main(position="B1-068", start_point="B1-001", layer_configs=b1_configs)
    
    # 使用自定义配置示例（保留原有注释代码）
    # custom_configs = [
    #     LayerConfig(
    #         name="custom-layer",
    #         file_path=os.path.join(script_dir, "map", "custom.geojson"),
    #         color="#FF00FF",
    #         is_base=True
    #     ),
    #     # 添加更多自定义图层...
    # ]
    # viewmap_main(layer_configs=custom_configs)

# 确保函数可以被其他模块导入
__all__ = ['viewmap_main', 'load_and_plot_geojson', 'LayerConfig']

