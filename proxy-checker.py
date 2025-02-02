import sys
import os
import time
import logging
import argparse
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional, Dict
from threading import Event

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QObject
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTextEdit, QSpinBox, QDoubleSpinBox,
    QCheckBox, QGroupBox, QGridLayout, QMessageBox
)

class ProxyChecker:
    """
    A class to fetch proxy lists from given URLs and check if they work.
    Cancellation is supported via an internal Event flag.
    """

    def __init__(self, proxy_urls: Dict[str, str], timeout: int = 1,
                 max_retries: int = 3, retry_delay: float = 1.0, max_workers: int = 20,
                 log_callback=None):
        """
        :param proxy_urls: A dict mapping proxy type (e.g., "http", "socks4") to URL.
        :param timeout: Timeout in seconds for requests.
        :param max_retries: Number of retries for fetching the proxy list.
        :param retry_delay: Delay between retries in seconds.
        :param max_workers: Number of concurrent threads for checking proxies.
        :param log_callback: Optional callback function for logging (e.g., to update a GUI log).
        """
        self.proxy_urls = proxy_urls
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.max_workers = max_workers
        self.total_proxies_checked = 0
        self.working_proxies_found = 0
        self.session = requests.Session()
        self.log_callback = log_callback
        self.cancel_event = Event()  # Used to signal cancellation

    def log(self, level: str, message: str):
        """Helper function to log messages both to the console and via the GUI callback."""
        full_message = f"{level.upper()}: {message}"
        if self.log_callback:
            self.log_callback(full_message)
        else:
            print(full_message)

    def cancel(self):
        """Set the cancellation flag so that long operations can abort."""
        self.cancel_event.set()
        self.log("info", "Cancellation requested.")

    def check_proxy(self, proxy: str) -> Optional[str]:
        """
        Checks if a single proxy is working by sending a request to Google.
        Returns the proxy if successful, otherwise None.
        """
        # If cancellation is requested, skip checking further proxies.
        if self.cancel_event.is_set():
            return None

        try:
            session = requests.Session()
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
            if self.cancel_event.is_set():
                self.log("info", "Cancellation detected while fetching proxies.")
                return []
            try:
                response = self.session.get(url, timeout=self.timeout)
                response.raise_for_status()
                self.log("info", f"Successfully fetched proxies from {url}")
                return response.text.strip().splitlines()
            except requests.RequestException as e:
                self.log("warning", f"Attempt {attempt + 1} failed to retrieve proxies from {url}: {e}")
                time.sleep(self.retry_delay)
        self.log("error", f"Failed to retrieve proxies from {url} after {self.max_retries} attempts.")
        return []

    @staticmethod
    def create_proxy_dir(directory: str) -> None:
        """Creates a directory to store proxy lists if it doesn't exist."""
        os.makedirs(directory, exist_ok=True)

    def process_proxies(self, proxy_type: str, url: str) -> int:
        """
        Fetches, checks, and saves working proxies of a specific type.
        Returns the number of working proxies found.
        """
        if self.cancel_event.is_set():
            self.log("info", "Cancellation detected before processing proxies.")
            return 0

        proxy_file = f'proxies/{proxy_type}.txt'
        self.create_proxy_dir(os.path.dirname(proxy_file))
        proxies = self.get_proxies(url)
        total_proxies = len(proxies)

        if not proxies:
            self.log("warning", f"No proxies to check for {proxy_type}")
            return 0

        self.log("info", f"Checking {total_proxies} {proxy_type} proxies from {url} with {self.max_workers} concurrent workers.")

        working_proxy_list = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all proxy check tasks.
            futures = {executor.submit(self.check_proxy, proxy): proxy for proxy in proxies}
            for future in as_completed(futures):
                if self.cancel_event.is_set():
                    self.log("info", "Cancellation detected during proxy checking loop.")
                    break
                result = future.result()
                if result:
                    working_proxy_list.append(result)

        try:
            with open(proxy_file, 'w') as f:
                f.write('\n'.join(working_proxy_list) + '\n')
        except OSError as e:
            self.log("error", f"Failed to write working proxies to {proxy_file}: {e}")

        self.log("info", f"Checked {total_proxies} {proxy_type} proxies. Working proxies: {len(working_proxy_list)}.")
        self.total_proxies_checked += total_proxies
        self.working_proxies_found += len(working_proxy_list)
        return len(working_proxy_list)

    def run(self):
        """Runs the proxy checking process for all proxy types."""
        start_time = time.time()

        for proxy_type, url in self.proxy_urls.items():
            if self.cancel_event.is_set():
                self.log("info", "Cancellation detected. Aborting further processing.")
                break
            self.process_proxies(proxy_type, url)

        self.session.close()
        end_time = time.time()
        execution_time = end_time - start_time
        minutes, seconds = divmod(execution_time, 60)
        self.log("info", f"Total proxies checked: {self.total_proxies_checked}. Working proxies: {self.working_proxies_found}.")
        self.log("info", f"Execution time: {int(minutes)} minutes {int(seconds)} seconds.")

