import sys
import os
import time
import csv
import json
import logging
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional, Dict, Callable, Union
from threading import Event

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QObject
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTextEdit, QSpinBox, QDoubleSpinBox,
    QCheckBox, QGroupBox, QGridLayout, QMessageBox, QProgressBar, QDialog,
    QComboBox, QFileDialog
)

# Define the current version of this tool.
CURRENT_VERSION = "1.2.9"

class ProxyChecker:
    """
    Fetches proxy lists from given URLs and checks if they work.
    Supports cancellation, progress reporting, and collects optional detailed
    response times, anonymity classification, and geo-location details for working proxies.
    """
    def __init__(self,
                 proxy_urls: Dict[str, str],
                 timeout: int = 1,
                 max_retries: int = 3,
                 retry_delay: float = 1.0,
                 max_workers: int = 20,
                 check_url: str = "http://www.google.com",
                 detailed_results: bool = False,
                 export_format: str = "txt",  # or "csv" or "json"
                 log_callback: Optional[Callable[[str], None]] = None,
                 progress_callback: Optional[Callable[[int], None]] = None):
        """
        :param proxy_urls: Mapping of proxy type to URL.
        :param timeout: Request timeout in seconds.
        :param max_retries: Maximum number of retries when fetching proxies.
        :param retry_delay: Delay between retries in seconds.
        :param max_workers: Number of concurrent threads for checking proxies.
        :param check_url: URL used to test proxies.
        :param detailed_results: If True, record response times, anonymity and geo info for working proxies.
        :param export_format: "txt" for plain text output, "csv" for CSV, or "json" for JSON export.
        :param log_callback: Callback for log messages.
        :param progress_callback: Callback to update overall progress (0–100).
        """
        self.proxy_urls = proxy_urls
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.max_workers = max_workers
        self.check_url = check_url
        self.detailed_results = detailed_results
        self.export_format = export_format.lower()
        self.log_callback = log_callback
        self.progress_callback = progress_callback
        self.cancel_event = Event()

        # Statistics counters
        self.total_proxies_checked = 0
        self.working_proxies_found = 0
        self.overall_total_count = 0
        self.overall_processed_count = 0

        # Store detailed working results by type.
        # For each proxy type, the value is a list of either:
        # - a string (if not detailed) or
        # - a dict (if detailed) with keys: proxy, response_time, anonymity, geo
        self.working_results: Dict[str, List[Union[str, Dict[str, Union[str, float, dict]]]]] = {}

        self.session = requests.Session()

        # Determine the client IP to help with anonymity detection.
        try:
            r = requests.get("https://api.ipify.org?format=json", timeout=3)
            r.raise_for_status()
            self.client_ip = r.json().get("ip")
            self.log("info", f"Client IP determined as {self.client_ip}")
        except requests.RequestException:
            self.client_ip = "unknown"
            self.log("warning", "Could not determine client IP for anonymity detection.")

    def log(self, level: str, message: str) -> None:
        full_message = f"{level.upper()}: {message}"
        if self.log_callback:
            self.log_callback(full_message)
        else:
            print(full_message)

    def cancel(self) -> None:
        self.cancel_event.set()
        self.log("info", "Cancellation requested.")

    def determine_anonymity(self, proxy: str) -> str:
        """
        Determines the anonymity of the proxy by comparing the IP it returns
        with the client IP.
        """
        try:
            session = requests.Session()
            session.proxies = {'http': proxy, 'https': proxy}
            r = session.get("https://api.ipify.org?format=json", timeout=self.timeout)
            r.raise_for_status()
            proxy_ip = r.json().get("ip")
            if proxy_ip == self.client_ip:
                return "transparent"
            else:
                return "anonymous"
        except requests.RequestException:
            return "unknown"

    def get_geo_info(self, ip: str) -> dict:
        """
        Retrieves geographical information for a given IP address using ip-api.com.
        """
        try:
            r = requests.get(f"http://ip-api.com/json/{ip}", timeout=3)
            r.raise_for_status()
            return r.json()  # Contains country, regionName, city, etc.
        except requests.RequestException:
            return {}

    def check_proxy(self, proxy: str) -> Optional[Union[str, dict]]:
        """
        Checks if a single proxy works by sending a request to self.check_url.
        Returns either the proxy (or a dict of details if detailed) if successful;
        otherwise, returns None.
        """
        if self.cancel_event.is_set():
            return None
        try:
            start = time.time()
            session = requests.Session()
            session.proxies = {'http': proxy, 'https': proxy}
            response = session.get(self.check_url, timeout=self.timeout)
            elapsed = time.time() - start
            if response.status_code == 200:
                if self.detailed_results:
                    anonymity = self.determine_anonymity(proxy)
                    # Assume proxy is in the format ip:port; extract IP for geo lookup.
                    ip_only = proxy.split(':')[0]
                    geo = self.get_geo_info(ip_only)
                    return {
                        "proxy": proxy,
                        "response_time": elapsed,
                        "anonymity": anonymity,
                        "geo": geo
                    }
                else:
                    return proxy
        except requests.RequestException:
            return None

    def get_proxies(self, url: str) -> List[str]:
        """Fetches a list of proxies from a URL using retry logic."""
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
        working_proxy_list = []  # type: List[Union[str, dict]]
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

        # Save the working results in memory
        self.working_results[proxy_type] = working_proxy_list

        # Choose file extension based on export format
        if self.export_format == "csv":
            file_ext = ".csv"
        elif self.export_format == "json":
            file_ext = ".json"
        else:
            file_ext = ".txt"
        proxy_file = f'proxies/{proxy_type}{file_ext}'
        self.create_proxy_dir(os.path.dirname(proxy_file))
        try:
            if self.export_format == "csv":
                with open(proxy_file, 'w', newline='') as f:
                    if self.detailed_results:
                        writer = csv.writer(f)
                        writer.writerow(["Proxy", "Response Time (s)", "Anonymity", "Country", "Region", "City"])
                        for item in working_proxy_list:
                            geo = item.get("geo", {})
                            writer.writerow([
                                item.get("proxy"),
                                f"{item.get('response_time', 0):.2f}",
                                item.get("anonymity"),
                                geo.get("country", ""),
                                geo.get("regionName", ""),
                                geo.get("city", "")
                            ])
                    else:
                        writer = csv.writer(f)
                        writer.writerow(["Proxy"])
                        for item in working_proxy_list:
                            writer.writerow([item])
            elif self.export_format == "json":
                with open(proxy_file, 'w') as f:
                    json.dump(working_proxy_list, f, indent=4)
            else:  # Plain text format
                with open(proxy_file, 'w') as f:
                    if self.detailed_results:
                        lines = [
                            f"{item.get('proxy')} - {item.get('response_time'):.2f} s - {item.get('anonymity')} - {item.get('geo', {}).get('country', '')}"
                            for item in working_proxy_list
                        ]
                    else:
                        lines = working_proxy_list
                    f.write('\n'.join(lines) + '\n')
        except OSError as e:
            self.log("error", f"Failed to write working proxies to {proxy_file}: {e}")

        self.log("info", f"Checked {total_proxies} {proxy_type} proxies. Working: {len(working_proxy_list)}.")
        self.total_proxies_checked += total_proxies
        self.working_proxies_found += len(working_proxy_list)
        return len(working_proxy_list)

    def get_statistics(self) -> str:
        """Returns a summary of the checking process."""
        stats = f"Total proxies checked: {self.total_proxies_checked}\n"
        stats += f"Working proxies found: {self.working_proxies_found}\n"
        if self.detailed_results:
            all_times = []
            for lst in self.working_results.values():
                all_times.extend([item.get("response_time") for item in lst if isinstance(item, dict)])
            if all_times:
                avg_time = sum(all_times) / len(all_times)
                stats += f"Average response time: {avg_time:.2f} seconds\n"
        return stats

    def run(self) -> None:
        """Runs the proxy checking process for all proxy types."""
        start_time = time.time()
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
        self.log("info", "Statistics:\n" + self.get_statistics())

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
                 check_url: str,
                 detailed_results: bool,
                 export_format: str):
        super().__init__()
        self.proxy_urls = proxy_urls
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.max_workers = max_workers
        self.check_url = check_url
        self.detailed_results = detailed_results
        self.export_format = export_format
        self.checker: Optional[ProxyChecker] = None

    def log_callback(self, message: str) -> None:
        self.log_signal.emit(message)

    def progress_callback(self, progress: int) -> None:
        self.progress_update.emit(progress)

    def cancel(self) -> None:
        if self.checker is not None:
            self.checker.cancel()

    def run(self) -> None:
        self.checker = ProxyChecker(
            proxy_urls=self.proxy_urls,
            timeout=self.timeout,
            max_retries=self.max_retries,
            retry_delay=self.retry_delay,
            max_workers=self.max_workers,
            check_url=self.check_url,
            detailed_results=self.detailed_results,
            export_format=self.export_format,
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
        self.setGeometry(100, 100, 850, 700)
        self.init_ui()
        self.thread: Optional[QThread] = None
        self.worker: Optional[ProxyCheckerWorker] = None

    def init_ui(self):
        main_widget = QWidget()
        main_layout = QVBoxLayout()

        # Configuration group
        config_group = QGroupBox("Settings")
        config_layout = QGridLayout()

        # Timeout
        config_layout.addWidget(QLabel("Timeout (s):"), 0, 0)
        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(1, 60)
        self.timeout_spin.setValue(3)
        config_layout.addWidget(self.timeout_spin, 0, 1)

        # Max Retries
        config_layout.addWidget(QLabel("Max Retries:"), 0, 2)
        self.retries_spin = QSpinBox()
        self.retries_spin.setRange(1, 10)
        self.retries_spin.setValue(3)
        config_layout.addWidget(self.retries_spin, 0, 3)

        # Retry Delay
        config_layout.addWidget(QLabel("Retry Delay (s):"), 1, 0)
        self.retry_delay_spin = QDoubleSpinBox()
        self.retry_delay_spin.setRange(0.1, 10.0)
        self.retry_delay_spin.setSingleStep(0.1)
        self.retry_delay_spin.setValue(1.0)
        config_layout.addWidget(self.retry_delay_spin, 1, 1)

        # Max Workers
        config_layout.addWidget(QLabel("Max Workers:"), 1, 2)
        self.workers_spin = QSpinBox()
        self.workers_spin.setRange(1, 200)
        self.workers_spin.setValue(50)
        config_layout.addWidget(self.workers_spin, 1, 3)

        # Test URL
        config_layout.addWidget(QLabel("Test URL:"), 2, 0)
        self.test_url_edit = QLineEdit("http://www.google.com")
        config_layout.addWidget(self.test_url_edit, 2, 1, 1, 3)

        # Detailed Results Option
        self.detailed_checkbox = QCheckBox("Detailed Results (Include Response Time, Anonymity & Geo)")
        config_layout.addWidget(self.detailed_checkbox, 3, 0, 1, 2)

        # Export Format Option
        config_layout.addWidget(QLabel("Export Format:"), 3, 2)
        self.export_format_combo = QComboBox()
        self.export_format_combo.addItems(["txt", "csv", "json"])
        config_layout.addWidget(self.export_format_combo, 3, 3)

        config_group.setLayout(config_layout)
        main_layout.addWidget(config_group)

        # Proxy Sources Group
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

        # Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        main_layout.addWidget(self.progress_bar)

        # Main Buttons
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

        # Extra Buttons: Show Statistics, Save Log, and Check for Update
        extra_btn_layout = QHBoxLayout()
        self.show_stats_btn = QPushButton("Show Statistics")
        self.show_stats_btn.setEnabled(False)
        self.show_stats_btn.clicked.connect(self.show_statistics)
        extra_btn_layout.addWidget(self.show_stats_btn)

        self.save_log_btn = QPushButton("Save Log")
        self.save_log_btn.clicked.connect(self.save_log)
        extra_btn_layout.addWidget(self.save_log_btn)

        self.check_update_btn = QPushButton("Check for Update")
        self.check_update_btn.clicked.connect(self.check_for_update)
        extra_btn_layout.addWidget(self.check_update_btn)
        main_layout.addLayout(extra_btn_layout)

        # Log Text Area
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
        self.show_stats_btn.setEnabled(False)
        self.progress_bar.setValue(0)
        self.log_text.clear()

        # Build proxy_urls from selected checkboxes.
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

        # Get settings from UI.
        timeout = self.timeout_spin.value()
        max_retries = self.retries_spin.value()
        retry_delay = self.retry_delay_spin.value()
        max_workers = self.workers_spin.value()
        check_url = self.test_url_edit.text().strip()
        detailed_results = self.detailed_checkbox.isChecked()
        export_format = self.export_format_combo.currentText().strip()

        # Set up the worker and thread.
        self.thread = QThread()
        self.worker = ProxyCheckerWorker(
            proxy_urls=selected_proxy_urls,
            timeout=timeout,
            max_retries=max_retries,
            retry_delay=retry_delay,
            max_workers=max_workers,
            check_url=check_url,
            detailed_results=detailed_results,
            export_format=export_format
        )
        self.worker.moveToThread(self.thread)

        # Connect signals.
        self.worker.log_signal.connect(self.append_log)
        self.worker.progress_update.connect(self.progress_bar.setValue)
        self.worker.finished.connect(self.on_finished)
        self.thread.started.connect(self.worker.run)
        self.thread.finished.connect(self.thread.deleteLater)

        self.thread.start()

    def cancel_checking(self):
        if self.worker is not None:
            self.append_log("Cancel requested by user...")
            self.worker.cancel()
            self.cancel_btn.setEnabled(False)

    def append_log(self, message: str):
        timestamp = time.strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")

    def on_finished(self):
        self.append_log("All tasks completed.")
        self.start_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.show_results_btn.setEnabled(True)
        self.show_stats_btn.setEnabled(True)
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
        
        btn_layout = QHBoxLayout()
        copy_btn = QPushButton("Copy to Clipboard")
        copy_btn.clicked.connect(lambda: QApplication.clipboard().setText(results_text))
        btn_layout.addWidget(copy_btn)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.close)
        btn_layout.addWidget(close_btn)
        dlg_layout.addLayout(btn_layout)
        
        dialog.setLayout(dlg_layout)
        dialog.exec()

    def show_statistics(self):
        """Show a dialog with summary statistics."""
        if self.worker and self.worker.checker:
            stats = self.worker.checker.get_statistics()
        else:
            stats = "No statistics available."
        QMessageBox.information(self, "Statistics", stats)

    def save_log(self):
        """Save the log output to a file."""
        filename, _ = QFileDialog.getSaveFileName(self, "Save Log", "", "Text Files (*.txt);;All Files (*)")
        if filename:
            try:
                with open(filename, 'w') as f:
                    f.write(self.log_text.toPlainText())
                QMessageBox.information(self, "Saved", f"Log saved to {filename}")
            except OSError as e:
                QMessageBox.warning(self, "Error", f"Failed to save log: {e}")

    def check_for_update(self):
        """Checks the GitHub API for the latest release."""
        try:
            response = requests.get("https://api.github.com/repos/Jesewe/proxy-checker/releases/latest", timeout=5)
            response.raise_for_status()
            data = response.json()
            latest_version = data["tag_name"].lstrip("v")
            if latest_version != CURRENT_VERSION:
                msg = (f"New version available: {latest_version}.\n"
                       f"You are using version {CURRENT_VERSION}.\n"
                       f"Visit {data['html_url']} to download the update.")
            else:
                msg = f"You are up-to-date with version {CURRENT_VERSION}."
            QMessageBox.information(self, "Update Check", msg)
        except Exception as e:
            QMessageBox.warning(self, "Update Check", f"Failed to check for updates: {e}")

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
                 check_url: str,
                 detailed_results: bool,
                 export_format: str):
        super().__init__()
        self.proxy_urls = proxy_urls
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.max_workers = max_workers
        self.check_url = check_url
        self.detailed_results = detailed_results
        self.export_format = export_format
        self.checker: Optional[ProxyChecker] = None

    def log_callback(self, message: str) -> None:
        self.log_signal.emit(message)

    def progress_callback(self, progress: int) -> None:
        self.progress_update.emit(progress)

    def cancel(self) -> None:
        if self.checker is not None:
            self.checker.cancel()

    def run(self) -> None:
        self.checker = ProxyChecker(
            proxy_urls=self.proxy_urls,
            timeout=self.timeout,
            max_retries=self.max_retries,
            retry_delay=self.retry_delay,
            max_workers=self.max_workers,
            check_url=self.check_url,
            detailed_results=self.detailed_results,
            export_format=self.export_format,
            log_callback=self.log_callback,
            progress_callback=self.progress_callback
        )
        self.log_callback("Starting proxy checking...")
        self.checker.run()
        self.log_callback("Proxy checking finished.")
        self.finished.emit()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())