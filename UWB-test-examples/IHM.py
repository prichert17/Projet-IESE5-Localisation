import sys
import re
import threading
import time
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
        self.root.geometry("900x700")
        self.root.configure(bg='#1e1e1e')
        
        # Données
        self.distances = deque(maxlen=100)  # Garder les 100 dernières mesures
        self.timestamps = deque(maxlen=100)
        self.current_distance = 0.0
        self.min_distance = float('inf')
        self.max_distance = 0.0
        self.avg_distance = 0.0
        self.measurement_count = 0
        
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
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Titre
        title_label = tk.Label(main_frame, text="📡 UWB Distance Monitor", 
                              font=('Helvetica', 24, 'bold'),
                              fg='#00ff88', bg='#1e1e1e')
        title_label.pack(pady=(0, 20))
        
        # Frame pour la distance actuelle
        distance_frame = tk.Frame(main_frame, bg='#2d2d2d', relief='ridge', bd=2)
        distance_frame.pack(fill=tk.X, pady=10)
        
        tk.Label(distance_frame, text="Distance actuelle", 
                font=('Helvetica', 14), fg='#888888', bg='#2d2d2d').pack(pady=(10, 0))
        
        self.distance_label = tk.Label(distance_frame, text="-- m", 
                                       font=('Helvetica', 72, 'bold'),
                                       fg='#00ff88', bg='#2d2d2d')
        self.distance_label.pack(pady=20)
        
        # Frame pour les statistiques
        stats_frame = tk.Frame(main_frame, bg='#1e1e1e')
        stats_frame.pack(fill=tk.X, pady=10)
        
        # Grille de stats
        stats_data = [
            ("Min", "min_label", "#ff6b6b"),
            ("Max", "max_label", "#4ecdc4"),
            ("Moyenne", "avg_label", "#ffe66d"),
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
        
        # Log des messages
        log_frame = tk.Frame(main_frame, bg='#1e1e1e')
        log_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        tk.Label(log_frame, text="📋 Log des messages", 
                font=('Helvetica', 12, 'bold'),
                fg='#888888', bg='#1e1e1e').pack(anchor='w')
        
        # Zone de texte avec scrollbar
        log_container = tk.Frame(log_frame, bg='#2d2d2d')
        log_container.pack(fill=tk.BOTH, expand=True, pady=5)
        
        scrollbar = tk.Scrollbar(log_container)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.log_text = tk.Text(log_container, height=8, 
                               font=('Consolas', 9),
                               bg='#2d2d2d', fg='#888888',
                               yscrollcommand=scrollbar.set,
                               state='disabled')
        self.log_text.pack(fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.log_text.yview)
        
        # Boutons de contrôle
        button_frame = tk.Frame(main_frame, bg='#1e1e1e')
        button_frame.pack(fill=tk.X, pady=10)
        
        self.clear_btn = tk.Button(button_frame, text="🗑️ Effacer", 
                                  font=('Helvetica', 10),
                                  command=self._clear_data,
                                  bg='#ff6b6b', fg='white')
        self.clear_btn.pack(side=tk.LEFT, padx=5)
        
        self.status_label = tk.Label(button_frame, text="🔴 En attente de connexion RTT...", 
                                    font=('Helvetica', 10),
                                    fg='#ff6b6b', bg='#1e1e1e')
        self.status_label.pack(side=tk.RIGHT, padx=5)
        
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
            
    def _update_distance(self, distance):
        """Mise à jour de l'affichage de la distance"""
        self.current_distance = distance
        self.measurement_count += 1
        
        # Mise à jour des stats
        self.min_distance = min(self.min_distance, distance)
        self.max_distance = max(self.max_distance, distance)
        
        self.distances.append(distance)
        self.timestamps.append(datetime.now())
        
        self.avg_distance = sum(self.distances) / len(self.distances)
        
        # Mise à jour des labels
        self.distance_label.config(text=f"{distance:.2f} m")
        self.min_label.config(text=f"{self.min_distance:.2f} m")
        self.max_label.config(text=f"{self.max_distance:.2f} m")
        self.avg_label.config(text=f"{self.avg_distance:.2f} m")
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
        self.current_distance = 0.0
        self.min_distance = float('inf')
        self.max_distance = 0.0
        self.avg_distance = 0.0
        self.measurement_count = 0
        
        self.distance_label.config(text="-- m", fg='#00ff88')
        self.min_label.config(text="--")
        self.max_label.config(text="--")
        self.avg_label.config(text="--")
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