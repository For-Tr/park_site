#!/bin/bash

# 删除relate目录下的parking_system相关文件
rm -f relate/db/parking_system*
sleep 3

# 运行数据库初始化脚本
python relate/make_move_db.py
sleep 10

# 运行流程控制脚本
exec python relate/run_flow_loop.py
