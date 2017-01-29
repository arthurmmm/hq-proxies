#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import time
import random
from redis import Redis
from proxy_spider import dbsetting_test as dbsetting
from threading import Thread
from datetime import datetime

import logging
from logging.handlers import RotatingFileHandler


FORMAT = '%(asctime)s %(levelno)s/%(lineno)d: %(message)s'
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter(fmt=FORMAT)
rfh = RotatingFileHandler('/var/tmp/proxy_pool_commander.log', maxBytes=5*1024*1024, backupCount=10)
rfh.setFormatter(formatter)
rfh.setLevel(logging.DEBUG)
logger.addHandler(rfh)

logging.basicConfig(level=logging.DEBUG, format=FORMAT)

redis_db = Redis(
    host=dbsetting.REDIS_HOST, 
    port=dbsetting.REDIS_PORT, 
    password=dbsetting.REDIS_PASSWORD,
    db=dbsetting.REDIS_DB
)

PROXY_LOW = 5
PROXY_EXHAUST = 2

CHECK_INTERVAL = 5 
LOOP_DELAY = 20
PROCTECT_SEC = 600
REFRESH_SEC = 3600 * 24

def startCrawl(reason=None):
    logger.info(reason)
    redis_db[dbsetting.PROXY_PROTECT] = True
    redis_db[dbsetting.REFRESH_SEC] = True
    redis_db.expire(dbsetting.PROXY_PROTECT, PROCTECT_SEC)
    redis_db.expire(dbsetting.PROXY_REFRESH, REFRESH_SEC)
    os.system('scrapy crawl proxy_fetch > /dev/null 2>&1')

def proxyFetch(test=False):
    while True:
        protect_ttl = redis_db.ttl(dbsetting.PROXY_PROTECT)
        refresh_ttl = redis_db.ttl(dbsetting.PROXY_REFRESH)
        
        pcount = int(redis_db['proxy_count'])
        logger.info('代理数量：%s' % pcount)
        if pcount < PROXY_LOW and not protect_ttl:
            startCrawl('代理池存量太低啦，需要补充些代理... (*゜ー゜*)')
        elif pcount < PROXY_EXHAUST:
            startCrawl('代理池即将耗尽啦，需要立即补充些代理... Σ( ° △ °|||)︴')
        elif pcount < PROXY_LOW and protect_ttl:
            logger.info('代理池存量有点低，但尚在保护期，让我们继续观察一会... (◑▽◐)')
        elif not refresh_ttl:
            startCrawl('代理池太久没更新啦，补充些新鲜代理... (～o￣3￣)～')
        else:
            logger.info('当前可用代理数：%s 库存情况良好... (๑•̀ㅂ•́)و✧' % pcount)
        if test:
            break
        
        protect_ttl = redis_db.ttl(dbsetting.PROXY_PROTECT)
        refresh_ttl = redis_db.ttl(dbsetting.PROXY_REFRESH)
        
        if protect_ttl:
            protect_ttl = int(protect_ttl)
            logger.info('代理池尚在保护期, 剩余保护时间：%s' % protect_ttl)
        if refresh_ttl:
            refresh_ttl = int(refresh_ttl)
            logger.info('距离下次常规更新还剩%s秒' % refresh_ttl)
        logger.info('%s秒后开始下次检测...' % LOOP_DELAY)
        time.sleep(LOOP_DELAY)

def proxyCheck(test=False):
    while True:
        logger.info('检查库存代理质量... =￣ω￣=')
        os.system('scrapy crawl proxy_check  > /dev/null 2>&1')
        if test:
            break
        pcount = int(redis_db['proxy_count'])
        logger.info('检查完成，存活代理数%s..' % pcount)
        time.sleep(CHECK_INTERVAL)

def main():
    logger.info('启动进程中...')
    # 重置protect和refresh标记
    redis_db.delete(dbsetting.PROXY_PROTECT)
    redis_db.delete(dbsetting.PROXY_REFRESH)
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
    
def test():
    proxyCheck(test=True)
    proxyFetch(test=True)
    
if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'test':
        test()
    # main()