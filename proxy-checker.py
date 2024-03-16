import requests
import concurrent.futures
import time
import os
from colorama import Fore, Style, init
import logging

# Initialize colorama
init()

# Set up logging
logging.basicConfig(filename='logs.txt', level=logging.INFO)

# List of URLs to check proxies
proxy_urls = {
    "http": "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
    "socks4": "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks4.txt",
    "socks5": "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks5.txt"
}

def check_proxy(proxy):
    try:
        response = requests.get('http://www.google.com', proxies={'http': proxy, 'https': proxy}, timeout=1)
        if response.status_code == 200:
            return proxy
    except requests.exceptions.RequestException as e:
        logging.error(f"Error checking proxy {proxy}: {e}")
        return None

def get_proxies(url):
    try:
        response = requests.get(url)
        return response.text.split('\n')
    except requests.exceptions.RequestException as e:
        logging.error(f"Error getting proxies from {url}: {e}")
        return []

# Create a directory for the proxies
if not os.path.exists('proxies'):
    os.makedirs('proxies')

start_time = time.time()
total_proxies = 0
working_proxies = 0

with concurrent.futures.ThreadPoolExecutor(max_workers=100) as executor:
    for proxy_type, url in proxy_urls.items():
        with open(f'proxies/{proxy_type}.txt', 'w') as f:
            proxies = get_proxies(url)
            total_proxies += len(proxies)
            print(f"{Fore.YELLOW}Checking {len(proxies)} {proxy_type} proxies from {url}.{Style.RESET_ALL} This may take some time...")
            logging.info(f"Checking {len(proxies)} {proxy_type} proxies from {url}.")
            future_to_proxy = {executor.submit(check_proxy, proxy): proxy for proxy in proxies}
            for future in concurrent.futures.as_completed(future_to_proxy):
                proxy = future_to_proxy[future]
                try:
                    result = future.result()
                except Exception as exc:
                    logging.error(f"{proxy} generated an exception: {exc}")
                else:
                    if result is not None:
                        f.write(result + '\n')
                        working_proxies += 1

end_time = time.time()
execution_time = end_time - start_time
minutes, seconds = divmod(execution_time, 60)
print(f"{Fore.GREEN}Checked {total_proxies} proxies. Working proxies: {working_proxies}.{Style.RESET_ALL}")
print(f"{Fore.CYAN}Execution time: {int(minutes)} minutes {int(seconds)} seconds.{Style.RESET_ALL}")
logging.info(f"Checked {total_proxies} proxies. Working proxies: {working_proxies}.")
logging.info(f"Execution time: {int(minutes)} minutes {int(seconds)} seconds.")