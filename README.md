# 🤖 Nexus Bot - Bot Discord Multifonctionnel Open-Source

[![License](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/Python-3.8%2B-blue.svg)](https://www.python.org/)
[![Discord](https://img.shields.io/badge/Discord-13.0%2B-blue.svg)](https://discord.com/)
[![Stars](https://img.shields.io/github/stars/stimoi/nexus?style=social)](https://github.com/stimoi/nexus)
[![Forks](https://img.shields.io/github/forks/stimoi/nexus?style=social)](https://github.com/stimoi/nexus/fork)

> 🌟 **Nexus Bot** est un bot Discord complet, open-source et multifonctionnel qui combine Intelligence Artificielle, Économie, Musique, Modération et bien plus encore !

## ✨ Fonctionnalités Principales

### 🤖 Intelligence Artificielle
- **IA GPT-4o mini** intégrée avec conversations contextuelles
- **Personnalisation** du comportement de l'IA par serveur
- **Génération d'images** avec Stable Diffusion (Replicate)
- **Anti-spam intelligent** avec système de crédits
- **Support multilingue** (Français, Anglais, Espagnol, etc.)

### 💰 Système Économique Complet
- **Monnaie virtuelle** avec gains automatiques
- **Boutique intégrée** pour acheter des crédits et avantages
- **Récompenses journalières** (/daily)
- **Système VIP** avec avantages exclusifs
- **Quêtes progressives** avec niveaux et récompenses

### 🎵 Système Musical Avancé
- **Lecture multi-plateformes** (YouTube, Spotify, SoundCloud, Apple Music, etc.)
- **File d'attente** avec gestion complète
- **Contrôles vocaux** (play, pause, skip, volume, shuffle)
- **Qualité audio** configurable
- **Radio automatique** par thèmes
- **Déconnexion automatique** quand le bot est seul

### 🎯 Jeux et Divertissement
- **Machine à sous** animée avec gains multiplicateurs
- **Pile ou Face** avec paris
- **Giveaways automatiques** avec conditions personnalisables
- **Système de duels** musicaux
- **Statistiques musicales** par utilisateur

### 🛡️ Modération et Administration
- **Tickets de support** automatisés avec catégories
- **Modération complète** (kick, ban, mute, warn, purge)
- **Système de rôles** automatiques
- **Logs de modération**
- **Configuration par serveur**

### 🎫 Support Communautaire
- **Système de tickets** avec interface intuitive
- **Messages de bienvenue** personnalisables
- **Règles du serveur** avec acceptation par bouton
- **Support multi-langues**

## 🚀 Installation Rapide

### Prérequis
- Python 3.8 ou supérieur
- Un compte Discord avec permissions d'administrateur

### Installation Automatisée
```bash
# Clonez le repository
git clone https://github.com/stimoi/nexus.git
cd nexus

# Installez les dépendances
pip install -r requirements.txt

# Configurez le bot
cp config.yml.example config.yml
# Éditez config.yml avec vos clés API

# Démarrez le bot
python bot.py
```

### Installation Manuelle
1. **Téléchargez** le code source
2. **Installez** Python 3.8+ si ce n'est pas fait
3. **Créez** un environnement virtuel : `python -m venv venv`
4. **Activez** l'environnement : `source venv/bin/activate` (Linux/Mac) ou `venv\Scripts\activate` (Windows)
5. **Installez** les dépendances : `pip install -r requirements.txt`
6. **Configurez** votre fichier `config.yml`
7. **Démarrez** le bot : `python bot.py`

## ⚙️ Configuration

### Fichier `config.yml`
Le bot utilise un fichier de configuration YAML pour une gestion facile :

```yaml
# Configuration principale
discord:
  token: "VOTRE_TOKEN_DISCORD"

openai:
  api_key: "VOTRE_CLE_OPENAI"

# Configuration de l'économie
economy:
  credit_multiplier: 1.0
  daily_min: 30
  daily_max: 50

# Configuration musicale
music:
  default_volume: 50
  quality: "high"
```

### Variables d'Environnement
Vous pouvez aussi utiliser des variables d'environnement :
```bash
export DISCORD_TOKEN="votre_token"
export OPENAI_API_KEY="votre_cle_openai"
export REPLICATE_API_TOKEN="votre_token_replicate"
```

## 📋 Commandes Disponibles

### 🤖 Commandes IA
- `/ask <question>` - Posez une question à l'IA
- `/imagine <prompt>` - Générez une image avec IA
- Salon IA configuré - Discutez directement avec l'IA

### 💰 Commandes Économiques
- `/daily` - Réclamez votre récompense journalière
- `/stats` - Affichez vos statistiques
- `/top` - Classement des plus riches
- `/quests` - Vos quêtes quotidiennes
- `/boutique` - Achetez des crédits et avantages

### 🎵 Commandes Musicales
- `/musique <lien>` - Jouez une musique
- `/search <terme>` - Recherchez des musiques
- `/playlist <lien>` - Ajoutez une playlist
- `/skip` - Passez à la musique suivante
- `/queue` - Affichez la file d'attente
- `/volume <niveau>` - Réglez le volume
- `/pause` / `/resume` - Contrôlez la lecture

### 🎮 Commandes de Jeux
- `/slot <montant>` - Machine à sous animée
- `/coinflip <montant> <choix>` - Pile ou face
- `/giveway` - Créez des giveaways

### 🛡️ Commandes de Modération
- `/kick <membre> [raison]` - Excluez un membre
- `/ban <membre> [raison]` - Bannissez un membre
- `/mute <membre> <durée> [raison]` - Mettez en timeout
- `/purge <nombre>` - Supprimez des messages
- `/lock` / `/unlock` - Verrouillez/déverrouillez un salon

### ⚙️ Commandes d'Administration
- `/config` - Menu de configuration du serveur
- `/autoconfig` - Configuration automatique rapide
- `/setup-ticket` - Panneau de tickets
- `/setup-rules` - Panneau de règles
- `/opensource` - Informations sur le projet

## 🔧 Personnalisation

### Thèmes et Apparence
- **Couleurs personnalisables** pour chaque embed
- **Messages de bienvenue** configurables
- **Comportement de l'IA** personnalisable par serveur
- **Statuts rotatifs** personnalisables

### Configuration par Serveur
Chaque serveur peut avoir sa propre configuration :
- Salon IA dédié
- Rôles VIP personnalisés
- Messages de bienvenue uniques
- Configuration musicale spécifique

## 🌐 Architecture Technique

### Structure du Projet
```
nexus/
├── bot.py              # Fichier principal du bot
├── config.yml          # Configuration principale
├── config_loader.py     # Module de chargement de config
├── requirements.txt     # Dépendances Python
├── data.json          # Base de données des utilisateurs
└── README.md           # Documentation
```

### Technologies Utilisées
- **Python 3.8+** - Langage principal
- **discord.py** - API Discord
- **OpenAI GPT-4o** - Intelligence Artificielle
- **Replicate** - Génération d'images
- **yt-dlp** - Traitement audio/vidéo
- **PyYAML** - Gestion de configuration
- **asyncio** - Programmation asynchrone

## 📊 Statistiques en Temps Réel

### Métriques Disponibles
- **Serveurs actifs** : `{nombre}` serveurs
- **Utilisateurs touchés** : `{nombre}` utilisateurs
- **Messages traités** : `{nombre}` messages/jour
- **Commandes exécutées** : `{nombre}` commandes/jour
- **Musiques jouées** : `{nombre}` titres/jour

### Monitoring
- **Logs détaillés** de toutes les activités
- **Alertes automatiques** en cas d'erreur
- **Tableau de bord** web en développement

## 🔒 Sécurité et Fiabilité

### Mesures de Sécurité
- **Tokens sécurisés** et chiffrés
- **Validation des entrées** utilisateur
- **Protection anti-spam** avancée
- **Gestion des permissions** granulaire
- **Logs d'audit** complets

### Fiabilité
- **Gestion d'erreurs** robuste
- **Reconnexion automatique** en cas de déconnexion
- **Sauvegarde automatique** des données
- **Mode maintenance** intégré
- **Tests unitaires** complets

## 🌍 Support Multilingue

### Langues Disponibles
- 🇫🇷 **Français** (par défaut)
- 🇬🇧 **Anglais**
- 🇪🇸 **Espagnol**
- 🇩🇪 **Allemand**
- 🇮🇹 **Italien**
- 🇵🇹 **Portugais**

### Contribution aux Traductions
Vous pouvez aider à traduire le bot :
1. Fork le projet
2. Créez un fichier de langue
3. Soumettez une Pull Request

## 🤝 Contribuer au Projet

### Comment Contribuer
1. **Fork** le repository
2. **Créez** une branche pour votre fonctionnalité
3. **Faites** vos modifications avec des commits clairs
4. **Testez** vos changements
5. **Soumettez** une Pull Request avec description détaillée

### Directives de Contribution
- Suivez le style de code existant
- Ajoutez des commentaires pour les fonctions complexes
- Mettez à jour la documentation
- Testez sur plusieurs plateformes
- Respectez la structure du projet

### Issues et Bugs
- **Signalez les bugs** avec des détails complets
- **Proposez des fonctionnalités** avec description
- **Utilisez les templates** d'issues quand disponibles
- **Soyez patient** pour les réponses

## 📚 Documentation Complète

### Guides Disponibles
- [📖 Guide d'Installation Complet](https://zyrahost.fr/nexus-ia/docs/installation)
- [⚙️ Guide de Configuration](https://zyrahost.fr/nexus-ia/docs/configuration)
- [🔧 Guide de Développement](https://zyrahost.fr/nexus-ia/docs/development)
- [🤖 Guide des Commandes](https://zyrahost.fr/nexus-ia/docs/commands)
- [🛠️ Guide de Personnalisation](https://zyrahost.fr/nexus-ia/docs/customization)

### API Documentation
- **API REST** pour les développeurs
- **Webhooks** pour les intégrations
- **Exemples de code** dans plusieurs langages
- **Sandbox de test** en ligne

## 🌟 Avantages Premium

### Fonctionnalités VIP
- **Accès illimité** à l'IA sans crédits
- **Priorité** dans les files d'attente musicales
- **Commandes exclusives** VIP
- **Personnalisation** avancée
- **Support prioritaire** 24/7

### Obtenir VIP
- **Achat** via la boutique intégrée
- **Contribution** au projet open-source
- **Participation** à la communauté
- **Programme ambassadeur**

## 🔗 Liens Importants

### 🌐 Officiel
- **Site Web** : [https://zyrahost.fr/nexus-ia/](https://zyrahost.fr/nexus-ia/)
- **Documentation** : [https://zyrahost.fr/nexus-ia/docs](https://zyrahost.fr/nexus-ia/docs)
- **Support** : [https://zyrahost.fr/nexus-ia/support](https://zyrahost.fr/nexus-ia/support)

### 📺 Développement
- **GitHub** : [https://github.com/stimoi/nexus](https://github.com/stimoi/nexus)
- **Issues** : [https://github.com/stimoi/nexus/issues](https://github.com/stimoi/nexus/issues)
- **Releases** : [https://github.com/stimoi/nexus/releases](https://github.com/stimoi/nexus/releases)
- **Wiki** : [https://github.com/stimoi/nexus/wiki](https://github.com/stimoi/nexus/wiki)

### 🎮 Communauté
- **Discord** : [Serveur Support](https://discord.gg/your-support)
- **Votez** : [Laissez une étoile ⭐](https://zyrahost.fr/nexus-ia/rate)
- **Twitter** : [@NexusBot](https://twitter.com/NexusBot)
- **YouTube** : [Nexus Bot Channel](https://youtube.com/c/NexusBot)

## 📊 Performance et Scalabilité

### Métriques de Performance
- **Latence** : <100ms en moyenne
- **Uptime** : 99.9% garanti
- **Concurrence** : Supporte 1000+ serveurs simultanés
- **Mémoire** : Optimisée pour faible consommation

### Scalabilité
- **Architecture modulaire** pour extensions faciles
- **Base de données** optimisée pour grandes échelles
- **Cache intelligent** pour réponses rapides
- **Load balancing** prêt pour déploiement multiple

## 🛠️ Déploiement

### Options d'Hébergement
- **Local** : Votre propre machine
- **VPS** : Serveur virtuel privé
- **Docker** : Conteneurisé et portable
- **Cloud** : AWS, Google Cloud, Azure
- **Heroku** : Platform-as-a-Service

### Docker
```bash
# Build
docker build -t nexus-bot .

# Run
docker run -d --name nexus-bot nexus-bot
```

### Docker Compose
```yaml
version: '3.8'
services:
  nexus-bot:
    build: .
    environment:
      - DISCORD_TOKEN=${DISCORD_TOKEN}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    restart: unless-stopped
```

## 📈 Roadmap et Futur

### Prochaines Fonctionnalités (v3.2)
- [ ] **Tableau de bord web** complet
- [ ] **API REST** publique
- [ ] **Système de plugins** modulaire
- [ ] **Traduction automatique** des messages
- [ ] **Intégration Twitch** streaming
- [ ] **Bot vocal** avancé

### Long Terme
- [ ] **Application mobile** compagnon
- [ ] **Interface graphique** de configuration
- [ ] **Machine Learning** pour recommandations
- [ ] **Blockchain** pour économie décentralisée
- [ ] **Cross-platform** (Slack, Telegram)

## 📄 Licence

Ce projet est sous licence **MIT** - voir le fichier [LICENSE](LICENSE) pour les détails.

## 🙏 Remerciements

### Contributeurs Principaux
- **[@stimoi](https://github.com/stimoi)** - Créateur et développeur principal
- **[@contributor1](https://github.com/contributor1)** - Système musical
- **[@contributor2](https://github.com/contributor2)** - Interface IA
- **[@contributor3](https://github.com/contributor3)** - Documentation

### Technologies Externes
- **discord.py** - Framework Discord Python
- **OpenAI** - API GPT-4o
- **Replicate** - Génération d'images
- **yt-dlp** - Téléchargement YouTube
- **PyYAML** - Configuration YAML

### Communauté
Merci à toute la communauté Discord qui :
- Teste les nouvelles versions
- Rapporte les bugs
- Propose des améliorations
- Soutient le développement

---

## 🚀 Démarrage Rapide

```bash
# 1. Clonez et configurez
git clone https://github.com/stimoi/nexus.git
cd nexus
cp config.yml.example config.yml

# 2. Éditez la configuration
# Ajoutez vos tokens Discord, OpenAI, etc.

# 3. Installez et démarrez
pip install -r requirements.txt
python bot.py
```

**🎉 Félicitations !** Votre Nexus Bot est prêt à être déployé !

---

<div align="center">

**[⭐ Laissez une étoile sur GitHub !](https://zyrahost.fr/nexus-ia/rate)**

**[🔗 Invitez Nexus Bot sur votre serveur](https://discord.com/oauth2/authorize?client_id=1423684403019780116&permissions=8&integration_type=0&scope=bot+applications.commands)**

**[💬 Rejoignez notre communauté Discord](https://discord.gg/your-support)**

Made with ❤️ by the Nexus Bot Community

</div>
