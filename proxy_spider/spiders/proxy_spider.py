# -*- coding: utf-8 -*-

import json
import time
from datetime import datetime
from pymongo import MongoClient
from redis import Redis
import re
import random
import requests
from scrapy import Spider, Request
from proxy_spider import dbsetting
from scrapy.http import HtmlResponse
from collections import defaultdict

import logging
from logging.handlers import RotatingFileHandler

logger = logging.getLogger(__name__)
rfh = RotatingFileHandler('/var/tmp/proxy_pool_spider.log', maxBytes=5*1024*1024, backupCount=10)
logger.addHandler(rfh)

class ProxyCheckSpider(Spider):
    name = 'proxy_check'
    
    def __init__(self, *args, **kwargs):
        mongo_client = MongoClient(dbsetting.MONGO_URI)
        mongo_db = mongo_client[dbsetting.MONGO_DATABASE]
        self.mongo_vendors = mongo_db[dbsetting.VENDOR_COLLECTION]
        self.mongo_validator = mongo_db[dbsetting.VALIDATOR_COLLECTION]
        self.redis_db = Redis(
            host=dbsetting.REDIS_HOST, 
            port=dbsetting.REDIS_PORT, 
            password=dbsetting.REDIS_PASSWORD,
            db=dbsetting.REDIS_DB
        )
        self.validator_pool = set([])
    
    def start_requests(self):
        # 载入验证页池
        for validator in self.mongo_validator.find({}):
            self.validator_pool.add((validator['url'], validator['startstring']))
        # 开始自检
        logger.info('开始自检...')
        self.redis_db[dbsetting.proxy_count] = self.redis_db.scard(dbsetting.PROXY_SET)
        for proxy in self.redis_db.smembers(dbsetting.PROXY_SET):
            proxy = proxy.decode('utf-8')
            vaurl, vastart = random.choice(list(self.validator_pool))
            yield Request(url=vaurl, meta={'proxy': proxy, 'startstring': vastart}, callback=self.checkin, dont_filter=True)
    
    def checkin(self, response):
        res = response.body_as_unicode()
        if 'startstring' in response.meta and res.startswith(response.meta['startstring']):
            proxy = response.meta['proxy']
            self.redis_db.sadd(dbsetting.PROXY_SET, proxy)
            yield {'msg': "可用代理+1  %s" % proxy}
        else:
            proxy = response.url if 'proxy' not in response.meta else response.meta['proxy']
            self.redis_db.srem(dbsetting.PROXY_SET, proxy)
            yield {'msg': "代理验证失败 %s" % proxy}
    
    def closed(self, reason):
        proxy_count = self.redis_db.scard(dbsetting.PROXY_SET)
        logger.info('代理池验证完成，有效代理: %s' % proxy_count)
        self.redis_db[dbsetting.proxy_count] = proxy_count

