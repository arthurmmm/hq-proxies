#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import time
import random
import unittest
from redis import Redis
from threading import Thread
from datetime import datetime
import logging
from logging.handlers import RotatingFileHandler

if __name__ == '__main__':
    from proxy_spider import dbsetting
    fetchcmd = 'scrapy crawl proxy_fetch > /dev/null 2>&1'
    checkcmd = 'scrapy crawl proxy_check > /dev/null 2>&1'
    log_path = '/var/tmp/proxy_pool_commander.log'
else:
    print('测试模式！')
    from proxy_spider import dbsetting_test as dbsetting
    fetchcmd = 'scrapy crawl proxy_fetch mode=test > /dev/null 2>&1'
    checkcmd = 'scrapy crawl proxy_check mode=test > /dev/null 2>&1'
    log_path = '/var/tmp/proxy_pool_commander.test.log'

FORMAT = '%(asctime)s %(levelno)s/%(lineno)d: %(message)s'
logging.basicConfig(level=logging.DEBUG, format=FORMAT)    
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter(fmt=FORMAT)
rfh = RotatingFileHandler(log_path, maxBytes=1*1024*1024, backupCount=10)
rfh.setFormatter(formatter)
rfh.setLevel(logging.DEBUG)
logger.addHandler(rfh)
    
redis_db = dbsetting.redis_db

PROXY_LOW = 5
PROXY_EXHAUST = 2

CHECK_INTERVAL = 5 
LOOP_DELAY = 20
PROCTECT_SEC = 600
REFRESH_SEC = 3600 * 24

def startFetch(reason=None, fetchcmd='scrapy crawl proxy_fetch > /dev/null 2>&1'):
    logger.info(reason)
    redis_db[dbsetting.PROXY_PROTECT] = True
    redis_db[dbsetting.PROXY_REFRESH] = True
    redis_db.expire(dbsetting.PROXY_PROTECT, PROCTECT_SEC)
    redis_db.expire(dbsetting.PROXY_REFRESH, REFRESH_SEC)
    os.system(fetchcmd)

def proxyFetch(single_run=False):
    while True:
        protect_ttl = redis_db.ttl(dbsetting.PROXY_PROTECT)
        refresh_ttl = redis_db.ttl(dbsetting.PROXY_REFRESH)
        
        pcount = int(redis_db['proxy_count'])
        logger.info('代理数量：%s' % pcount)
        if pcount < PROXY_LOW and not protect_ttl:
            startFetch('代理池存量低了，我们需要补充些代理... (*゜ー゜*)', fetchcmd)
        elif pcount < PROXY_EXHAUST:
            startFetch('代理池即将耗尽啦，需要立即补充些代理... Σ( ° △ °|||)', fetchcmd)
        elif pcount < PROXY_LOW and protect_ttl:
            logger.info('代理池存量有点低，但尚在保护期，让我们继续观察一会... (◑▽◐)')
        elif not refresh_ttl:
            startFetch('代理池太久没更新啦，补充些新鲜代理... ( ⊙ o ⊙ )', fetchcmd)
        else:
            logger.info('当前可用代理数：%s 库存情况良好... (๑•̀ㅂ•́)و✧' % pcount)
        
        protect_ttl = redis_db.ttl(dbsetting.PROXY_PROTECT)
        refresh_ttl = redis_db.ttl(dbsetting.PROXY_REFRESH)
        
        if protect_ttl:
            protect_ttl = int(protect_ttl)
            logger.info('代理池尚在保护期, 剩余保护时间：%s' % protect_ttl)
        if refresh_ttl:
            refresh_ttl = int(refresh_ttl)
            logger.info('距离下次常规更新还剩%s秒' % refresh_ttl)
        logger.info('%s秒后开始下次检测...' % LOOP_DELAY)
        
        if single_run:
            break
        time.sleep(LOOP_DELAY)

def proxyCheck(single_run=False):
    while True:
        logger.info('检查库存代理质量...')
        os.system('scrapy crawl proxy_check  > /dev/null 2>&1')
        pcount = redis_db[dbsetting.PROXY_COUNT]
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
    # 重置protect和refresh标记
    redis_db.delete(dbsetting.PROXY_PROTECT)
    redis_db[dbsetting.PROXY_REFRESH] = True
    redis_db.expire(dbsetting.PROXY_REFRESH, REFRESH_SEC)
    # 启动自检进程
    check_thd = Thread(target=proxyCheck)
    check_thd.daemon = True
    check_thd.start()
    # 启动代理池补充进程
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
    def loop(self):
        main()

if __name__ == '__main__':
    main()