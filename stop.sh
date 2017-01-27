#!/bin/sh
# -*- coding: utf-8 -*-


pid=`ps aux | grep proxy_spider/start.py | grep -v grep | awk '{print $2}'`
echo "pid: $pid"
ps aux | grep proxy_spider/start.py | grep -v grep | awk '{print $2}' | xargs -i kill {}
echo "killed"
ps aux | grep proxy_spider/start.py