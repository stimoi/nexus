# 📖 Guide d'utilisation du fichier config.yml

## 🎯 Objectif
Le fichier `config.yml` permet de modifier facilement les variables de configuration du bot Nexus sans avoir à éditer le code source `bot.py`.

## 📁 Structure des fichiers
- `config.yml` - Fichier de configuration principal
- `config_loader.py` - Module qui charge la configuration YAML
- `bot.py` - Code du bot (modifié pour utiliser config.yml)
- `requiments.txt` - Dépendances (inclut maintenant PyYAML)

## 🔧 Installation

1. **Installer les dépendances** :
   ```bash
   pip install -r requiments.txt
   ```

2. **Configurer le bot** :
   - Ouvrir `config.yml`
   - Modifier les valeurs selon vos besoins
   - Remplir les informations essentielles (token, IDs, etc.)

## 📋 Sections de configuration

### 🤖 Bot
- `token`: Token Discord du bot
- `owner_id`: ID du propriétaire
- `support_server_id`: ID du serveur de support
- `invite_url`: URL d'invitation du bot
- `command_prefix`: Préfixe des commandes (par défaut ",")

### 🧠 Intelligence Artificielle
- `openai_api_key`: Clé API OpenAI
- `behavior_prompt`: Prompt de comportement de l'IA
- `image_generation_cost`: Coût en crédits pour générer une image
- `message_limit`: Limite de messages anti-spam
- `period_seconds`: Période pour la limite anti-spam

### 🎵 Musique
- `ffmpeg_options`: Options FFmpeg pour la lecture audio
- `ydl_options`: Options yt-dlp pour le téléchargement

### 💰 Économie
- `credit_boost_multiplier`: Multiplicateur de crédits
- `starting_credits`: Crédits de départ des nouveaux utilisateurs
- `starting_money`: Argent de départ
- `daily_reward_min/max`: Récompenses aléatoires pour messages

### 🎯 Quêtes
- `tier_1_quests_required`: Quêtes nécessaires pour le niveau 2
- `tier_2_quests_required`: Quêtes nécessaires pour le niveau 3
- `max_tier`: Niveau maximum
- `possible_quests`: Liste des quêtes disponibles

### 🎟️ Rôles
- `vip_role_id`: ID du rôle VIP (null si non utilisé)
- `ticket_category_id`: ID de la catégorie pour les tickets

### ⚙️ Fonctionnalités
- `imagine_maintenance`: Mode maintenance pour les images
- `event_mode_enabled`: Mode événement (IA illimitée)

### 📁 Stockage
- `data_file`: Nom du fichier de sauvegarde des données

## 🚀 Démarrage

1. **Configurer vos clés** :
   ```yaml
   bot:
     token: "VOTRE_TOKEN_DISCORD"
     owner_id: VOTRE_ID_UTILISATEUR
   
   ai:
     openai_api_key: "VOTRE_CLE_OPENAI"
   ```

2. **Personnaliser les valeurs** :
   - Modifier les coûts, récompenses, limites selon vos préférences
   - Ajuster les quêtes et la progression

3. **Lancer le bot** :
   ```bash
   python bot.py
   ```

## ⚠️ Important

- **Ne partagez jamais** votre `config.yml` contenant vos clés API
- Le fichier `config.yml` est chargé au démarrage du bot
- Redémarrez le bot après avoir modifié la configuration
- Les valeurs par défaut sont incluses pour référence

## 🔄 Mise à jour depuis l'ancien système

Si vous utilisiez l'ancien système avec variables codées en dur dans `bot.py` :

1. ✅ Toutes vos variables ont été transférées dans `config.yml`
2. ✅ Le code `bot.py` a été mis à jour automatiquement
3. ✅ Les dépendances nécessaires ont été ajoutées
4. ✅ Il ne reste plus qu'à configurer vos valeurs personnelles

## 🐛 Dépannage

- **Erreur YAML** : Vérifiez l'indentation (utilisez des espaces, pas de tabulations)
- **ImportError** : Installez PyYAML avec `pip install PyYAML`
- **Configuration non chargée** : Vérifiez que `config.yml` est dans le même dossier que `bot.py`