class ProxyFetchSpider(Spider):
    name = 'proxy_fetch'
    loop_delay = 10
    protect_sec = 180
    
    def __init__(self, *args, **kwargs):
        mongo_client = MongoClient(dbsetting.MONGO_URI)
        mongo_db = mongo_client[dbsetting.MONGO_DATABASE]
        self.mongo_vendors = mongo_db[dbsetting.VENDOR_COLLECTION]
        self.mongo_validator = mongo_db[dbsetting.VALIDATOR_COLLECTION]
        self.redis_db = Redis(
            host=dbsetting.REDIS_HOST, 
            port=dbsetting.REDIS_PORT, 
            password=dbsetting.REDIS_PASSWORD,
            db=dbsetting.REDIS_DB
        )
        self.validator_pool = set([])
    
    def start_requests(self):
        # 载入验证页池
        for validator in self.mongo_validator.find({}):
            self.validator_pool.add((validator['url'], validator['startstring']))
        # 验证页面
        for vendor in self.mongo_vendors.find({'status': 'active'}):
            logger.debug(vendor)
            callback = getattr(self, vendor['parser'])
            proxy = self.redis_db.srandmember(dbsetting.PROXY_SET)
            if proxy:
                proxy = proxy.decode('utf-8')
            logger.info('获得代理：'+proxy)
            yield Request(url=vendor['url'], callback=callback)
    
    
    def checkin(self, response):
        res = response.body_as_unicode()
        if 'startstring' in response.meta and res.startswith(response.meta['startstring']):
            proxy = response.meta['proxy']
            self.redis_db.sadd(dbsetting.PROXY_SET, proxy)
            yield {'msg': "可用代理+1  %s" % proxy}
        else:
            proxy = response.url if 'proxy' not in response.meta else response.meta['proxy']
            yield {'msg': "代理验证失败 %s" % proxy}
    
    
    def parse_xici(self, response):
        # ''' 
        # @url http://www.xicidaili.com/nn/
        # '''
        logger.info('解析http://www.xicidaili.com/nn/')
        succ = 0
        fail = 0
        count = 0
        for tr in response.css('#ip_list tr'):
            td_list = tr.css('td::text')
            if len(td_list) < 3:
                continue
            ipaddr = td_list[0].extract()
            port = td_list[1].extract()
            proto = td_list[5].extract()
            latency = tr.css('div.bar::attr(title)').extract_first()
            latency = re.match('(\d+\.\d+)秒', latency).group(1)
            proxy = '%s://%s:%s' % (proto, ipaddr, port)
            proxies = {proto: '%s:%s' % (ipaddr, port)}
            if float(latency) > 3:
                logger.info('丢弃慢速代理: %s 延迟%s秒' % (proxy, latency))
                continue
            logger.info('验证: %s' % proxy)
            if not self.redis_db.sismember(dbsetting.PROXY_SET, proxy):
                vaurl, vastart = random.choice(list(self.validator_pool))
                yield Request(url=vaurl, meta={'proxy': proxy, 'startstring': vastart}, callback=self.checkin, dont_filter=True)
            else:
                logger.info('该代理已收录..')
    
    def parse_66ip(self, response):
        ''' 
        @url http://www.66ip.cn/nmtq.php?getnum=100&isp=0&anonymoustype=3&start=&ports=&export=&ipaddress=&area=1&proxytype=0&api=66ip
        '''
        logger.info('开始爬取66ip')
        if 'proxy' in response.meta:
            logger.info('=>使用代理%s' % response.meta['proxy'])
        res = response.body_as_unicode()
        # logger.debug()
        for addr in re.findall('\d+\.\d+\.\d+\.\d+\:\d+', res):
            proxy = 'http://' + addr
            print(proxy)
            logger.info('验证: %s' % proxy)
            if not self.redis_db.sismember(dbsetting.PROXY_SET, proxy):
                vaurl, vastart = random.choice(list(self.validator_pool))
                yield Request(url=vaurl, meta={'proxy': proxy, 'startstring': vastart}, callback=self.checkin, dont_filter=True)
            else:
                logger.info('该代理已收录..')
    
    def parse_ip181(self, response):
        ''' 
        @url http://www.ip181.com/
        '''
        logger.info('开始爬取ip181')
        if 'proxy' in response.meta:
            logger.info('=>使用代理%s' % response.meta['proxy'])
        for tr in response.css('table tbody tr'):
            ip = tr.css('td::text').extract()[0]
            port = tr.css('td::text').extract()[1]
            type = tr.css('td::text').extract()[2]
            proxy = 'http://%s:%s' % (ip, port)
            if type != '高匿':
                logger.info('丢弃非高匿代理：%s' % proxy)
                continue
            logger.info('验证: %s' % proxy)
            if not self.redis_db.sismember(dbsetting.PROXY_SET, proxy):
                vaurl, vastart = random.choice(list(self.validator_pool))
                yield Request(url=vaurl, meta={'proxy': proxy, 'startstring': vastart}, callback=self.checkin, dont_filter=True)
            else:
                logger.info('该代理已收录..')
    
    def parse_kxdaili(self, response):
        ''' 
        @url http://www.kxdaili.com/dailiip/1/1.html#ip
        '''
        logger.info('开始爬取kxdaili')
        if 'proxy' in response.meta:
            logger.info('=>使用代理%s' % response.meta['proxy'])
        url_pattern = 'http://www.kxdaili.com/dailiip/1/%s.html#ip'
        try:
            page = re.search('(\d)+\.html', response.url).group(1)
            page = int(page)
        except Exception as e:
            logger.exception(e)
            logger.error(response.url)
        for tr in response.css('table.ui.table.segment tbody tr'):
            ip = tr.css('td::text').extract()[0]
            port = tr.css('td::text').extract()[1]
            proxy = 'http://%s:%s' % (ip, port)
            logger.info('验证: %s' % proxy)
            if not self.redis_db.sismember(dbsetting.PROXY_SET, proxy):
                vaurl, vastart = random.choice(list(self.validator_pool))
                yield Request(url=vaurl, meta={'proxy': proxy, 'startstring': vastart}, callback=self.checkin, dont_filter=True)
            else:
                logger.info('该代理已收录..')
        if page < 3: # 爬取前3页
            page += 1
            new_url = url_pattern % page
            new_meta = response.meta.copy()
            new_meta['page'] = page
            yield Request(url=new_url, meta=new_meta, callback=self.parse_kxdaili)
    
    def closed(self, reason):
        logger.info('代理池更新完成，有效代理: %s' % self.redis_db.scard(dbsetting.PROXY_SET))
        
        
if __name__ == '__main__':
    from scrapy.crawler import CrawlerProcess
    process = CrawlerProcess()
    process.crawl(ProxyCheckSpider)
    process.crawl(MySpider2)