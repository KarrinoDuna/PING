# -*- coding: utf-8 -*-
import tkinter as tk
from tkinter import ttk, scrolledtext
import threading
import subprocess
import platform
import re
from collections import deque
import json
import os


class NetworkMonitor:
    def __init__(self, root):
        self.root = root
        self.root.title("Монитор сети")
        self.root.geometry("1200x700")

        # Настройки истории
        self.history_file = 'host_history.json'
        self.MAX_HISTORY_ENTRIES = 10
        self.host_history = []
        self.load_history()

        # Переменные
        self.host = tk.StringVar(value=self.host_history[0] if self.host_history else "ya.ru")
        self.ping_running = False
        self.trace_running = False

        # 🌟 НОВОЕ: Переменные для хранения процессов (ping.exe, tracert.exe)
        self.ping_process = None
        self.trace_process = None
        # ---------------------------------------------------------------------

        # Статистика пинга
        self.ping_stats = {
            'sent': 0,
            'received': 0,
            'lost': 0,
            'times': deque(maxlen=20)
        }

        self.create_widgets()
        self.setup_copy_paste()

        # Сохранение истории и завершение процессов при закрытии
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def load_history(self):
        """Загружает историю хостов из JSON-файла."""
        try:
            if os.path.exists(self.history_file):
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        self.host_history = data
                    else:
                        self.host_history = ["ya.ru"]
            else:
                self.host_history = ["ya.ru"]
        except Exception:
            self.host_history = ["ya.ru"]

    def save_history(self):
        """Сохраняет историю хостов в JSON-файл."""
        try:
            self.update_history(self.host.get())

            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self.host_history, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"Ошибка сохранения истории: {e}")

    def terminate_processes(self):
        """Безопасно завершает все активные дочерние процессы."""

        # 1. Сначала сбрасываем флаг, чтобы остановить циклы в потоках
        self.ping_running = False

        # 2. Завершаем процесс пинга, если он активен
        if self.ping_process and self.ping_process.poll() is None:
            try:
                self.ping_process.terminate()
                self.ping_process.wait(timeout=1)  # Ждем завершения
            except Exception:
                pass
            self.ping_process = None

        # 3. Завершаем процесс трассировки, если он активен
        if self.trace_process and self.trace_process.poll() is None:
            try:
                self.trace_process.terminate()
                self.trace_process.wait(timeout=1)
            except Exception:
                pass
            self.trace_process = None

    def on_closing(self):
        """Вызывается при закрытии окна."""
        self.terminate_processes()
        self.save_history()
        self.root.destroy()

    def update_history(self, current_host):
        """Обновляет список истории: добавляет новый хост и обрезает список."""
        current_host = current_host.strip()
        if not current_host:
            return

        try:
            self.host_history.remove(current_host)
        except ValueError:
            pass

        self.host_history.insert(0, current_host)
        self.host_history = self.host_history[:self.MAX_HISTORY_ENTRIES]
        self.host_combobox['values'] = self.host_history

    def create_widgets(self):
        # Панель управления
        control_frame = ttk.Frame(self.root, padding="10")
        control_frame.grid(row=0, column=0, columnspan=3, sticky="ew")

        ttk.Label(control_frame, text="Хост:").grid(row=0, column=0, padx=5)

        self.host_combobox = ttk.Combobox(
            control_frame,
            textvariable=self.host,
            width=20,
            values=self.host_history,
            state='normal'
        )
        self.host_combobox.grid(row=0, column=1, padx=5)

        ttk.Button(control_frame, text="Старт пинг", command=self.start_ping).grid(row=0, column=2, padx=5)
        ttk.Button(control_frame, text="Стоп пинг", command=self.stop_ping).grid(row=0, column=3, padx=5)

        ttk.Button(control_frame, text="Трассировка", command=self.start_trace).grid(row=0, column=4, padx=5)
        ttk.Button(control_frame, text="Очистить все", command=self.clear_all).grid(row=0, column=5, padx=5)

        paned_window = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        paned_window.grid(row=1, column=0, columnspan=3, sticky="nsew", padx=10, pady=10)

        ping_frame = ttk.LabelFrame(paned_window, text="Пинг (live)", padding="5")
        paned_window.add(ping_frame, weight=1)
        self.ping_text = scrolledtext.ScrolledText(ping_frame, height=25, width=35, wrap=tk.WORD)
        self.ping_text.pack(fill=tk.BOTH, expand=True)

        stats_frame = ttk.LabelFrame(paned_window, text="Статистика пинга", padding="5")
        paned_window.add(stats_frame, weight=1)
        self.stats_text = scrolledtext.ScrolledText(stats_frame, height=25, width=30, wrap=tk.WORD)
        self.stats_text.pack(fill=tk.BOTH, expand=True)

        trace_frame = ttk.LabelFrame(paned_window, text="Трассировка", padding="5")
        paned_window.add(trace_frame, weight=1)
        self.trace_text = scrolledtext.ScrolledText(trace_frame, height=25, width=35, wrap=tk.WORD)
        self.trace_text.pack(fill=tk.BOTH, expand=True)

        self.root.grid_rowconfigure(1, weight=1)
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_columnconfigure(1, weight=1)
        self.root.grid_columnconfigure(2, weight=1)

        self.update_stats_display()

    def setup_copy_paste(self):
        # ... (Код для setup_copy_paste остается без изменений) ...
        def copy_text(event=None):
            widget = self.root.focus_get()
            if isinstance(widget, tk.Text):
                try:
                    widget.event_generate("<<Copy>>")
                except:
                    try:
                        text = widget.get(tk.SEL_FIRST, tk.SEL_LAST)
                        widget.clipboard_clear()
                        widget.clipboard_append(text)
                    except:
                        pass

        def create_context_menu(widget):
            menu = tk.Menu(widget, tearoff=0)
            menu.add_command(label="Копировать", command=copy_text)
            menu.add_separator()
            menu.add_command(label="Выделить все",
                             command=lambda: widget.tag_add(tk.SEL, "1.0", tk.END))

            def show_menu(event):
                menu.tk_popup(event.x_root, event.y_root)

            widget.bind("<Button-3>", show_menu)

        self.root.bind("<Control-c>", copy_text)
        self.root.bind("<Control-C>", copy_text)

        for widget in [self.ping_text, self.stats_text, self.trace_text]:
            create_context_menu(widget)
            widget.config(state='normal', exportselection=True)
            widget.bind("<Control-a>", lambda e: e.widget.tag_add(tk.SEL, "1.0", tk.END))

        self.stats_text.config(state='disabled')

    def get_encoding(self):
        if platform.system().lower() == "windows":
            return 'cp866'
        else:
            return 'utf-8'

    def parse_ping_time(self, line):
        patterns = [
            r'время[=<](\d+)мс',
            r'time[=<](\d+)ms',
            r'time=(\d+\.?\d*)\s*ms',
            r'время=(\d+\.?\d*)\s*мс'
        ]

        for pattern in patterns:
            match = re.search(pattern, line.lower())
            if match:
                return float(match.group(1))
        return None

    def update_stats_display(self):
        stats = self.ping_stats
        total = stats['sent']

        if total > 0:
            loss_percent = (stats['lost'] / total) * 100
        else:
            loss_percent = 0

        if stats['times']:
            avg_time = sum(stats['times']) / len(stats['times'])
            max_time = max(stats['times'])
            min_time = min(stats['times'])
        else:
            avg_time = max_time = min_time = 0

        stats_text = f"""СТАТИСТИКА ПИНГА
{'-' * 30}

Отправлено пакетов: {stats['sent']}
Получено ответов: {stats['received']}
Потеряно пакетов: {stats['lost']}
Потеря: {loss_percent:.1f}%

За последние {len(stats['times'])} пингов:
Средний пинг: {avg_time:.1f} мс
Максимальный: {max_time:.1f} мс
Минимальный:  {min_time:.1f} мс

Статус: {'Активен' if self.ping_running else 'Остановлен'}
"""

        self.stats_text.config(state='normal')
        self.stats_text.delete(1.0, tk.END)
        self.stats_text.insert(tk.END, stats_text)
        self.stats_text.config(state='disabled')

    def ping_host(self):
        host = self.host.get()
        encoding = self.get_encoding()
        startupinfo = None

        self.root.after(0, self.update_history, host)

        if platform.system().lower() == "windows":
            command = ["ping", "-t", host]
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
        else:
            command = ["ping", host]

        self.ping_running = True
        self.ping_stats = {'sent': 0, 'received': 0, 'lost': 0, 'times': deque(maxlen=20)}

        try:
            # 🌟 Сохраняем ссылку на процесс
            self.ping_process = subprocess.Popen(command,
                                                 stdout=subprocess.PIPE,
                                                 stderr=subprocess.PIPE,
                                                 startupinfo=startupinfo)

            while self.ping_running:
                output = self.ping_process.stdout.readline()
                if output:
                    try:
                        decoded_output = output.decode(encoding, errors='ignore')

                        self.root.after(0, self._update_ping_text, decoded_output)

                        line_lower = decoded_output.lower()
                        if "превышен" in line_lower or "timeout" in line_lower or "timed out" in line_lower:
                            self.ping_stats['sent'] += 1
                            self.ping_stats['lost'] += 1
                        elif "байт=" in line_lower or "bytes=" in line_lower or "ttl=" in line_lower:
                            self.ping_stats['sent'] += 1
                            self.ping_stats['received'] += 1
                            ping_time = self.parse_ping_time(decoded_output)
                            if ping_time:
                                self.ping_stats['times'].append(ping_time)

                        self.root.after(0, self.update_stats_display)

                    except Exception as e:
                        print(f"Ошибка обработки: {e}")
                elif self.ping_process.poll() is not None:
                    # Процесс завершился сам по себе
                    break

        except Exception as e:
            self.root.after(0, self._show_ping_error, f"Ошибка пинга: {e}")
        finally:
            # Сбрасываем ссылку на процесс, если он завершился
            self.ping_process = None

    def _update_ping_text(self, text):
        """Обновление текста пинга"""
        self.ping_text.insert(tk.END, text)
        self.ping_text.see(tk.END)

    def _show_ping_error(self, error_text):
        """Отображение ошибки пинга"""
        self.ping_text.insert(tk.END, error_text + "\n")
        self.ping_text.see(tk.END)

    def trace_host(self):
        """Трассировка маршрута"""
        host = self.host.get()
        encoding = self.get_encoding()

        self.root.after(0, self.update_history, host)

        self.root.after(0, self._start_trace_display, host)

        try:
            startupinfo = None

            if platform.system().lower() == "windows":
                command = ["tracert", "-h", "15", host]
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE

                # 🌟 Сохраняем ссылку на процесс
                self.trace_process = subprocess.Popen(command,
                                                      stdout=subprocess.PIPE,
                                                      stderr=subprocess.PIPE,
                                                      startupinfo=startupinfo)
            else:
                command = ["traceroute", "-m", "15", host]
                # 🌟 Сохраняем ссылку на процесс
                self.trace_process = subprocess.Popen(command, stdout=subprocess.PIPE,
                                                      stderr=subprocess.PIPE)

            while True:
                output = self.trace_process.stdout.readline()
                if output:
                    decoded_output = output.decode(encoding, errors='replace')
                    self.root.after(0, self._update_trace_text, decoded_output)
                elif self.trace_process.poll() is not None:
                    break

            stderr = self.trace_process.stderr.read()
            if stderr:
                decoded_error = stderr.decode(encoding, errors='replace')
                self.root.after(0, self._update_trace_text, f"\nОшибки:\n{decoded_error}")

            self.root.after(0, self._finish_trace, self.trace_process.returncode)

        except subprocess.TimeoutExpired:
            self.root.after(0, self._update_trace_text, "\nТрассировка прервана по таймауту\n")
        except FileNotFoundError:
            self.root.after(0, self._update_trace_text, "\nОшибка: tracert/traceroute не найден\n")
        except Exception as e:
            self.root.after(0, self._update_trace_text, f"\nОшибка трассировки: {e}\n")
        finally:
            self.trace_running = False
            # Сбрасываем ссылку на процесс, когда трассировка завершена
            self.trace_process = None

    def _start_trace_display(self, host):
        """Начало отображения трассировки"""
        self.trace_text.delete(1.0, tk.END)
        self.trace_text.insert(tk.END, f"Запуск трассировки к {host}...\n\n")
        self.trace_text.see(tk.END)

    def _update_trace_text(self, text):
        """Обновление текста трассировки"""
        self.trace_text.insert(tk.END, text)
        self.trace_text.see(tk.END)

    def _finish_trace(self, returncode):
        """Завершение трассировки"""
        self.trace_text.insert(tk.END, f"\n\nТрассировка завершена с кодом: {returncode}\n")
        self.trace_text.insert(tk.END, "\n" + "=" * 50 + "\n")
        self.trace_text.see(tk.END)

    def start_ping(self):
        if not self.ping_running:
            self.ping_text.delete(1.0, tk.END)
            self.ping_text.insert(tk.END, f"Запуск пинга к {self.host.get()}...\n")
            self.ping_text.see(tk.END)
            ping_thread = threading.Thread(target=self.ping_host)
            ping_thread.daemon = True
            ping_thread.start()

    def stop_ping(self):
        """Останавливает пинг и принудительно завершает процесс OS."""
        self.ping_running = False

        # 🌟 НОВОЕ: Принудительное завершение процесса при нажатии "Стоп"
        if self.ping_process and self.ping_process.poll() is None:
            try:
                self.ping_process.terminate()
            except Exception:
                pass
            self.ping_process = None
        # -------------------------------------------------------------

        self.ping_text.insert(tk.END, "\nПинг остановлен\n")
        self.ping_text.see(tk.END)
        self.update_stats_display()

    def start_trace(self):
        if not self.trace_running:
            self.trace_running = True
            trace_thread = threading.Thread(target=self.trace_host)
            trace_thread.daemon = True
            trace_thread.start()

    def clear_all(self):
        self.ping_text.delete(1.0, tk.END)
        self.trace_text.delete(1.0, tk.END)

        self.stats_text.config(state='normal')
        self.stats_text.delete(1.0, tk.END)
        self.stats_text.config(state='disabled')

        self.ping_stats = {'sent': 0, 'received': 0, 'lost': 0, 'times': deque(maxlen=20)}
        self.update_stats_display()


def main():
    root = tk.Tk()
    app = NetworkMonitor(root)
    root.mainloop()


if __name__ == "__main__":
    main()