import sys
import re
import threading
import time
import csv
import statistics
import os
from collections import deque
from datetime import datetime

try:
    import tkinter as tk
    from tkinter import ttk, messagebox
except ImportError:
    print("tkinter est requis. Installez-le avec: pip install tk")
    sys.exit(1)

try:
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    print("matplotlib non disponible - graphique désactivé")

# Essayer d'importer pylink pour la connexion J-Link RTT
try:
    import pylink
    PYLINK_AVAILABLE = True
except ImportError:
    PYLINK_AVAILABLE = False
    print("pylink non disponible - installez avec: pip install pylink-square")


class PyLinkRTTReader:
    """Lecteur de données RTT via pylink (J-Link)"""
    
    def __init__(self, device="NRF52833_XXAA", serial_no=None):
        self.device = device
        self.serial_no = serial_no  # Numéro de série J-Link (ex: 760216204)
        self.jlink = None
        self.running = False
        
    def start(self, callback):
        """Démarre la lecture RTT"""
        self.running = True
        self.callback = callback
        self.thread = threading.Thread(target=self._read_loop, daemon=True)
        self.thread.start()
        
    def _read_loop(self):
        """Boucle de lecture RTT"""
        try:
            self.jlink = pylink.JLink()
            
            # Connexion au J-Link
            if self.serial_no:
                self.jlink.open(serial_no=self.serial_no)
            else:
                self.jlink.open()
                
            self.callback(f"J-Link connecté: {self.jlink.product_name}")
            
            # Connexion à la cible
            self.jlink.set_tif(pylink.enums.JLinkInterfaces.SWD)
            self.jlink.connect(self.device, verbose=True)
            self.callback(f"Connecté à {self.device}")
            
            # Démarrer RTT
            self.jlink.rtt_start()
            self.callback("RTT démarré - En attente de données...")
            
            # Attendre que RTT soit prêt
            time.sleep(0.5)
            
            # Buffer pour accumuler les données
            buffer = ""
            
            while self.running:
                try:
                    # Lire les données RTT du canal 0 (terminal up)
                    data = self.jlink.rtt_read(0, 1024)
                    if data:
                        # Convertir les bytes en string
                        text = bytes(data).decode('utf-8', errors='ignore')
                        buffer += text
                        
                        # Traiter les lignes complètes
                        while '\n' in buffer:
                            line, buffer = buffer.split('\n', 1)
                            line = line.strip()
                            if line:
                                self.callback(line)
                    else:
                        time.sleep(0.01)  # Petit délai si pas de données
                        
                except Exception as e:
                    self.callback(f"Erreur lecture RTT: {str(e)}")
                    time.sleep(0.1)
                    
        except pylink.errors.JLinkException as e:
            self.callback(f"ERREUR J-Link: {str(e)}")
            self.callback("Vérifiez que nRF Connect n'utilise pas le J-Link")
        except Exception as e:
            self.callback(f"ERREUR: {str(e)}")
            
    def stop(self):
        """Arrête la lecture RTT"""
        self.running = False
        if self.jlink:
            try:
                self.jlink.rtt_stop()
                self.jlink.close()
            except:
                pass


class FileRTTReader:
    """Lecteur de données depuis un fichier (pour copier-coller depuis RTT Viewer)"""
    
    def __init__(self, filepath):
        self.filepath = filepath
        self.running = False
        self.last_position = 0
        
    def start(self, callback):
        self.running = True
        self.callback = callback
        self.thread = threading.Thread(target=self._read_loop, daemon=True)
        self.thread.start()
        
    def _read_loop(self):
        self.callback(f"Lecture du fichier: {self.filepath}")
        self.callback("Collez les données RTT dans ce fichier...")
        
        while self.running:
            try:
                with open(self.filepath, 'r') as f:
                    f.seek(self.last_position)
                    new_data = f.read()
                    if new_data:
                        self.last_position = f.tell()
                        for line in new_data.strip().split('\n'):
                            if line.strip():
                                self.callback(line.strip())
            except FileNotFoundError:
                # Créer le fichier s'il n'existe pas
                open(self.filepath, 'w').close()
            except Exception as e:
                self.callback(f"Erreur fichier: {str(e)}")
            time.sleep(0.1)
            
    def stop(self):
        self.running = False


