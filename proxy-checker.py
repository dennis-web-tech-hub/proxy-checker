import sys
import os
import time
import logging
import argparse
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional, Dict, Callable
from threading import Event

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QObject
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTextEdit, QSpinBox, QDoubleSpinBox,
    QCheckBox, QGroupBox, QGridLayout, QMessageBox, QProgressBar, QDialog
)

class ProxyChecker:
    """
    A class to fetch proxy lists from given URLs and check if they work.
    Cancellation and progress reporting are supported via callbacks.
    """
    def __init__(self,
                 proxy_urls: Dict[str, str],
                 timeout: int = 1,
                 max_retries: int = 3,
                 retry_delay: float = 1.0,
                 max_workers: int = 20,
                 check_url: str = "http://www.google.com",
                 log_callback: Optional[Callable[[str], None]] = None,
                 progress_callback: Optional[Callable[[int], None]] = None):
        """
        :param proxy_urls: Mapping of proxy type (e.g., "http", "socks4") to URL.
        :param timeout: Request timeout in seconds.
        :param max_retries: Maximum number of retries when fetching proxies.
        :param retry_delay: Delay between retries (in seconds).
        :param max_workers: Number of concurrent threads for checking proxies.
        :param check_url: URL to use when testing if a proxy works.
        :param log_callback: Callback to send log messages.
        :param progress_callback: Callback to update overall progress (0–100).
        """
        self.proxy_urls = proxy_urls
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.max_workers = max_workers
        self.check_url = check_url
        self.log_callback = log_callback
        self.progress_callback = progress_callback
        self.cancel_event = Event()

        # Statistics counters
        self.total_proxies_checked = 0
        self.working_proxies_found = 0
        self.overall_total_count = 0
        self.overall_processed_count = 0

        self.session = requests.Session()

    def log(self, level: str, message: str) -> None:
        """Helper function to log messages via the callback or to console."""
        full_message = f"{level.upper()}: {message}"
        if self.log_callback:
            self.log_callback(full_message)
        else:
            print(full_message)

    def cancel(self) -> None:
        """Signal cancellation."""
        self.cancel_event.set()
        self.log("info", "Cancellation requested.")

    def check_proxy(self, proxy: str) -> Optional[str]:
        """
        Checks if a single proxy works by sending a request to self.check_url.
        Returns the proxy if successful; otherwise, None.
        """
        if self.cancel_event.is_set():
            return None
        try:
            session = requests.Session()
            session.proxies = {'http': proxy, 'https': proxy}
            response = session.get(self.check_url, timeout=self.timeout)
            if response.status_code == 200:
                return proxy
        except requests.RequestException:
            return None

    def get_proxies(self, url: str) -> List[str]:
        """
        Fetches a list of proxies from a URL using retry logic.
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
                self.log("warning", f"Attempt {attempt + 1} failed for {url}: {e}")
                time.sleep(self.retry_delay)
        self.log("error", f"Failed to retrieve proxies from {url} after {self.max_retries} attempts.")
        return []

    @staticmethod
    def create_proxy_dir(directory: str) -> None:
        """Creates the directory if it does not exist."""
        os.makedirs(directory, exist_ok=True)

    def process_proxies(self,
                        proxy_type: str,
                        url: Optional[str] = None,
                        proxies: Optional[List[str]] = None) -> int:
        """
        Checks and saves working proxies for a given type.
        If a proxies list is provided, it is used instead of fetching from the URL.
        """
        if proxies is None and url is not None:
            proxies = self.get_proxies(url)
        if self.cancel_event.is_set():
            self.log("info", "Cancellation detected before processing proxies.")
            return 0
        if not proxies:
            self.log("warning", f"No proxies to check for {proxy_type}")
            return 0

        total_proxies = len(proxies)
        self.log("info", f"Checking {total_proxies} {proxy_type} proxies with {self.max_workers} workers.")
        working_proxy_list = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {executor.submit(self.check_proxy, proxy): proxy for proxy in proxies}
            for future in as_completed(futures):
                if self.cancel_event.is_set():
                    self.log("info", "Cancellation detected during proxy checking loop.")
                    break
                result = future.result()
                self.overall_processed_count += 1
                if self.progress_callback and self.overall_total_count > 0:
                    progress_percent = int((self.overall_processed_count / self.overall_total_count) * 100)
                    self.progress_callback(progress_percent)
                if result:
                    working_proxy_list.append(result)

        proxy_file = f'proxies/{proxy_type}.txt'
        self.create_proxy_dir(os.path.dirname(proxy_file))
        try:
            with open(proxy_file, 'w') as f:
                f.write('\n'.join(working_proxy_list) + '\n')
        except OSError as e:
            self.log("error", f"Failed to write working proxies to {proxy_file}: {e}")

        self.log("info", f"Checked {total_proxies} {proxy_type} proxies. Working: {len(working_proxy_list)}.")
        self.total_proxies_checked += total_proxies
        self.working_proxies_found += len(working_proxy_list)
        return len(working_proxy_list)

    def run(self) -> None:
        """Runs the proxy checking process for all proxy types."""
        start_time = time.time()
        # Pre-fetch proxies for all types to compute overall progress
        self.overall_total_count = 0
        self.overall_processed_count = 0
        proxies_by_type: Dict[str, List[str]] = {}

        for proxy_type, url in self.proxy_urls.items():
            if self.cancel_event.is_set():
                self.log("info", "Cancellation detected. Aborting processing.")
                return
            proxies = self.get_proxies(url)
            proxies_by_type[proxy_type] = proxies
            self.overall_total_count += len(proxies)

        if self.overall_total_count == 0:
            self.log("warning", "No proxies fetched from any source.")

        # Process each proxy type using the pre-fetched lists
        for proxy_type, proxies in proxies_by_type.items():
            if self.cancel_event.is_set():
                self.log("info", "Cancellation detected. Aborting further processing.")
                break
            self.process_proxies(proxy_type, proxies=proxies)

        self.session.close()
        end_time = time.time()
        execution_time = end_time - start_time
        minutes, seconds = divmod(execution_time, 60)
        self.log("info", f"Total proxies checked: {self.total_proxies_checked}. Working proxies: {self.working_proxies_found}.")
        self.log("info", f"Execution time: {int(minutes)} minutes {int(seconds)} seconds.")

class ProxyCheckerWorker(QObject):
    """
    Worker class to run the proxy checking process in a separate thread.
    Emits log messages, progress updates, and a finished signal.
    """
    log_signal = pyqtSignal(str)
    progress_update = pyqtSignal(int)
    finished = pyqtSignal()

    def __init__(self,
                 proxy_urls: Dict[str, str],
                 timeout: int,
                 max_retries: int,
                 retry_delay: float,
                 max_workers: int,
                 check_url: str):
        super().__init__()
        self.proxy_urls = proxy_urls
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.max_workers = max_workers
        self.check_url = check_url
        self.checker: Optional[ProxyChecker] = None

    def log_callback(self, message: str) -> None:
        """Emits log messages to the GUI."""
        self.log_signal.emit(message)

    def progress_callback(self, progress: int) -> None:
        """Emits progress updates (0–100) to the GUI."""
        self.progress_update.emit(progress)

    def cancel(self) -> None:
        """Called to cancel the operation."""
        if self.checker is not None:
            self.checker.cancel()

    def run(self) -> None:
        """Starts the proxy checking process."""
        self.checker = ProxyChecker(
            proxy_urls=self.proxy_urls,
            timeout=self.timeout,
            max_retries=self.max_retries,
            retry_delay=self.retry_delay,
            max_workers=self.max_workers,
            check_url=self.check_url,
            log_callback=self.log_callback,
            progress_callback=self.progress_callback
        )
        self.log_callback("Starting proxy checking...")
        self.checker.run()
        self.log_callback("Proxy checking finished.")
        self.finished.emit()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Proxy Checker")
        self.setGeometry(100, 100, 800, 650)
        self.init_ui()
        self.thread: Optional[QThread] = None
        self.worker: Optional[ProxyCheckerWorker] = None

    def init_ui(self):
        # Main widget and layout
        main_widget = QWidget()
        main_layout = QVBoxLayout()

        # Configuration group (settings)
        config_group = QGroupBox("Settings")
        config_layout = QGridLayout()

        # Timeout
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

        # Test URL (custom target for checking proxies)
        config_layout.addWidget(QLabel("Test URL:"), 2, 0)
        self.test_url_edit = QLineEdit("http://www.google.com")
        config_layout.addWidget(self.test_url_edit, 2, 1, 1, 3)

        config_group.setLayout(config_layout)
        main_layout.addWidget(config_group)

        # Proxy sources group
        proxy_group = QGroupBox("Proxy Sources")
        proxy_layout = QGridLayout()

        self.proxy_urls = {
            "http": "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
            "socks4": "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks4.txt",
            "socks5": "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks5.txt"
        }

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

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        main_layout.addWidget(self.progress_bar)

        # Buttons for Start, Cancel, and Show Results
        btn_layout = QHBoxLayout()
        self.start_btn = QPushButton("Start Checking")
        self.start_btn.clicked.connect(self.start_checking)
        btn_layout.addWidget(self.start_btn)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self.cancel_checking)
        btn_layout.addWidget(self.cancel_btn)

        self.show_results_btn = QPushButton("Show Results")
        self.show_results_btn.setEnabled(False)
        self.show_results_btn.clicked.connect(self.show_results)
        btn_layout.addWidget(self.show_results_btn)

        main_layout.addLayout(btn_layout)

        # Log text area
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet("background-color: #1e1e1e; color: #d4d4d4; font-family: Consolas; font-size: 12pt;")
        main_layout.addWidget(self.log_text)

        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)

    def start_checking(self):
        """Initiate the proxy checking process."""
        self.start_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.show_results_btn.setEnabled(False)
        self.progress_bar.setValue(0)
        self.log_text.clear()

        # Build proxy_urls from selected checkboxes
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

        # Get settings values from UI
        timeout = self.timeout_spin.value()
        max_retries = self.retries_spin.value()
        retry_delay = self.retry_delay_spin.value()
        max_workers = self.workers_spin.value()
        check_url = self.test_url_edit.text().strip()

        # Set up the worker and thread
        self.thread = QThread()
        self.worker = ProxyCheckerWorker(
            proxy_urls=selected_proxy_urls,
            timeout=timeout,
            max_retries=max_retries,
            retry_delay=retry_delay,
            max_workers=max_workers,
            check_url=check_url
        )
        self.worker.moveToThread(self.thread)

        # Connect signals
        self.worker.log_signal.connect(self.append_log)
        self.worker.progress_update.connect(self.progress_bar.setValue)
        self.worker.finished.connect(self.on_finished)
        self.thread.started.connect(self.worker.run)
        self.thread.finished.connect(self.thread.deleteLater)

        self.thread.start()

    def cancel_checking(self):
        """Cancel the proxy checking process."""
        if self.worker is not None:
            self.append_log("Cancel requested by user...")
            self.worker.cancel()
            self.cancel_btn.setEnabled(False)

    def append_log(self, message: str):
        """Append a timestamped message to the log area."""
        timestamp = time.strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")

    def on_finished(self):
        """Called when the worker finishes."""
        self.append_log("All tasks completed.")
        self.start_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.show_results_btn.setEnabled(True)
        if self.thread is not None:
            self.thread.quit()
            self.thread.wait()

    def show_results(self):
        """Open a dialog showing the working proxies from the saved files."""
        results_text = ""
        proxy_dir = "proxies"
        if os.path.isdir(proxy_dir):
            for filename in os.listdir(proxy_dir):
                filepath = os.path.join(proxy_dir, filename)
                results_text += f"--- {filename} ---\n"
                try:
                    with open(filepath, 'r') as f:
                        results_text += f.read() + "\n"
                except OSError as e:
                    results_text += f"Error reading file: {e}\n"
        else:
            results_text = "No results found."
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Working Proxies")
        dialog.resize(600, 400)
        dlg_layout = QVBoxLayout()
        text_area = QTextEdit()
        text_area.setReadOnly(True)
        text_area.setText(results_text)
        dlg_layout.addWidget(text_area)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.close)
        dlg_layout.addWidget(close_btn)
        dialog.setLayout(dlg_layout)
        dialog.exec()

def console_main(args):
    proxy_urls = {
        "http": args.http_url,
        "socks4": args.socks4_url,
        "socks5": args.socks5_url
    }
    # Define simple callbacks for logging and progress.
    def log_cb(msg: str):
        print(msg)
    def progress_cb(progress: int):
        print(f"Progress: {progress}%")
    checker = ProxyChecker(
        proxy_urls=proxy_urls,
        timeout=args.timeout,
        max_retries=args.max_retries,
        retry_delay=args.retry_delay,
        max_workers=args.max_workers,
        check_url=args.test_url,
        log_callback=log_cb,
        progress_callback=progress_cb
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
    parser.add_argument("--test-url", type=str, default="http://www.google.com", help="URL used to test proxies")
    args = parser.parse_args()

    if args.console:
        console_main(args)
    else:
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
        app = QApplication(sys.argv)
        window = MainWindow()
        window.show()
        sys.exit(app.exec())

if __name__ == "__main__":
    main()