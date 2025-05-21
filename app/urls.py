from django.urls import path
from app import views
from django.conf import settings
from django.conf.urls.static import static
import os

urlpatterns = [
    path('', views.SearchDataView.as_view(), name='search_data'),
    path("index/", views.IndexView.as_view(), name="index"), 
    path('api/guide-screen-status/', views.get_guide_screen_status, name='guide-screen-status'),
    path('api/device-status/',views.device_status, name = 'device_status'),
    path('search/', views.search_data_view, name='search_data'),
    path('search/<str:start_point>/', views.search_data_view, name='search_data_with_start'),
    path('api/search-by-plate/', views.search_by_plate, name='search-by-plate'),
    path('home/', views.index1_view, name='index1'),
    # 导航相关路由
    path('navigate/', views.navigate_to_position, name='navigate'),
    path('navigation-map/', views.navigation_map, name='navigation_map'),
    # 位置选项相关路由
    path('api/location-options/', views.get_location_options, name='location-options'),
]

# 在开发环境中添加静态文件服务
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static('/static/', document_root=os.path.join(settings.BASE_DIR, 'static'))