class SimulatedReader:
    """Lecteur simulé pour les tests"""
    
    def __init__(self):
        self.running = False
        import random
        self.random = random
        
    def start(self, callback):
        self.running = True
        self.thread = threading.Thread(target=self._simulate, args=(callback,), daemon=True)
        self.thread.start()
        
    def _simulate(self, callback):
        import time
        base_distance = 1.0
        while self.running:
            # Simule des variations de distance
            distance = base_distance + self.random.gauss(0, 0.1)
            callback(f"DIST: {distance:.2f} m")
            time.sleep(0.5)
            callback(f"*** DISTANCE: {distance:.2f} m ***")
            time.sleep(0.5)
            
    def stop(self):
        self.running = False


class DistanceMonitorApp:
    """Application principale de monitoring de distance UWB"""
    
    def __init__(self, root, reader_type="simulation", serial_no=None):
        self.root = root
        self.root.title("UWB Distance Monitor - SS-TWR")
        
        # Adapter la fenêtre à la taille de l'écran
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        self.root.geometry(f"{screen_width}x{screen_height}+0+0")
        
        # Maximiser la fenêtre (fonctionne sur Windows)
        try:
            self.root.state('zoomed')
        except tk.TclError:
            pass # Fallback si 'zoomed' n'est pas supporté sur l'OS
            
        self.root.configure(bg='#1e1e1e')
        
        # Données
        self.distances = deque(maxlen=100)  # Garder les 100 dernières mesures
        self.timestamps = deque(maxlen=100)
        self.median_window = deque(maxlen=10)  # Fenêtre glissante pour la médiane
        self.current_distance = 0.0
        self.min_distance = float('inf')
        self.max_distance = 0.0
        self.avg_distance = 0.0
        self.measurement_count = 0
        
        # Export CSV
        self.csv_export_folder = r"C:\Projet-IESE5-Localisation\Résultat mesures"
        self.csv_file = None
        self.csv_writer = None
        self.csv_exporting = False
        
        # Créer le lecteur approprié
        if reader_type == "simulation":
            self.reader = SimulatedReader()
        elif reader_type == "pylink":
            self.reader = PyLinkRTTReader(serial_no=serial_no)
        elif reader_type == "file":
            self.reader = FileRTTReader("rtt_data.txt")
        else:
            self.reader = SimulatedReader()
        
        # Regex pour parser les distances
        self.distance_pattern = re.compile(r'DIST:\s*([\d.]+)\s*m')
        
        # Construction de l'interface
        self._build_ui()
        
        # Démarrage de la lecture
        self.reader.start(self._on_data_received)
        
        # Fermeture propre
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)
        
    def _build_ui(self):
        """Construction de l'interface graphique"""
        
        # Style
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('Title.TLabel', font=('Helvetica', 24, 'bold'), 
                       foreground='#00ff88', background='#1e1e1e')
        style.configure('Distance.TLabel', font=('Helvetica', 72, 'bold'), 
                       foreground='#00ff88', background='#2d2d2d')
        style.configure('Stats.TLabel', font=('Helvetica', 14), 
                       foreground='#ffffff', background='#1e1e1e')
        style.configure('Log.TLabel', font=('Consolas', 10), 
                       foreground='#888888', background='#1e1e1e')
        
        # Frame principal
        main_frame = tk.Frame(self.root, bg='#1e1e1e')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(20, 5))
        
        # ====== Boutons de contrôle (packés EN PREMIER avec side=BOTTOM) ======
        button_frame = tk.Frame(main_frame, bg='#1e1e1e')
        button_frame.pack(fill=tk.X, pady=(5, 0), side=tk.BOTTOM)
        
        self.clear_btn = tk.Button(button_frame, text="🗑️ Effacer", 
                                  font=('Helvetica', 10),
                                  command=self._clear_data,
                                  bg='#ff6b6b', fg='white')
        self.clear_btn.pack(side=tk.LEFT, padx=5)
        
        tk.Label(button_frame, text="Nom CSV:", font=('Helvetica', 10), 
                 fg='#888888', bg='#1e1e1e').pack(side=tk.LEFT, padx=(15, 2))
        
        self.filename_var = tk.StringVar()
        self.filename_entry = tk.Entry(button_frame, textvariable=self.filename_var, 
                                      font=('Helvetica', 10), width=20, 
                                      bg='#2d2d2d', fg='white', insertbackground='white')
        self.filename_entry.pack(side=tk.LEFT, padx=5)
        
        self.export_btn = tk.Button(button_frame, text="📁 Démarrer Export CSV", 
                                   font=('Helvetica', 10),
                                   command=self._toggle_csv_export,
                                   bg='#4ecdc4', fg='white')
        self.export_btn.pack(side=tk.LEFT, padx=5)
        
        self.status_label = tk.Label(button_frame, text="🔴 En attente de connexion RTT...", 
                                    font=('Helvetica', 10),
                                    fg='#ff6b6b', bg='#1e1e1e')
        self.status_label.pack(side=tk.RIGHT, padx=5)
        
        # ====== Log des messages (packé avec side=BOTTOM, au-dessus des boutons) ======
        log_frame = tk.Frame(main_frame, bg='#1e1e1e')
        log_frame.pack(fill=tk.X, pady=5, side=tk.BOTTOM)
        
        tk.Label(log_frame, text="📋 Log des messages", 
                font=('Helvetica', 12, 'bold'),
                fg='#888888', bg='#1e1e1e').pack(anchor='w')
        
        log_container = tk.Frame(log_frame, bg='#2d2d2d')
        log_container.pack(fill=tk.X, pady=5)
        
        scrollbar = tk.Scrollbar(log_container)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.log_text = tk.Text(log_container, height=4, 
                               font=('Consolas', 9),
                               bg='#2d2d2d', fg='#888888',
                               yscrollcommand=scrollbar.set,
                               state='disabled')
        self.log_text.pack(fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.log_text.yview)
        
        # ====== Contenu principal (packé avec side=TOP, remplit l'espace restant) ======
        # Titre
        title_label = tk.Label(main_frame, text="📡 UWB Distance Monitor", 
                              font=('Helvetica', 24, 'bold'),
                              fg='#00ff88', bg='#1e1e1e')
        title_label.pack(pady=(0, 10))
        
        # Frame pour la distance actuelle
        distance_frame = tk.Frame(main_frame, bg='#2d2d2d', relief='ridge', bd=2)
        distance_frame.pack(fill=tk.X, pady=5)
        
        tk.Label(distance_frame, text="Distance actuelle", 
                font=('Helvetica', 14), fg='#888888', bg='#2d2d2d').pack(pady=(5, 0))
        
        self.distance_label = tk.Label(distance_frame, text="-- m", 
                                       font=('Helvetica', 72, 'bold'),
                                       fg='#00ff88', bg='#2d2d2d')
        self.distance_label.pack(pady=10)
        
        # Frame pour les statistiques
        stats_frame = tk.Frame(main_frame, bg='#1e1e1e')
        stats_frame.pack(fill=tk.X, pady=5)
        
        # Grille de stats
        stats_data = [
            ("Min", "min_label", "#ff6b6b"),
            ("Max", "max_label", "#4ecdc4"),
            ("Moyenne", "avg_label", "#ffe66d"),
            ("Médiane", "median_label", "#ffd480"),
            ("Mesures", "count_label", "#95e1d3")
        ]
        
        for i, (title, attr, color) in enumerate(stats_data):
            frame = tk.Frame(stats_frame, bg='#2d2d2d', relief='ridge', bd=1)
            frame.grid(row=0, column=i, padx=5, pady=5, sticky='nsew')
            stats_frame.columnconfigure(i, weight=1)
            
            tk.Label(frame, text=title, font=('Helvetica', 10), 
                    fg='#888888', bg='#2d2d2d').pack(pady=(5, 0))
            label = tk.Label(frame, text="--", font=('Helvetica', 18, 'bold'), 
                           fg=color, bg='#2d2d2d')
            label.pack(pady=(0, 5))
            setattr(self, attr, label)
        
        # Graphique (si matplotlib disponible)
        if MATPLOTLIB_AVAILABLE:
            self._build_graph(main_frame)
        
    def _build_graph(self, parent):
        """Construction du graphique matplotlib"""
        graph_frame = tk.Frame(parent, bg='#2d2d2d', relief='ridge', bd=2)
        graph_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        self.fig = Figure(figsize=(8, 3), facecolor='#2d2d2d')
        self.ax = self.fig.add_subplot(111)
        self.ax.set_facecolor('#1e1e1e')
        self.ax.set_xlabel('Temps', color='white')
        self.ax.set_ylabel('Distance (m)', color='white')
        self.ax.tick_params(colors='white')
        self.ax.spines['bottom'].set_color('white')
        self.ax.spines['top'].set_color('#2d2d2d')
        self.ax.spines['left'].set_color('white')
        self.ax.spines['right'].set_color('#2d2d2d')
        self.ax.grid(True, alpha=0.3)
        
        self.line, = self.ax.plot([], [], color='#00ff88', linewidth=2)
        
        self.canvas = FigureCanvasTkAgg(self.fig, master=graph_frame)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
    def _on_data_received(self, data):
        """Callback appelé quand une donnée est reçue"""
        # Mise à jour dans le thread principal
        self.root.after(0, lambda: self._process_data(data))
        
    def _process_data(self, data):
        """Traitement des données reçues"""
        # Log du message
        self._log_message(data)
        
        # Parser la distance
        match = self.distance_pattern.search(data)
        if match:
            distance = float(match.group(1))
            self._update_distance(distance)
            
        # Mise à jour du statut de connexion
        if "ERREUR" in data:
            self.status_label.config(text=f"🔴 {data}", fg='#ff6b6b')
        elif self.measurement_count > 0:
            self.status_label.config(text="🟢 Connecté - Réception des données", fg='#00ff88')
            
    def _compute_sliding_average(self):
        """Retourne la moyenne glissante des dernières mesures (jusqu'à 100).
        Utilise le buffer `self.distances` défini avec maxlen=100.
        """
        if not self.distances:
            return 0.0
        return sum(self.distances) / len(self.distances)

    def _compute_median(self):
        """Retourne la médiane glissante des dernières mesures stockées.
        Renvoie 0.0 si aucune mesure n'est disponible.
        """
        if not self.median_window:
            return 0.0
        # Utilise statistics.median pour gérer pair/impair proprement
        return statistics.median(self.median_window)

    def _update_distance(self, distance):
        """Mise à jour de l'affichage de la distance"""
        self.current_distance = distance
        self.measurement_count += 1
        
        # Mise à jour des stats
        self.min_distance = min(self.min_distance, distance)
        self.max_distance = max(self.max_distance, distance)
        
        self.distances.append(distance)
        self.timestamps.append(datetime.now())
        self.median_window.append(distance)
        
        # Utilisation de la fonction de moyenne glissante et calcul de la médiane
        self.avg_distance = self._compute_sliding_average()
        self.median_distance = self._compute_median()
        
        # Mise à jour des labels
        self.distance_label.config(text=f"{distance:.2f} m")
        self.min_label.config(text=f"{self.min_distance:.2f} m")
        self.max_label.config(text=f"{self.max_distance:.2f} m")
        self.avg_label.config(text=f"{self.avg_distance:.2f} m")
        # Mettre à jour le label médiane s'il existe
        if hasattr(self, 'median_label'):
            self.median_label.config(text=f"{self.median_distance:.2f} m")
        self.count_label.config(text=str(self.measurement_count))
        
        # Couleur selon la distance
        if distance < 1.0:
            color = '#00ff88'  # Vert - proche
        elif distance < 3.0:
            color = '#ffe66d'  # Jaune - moyen
        else:
            color = '#ff6b6b'  # Rouge - loin
        self.distance_label.config(fg=color)
        
        # Mise à jour du graphique
        if MATPLOTLIB_AVAILABLE and len(self.distances) > 1:
            self._update_graph()
        
        # Export CSV si actif
        if self.csv_exporting and self.csv_writer:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            self.csv_writer.writerow([timestamp, distance, self.min_distance, self.max_distance, self.avg_distance, getattr(self, 'median_distance', 0.0)])
            self.csv_file.flush()  # S'assurer que les données sont écrites
            
    def _toggle_csv_export(self):
        """Démarre ou arrête l'export CSV"""
        if self.csv_exporting:
            self._stop_csv_export()
        else:
            self._start_csv_export()
            
    def _start_csv_export(self):
        """Démarre l'export CSV dans un nouveau fichier"""
        try:
            # Créer le dossier s'il n'existe pas
            os.makedirs(self.csv_export_folder, exist_ok=True)
            
            # Déterminer le nom du fichier
            custom_name = self.filename_var.get().strip()
            if custom_name:
                if not custom_name.lower().endswith('.csv'):
                    custom_name += '.csv'
                filename = custom_name
            else:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"mesures_uwb_{timestamp}.csv"
                
            filepath = os.path.join(self.csv_export_folder, filename)
            file_exists = os.path.isfile(filepath)
            
            # Ouvrir le fichier CSV (en mode ajout si le fichier existe déjà)
            self.csv_file = open(filepath, 'a' if file_exists else 'w', newline='', encoding='utf-8')
            self.csv_writer = csv.writer(self.csv_file)
            
            # Écrire l'en-tête seulement si c'est un nouveau fichier
            if not file_exists:
                self.csv_writer.writerow(['Timestamp', 'Distance (m)', 'Min (m)', 'Max (m)', 'Moyenne (m)', 'Médiane (m)'])
            self.csv_file.flush()
            
            self.csv_exporting = True
            self.export_btn.config(text="⏹️ Arrêter Export CSV", bg='#ff6b6b')
            self.filename_entry.config(state='disabled')  # Désactiver le champ texte
            self._log_message(f"Export CSV démarré: {filepath}")
            
        except Exception as e:
            messagebox.showerror("Erreur", f"Impossible de créer le fichier CSV:\n{str(e)}")
            
    def _stop_csv_export(self):
        """Arrête l'export CSV"""
        if self.csv_file:
            try:
                self.csv_file.close()
                self._log_message("Export CSV arrêté")
            except:
                pass
        self.csv_file = None
        self.csv_writer = None
        self.csv_exporting = False
        self.export_btn.config(text="📁 Démarrer Export CSV", bg='#4ecdc4')
        self.filename_entry.config(state='normal')  # Réactiver le champ texte
            
    def _update_graph(self):
        """Mise à jour du graphique"""
        x_data = list(range(len(self.distances)))
        y_data = list(self.distances)
        
        self.line.set_data(x_data, y_data)
        self.ax.relim()
        self.ax.autoscale_view()
        
        # Ajout d'une ligne moyenne
        if hasattr(self, 'avg_line'):
            self.avg_line.remove()
        self.avg_line = self.ax.axhline(y=self.avg_distance, color='#ffe66d', 
                                        linestyle='--', alpha=0.5, label='Moyenne')
        
        self.canvas.draw()
        
    def _log_message(self, message):
        """Ajoute un message au log"""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        
        self.log_text.config(state='normal')
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)  # Auto-scroll
        self.log_text.config(state='disabled')
        
        # Limiter le nombre de lignes
        lines = int(self.log_text.index('end-1c').split('.')[0])
        if lines > 200:
            self.log_text.config(state='normal')
            self.log_text.delete('1.0', '50.0')
            self.log_text.config(state='disabled')
            
    def _clear_data(self):
        """Efface toutes les données"""
        self.distances.clear()
        self.timestamps.clear()
        self.median_window.clear()
        self.current_distance = 0.0
        self.min_distance = float('inf')
        self.max_distance = 0.0
        self.avg_distance = 0.0
        self.median_distance = 0.0
        self.measurement_count = 0
        
        self.distance_label.config(text="-- m", fg='#00ff88')
        self.min_label.config(text="--")
        self.max_label.config(text="--")
        self.avg_label.config(text="--")
        if hasattr(self, 'median_label'):
            self.median_label.config(text="--")
        self.count_label.config(text="0")
        
        if MATPLOTLIB_AVAILABLE:
            self.line.set_data([], [])
            if hasattr(self, 'avg_line'):
                self.avg_line.remove()
                del self.avg_line
            self.canvas.draw()
            
        self.log_text.config(state='normal')
        self.log_text.delete('1.0', tk.END)
        self.log_text.config(state='disabled')
        
    def _on_closing(self):
        """Fermeture propre de l'application"""
        self._stop_csv_export()  # Fermer le fichier CSV proprement
        self.reader.stop()
        self.root.destroy()


