import pandas as pd
import matplotlib.pyplot as plt
import os
import glob

def extraire_segment_stable(chemin_fichier, duree_fenetre=10):
    """
    Charge un CSV et extrait le segment de 'duree_fenetre' secondes 
    ayant le plus petit écart-type (le plus stable).
    """
    # 1. Lecture avec détection auto du séparateur
    df = pd.read_csv(chemin_fichier, sep=None, engine='python')
    df.columns = [c.strip() for c in df.columns] # Nettoyage noms colonnes
    
    # 2. Conversion et préparation du temps
    df['Timestamp'] = pd.to_datetime(df['Timestamp'])
    df = df.sort_values('Timestamp')
    
    # Calcul de la durée totale du fichier
    duree_totale = (df['Timestamp'].max() - df['Timestamp'].min()).total_seconds()
    
    # 3. Recherche du segment le plus stable
    if duree_totale <= duree_fenetre:
        print(f"  - {chemin_fichier} : Trop court ({duree_totale:.1f}s), utilisation du fichier complet.")
        segment = df.copy()
        t_depart = segment['Timestamp'].min()
    else:
        # On utilise une fenêtre roulante de X secondes pour calculer l'écart-type
        df_temp = df.set_index('Timestamp')
        # Calcul de l'écart-type sur une fenêtre temporelle
        rolling_std = df_temp['Distance (m)'].rolling(f'{duree_fenetre}s').std()
        
        # On ne garde que les fenêtres qui font vraiment la durée demandée
        # (le début du rolling est incomplet)
        temps_mini_requis = df['Timestamp'].min() + pd.Timedelta(seconds=duree_fenetre)
        valid_windows = rolling_std[rolling_std.index >= temps_mini_requis]
        
        if valid_windows.empty:
            segment = df.copy()
            t_depart = segment['Timestamp'].min()
        else:
            # On trouve le moment où l'écart-type est minimal
            t_fin_stable = valid_windows.idxmin()
            t_depart = t_fin_stable - pd.Timedelta(seconds=duree_fenetre)
            
            # Extraction du segment
            segment = df[(df['Timestamp'] >= t_depart) & (df['Timestamp'] <= t_fin_stable)].copy()
    
    # 4. Création du temps relatif (commence à 0)
    segment['TempsRelatif'] = (segment['Timestamp'] - t_depart).dt.total_seconds()
    
    return segment

def comparer_csv(fenetre_secondes=10):
    fichiers = glob.glob("5m*.csv")
    if not fichiers:
        print("Aucun fichier CSV trouvé dans le dossier.")
        return

    plt.figure(figsize=(12, 6))
    
    for fichier in fichiers:
        try:
            segment = extraire_segment_stable(fichier, fenetre_secondes)
            
            # Calcul de la moyenne du segment pour l'info dans la légende
            moyenne = segment['Distance (m)'].mean()
            std = segment['Distance (m)'].std()
            
            # Tracé : Temps Relatif vs Distance
            plt.plot(segment['TempsRelatif'], segment['Distance (m)'], 
                     label=f"{fichier} (Moy: {moyenne:.2f}m, Std: {std:.4f})", alpha=0.8)
            
        except Exception as e:
            print(f"Erreur sur {fichier} : {e}")

    plt.title(f'Comparaison des segments de {fenetre_secondes}s les plus stables')
    plt.xlabel('Temps écoulé depuis le début du segment (secondes)')
    plt.ylabel('Distance (m)')
    plt.legend(loc='upper right', fontsize='small')
    plt.grid(True, which='both', linestyle='--', alpha=0.5)
    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    # Vous pouvez changer 10 par la durée souhaitée
    comparer_csv(fenetre_secondes=10)