# Configuration de l'environnement nRF Connect (nRF54L15)

Ce document décrit la procédure d'installation et de compilation pour le projet de démonstrateur Localisation (UWB/BLE).

---

## 1. Installation des outils (Windows)

La méthode recommandée passe par le gestionnaire graphique de Nordic pour éviter les erreurs de chemins et de dépendances.

1. Télécharger et installer **nRF Connect for Desktop**.
2. Télécharger et installer **SEGGER J-Link** (dernière version, nécessaire pour flasher les cartes Nordic).
3. Lancer l'application et installer le module **Toolchain Manager**, qui redirige vers l'extension VS Code.
4. Dans VS Code (méthode recommandée par Nordic), installer l'extension : **nRF Connect for VS Code Extension Pack**.

> ⚠️ **Attention** : peut rentrer en conflit avec d'autres extensions comme *CMake Tools*. Désactiver celles-ci si nécessaire.

---

## 2. Créer et configurer une application

1. Dans la barre latérale gauche (icône nRF), cliquer sur **Create a new application**.
2. Configurer comme suit :
   - *Create a blank application*
   - Sélectionner un **path court** pour éviter les erreurs de compilation à cause d'un path trop long.
   - Valider pour créer le projet.

---

## 3. Compilation (Build)

Une fois le projet ouvert :

1. Dans le panneau **APPLICATIONS** (à gauche), cliquer sur **+ Add build configuration**.
2. Sélectionner la cible matérielle (Board Target) : par exemple `nrf54l15dk/nrf54l15/cpuapp` pour notre carte.
3. Cliquer sur **Générer et build**.
4. Attendre la fin de la compilation. Si le message `Build completed successfully` apparaît dans le terminal, l'environnement est fonctionnel.