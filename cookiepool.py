import sys
import time
import redis
import random
import logging
import requests
import threading
import subprocess
from settings import *
from proxypool import ipGetter
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
        sys.stderr = sys.stdout
        endline = '-' * 20 + '*' * 20 + '-' * 20
        logging.basicConfig(format='%(asctime)s - %(levelname)s - line %(lineno)d:\n'
                                   '-***- %(message)s -***-\n' + endline + '\n')

        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(level=logging.INFO)
        file_handler = logging.FileHandler(path + 'proxy.log')
        file_handler.setLevel(level=logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - line %(lineno)d:\n'
                                      '-***- %(message)s -***-\n' + endline + '\n')

        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)

    def monitor(self):
        self.connectMonitor()
        self.poolMonitor()

    def connectMonitor(self):
        while True:
            if self.canConnect():
                break
            else:
                time.sleep(60)
        return

    def canConnect(self):
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
        poolCapability = self.conn.zcard(self.poolName)
        if poolCapability < poolMinium:
            self.poolAdd(poolCapability)
        else:
            print('Everything is ok.')

    def poolAdd(self, poolCapability):
        self.logger.info(f'Unrevised pool\'s capability is {poolCapability}.')
        self.crawlschedule(num)
        poolCapability = self.conn.zcard(self.poolName)
        self.logger.info(f'Revised pool\'s capability is {poolCapability}')

    def schedule(self, num):
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
        try:
            response = self.crawl()
            self.cookieExtract(response)
        except Exception as e:
            err = str(e)
            self.logger.warning(f'Crawl failed.{err}')

    def cookieExtract(self, response):
        code = response.status_code
        if code == 200:
            cookieList = [f'{key}={value}'for key, value in response.cookies.get_dict().items()]
            cookie = '; '.join(cookieList)
            self.sucInCraw += 1
            self.cookieRequire -= 1
            self.cookieToPool(cookie)
        else:
            self.logger.warning(f'Wrong code {code}')
            return None

    def cookieToPool(self, cookie):
        self.conn.rpush(self.poolName, cookie)

    def changeCrawl(self, crawl):
        self.crawl = crawl
        assert hasattr(crawl, '__call__')


class xqCookie(cookiepool):
    def __init__(self, crawl=None):
        super(xqCookie, self).__init__(crawl)
        self.ips = ipGetter
        self.crawl = self.xqcrawl

    def xqcrawl(self):
        ua = UAS()
        url = "https://xueqiu.com/"
        ip = self.ips.get()
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

        try:
            res = requests.get(url, headers=headers, proxies=proxies, timeout=5)
        except Exception as e:
            print(e)


if __name__ == '__main__':
    your_own_pool = xqCookie()
    while True:
        your_own_pool.monitor()
