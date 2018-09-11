import sys
import time
import redis
import random
import logging
import requests
import threading
import subprocess
from setting import *
from proxyPool import ipGetter
from fake_useragent import UserAgent as UAS


class cookiepool():
    def __init__(self, crawl=None):
        self.crawl = crawl
        self.loggerBuild()
        self.sucInCraw = 0
        self.cookieRequire = 0
        self.poolName = cookiePool
        self.conn = redis.StrictRedis(host=redis_host,
                                      port=redis_port,
                                      password=redis_password)
        self.conn.delete(self.poolName)

    def loggerBuild(self):
        """
        用于创建日志
        :return:
        """
        sys.stderr = sys.stdout
        endline = '-' * 20 + '*' * 20 + '-' * 20
        # 打印日志格式由此修改
        logging.basicConfig(format='%(asctime)s - %(levelname)s - line %(lineno)d:\n'
                                   '-***- %(message)s -***-\n' + endline + '\n')

        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(level=logging.INFO)
        file_handler = logging.FileHandler(path + 'proxy.log')
        file_handler.setLevel(level=logging.INFO)
        # 日志文件格式由此修改
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - line %(lineno)d:\n'
                                      '-***- %(message)s -***-\n' + endline + '\n')

        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)

    def monitor(self):
        """
        主要函数，运行cookie池时会一直运行此函数
        :return:
        """
        self.connectMonitor()
        self.poolMonitor()
        self.staleCheck()

    def connectMonitor(self):
        """
        联网监控
        :return:
        """
        while True:
            if self.canConnect():
                break
            else:
                time.sleep(60)
        return

    def canConnect(self):
        """
        ping百度的绿色DNS
        网络联通则返回True
        :return:
        """
        data = subprocess.Popen('ping 180.76.76.76',
                                stdout=subprocess.PIPE,
                                shell=True)
        stdout1 = data.stdout.read()
        stdout = str(stdout1, encoding='gbk')
        if '超时' in stdout:
            self.logger.fatal('网络连接超时')
            return False
        else:
            self.logger.info('网络连接正常')
            return True

    def poolMonitor(self):
        """
        cookie池监控
        :return:
        """
        poolCapability = self.conn.zcard(self.poolName)
        if poolCapability < poolMinium:
            self.poolAdd(poolCapability)
        else:
            print('Everything is ok.')

    def poolAdd(self, poolCapability):
        """
        :param poolCapability: 添加的cookie数量
        :return:
        """
        self.logger.info(f'Unrevised pool\'s capability is {poolCapability}.')
        self.schedule(poolCapability)
        poolCapability = self.conn.zcard(self.poolName)
        self.logger.info(f'Revised pool\'s capability is {poolCapability}')

    def schedule(self, num):
        """
        爬取cookie的调度
        :param num:
        :return:
        """
        count = 0
        self.cookieRequire = num
        while self.cookieRequire >= 0:
            threads = []
            self.sucInCraw = 0
            for i in range(threadNum):
                count += 1
                thread = threading.Thread(target=self.cookieGet, name=str(count))
                thread.start()
                threads.append(thread)
            while threads:
                threads.pop().join()
            self.logger.info(f'Get {self.sucInCraw} cookies in {threadNum} crawl.')

        self.cookieRequire = 0

    def cookieGet(self):
        """
        根据提供的爬虫发送多线程请求
        :return:
        """
        try:
            response = self.crawl()
            self.cookieExtract(response)
        except Exception as e:
            err = str(e)
            self.logger.warning(f'Crawl failed.{err}')

    def cookieExtract(self, response):
        """
        从response对象中提取cookie
        :param response:
        :return:
        """
        code = response.status_code
        if code == 200:
            cookieList = [f'{key}={value}'for key, value in response.cookies.get_dict().items()]
            cookie = '; '.join(cookieList)
            self.sucInCraw += 1
            self.cookieRequire -= 1
            self.cookieToPool(cookie)
            self.logger.info('Succeed get cookie.')
        else:
            self.logger.warning(f'Wrong code {code}.')
            return None

    def cookieToPool(self, cookie):
        """
        将cookie及插入时间添加入cookie池中
        :param cookie:
        :return:
        """
        insert_time = str(time.time())[5:10]
        self.conn.zadd(self.poolName, insert_time, cookie)

    def changeCrawl(self, crawl):
        """
        改变爬取函数，增加复用性
        :param crawl:
        :return:
        """
        self.crawl = crawl
        assert hasattr(crawl, '__call__')

    def staleCheck(self):
        """
        删除过期的cookie
        :return:
        """
        now = int(str(time.time())[5:10])
        staleNum = self.conn.zcount(self.poolName, min=0, max=now-expire)
        self.conn.zremrangebyscore(self.poolName, min=0, max=now-expire)
        self.logger.info(f'{staleNum} cookies has stale.')


class cookieTool():
    def __init__(self):
        self.poolName = cookiePool
        self.conn = redis.StrictRedis(host=redis_host,
                                      port=redis_port,
                                      password=redis_password)

    def pop(self):
        dic = {}
        for proxy, score in self.conn.zrange(self.poolName, 0, 0, withscores=True):
            dic = {str(proxy, encoding='utf-8'): score}
            self.conn.zrem(self.poolName, proxy)
        return dic

    def recycle(self, dic):
        for cookie in dic:
            self.conn.zadd(self.poolName, cookie, dic[cookie]-20)

    def getAll(self):
        dicCookie = {str(cookie, encoding='utf-8'): score
                     for cookie, score in self.conn.zrevrange(self.poolName, 0, -1, withscores=True)}
        return dicCookie


ips = ipGetter()


def xqcrawl():
    ua = UAS()
    global ips
    url = "https://xueqiu.com/"
    ip = ips.get()
    proxies = {'https': 'https://'+ip}
    headers = {
        'accept': "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
        'accept-encoding': "gzip, deflate, br",
        'accept-language': "zh-CN,zh;q=0.9",
        'cache-control': "no-cache",
        'connection': "keep-alive",
        'host': "xueqiu.com",
        'pragma': "no-cache",
        'upgrade-insecure-requests': "1",
        'user-agent': ua.random,
    }

    res = requests.get(url, headers=headers, proxies=proxies, timeout=5)
    return res


class xqCookie(cookiepool):
    def __init__(self, crawl=None):
        super(xqCookie, self).__init__(crawl)
        self.ips = ipGetter
        self.crawl = xqcrawl


if __name__ == '__main__':
    your_own_pool = xqCookie()
    while True:
        your_own_pool.monitor()
