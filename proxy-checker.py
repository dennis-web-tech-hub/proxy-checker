import requests
import concurrent.futures
import time
import os
from colorama import Fore, Style, init

# Initialize colorama
init()

# List of URLs to check proxies
proxy_urls = {
  "http": "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
  "socks4": "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks4.txt",
  "socks5": "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks5.txt"
}

# Configurable parameters
TIMEOUT = 1
MAX_WORKERS = 500

def check_proxy(proxy):
    try:
        session = requests.Session()
        session.proxies = {'http': proxy, 'https': proxy}
        response = session.get('http://www.google.com', timeout=TIMEOUT)
        if response.status_code == 200:
            return proxy
    except requests.RequestException:
        pass
    return None

def get_proxies(url):
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.text.strip().splitlines()
    except requests.RequestException:
        return []

def create_proxy_dir(directory):
    os.makedirs(directory, exist_ok=True)

def process_proxies(proxy_type, url):
    proxy_dir = f'proxies/{proxy_type}.txt'
    create_proxy_dir(os.path.dirname(proxy_dir))
    with open(proxy_dir, 'w') as f:
        proxies = get_proxies(url)
        total_proxies = len(proxies)
        print(f"{Fore.YELLOW}Checking {total_proxies} {proxy_type} proxies from {url}.{Style.RESET_ALL} This may take some time...")

        working_proxy_list = []
        futures = [executor.submit(check_proxy, proxy) for proxy in proxies]
        for future in concurrent.futures.as_completed(futures):
            try:
                result = future.result()
            except Exception:
                pass
            else:
                if result is not None:
                    working_proxy_list.append(result)

        try:
            f.write('\n'.join(working_proxy_list) + '\n')
        except OSError:
            pass

    return total_proxies, len(working_proxy_list)

if __name__ == "__main__":
    start_time = time.time()
    total_proxies_checked = 0
    working_proxies_found = 0

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = [executor.submit(process_proxies, proxy_type, url) for proxy_type, url in proxy_urls.items()]
            for future in concurrent.futures.as_completed(futures):
                try:
                    total_proxies, working_proxies = future.result()
                except Exception:
                    pass
                else:
                    total_proxies_checked += total_proxies
                    working_proxies_found += working_proxies
    except KeyboardInterrupt:
        print(f"{Fore.RED}Process interrupted by user. Exiting...{Style.RESET_ALL}")

    end_time = time.time()
    execution_time = end_time - start_time
    minutes, seconds = divmod(execution_time, 60)
    print(f"{Fore.GREEN}Checked {total_proxies_checked} proxies. Working proxies: {working_proxies_found}.{Style.RESET_ALL}")
    print(f"{Fore.CYAN}Execution time: {int(minutes)} minutes {int(seconds)} seconds.{Style.RESET_ALL}")