class ProxyCheckerWorker(QObject):
    """
    Worker class to run the proxy checking process in a separate thread.
    Emits progress messages and a finished signal when done.
    """
    progress = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, proxy_urls: Dict[str, str], timeout: int, max_retries: int,
                 retry_delay: float, max_workers: int):
        super().__init__()
        self.proxy_urls = proxy_urls
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.max_workers = max_workers
        self._is_interrupted = False
        self.checker = None

    def log_callback(self, message: str):
        """Emits a progress signal with the log message."""
        self.progress.emit(message)

    def cancel(self):
        """Called by the GUI to cancel the running operation."""
        self._is_interrupted = True
        if self.checker is not None:
            self.checker.cancel()

    def run(self):
        """Starts the proxy checking process."""
        self.checker = ProxyChecker(
            proxy_urls=self.proxy_urls,
            timeout=self.timeout,
            max_retries=self.max_retries,
            retry_delay=self.retry_delay,
            max_workers=self.max_workers,
            log_callback=self.log_callback
        )
        self.log_callback("Starting proxy checking...")
        self.checker.run()
        self.log_callback("Proxy checking finished.")
        self.finished.emit()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Proxy Checker")
        self.setGeometry(100, 100, 800, 600)
        self.init_ui()
        self.thread = None
        self.worker = None

    def init_ui(self):
        # Main widget and layout
        main_widget = QWidget()
        main_layout = QVBoxLayout()

        # Group box for configuration settings
        config_group = QGroupBox("Settings")
        config_layout = QGridLayout()

        # Timeout setting
        config_layout.addWidget(QLabel("Timeout (s):"), 0, 0)
        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(1, 60)
        self.timeout_spin.setValue(3)
        config_layout.addWidget(self.timeout_spin, 0, 1)

        # Max retries
        config_layout.addWidget(QLabel("Max Retries:"), 0, 2)
        self.retries_spin = QSpinBox()
        self.retries_spin.setRange(1, 10)
        self.retries_spin.setValue(3)
        config_layout.addWidget(self.retries_spin, 0, 3)

        # Retry delay
        config_layout.addWidget(QLabel("Retry Delay (s):"), 1, 0)
        self.retry_delay_spin = QDoubleSpinBox()
        self.retry_delay_spin.setRange(0.1, 10.0)
        self.retry_delay_spin.setSingleStep(0.1)
        self.retry_delay_spin.setValue(1.0)
        config_layout.addWidget(self.retry_delay_spin, 1, 1)

        # Max workers
        config_layout.addWidget(QLabel("Max Workers:"), 1, 2)
        self.workers_spin = QSpinBox()
        self.workers_spin.setRange(1, 200)
        self.workers_spin.setValue(50)
        config_layout.addWidget(self.workers_spin, 1, 3)

        config_group.setLayout(config_layout)
        main_layout.addWidget(config_group)

        # Group box for proxy types selection
        proxy_group = QGroupBox("Proxy Sources")
        proxy_layout = QGridLayout()

        # Default proxy URLs
        self.proxy_urls = {
            "http": "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
            "socks4": "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks4.txt",
            "socks5": "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks5.txt"
        }

        # Create checkboxes and line edits for each proxy type
        self.proxy_type_checkboxes = {}
        self.proxy_url_edits = {}
        row = 0
        for proxy_type, url in self.proxy_urls.items():
            checkbox = QCheckBox(proxy_type)
            checkbox.setChecked(True)
            self.proxy_type_checkboxes[proxy_type] = checkbox
            proxy_layout.addWidget(checkbox, row, 0)

            url_edit = QLineEdit(url)
            self.proxy_url_edits[proxy_type] = url_edit
            proxy_layout.addWidget(url_edit, row, 1)
            row += 1

        proxy_group.setLayout(proxy_layout)
        main_layout.addWidget(proxy_group)

        # Start and Cancel buttons
        btn_layout = QHBoxLayout()
        self.start_btn = QPushButton("Start Checking")
        self.start_btn.clicked.connect(self.start_checking)
        btn_layout.addWidget(self.start_btn)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self.cancel_checking)
        btn_layout.addWidget(self.cancel_btn)
        main_layout.addLayout(btn_layout)

        # Log window to display progress messages
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet("background-color: #1e1e1e; color: #d4d4d4; font-family: Consolas; font-size: 12pt;")
        main_layout.addWidget(self.log_text)

        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)

    def start_checking(self):
        # Disable start button and enable cancel button
        self.start_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.log_text.clear()

        # Build the proxy_urls dictionary from the checkboxes and line edits
        selected_proxy_urls = {}
        for proxy_type, checkbox in self.proxy_type_checkboxes.items():
            if checkbox.isChecked():
                url = self.proxy_url_edits[proxy_type].text().strip()
                if url:
                    selected_proxy_urls[proxy_type] = url

        if not selected_proxy_urls:
            QMessageBox.warning(self, "No Proxies Selected", "Please select at least one proxy type to check.")
            self.start_btn.setEnabled(True)
            self.cancel_btn.setEnabled(False)
            return

        # Get configuration values from the UI
        timeout = self.timeout_spin.value()
        max_retries = self.retries_spin.value()
        retry_delay = self.retry_delay_spin.value()
        max_workers = self.workers_spin.value()

        # Set up the worker and thread
        self.thread = QThread()
        self.worker = ProxyCheckerWorker(
            proxy_urls=selected_proxy_urls,
            timeout=timeout,
            max_retries=max_retries,
            retry_delay=retry_delay,
            max_workers=max_workers
        )
        self.worker.moveToThread(self.thread)

        # Connect signals
        self.worker.progress.connect(self.append_log)
        self.worker.finished.connect(self.on_finished)
        self.thread.started.connect(self.worker.run)
        self.thread.finished.connect(self.thread.deleteLater)

        # Start the thread
        self.thread.start()

    def cancel_checking(self):
        """Called when the Cancel button is clicked."""
        if self.worker is not None:
            self.append_log("Cancel requested by user...")
            self.worker.cancel()
            self.cancel_btn.setEnabled(False)

    def append_log(self, message: str):
        """Appends a message to the log text area."""
        timestamp = time.strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")

    def on_finished(self):
        """Called when the worker has finished processing."""
        self.append_log("All tasks completed.")
        self.start_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        if self.thread is not None:
            self.thread.quit()
            self.thread.wait()

