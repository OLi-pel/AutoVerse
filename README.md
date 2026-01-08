# AutoVerse

![AutoVerse Logo](https://raw.githubusercontent.com/OLi-pel/AutoVerse/main/assets/logo.png?raw=true) width="150"

**Application de Bureau pour la Transcription et l'Identification des Locuteurs par IA**

[![macOS Build](https://github.com/OLi-pel/AutoVerse/actions/workflows/macos-build.yml/badge.svg)](https://github.com/OLi-pel/AutoVerse/actions/workflows/macos-build.yml)
[![Windows Build](https://github.com/OLi-pel/AutoVerse/actions/workflows/windows-build.yml/badge.svg)](https://github.com/OLi-pel/AutoVerse/actions/workflows/windows-build.yml)
[![Latest Release](https://img.shields.io/github/v/release/OLi-pel/AutoVerse)](https://github.com/OLi-pel/AutoVerse/releases/latest)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

AutoVerse est une solution tout-en-un pour transformer vos fichiers audio et vidéo en texte. Conçu pour être simple mais puissant, il utilise les dernières avancées en IA pour transcrire la parole et identifier précisément qui parle (diarisation), le tout s'exécutant localement sur votre machine pour une confidentialité totale.

---

## ✨ Fonctionnalités Principales

-   **Transcription Haute Précision** : Propulsé par le modèle **Whisper** d'OpenAI.
-   **Identification des Locuteurs (Diarisation)** : Distingue automatiquement les différents intervenants grâce à **Pyannote.audio**.
-   **Performance Accélérée par GPU** :
    -   🚀 **Windows** : Support complet des cartes graphiques NVIDIA (CUDA).
    -   🍎 **macOS** : Support natif des puces Apple Silicon (M1/M2/M3) via Metal (MPS).
-   **Éditeur de Correction Avancé** :
    -   Visualisation de la **forme d'onde** audio synchronisée avec le texte.
    -   Outils de fusion, division et suppression de segments.
    -   Ajustement visuel des horodatages (timestamps).
    -   Gestion complète de l'historique (Annuler/Rétablir).
-   **Tutoriels Interactifs** : Un guide pas-à-pas intégré dans l'application pour vous apprendre à l'utiliser.
-   **Mises à jour Automatiques** : L'application télécharge et installe automatiquement les nouvelles versions.
-   **Traitement par Lots** : Transcrivez plusieurs fichiers en une seule fois.

## 📥 Installation

Téléchargez la dernière version pour votre système d'exploitation depuis la [**Page des Releases**](https://github.com/OLi-pel/AutoVerse/releases/latest).

### macOS
1.  Téléchargez le fichier `AutoVerse-macOS-Installer.dmg`.
2.  Ouvrez le fichier et glissez l'icône `AutoVerse` dans le dossier `Applications`.
3.  Lancez l'application depuis votre dossier Applications.

### Windows
1.  Téléchargez le fichier `AutoVerse-Setup.exe`.
2.  Lancez l'installateur et suivez les instructions.
3.  **Note :** Si Windows SmartScreen apparaît, cliquez sur "Informations complémentaires" puis "Exécuter quand même" (l'application n'est pas encore signée numériquement).

## 🚀 Démarrage Rapide

L'interface est conçue autour d'un flux de travail simple en 3 étapes.

### Étape 1 : Sélection des Fichiers
Glissez-déposez vos fichiers audio ou vidéo (`.mp3`, `.wav`, `.mp4`, `.mov`, etc.) dans la fenêtre principale.

### Étape 2 : Configuration
Activez les options selon vos besoins :
-   **Identifier les locuteurs** : Cochez cette case si plusieurs personnes parlent.
-   **Horodatages** : Inclure les temps de début et de fin.
-   **Fusion Auto** : Combine automatiquement les phrases consécutives du même orateur.

### Étape 3 : Traitement et Correction
Cliquez sur **Démarrer le Traitement**. Une fois terminé, cliquez sur **Aller à l'onglet Correction** pour peaufiner votre transcription dans l'éditeur visuel.

---

## 🔐 Configuration de l'Identification des Locuteurs

Pour utiliser la fonction de détection des locuteurs, vous devez obtenir un jeton d'accès gratuit (Token) de Hugging Face. C'est une étape unique nécessaire pour accepter les conditions d'utilisation des modèles IA.

1.  **Créer un compte Hugging Face**
    Rendez-vous sur [huggingface.co/join](https://huggingface.co/join) (gratuit).

2.  **Accepter les conditions d'utilisation**
    Visitez ces deux pages et cliquez sur le bouton pour accepter les conditions :
    -   [pyannote/segmentation-3.0](https://huggingface.co/pyannote/segmentation-3.0)
    -   [pyannote/speaker-diarization-3.1](https://huggingface.co/pyannote/speaker-diarization-3.1)

3.  **Créer un Token**
    -   Allez dans vos [Paramètres de Tokens](https://huggingface.co/settings/tokens).
    -   Créez un nouveau token avec le rôle **"Read"**.
    -   Copiez le token (il commence par `hf_...`).

4.  **Dans AutoVerse**
    -   Cochez la case "Identifier les différents locuteurs".
    -   Collez votre token et cliquez sur **Gérer le Token** -> **Sauvegarder**.

---

## 🛠️ Pour les Développeurs

Si vous souhaitez exécuter l'application depuis le code source :

**Prérequis :**
-   Python 3.12+
-   FFmpeg (doit être accessible dans le PATH système ou dans un dossier `bin/` à la racine)

**Installation :**

```bash
# Cloner le dépôt
git clone https://github.com/OLi-pel/AutoVerse.git
cd AutoVerse

# Créer un environnement virtuel
python -m venv venv
# Activer (Mac/Linux): source venv/bin/activate
# Activer (Windows): .\venv\Scripts\activate

# Installer les dépendances
# Note : Sur Windows, installez d'abord PyTorch avec support CUDA manuellement si nécessaire
pip install -r requirements.txt

# Lancer l'application
python main_pyside.py
```

## Licence

Ce projet est sous licence MIT. Voir le fichier [LICENSE](LICENSE) pour plus de détails.

---
*Développé avec ❤️ par Olivier.*