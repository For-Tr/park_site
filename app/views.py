from django.shortcuts import render
from django.db.models import Q
from app import models
from django.core.paginator import Paginator
import json
from django.http import JsonResponse
from django.views import View
import logging
from .base import *
from pathlib import Path
import pandas as pd
from django.conf import settings
from relate.read_dbdata import DBReader
from .models import SiteConfigeration
from datetime import datetime, timedelta
from relate import viewmap
import os
import sys
import csv

logger = logging.getLogger('app')  # 使用您在 LOGGING 配置中定义的日志器名称

def chinese_to_hex(input_str):
    hex_str = input_str.encode('utf-8').hex()
    
    while len(hex_str) < 60:
        hex_str = 'f' + hex_str
    
    return hex_str[:60]  

def hex_to_chinese(hex_str):
    # 移除前导的'f'字符
    hex_str = hex_str.lstrip('f')
    
    byte_data = bytes.fromhex(hex_str)    
    chinese_str = byte_data.decode('utf-8')
    
    return chinese_str


class IndexView(View):
    def get(self, request, *args, **kwargs):
        return render(request, 'index.html', {"active": "index"})

# 新增的三个视图函数
def index1_view(request):
    return render(request, 'index1.html')

def home_view(request):
    return render(request, 'home.html')

def get_guide_screen_status(request):
    reader = DBReader()
    stats = reader.get_guide_screen_status()
    # print(f"stats: {stats}")
    
    # 处理每个引导屏的名称
    for screen in stats:
        if 'guide_screen_name' in screen:
            screen['guide_screen_name'] = hex_to_chinese(screen['guide_screen_name'])
    
    return JsonResponse(stats, safe=False)

def get_timeout_status(request):
    reader = DBReader()
    status = reader.get_timeout_status()
    
    devices = []
    current_time = datetime.strptime(status['current_time'], '%Y-%m-%d %H:%M:%S')
    
    for panel in status['panel']:
        # 解码设备名称（去掉前导 'f' 并转换 hex 为 utf-8）
        name = panel['name']
        if name.startswith('f'):
            try:
                name = bytes.fromhex(name.lstrip('f')).decode('utf-8')
            except:
                name = '未知设备'
        
        # 计算最后更新时间
        last_updated = datetime.strptime(panel['last_updated'], '%Y-%m-%d %H:%M:%S')
        time_diff = (current_time - last_updated).total_seconds() / 3600  # 转换为小时
        
        devices.append({
            'id': panel['screen_id'],
            'name': name,
            'status': '离线' if time_diff > 1 else '在线',  # 超过1小时判定为离线
            'last_update': panel['last_updated']
        })
    
    return JsonResponse(devices, safe=False)

class SearchDataView(View):
    def get(self, request):
        return render(request, "search_data.html", {"active": "search_data"})

def search_by_plate(request):
    try:
        plate = request.GET.get('plate', '')
        reader = DBReader()
        results = reader.search_by_partial_plate(plate)
        return JsonResponse({'code': 200, 'data': results})
    except Exception as e:
        return JsonResponse({'code': 500, 'message': str(e)})

def device_status(request):
    reader = DBReader()
    status = reader.get_timeout_status()
    
    # 重新组织数据结构
    result = {
        'screens': [],
        'nodes': []
    }
    
    # 分类处理设备
    for device in status['panel']:
        # 处理名称的中文转换
        name = device['name']
        if name and name.startswith('f'):
            try:
                # 转换为中文并去除可能的换行符
                name = bytes.fromhex(name.lstrip('f')).decode('utf-8').strip().replace('\n', '')
            except:
                name = '未知设备'
        
        if device['sort'] == 'panel':
            result['screens'].append({
                'name': name,
                'address': device['address'],
                'last_updated': device['last_updated']
            })
        elif device['sort'] == 'node':

            result['nodes'].append({
                'position': device['position'],  # 添加车位位置
                'address': device['address'],
                'address1': device['address1'],
                'name': name,  # 使用处理后的名称
                'last_updated': device['last_updated']
            })
    
    return JsonResponse(result)

