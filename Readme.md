Configuration de l'environnement nRF Connect (nRF54L15)
Ce document décrit la procédure d'installation et de compilation pour le projet de démonstrateur Localisation (UWB/BLE).

1. Installation des outils (Windows)

La méthode recommandée passe par le gestionnaire graphique de Nordic pour éviter les erreurs de chemins et de dépendances.

Télécharger et installer nRF Connect for Desktop.

Lancer l'application et installer le module Toolchain Manager.

Ouvrir Toolchain Manager :

Installer la dernière version recommandée du nRF Connect SDK v3.x.x.

Cela installera automatiquement Zephyr OS, le compilateur GCC ARM et les outils nécessaires.

Dans VS Code (méthode recommandée a par Nordic), installer l'extension : nRF Connect for VS Code Extension Pack.

(Attention : peut rentrer en conflit avec d'autres extensions comme Cmake Tools. Désactiver celles-ci si nécessaire.)



2. Créer et configurer une application

Dans la barre latérale gauche (icône nRF), cliquer sur Create a new application.

Configurer comme suit :

- Create a blank application

- Sélectionner un path court pour éviter les erreurs de compilation à cause d'un path trop long.

- Valider pour créer le projet.



3. Compilation (Build)

Une fois le projet ouvert :

Dans le panneau APPLICATIONS (à gauche), cliquer sur + Add build configuration.

Sélectionner la cible matérielle (Board Target) : par exemple nrf54l15dk/nrf54l15/cpuapp pour notre carte.

Cliquer sur Générer et build.

Attendre la fin de la compilation. Si le message Build completed successfully apparaît dans le terminal, l'environnement est fonctionnel.