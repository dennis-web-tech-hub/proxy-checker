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

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QObject, QTimer
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTextEdit, QSpinBox, QDoubleSpinBox,
    QCheckBox, QGroupBox, QGridLayout, QMessageBox, QProgressBar, QDialog,
    QComboBox, QFileDialog
)

# Define the current version of this tool.
CURRENT_VERSION = "1.3.0"

class ProxyChecker:
    """
    Fetches proxy lists from given URLs and checks if they work.
    Supports cancellation, pause/resume, progress reporting, and collects optional detailed
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
                 user_agent: Optional[str] = None,
                 log_callback: Optional[Callable[[str], None]] = None,
                 progress_callback: Optional[Callable[[int], None]] = None):
        self.proxy_urls = proxy_urls
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.max_workers = max_workers
        self.check_url = check_url
        self.detailed_results = detailed_results
        self.export_format = export_format.lower()
        self.user_agent = user_agent
        self.log_callback = log_callback
        self.progress_callback = progress_callback
        self.cancel_event = Event()
        self.pause_event = Event()  # When set, processing is paused

        # Statistics counters
        self.total_proxies_checked = 0
        self.working_proxies_found = 0
        self.overall_total_count = 0
        self.overall_processed_count = 0

        # Store detailed working results by type.
        self.working_results: Dict[str, List[Union[str, Dict[str, Union[str, float, dict]]]]] = {}

        self.session = requests.Session()
        if self.user_agent:
            self.session.headers["User-Agent"] = self.user_agent

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

    def pause(self) -> None:
        self.pause_event.set()
        self.log("info", "Proxy checking paused.")

    def resume(self) -> None:
        self.pause_event.clear()
        self.log("info", "Proxy checking resumed.")

    def determine_anonymity(self, proxy: str) -> str:
        try:
            session = requests.Session()
            session.proxies = {'http': proxy, 'https': proxy}
            r = session.get("https://api.ipify.org?format=json", timeout=self.timeout)
            r.raise_for_status()
            proxy_ip = r.json().get("ip")
            return "transparent" if proxy_ip == self.client_ip else "anonymous"
        except requests.RequestException:
            return "unknown"

    def get_geo_info(self, ip: str) -> dict:
        try:
            r = requests.get(f"http://ip-api.com/json/{ip}", timeout=3)
            r.raise_for_status()
            return r.json()
        except requests.RequestException:
            return {}

    def check_proxy(self, proxy: str) -> Optional[Union[str, dict]]:
        if self.cancel_event.is_set():
            return None
        # If paused, wait until resumed.
        while self.pause_event.is_set():
            time.sleep(0.1)
        try:
            start = time.time()
            session = requests.Session()
            session.proxies = {'http': proxy, 'https': proxy}
            if self.user_agent:
                session.headers["User-Agent"] = self.user_agent
            response = session.get(self.check_url, timeout=self.timeout)
            elapsed = time.time() - start
            if response.status_code == 200:
                if self.detailed_results:
                    anonymity = self.determine_anonymity(proxy)
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
                while self.pause_event.is_set():
                    time.sleep(0.1)
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

        self.working_results[proxy_type] = working_proxy_list
        file_ext = ".csv" if self.export_format == "csv" else ".json" if self.export_format == "json" else ".txt"
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
            else:
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
        minutes, seconds = divmod(end_time - start_time, 60)
        self.log("info", f"Total proxies checked: {self.total_proxies_checked}. Working proxies: {self.working_proxies_found}.")
        self.log("info", f"Execution time: {int(minutes)} minutes {int(seconds)} seconds.")
        self.log("info", "Statistics:\n" + self.get_statistics())
        # Append history log
        try:
            with open("history.log", "a") as hist_file:
                hist_file.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - {self.get_statistics()}\n")
        except OSError as e:
            self.log("error", f"Failed to write history log: {e}")

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
                 export_format: str,
                 user_agent: Optional[str] = None):
        super().__init__()
        self.proxy_urls = proxy_urls
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.max_workers = max_workers
        self.check_url = check_url
        self.detailed_results = detailed_results
        self.export_format = export_format
        self.user_agent = user_agent
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
            user_agent=self.user_agent,
            log_callback=self.log_callback,
            progress_callback=self.progress_callback
        )
        self.log_callback("Starting proxy checking...")
        self.checker.run()
        self.log_callback("Proxy checking finished.")
        self.finished.emit()

class UpdateChecker(QObject):
    """
    Worker class to check for software updates.
    """
    update_checked = pyqtSignal(str)

    def run(self) -> None:
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
        except Exception as e:
            msg = f"Failed to check for updates: {e}"
        self.update_checked.emit(msg)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Proxy Checker")
        self.setGeometry(100, 100, 850, 750)
        self.init_ui()
        self.thread: Optional[QThread] = None
        self.worker: Optional[ProxyCheckerWorker] = None
        self.update_thread: Optional[QThread] = None
        self.last_checker: Optional[ProxyChecker] = None
        self.is_paused = False

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

        # Custom User-Agent
        config_layout.addWidget(QLabel("Custom User-Agent:"), 3, 0)
        self.user_agent_edit = QLineEdit("")
        self.user_agent_edit.setPlaceholderText("Leave blank for default")
        config_layout.addWidget(self.user_agent_edit, 3, 1, 1, 3)

        # Detailed Results Option
        self.detailed_checkbox = QCheckBox("Detailed Results (Include Response Time, Anonymity & Geo)")
        config_layout.addWidget(self.detailed_checkbox, 4, 0, 1, 2)

        # Export Format Option
        config_layout.addWidget(QLabel("Export Format:"), 4, 2)
        self.export_format_combo = QComboBox()
        self.export_format_combo.addItems(["txt", "csv", "json"])
        config_layout.addWidget(self.export_format_combo, 4, 3)

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

        self.pause_btn = QPushButton("Pause")
        self.pause_btn.setEnabled(False)
        self.pause_btn.clicked.connect(self.toggle_pause)
        btn_layout.addWidget(self.pause_btn)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self.cancel_checking)
        btn_layout.addWidget(self.cancel_btn)

        self.show_results_btn = QPushButton("Show Results")
        self.show_results_btn.setEnabled(False)
        self.show_results_btn.clicked.connect(self.show_results)
        btn_layout.addWidget(self.show_results_btn)
        main_layout.addLayout(btn_layout)

        # Extra Buttons: Show Statistics, Save Log
        extra_btn_layout = QHBoxLayout()
        self.show_stats_btn = QPushButton("Show Statistics")
        self.show_stats_btn.setEnabled(False)
        self.show_stats_btn.clicked.connect(self.show_statistics)
        extra_btn_layout.addWidget(self.show_stats_btn)

        self.save_log_btn = QPushButton("Save Log")
        self.save_log_btn.clicked.connect(self.save_log)
        extra_btn_layout.addWidget(self.save_log_btn)
        main_layout.addLayout(extra_btn_layout)

        # Log Text Area
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet("background-color: #1e1e1e; color: #d4d4d4; font-family: Consolas; font-size: 12pt;")
        main_layout.addWidget(self.log_text)

        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)

    def start_checking(self):
        self.start_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.pause_btn.setEnabled(True)
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
            self.pause_btn.setEnabled(False)
            return

        # Get settings from UI.
        timeout = self.timeout_spin.value()
        max_retries = self.retries_spin.value()
        retry_delay = self.retry_delay_spin.value()
        max_workers = self.workers_spin.value()
        check_url = self.test_url_edit.text().strip()
        detailed_results = self.detailed_checkbox.isChecked()
        export_format = self.export_format_combo.currentText().strip()
        user_agent = self.user_agent_edit.text().strip() or None

        self.thread = QThread()
        self.worker = ProxyCheckerWorker(
            proxy_urls=selected_proxy_urls,
            timeout=timeout,
            max_retries=max_retries,
            retry_delay=retry_delay,
            max_workers=max_workers,
            check_url=check_url,
            detailed_results=detailed_results,
            export_format=export_format,
            user_agent=user_agent
        )
        self.worker.moveToThread(self.thread)
        self.worker.log_signal.connect(self.append_log)
        self.worker.progress_update.connect(self.progress_bar.setValue)
        self.worker.finished.connect(self.on_finished)
        self.thread.started.connect(self.worker.run)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.start()

    def toggle_pause(self):
        if self.worker and self.worker.checker:
            if not self.is_paused:
                self.worker.checker.pause()
                self.is_paused = True
                self.pause_btn.setText("Resume")
                self.append_log("Paused proxy checking.")
            else:
                self.worker.checker.resume()
                self.is_paused = False
                self.pause_btn.setText("Pause")
                self.append_log("Resumed proxy checking.")

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
        self.pause_btn.setEnabled(False)
        self.show_results_btn.setEnabled(True)
        self.show_stats_btn.setEnabled(True)
        if self.thread is not None:
            self.thread.quit()
            self.thread.wait()
        # Save a reference to the last checker for filtering results.
        if self.worker:
            self.last_checker = self.worker.checker

    def show_results(self):
        # If detailed results are enabled, allow filtering by response time.
        if self.last_checker and self.last_checker.detailed_results:
            dialog = QDialog(self)
            dialog.setWindowTitle("Filtered Working Proxies")
            dialog.resize(600, 500)
            layout = QVBoxLayout()

            filter_layout = QHBoxLayout()
            filter_layout.addWidget(QLabel("Max Response Time (s):"))
            filter_spin = QDoubleSpinBox()
            filter_spin.setRange(0.1, 10.0)
            filter_spin.setSingleStep(0.1)
            filter_spin.setValue(1.0)
            filter_layout.addWidget(filter_spin)
            apply_btn = QPushButton("Apply Filter")
            filter_layout.addWidget(apply_btn)
            layout.addLayout(filter_layout)

            result_area = QTextEdit()
            result_area.setReadOnly(True)
            layout.addWidget(result_area)

            def apply_filter():
                threshold = filter_spin.value()
                text = ""
                for ptype, results in self.last_checker.working_results.items():
                    filtered = []
                    for item in results:
                        if isinstance(item, dict) and item.get("response_time") <= threshold:
                            geo = item.get("geo", {})
                            filtered.append(f"{item.get('proxy')} - {item.get('response_time'):.2f} s - {item.get('anonymity')} - {geo.get('country', '')}")
                    if filtered:
                        text += f"--- {ptype} ---\n" + "\n".join(filtered) + "\n\n"
                result_area.setText(text if text else "No proxies match the filter criteria.")

            apply_btn.clicked.connect(apply_filter)
            # Show all results initially
            apply_filter()

            btn_layout = QHBoxLayout()
            copy_btn = QPushButton("Copy to Clipboard")
            copy_btn.clicked.connect(lambda: QApplication.clipboard().setText(result_area.toPlainText()))
            btn_layout.addWidget(copy_btn)
            close_btn = QPushButton("Close")
            close_btn.clicked.connect(dialog.close)
            btn_layout.addWidget(close_btn)
            layout.addLayout(btn_layout)

            dialog.setLayout(layout)
            dialog.exec()
        else:
            # Fallback: read the exported files from the proxies directory.
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
        if self.worker and self.worker.checker:
            stats = self.worker.checker.get_statistics()
        else:
            stats = "No statistics available."
        QMessageBox.information(self, "Statistics", stats)

    def save_log(self):
        filename, _ = QFileDialog.getSaveFileName(self, "Save Log", "", "Text Files (*.txt);;All Files (*)")
        if filename:
            try:
                with open(filename, 'w') as f:
                    f.write(self.log_text.toPlainText())
                QMessageBox.information(self, "Saved", f"Log saved to {filename}")
            except OSError as e:
                QMessageBox.warning(self, "Error", f"Failed to save log: {e}")

    def auto_check_for_update(self):
        self.update_thread = QThread()
        self.update_worker = UpdateChecker()
        self.update_worker.moveToThread(self.update_thread)
        self.update_worker.update_checked.connect(self.show_update_message)
        self.update_thread.started.connect(self.update_worker.run)
        self.update_thread.start()

    def show_update_message(self, msg: str):
        QMessageBox.information(self, "Update Check", msg)
        self.update_thread.quit()
        self.update_thread.wait()

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(1000, self.auto_check_for_update)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())