def navigate_to_position(request):
    position = request.GET.get('position')
    start = request.GET.get('start')
    
    if not position:
        logger.error("未提供位置信息")
        return JsonResponse({'error': '未提供位置信息'}, status=400)
    
    if not start:
        logger.error("未提供起点位置")
        return JsonResponse({'error': '未提供起点位置'}, status=400)
    
    try:
        # 确保位置编号都是大写
        position = position.upper() if position else None
        start = start.upper() if start else None
        
        logger.info(f"收到导航请求，起点: {start}, 目标位置: {position}")
        if position[:2] != start[:2]:
            logger.error(f"起点和目标位置不在同一区域: {start} -> {position}")
            return JsonResponse({
                'success': False,
                'error': '起点和目标位置不在同一区域'
            }, status=400)
        
        # 定义B1和B2的图层配置
        script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        b1_configs = [
            viewmap.LayerConfig(
                name="0-DP3",
                file_path=os.path.join(script_dir, "relate", "map", "0-DP3_B1.geojson"),
                color="#A0A0A0",
                is_base=True
            ),
            viewmap.LayerConfig(
                name="0-BH",
                file_path=os.path.join(script_dir, "relate", "map", "0-BH_B1.geojson"),
                color="#964B00",
                is_marker=True
            ),
            viewmap.LayerConfig(
                name="0-DP2",
                file_path=os.path.join(script_dir, "relate", "map", "0-DP2_B1.geojson"),
                color="#FF0000",
                is_marker=True
            ),
            viewmap.LayerConfig(
                name="0-CW",
                file_path=os.path.join(script_dir, "relate", "map", "0-CW_B1.geojson"),
                color="#0000FF",
                is_base=True
            )
        ]

        b2_configs = [
            viewmap.LayerConfig(
                name="0-DP3",
                file_path=os.path.join(script_dir, "relate", "map", "0-DP3_B2.geojson"),
                color="#444444",
                is_base=True
            ),
            viewmap.LayerConfig(
                name="0-BH",
                file_path=os.path.join(script_dir, "relate", "map", "0-BH_B2.geojson"),
                color="#964B00",
                is_marker=True
            ),
            viewmap.LayerConfig(
                name="0-DP2",
                file_path=os.path.join(script_dir, "relate", "map", "0-DP2_B2.geojson"),
                color="#FF0000",
                is_marker=True
            ),
            viewmap.LayerConfig(
                name="0-CW",
                file_path=os.path.join(script_dir, "relate", "map", "0-CW_B2.geojson"),
                color="#0000FF",
                is_base=True
            )
        ]

        # 根据position前缀选择配置
        position_prefix = position[:2].upper() if position else "B1"  # 默认为B1
        selected_configs = b2_configs if position_prefix == "B2" else b1_configs

        # 使用选定的配置创建地图
        map_html = viewmap.viewmap_main(
            position=position,
            start_point=start,
            layer_configs=selected_configs
        )
        
        if map_html:
            # 检查生成的文件是否存在
            map_file = os.path.join(settings.BASE_DIR, 'static', 'navigation_map.html')
            if os.path.exists(map_file):
                logger.info(f"导航地图生成成功: {map_file}")
                # 返回成功响应，包含地图URL
                return JsonResponse({
                    'success': True,
                    'map_url': '/static/navigation_map.html',
                    'start_point': start,
                    'end_point': position
                })
            else:
                logger.error(f"导航地图文件未生成: {map_file}")
                return JsonResponse({
                    'success': False,
                    'error': '导航地图文件未生成'
                }, status=500)
        else:
            logger.error("生成导航地图失败")
            return JsonResponse({
                'success': False,
                'error': '生成导航地图失败'
            }, status=500)
            
    except Exception as e:
        logger.error(f"❌ 生成导航地图时出错: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return JsonResponse({
            'success': False,
            'error': f'生成导航地图时出错: {str(e)}'
        }, status=500)

def navigation_map(request):
    # 获取起点和终点参数
    start_point = request.GET.get('start')
    end_point = request.GET.get('end')
    
    if not start_point:
        return JsonResponse({
            'success': False,
            'error': '未提供起点位置'
        }, status=400)
    
    context = {
        'start_point': start_point,
        'end_point': end_point
    }
    return render(request, 'navigation_map.html', context)

def search_data_view(request, start_point=None):
    # 不设置默认值，让前端处理
    return render(request, "search_data.html", {
        "active": "search_data",
        "start_point": start_point  # 移除默认值
    })

def get_location_options(request):
    try:
        # 读取 BH_texts.csv 文件
        csv_path = os.path.join(settings.BASE_DIR, 'relate', 'map', 'BH_texts.csv')
        locations = []
        
        with open(csv_path, 'r', encoding='utf-8') as f:
            csv_reader = csv.reader(f)
            next(csv_reader)  # 跳过标题行
            for row in csv_reader:
                if row and row[0].strip():  # 确保行不为空且第一个元素不为空
                    locations.append(row[0].strip())
        
        return JsonResponse({
            'code': 200,
            'data': sorted(locations)  # 返回排序后的位置列表
        })
    except Exception as e:
        logger.error(f"获取位置选项失败: {str(e)}")
        return JsonResponse({
            'code': 500,
            'message': f'获取位置选项失败: {str(e)}'
        })
