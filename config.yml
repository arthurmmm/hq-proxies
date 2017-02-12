#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import sys
import time
import random
import unittest
import yaml
from redis import StrictRedis
from threading import Thread
from datetime import datetime
import logging
from logging.handlers import RotatingFileHandler

if __name__ == '__main__':
    LOCAL_CONFIG_YAML = '/etc/hq-proxies.yml'
    with open(LOCAL_CONFIG_YAML, 'r') as f:
        LOCAL_CONFIG = yaml.load(f)
    fetchcmd = 'scrapy crawl proxy_fetch'
    checkcmd = 'scrapy crawl proxy_check > /dev/null 2>&1'
    log_path = '/data/logs/hq-proxies.log'
else:
    print('测试模式！')
    LOCAL_CONFIG_YAML = '/etc/hq-proxies.test.yml'
    with open(LOCAL_CONFIG_YAML, 'r') as f:
        LOCAL_CONFIG = yaml.load(f)
    fetchcmd = 'scrapy crawl proxy_fetch -a mode=test'
    checkcmd = 'scrapy crawl proxy_check -a mode=test'
    log_path = '/data/logs/hq-proxies.test.log'

FORMAT = '%(asctime)s %(levelno)s/%(lineno)d: %(message)s'
logging.basicConfig(level=logging.DEBUG, format=FORMAT)    
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter(fmt=FORMAT)
rfh = RotatingFileHandler(log_path, maxBytes=1*1024*1024, backupCount=10)
rfh.setFormatter(formatter)
rfh.setLevel(logging.DEBUG)
logger.addHandler(rfh)

# redis keys
PROXY_COUNT = 'hq-proxies:proxy_count'
PROXY_SET = 'hq-proxies:proxy_pool'
PROXY_PROTECT = 'hq-proxies:proxy_protect'
PROXY_REFRESH = 'hq-proxies:proxy_refresh'

# mongo collections
VENDORS = 'vendors'
VALIDATORS = 'validators'
    
redis_db = StrictRedis(
    host=LOCAL_CONFIG['REDIS_HOST'], 
    port=LOCAL_CONFIG['REDIS_PORT'], 
    password=LOCAL_CONFIG['REDIS_PASSWORD'],
    db=LOCAL_CONFIG['REDIS_DB']
)

PROXY_LOW = 5
PROXY_EXHAUST = 2

CHECK_INTERVAL = 10
LOOP_DELAY = 20
PROTECT_SEC = 600
REFRESH_SEC = 3600 * 24

def startFetch(reason=None, fetchcmd='scrapy crawl proxy_fetch > /dev/null 2>&1'):
    logger.info(reason)
    redis_db.setex(PROXY_PROTECT, PROTECT_SEC, True)
    redis_db.setex(PROXY_REFRESH, REFRESH_SEC, True)
    os.system(fetchcmd)

def proxyFetch(single_run=False):
    while True:
        protect_ttl = redis_db.ttl(PROXY_PROTECT)
        refresh_ttl = redis_db.ttl(PROXY_REFRESH)
        
        pcount = redis_db.get(PROXY_COUNT)
        if not pcount:
            pcount = 0
        else:
            pcount = int(pcount)
        logger.info('代理数量：%s' % pcount)
        if pcount < PROXY_LOW and protect_ttl <= 0:
            startFetch('代理池存量低了，需要补充些代理... (*゜ー゜*)', fetchcmd)
        elif pcount < PROXY_EXHAUST:
            startFetch('代理池即将耗尽啦，需要立即补充些代理... Σ( ° △ °|||)', fetchcmd)
        elif pcount < PROXY_LOW and protect_ttl > 0:
            logger.info('代理池存量有点低，但尚在保护期，让我们继续观察一会... O__O')
        elif not refresh_ttl:
            startFetch('代理池太久没更新啦，补充些新鲜代理... ლ(╹◡╹ლ)', fetchcmd)
        else:
            logger.info('当前可用代理数：%s 库存情况良好... (๑•̀ㅂ•́)و✧' % pcount)
        
        protect_ttl = redis_db.ttl(PROXY_PROTECT)
        refresh_ttl = redis_db.ttl(PROXY_REFRESH)
        if protect_ttl > 0:
            logger.info('代理池尚在保护期, 剩余保护时间：%s' % protect_ttl)
        if refresh_ttl > 0:
            logger.info('距离下次常规更新还剩%s秒' % refresh_ttl)
        logger.info('%s秒后开始下次检测...' % LOOP_DELAY)
        
        if single_run:
            break
        time.sleep(LOOP_DELAY)

def proxyCheck(single_run=False):
    while True:
        logger.info('检查库存代理质量...')
        os.system(checkcmd)
        pcount = redis_db.get(PROXY_COUNT)
        if pcount:
            pcount = int(pcount)
        else:
            pcount = 0
        logger.info('检查完成，存活代理数%s..' % pcount)
        if single_run:
            break
        time.sleep(CHECK_INTERVAL)

def main():
    logger.info('启动进程中...')
    # reset 'protect' and 'refresh' tag
    redis_db.delete(PROXY_PROTECT)
    redis_db.setex(PROXY_REFRESH, REFRESH_SEC, True)
    # start proxy-check thread
    check_thd = Thread(target=proxyCheck)
    check_thd.daemon = True
    check_thd.start()
    # start proxy-fetch thread
    fetch_thd = Thread(target=proxyFetch)
    fetch_thd.daemon = True
    fetch_thd.start()
    
    while True:
        if not check_thd.is_alive():
            logger.error('自检线程已挂..重启中..')
            check_thd.start()
        if not fetch_thd.is_alive():
            logger.error('抓取线程已挂..重启中..')
            fetch_thd.start()
        time.sleep(60)

class TestCases(unittest.TestCase):
    def proxyCheck(self):
        proxyCheck(True)
        
    def proxyFetch(self):
        proxyFetch(True) 
        
    def proxyExhaust(self):
        redis_db.setex(PROXY_PROTECT, PROTECT_SEC, True)
        redis_db.set(PROXY_COUNT, 0)
        proxyFetch(True)
        
    def proxyLow(self):
        redis_db.delete(PROXY_PROTECT)
        redis_db.set(PROXY_COUNT, 3)
        proxyFetch(True)
        
    def proxyLowProtect(self):
        redis_db.setex(PROXY_PROTECT, PROTECT_SEC, True)
        redis_db.set(PROXY_COUNT, 3)
        proxyFetch(True)    
    
    def proxyRefresh(self):
        redis_db.delete(PROXY_REFRESH)
        redis_db.set(PROXY_COUNT, 10)
        proxyFetch(True)  
    
    def loop(self):
        main()

if __name__ == '__main__':
    main()