def console_main(args):
    # Build the proxy URL dictionary from command-line arguments.
    proxy_urls = {
        "http": args.http_url,
        "socks4": args.socks4_url,
        "socks5": args.socks5_url
    }
    # For console mode, you might choose to use all proxies (or filter as needed).
    checker = ProxyChecker(
        proxy_urls=proxy_urls,
        timeout=args.timeout,
        max_retries=args.max_retries,
        retry_delay=args.retry_delay,
        max_workers=args.max_workers,
        log_callback=lambda msg: print(msg)
    )

    try:
        print("Starting proxy checking in console mode. Press Ctrl+C to cancel.")
        checker.run()
    except KeyboardInterrupt:
        checker.cancel()
        print("Cancellation requested. Exiting...")
    finally:
        print("Done.")

def main():
    parser = argparse.ArgumentParser(description="Proxy Checker Tool")
    parser.add_argument("--console", action="store_true", help="Run in console mode without GUI")
    parser.add_argument("--timeout", type=int, default=3, help="Timeout in seconds")
    parser.add_argument("--max-retries", type=int, default=3, help="Maximum number of retries")
    parser.add_argument("--retry-delay", type=float, default=1.0, help="Delay between retries in seconds")
    parser.add_argument("--max-workers", type=int, default=50, help="Number of concurrent workers")
    parser.add_argument("--http-url", type=str, default="https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
                        help="URL for HTTP proxies")
    parser.add_argument("--socks4-url", type=str, default="https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks4.txt",
                        help="URL for SOCKS4 proxies")
    parser.add_argument("--socks5-url", type=str, default="https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks5.txt",
                        help="URL for SOCKS5 proxies")
    args = parser.parse_args()

    if args.console:
        console_main(args)
    else:
        # Configure basic logging (this logs to console; GUI logging is handled via the callback)
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

        app = QApplication(sys.argv)
        window = MainWindow()
        window.show()
        sys.exit(app.exec())

if __name__ == "__main__":
    main()