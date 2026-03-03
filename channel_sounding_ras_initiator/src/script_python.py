import sys
import serial
import re
import collections
import csv
import threading
import time
import numpy as np
from datetime import datetime
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QComboBox, QPushButton, QFileDialog)
from PyQt6.QtCore import QTimer, Qt, pyqtSignal, QObject

# --- CONFIGURATION ---
SERIAL_PORT = 'COM5'
BAUD_RATE = 115200
WINDOW_SIZE = 100
MAX_AP = 4

class SerialWorker(QObject):
    """Thread dédié à la capture haute performance"""
    # Signal: ap_id, r, i, k, min, max, moy, med
    data_received = pyqtSignal(int, float, float, float, float, float, float, float)
    stats_updated = pyqtSignal(float, int)

    def __init__(self, port, baud):
        super().__init__()
        self.port = port
        self.baud = baud
        self.running = True
        self.is_recording = False
        self.csv_writer = None
        self.csv_file = None
        self.line_count = 0
        self.total_received = 0
        
        ""
        # Initialisation des stats
        self.reset_statistics()

        try:
            self.ser = serial.Serial(self.port, self.baud, timeout=0.01)
        except Exception as e:
            print(f"Erreur Port: {e}")
            sys.exit(1)

    def reset_statistics(self):
        """Réinitialise les calculs de Min/Max et l'historique glissant"""
        self.history = {ap: collections.deque(maxlen=100) for ap in range(MAX_AP)}
        self.mins = {ap: float('inf') for ap in range(MAX_AP)}
        self.maxs = {ap: float('-inf') for ap in range(MAX_AP)}

    def run(self):
        regex = re.compile(r"AP (\d+) \| RTT Calibre: ([\d.]+)m \| IFFT: ([\d.]+)m \| => FUSION KALMAN: ([\d.]+) meters")
        last_stat_time = time.time()
        frames_in_second = 0
        
        while self.running:
            if self.ser.in_waiting > 0:
                try:
                    lines = self.ser.readlines()
                    for line_raw in lines:
                        line = line_raw.decode('utf-8', errors='ignore').strip()
                        match = regex.search(line)
                        if match:
                            ap_id, r_val, i_val, k_val = int(match.group(1)), float(match.group(2)), float(match.group(3)), float(match.group(4))

                            if ap_id < MAX_AP:
                                # Mise à jour historique
                                self.history[ap_id].append(k_val)
                                if k_val < self.mins[ap_id]: self.mins[ap_id] = k_val
                                if k_val > self.maxs[ap_id]: self.maxs[ap_id] = k_val
                                
                                # Calculs statistiques
                                current_history = list(self.history[ap_id])
                                avg_val = np.mean(current_history)
                                med_val = np.median(current_history)
                                min_val = self.mins[ap_id]
                                max_val = self.maxs[ap_id]

                                # Ecriture CSV (incluant la Médiane)
                                if self.is_recording and self.csv_writer:
                                    now = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                                    self.csv_writer.writerow([
                                        now, ap_id, r_val, i_val, k_val, 
                                        f"{min_val:.3f}", f"{max_val:.3f}", 
                                        f"{avg_val:.3f}", f"{med_val:.3f}"
                                    ])
                                    self.line_count += 1

                                self.total_received += 1
                                frames_in_second += 1
                                self.data_received.emit(ap_id, r_val, i_val, k_val, min_val, max_val, avg_val, med_val)
                except: pass

            current_time = time.time()
            if current_time - last_stat_time >= 1.0:
                hz = frames_in_second / (current_time - last_stat_time)
                self.stats_updated.emit(hz, self.line_count if self.is_recording else self.total_received)
                frames_in_second = 0
                last_stat_time = current_time
        self.ser.close()

