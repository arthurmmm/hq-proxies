#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import time
import random
from redis import Redis
from proxy_spider import dbsetting
from threading import Thread

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

CHECK_INTERVAL = 5
LOOP_DELAY = 20
PROCTECT_SEC = 600

def proxyFetch(test=False):
    while True:
        pcount = int(redis_db['proxy_count'])
        logger.info('代理数量：%s' % pcount)
        if pcount < 5 and not redis_db.exists(dbsetting.PROXY_PROTECT):
            logger.info('代理数量过低，补充代理中...')
            redis_db[dbsetting.PROXY_PROTECT] = True
            redis_db.expire(dbsetting.PROXY_PROTECT, PROCTECT_SEC)
            os.system('scrapy crawl proxy_fetch > /dev/null 2>&1')
        elif pcount < 2:
            logger.info('代理池即将耗尽，强制补充...')
            redis_db[dbsetting.PROXY_PROTECT] = True
            redis_db.expire(dbsetting.PROXY_PROTECT, PROCTECT_SEC)
            os.system('scrapy crawl proxy_fetch')
        elif redis_db.exists(dbsetting.PROXY_PROTECT):
            logger.info('未达到代理更新最小间隔...')
        else:
            logger.info('当前可用代理数：%s 库存情况良好\(^o^)/' % pcount)
        if test:
            break
        loop_delay = LOOP_DELAY+random.random()*2
        try:
            ttl = int(redis_db.ttl(dbsetting.PROXY_PROTECT))
        except TypeError:
            ttl = 0
        logger.info('%s秒后开始下次检测，剩余保护时间：%s' % (loop_delay, ttl))
        time.sleep(loop_delay)

def proxyCheck(test=False):
    while True:
        logger.info('开始自检..')
        os.system('scrapy crawl proxy_check  > /dev/null 2>&1')
        if test:
            break
        pcount = int(redis_db['proxy_count'])
        logger.info('自检完成，存活代理数%s..' % pcount)
        time.sleep(CHECK_INTERVAL)

def main():
    logger.info('启动进程..')
    # 重置protect
    redis_db.delete(dbsetting.PROXY_PROTECT)
    # 启动自检进程
    check_thd = Thread(target=proxyCheck)
    check_thd.daemon = True
    check_thd.start()
    # 启动代理池补充进程
    fetch_thd = Thread(target=proxyFetch)
    fetch_thd.daemon = True
    fetch_thd.start()
    
    # fetch_thd.join()
    # check_thd.join()
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
    # print('start fetch')
    proxyFetch(test=True)
    
if __name__ == '__main__':
    main()