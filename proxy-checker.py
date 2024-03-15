import requests
import concurrent.futures
import time
from colorama import Fore, Style, init
import logging

init()

logging.basicConfig(filename='logs.txt', level=logging.INFO)

proxy_urls = [
    # Url list
]

def check_proxy(proxy):
    try:
        response = requests.get('http://www.google.com', proxies={'http': proxy, 'https': proxy}, timeout=1)
        if response.status_code == 200:
            return proxy
    except:
        return None

def get_proxies(url):
    response = requests.get(url)
    return response.text.split('\n')

start_time = time.time()
total_proxies = 0
working_proxies = 0

with open('proxies.txt', 'w') as f:
    with concurrent.futures.ThreadPoolExecutor() as executor:
        for url in proxy_urls:
            proxies = get_proxies(url)
            total_proxies += len(proxies)
            print(f"{Fore.YELLOW}Checking {len(proxies)} proxies from {url}.{Style.RESET_ALL} This may take some time...")
            logging.info(f"Checking {len(proxies)} proxies from {url}.")
            for proxy in executor.map(check_proxy, proxies):
                if proxy is not None:
                    f.write(proxy + '\n')
                    working_proxies += 1

end_time = time.time()
execution_time = end_time - start_time
minutes, seconds = divmod(execution_time, 60)
print(f"{Fore.GREEN}Checked {total_proxies} proxies. Working proxies: {working_proxies}.{Style.RESET_ALL}")
print(f"{Fore.CYAN}Execution time: {int(minutes)} minutes {int(seconds)} seconds.{Style.RESET_ALL}")
logging.info(f"Checked {total_proxies} proxies. Working proxies: {working_proxies}.")
logging.info(f"Execution time: {int(minutes)} minutes {int(seconds)} seconds.")