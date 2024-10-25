import requests
import time
import os
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional, Dict

# Initialize logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class ProxyChecker:
    def __init__(self, proxy_urls: Dict[str, str], timeout: int = 1, max_retries: int = 3, retry_delay: float = 1.0, max_workers: int = 20):
        self.proxy_urls = proxy_urls
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.max_workers = max_workers
        self.total_proxies_checked = 0
        self.working_proxies_found = 0
        self.session = requests.Session()  # Single session for all requests

    def check_proxy(self, proxy: str) -> Optional[str]:
        """
        Checks if a single proxy is working by sending a request to Google.
        Returns the proxy if successful, otherwise None.
        """
        try:
            session = requests.Session()  # Separate session per request
            session.proxies = {'http': proxy, 'https': proxy}
            response = session.get('http://www.google.com', timeout=self.timeout)
            if response.status_code == 200:
                return proxy
        except requests.RequestException:
            return None

    def get_proxies(self, url: str) -> List[str]:
        """
        Fetches a list of proxies from a URL with retry logic.
        Returns a list of proxy strings.
        """
        for attempt in range(self.max_retries):
            try:
                response = self.session.get(url, timeout=self.timeout)
                response.raise_for_status()
                logging.info(f"Successfully fetched proxies from {url}")
                return response.text.strip().splitlines()
            except requests.RequestException as e:
                logging.warning(f"Attempt {attempt + 1} failed to retrieve proxies from {url}: {e}")
                time.sleep(self.retry_delay)
        logging.error(f"Failed to retrieve proxies from {url} after {self.max_retries} attempts.")
        return []

    @staticmethod
    def create_proxy_dir(directory: str) -> None:
        """Creates a directory to store proxy lists if it doesn't exist."""
        os.makedirs(directory, exist_ok=True)

    def process_proxies(self, proxy_type: str, url: str) -> None:
        """
        Fetches, checks, and saves working proxies of a specific type.
        Logs the number of working proxies and writes them to a file.
        """
        proxy_dir = f'proxies/{proxy_type}.txt'
        self.create_proxy_dir(os.path.dirname(proxy_dir))
        proxies = self.get_proxies(url)
        total_proxies = len(proxies)
        
        if not proxies:
            logging.warning(f"No proxies to check for {proxy_type}")
            return
        
        logging.info(f"Checking {total_proxies} {proxy_type} proxies from {url} with {self.max_workers} concurrent workers.")

        # List to store working proxies
        working_proxy_list = []

        # Controlled concurrent checking of proxies
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {executor.submit(self.check_proxy, proxy): proxy for proxy in proxies}
            for future in as_completed(futures):
                result = future.result()
                if result:
                    working_proxy_list.append(result)

        # Save the working proxies to a file
        try:
            with open(proxy_dir, 'w') as f:
                f.write('\n'.join(working_proxy_list) + '\n')
        except OSError as e:
            logging.error(f"Failed to write working proxies to {proxy_dir}: {e}")

        logging.info(f"Checked {total_proxies} {proxy_type} proxies. Working proxies: {len(working_proxy_list)}.")
        self.total_proxies_checked += total_proxies
        self.working_proxies_found += len(working_proxy_list)

    def run(self) -> None:
        """Runs the proxy checking process for all proxy types."""
        start_time = time.time()
        
        try:
            for proxy_type, url in self.proxy_urls.items():
                self.process_proxies(proxy_type, url)
        except KeyboardInterrupt:
            logging.warning("Process interrupted by user. Exiting...")
        finally:
            self.session.close()  # Ensure session is closed after execution

        end_time = time.time()
        execution_time = end_time - start_time
        minutes, seconds = divmod(execution_time, 60)
        logging.info(f"Total proxies checked: {self.total_proxies_checked}. Working proxies: {self.working_proxies_found}.")
        logging.info(f"Execution time: {int(minutes)} minutes {int(seconds)} seconds.")

if __name__ == "__main__":
    proxy_urls = {
        "http": "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
        "socks4": "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks4.txt",
        "socks5": "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks5.txt"
    }

    checker = ProxyChecker(proxy_urls, max_workers=100)
    checker.run()