class UARTKalmanVisualizer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Nordic CS - Pro Analyzer (Median Filter)")
        self.resize(1100, 950)
        self.setStyleSheet("background-color: #121212; color: #E0E0E0;")

        self.current_ap = 0
        self.data = {ap: {
            'kalman': collections.deque([0.0] * WINDOW_SIZE, maxlen=WINDOW_SIZE),
            'ifft': collections.deque([0.0] * WINDOW_SIZE, maxlen=WINDOW_SIZE),
            'rtt': collections.deque([0.0] * WINDOW_SIZE, maxlen=WINDOW_SIZE)
        } for ap in range(MAX_AP)}

        self.init_ui()

        self.worker = SerialWorker(SERIAL_PORT, BAUD_RATE)
        self.worker.data_received.connect(self.process_new_data)
        self.worker.stats_updated.connect(self.update_stats)
        self.worker_thread = threading.Thread(target=self.worker.run, daemon=True)
        self.worker_thread.start()

        self.display_timer = QTimer()
        self.display_timer.timeout.connect(self.update_plot)
        self.display_timer.start(33)

    def init_ui(self):
        import pyqtgraph as pg
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)

        # Header bar
        header = QHBoxLayout()
        self.hz_label = QLabel("Débit: 0 Hz")
        self.hz_label.setStyleSheet("color: #3498db; font-weight: bold; font-family: Consolas;")
        
        self.reset_btn = QPushButton("Reset Stats")
        self.reset_btn.clicked.connect(lambda: self.worker.reset_statistics())
        self.reset_btn.setStyleSheet("background: #444; color: white; border-radius: 4px;")

        self.record_btn = QPushButton("🔴 Sauvegarder")
        self.record_btn.setCheckable(True)
        self.record_btn.clicked.connect(self.toggle_recording)
        self.record_btn.setFixedSize(120, 30)
        
        header.addWidget(self.hz_label)
        header.addStretch()
        header.addWidget(self.reset_btn)
        header.addWidget(self.record_btn)
        main_layout.addLayout(header)

        # Dashboard Statistiques
        stats_layout = QHBoxLayout()
        self.lbl_min = QLabel("Min: ---")
        self.lbl_max = QLabel("Max: ---")
        self.lbl_avg = QLabel("Moy: ---")
        self.lbl_med = QLabel("Médiane: ---")
        
        for lbl in [self.lbl_min, self.lbl_max, self.lbl_avg, self.lbl_med]:
            lbl.setStyleSheet("font-size: 16px; color: #FFD700; font-family: 'Consolas'; border: 1px solid #333; padding: 5px;")
            stats_layout.addWidget(lbl)
        main_layout.addLayout(stats_layout)

        # Distance Digitale
        self.big_dist = QLabel("0.000 m")
        self.big_dist.setStyleSheet("font-size: 110px; color: #00FF7F; font-family: 'Consolas'; font-weight: bold;")
        self.big_dist.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self.big_dist)

        # Graphique
        self.plot_widget = pg.PlotWidget()
        self.curve_k = self.plot_widget.plot(pen=pg.mkPen('#00FF7F', width=4), name="Kalman")
        self.curve_i = self.plot_widget.plot(pen=pg.mkPen('#3498db', width=1), name="IFFT")
        self.curve_r = self.plot_widget.plot(pen=pg.mkPen('#e74c3c', width=1), name="RTT")
        main_layout.addWidget(self.plot_widget)

    def toggle_recording(self):
        if self.record_btn.isChecked():
            path, _ = QFileDialog.getSaveFileName(self, "Sauvegarder", f"cs_session_{datetime.now().strftime('%H%M%S')}.csv", "CSV (*.csv)")
            if path:
                f = open(path, 'w', newline='')
                writer = csv.writer(f)
                writer.writerow(['Timestamp', 'AP_ID', 'RTT', 'IFFT', 'Kalman', 'Min', 'Max', 'Moy_100', 'Med_100'])
                self.worker.line_count = 0
                self.worker.csv_file = f
                self.worker.csv_writer = writer
                self.worker.is_recording = True
                self.record_btn.setText("⏹️ STOP")
                self.record_btn.setStyleSheet("background: #e74c3c;")
            else:
                self.record_btn.setChecked(False)
        else:
            self.worker.is_recording = False
            if self.worker.csv_file: self.worker.csv_file.close()
            self.record_btn.setText("🔴 Sauvegarder")
            self.record_btn.setStyleSheet("")

    def process_new_data(self, ap_id, r, i, k, d_min, d_max, d_avg, d_med):
        if ap_id < MAX_AP:
            self.data[ap_id]['rtt'].append(r)
            self.data[ap_id]['ifft'].append(i)
            self.data[ap_id]['kalman'].append(k)
            
            if ap_id == self.current_ap:
                self.big_dist.setText(f"{k:.3f} m")
                self.lbl_min.setText(f"Min: {d_min:.3f}")
                self.lbl_max.setText(f"Max: {d_max:.3f}")
                self.lbl_avg.setText(f"Moy: {d_avg:.3f}")
                self.lbl_med.setText(f"Méd: {d_med:.3f}")

    def update_stats(self, hz, count):
        self.hz_label.setText(f"Débit: {hz:.1f} Hz | Points: {count}")

    def update_plot(self):
        d = self.data[self.current_ap]
        self.curve_k.setData(list(d['kalman']))
        self.curve_i.setData(list(d['ifft']))
        self.curve_r.setData(list(d['rtt']))

    def closeEvent(self, event):
        self.worker.running = False
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = UARTKalmanVisualizer()
    win.show()
    sys.exit(app.exec())