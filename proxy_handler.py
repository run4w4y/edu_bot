import requests
import ast
from queue import Queue
import time


class ProxyHandler:
    def check(self, proxy, f):
        try:
            self.session.get('https://edu.tatar.ru/logon', proxies=proxy, timeout=2)
            self.good_proxies.put(proxy)

            f.write(str(proxy) + '\n')
            return True
        except BaseException:
            self.bad_proxies.append(proxy)
            return False


    def check_bad(self, verbose=True):
        temp = self.bad_proxies
        self.bad_proxies = []
        for proxy in temp:
            self.check(proxy)
            time.sleep(0.1)


    def check_all(self, verbose=True):
        with open('good_proxies.txt', 'w')  as f:
            self.bad_proxies = []
            count = 0
            for proxy in self.all_proxies:
                count += 1
                status = self.check(proxy, f)
                if verbose:
                    print('[O] -' if status else '[X] -', proxy['https'])


    def __init__(self, proxy_path='proxies.txt'):
        self.good_proxies = Queue()
        self.busy_proxies = {}
        self.bad_proxies = []
        self.session = requests.session()
        with open(proxy_path, 'r') as f:
            self.all_proxies = [ast.literal_eval(line) for line in f.readlines()]
        self.check_all()


    def get_proxy(self, chat_id):
        while self.good_proxies.empty():
            time.sleep(0.5)
        proxy = self.good_proxies.get()
        self.busy_proxies[chat_id] = proxy
        return proxy

    
    def free_proxy(self, chat_id):
        proxy = self.busy_proxies[chat_id]
        self.bad_proxies.append(proxy)
        del self.busy_proxies[chat_id]