def main():
    # Parser les arguments
    use_simulation = "--simulate" in sys.argv or "-s" in sys.argv
    use_file = "--file" in sys.argv or "-f" in sys.argv
    serial_no = None
    
    # Chercher le numéro de série J-Link
    for i, arg in enumerate(sys.argv):
        if arg in ["--serial", "--sn"] and i + 1 < len(sys.argv):
            serial_no = int(sys.argv[i + 1])
    
    print("=" * 50)
    print("   UWB Distance Monitor")
    print("=" * 50)
    
    if use_simulation:
        print("Mode: SIMULATION")
        reader_type = "simulation"
    elif use_file:
        print("Mode: FICHIER")
        print("Collez vos données RTT dans: rtt_data.txt")
        reader_type = "file"
    elif PYLINK_AVAILABLE:
        print("Mode: J-Link RTT (pylink)")
        if serial_no:
            print(f"J-Link Serial: {serial_no}")
        else:
            print("Utilisez --serial <numero> pour spécifier le J-Link")
        print("\n⚠️  IMPORTANT: Fermez nRF Connect RTT avant de lancer!")
        reader_type = "pylink"
    else:
        print("Mode: FICHIER (pylink non disponible)")
        print("Installez pylink avec: pip install pylink-square")
        print("Ou utilisez --file pour lire depuis rtt_data.txt")
        reader_type = "file"
    
    print("\nOptions disponibles:")
    print("  --simulate, -s     Mode simulation")
    print("  --file, -f         Lecture depuis rtt_data.txt")
    print("  --serial <num>     Numéro de série J-Link")
    print("=" * 50)
    
    root = tk.Tk()
    app = DistanceMonitorApp(root, reader_type=reader_type, serial_no=serial_no)
    root.mainloop()


if __name__ == "__main__":
    main()