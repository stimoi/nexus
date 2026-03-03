import discord
from discord.ext import commands, tasks
from openai import OpenAI
import random
import time
import json
import os
import asyncio
from discord import ui
import datetime
from discord import app_commands
from discord.app_commands import checks
import replicate
import inspect
import shutil
from typing import Optional, Union

import re
import urllib.parse
import requests
import yt_dlp
from yt_dlp import *
from discord import FFmpegPCMAudio
from discord import PCMVolumeTransformer
import pytube
from pytube import YouTube


def _require_env(var_name: str) -> str:
    """Retrieve a required environment variable or raise a runtime error."""
    value = os.getenv(var_name)
    if not value:
        raise RuntimeError(
            f"La variable d'environnement '{var_name}' est requise mais n'est pas définie."
        )
    return value


# ==================================
# 🔑 CONFIGURATION CLÉS (À REMPLACER)
# ==================================
IMAGINE_MAINTENANCE = False
SUPPORT_SERVER_ID = 1430518750397988967 # L'ID DE VOTRE SERVEUR DE SUPPORT
TICKET_CATEGORY_ID = 0 # variable innutile
IA_COMPORTEMENT = """Tu es Nexus, une IA Discord avancée avec des capacités de gestion de serveur.

CAPACITÉS SPÉCIALES:
- Tu peux créer des salons textuels avec des permissions personnalisées
- Tu peux créer des rôles avec des noms et couleurs personnalisés
- Tu es dans Discord et tu interagis avec les membres du serveur

COMMENT CRÉER:
- Pour créer un salon: cette feature est encore en dévoloppement et ne marche pas encore mais dis : "crée un salon nommé [nom]" ou "crée-moi un salon [nom]"
- Pour créer un rôle: cette feature est encore en dévoloppement et ne marche pas encore mais dis : "crée un rôle nommé [nom]" ou "crée-moi un rôle [nom]"

EXEMPLES:
- "crée un salon nommé discussions"
- "crée un rôle nommé VIP"
- "fait moi un salon appelé général"

IMPORTANT: Quand tu détectes une demande de création, utilise les fonctions internes du bot. Sois proactif et propose des créations quand c'est pertinent.

Sois utile, amical et aide les utilisateurs à gérer leur serveur Discord."""
INVITE_URL = "VOTRE INVITE POUR LE BOT"
OWNER_ID = 1139156246965002310  # VOTRE UTILISATEUR ID
DISCORD_TOKEN = "VOTRE TOKEN DISCORD"
OPENAI_API_KEY = "VOTRE API CHATGPT"
EVENT_MODE_ENABLED = False # True pour IA Illimitée pour TOUS
CREDIT_BOOST_MULTIPLIER = 1 # Multiplicateur de crédits (Ex: 2 pour doubler les récompenses)

# ==================================
# 🎵 SYSTÈME DE MUSIQUE AUTOMATIQUE
# ==================================
music_channels = {}  # Variables globales pour la musique
voice_clients = {}
music_queues = {}
now_playing = {}
music_paused = {}  # Pour suivre l'état pause/reprise
music_volume = {}  # Pour le contrôle du volume
vote_skip_sessions = {}  # Pour les votes de skip
FFMPEG_OPTIONS = {'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5', 'options': '-vn'}
YDL_OPTIONS = {'format': 'bestaudio/best', 'noplaylist': True, 'quiet': True, 'no_warnings': True}

# Fichier de sauvegarde
DATA_FILE = "data.json"

# Anti-spam IA
LIMIT = 3
PERIOD = 60 # 3 messages max par utilisateur toutes les 60 secondes pour l'IA (désactivé si priorité)
user_message_log = {}

# ==================================
# FONCTION DE GESTION DES QUÊTES (NOUVEAU)
# ==================================

# Quêtes possibles
POSSIBLE_QUESTS = [
    {
        "name": "Parler avec l'IA",
        "description": "Utilise le salon IA pour envoyer 5 messages.",
        "type": "ia_messages", # Le compteur doit s'incrémenter ailleurs (dans on_message)
        "target": 5,
        "reward_money": 250
    },
    {
        "name": "Réclamer le Daily",
        "description": "Réclame ta récompense journalière avec /daily.",
        "type": "econ_action_daily", # Le compteur est incrémenté dans /daily
        "target": 1,
        "reward_money": 100
    }
]

QUEST_OPTIONS = [
    # Clés pour la logique on_message
    {"type": "messages", "goal": 10, "reward": 50, "description": "Envoyer 10 messages dans n'importe quel canal.", "icon": "💬"},
    {"type": "ai_usage", "goal": 3, "reward": 75, "description": "Utiliser l'IA (salon IA ou slash command) 3 fois.", "icon": "🤖"},
    # Mots-clés pour la logique de quête
    {"type": "keyword", "goal": 5, "reward": 60, "description": "Dire le mot 'Nexus' 5 fois.", "icon": "🔑", "keyword": ["Nexus"]}, 
    {"type": "econ_action_daily", "goal": 1, "reward": 50, "description": "Récupérer votre argent quotidien avec `/daily`.", "icon": "🪙"}, 
    # Autres options de quêtes ici
]

QUEST_COUNTER_DEFAULTS = {
    "ai_usage_count": 0,
    "econ_action_daily": 0,
    "econ_action_top": 0,
    "ia_messages": 0,
    "image_gen_count": 0,
    "invites_count": 0,
    "messages": 0,
    "keyword": 0
}

def reset_and_start_new_quest(user_id):
    """Réinitialise les compteurs de quête et attribue une nouvelle quête aléatoire."""
    global data
    user_id_str = str(user_id)
    ensure_user(user_id_str)
    
    # 1. Choisir une nouvelle quête aléatoire
    new_quest = random.choice(POSSIBLE_QUESTS)
    
    # Mettre à jour les données
    data[user_id_str]['current_quest'] = new_quest
    data[user_id_str]['quest_start_time'] = time.time()
    
    # Réinitialiser le compteur
    # Réinitialiser uniquement le compteur requis pour la nouvelle quête
    # pour éviter de perdre la progression
    quest_type_to_reset = new_quest.get('type')
    if 'quest_counters' not in data[user_id_str]:
        data[user_id_str]['quest_counters'] = {}
        
    data[user_id_str]['quest_counters'][quest_type_to_reset] = 0
    
    # Sauvegarder
    save_data()

DAILY_QUEST_TIERS = {
    # --- NIVEAU 1 : FACILE (Seuil pour passer au Tier 2 : 5 Quêtes Terminées) ---
    "TIER_1": [
        {
            "description": "Discute 15 fois dans un salon non-IA.",
            "type": "MESSAGE_COUNT",
            "target_value": 15,
            "reward": 80,
            "alias": "chat_facile"
        },
        {
            "description": "Utilise le mot 'bot' ou 'IA' 3 fois dans un salon non-IA.",
            "type": "KEYWORD",
            "target_value": 3,
            "reward": 70,
            "alias": "mot_base",
            "keyword": ["bot", "ia"]
        },
        {
            "description": "Récupère ta récompense quotidienne (,daily).",
            "type": "ECON_ACTION_DAILY", # Nouveau type
            "target_value": 1,
            "reward": 100,
            "alias": "daily_action"
        },
        {
            "description": "Consulte le classement de richesse (,top).",
            "type": "ECON_ACTION_TOP", # Nouveau type
            "target_value": 1,
            "reward": 60,
            "alias": "top_action"
        },
        {
            "description": "Discute 2 fois avec l'IA dans le salon dédié.",
            "type": "AI_USAGE", # Nouveau type
            "target_value": 2,
            "reward": 90,
            "alias": "ai_talk_facile"
        }
    ],

    # --- NIVEAU 2 : MOYEN (Seuil pour passer au Tier 3 : 15 Quêtes Terminées) ---
    "TIER_2": [
        {
            "description": "Discute 40 fois dans un salon non-IA.",
            "type": "MESSAGE_COUNT",
            "target_value": 40,
            "reward": 180,
            "alias": "chat_moyen"
        },
        {
            "description": "Utilise le mot 'économie' 8 fois dans un salon non-IA.",
            "type": "KEYWORD",
            "target_value": 8,
            "reward": 170,
            "alias": "mot_eco",
            "keyword": ["économie", "economie"]
        },
        {
            "description": "Discute 5 fois avec l'IA dans le salon dédié.",
            "type": "AI_USAGE", 
            "target_value": 5,
            "reward": 200,
            "alias": "ai_talk_moyen"
        },
        {
            "description": "Consulte le classement de richesse (,top).",
            "type": "ECON_ACTION_TOP",
            "target_value": 1,
            "reward": 150,
            "alias": "top_action_moyen"
        }
    ],

    # --- NIVEAU 3 : DIFFICILE (Quêtes de fin de chaîne) ---
    "TIER_3": [
        {
            "description": "Discute 75 fois dans un salon non-IA.",
            "type": "MESSAGE_COUNT",
            "target_value": 75,
            "reward": 350,
            "bonus_credits": 1, 
            "alias": "chat_difficile"
        },
        {
            "description": "Utilise le mot 'crédit' ou 'priorité' 15 fois dans un salon non-IA.",
            "type": "KEYWORD",
            "target_value": 15,
            "reward": 300,
            "bonus_credits": 1,
            "alias": "mot_premium",
            "keyword": ["crédit", "credit", "priorité", "priorite"]
        },
        {
            "description": "Utilise un total de 10 crédits IA dans le salon dédié.",
            "type": "AI_USAGE", 
            "target_value": 10,
            "reward": 500,
            "bonus_credits": 2,
            "alias": "ai_usage_difficile"
        }
    ]
}

# --- NOUVELLES CONSTANTES DE PROGRESSION ---
TIER_1_QUESTS_REQUIRED = 5
TIER_2_QUESTS_REQUIRED = 15
MAX_TIER = 3

# ==================================
# 💾 FONCTIONS DE SAUVEGARDE
# ==================================

def get_current_day_of_year():
    """Retourne le jour de l'année (1 à 366) pour vérifier le reset quotidien, basé sur UTC."""
    # Fuseau horaire UTC pour la cohérence
    return datetime.datetime.now(datetime.timezone.utc).timetuple().tm_yday

def load_data():
    """Charge les données du fichier JSON."""
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                timestamp = int(time.time())
                backup_path = f"{DATA_FILE}.corrupted_{timestamp}"
                try:
                    shutil.copy2(DATA_FILE, backup_path)
                    print(f"⚠️ Erreur de décodage JSON. Copie du fichier corrompu vers '{backup_path}'.")
                except Exception as backup_error:
                    print(f"⚠️ Erreur de décodage JSON et impossibilité de sauvegarder la copie ({backup_error}).")
                return {"config": {}}
    return {"config": {}}

def save_data():
    """Sauvegarde les données dans le fichier JSON."""
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

# ==================================
# 🎵 FONCTIONS UTILITAIRES MUSIQUE
# ==================================
def is_music_link(message):
    """Vérifie si le message contient un lien de musique (YouTube, Spotify, etc.)"""
    music_patterns = [
        # YouTube
        r'https?://(?:www\.)?youtube\.com/watch\?v=[\w-]+(?:&[\w-]+=[\w-]*)*',
        r'https?://youtu\.be/[\w-]+(?:\?[\w-]+=[\w-]*)*',
        r'https?://(?:www\.)?youtube\.com/embed/[\w-]+',
        r'https?://(?:www\.)?youtube\.com/shorts/[\w-]+',
        # Spotify
        r'https?://(?:www\.)?spotify\.com/track/[\w-]+(?:\?[\w-]+=[\w-]*)*',
        r'https?://(?:www\.)?spotify\.com/album/[\w-]+(?:\?[\w-]+=[\w-]*)*',
        r'https?://(?:www\.)?spotify\.com/playlist/[\w-]+(?:\?[\w-]+=[\w-]*)*',
        # SoundCloud
        r'https?://(?:www\.)?soundcloud\.com/[\w-]+/[\w-]+(?:\?[\w-]+=[\w-]*)*',
        # Apple Music
        r'https?://(?:www\.)?music\.apple\.com/[\w-]+/[\w-]+/[\w-]+(?:\?[\w-]+=[\w-]*)*',
        r'https?://(?:www\.)?itunes\.apple\.com/[\w-]+/[\w-]+/[\w-]+(?:\?[\w-]+=[\w-]*)*',
        # Deezer
        r'https?://(?:www\.)?deezer\.com/(?:[\w-]+/)?track/[\w-]+',
        r'https?://(?:www\.)?deezer\.com/(?:[\w-]+/)?album/[\w-]+',
        # Tidal patterns
        r'https?://(?:www\.)?tidal\.com/browse/track/[\w-]+',
        r'https?://(?:www\.)?tidal\.com/browse/album/[\w-]+',
        # Bandcamp
        r'https?://[\w-]+\.bandcamp\.com/track/[\w-]+',
        r'https?://[\w-]+\.bandcamp\.com/album/[\w-]+',
        # Mixcloud
        r'https?://(?:www\.)?mixcloud\.com/[\w-]+/[\w-]+(?:\?[\w-]+=[\w-]*)*',
        # Twitch
        r'https?://(?:www\.)?twitch\.tv/[\w-]+(?:/clip/[\w-]+)?',
        # Vimeo patterns
        r'https?://(?:www\.)?vimeo\.com/[\d]+'
    ]
    return any(re.search(pattern, message, re.IGNORECASE) for pattern in music_patterns)

def extract_music_url(message):
    """Extrait le premier lien de musique trouvé dans le message"""
    music_patterns = [
        # YouTube
        r'https?://(?:www\.)?youtube\.com/watch\?v=[\w-]+(?:&[\w-]+=[\w-]*)*',
        r'https?://youtu\.be/[\w-]+(?:\?[\w-]+=[\w-]*)*',
        r'https?://(?:www\.)?youtube\.com/embed/[\w-]+',
        r'https?://(?:www\.)?youtube\.com/shorts/[\w-]+',
        # Spotify
        r'https?://(?:www\.)?spotify\.com/track/[\w-]+(?:\?[\w-]+=[\w-]*)*',
        r'https?://(?:www\.)?spotify\.com/album/[\w-]+(?:\?[\w-]+=[\w-]*)*',
        r'https?://(?:www\.)?spotify\.com/playlist/[\w-]+(?:\?[\w-]+=[\w-]*)*',
        # SoundCloud
        r'https?://(?:www\.)?soundcloud\.com/[\w-]+/[\w-]+(?:\?[\w-]+=[\w-]*)*',
        # Apple Music
        r'https?://(?:www\.)?music\.apple\.com/[\w-]+/[\w-]+/[\w-]+(?:\?[\w-]+=[\w-]*)*',
        r'https?://(?:www\.)?itunes\.apple\.com/[\w-]+/[\w-]+/[\w-]+(?:\?[\w-]+=[\w-]*)*',
        # Deezer
        r'https?://(?:www\.)?deezer\.com/(?:[\w-]+/)?track/[\w-]+',
        r'https?://(?:www\.)?deezer\.com/(?:[\w-]+/)?album/[\w-]+',
        # Tidal patterns
        r'https?://(?:www\.)?tidal\.com/browse/track/[\w-]+',
        r'https?://(?:www\.)?tidal\.com/browse/album/[\w-]+',
        # Bandcamp
        r'https?://[\w-]+\.bandcamp\.com/track/[\w-]+',
        r'https?://[\w-]+\.bandcamp\.com/album/[\w-]+',
        # Mixcloud
        r'https?://(?:www\.)?mixcloud\.com/[\w-]+/[\w-]+(?:\?[\w-]+=[\w-]*)*',
        # Twitch
        r'https?://(?:www\.)?twitch\.tv/[\w-]+(?:/clip/[\w-]+)?',
        # Vimeo patterns
        r'https?://(?:www\.)?vimeo\.com/[\d]+'
    ]
    
    for pattern in music_patterns:
        match = re.search(pattern, message, re.IGNORECASE)
        if match:
            return match.group(0)
    return None

def extract_video_info(url):
    """Extrait les informations d'une vidéo YouTube"""
    try:
        with YoutubeDL(YDL_OPTIONS) as ydl:
            info = ydl.extract_info(url, download=False)
            return {
                'title': info.get('title', 'Titre inconnu'),
                'url': url,
                'duration': info.get('duration', 0),
                'uploader': info.get('uploader', 'Artiste inconnu'),
                'thumbnail': info.get('thumbnail', '')
            }
    except Exception as e:
        print(f"Erreur extraction vidéo: {e}")
        return None

async def play_music(guild_id, voice_client, song_info):
    """Joue une musique dans le salon vocal"""
    try:
        with YoutubeDL(YDL_OPTIONS) as ydl:
            info = ydl.extract_info(song_info['url'], download=False)
            url = info['formats'][0]['url']
            
            source = discord.FFmpegPCMAudio(url, **FFMPEG_OPTIONS)
            voice_client.play(source, after=lambda e: asyncio.run_coroutine_threadsafe(play_next_song(guild_id), bot.loop))
            
            now_playing[guild_id] = song_info
            
            # Changer le nom du bot
            try:
                guild = bot.get_guild(guild_id)
                if guild:
                    # Limiter à 32 caractères
                    song_name = f"{song_info['title']} - {song_info['uploader']}"
                    if len(song_name) > 32:
                        # Garder l'artiste si possible
                        if len(song_info['uploader']) < 20:
                            song_name = f"{song_info['uploader']} - {song_info['title'][:32-len(song_info['uploader'])-3]}..."
                        else:
                            song_name = song_name[:29] + "..."
                    
                    await guild.me.edit(nick=song_name)
                    print(f"✅ Bot renommé en: {song_name}")
            except discord.Forbidden:
                print("⚠️ Pas la permission de changer le nom du bot")
            except Exception as e:
                print(f"⚠️ Erreur changement nom bot: {e}")
            
            return True
    except Exception as e:
        print(f"Erreur lecture musique: {e}")
        return False

async def play_next_song(guild_id):
    """Joue la musique suivante dans la file d'attente"""
    if guild_id in music_queues and music_queues[guild_id]:
        next_song = music_queues[guild_id].pop(0)
        voice_client = voice_clients.get(guild_id)
        
        if voice_client and not voice_client.is_playing():
            await play_music(guild_id, voice_client, next_song)
    else:
        # Plus de musique
        now_playing[guild_id] = None
        
        # Vérifier si le bot est seul
        await check_alone_in_voice(guild_id)

async def check_alone_in_voice(guild_id):
    """Vérifie si le bot est seul dans le salon vocal et quitte si nécessaire"""
    voice_client = voice_clients.get(guild_id)
    if not voice_client:
        return
        
    guild = bot.get_guild(guild_id)
    if not guild:
        return
        
    voice_channel = voice_client.channel
    if not voice_channel:
        return
    
    # Compter les membres (hors bots)
    human_members = [member for member in voice_channel.members if not member.bot]
    
    # Si seul ou vide
    if len(human_members) == 0:
        print(f"🤖 Bot seul dans le salon vocal {voice_channel.name}, déconnexion...")
        
        # Arrêter la musique
        if voice_client.is_playing() or voice_client.is_paused():
            voice_client.stop()
        
        # Quitter le salon
        await voice_client.disconnect()
        del voice_clients[guild_id]
        
        # Réinitialiser le nom
        try:
            await guild.me.edit(nick=None)
            print("✅ Nom du bot réinitialisé")
        except discord.Forbidden:
            print("⚠️ Pas la permission de réinitialiser le nom du bot")
        except Exception as e:
            print(f"⚠️ Erreur réinitialisation nom bot: {e}")
        
        # Vider la file
        if guild_id in music_queues:
            music_queues[guild_id] = []
        
        # Réinitialiser l'état
        now_playing[guild_id] = None
        music_paused[guild_id] = False

async def join_voice_channel(channel, author):
    """Rejoint le salon vocal de l'utilisateur"""
    try:
        if author.voice and author.voice.channel:
            voice_client = await author.voice.channel.connect()
            return voice_client
        else:
            return None
    except Exception as e:
        print(f"Erreur connexion vocal: {e}")
        return None

data = load_data()

# Configuration des données
if "config" not in data:
    data["config"] = {}

# ==================================
# 🤖 CONFIGURATION DU BOT
# ==================================
# Permissions pour lire les messages
intents = discord.Intents.default()
intents.message_content = True
intents.members = True 
bot = commands.Bot(command_prefix=",", intents=intents, help_command=None)

# Clients API
client = OpenAI(api_key=OPENAI_API_KEY)

# ==================================
# 🛠️ UTILITAIRES POUR LES QUÊTES
# ==================================
async def assign_daily_quest(user_id_str, channel):
    global data
    user_id = user_id_str
    ensure_user(user_id)
    
    current_quest = data[user_id]['quest']

    # Vérification Anti-Bot
    # Erreur 404 évitée (plus de fetch_user)
    if data[user_id].get('is_bot', False):
        return
        
    # Vérifier si utilisateur est bot
    user = None
    try:
        user = channel.guild.get_member(int(user_id))
        if user and user.bot:
            return
    except:
        # Continuer avec la data si membre non disponible
        pass

    # Logique d'assignation
    current_quest = data[user_id]['quest']
    
    # Si pas de quête active
    if not current_quest['active']:
        
        # Choisir une quête aléatoire
        new_quest_data = random.choice(QUEST_OPTIONS)
        
        # Assigner les valeurs
        data[user_id]['quest'] = {
            "active": True,
            "type": new_quest_data['type'],
            "progress": 0,
            "goal": new_quest_data['goal'],
            "reward": new_quest_data['reward'],
            "description": new_quest_data['description'],
            "icon": new_quest_data['icon']
        }
        
        # Réinitialiser les compteurs
        # Ceci est important pour les quêtes basées sur des actions (messages_count, slash_commands_count)
        if new_quest_data['type'] == 'messages':
            data[user_id]['messages_count'] = 0
        elif new_quest_data['type'] == 'slash_commands':
            data[user_id]['slash_commands_count'] = 0
        
        save_data()

        # Notification
        
        notification_embed = discord.Embed(
            title=f"{new_quest_data['icon']} Nouvelle Quête Quotidienne !",
            description=f"Ta nouvelle mission est : **{new_quest_data['description']}**\n\nRécompense : **{new_quest_data['reward']} crédits** 💰",
            color=discord.Color.gold()
        )
        
        # Tente d'envoyer en DM, sinon dans le canal
        if user:
            try:
                await user.send(embed=notification_embed)
                return # Si le DM réussit, on arrête ici
            except:
                # Si le DM échoue, on continue et on envoie dans le canal
                pass
                
        # Si DM échoue, envoyer dans le canal
        try:
            # Message éphémère si possible
            await channel.send(f"Hey <@{user_id}> ! Regarde tes DMs (ou utilise `/quests`) : une nouvelle mission t'attend !", delete_after=10)
        except:
            pass # Si le bot ne peut pas envoyer dans le canal, on ignore.
            
# Fin de la fonction

async def complete_quest_reward(user_id_str, quest, channel):
    """Gère la récompense d'une quête terminée et augmente le niveau."""
    user_data = data[user_id_str]
    reward = quest["reward"]
    bonus_credits = quest.get("bonus_credits", 0)
    
    # 1. Ajout des récompenses et incrémentation du compteur total
    user_data["money"] += reward
    if bonus_credits > 0:
        user_data["credits"] += bonus_credits
        
    user_data["quests"]["total_quests_completed"] += 1 # COMPTEUR DE PROGRESSION DU TIER

    # Vérification et augmentation du niveau
    current_total = user_data["quests"]["total_quests_completed"]
    current_tier = user_data["quests"]["current_tier"]
    
    new_tier = current_tier
    if current_tier == 1 and current_total >= TIER_1_QUESTS_REQUIRED:
        new_tier = 2
    elif current_tier == 2 and current_total >= TIER_2_QUESTS_REQUIRED:
        new_tier = 3
    
    # Message de progression
    if new_tier != current_tier:
        user_data["quests"]["current_tier"] = new_tier
        next_quest_msg = f"Préparez-vous : vous passez au **Niveau {new_tier}** !"
    elif current_tier < MAX_TIER:
        # Si on ne change pas de Tier, on continue dans le même niveau
        remaining = TIER_1_QUESTS_REQUIRED - current_total if current_tier == 1 else TIER_2_QUESTS_REQUIRED - current_total
        next_quest_msg = f"Prochaine Quête : Niveau {current_tier}. Vous devez en compléter {remaining} de plus pour le niveau supérieur."
    else:
        # Niveau maximum atteint pour aujourd'hui
        user_data["quests"]["completed_today"] = True
        next_quest_msg = "Vous avez complété **toutes les quêtes du jour** ! Revenez demain 👑."
        
    # Réinitialiser pour la prochaine quête
    user_data["quests"]["active_quest"] = None 
    save_data()

    # Message de félicitations en DM
    embed = discord.Embed(
        title="🎉 Quête Terminée !",
        description=f"Félicitations ! Vous avez terminé :\n**{quest['description']}**",
        color=discord.Color.gold()
    )
    embed.add_field(name="💰 Récompense", value=f"Vous gagnez **{reward}$**{f' + {bonus_credits} Crédit(s) IA 🧠' if bonus_credits > 0 else ''} !", inline=False)
    embed.add_field(name="✨ Prochain Objectif", value=next_quest_msg, inline=False)
    
    try:
        user = await bot.fetch_user(int(user_id_str))
    except Exception:
        user = None

    dm_sent = False
    if user:
        try:
            await user.send(embed=embed)
            dm_sent = True
        except discord.Forbidden:
            dm_sent = False
        except Exception:
            dm_sent = False

    if not dm_sent:
        # En dernier recours, message discret dans le salon où la quête a été complétée
        mention = user.mention if user else f"<@{user_id_str}>"
        await channel.send(mention, embed=embed)

    # Pas de nouvelle quête immédiate

async def grant_vip_access(user_id):
    """Accorde l'accès VIP à un utilisateur."""
    user_id_str = str(user_id)
    ensure_user(user_id_str)
    data[user_id_str]["has_priority"] = True
    save_data()

async def ensure_vip_state(user_id, member):
    """Vérifie et met à jour l'état VIP d'un utilisateur."""
    user_id_str = str(user_id)
    ensure_user(user_id_str)
    
    # Vérifier rôle VIP
    has_vip_role = any(role.id == VIP_ROLE_ID for role in member.roles) if VIP_ROLE_ID else False
    
    # Mettre à jour l'état VIP dans les données
    if has_vip_role and not data[user_id_str]["has_priority"]:
        data[user_id_str]["has_priority"] = True
        save_data()
    elif not has_vip_role and data[user_id_str]["has_priority"]:
        data[user_id_str]["has_priority"] = False
        save_data()
    
    return data[user_id_str]["has_priority"]

async def is_vip_server(ctx):
    """Vérifie si l'utilisateur qui exécute la commande est VIP sur le serveur support."""
    # (Le corps de cette fonction est absent du fichier fourni, mais nous laissons le décorateur.)
    # TODO: Implémenter vérification rôle VIP
    # Remplacement temporaire si VIP_ROLE_ID défini
    # On va la remplacer par une simple vérification de rôle temporaire si VIP_ROLE_ID est défini.
    if ctx.guild.id != SUPPORT_SERVER_ID:
        return False # Doit être exécuté sur le serveur support

    member = ctx.guild.get_member(ctx.author.id)
    if not member:
        return False

    return await ensure_vip_state(ctx.author.id, member)

def ensure_user(user_id):
    """
    Assure qu'un utilisateur possède toutes les clés nécessaires 
    dans le dictionnaire de données 'data' (initialisation et rétrocompatibilité).
    """
    user_id = str(user_id)
    default_quest_state = {
        "active": False,
        "type": "none",
        "progress": 0,
        "goal": 0,
        "reward": 0,
        "description": "Pas de quête active.",
        "icon": ""
    }
    default_quests_metadata = {
        "last_reset_day": 0,
        "current_tier": 1,
        "active_quest": None,
        "completed_today": False,
        "total_quests_completed": 0
    }
    
    # Vérification de l'existence de l'utilisateur
    if user_id not in data:
        # --- NOUVEAU PROFIL : Initialisation complète ---
        data[user_id] = {
            "credits": 10,  # Crédits de départ (pour IA)
            "money": 0,     # Monnaie virtuelle (pour la boutique)
            "image_tokens": 0,
            "level": 0,
            "xp": 0,
            "quest": default_quest_state.copy(),    # Quête quotidienne active
            "quest_counters": QUEST_COUNTER_DEFAULTS.copy(), # Compteurs pour les quêtes (ex: messages_count, ai_usage_count)
            "has_priority": False, # Par exemple, pour les VIP/Premium
            "quests": default_quests_metadata.copy(),
            "current_quest": None,
            "quest_start_time": 0,
            "tier_level": 1,
            "tier_xp": 0,
            "last_ai_response": "",
            "last_ai_prompt": ""
        }
        
    else:
        # --- PROFIL EXISTANT : Rétrocompatibilité ---
        user_data = data[user_id]
        
        # S'assurer que les clés essentielles existent avec une valeur par défaut si absentes
        user_data.setdefault("credits", 10) # 10 par défaut si absents (ajustez si besoin)
        user_data.setdefault("money", 0)
        user_data.setdefault("image_tokens", 0)
        user_data.setdefault("level", 0)
        user_data.setdefault("xp", 0)
        quest_state = user_data.get("quest")
        if not isinstance(quest_state, dict):
            quest_state = {}
        for key, value in default_quest_state.items():
            quest_state.setdefault(key, value)
        user_data["quest"] = quest_state
        quest_counters = user_data.get("quest_counters")
        if not isinstance(quest_counters, dict):
            quest_counters = {}
        for key, value in QUEST_COUNTER_DEFAULTS.items():
            quest_counters.setdefault(key, value)
        user_data["quest_counters"] = quest_counters
        user_data.setdefault("has_priority", False)
        quests_meta = user_data.get("quests")
        if not isinstance(quests_meta, dict):
            quests_meta = {}
        for key, value in default_quests_metadata.items():
            quests_meta.setdefault(key, value)
        user_data["quests"] = quests_meta
        user_data.setdefault("current_quest", None)
        user_data.setdefault("quest_start_time", 0)
        user_data.setdefault("tier_level", 1)
        user_data.setdefault("tier_xp", 0)
        user_data.setdefault("last_ai_response", "")
        user_data.setdefault("last_ai_prompt", "")

def set_guild_rules_role(guild_id: int, role_id: int):
    guild_key = str(guild_id)
    data.setdefault("config", {})
    guild_config = data["config"].setdefault(guild_key, {})
    guild_config["rules_role_id"] = role_id
    save_data()

def get_guild_rules_role_id(guild_id: int) -> Optional[int]:
    return data.get("config", {}).get(str(guild_id), {}).get("rules_role_id")

async def add_money(user_id):
    """Ajoute de l'argent virtuel à un utilisateur pour les messages dans les salons non-IA."""
    user_id_str = str(user_id)
    ensure_user(user_id_str)
    
    amount = random.randint(3, 5)
    data[user_id_str]["money"] += amount
    save_data()

async def send_owner_dm(*args, **kwargs):
    """Envoie un message ou un embed privé au propriétaire du bot (OWNER_ID)."""
    try:
        owner = await bot.fetch_user(OWNER_ID)
        if owner:
            await owner.send(*args, **kwargs) 
    except Exception as e:
        print(f"⚠️ Erreur lors de l'envoi d'un DM au propriétaire: {e}")
        
# ==================================
# 🎫 LOGIQUE DE CRÉATION DE TICKET (SANS CATÉGORIE)
# ==================================

async def create_ticket_logic(interaction: discord.Interaction, sujet: str):
    """Logique de création de ticket réutilisable, crée le salon à la racine du serveur."""
    
    guild = interaction.guild
    # guild_id = str(guild.id) # Non nécessaire sans configuration de catégorie

    # 1. Optionnel : Vérification anti-spam ou ticket déjà ouvert
    # (Non inclus pour rester simple, mais à considérer pour la production)

    # 2. Création du Salon de Ticket (À la racine du serveur)
    # Le nom du salon est créé à partir du nom d'utilisateur (avec max 100 caractères)
    ticket_name = f"ticket-{interaction.user.name.lower()}"[:100]
    
    # Définition des permissions (uniquement pour l'utilisateur, les admins et le bot)
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False), # Le rôle @everyone ne voit pas
        interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True), # L'utilisateur le voit
        guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True), # Le bot le voit
    }
    
    try:
        new_channel = await guild.create_text_channel(
            name=ticket_name,
            # category=... (Paramètre retiré pour création à la racine)
            overwrites=overwrites,
            reason=f"Ticket créé par {interaction.user.name}"
        )

        # 3. Message de Bienvenue dans le Ticket
        welcome_embed = discord.Embed(
            title=f"🎫 Ticket Support | {sujet}",
            description=f"Bienvenue, {interaction.user.mention} ! L'équipe de support va s'occuper de votre demande concernant : **{sujet}**.\n\n"
                        "Veuillez détailler votre problème ici. Un membre de l'équipe sera là sous peu.",
            color=discord.Color.blue()
        )
        
        await new_channel.send(f"{interaction.user.mention}", embed=welcome_embed)

        # 4. Confirmation à l'Utilisateur
        await interaction.followup.send(f"✅ Votre ticket a été créé : {new_channel.mention}", ephemeral=True)

    except discord.Forbidden:
        await interaction.followup.send("❌ Je n'ai pas les permissions nécessaires (`Gérer les Salons`) pour créer le ticket sur ce serveur.", ephemeral=True)
    except Exception as e:
        print(f"Erreur lors de la création du ticket : {e}")
        await interaction.followup.send("❌ Une erreur inconnue s'est produite lors de la création du ticket.", ephemeral=True)


# ==================================
# 🖥️ CLASSE BOUTON ET MODAL
# ==================================

class SubjectModal(ui.Modal, title="Ouvrir un Ticket de Support"):
    """Formulaire qui apparaît après le clic sur le bouton."""
    
    # Champ de texte pour le sujet
    subject_input = ui.TextInput(
        label="Quel est le sujet de votre demande ?",
        placeholder="Ex: Problème d'abonnement, Bug IA, Suggestion...",
        style=discord.TextStyle.short,
        max_length=100
    )

    async def on_submit(self, modal_interaction: discord.Interaction):
        # 1. Répondre au Modal : Déclenche l'opération longue (création du salon)
        await modal_interaction.response.defer(ephemeral=True) 
        
        # 2. Appeler la logique de création de ticket
        await create_ticket_logic(modal_interaction, str(self.subject_input))


class TicketButton(ui.View):
    """Vue persistante contenant le bouton d'ouverture de ticket."""
    def __init__(self):
        super().__init__(timeout=None) # Rend la vue persistante
        
    @ui.button(label="Ouvrir un Ticket", style=discord.ButtonStyle.blurple, custom_id="persistent_ticket_button", emoji="🎫")
    async def ticket_callback(self, interaction: discord.Interaction, button: ui.Button):
        
        # --- CORRECTION DE L'ERREUR 'send_modal' ---
        # 💡 Envoi du Modal comme réponse initiale à l'interaction du bouton.
        await interaction.response.send_modal(SubjectModal())


class RulesAcceptView(ui.View):
    """Vue persistante qui gère l'acceptation des règles et l'attribution du rôle."""

    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="✅ Accepter les règles", style=discord.ButtonStyle.green, custom_id="rules_accept_button")
    async def accept_rules(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.guild is None:
            return await interaction.response.send_message("❌ Cette action doit être réalisée sur un serveur.", ephemeral=True)

        role_id = get_guild_rules_role_id(interaction.guild.id)
        if not role_id:
            return await interaction.response.send_message("⚠️ Le rôle d'acceptation des règles n'est pas configuré.", ephemeral=True)

        role = interaction.guild.get_role(role_id)
        if role is None:
            return await interaction.response.send_message("⚠️ Le rôle configuré n'existe plus. Contactez un administrateur.", ephemeral=True)

        member = interaction.guild.get_member(interaction.user.id)
        if member is None:
            return await interaction.response.send_message("❌ Impossible de récupérer votre profil. Réessayez plus tard.", ephemeral=True)

        if role in member.roles:
            return await interaction.response.send_message("✅ Vous avez déjà accepté les règles.", ephemeral=True)

        try:
            await member.add_roles(role, reason="Acceptation des règles via le bouton d'adhésion")
            await interaction.response.send_message("🎉 Merci ! Vous avez accepté les règles et obtenu l'accès au serveur.", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("❌ Je n'ai pas les permissions nécessaires pour vous attribuer ce rôle.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Une erreur est survenue lors de l'attribution du rôle : {e}", ephemeral=True)


# ==================================
# ⚙️ COMMANDE SLASH /TICKET-PANEL (ADMIN)
# ==================================

@bot.tree.command(name="ticket-panel", description="Affiche le panneau de support avec le bouton d'ouverture de ticket.")
@commands.has_permissions(administrator=True)
async def ticket_panel(interaction: discord.Interaction):
    
    embed = discord.Embed(
        title="Centre de Support - Créez votre Ticket",
        description="Cliquez sur le bouton ci-dessous pour ouvrir un ticket privé avec notre équipe de support. Un formulaire vous demandera le sujet de votre demande.",
        color=discord.Color.blue()
    )
    
    # Envoie l'embed avec la vue persistante (le bouton)
    await interaction.response.send_message(embed=embed, view=TicketButton())

@ticket_panel.error
async def ticket_panel_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, commands.MissingPermissions):
        await interaction.response.send_message("❌ Permission Refusée : Tu dois avoir la permission `Administrateur` pour créer le panneau de tickets.", ephemeral=True)
    else:
        await interaction.response.send_message(f"❌ Erreur lors de l'envoi du panneau : {error}", ephemeral=True)


# ==================================
# 📜 COMMANDE SLASH /SETUP-RULES (ADMIN)
# ==================================

@bot.tree.command(name="setup-rules", description="Configure un panneau d'acceptation des règles avec attribution de rôle.")
@checks.has_permissions(administrator=True)
async def setup_rules(interaction: discord.Interaction, role: discord.Role):
    guild = interaction.guild
    if guild is None:
        return await interaction.response.send_message("❌ Cette commande doit être utilisée sur un serveur.", ephemeral=True)

    set_guild_rules_role(guild.id, role.id)

    tos_summary = (
        "Bienvenue ! Avant de participer, merci de respecter les règles suivantes :\n\n"
        "• 🤝 Respect mutuel et aucune forme de harcèlement.\n"
        "• 🚫 Pas de contenu illégal, NSFW ou incitant à la haine.\n"
        "• 📵 Pas de spam, phishing ou distribution de logiciels malveillants.\n"
        "• 🔐 Protégez votre compte : ne partagez jamais vos identifiants.\n\n"
        "En acceptant, vous confirmez respecter ces règles ainsi que les [Conditions d'utilisation de Discord](https://discord.com/terms)."
    )

    embed = discord.Embed(
        title="📜 Règles du serveur",
        description=tos_summary,
        color=discord.Color.blue()
    )
    embed.set_footer(text="Cliquez sur le bouton pour accepter et obtenir l'accès complet.")

    await interaction.response.send_message(embed=embed, view=RulesAcceptView())


@setup_rules.error
async def setup_rules_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, checks.MissingPermissions):
        await interaction.response.send_message("❌ Seuls les administrateurs peuvent configurer les règles.", ephemeral=True)
    else:
        await interaction.response.send_message(f"❌ Erreur lors de la configuration des règles : {error}", ephemeral=True)


### B. Commande pour Fermer le Ticket
@bot.command(aliases=['cl'])
async def close(ctx):
    """
    Ferme et supprime le canal de ticket actuel.
    """
    # Vérification que la commande est utilisée dans le serveur de support
    if ctx.guild.id != SUPPORT_SERVER_ID:
        return 
        
    # Vérification que c'est un canal de ticket (en regardant le nom)
    if not ctx.channel.name.startswith("ticket-"):
        return await ctx.send("❌ Cette commande ne peut être utilisée que dans un canal de ticket.")
        
    # Vérification des permissions du staff (exemple: le rôle 'Administrateur')
    if not ctx.author.guild_permissions.manage_channels:
        return await ctx.send("❌ Vous devez avoir la permission de 'Gérer les canaux' pour fermer un ticket.")
        
    
    await ctx.send("⏳ Fermeture du ticket dans 5 secondes...")
    await discord.utils.sleep_until(discord.utils.utcnow() + datetime.timedelta(seconds=5))
    
    # Suppression du canal
    try:
        await ctx.channel.delete()
    except discord.Forbidden:
        await ctx.author.send(f"❌ Impossible de supprimer le canal {ctx.channel.name} car je n'ai pas les permissions.")
    except Exception as e:
        await ctx.author.send(f"❌ Erreur lors de la suppression du canal : {e}")
        

# ==================================
# 🧠 ÉVÉNEMENT ON_MESSAGE (Logique Principale)
# ==================================
# ==================================
# 🧠 IA, ÉCONOMIE & SYSTÈME DE CRÉDITS (on_message)
# ==================================

@bot.event
async def on_message(message):
    # 1. Empêche le bot de se répondre à lui-même
    if message.author.bot:
        return

    # 2. Si c'est un message privé (MP)
    if isinstance(message.channel, discord.DMChannel):
        await message.channel.send(
            "👋 Salut ! Si tu veux m’ajouter sur ton serveur, clique ici :\n"
            f"🔗 [ajouter le bot]({INVITE_URL})"
        )
        return

    # --- Logique pour les messages de SERVEUR ---
    
    # 3. Traitement des commandes à préfixe (,stats, ,config, etc.)
    await bot.process_commands(message)

    # 4. Logique de l'IA et de l'argent

    user_id = str(message.author.id)
    guild_id = str(message.guild.id)
    
    # Initialise les données de l'utilisateur s'il est nouveau
    ensure_user(user_id)
    user_data = data[user_id]
    
    # --- LOGIQUE DE QUÊTE QUOTIDIENNE ET PROGRESSIVE ---
    
    # Vérifie si le message actuel est une commande
    is_command = message.content.startswith(bot.command_prefix)
    
    # 1. Assignation de la quête quotidienne si nécessaire
    await assign_daily_quest(user_id, message.channel)

    # 2. Progression de la quête active
    quest = user_data.get("quest", {})
    if quest.get("active", False):  
        
        ai_channel_id = data.get("config", {}).get(guild_id, {}).get("ai_channel")
        progress_made = False

        # --- PROGRESSION VIA MESSAGE OU MOT-CLÉ (salons non-IA) ---
        if not is_command and message.channel.id != ai_channel_id:
            
            # Type MESSAGE_COUNT (messages)
            if quest["type"] == "messages": 
                user_data["messages_count"] = user_data.get("messages_count", 0) + 1
                quest["progress"] = user_data["messages_count"] 
                progress_made = True
                
            # Type KEYWORD
            elif quest["type"] == "keyword": 
                keywords = quest.get("keyword", [])
                if any(k.lower() in message.content.lower() for k in keywords):
                    quest["progress"] += 1
                    progress_made = True

        # 3. Vérification de la complétion pour TOUS les types
        if quest["progress"] >= quest["goal"]: 
            await complete_quest_reward(user_id, quest, message.channel)
            
        # 4. Sauvegarde si la quête a progressé
        elif progress_made:
            save_data()
    
    # --- LOGIQUE DE L'IA ET DE L'ARGENT ---
    
    ai_channel_id = data.get("config", {}).get(guild_id, {}).get("ai_channel")

    # B. Si le message est dans le salon IA configuré
    if message.channel.id == ai_channel_id:
        
        credits_key = "credits"  # Clé des crédits IA (alignée avec ensure_user et le stockage JSON)
        credit_deducted = False
        
        # VÉRIFICATION DU MODE ÉVÉNEMENT (NEXUS DAY)
        global EVENT_MODE_ENABLED
        
        # Vérification Pass Priorité IA
        if not user_data.get("has_priority", False):
            # Anti-spam (uniquement si l'utilisateur n'a PAS la priorité)
            now = time.time()
            user_message_log.setdefault(user_id, [])
            user_message_log[user_id] = [t for t in user_message_log[user_id] if now - t < PERIOD]
            
            # Anti-spam (limite)
            if len(user_message_log[user_id]) >= LIMIT:
                await message.channel.send("⏳ Tu envoies trop vite, attends un peu avant de reparler 😉")
                return

            user_message_log[user_id].append(now)

        # --- LOGIQUE DE CRÉDITS (Nexus Day) ---
        if not EVENT_MODE_ENABLED:
            # MODE NORMAL: Vérification et déduction des crédits
            
            # 💡 CORRECTION APPLIQUÉE : Utilisation de .get() pour gérer l'erreur Key Error
            if user_data.get(credits_key, 0) <= 0:
                await message.channel.send("❌ Tu n’as plus de crédits IA ! Utilise `/boutique` pour en acheter 🛒 ou attends le **Nexus Day** pour l'accès illimité !", delete_after=15)
                return

            # Déduction d’un crédit
            user_data[credits_key] = user_data.get(credits_key, 0) - 1 # Assure que la clé est créée si absente
            credit_deducted = True
        
        
        # ✅ AJOUT : Incrémentation du compteur de quête d'utilisation de l'IA
        user_data.setdefault("quest_counters", {})
        user_data["quest_counters"]["ai_usage_count"] = user_data["quest_counters"].get("ai_usage_count", 0) + 1

        save_data()

        # Envoi à l'API OpenAI
        try:
            messages_payload = [
                {"role": "system", "content": IA_COMPORTEMENT},
            ]

            last_prompt = user_data.get("last_ai_prompt")
            last_response = user_data.get("last_ai_response")
            if last_prompt and last_response:
                messages_payload.append({"role": "user", "content": last_prompt})
                messages_payload.append({"role": "assistant", "content": last_response})
            elif last_response:
                messages_payload.append({"role": "assistant", "content": last_response})

            messages_payload.append({"role": "user", "content": message.content})

            async with message.channel.typing():
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    max_tokens=300,
                    messages=messages_payload
                )

            reply = response.choices[0].message.content
            user_data["last_ai_prompt"] = message.content
            user_data["last_ai_response"] = reply
            save_data()
            await message.channel.send(reply)

        except Exception as e:
            print(f"⚠️ Erreur OpenAI pour l'utilisateur {message.author}: {e}")
            
            # Remboursement du crédit UNIQUEMENT si un crédit a été déduit (mode normal)
            if credit_deducted:
                user_data[credits_key] = user_data.get(credits_key, 0) + 1 # Remboursement sécurisé
                # REMBOURSEMENT COMPTEUR AUSSI
                user_data["quest_counters"]["ai_usage_count"] -= 1
            
            save_data()
            await message.channel.send("⚠️ Erreur lors de la génération de la réponse. Le crédit a été remboursé.")
            
    # C. Si le message n'est PAS dans le salon IA configuré, l'utilisateur gagne de l'argent.
    elif not is_command:
        # Gagne de l'argent pour le message
        await add_money(user_id)
        
# ==================================
# ÉVÉNEMENT ON_MEMBER_JOIN (Message de Bienvenue)
# ==================================
@bot.event
async def on_member_join(member):
    try:
        guild_id = str(member.guild.id)
        
        # Vérifier si la configuration de bienvenue existe pour ce serveur
        if guild_id in data and 'bienvenue' in data[guild_id]:
            config = data[guild_id]['bienvenue']
            salon = member.guild.get_channel(config['salon_id'])
            
            if not salon:
                return  # Le salon n'existe plus
                
            # Récupérer l'inviteur si possible
            inviter = None
            try:
                invites = await member.guild.invites()
                for invite in invites:
                    if invite.uses > (data.get('invite_uses', {}).get(str(invite.id), 0)):
                        inviter = invite.inviter
                        # Mettre à jour le compteur d'utilisations
                        if 'invite_uses' not in data:
                            data['invite_uses'] = {}
                        data['invite_uses'][str(invite.id)] = invite.uses
                        save_data()
                        break
            except Exception as e:
                print(f"Erreur lors de la récupération de l'invitation : {e}")
            
            # Remplacer les variables dans le message
            message = config['message']
            message = message.replace('%player%', member.mention)
            if inviter:
                message = message.replace('%inviter%', inviter.mention)
            else:
                message = message.replace('%inviter%', 'un inconnu')
            
            # Envoyer le message de bienvenue
            await salon.send(message)
            
            # Attribuer le rôle si spécifié
            role = member.guild.get_role(config['role_id'])
            if role:
                try:
                    await member.add_roles(role, reason="Rôle de bienvenue")
                except Exception as e:
                    print(f"Erreur lors de l'attribution du rôle : {e}")
                    
    except Exception as e:
        print(f"Erreur dans on_member_join : {e}")

# ==================================
# COMMANDE /setup-bienvenue (ADMIN ONLY)
# ==================================
@bot.tree.command(name="setup-bienvenue", description="Configure le message de bienvenue et le rôle à attribuer")
@commands.has_permissions(administrator=True)
async def setup_bienvenue(interaction: discord.Interaction, salon: discord.TextChannel, message: str, role: discord.Role):
    """
    Configure le message de bienvenue et le rôle à attribuer aux nouveaux membres.
    
    Variables spéciales :
    - %player% : sera remplacé par le pseudo du nouveau membre
    - %inviter% : sera remplacé par la personne qui a invité le membre (si détecté)
    """
    try:
        # Vérifier si la clé 'bienvenue' existe dans les données du serveur
        guild_id = str(interaction.guild.id)
        if guild_id not in data:
            data[guild_id] = {}
        
        if 'bienvenue' not in data[guild_id]:
            data[guild_id]['bienvenue'] = {}
        
        # Enregistrer la configuration
        data[guild_id]['bienvenue'] = {
            'salon_id': salon.id,
            'message': message,
            'role_id': role.id
        }
        
        save_data()
        
        embed = discord.Embed(
            title=" Configuration enregistrée",
            description=f"Le message de bienvenue a été configuré avec succès dans {salon.mention} !",
            color=discord.Color.green()
        )
        embed.add_field(name="Message", value=message, inline=False)
        embed.add_field(name="Rôle à attribuer", value=role.mention, inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
    except Exception as e:
        error_embed = discord.Embed(
            title=" Erreur",
            description=f"Une erreur est survenue : {str(e)}",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=error_embed, ephemeral=True)

@setup_bienvenue.error
async def setup_bienvenue_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, commands.MissingPermissions):
        await interaction.response.send_message(" Vous n'avez pas la permission d'utiliser cette commande.", ephemeral=True)
    else:
        error_embed = discord.Embed(
            title=" Erreur",
            description=f"Une erreur est survenue : {str(error)}",
            color=discord.Color.red()
        )
        if interaction.response.is_done():
            await interaction.followup.send(embed=error_embed, ephemeral=True)
        else:
            await interaction.response.send_message(embed=error_embed, ephemeral=True)

# ==================================
# ÉVÉNEMENT ON_GUILD_JOIN (Message de Bienvenue)
# ==================================
@bot.event
async def on_guild_join(guild):
    
    # 1. Tenter d'envoyer un message au propriétaire du SERVEUR (celui qui a ajouté le bot)
    owner = guild.owner
    if owner:
        try:
            await owner.send(f"Merci d'avoir ajouté **{bot.user.name}** à votre serveur ({guild.name}) ! Utilisez la commande `,autoconfig` pour commencer la configuration rapide. Pour toute aide : ,help")
        except discord.Forbidden:
            print(f"⚠️ Impossible d'envoyer un MP au propriétaire du serveur {owner.name} de {guild.name}.")
    
    # 2. Préparer et envoyer l'Embed de Bienvenue dans le salon public
    channel = next((c for c in guild.text_channels if c.permissions_for(guild.me).send_messages), None)

    if channel:
        embed = discord.Embed(
            title="👋 Merci de m'avoir ajouté !",
            description=f"Je suis **{bot.user.name}**, le bot Économie et Intelligence Artificielle.\n\n"
                        "Pour commencer la configuration rapide du salon IA et économie, tapez :\n"
                        "```\n,autoconfig\n```\n"
                        "Vous pouvez aussi utiliser `,config` pour une configuration manuelle.",
            color=discord.Color.blue()
        )
        
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        
        embed.add_field(
            name="🤖 Fonctionnalités Clés", 
            value="• IA (GPT-4o mini) par crédit\n• Économie et Daily\n• Quêtes Quotidiennes Progressives\n• Système de Tickets de Support", 
            inline=False
        )
        embed.set_footer(text=f"Propriétaire du serveur : {guild.owner.name}")
        
        try:
            await channel.send(embed=embed)
        except discord.Forbidden:
            print(f"❌ Erreur de permission dans {guild.name} pour envoyer le message de bienvenue public.")
            
    # 3. NOTIFICATION MP AU PROPRIÉTAIRE DU BOT (Vous)
    try:
        dev_owner = await bot.fetch_user(OWNER_ID)
        if dev_owner:
            
            invite_link = "Lien d'invitation non généré."
            try:
                # Cherche le premier canal où on peut créer une invitation
                target_channel = next((c for c in guild.text_channels if c.permissions_for(guild.me).create_instant_invite), None)
                if target_channel:
                    # Durée de 1 semaine = 604800 secondes
                    invite = await target_channel.create_invite(max_uses=1, max_age=604800, unique=True, reason="Lien d'invitation pour le propriétaire du bot (join).")
                    invite_link = invite.url
            except Exception as e:
                print(f"⚠️ Impossible de créer un lien d'invitation pour {guild.name}: {e}")
            
            # Envoi du message au développeur
            await dev_owner.send(
                f"🎉 **[Notification Bot]** 🎉\n"
                f"Mon bot a été ajouté à un **nouveau serveur** !\n\n"
                f"**Nom du serveur :** `{guild.name}` (ID: `{guild.id}`)\n"
                f"**Propriétaire :** `{guild.owner.name}` (ID: `{guild.owner.id}`)\n"
                f"**Membres :** `{guild.member_count}`\n\n"
                f"🔗 **Lien d'invitation (valable 1 semaine) :** {invite_link}"
            )
            print(f"✅ Notification MP envoyée à l'OWNER_ID ({dev_owner.name}) pour {guild.name}.")
            
    except Exception as e:
        print(f"❌ Erreur lors de l'envoi de la notification MP à l'OWNER_ID ({OWNER_ID}) : {e}")

    print(f"✅ J'ai rejoint le serveur : {guild.name} ({guild.id})")


# ==================================
# 💬 COMMANDES UTILITAIRES ET ÉCONOMIE
# ==================================

# ==================================
# ⚙️ CONFIGURATION DE LA MACHINE À SOUS (INCHANGÉE)
# ==================================
SLOT_SYMBOLS = ["💰", "🍒", "🍒", "🍋", "🍋", "🍋", "7️⃣", "7️⃣", "⭐"]
PAYOUTS = {
    "💰💰💰": 10,
    "7️⃣7️⃣7️⃣": 7,
    "🍒🍒🍒": 5,
    "🍋🍋🍋": 3,
    "💰💰": 2
}

# ==================================
# 🔄 FONCTION D'ANIMATION (NOUVEAU)
# ==================================
async def animate_slots(interaction: discord.Interaction, montant: int):
    """Simule l'animation des rouleaux de machine à sous."""
    
    # 3 étapes d'animation
    for i in range(1, 4):
        # Créer un tirage aléatoire pour l'animation
        temp_results = [random.choice(SLOT_SYMBOLS) for _ in range(3)]
        temp_result_str = " | ".join(temp_results)
        
        # Le titre et la description changent légèrement pour simuler le spin
        spin_embed = discord.Embed(
            title=f"🎰 Machine à Sous : {montant}$",
            description=f"**Tour n°{i}**... Faites vos jeux !",
            color=discord.Color.light_grey()
        )
        spin_embed.add_field(name="[ EN COURS ]", value=f"`{temp_result_str}`", inline=False)
        spin_embed.set_footer(text="La pièce atterrit...")

        if i == 1:
            # Pour le premier passage, on répond initialement
            await interaction.response.send_message(embed=spin_embed)
        else:
            # Pour les passages suivants, on modifie le message existant
            await interaction.edit_original_response(embed=spin_embed)
            
        # Délai pour l'effet visuel (il diminue pour un effet d'accélération)
        await asyncio.sleep(0.4 / i)


# ==================================
# 💬 COMMANDE /slot (MACHINE À SOUS) - MISE À JOUR
# ==================================
@bot.tree.command(name="slot", description="Jouez à la machine à sous avec un spin excitant !")
@app_commands.describe(
    montant="Le montant d'argent à parier (minimum 50$).",
)
async def slot_slash(interaction: discord.Interaction, montant: int):
    user_id = str(interaction.user.id)
    
    # 1. Préparation et Vérifications (Identique à la version précédente)
    ensure_user(user_id)
    user_data = data[user_id]
    current_money = user_data.get('money', 0)

    MIN_BET = 50
    if montant < MIN_BET:
        return await interaction.response.send_message(f"❌ **Mise Invalide :** Le montant minimum à parier est de **{MIN_BET}$**.", ephemeral=True)
    if montant > current_money:
        return await interaction.response.send_message(f"❌ **Fonds Insuffisants :** Vous n'avez que **{current_money}$**. Vous ne pouvez pas parier **{montant}$**.", ephemeral=True)
    
    # Déduire la mise AVANT l'animation
    user_data['money'] -= montant
    
    # 2. Lancement de l'Animation (NOUVEAU)
    await animate_slots(interaction, montant)
    
    # 3. Logique du jeu (après l'animation)
    
    # Choisir 3 symboles aléatoires pour le RÉSULTAT FINAL
    results = [random.choice(SLOT_SYMBOLS) for _ in range(3)]
    result_str = " | ".join(results)
    
    # 4. Calcul du gain (Identique à la version précédente)
    payout_multiplier = 0
    if results[0] == results[1] == results[2]:
        payout_multiplier = PAYOUTS.get(results[0] * 3, 0)
    elif results.count("💰") >= 2:
        payout_multiplier = PAYOUTS.get("💰💰", 0)

    # 5. Mise à jour des données et création de l'embed
    if payout_multiplier > 0:
        gain = montant * payout_multiplier
        benefice = gain - montant
        user_data['money'] += gain
        
        embed = discord.Embed(
            title="🎉 JACKPOT ! TRIPLE CHANCE !",
            description=f"**[{result_str}]**\n\n🎉 **VICTOIRE !** Vous remportez un multiplicateur de x{payout_multiplier}.",
            color=discord.Color.green()
        )
        embed.add_field(name="Gains nets", value=f"**+{benefice}$**", inline=True)
        # Mise à jour du compteur de quête
        user_data['quest_counters']['econ_action_daily'] = user_data['quest_counters'].get('econ_action_daily', 0) + 1
        
    else:
        # DÉFAITE
        perte = montant
        
        embed = discord.Embed(
            title="💔 Fin de la Chance",
            description=f"**[{result_str}]**\n\n💔 **DÉFAITE**... Mieux la prochaine fois.",
            color=discord.Color.red()
        )
        embed.add_field(name="Perte nette", value=f"-{perte}$", inline=True)
        
    # 6. Sauvegarde et Modification Finale de la Réponse
    save_data()
    
    embed.add_field(name="\u200b", value="\u200b", inline=False) 
    embed.add_field(name="💰 Solde Actuel", value=f"**{user_data['money']}$**", inline=False)
    embed.set_footer(text=f"Vous aviez misé {montant}$")
    
    # On utilise edit_original_response pour remplacer l'animation par le résultat final
    await interaction.edit_original_response(embed=embed)


# ==================================
# 💬 COMMANDE /coinflip (PILE OU FACE)
# ==================================
@bot.tree.command(name="coinflip", description="Pariez votre argent sur Pile ou Face. Doublez votre mise en cas de victoire !")
@app_commands.describe(
    montant="Le montant d'argent à parier (minimum 10$).",
    choix="Votre choix : 'pile' ou 'face'."
)
async def coinflip_slash(interaction: discord.Interaction, montant: int, choix: str):
    user_id = str(interaction.user.id)
    
    # 1. Préparation et normalisation des données
    ensure_user(user_id)
    user_data = data[user_id]
    current_money = user_data.get('money', 0)
    
    # Normalisation du choix de l'utilisateur
    choix = choix.lower()
    if choix.startswith('p'):
        choix = 'pile'
    elif choix.startswith('f'):
        choix = 'face'

    # 2. Vérifications
    if montant < 10:
        return await interaction.response.send_message(
            "❌ **Mise Invalide :** Le montant minimum à parier est de **10$**.", 
            ephemeral=True
        )
    
    if montant > current_money:
        return await interaction.response.send_message(
            f"❌ **Fonds Insuffisants :** Vous n'avez que **{current_money}$**. Vous ne pouvez pas parier **{montant}$**.", 
            ephemeral=True
        )
    
    if choix not in ['pile', 'face']:
        return await interaction.response.send_message(
            "❌ **Choix Invalide :** Votre choix doit être 'pile' ou 'face'.", 
            ephemeral=True
        )
    
    # 3. Logique du jeu
    
    # Déterminer le résultat aléatoire
    result = random.choice(['pile', 'face'])
    
    # Définition des emojis pour l'affichage
    PILE_EMOJI = "🟡"
    FACE_EMOJI = "🔵"
    result_emoji = PILE_EMOJI if result == 'pile' else FACE_EMOJI
    
    # Vérification du résultat
    if choix == result:
        # VICTOIRE
        gain = montant
        new_money = current_money + gain
        user_data['money'] = new_money
        
        embed = discord.Embed(
            title=f"🎉 VICTOIRE ! ({result.capitalize()})",
            description=f"La pièce a atterri sur **{result_emoji} {result.capitalize()}** !\nVous gagnez **{gain}$**.",
            color=discord.Color.green()
        )
        # Mise à jour du compteur de quête d'action quotidienne
        user_data['quest_counters']['econ_action_daily'] = user_data['quest_counters'].get('econ_action_daily', 0) + 1
        
    else:
        # DÉFAITE
        perte = montant
        new_money = current_money - perte
        user_data['money'] = new_money
        
        embed = discord.Embed(
            title=f"💔 DÉFAITE ! ({result.capitalize()})",
            description=f"La pièce a atterri sur **{result_emoji} {result.capitalize()}**...\nVous perdez **{perte}$**.",
            color=discord.Color.red()
        )
        
    # 4. Sauvegarde et Réponse
    save_data()
    
    embed.add_field(name="\u200b", value="\u200b", inline=False) # Ligne vide pour l'espacement
    embed.add_field(name="💰 Votre Solde", value=f"**{new_money}$**", inline=False)
    embed.set_footer(text=f"Vous aviez parié {montant}$ sur {choix.capitalize()}")
    
    await interaction.followup.send(embed=embed)


# --- Commande ,stats (MISE À JOUR) ---
@bot.command()
async def stats(ctx):
    ensure_user(ctx.author.id)
    user_data = data[str(ctx.author.id)]
    money = user_data["money"]
    credits = user_data["credits"]
    image_tokens = user_data["image_tokens"]
    has_priority = user_data["has_priority"]
    
    priority_status = "👑 ACTIF" if has_priority else "❌ Inactif"
    
    embed = discord.Embed(
        title=f"Statistiques de {ctx.author.display_name}",
        color=discord.Color.gold()
    )
    embed.add_field(name="💰 Argent Virtuel", value=f"**{money}$**", inline=True)
    embed.add_field(name="🧠 Crédits IA", value=f"**{credits}**", inline=True)
    embed.add_field(name="🖼️ Jetons Image", value=f"**{image_tokens}**", inline=True)
    """Réclame la récompense journalière (une fois toutes les 24 heures)."""
    user_id_str = str(interaction.user.id)
    ensure_user(user_id_str)
    user_data = data[user_id_str]
    
    COOLDOWN = 24 * 60 * 60 
    now = time.time()
    
    last_daily = user_data.get("last_daily", 0) 
    time_since = now - last_daily
    
    if time_since >= COOLDOWN:
        reward = random.randint(30, 50)
        
        user_data["money"] = user_data.get("money", 0) + reward
        user_data["last_daily"] = now
        
        # ✅ Incrémentation du compteur de quête daily
        user_data.setdefault("quest_counters", {})
        user_data["quest_counters"]["econ_action_daily"] += 1 

        save_data()
        
        embed = discord.Embed(
            title="💰 Récompense Journalière Réclamée !",
            description=f"Tu as gagné **{reward}$** !\nReviens dans 24h pour ta prochaine récompense.",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed)
    else:
        remaining_time = COOLDOWN - time_since
        hours = int(remaining_time // 3600)
        minutes = int((remaining_time % 3600) // 60)
        seconds = int(remaining_time % 60)
        
        time_left = f"{hours}h {minutes}min {seconds}s"
        
        embed = discord.Embed(
            title="⏰ Récompense Indisponible",
            description=f"Tu dois encore attendre **{time_left}** avant de pouvoir réclamer ta récompense journalière.",
            color=discord.Color.orange()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


# ==================================
# 💬 COMMANDE /quests (SLASH COMMAND) - FINAL
# ==================================
@bot.tree.command(name="quests", description="Affiche ta quête quotidienne et ta progression de niveau (Tier).")
async def quests_slash(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    
    ensure_user(user_id) 
    user_data = data[user_id] 
    
    # --- LOGIQUE DE VÉRIFICATION ET RÉINITIALISATION DE LA QUÊTE ---
    last_quest_start = user_data.get('quest_start_time', 0)
    quest_duration = 24 * 60 * 60 
    current_time = time.time()
    
    # Vérifie si la quête a expiré ou si aucune n'est active
    if current_time - last_quest_start >= quest_duration or not user_data.get('current_quest'):
        # 🚨 APPEL MAINTENANT VALIDE :
        reset_and_start_new_quest(user_id) 
        user_data = data[user_id] # Recharger les données après reset
        
    # --- AFFICHAGE ---
    current_quest = user_data['current_quest']
    current_tier_xp = user_data.get('tier_xp', 0)
    current_tier_level = user_data.get('tier_level', 1)

    embed = discord.Embed(
        title=f"🎯 Quêtes Quotidiennes & Niveau de Tier ({interaction.user.display_name})",
        color=discord.Color.from_rgb(255, 165, 0)
    )

    # ... (Affichage de la Quête) ...
    quest_name = current_quest.get('name', "Erreur de quête")
    quest_desc = current_quest.get('description', "Veuillez réessayer.")
    quest_type = current_quest.get('type', 'none')
    quest_target = current_quest.get('target', 0)
    quest_reward = current_quest.get('reward_money', 0)
    
    current_progress = user_data['quest_counters'].get(quest_type, 0)
    is_completed = current_progress >= quest_target
    
    status_icon = "✅ Terminé" if is_completed else "🔄 En cours"
    
    embed.add_field(name="📜 Quête du Jour", value=f"**{quest_name}**", inline=False)
    embed.add_field(name="Objectif", value=f"{current_progress}/{quest_target} - ({quest_desc})", inline=True)
    embed.add_field(name="Récompense", value=f"{quest_reward}$", inline=True)
    embed.add_field(name="Statut", value=status_icon, inline=True)

    # ... (Affichage du Tier Level) ...
    xp_to_next_level = current_tier_level * 500 
    
    embed.add_field(name="\u200b", value="\u200b", inline=False) 
    embed.add_field(name="⭐ Ton Niveau de Tier Actuel", value=f"**Tier {current_tier_level}**", inline=True)
    embed.add_field(name="Progression XP", value=f"{current_tier_xp}/{xp_to_next_level} XP", inline=True)

    embed.set_footer(text="Les quêtes se réinitialisent toutes les 24h. Le Tier XP est permanent.")

    await interaction.response.send_message(embed=embed)

# Suppression de l'ancienne commande ,quests
try:
    bot.remove_command('quests')
except:
    pass

# ---


# ==================================
# 🧠 COMMANDE SLASH /ASK (IA)
# ==================================
@bot.tree.command(name="ask", description="Pose une question à l'IA (GPT-4o-mini).")
@app_commands.describe(question="Votre question ou requête pour l'IA.")
async def ask_command(interaction: discord.Interaction, question: str):
    await interaction.response.defer(ephemeral=False)

    user_id = str(interaction.user.id)
    guild_id = str(interaction.guild_id)
    
    # --- 1. VÉRIFICATION DES CONDITIONS D'ACCÈS ---
    
    # 1.1 Statut Premium/VIP
    
    # ⭐ CORRECTION APPLIQUÉE ICI : Utilisation de la structure de données globale 'data' (JSON)
    # Vérifie si le serveur est Premium via la configuration enregistrée (si la clé existe, sinon False)
    is_guild_premium = data.get("config", {}).get(guild_id, {}).get("is_premium", False)
    
    # L'utilisateur a-t-il le rôle VIP ?
    guild_member = interaction.guild.get_member(interaction.user.id) if interaction.guild else None
    is_vip = await ensure_vip_state(interaction.user.id, guild_member)

    global EVENT_MODE_ENABLED
    
    has_unlimited_access = is_guild_premium or is_vip or EVENT_MODE_ENABLED
    
    # 1.2 Détermination si l'accès est illimité (Premium/VIP/Nexus Day)
    
    credits_key = "credits" # Clé des crédits IA (ajuster si vous utilisez "credits")
    credit_deducted = False

    if not has_unlimited_access:
        ensure_user(user_id)
        user_data = data[user_id]
        
        # 💡 Vérification sécurisée avec .get()
        if user_data.get(credits_key, 0) <= 0:
            embed = discord.Embed(
                title="❌ Accès Refusé - Crédits Épuisés",
                description="Tu n’as plus de crédits IA ! Utilise `/boutique` pour en acheter 🛒 ou attends le **Nexus Day** pour l'accès illimité !",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed)
            return

        # Déduction d’un crédit (Coût unique pour l'IA conversationnelle)
        user_data[credits_key] -= 1
        
        # Le crédit a été déduit, marquer pour le remboursement en cas d'erreur
        credit_deducted = True
    else:
        # ACCÈS ILLIMITÉ (Premium, VIP ou Nexus Day)
        credit_deducted = False

    # 1.3 Gestion de l'état de l'utilisateur (Sauvegarde avant l'appel API)
    ensure_user(user_id)
    
    # ✅ Incrémentation du compteur de quête d'utilisation de l'IA
    user_data = data[user_id]
    user_data.setdefault("quest_counters", {})
    user_data["quest_counters"]["ai_usage_count"] = user_data["quest_counters"].get("ai_usage_count", 0) + 1
    save_data()
    
    # --- 2. APPEL À L'API OPENAI ---
    
    try:
        # Envoi à l'API OpenAI
        messages_payload = [
            {"role": "system", "content": IA_COMPORTEMENT},
        ]

        last_prompt = user_data.get("last_ai_prompt")
        last_response = user_data.get("last_ai_response")
        if last_prompt and last_response:
            messages_payload.append({"role": "user", "content": last_prompt})
            messages_payload.append({"role": "assistant", "content": last_response})
        elif last_response:
            messages_payload.append({"role": "assistant", "content": last_response})

        messages_payload.append({"role": "user", "content": question})

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=500, # Peut être ajusté pour les slash commands
            messages=messages_payload
        )

        ai_response = response.choices[0].message.content
        user_data["last_ai_prompt"] = question
        user_data["last_ai_response"] = ai_response
        save_data()
        
        # 3. ENVOI DE LA RÉPONSE
        
        # Ajout d'une mention si l'accès était illimité
        if has_unlimited_access:
            footer_text = "✨ Accès illimité via Statut Premium, VIP ou Nexus Day."
            color = discord.Color.blue()
        else:
            footer_text = f"⚡️ Crédit restant : {user_data.get(credits_key, 0)}"
            color = discord.Color.green()
        
        embed = discord.Embed(
            title=f"🧠 Nexus AI (GPT-4o-mini) :",
            description=ai_response,
            color=color
        )
        embed.set_footer(text=footer_text)
        
        await interaction.followup.send(embed=embed)

    except Exception as e:
        print(f"⚠️ Erreur OpenAI pour la commande /ask ({interaction.user}): {e}")
        
        # 4. GESTION DU REMBOURSEMENT EN CAS D'ÉCHEC
        if credit_deducted:
            # Remboursement du crédit
            user_data[credits_key] += 1
            
            # REMBOURSEMENT COMPTEUR AUSSI
            user_data["quest_counters"]["ai_usage_count"] -= 1
            
            save_data()
            await interaction.followup.send("⚠️ Erreur lors de la génération de la réponse. Le crédit a été remboursé.", ephemeral=True)
        else:
            await interaction.followup.send("⚠️ Erreur lors de la génération de la réponse. Veuillez réessayer.", ephemeral=True)
# 💬 COMMANDE /top (SLASH COMMAND) - CORRIGÉE
# ==================================
@bot.tree.command(name="top", description="Affiche le classement des utilisateurs les plus riches.")
@app_commands.describe(portee="La portée du classement: 'serveur' ou 'global'.")
async def top_slash(interaction: discord.Interaction, portee: str = 'serveur'):
    try:
        # Assurer que l'option est valide
        portee = portee.lower()
        if portee not in ['serveur', 'global']:
            await interaction.response.send_message("⚠️ Portée invalide. Utilisez `serveur` ou `global`.", ephemeral=True)
            return

        if portee == 'serveur' and not interaction.guild:
            await interaction.response.send_message("⚠️ Impossible d'afficher le classement du serveur dans ce contexte (MP).", ephemeral=True)
            return
            
        # Déférer la réponse immédiatement
        await interaction.response.defer(ephemeral=False)
    except discord.NotFound:
        # Si l'interaction a déjà été répondue ou a expiré
        return

    # 1. Préparer les données
    leaderboard = []
    
    if portee == 'global':
        # Classement Global (parcourt tous les utilisateurs dans le fichier data)
        for user_id, user_data in data.items():
            
            # CORRECTION ICI : Gérer les clés non-ID (comme 'config')
            try:
                user_id_int = int(user_id)
                leaderboard.append((user_id_int, user_data.get('money', 0)))
            except ValueError:
                # La clé n'est pas un ID d'utilisateur (ex: 'config'), on l'ignore.
                continue
    
    elif portee == 'serveur':
        # Classement Serveur (parcourt uniquement les membres du serveur actuel)
        for member in interaction.guild.members:
            if str(member.id) in data:
                leaderboard.append((member.id, data[str(member.id)].get('money', 0)))

    # 2. Tri du classement (par argent, décroissant)
    leaderboard.sort(key=lambda item: item[1], reverse=True)
    leaderboard = leaderboard[:10]
    
    # 3. Création de l'Embed
    embed = discord.Embed(
        title=f"👑 Classement des Utilisateurs (Portée: {portee.capitalize()})",
        color=discord.Color.gold()
    )
    
    rank_text = ""
    
    for index, (user_id, money) in enumerate(leaderboard):
        try:
            # Tente de récupérer l'objet membre/utilisateur
            user_obj = interaction.guild.get_member(user_id) if portee == 'serveur' and interaction.guild else bot.get_user(user_id)
            name = user_obj.display_name if user_obj else f"Utilisateur Inconnu ({user_id})"
            
            # Décoration du rang
            if index == 0:
                rank_icon = "🥇"
            elif index == 1:
                rank_icon = "🥈"
            elif index == 2:
                rank_icon = "🥉"
            else:
                rank_icon = f"#{index + 1}"
                
            rank_text += f"{rank_icon} **{name}** : **{money}$**\n"
            
        except Exception:
            # Gère les cas où l'utilisateur n'est plus accessible
            rank_text += f"#{index + 1} **Utilisateur Inconnu** : **{money}$**\n"

    if not rank_text:
        rank_text = "Aucun utilisateur classé."

    embed.description = rank_text
    
    # 4. Répondre à l'interaction avec followup
    try:
        await interaction.followup.send(embed=embed)
    except discord.NotFound:
        # Si l'interaction a expiré, envoyer un message normal
        channel = interaction.channel
        if channel:
            await channel.send(embed=embed)

# Suppression de l'ancienne commande ,top
try:
    bot.remove_command('top')
except:
    pass

@bot.command()
@commands.is_owner()
async def setpremium(ctx, guild_id: int, status: bool):
    """[OWNER] Active/Désactive le statut Premium pour un serveur."""
    guild_id_str = str(guild_id)
    
    if guild_id_str not in data["config"]:
        data["config"][guild_id_str] = {}

    data["config"][guild_id_str]["is_premium"] = status
    save_data()
    
    await ctx.send(f"✅ Statut Premium du serveur `{guild_id}` défini sur : **{status}**")


# ==================================
# COMMANDE SLASH /IMAGINE (Génération d'Image)
# ==================================
@bot.tree.command(name="imagine", description="Génère une image à partir d'une description textuelle (Stable Diffusion XL).")
@app_commands.describe(prompt="La description détaillée de l'image à générer.")
async def imagine_command(interaction: discord.Interaction, prompt: str):
    await interaction.response.defer(ephemeral=False) 

    # Vérifier si replicate est disponible
    if 'replicate' not in globals() or not hasattr(replicate, 'run'):
        embed = discord.Embed(
            title="❌ Erreur de Configuration",
            description="La fonctionnalité d'image IA est actuellement désactivée en raison d'une incompatibilité avec Python 3.14.\n\nVeuillez utiliser Python 3.11 ou 3.10 pour bénéficier de cette fonctionnalité.",
            color=discord.Color.red()
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        return

    user_id = str(interaction.user.id)
    global IMAGINE_MAINTENANCE

    if IMAGINE_MAINTENANCE:
        embed = discord.Embed(
            title="🛠️ Génération d'images en maintenance",
            description=(
                "La commande `/imagine` est temporairement indisponible car la clé API Replicate n'est pas configurée.\n"
                "Merci de réessayer plus tard ou de contacter un administrateur."
            ),
            color=discord.Color.red()
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        return

    # --- 1. VÉRIFICATION DES CRÉDITS (Utilise les variables globales : EVENT_MODE_ENABLED, VIP_ROLE_ID, data) ---
    is_guild_premium = data.get("config", {}).get(str(interaction.guild_id), {}).get("is_premium", False)
    
    # Assurez-vous que VIP_ROLE_ID est défini quelque part (ex: VIP_ROLE_ID = 123456...)
    guild_member = interaction.guild.get_member(interaction.user.id) if interaction.guild else None
    is_vip = await ensure_vip_state(interaction.user.id, guild_member)

    global EVENT_MODE_ENABLED
    has_unlimited_access = is_guild_premium or is_vip or EVENT_MODE_ENABLED
    
    COST_IMAGE = 5 # Coût de l'image
    credits_key = "credits" 
    credit_deducted = False

    if not has_unlimited_access:
        ensure_user(user_id)
        user_data = data[user_id]
        
        # 💡 Vérification sécurisée avec .get()
        if user_data.get(credits_key, 0) < COST_IMAGE:
            embed = discord.Embed(
                title="❌ Accès Refusé - Crédits Insuffisants",
                description=f"La génération d'image coûte **{COST_IMAGE} crédits** ! Utilise `/boutique` ou attends le **Nexus Day** !",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed)
            return

        # Déduction des crédits
        user_data[credits_key] = user_data.get(credits_key, 0) - COST_IMAGE
        credit_deducted = True

    # Sauvegarde de la progression et des compteurs
    ensure_user(user_id)
    user_data = data[user_id]
    user_data.setdefault("quest_counters", {})
    user_data["quest_counters"]["image_gen_count"] = user_data["quest_counters"].get("image_gen_count", 0) + 1
    save_data()
    
    # --- 2. APPEL À L'API REPLICATE ---
    try:
        model = "stability-ai/sdxl"
        
        # Le client Replicate utilise la variable d'environnement REPLICATE_API_TOKEN
        output = replicate.run(
            model,
            input={
                "prompt": prompt,
                "width": 1024,
                "height": 1024,
                "num_outputs": 1,
                "scheduler": "K_EULER"
            }
        )
        
        # L'output est une liste d'URLs
        image_url = output[0] 
        
        # 3. ENVOI DE LA RÉPONSE
        if has_unlimited_access:
            footer_text = "✨ Accès illimité"
            cost_text = "GRATUIT"
            color = discord.Color.blue()
        else:
            footer_text = f"⚡️ Crédits restants : {user_data.get(credits_key, 0)}"
            cost_text = f"Coût: {COST_IMAGE} crédits"
            color = discord.Color.purple()
        
        embed = discord.Embed(
            title=f"🎨 Stable Diffusion XL (Replicate)",
            description=f"**Prompt :** *{prompt}*",
            color=color
        )
        embed.set_image(url=image_url)
        embed.set_footer(text=f"{cost_text} | {footer_text}")
        
        await interaction.followup.send(embed=embed)

    except Exception as e:
        print(f"⚠️ Erreur Replicate pour la commande /imagine ({interaction.user}): {e}")
        
        # 4. GESTION DU REMBOURSEMENT EN CAS D'ÉCHEC
        if credit_deducted:
            # Remboursement des crédits
            user_data[credits_key] = user_data.get(credits_key, 0) + COST_IMAGE
            # REMBOURSEMENT COMPTEUR AUSSI
            user_data["quest_counters"]["image_gen_count"] = user_data["quest_counters"].get("image_gen_count", 0) - 1
            
            save_data()
            await interaction.followup.send("⚠️ Erreur lors de la génération de l'image (API Replicate). Le coût a été remboursé.", ephemeral=True)
        else:
            await interaction.followup.send("⚠️ Erreur lors de la génération de l'image. Veuillez réessayer.", ephemeral=True)

# --- Commande ,userinfo (MISE À JOUR) ---
@bot.command(aliases=['info', 'user'])
async def userinfo(ctx, member: discord.Member = None):
    """
    Affiche des informations détaillées sur un membre du serveur.
    """
    if member is None:
        member = ctx.author

    embed = build_userinfo_embed(member, ctx.author)
    await ctx.send(embed=embed)


@userinfo.error
async def userinfo_error(ctx, error):
    if isinstance(error, commands.BadArgument):
        await ctx.send("❌ Utilisateur introuvable. Veuillez mentionner un membre valide du serveur.")
    else:
        await ctx.send("⚠️ Une erreur inattendue est survenue.")


# ==================================
# COMMANDE /daily (VERSION SLASH)
# ==================================
@bot.tree.command(name="daily", description=" Réclame ta récompense journalière (toutes les 24h)")
async def daily_slash(interaction: discord.Interaction):
    """Réclame la récompense journalière (une fois toutes les 24 heures)."""
    user_id_str = str(interaction.user.id)
    ensure_user(user_id_str)
    user_data = data[user_id_str]
    
    COOLDOWN = 24 * 60 * 60 
    now = time.time()
    
    last_daily = user_data.get("last_daily", 0) 
    time_since = now - last_daily
    
    if time_since >= COOLDOWN:
        reward = random.randint(30, 50)
        
        user_data["money"] = user_data.get("money", 0) + reward
        user_data["last_daily"] = now
        
        # Incrémentation du compteur de quête daily
        user_data.setdefault("quest_counters", {})
        user_data["quest_counters"]["econ_action_daily"] += 1 

        save_data()
        
        embed = discord.Embed(
            title=" Récompense Journalière Réclamée !",
            description=f"Tu as gagné **{reward}$** !\nReviens dans 24h pour ta prochaine récompense.",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed)
    else:
        remaining_time = COOLDOWN - time_since
        hours = int(remaining_time // 3600)
        minutes = int((remaining_time % 3600) // 60)
        seconds = int(remaining_time % 60)
        
        time_left = f"{hours}h {minutes}min {seconds}s"
        
        embed = discord.Embed(
            title=" Récompense Indisponible",
            description=f"Tu dois encore attendre **{time_left}** avant de pouvoir réclamer ta récompense journalière.",
            color=discord.Color.orange()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


# ==================================
# COMMANDE /boutique (VERSION SLASH)
# ==================================
@bot.tree.command(name="boutique", description=" Ouvre la boutique pour acheter des crédits IA et des avantages")
async def boutique_slash(interaction: discord.Interaction):
    """Ouvre la boutique IA avec interface moderne."""
    user_id_str = str(interaction.user.id)
    ensure_user(user_id_str)  # ✅ Correction: Assurer l'existence de l'utilisateur
    
    user_data = data[user_id_str]
    
    class BoutiqueView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=180)  # Timeout après 3 minutes

        async def check_balance_and_process(self, interaction: discord.Interaction, cost: int, reward_func, success_message: str):
            """Vérifie le solde et traite l'achat avec gestion d'erreurs améliorée."""
            user_id = str(interaction.user.id)
            
            # ✅ Correction: Vérification de l'existence des données
            if user_id not in data:
                return await interaction.response.send_message(
                    "❌ Erreur: Données utilisateur introuvables. Veuillez réessayer.", 
                    ephemeral=True
                )
            
            if data[user_id].get("money", 0) < cost:
                return await interaction.response.send_message(
                    f"❌ Tu n'as pas assez d'argent virtuel (il te faut {cost}$)! 🛒", 
                    ephemeral=True
                )
            
            try:
                data[user_id]["money"] -= cost
                result = reward_func(data[user_id])
                if inspect.isawaitable(result):
                    await result
                save_data()
                
                await interaction.response.send_message(
                    f"✅ Achat réussi ! {success_message} Solde restant : {data[user_id]['money']}$", 
                    ephemeral=False
                )
            except Exception as e:
                # ✅ Correction: Rollback en cas d'erreur
                data[user_id]["money"] += cost
                save_data()
                await interaction.response.send_message(
                    f"❌ Erreur lors de l'achat: {str(e)}", 
                    ephemeral=True
                )


        @discord.ui.button(label="Acheter 1 crédit IA (20$)", style=discord.ButtonStyle.green, custom_id="buy_credit_small")
        async def buy_credit(self, interaction: discord.Interaction, button: discord.ui.Button):
            def reward(user_data): 
                user_data["credits"] = user_data.get("credits", 0) + 1
            await self.check_balance_and_process(interaction, 20, reward, "1 crédit IA ajouté 🧠.")

        @discord.ui.button(label="Pack Crédits XL (50🧠)", style=discord.ButtonStyle.green, custom_id="buy_credits_xl")
        async def buy_credits_xl_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
            def reward(user_data): 
                user_data["credits"] = user_data.get("credits", 0) + 50
            await self.check_balance_and_process(interaction, 750, reward, "50 crédits IA ajoutés 🧠.")

        @discord.ui.button(label="Jeton d'Image (1🖼️) - Maint.", style=discord.ButtonStyle.grey, custom_id="buy_image_token", disabled=True)
        async def buy_image_token_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
            embed_maintenance = discord.Embed(
                title="❌ Achat Indisponible Temporairement",
                description="La fonction de génération d'images (`/imagine`) est en maintenance.\n\n"
                            "**L'achat des Jetons d'Image (🖼️) est bloqué** jusqu'au retour à la normale.",
                color=discord.Color.red()
            )
            return await interaction.response.send_message(embed=embed_maintenance, ephemeral=True)

        @discord.ui.button(label="Pass Priorité IA (200$)", style=discord.ButtonStyle.blurple, custom_id="buy_priority")
        async def buy_priority_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
            user_id = str(interaction.user.id)
            ensure_user(user_id)  # ✅ Correction: Assurer l'existence
            
            if data[user_id].get("has_priority", False):
                return await interaction.response.send_message("⚠️ Vous possédez déjà le Pass Priorité IA !", ephemeral=True)
            
            async def reward(user_data): 
                await grant_vip_access(interaction.user.id)
            await self.check_balance_and_process(interaction, 200, reward, "Pass Priorité IA activé 👑 (vous sautez le cooldown)!")

    # Création de l'embed de la boutique
    embed = discord.Embed(
        title="🛒 Boutique IA",
        description=(
            f"**Ton solde :** {user_data.get('money', 0)}$ et {user_data.get('credits', 0)} crédits IA 🧠.\n"
            f"**Statut Priorité :** {'👑 Actif' if user_data.get('has_priority') else '❌ Inactif'}\n\n"
            "**--- Crédits et Jetons IA ---**"
        ),
        color=discord.Color.blue()
    )
    
    await interaction.response.send_message(embed=embed, view=BoutiqueView())

# ==================================
# 💬 COMMANDES ADMINISTRATEUR
# ==================================

# --- Commande ,setpersona (VIP Server Access) ---
@bot.command(aliases=['setai'])
@commands.check(is_vip_server) 
async def setpersona(ctx, *, prompt: str = None):
    """
    Définit la personnalité (prompt système) de l'IA pour ce serveur.
    Accessible uniquement si l'utilisateur a le rôle VIP sur le serveur support du bot.
    """
    guild_id_str = str(ctx.guild.id)
    
    # S'assurer que la configuration du serveur existe
    if guild_id_str not in data["config"]:
        data["config"][guild_id_str] = {}

    if prompt is None or prompt.lower() in ["default", "défaut", "reset"]:
        # Réinitialisation à la valeur par défaut
        if "ai_persona" in data["config"][guild_id_str]:
            del data["config"][guild_id_str]["ai_persona"]
        save_data()
        return await ctx.send("✅ La personnalité de l'IA a été réinitialisée à la version par défaut (utile et amicale).")

    # Mise à jour du prompt
    data["config"][guild_id_str]["ai_persona"] = prompt
    save_data()

    embed = discord.Embed(
        title="👑 Personnalité de l'IA Mise à Jour !",
        description=f"Le prompt système de l'IA pour ce serveur est maintenant :\n\n>>> **{prompt[:250]}{'...' if len(prompt) > 250 else ''}**",
        color=discord.Color.dark_green()
    )
    await ctx.send(embed=embed)

# 🚨 Ajout du gestionnaire d'erreur spécifique au check
@setpersona.error
async def setpersona_error(ctx, error):
    if isinstance(error, commands.CheckFailure):
        await ctx.send(
            f"❌ **Accès Refusé.** Cette commande est réservée aux utilisateurs ayant le rôle VIP "
            f"sur le serveur support du bot. Achetez le Pass VIP pour débloquer cette personnalisation !"
        )
    else:
        await ctx.send(f"⚠️ Une erreur inconnue est survenue : {error}")

class ConfigView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)
        self.value = None

    @discord.ui.select(
        placeholder="Choisissez une catégorie à configurer",
        options=[
            discord.SelectOption(
                label="IA",
                description="Configurer le salon IA et les paramètres d'IA",
                emoji="🤖"
            ),
            discord.SelectOption(
                label="Tickets",
                description="Configurer le système de tickets",
                emoji="🎫"
            ),
            discord.SelectOption(
                label="Musique",
                description="Configurer les paramètres audio",
                emoji="🎵"
            ),
            discord.SelectOption(
                label="Modération",
                description="Configurer les logs et la modération",
                emoji="🛡️"
            )
        ]
    )
    async def select_callback(self, interaction: discord.Interaction, select: discord.ui.Select):
        category = select.values[0]
        self.value = category
        self.stop()
        
        # Créer un embed de réponse
        embed = discord.Embed(
            title=f"Configuration - {category}",
            description=f"Vous avez sélectionné la catégorie **{category}**.",
            color=discord.Color.blue()
        )
        
        # Ajouter des champs spécifiques à chaque catégorie
        if category == "IA":
            embed.add_field(
                name="Paramètres disponibles",
                value="• Salon IA actuel\n• Modèle d'IA\n• Limite de crédits",
                inline=False
            )
            embed.set_footer(text="Utilisez /config-ia pour configurer ces paramètres")
            
        elif category == "Tickets":
            embed.add_field(
                name="Paramètres disponibles",
                value="• Catégorie des tickets\n• Rôle du support\n• Message de bienvenue",
                inline=False
            )
            embed.set_footer(text="Utilisez /config-ticket pour configurer ces paramètres")
            
        elif category == "Musique":
            embed.add_field(
                name="Paramètres disponibles",
                value="• Volume par défaut\n• Qualité audio\n• Commandes DJ uniquement",
                inline=False
            )
            embed.set_footer(text="Utilisez /config-musique pour configurer ces paramètres")
            
        elif category == "Modération":
            embed.add_field(
                name="Paramètres disponibles",
                value="• Salon des logs\n• Rôles de modération\n• Filtres automatiques",
                inline=False
            )
            embed.set_footer(text="Utilisez /config-mod pour configurer ces paramètres")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

# --- Commande /config (Admin) ---
@bot.tree.command(name="config", description="Affiche le menu de configuration du serveur")
@commands.has_permissions(administrator=True)
async def config(interaction: discord.Interaction):
    """Affiche le menu de configuration du serveur avec les différentes catégories."""
    view = ConfigView()
    
    embed = discord.Embed(
        title="⚙️ Configuration du serveur",
        description="Sélectionnez une catégorie à configurer dans le menu déroulant ci-dessous.",
        color=discord.Color.blue()
    )
    
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

# --- Ancienne commande config (conservée pour rétrocompatibilité) ---
@bot.command()
@commands.has_permissions(administrator=True)
async def old_config(ctx, salonIA: discord.TextChannel = None):
    """Ancienne commande de configuration - Utilisez /config à la place"""
    await ctx.send("⚠️ Cette commande est obsolète. Utilisez la commande `/config` avec le menu interactif.")
    
    if salonIA is not None:
        guild_id = str(ctx.guild.id)
        salon_id = salonIA.id

        if guild_id not in data["config"]:
            data["config"][guild_id] = {}

        data["config"][guild_id]["ai_channel"] = salon_id
        save_data()
        await ctx.send(f"✅ Le salon IA pour **{ctx.guild.name}** a été mis à jour : {salonIA.mention}")

@config.error
async def config_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message(
            "❌ Vous n'avez pas les permissions d'administrateur pour utiliser cette commande.",
            ephemeral=True
        )
    else:
        await interaction.response.send_message(
            f"❌ Une erreur est survenue : {str(error)}",
            ephemeral=True
        )


# --- Commande ,autoconfig (Admin) ---
@bot.command()
@commands.has_permissions(administrator=True)
async def autoconfig(ctx):
    """Crée un salon 'ia' et le configure comme salon IA du serveur."""
    guild_id = str(ctx.guild.id)
    
    try:
        category = discord.utils.get(ctx.guild.categories, name="Général")
        channel_name = "ia"
        existing_channel = discord.utils.get(ctx.guild.text_channels, name=channel_name)

        if existing_channel:
            await ctx.send(f"⚠️ Un salon nommé `{channel_name}` existe déjà. Utilisation de ce salon pour la configuration.")
            new_channel = existing_channel
        else:
            new_channel = await ctx.guild.create_text_channel(
                name=channel_name, 
                category=category,
                reason="Création automatique du salon pour l'IA"
            )
            await new_channel.send("🤖 **Configuration terminée !** Vous pouvez commencer à discuter ici avec l'IA. (1 crédit par message)")

    except Exception as e:
        print(f"Erreur lors de la création/recherche du salon : {e}")
        return await ctx.send("❌ Une erreur s'est produite lors de la création du salon. Vérifiez les permissions du bot.")

    salon_id = new_channel.id

    if guild_id not in data["config"]:
        data["config"][guild_id] = {}

    data["config"][guild_id]["ai_channel"] = salon_id
    save_data()

    await ctx.send(f"🎉 **Configuration IA automatique réussie !** Le salon {new_channel.mention} est maintenant configuré comme salon IA.")


# --- Commande ,broadcast (Owner seulement) ---
@bot.command()
@commands.is_owner()
async def broadcast(ctx, *, message_content):
    """Envoie un message donné à tous les salons IA configurés sur chaque serveur (Owner seulement)."""
    
    await ctx.send(f"⏳ Lancement du broadcast du message : **{message_content}** dans tous les salons IA configurés.")
    
    count = 0
    
    for guild_id_str, config in data["config"].items():
        try:
            guild_id = int(guild_id_str)
            ai_channel_id = config.get("ai_channel")

            if ai_channel_id:
                guild = bot.get_guild(guild_id)
                if not guild: continue
                channel = guild.get_channel(ai_channel_id)

                if channel and channel.permissions_for(guild.me).send_messages:
                    await channel.send(f"📢 **Message du développeur :** {message_content}")
                    count += 1
                
        except Exception as e:
            print(f"Erreur lors du broadcast sur le serveur ID {guild_id_str}: {e}")

    await ctx.send(f"✅ Broadcast terminé ! Message envoyé dans **{count}** salons IA.")

@broadcast.error
async def broadcast_error(ctx, error):
    if isinstance(error, commands.NotOwner):
        await ctx.send("❌ **Accès refusé.** Seul le propriétaire du bot est autorisé à utiliser cette commande.")
    else:
        await ctx.send(f"⚠️ Erreur : {error}")
        
        
# ==================================
#  COMMANDE /setup-ticket (ADMIN ONLY)
# ==================================
# Utilise discord.app_commands.checks.has_permissions(administrator=True) pour restreindre l'accès
from discord import app_commands

@bot.tree.command(name="setup-ticket", description="[ADMIN] Configure le panneau permanent pour ouvrir des tickets.")
@app_commands.checks.has_permissions(administrator=True)
async def setup_ticket_slash(interaction: discord.Interaction):
    guild = interaction.guild
    
    # 1. Vérification et Création de la Catégorie (Logique du précédent ticket_slash)
    category = discord.utils.get(guild.categories, id=TICKET_CATEGORY_ID)
    
    if not category:
        try:
            category = await guild.create_category(
                "💬 TICKETS SUPPORT 💬",
                overwrites={
                    guild.default_role: discord.PermissionOverwrite(read_messages=False),
                    guild.me: discord.PermissionOverwrite(read_messages=True)
                }
            )
            # NOTE: L'ID de la catégorie est créé, mais TICKET_CATEGORY_ID (la constante)
            # NE PEUT PAS être mise à jour ici car c'est une variable globale définie au départ.
            # L'administrateur devra noter l'ID de cette catégorie pour mettre à jour la constante TICKET_CATEGORY_ID
            # en haut du fichier pour la persistance du bot après redémarrage.
            
            await interaction.response.send_message(
                f"✅ Catégorie de ticket créée : **{category.name}** (`{category.id}`). Veuillez mettre à jour la constante `TICKET_CATEGORY_ID` dans le code du bot.",
                ephemeral=True
            )
            # L'interaction initiale a déjà été répondue. On va éditer/envoyer le panneau après.

        except discord.Forbidden:
            return await interaction.response.send_message(
                "❌ **Erreur :** Le bot n'a pas les permissions de créer la catégorie.",
                ephemeral=True
            )
    else:
        # Répondre immédiatement pour ne pas expirer (Admin)
        await interaction.response.send_message("⚙️ Panneau de tickets en cours de configuration...", ephemeral=True)


    # 2. Création du Panneau de Tickets
    
    panel_embed = discord.Embed(
        title="📩 Support Technique & Aide",
        description="Cliquez sur le bouton ci-dessous pour ouvrir un ticket et obtenir de l'aide de notre équipe de support. \n\n**Merci de fournir tous les détails de votre problème.**",
        color=discord.Color.blue()
    )
    panel_embed.set_footer(text="Un ticket par problème, merci.")
    
    # Envoi du panneau avec le bouton permanent
    await interaction.channel.send(embed=panel_embed, view=TicketButton())
    
    # Confirmer l'envoi
    await interaction.edit_original_response(content="✅ **Panneau de tickets configuré avec succès !**")


# --- Commande ,stop (Owner seulement) ---
@bot.command()
@commands.is_owner()
async def stop(ctx):
    """
    Envoie un message d'arrêt dans tous les salons IA, puis éteint le bot. 
    (Owner seulement)
    """
    
    await ctx.send("🚨 **Arrêt imminent !** Envoi du message d'extinction à tous les serveurs...")
    
    shutdown_message = "🔴 **Maintenance :** Le bot s'éteint pour maintenance et mise à jour. Nous serons de retour sous peu. Merci de votre compréhension !"
    count = 0
    
    for guild_id_str, config in data["config"].items():
        try:
            guild_id = int(guild_id_str)
            ai_channel_id = config.get("ai_channel")

            if ai_channel_id:
                guild = bot.get_guild(guild_id)
                if not guild: continue
                channel = guild.get_channel(ai_channel_id)

                if channel and channel.permissions_for(guild.me).send_messages:
                    await channel.send(shutdown_message)
                    count += 1
                
        except Exception as e:
            print(f"Erreur lors de l'envoi du message d'arrêt sur le serveur ID {guild_id_str}: {e}")

    await ctx.send(f"✅ Message d'arrêt envoyé dans **{count}** salons. Extinction du bot en cours...")
    
    try:
        await bot.close()
        print("🔴 Le bot a été éteint par la commande !stop.")
    except Exception as e:
        print(f"Erreur lors de la fermeture de la connexion du bot : {e}")


@stop.error
async def stop_error(ctx, error):
    if isinstance(error, commands.NotOwner):
        await ctx.send("❌ **Accès refusé.** Seul le propriétaire du bot est autorisé à utiliser cette commande.")
    else:
        await ctx.send(f"⚠️ Erreur lors de l'exécution de la commande d'arrêt : {error}")

# ==================================
# 🔒 COMMANDE /reload (OWNER ONLY)
# ==================================
@bot.command(name='reload', aliases=['save', 'recharge'])
async def reload_data(ctx):
    """Sauvegarde manuellement les données du bot (propriétaire uniquement)."""
    if ctx.author.id != OWNER_ID:
        await ctx.send("❌ **Accès Refusé :** Seul le propriétaire du bot peut utiliser cette commande.")
        return
    
    try:
        save_data()
        await ctx.send("✅ **Sauvegarde Forcée :** Les données en mémoire ont été écrites dans `data.json` avec succès.")
    except Exception as e:
        error_msg = f"❌ **Erreur lors de la sauvegarde :** {str(e)}"
        print(f"Erreur dans reload_data: {e}")
        await ctx.send(error_msg)


# ==================================
# 🌐 CONFIGURATION : HELP_CATEGORIES
# ==================================
HELP_CATEGORIES = {
    "general": {
        "label": "🌐 Général & Support",
        "description": "Commandes de base du bot.",
        "commands": [
            { "name": "📚 /help", "value": "Affiche ce menu d'aide interactif." },
            { "name": "🔗 /invite", "value": "Obtenez le lien d'invitation pour m'ajouter à d'autres serveurs." },
            { "name": "🧑‍💻 /userinfo [@membre]", "value": "Affiche les infos Discord et économiques d'un membre." },
            { "name": "🏓 /ping", "value": "Affiche la latence du bot." },
            { "name": "📊 /stats", "value": "Affiche vos statistiques économiques et votre progression." }
        ]
    },
    "economie": {
        "label": "💰 Économie & Quêtes",
        "description": "Gagnez, dépensez et classez-vous !",
        "commands": [
            { "name": "📈 /stats [membre]", "value": "Affiche votre solde, crédits IA et votre statut de priorité." },
            { "name": "💵 /daily", "value": "Réclame ta récompense journalière (toutes les 24h)." },
            { "name": "🎯 /quests", "value": "Affiche ta quête quotidienne et ta progression de niveau (Tier)." },
            { "name": "👑 /top [serveur/global]", "value": "Affiche le classement des utilisateurs les plus riches." },
            { "name": "🛒 /boutique", "value": "Ouvre la boutique pour acheter des crédits IA et des avantages. (Bientôt en slash)" }
        ]
    },
    "minijeux": {
        "label": "🎲 Mini-JeuX",
        "description": "Tentez votre chance avec votre argent virtuel.",
        "commands": [
            { "name": "🪙 /coinflip <montant> <choix>", "value": "Pile ou face. Doublez votre mise en cas de victoire !" },
            { "name": "🎰 /slot <montant>", "value": "Jouez à la machine à sous avec animation. Triplez votre mise pour le jackpot !" }
        ]
    },
    "musique": {
        "label": "🎵 Musique & Audio",
        "description": "Commandes pour écouter et gérer la musique.",
        "commands": [
            { "name": "🎵 /musique <lien>", "value": "Joue une musique dans ton salon vocal." },
            { "name": "⏭️ /skip", "value": "Passe à la musique suivante." },
            { "name": "📋 /queue", "value": "Affiche la file d'attente des musiques." },
            { "name": "🗑️ /clear", "value": "Vide toute la file d'attente." },
            { "name": "❌ /remove <position>", "value": "Retire une musique spécifique de la file." },
            { "name": "🔀 /melange", "value": "Mélange la file d'attente." },
            { "name": "⏸️ /pause", "value": "Met en pause la musique actuelle." },
            { "name": "▶️ /resume", "value": "Reprend la musique en pause." },
            { "name": "🔊 /volume <niveau>", "value": "Règle le volume (0-200%)." },
            { "name": "🔍 /search <titre>", "value": "Recherche des musiques sur YouTube." },
            { "name": "📝 /playlist <lien>", "value": "Charge une playlist YouTube." },
            { "name": "🎭 /mood <ambiance>", "value": "Joue une musique selon ton humeur." },
            { "name": "🎸 /genre <style>", "value": "Joue une musique selon un genre musical." },
            { "name": "📻 /radio <station>", "value": "Lance une radio automatique." },
            { "name": "🎧 /quality <qualité>", "value": "Change la qualité audio (haute/normale)." },
            { "name": "🔊 /bassboost", "value": "Améliore les basses de la musique." },
            { "name": "📊 /music-stats", "value": "Affiche tes statistiques musicales." },
            { "name": "📈 /top-songs", "value": "Affiche les musiques les plus populaires." },
            { "name": "📜 /history", "value": "Affiche l'historique des musiques écoutées." },
            { "name": "⚔️ /duel <utilisateur>", "value": "Défie un autre utilisateur en musique." },
            { "name": "🗳️ /vote-skip", "value": "Lance un vote pour passer la musique." },
            { "name": "🎵 /song-request <titre>", "value": "Demande une musique aux autres utilisateurs." },
            { "name": "🔒 /music-lock <état>", "value": "Verrouille/déverrouille les commandes musicales." },
            { "name": "⏱️ /max-duration <minutes>", "value": "Définit la durée maximale des musiques." },
            { "name": "🚫 /blacklist <mot>", "value": "Ajoute un mot à la liste noire." }
        ]
    },
    "ia": {
        "label": "🧠 Intelligence Artificielle",
        "description": "Interagissez avec l'Intelligence Artificielle.",
        "commands": [
            { "name": "🗣️ Salon IA", "value": "Discute avec l'IA dans le salon configuré (1 crédit utilisé par message)." },
            { "name": "🖼️ /imagine <prompt>", "value": "**[NOUVEAU !]** Génère une image via l'IA DALL-E (coûte 5 jetons)." },
            { "name": "⚙️ /setpersona <prompt>", "value": "**VIP** : Définit la personnalité de l'IA sur le serveur. (Bientôt en slash)" }
        ]
    },
    "moderation": {
        "label": "🛡️ Modération & Sécurité",
        "description": "Outils essentiels pour le Staff (Niveau de permission requis : Modérer les membres).",
        "commands": [
            { "name": "🔨 /ban <m> [r]", "value": "Bannit un membre." },
            { "name": "🚪 /kick <m> [r]", "value": "Exclut un membre." },
            { "name": "🔇 /mute <m> <d>", "value": "Met en timeout un membre pour X minutes." },
            { "name": "⚠️ /warn <m> [r]", "value": "Envoie un avertissement officiel (DM inclus)." },
            { "name": "🔓 /unban <ID>", "value": "Lève le bannissement (via ID)." },
            { "name": "🗑️ /purge <n>", "value": "Supprime X messages dans le canal." },
            { "name": "🔒 /lock [canal]", "value": "Verrouille l'accès en écriture d'un salon." },
            { "name": "🔑 /unlock [canal]", "value": "Déverrouille un salon." }
        ]
    },
    "gestion": {
        "label": "🛠️ Configuration & Gestion",
        "description": "Commandes pour les administrateurs et outils.",
        "commands": [
            { "name": "🔗 ,config <#salon>", "value": "**ADMIN** : Définit le salon IA de discussion." },
            { "name": "✨ ,autoconfig", "value": "**ADMIN** : Crée et configure automatiquement un salon `#ia`." },
            { "name": "⚙️ /setup-ticket", "value": "**ADMIN** : Crée le panneau de tickets (bouton permanent)." },
            { "name": "🔐 ,close", "value": "**STAFF** : Ferme et archive un ticket de support." }
        ]
    }
}
def get_embed_for_category(category_key: str) -> discord.Embed:
    # Récupère les données de la catégorie
    category_data = HELP_CATEGORIES.get(category_key, HELP_CATEGORIES["general"])
    
    # Création de l'embed
    embed = discord.Embed(
        title=f"{category_data['label']} - Commandes",
        description=f"*{category_data['description']}*",
        color=discord.Color.blue()
    )
    
    # Ajout des commandes
    for cmd in category_data["commands"]:
        embed.add_field(
            name=cmd["name"],
            value=cmd["value"],
            inline=False # Chaque commande prend une ligne
        )
        
    embed.set_footer(text=f"Catégorie: {category_key.capitalize()} | Bot par Nexus AI")
    
    return embed

# ==================================
# ⬇️ CLASSE HelpCategorySelect
# ==================================
class HelpCategorySelect(discord.ui.Select):
    def __init__(self):
        # Créer les options à partir du dictionnaire HELP_CATEGORIES
        options = [
            discord.SelectOption(
                label=data["label"].split(' ')[1], # Utilise uniquement le texte (ex: "Général")
                description=data["description"],
                emoji=data["label"].split(' ')[0], # Utilise l'emoji au début du label
                value=key
            )
            for key, data in HELP_CATEGORIES.items()
        ]

        super().__init__(
            placeholder="Choisir une catégorie...",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        # La catégorie sélectionnée est le premier (et unique) élément de self.values
        selected_category_key = self.values[0]
        
        # 1. Générer le nouvel embed
        new_embed = get_embed_for_category(selected_category_key)
        
        # 2. Mettre à jour la View pour garder l'état de la catégorie actuelle
        self.view.current_category = selected_category_key
        
        # 3. Répondre en éditant le message avec le nouvel embed
        await interaction.response.edit_message(embed=new_embed, view=self.view)

# ==================================
# 🌐 CLASSE HelpView (Conteneur - CORRIGÉE)
# ==================================
class HelpView(discord.ui.View):
    def __init__(self, initial_category: str):
        super().__init__(timeout=None) 
        self.current_category = initial_category
        
        # 1. Ajouter le menu déroulant
        self.add_item(HelpCategorySelect())
        
        # 2. Le bouton de fermeture est DEJA ajouté via le décorateur @discord.ui.button
        # ⚠️ RETIREZ cette ligne si elle est présente : self.add_item(self.stop_button) 
        # Laissez simplement le décorateur faire le travail.
        
    # Le bouton lui-même est défini ci-dessous :
    @discord.ui.button(label="Fermer le Menu", style=discord.ButtonStyle.red, emoji="❌", custom_id="help:stop")
    async def stop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # ... (logique du bouton) ...
        pass
        # Répondre en désactivant tous les composants et en modifiant l'embed pour indiquer la fermeture
        new_embed = discord.Embed(
            title="👋 Menu d'Aide Fermé",
            description="Merci d'avoir consulté le menu. Utilisez `/help` à nouveau si besoin !",
            color=discord.Color.dark_red()
        )
        
        # Désactiver les composants
        for item in self.children:
            item.disabled = True
            
        await interaction.response.edit_message(embed=new_embed, view=self)
        self.stop() # Arrête le View

# ==================================
# ⬇️ COMMANDE /help (Rappel de l'appel)
# ==================================
# Assurez-vous que votre commande /help utilise bien cette structure :

@bot.tree.command(name="help", description="Affiche le menu d'aide interactif du bot.")
async def help_command_slash(interaction: discord.Interaction):
    initial_category = "general" # Catégorie par défaut
    
    # Le bot.py ligne 1985 (dans votre log) doit être cette ligne, MAINTENANT CORRIGÉE.
    view = HelpView(initial_category)
    initial_embed = get_embed_for_category(initial_category)
    
    await interaction.response.send_message(embed=initial_embed, view=view, ephemeral=True)


@bot.tree.command(name="ping", description="Affiche la latence du bot.")
async def ping_command_slash(interaction: discord.Interaction):
    latency = round(bot.latency * 1000)
    await interaction.response.send_message(f"Pong! 🏓 ({latency} ms)")


@bot.tree.command(name="invite", description="Obtenez le lien d'invitation du bot.")
async def invite_command_slash(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🤖 Ajouter le bot sur ton serveur",
        description=f"[Clique ici pour m’ajouter à ton serveur]({INVITE_URL})",
        color=discord.Color.green()
    )
    embed.set_footer(text="Merci d’utiliser le bot 💙")
    await interaction.response.send_message(embed=embed, ephemeral=True)


def build_userinfo_embed(member: discord.Member, requester: discord.Member) -> discord.Embed:
    """
    Construit un embed avec les informations d'un membre.
    
    Args:
        member: Le membre dont afficher les informations
        requester: L'utilisateur qui a fait la requête
        
    Returns:
        discord.Embed: L'embed contenant les informations du membre
    """
    # Informations de base
    created_at = member.created_at.strftime("%d/%m/%Y à %H:%M")
    joined_at = member.joined_at.strftime("%d/%m/%Y à %H:%M") if member.joined_at else "Inconnu"
    
    # Récupération des données économiques
    user_id = str(member.id)
    ensure_user(user_id)
    user_data = data.get(user_id, {})
    money = user_data.get("money", 0)
    credits = user_data.get("credits", 0)
    image_tokens = user_data.get("image_tokens", 0)
    has_priority = user_data.get("has_priority", False)
    
    # Rôles (sans le @everyone)
    roles = [role.mention for role in member.roles[1:]]  # On enlève le @everyone
    if not roles:
        roles_str = "Aucun rôle"
    
    # Statut et activité
    status = str(member.status).capitalize()
    activity = f"{member.activity.type.name.capitalize()} {member.activity.name}" if member.activity else "Aucune activité"
    
    # Création de l'embed
    embed = discord.Embed(
        title=f"ℹ️ Informations sur {member.display_name}",
        color=member.color if member.color != discord.Color.default() else 0x2f3136
    )
    
    # Avatar
    embed.set_thumbnail(url=member.display_avatar.url)
    
    # Champs d'informations
    embed.add_field(name="👤 Pseudo", value=f"{member.name}#{member.discriminator}", inline=True)
    embed.add_field(name="🏷️ Surnom", value=member.display_name, inline=True)
    embed.add_field(name="👁️ ID", value=member.id, inline=True)
    
    embed.add_field(name="📅 Compte créé le", value=created_at, inline=True)
    embed.add_field(name="🌍 A rejoint le", value=joined_at, inline=True)
    
    embed.add_field(name="🤖 Bot", value="✅" if member.bot else "❌", inline=True)
    embed.add_field(name="🔒 Statut", value=status, inline=True)
    
    # Section économique
    embed.add_field(name="💰 Économie", value="​", inline=False)
    embed.add_field(name="💵 Argent", value=f"**{money}$**", inline=True)
    embed.add_field(name="🧮 Crédits IA", value=f"**{credits}**", inline=True)
    embed.add_field(name="🖼️ Jetons Image", value=f"**{image_tokens}**", inline=True)
    
    # Statut de priorité
    priority_status = "👑 Prioritaire" if has_priority else "👤 Standard"
    embed.add_field(name="⚖️ Statut", value=priority_status, inline=True)
    
    # Section activité et rôles
    embed.add_field(name="🎮 Activité", value=activity, inline=False)
    embed.add_field(name=f"👔 Rôles ({len(roles)})", value=roles_str, inline=False)
    
    # Pied de page
    embed.set_footer(text=f"Demandé par {requester}", icon_url=requester.display_avatar.url)
    
    return embed

@bot.tree.command(name="userinfo", description="Affiche les infos Discord et économiques d'un membre.")
@app_commands.describe(member="Membre dont afficher les informations")
async def userinfo_command_slash(interaction: discord.Interaction, member: Optional[discord.Member] = None):
    if interaction.guild is None:
        await interaction.response.send_message("❌ Cette commande doit être utilisée dans un serveur.", ephemeral=True)
        return

    if member is None:
        if isinstance(interaction.user, discord.Member):
            member = interaction.user
        else:
            member = interaction.guild.get_member(interaction.user.id)

    if member is None:
        await interaction.response.send_message("❌ Impossible de trouver ce membre sur le serveur.", ephemeral=True)
        return

    embed = build_userinfo_embed(member, interaction.user)
    await interaction.response.send_message(embed=embed, ephemeral=True)


# --- Autres commandes de base ---
@bot.command()
async def ping(ctx):
    latency = round(bot.latency * 1000)
    await ctx.send(f"Pong! 🏓 ({latency} ms)")
    
@bot.command(name="bot", aliases=["add"])
async def bot_invite(ctx):
    embed = discord.Embed(
        title="🤖 Ajouter le bot sur ton serveur",
        description=f"[Clique ici pour m’ajouter à ton serveur]({INVITE_URL})",
        color=discord.Color.green()
    )
    embed.set_footer(text="Merci d’utiliser le bot 💙")
    await ctx.send(embed=embed)

# ==================================
# COMMANDE /skip
# ==================================
@bot.tree.command(name="skip", description="Passe à la musique suivante")
async def skip_command(interaction: discord.Interaction):
    """Passe à la musique suivante dans la file d'attente"""
    guild_id = interaction.guild.id
    voice_client = voice_clients.get(guild_id)
    
    # Vérifier si le bot est connecté
    if not voice_client:
        embed = discord.Embed(
            title="❌ Bot Non Connecté",
            description="Je ne suis pas dans un salon vocal.",
            color=discord.Color.orange()
        )
        return await interaction.response.send_message(embed=embed, ephemeral=True)
    
    # Vérifier si quelque chose est en train de jouer
    if not voice_client.is_playing():
        embed = discord.Embed(
            title="❌ Aucune Musique en Lecture",
            description="Aucune musique n'est en train de jouer.",
            color=discord.Color.orange()
        )
        return await interaction.response.send_message(embed=embed, ephemeral=True)
    
    # Vérifier s'il y a une musique suivante
    if guild_id not in music_queues or not music_queues[guild_id]:
        embed = discord.Embed(
            title="❌ File d'Attente Vide",
            description="Il n'y a pas de musique suivante dans la file d'attente.",
            color=discord.Color.orange()
        )
        return await interaction.response.send_message(embed=embed, ephemeral=True)
    
    # Arrêter la musique actuelle (play_next_song sera appelé automatiquement)
    voice_client.stop()
    
    embed = discord.Embed(
        title="⏭️ Musique Passée",
        description="Passage à la musique suivante...",
        color=discord.Color.green()
    )
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="resume", description="Reprend la musique en pause")
async def resume_command(interaction: discord.Interaction):
    """Reprend la lecture de la musique"""
    guild_id = interaction.guild.id
    voice_client = voice_clients.get(guild_id)
    
    if not voice_client or not voice_client.is_paused():
        embed = discord.Embed(
            title="❌ Aucune Musique en Pause",
            description="Aucune musique n'est en pause.",
            color=discord.Color.orange()
        )
        return await interaction.response.send_message(embed=embed)
    
    voice_client.resume()
    music_paused[guild_id] = False
    
    embed = discord.Embed(
        title="▶️ Musique Reprise",
        description="La lecture a repris.",
        color=discord.Color.green()
    )
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="volume", description="Règle le volume de la musique")
@app_commands.describe(level="Niveau de volume (0-100)")
async def volume_command(interaction: discord.Interaction, level: int):
    """Règle le volume de la musique (0-100)"""
    guild_id = interaction.guild.id
    voice_client = voice_clients.get(guild_id)
    
    if level < 0 or level > 100:
        embed = discord.Embed(
            title="❌ Volume Invalide",
            description="Le volume doit être entre 0 et 100.",
            color=discord.Color.red()
        )
        return await interaction.response.send_message(embed=embed)
    
    music_volume[guild_id] = level / 100  # Convertir en 0.0-1.0
    
    # Si une musique joue, appliquer le volume
    if voice_client and voice_client.source:
        voice_client.source.volume = level / 100
    
    embed = discord.Embed(
        title="🔊 Volume Modifié",
        description=f"Volume réglé à **{level}%**.",
        color=discord.Color.green()
    )
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="stop", description="Arrête la musique et déconnecte le bot")
@checks.has_permissions(administrator=True)
async def stop_command(interaction: discord.Interaction):
    """Arrête la musique et déconnecte le bot du salon vocal"""
    guild_id = interaction.guild.id
    voice_client = voice_clients.get(guild_id)
    
    # Vérifier si le bot est connecté
    if not voice_client:
        embed = discord.Embed(
            title="❌ Bot Non Connecté",
            description="Je ne suis pas dans un salon vocal.",
            color=discord.Color.orange()
        )
        return await interaction.response.send_message(embed=embed, ephemeral=True)
    
    # Arrêter la musique
    voice_client.stop()
    
    # Vider la file d'attente
    if guild_id in music_queues:
        music_queues[guild_id].clear()
    
    # Réinitialiser l'état de pause
    music_paused[guild_id] = False
    
    # Déconnecter le bot
    await voice_client.disconnect()
    del voice_clients[guild_id]

    nickname_reset = False
    try:
        guild_me = interaction.guild.me
        if guild_me and guild_me.nick:
            await guild_me.edit(nick=None)
            nickname_reset = True
    except discord.Forbidden:
        nickname_reset = False

    embed = discord.Embed(
        title="⏹️ Musique Arrêtée",
        description="J'ai arrêté la musique et quitté le salon vocal.",
        color=discord.Color.red()
    )
    if nickname_reset:
        embed.set_footer(text="Le surnom du bot a été réinitialisé.")
    else:
        embed.set_footer(text="Impossible de réinitialiser le surnom (permissions insuffisantes).")
    await send_embed(interaction, embed)

@stop_command.error
async def stop_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, checks.MissingPermissions):
        embed = discord.Embed(
            title="❌ Accès Refusé",
            description="Cette commande est réservée aux administrateurs.",
            color=discord.Color.red()
        )
        await send_embed(interaction, embed, ephemeral=True)
    else:
        raise error

@bot.command(name="stop_music", aliases=["musicstop"])
async def stop_music(ctx):
    """Arrête la musique et déconnecte le bot (commande préfixe)
    Renommée en `stop_music` pour éviter un conflit avec la commande owner `stop`.
    """
    guild_id = ctx.guild.id
    voice_client = voice_clients.get(guild_id)
    
    # Vérifier si le bot est connecté
    if not voice_client:
        embed = discord.Embed(
            title="❌ Bot Non Connecté",
            description="Je ne suis pas dans un salon vocal.",
            color=discord.Color.orange()
        )
        return await ctx.send(embed=embed)
    
    # Arrêter la musique
    voice_client.stop()
    
    # Vider la file d'attente
    if guild_id in music_queues:
        music_queues[guild_id].clear()
    
    # Réinitialiser l'état de pause
    music_paused[guild_id] = False
    
    # Déconnecter le bot
    await voice_client.disconnect()
    del voice_clients[guild_id]
    
    embed = discord.Embed(
        title="⏹️ Musique Arrêtée",
        description="J'ai arrêté la musique et quitté le salon vocal.",
        color=discord.Color.red()
    )
    await ctx.send(embed=embed)

@bot.tree.command(name="pause", description="Met en pause la musique")
async def pause_command(interaction: discord.Interaction):
    """Met en pause la musique"""
    guild_id = interaction.guild.id
    voice_client = voice_clients.get(guild_id)
    
    if not voice_client or not voice_client.is_playing():
        embed = discord.Embed(
            title="❌ Aucune Musique en Lecture",
            description="Aucune musique n'est en train de jouer.",
            color=discord.Color.orange()
        )
        return await interaction.response.send_message(embed=embed, ephemeral=True)
    
    voice_client.pause()
    music_paused[guild_id] = True
    
    embed = discord.Embed(
        title="⏸️ Musique en Pause",
        description="La musique a été mise en pause.",
        color=discord.Color.orange()
    )
    await interaction.response.send_message(embed=embed)

@bot.command()
async def pause(ctx):
    """Met en pause la musique (commande préfixe)"""
    guild_id = ctx.guild.id
    voice_client = voice_clients.get(guild_id)
    
    if not voice_client or not voice_client.is_playing():
        embed = discord.Embed(
            title="❌ Aucune Musique en Lecture",
            description="Aucune musique n'est en train de jouer.",
            color=discord.Color.orange()
        )
        return await ctx.send(embed=embed)
    
    voice_client.pause()
    music_paused[guild_id] = True
    
    embed = discord.Embed(
        title="⏸️ Musique en Pause",
        description="La musique a été mise en pause.",
        color=discord.Color.orange()
    )
    await ctx.send(embed=embed)

@bot.tree.command(name="queue", description="Affiche la file d'attente")
async def queue_command(interaction: discord.Interaction):
    """Affiche la file d'attente des musiques"""
    guild_id = interaction.guild.id
    
    if guild_id not in music_queues or not music_queues[guild_id]:
        embed = discord.Embed(
            title="📋 File d'Attente Vide",
            description="Il n'y a aucune musique dans la file d'attente.",
            color=discord.Color.orange()
        )
        return await interaction.response.send_message(embed=embed)
    
    queue = music_queues[guild_id]
    embed = discord.Embed(
        title="📋 File d'Attente",
        description=f"**{len(queue)}** musique(s) dans la file d'attente",
        color=discord.Color.blue()
    )
    
    # Afficher les 10 premières musiques
    for i, song in enumerate(queue[:10], 1):
        title = song.get('title', 'Titre inconnu')
        uploader = song.get('uploader', 'Inconnu')
        duration = song.get('duration', 0)
        duration_str = f"{duration//60}:{duration%60:02d}" if duration else "Inconnue"
        
        embed.add_field(
            name=f"{i}. {title[:40]}{'...' if len(title) > 40 else ''}",
            value=f"👤 {uploader} | ⏱️ {duration_str}",
            inline=False
        )
    
    if len(queue) > 10:
        embed.set_footer(text=f"... et {len(queue) - 10} autres musiques")
    
    await interaction.response.send_message(embed=embed)

@bot.command()
async def queue(ctx):
    """Affiche la file d'attente (commande préfixe)"""
    guild_id = ctx.guild.id
    
    if guild_id not in music_queues or not music_queues[guild_id]:
        embed = discord.Embed(
            title="📋 File d'Attente Vide",
            description="Il n'y a aucune musique dans la file d'attente.",
            color=discord.Color.orange()
        )
        return await ctx.send(embed=embed)
    
    queue = music_queues[guild_id]
    embed = discord.Embed(
        title="📋 File d'Attente",
        description=f"**{len(queue)}** musique(s) dans la file d'attente",
        color=discord.Color.blue()
    )
    
    # Afficher les 10 premières musiques
    for i, song in enumerate(queue[:10], 1):
        title = song.get('title', 'Titre inconnu')
        uploader = song.get('uploader', 'Inconnu')
        duration = song.get('duration', 0)
        duration_str = f"{duration//60}:{duration%60:02d}" if duration else "Inconnue"
        
        embed.add_field(
            name=f"{i}. {title[:40]}{'...' if len(title) > 40 else ''}",
            value=f"👤 {uploader} | ⏱️ {duration_str}",
            inline=False
        )
    
    if len(queue) > 10:
        embed.set_footer(text=f"... et {len(queue) - 10} autres musiques")
    
    await ctx.send(embed=embed)

@bot.tree.command(name="clear", description="Vide la file d'attente")
async def clear_command(interaction: discord.Interaction):
    """Vide la file d'attente des musiques"""
    guild_id = interaction.guild.id
    
    if guild_id not in music_queues or not music_queues[guild_id]:
        embed = discord.Embed(
            title="📋 File d'Attente Vide",
            description="La file d'attente est déjà vide.",
            color=discord.Color.orange()
        )
        return await interaction.response.send_message(embed=embed, ephemeral=True)
    
    queue_length = len(music_queues[guild_id])
    music_queues[guild_id].clear()
    
    embed = discord.Embed(
        title="🗑️ File d'Attente Vidée",
        description=f"**{queue_length}** musique(s) ont été retirées de la file d'attente.",
        color=discord.Color.red()
    )
    await interaction.response.send_message(embed=embed)

@bot.command()
async def clear(ctx):
    """Vide la file d'attente (commande préfixe)"""
    guild_id = ctx.guild.id
    
    if guild_id not in music_queues or not music_queues[guild_id]:
        embed = discord.Embed(
            title="📋 File d'Attente Vide",
            description="La file d'attente est déjà vide.",
            color=discord.Color.orange()
        )
        return await ctx.send(embed=embed)
    
    queue_length = len(music_queues[guild_id])
    music_queues[guild_id].clear()
    
    embed = discord.Embed(
        title="🗑️ File d'Attente Vidée",
        description=f"**{queue_length}** musique(s) ont été retirées de la file d'attente.",
        color=discord.Color.red()
    )
    await ctx.send(embed=embed)

@bot.tree.command(name="remove", description="Retire une musique de la file d'attente")
@app_commands.describe(position="Position de la musique dans la file d'attente")
async def remove_command(interaction: discord.Interaction, position: int):
    """Retire une musique spécifique de la file d'attente"""
    guild_id = interaction.guild.id
    
    if guild_id not in music_queues or not music_queues[guild_id]:
        embed = discord.Embed(
            title="📋 File d'Attente Vide",
            description="Il n'y a aucune musique dans la file d'attente.",
            color=discord.Color.orange()
        )
        return await interaction.response.send_message(embed=embed, ephemeral=True)
    
    queue = music_queues[guild_id]
    
    if position < 1 or position > len(queue):
        embed = discord.Embed(
            title="❌ Position Invalide",
            description=f"La position doit être entre 1 et {len(queue)}.",
            color=discord.Color.red()
        )
        return await interaction.response.send_message(embed=embed, ephemeral=True)
    
    removed_song = queue.pop(position - 1)
    title = removed_song.get('title', 'Titre inconnu')
    
    embed = discord.Embed(
        title="🗑️ Musique Retirée",
        description=f"**{title}** a été retirée de la file d'attente.",
        color=discord.Color.green()
    )
    await interaction.response.send_message(embed=embed)

@bot.command()
async def remove(ctx, position: int):
    """Retire une musique spécifique de la file d'attente (commande préfixe)"""
    guild_id = ctx.guild.id
    
    if guild_id not in music_queues or not music_queues[guild_id]:
        embed = discord.Embed(
            title="📋 File d'Attente Vide",
            description="Il n'y a aucune musique dans la file d'attente.",
            color=discord.Color.orange()
        )
        return await ctx.send(embed=embed)
    
    queue = music_queues[guild_id]
    
    if position < 1 or position > len(queue):
        embed = discord.Embed(
            title="❌ Position Invalide",
            description=f"La position doit être entre 1 et {len(queue)}.",
            color=discord.Color.red()
        )
        return await ctx.send(embed=embed)
    
    removed_song = queue.pop(position - 1)
    title = removed_song.get('title', 'Titre inconnu')
    
    embed = discord.Embed(
        title="🗑️ Musique Retirée",
        description=f"**{title}** a été retirée de la file d'attente.",
        color=discord.Color.green()
    )
    await ctx.send(embed=embed)

@bot.tree.command(name="shuffle", description="Mélange la file d'attente")
async def shuffle_command(interaction: discord.Interaction):
    """Mélange la file d'attente des musiques"""
    guild_id = interaction.guild.id
    
    if guild_id not in music_queues or not music_queues[guild_id]:
        embed = discord.Embed(
            title="📋 File d'Attente Vide",
            description="Il n'y a aucune musique dans la file d'attente.",
            color=discord.Color.orange()
        )
        return await interaction.response.send_message(embed=embed, ephemeral=True)
    
    queue_length = len(music_queues[guild_id])
    random.shuffle(music_queues[guild_id])
    
    embed = discord.Embed(
        title="🔀 File d'Attente Mélangée",
        description=f"**{queue_length}** musique(s) ont été mélangées.",
        color=discord.Color.purple()
    )
    await interaction.response.send_message(embed=embed)

@bot.command()
async def melange(ctx):
    """Mélange la file d'attente (commande préfixe)"""
    guild_id = ctx.guild.id
    
    if guild_id not in music_queues or not music_queues[guild_id]:
        embed = discord.Embed(
            title="📋 File d'Attente Vide",
            description="Il n'y a aucune musique dans la file d'attente.",
            color=discord.Color.orange()
        )
        return await ctx.send(embed=embed)
    
    queue_length = len(music_queues[guild_id])
    random.shuffle(music_queues[guild_id])
    
    embed = discord.Embed(
        title="🔀 File d'Attente Mélangée",
        description=f"**{queue_length}** musique(s) ont été mélangées.",
        color=discord.Color.purple()
    )
    await ctx.send(embed=embed)

# ==================================
# COMMANDES DE RECHERCHE
# ==================================
class AddToQueueView(discord.ui.View):
    def __init__(self, song_info: dict, user_id: int):
        super().__init__(timeout=30)
        self.song_info = song_info
        self.user_id = user_id
        self.message: Optional[discord.Message] = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user_id

    async def on_timeout(self) -> None:
        for child in self.children:
            child.disabled = True
        if self.message:
            try:
                await self.message.edit(content="Temps écoulé. Action annulée.", view=self)
            except discord.HTTPException:
                pass

    async def _ensure_voice_client(self, interaction: discord.Interaction) -> tuple[Optional[discord.VoiceClient], Optional[str]]:
        guild_id = interaction.guild.id
        voice_client = voice_clients.get(guild_id)

        if voice_client and voice_client.is_connected():
            return voice_client, None

        voice_client = interaction.guild.voice_client
        if voice_client and voice_client.is_connected():
            voice_clients[guild_id] = voice_client
            return voice_client, None

        if not interaction.user.voice or not interaction.user.voice.channel:
            return None, "❌ Tu dois être dans un salon vocal pour utiliser cette commande !"

        try:
            voice_client = await interaction.user.voice.channel.connect()
            voice_clients[guild_id] = voice_client
            return voice_client, None
        except RuntimeError as e:
            if "PyNaCl" in str(e):
                return None, (
                    "❌ Bibliothèque Manquante\nLa bibliothèque PyNaCl est requise pour les fonctionnalités vocales."
                )
            raise

    async def _add_song_to_queue(self, interaction: discord.Interaction) -> tuple[str, Optional[discord.Embed]]:
        guild_id = interaction.guild.id
        song_info = self.song_info.copy()

        detailed_info = extract_video_info(song_info.get('url')) if song_info.get('url') else None
        if detailed_info:
            if song_info.get('thumbnail') and not detailed_info.get('thumbnail'):
                detailed_info['thumbnail'] = song_info['thumbnail']
            song_info = detailed_info
        else:
            song_info.setdefault('title', 'Titre inconnu')
            song_info.setdefault('uploader', 'Inconnu')
            song_info.setdefault('duration', 0)
            song_info.setdefault('thumbnail', '')
            song_info.setdefault('url', self.song_info.get('url', ''))

        if guild_id not in music_queues:
            music_queues[guild_id] = []

        voice_client, error_message = await self._ensure_voice_client(interaction)
        if not voice_client:
            return error_message or "❌ Impossible de rejoindre le salon vocal.", None

        if voice_client.is_playing() or voice_client.is_paused():
            music_queues[guild_id].append(song_info)
            position = len(music_queues[guild_id])
            embed = discord.Embed(
                title="🎵 Ajoutée à la File d'Attente",
                description=f"**{song_info['title']}** a été ajoutée (position {position}).",
                color=discord.Color.blue()
            )
            if song_info.get('url'):
                embed.add_field(name="Lien SoundCloud", value=f"[Écouter]({song_info['url']})", inline=False)
            if song_info.get('thumbnail'):
                embed.set_thumbnail(url=song_info['thumbnail'])
            return "", embed

        success = await play_music(guild_id, voice_client, song_info)
        if not success:
            return "❌ Impossible de lire cette musique. Réessaie plus tard.", None

        embed = discord.Embed(
            title="🎵 Lecture Lancée !",
            description=f"Je joue maintenant : **{song_info['title']}**",
            color=discord.Color.green()
        )
        if song_info.get('thumbnail'):
            embed.set_thumbnail(url=song_info['thumbnail'])
        if song_info.get('url'):
            embed.add_field(name="Lien SoundCloud", value=f"[Écouter]({song_info['url']})", inline=False)
        return "", embed

    def _disable_buttons(self):
        for child in self.children:
            child.disabled = True

    @discord.ui.button(label="Ajouter à la file", style=discord.ButtonStyle.success, emoji="➕")
    async def add_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        message, embed = await self._add_song_to_queue(interaction)
        self._disable_buttons()

        content = message or "✅ La musique a été prise en compte."
        await interaction.response.edit_message(content=content, embed=embed, view=self)
        self.stop()

    @discord.ui.button(label="Annuler", style=discord.ButtonStyle.danger, emoji="✖️")
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self._disable_buttons()
        await interaction.response.edit_message(content="❌ Ajout annulé.", embed=None, view=self)
        self.stop()

class SearchView(discord.ui.View):
    def __init__(self, search_results, user_id):
        super().__init__(timeout=60)
        self.search_results = search_results
        self.user_id = user_id
        self.add_buttons()
    
    def add_buttons(self):
        for i in range(min(5, len(self.search_results))):
            self.add_item(SearchButton(i+1, self.search_results[i]))
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user_id

class SearchButton(discord.ui.Button):
    def __init__(self, number: int, song_info: dict):
        self.song_info = song_info
        super().__init__(
            label=str(number),
            style=discord.ButtonStyle.primary,
            custom_id=f"search_{number}"
        )
    
    async def callback(self, interaction: discord.Interaction):
        # Désactiver tous les boutons
        for item in self.view.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True
        
        # Mettre à jour le message pour montrer la sélection
        embed = interaction.message.embeds[0]
        embed.title = "✅ Musique Sélectionnée"
        link = self.song_info.get('url', '')
        link_line = f"[🎧 Ouvrir sur SoundCloud]({link})\n" if link else ""
        embed.description = f"**{self.song_info['title']}**\n{link_line}*Choisis si tu veux l'ajouter à la file d'attente.*"
        embed.color = discord.Color.green()
        
        await interaction.response.edit_message(embed=embed, view=self.view)

        link_message = "Souhaites-tu l'ajouter à la file d'attente ?"
        if link:
            link_message = f"🎧 Voici ton lien SoundCloud : {link}\nSouhaites-tu l'ajouter à la file d'attente ?"

        queue_view = AddToQueueView(self.song_info, interaction.user.id)
        message = await interaction.followup.send(link_message, view=queue_view, ephemeral=True)
        queue_view.message = message

@bot.tree.command(name="search", description="Recherche des musiques sur SoundCloud")
@app_commands.describe(terme="Terme de recherche")
async def search_command(interaction: discord.Interaction, terme: str):
    """Recherche des musiques sur SoundCloud avec sélection par boutons"""
    try:
        # Vérifier si l'utilisateur est dans un salon vocal
        if not interaction.user.voice or not interaction.user.voice.channel:
            embed = discord.Embed(
                title="❌ Salon Vocal Requis",
                description="Tu dois être dans un salon vocal pour utiliser cette commande !",
                color=discord.Color.red()
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)
        
        await interaction.response.defer()
        
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'skip_download': True,
        }

        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"scsearch5:{terme}", download=False)
            
            if not info or 'entries' not in info or not info['entries']:
                embed = discord.Embed(
                    title="🔍 Aucun Résultat",
                    description=f"Aucune musique trouvée pour : **{terme}**",
                    color=discord.Color.orange()
                )
                return await interaction.followup.send(embed=embed)
            
            embed = discord.Embed(
                title=f"🔍 Résultats pour : {terme}",
                description="Choisis une musique en cliquant sur le bouton correspondant :",
                color=discord.Color.blue()
            )
            
            results = []

            def format_duration(seconds: Optional[int]) -> str:
                if not seconds:
                    return "Inconnue"
                minutes = seconds // 60
                remaining = seconds % 60
                return f"{minutes}:{remaining:02d}"

            for i, entry in enumerate(info['entries'][:5], 1):
                title = entry.get('title', 'Titre inconnu')
                duration_seconds = entry.get('duration') or entry.get('duration_str')
                duration_value = 0
                if isinstance(duration_seconds, (int, float)):
                    duration_value = int(duration_seconds)
                elif isinstance(duration_seconds, str) and duration_seconds.isdigit():
                    duration_value = int(duration_seconds)
                uploader = entry.get('uploader', 'Inconnu')
                url = entry.get('webpage_url', '')
                thumbnail = entry.get('thumbnail', '')
                
                duration_str = format_duration(duration_value)
                
                embed.add_field(
                    name=f"{i}. {title[:50]}{'...' if len(title) > 50 else ''}",
                    value=f"👤 {uploader} | ⏱️ {duration_str}",
                    inline=False
                )
                
                results.append({
                    'title': title,
                    'url': url,
                    'uploader': uploader,
                    'duration': duration_value,
                    'duration_str': duration_str,
                    'thumbnail': thumbnail
                })
            
            # Créer et envoyer la vue avec les boutons
            view = SearchView(results, interaction.user.id)
            await interaction.followup.send(embed=embed, view=view)
            
    except Exception as e:
        print(f"Erreur recherche: {e}")
        embed = discord.Embed(
            title="❌ Erreur de Recherche",
            description=f"Une erreur est survenue lors de la recherche: {str(e)}",
            color=discord.Color.red()
        )
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(embed=embed, ephemeral=True)
            else:
                await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e2:
            print(f"Erreur lors de l'envoi du message d'erreur: {e2}")

@bot.tree.command(name="playlist", description="Ajoute une playlist YouTube à la file d'attente")
@app_commands.describe(lien="Lien de la playlist YouTube")
async def playlist_command(interaction: discord.Interaction, lien: str):
    """Ajoute une playlist entière à la file d'attente"""
    guild_id = interaction.guild.id
    
    # Vérifier si l'utilisateur est dans un salon vocal
    if not interaction.user.voice or not interaction.user.voice.channel:
        embed = discord.Embed(
            title="❌ Salon Vocal Requis",
            description="Tu dois être dans un salon vocal pour que je puisse jouer de la musique !",
            color=discord.Color.orange()
        )
        return await interaction.response.send_message(embed=embed, ephemeral=True)
    
    try:
        # Configurer yt-dlp pour les playlists
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,  # Pour obtenir les infos sans télécharger
            'ignoreerrors': True,
        }
        
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(lien, download=False)
            
            if not info or 'entries' not in info:
                embed = discord.Embed(
                    title="❌ Playlist Invalide",
                    description="Impossible de lire cette playlist. Vérifie le lien.",
                    color=discord.Color.red()
                )
                return await interaction.response.send_message(embed=embed)
            
            entries = info['entries']
            if not entries:
                embed = discord.Embed(
                    title="❌ Playlist Vide",
                    description="Cette playlist ne contient aucune vidéo.",
                    color=discord.Color.orange()
                )
                return await interaction.response.send_message(embed=embed)
            
            # Initialiser la file d'attente si nécessaire
            if guild_id not in music_queues:
                music_queues[guild_id] = []
            
            # Limiter à 50 musiques maximum pour éviter les files trop longues
            songs_to_add = entries[:50]
            added_count = 0
            
            for entry in songs_to_add:
                if entry and entry.get('webpage_url'):
                    song_info = {
                        'title': entry.get('title', 'Titre inconnu'),
                        'url': entry['webpage_url'],
                        'uploader': entry.get('uploader', 'Inconnu'),
                        'duration': entry.get('duration', 0),
                        'thumbnail': entry.get('thumbnail', '')
                    }
                    music_queues[guild_id].append(song_info)
                    added_count += 1
            
            # Vérifier si le bot est connecté
            voice_client = voice_clients.get(guild_id)
            if not voice_client:
                voice_client = await interaction.user.voice.channel.connect()
                voice_clients[guild_id] = voice_client
                
                # Jouer la première musique
                if music_queues[guild_id]:
                    first_song = music_queues[guild_id].pop(0)
                    success = await play_music(guild_id, voice_client, first_song)
                    
                    if success:
                        embed = discord.Embed(
                            title="🎵 Playlist Lancée !",
                            description=f"**{added_count}** musiques ajoutées.\nJe joue maintenant : **{first_song['title']}**",
                            color=discord.Color.green()
                        )
                    else:
                        embed = discord.Embed(
                            title="❌ Erreur de Lecture",
                            description="Erreur lors de la lecture de la première musique.",
                            color=discord.Color.red()
                        )
            else:
                embed = discord.Embed(
                    title="🎵 Playlist Ajoutée !",
                    description=f"**{added_count}** musiques ajoutées à la file d'attente.",
                    color=discord.Color.blue()
                )
            
            await interaction.response.send_message(embed=embed)
            
    except Exception as e:
        print(f"Erreur playlist: {e}")
        embed = discord.Embed(
            title="❌ Erreur de Playlist",
            description="Une erreur est survenue lors du chargement de la playlist.",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed)

# ==================================
# COMMANDES DE THÈMES ET AMBIANCES
# ==================================
@bot.tree.command(name="mood", description="Joue des musiques selon une ambiance")
@app_commands.describe(ambiance="Ambiance musicale (chill, energy, study, party, relax)")
async def mood_command(interaction: discord.Interaction, ambiance: str):
    """Joue des musiques selon l'ambiance choisie"""
    guild_id = interaction.guild.id
    
    # Vérifier si l'utilisateur est dans un salon vocal
    if not interaction.user.voice or not interaction.user.voice.channel:
        embed = discord.Embed(
            title="❌ Salon Vocal Requis",
            description="Tu dois être dans un salon vocal pour que je puisse jouer de la musique !",
            color=discord.Color.orange()
        )
        return await interaction.response.send_message(embed=embed, ephemeral=True)
    
    # Définir les recherches par ambiance
    mood_searches = {
        "chill": ["chill lofi beats", "relaxing music", "calm piano"],
        "energy": ["upbeat electronic music", "workout motivation", "high energy"],
        "study": ["study focus music", "classical study", "concentration music"],
        "party": ["party dance music", "club hits", "party playlist"],
        "relax": ["meditation music", "spa relaxation", "peaceful sounds"]
    }
    
    ambiance = ambiance.lower()
    if ambiance not in mood_searches:
        embed = discord.Embed(
            title="❌ Ambiance Inconnue",
            description="Ambiances disponibles : chill, energy, study, party, relax",
            color=discord.Color.red()
        )
        return await interaction.response.send_message(embed=embed)
    
    try:
        # Choisir une recherche aléatoire pour cette ambiance
        search_term = random.choice(mood_searches[ambiance])
        
        with YoutubeDL({'quiet': True, 'no_warnings': True, 'skip_download': True}) as ydl:
            info = ydl.extract_info(f"ytsearch3:{search_term}", download=False)
            
            if not info or 'entries' not in info or not info['entries']:
                embed = discord.Embed(
                    title="❌ Aucun Résultat",
                    description=f"Aucune musique trouvée pour l'ambiance : **{ambiance}**",
                    color=discord.Color.orange()
                )
                return await interaction.response.send_message(embed=embed)
            
            # Initialiser la file d'attente si nécessaire
            if guild_id not in music_queues:
                music_queues[guild_id] = []
            
            # Ajouter les musiques trouvées
            added_count = 0
            for entry in info['entries']:
                if entry and entry.get('webpage_url'):
                    song_info = {
                        'title': entry.get('title', 'Titre inconnu'),
                        'url': entry['webpage_url'],
                        'uploader': entry.get('uploader', 'Inconnu'),
                        'duration': entry.get('duration', 0),
                        'thumbnail': entry.get('thumbnail', '')
                    }
                    music_queues[guild_id].append(song_info)
                    added_count += 1
            
            # Vérifier si le bot est connecté
            voice_client = voice_clients.get(guild_id)
            if not voice_client:
                voice_client = await interaction.user.voice.channel.connect()
                voice_clients[guild_id] = voice_client
                
                # Jouer la première musique
                if music_queues[guild_id]:
                    first_song = music_queues[guild_id].pop(0)
                    success = await play_music(guild_id, voice_client, first_song)
                    
                    if success:
                        embed = discord.Embed(
                            title=f"🎵 Ambiance {ambiance.title()} !",
                            description=f"**{added_count}** musiques ajoutées.\nJe joue maintenant : **{first_song['title']}**",
                            color=discord.Color.green()
                        )
                    else:
                        embed = discord.Embed(
                            title="❌ Erreur de Lecture",
                            description="Erreur lors de la lecture de la première musique.",
                            color=discord.Color.red()
                        )
            else:
                embed = discord.Embed(
                    title=f"🎵 Ambiance {ambiance.title()} !",
                    description=f"**{added_count}** musiques ajoutées à la file d'attente.",
                    color=discord.Color.blue()
                )
            
            await interaction.response.send_message(embed=embed)
            
    except Exception as e:
        print(f"Erreur mood: {e}")
        embed = discord.Embed(
            title="❌ Erreur d'Ambiance",
            description="Une erreur est survenue lors du chargement de l'ambiance.",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed)

@bot.tree.command(name="genre", description="Joue des musiques par genre")
@app_commands.describe(genre="Genre musical (rock, pop, jazz, electronic, classical, hip-hop)")
async def genre_command(interaction: discord.Interaction, genre: str):
    """Joue des musiques selon le genre choisi"""
    guild_id = interaction.guild.id
    
    # Vérifier si l'utilisateur est dans un salon vocal
    if not interaction.user.voice or not interaction.user.voice.channel:
        embed = discord.Embed(
            title="❌ Salon Vocal Requis",
            description="Tu dois être dans un salon vocal pour que je puisse jouer de la musique !",
            color=discord.Color.orange()
        )
        return await interaction.response.send_message(embed=embed, ephemeral=True)
    
    # Définir les recherches par genre
    genre_searches = {
        "rock": ["classic rock hits", "modern rock", "indie rock"],
        "pop": ["pop hits 2024", "top pop songs", "pop music"],
        "jazz": ["smooth jazz", "classic jazz", "jazz instrumental"],
        "electronic": ["electronic music", "edm hits", "techno house"],
        "classical": ["classical music", "symphony orchestra", "piano classical"],
        "hip-hop": ["hip hop hits", "rap music", "hip hop beats"]
    }
    
    genre = genre.lower()
    if genre not in genre_searches:
        embed = discord.Embed(
            title="❌ Genre Inconnu",
            description="Genres disponibles : rock, pop, jazz, electronic, classical, hip-hop",
            color=discord.Color.red()
        )
        return await interaction.response.send_message(embed=embed)
    
    try:
        # Choisir une recherche aléatoire pour ce genre
        search_term = random.choice(genre_searches[genre])
        
        with YoutubeDL({'quiet': True, 'no_warnings': True, 'skip_download': True}) as ydl:
            info = ydl.extract_info(f"ytsearch3:{search_term}", download=False)
            
            if not info or 'entries' not in info or not info['entries']:
                embed = discord.Embed(
                    title="❌ Aucun Résultat",
                    description=f"Aucune musique trouvée pour le genre : **{genre}**",
                    color=discord.Color.orange()
                )
                return await interaction.response.send_message(embed=embed)
            
            # Initialiser la file d'attente si nécessaire
            if guild_id not in music_queues:
                music_queues[guild_id] = []
            
            # Ajouter les musiques trouvées
            added_count = 0
            for entry in info['entries']:
                if entry and entry.get('webpage_url'):
                    song_info = {
                        'title': entry.get('title', 'Titre inconnu'),
                        'url': entry['webpage_url'],
                        'uploader': entry.get('uploader', 'Inconnu'),
                        'duration': entry.get('duration', 0),
                        'thumbnail': entry.get('thumbnail', '')
                    }
                    music_queues[guild_id].append(song_info)
                    added_count += 1
            
            # Vérifier si le bot est connecté
            voice_client = voice_clients.get(guild_id)
            if not voice_client:
                voice_client = await interaction.user.voice.channel.connect()
                voice_clients[guild_id] = voice_client
                
                # Jouer la première musique
                if music_queues[guild_id]:
                    first_song = music_queues[guild_id].pop(0)
                    success = await play_music(guild_id, voice_client, first_song)
                    
                    if success:
                        embed = discord.Embed(
                            title=f"🎸 Genre {genre.title()} !",
                            description=f"**{added_count}** musiques ajoutées.\nJe joue maintenant : **{first_song['title']}**",
                            color=discord.Color.green()
                        )
                    else:
                        embed = discord.Embed(
                            title="❌ Erreur de Lecture",
                            description="Erreur lors de la lecture de la première musique.",
                            color=discord.Color.red()
                        )
            else:
                embed = discord.Embed(
                    title=f"🎸 Genre {genre.title()} !",
                    description=f"**{added_count}** musiques ajoutées à la file d'attente.",
                    color=discord.Color.blue()
                )
            
            await interaction.response.send_message(embed=embed)
            
    except Exception as e:
        print(f"Erreur genre: {e}")
        embed = discord.Embed(
            title="❌ Erreur de Genre",
            description="Une erreur est survenue lors du chargement du genre.",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed)

@bot.tree.command(name="radio", description="Lance une radio automatique")
@app_commands.describe(station="Station radio (hits, chill, energy, study)")
async def radio_command(interaction: discord.Interaction, station: str):
    """Lance une radio automatique qui ajoute continuellement des musiques"""
    guild_id = interaction.guild.id
    
    # Vérifier si l'utilisateur est dans un salon vocal
    if not interaction.user.voice or not interaction.user.voice.channel:
        embed = discord.Embed(
            title="❌ Salon Vocal Requis",
            description="Tu dois être dans un salon vocal pour que je puisse jouer de la musique !",
            color=discord.Color.orange()
        )
        return await interaction.response.send_message(embed=embed, ephemeral=True)
    
    # Définir les stations radio
    radio_stations = {
        "hits": ["top hits 2024", "viral songs", "trending music"],
        "chill": ["chill vibes", "lofi radio", "relaxing beats"],
        "energy": ["workout motivation", "high energy music", "upbeat songs"],
        "study": ["study music", "focus beats", "concentration playlist"]
    }
    
    station = station.lower()
    if station not in radio_stations:
        embed = discord.Embed(
            title="❌ Station Inconnue",
            description="Stations disponibles : hits, chill, energy, study",
            color=discord.Color.red()
        )
        return await interaction.response.send_message(embed=embed)
    
    try:
        # Sauvegarder le mode radio
        if not hasattr(bot, 'radio_mode'):
            bot.radio_mode = {}
        bot.radio_mode[guild_id] = station
        
        # Choisir une recherche aléatoire pour cette station
        search_term = random.choice(radio_stations[station])
        
        with YoutubeDL({'quiet': True, 'no_warnings': True, 'skip_download': True}) as ydl:
            info = ydl.extract_info(f"ytsearch5:{search_term}", download=False)
            
            if not info or 'entries' not in info or not info['entries']:
                embed = discord.Embed(
                    title="❌ Aucun Résultat",
                    description=f"Aucune musique trouvée pour la station : **{station}**",
                    color=discord.Color.orange()
                )
                return await interaction.response.send_message(embed=embed)
            
            # Initialiser la file d'attente si nécessaire
            if guild_id not in music_queues:
                music_queues[guild_id] = []
            
            # Ajouter les musiques trouvées
            added_count = 0
            for entry in info['entries']:
                if entry and entry.get('webpage_url'):
                    song_info = {
                        'title': entry.get('title', 'Titre inconnu'),
                        'url': entry['webpage_url'],
                        'uploader': entry.get('uploader', 'Inconnu'),
                        'duration': entry.get('duration', 0),
                        'thumbnail': entry.get('thumbnail', '')
                    }
                    music_queues[guild_id].append(song_info)
                    added_count += 1
            
            # Vérifier si le bot est connecté
            voice_client = voice_clients.get(guild_id)
            if not voice_client:
                voice_client = await interaction.user.voice.channel.connect()
                voice_clients[guild_id] = voice_client
                
                # Jouer la première musique
                if music_queues[guild_id]:
                    first_song = music_queues[guild_id].pop(0)
                    success = await play_music(guild_id, voice_client, first_song)
                    
                    if success:
                        embed = discord.Embed(
                            title=f"📻 Radio {station.title()} Lancée !",
                            description=f"**{added_count}** musiques ajoutées.\nJe joue maintenant : **{first_song['title']}**\n\n*La radio ajoutera automatiquement de nouvelles musiques.*",
                            color=discord.Color.green()
                        )
                    else:
                        embed = discord.Embed(
                            title="❌ Erreur de Lecture",
                            description="Erreur lors de la lecture de la première musique.",
                            color=discord.Color.red()
                        )
            else:
                embed = discord.Embed(
                    title=f"📻 Radio {station.title()} Activée !",
                    description=f"**{added_count}** musiques ajoutées à la file d'attente.\n\n*La radio ajoutera automatiquement de nouvelles musiques.*",
                    color=discord.Color.blue()
                )
            
            await interaction.response.send_message(embed=embed)
            
    except Exception as e:
        print(f"Erreur radio: {e}")
        embed = discord.Embed(
            title="❌ Erreur de Radio",
            description="Une erreur est survenue lors du lancement de la radio.",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed)

# ==================================
# COMMANDES DE QUALITÉ AUDIO
# ==================================
@bot.tree.command(name="quality", description="Change la qualité audio")
@app_commands.describe(qualite="Qualité audio (haute/normale)")
async def quality_command(interaction: discord.Interaction, qualite: str):
    """Change la qualité audio des musiques"""
    global YDL_OPTIONS, FFMPEG_OPTIONS
    
    qualite = qualite.lower()
    if qualite not in ["haute", "normale"]:
        embed = discord.Embed(
            title="❌ Qualité Invalide",
            description="Qualités disponibles : haute, normale",
            color=discord.Color.red()
        )
        return await interaction.response.send_message(embed=embed)
    
    if qualite == "haute":
        YDL_OPTIONS = {
            'format': 'bestaudio/best',
            'noplaylist': True,
            'quiet': True,
            'no_warnings': True,
            'audioquality': '0',  # Meilleure qualité
            'audioformat': 'mp3',
        }
        FFMPEG_OPTIONS = {
            'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
            'options': '-vn -b:a 320k'  # Bitrate élevé
        }
    else:
        YDL_OPTIONS = {
            'format': 'bestaudio/best',
            'noplaylist': True,
            'quiet': True,
            'no_warnings': True,
        }
        FFMPEG_OPTIONS = {
            'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
            'options': '-vn'
        }
    
    embed = discord.Embed(
        title=f"🎧 Qualité Audio : {qualite.title()}",
        description=f"La qualité audio a été changée pour : **{qualite}**\n\n*Les prochaines musiques utiliseront cette qualité.*",
        color=discord.Color.green()
    )
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="bassboost", description="Améliore les basses de la musique")
async def bassboost_command(interaction: discord.Interaction):
    """Active/désactive le bass boost"""
    guild_id = interaction.guild.id
    voice_client = voice_clients.get(guild_id)
    
    if not voice_client or not voice_client.source:
        embed = discord.Embed(
            title="❌ Aucune Musique",
            description="Aucune musique n'est en train de jouer.",
            color=discord.Color.orange()
        )
        return await interaction.response.send_message(embed=embed)
    
    # Sauvegarder l'état bass boost
    if not hasattr(bot, 'bassboost_mode'):
        bot.bassboost_mode = {}
    
    bot.bassboost_mode[guild_id] = not bot.bassboost_mode.get(guild_id, False)
    
    if bot.bassboost_mode[guild_id]:
        FFMPEG_OPTIONS['options'] += ' -af "bass=g=10"'
        embed = discord.Embed(
            title="🔊 Bass Boost Activé",
            description="Les basses sont maintenant amplifiées !",
            color=discord.Color.green()
        )
    else:
        FFMPEG_OPTIONS['options'] = FFMPEG_OPTIONS['options'].replace(' -af "bass=g=10"', '')
        embed = discord.Embed(
            title="🔉 Bass Boost Désactivé",
            description="Les basses sont revenues à la normale.",
            color=discord.Color.red()
        )
    
    await interaction.response.send_message(embed=embed)

# =================================:
# COMMANDES DE STATISTIQUES MUSICALES
# =================================:
@bot.tree.command(name="music-stats", description="Affiche tes statistiques musicales")
async def music_stats_command(interaction: discord.Interaction):
    """Affiche les statistiques musicales de l'utilisateur"""
    guild_id = interaction.guild.id
    user_id = interaction.user.id
    
    # Initialiser les statistiques si nécessaire
    if not hasattr(bot, 'music_stats'):
        bot.music_stats = {}
    
    if guild_id not in bot.music_stats:
        bot.music_stats[guild_id] = {}
    
    if user_id not in bot.music_stats[guild_id]:
        bot.music_stats[guild_id][user_id] = {
            'songs_played': 0,
            'time_listened': 0,
            'favorites': [],
            'first_song': None,
            'last_song': None
        }
    
    stats = bot.music_stats[guild_id][user_id]
    
    embed = discord.Embed(
        title="📊 Tes Statistiques Musicales",
        description=f"Statistiques de **{interaction.user.display_name}**",
        color=discord.Color.blue()
    )
    
    embed.add_field(name="🎵 Musiques Écoutées", value=f"{stats['songs_played']}", inline=True)
    embed.add_field(name="⏱️ Temps d'Écoute", value=f"{stats['time_listened']} minutes", inline=True)
    embed.add_field(name="❤️ Favoris", value=f"{len(stats['favorites'])}", inline=True)
    
    if stats['first_song']:
        embed.add_field(name="🎯 Première Musique", value=stats['first_song'][:30], inline=False)
    
    if stats['last_song']:
        embed.add_field(name="⏮️ Dernière Musique", value=stats['last_song'][:30], inline=False)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="top-songs", description="Affiche les musiques les plus populaires du serveur")
async def top_songs_command(interaction: discord.Interaction):
    """Affiche les musiques les plus écoutées sur le serveur"""
    guild_id = interaction.guild.id
    
    # Initialiser les statistiques si nécessaire
    if not hasattr(bot, 'server_music_stats'):
        bot.server_music_stats = {}
    
    if guild_id not in bot.server_music_stats:
        bot.server_music_stats[guild_id] = {}
    
    song_stats = bot.server_music_stats[guild_id]
    
    if not song_stats:
        embed = discord.Embed(
            title="📈 Aucune Statistique",
            description="Aucune musique n'a été écoutée sur ce serveur.",
            color=discord.Color.orange()
        )
        return await interaction.response.send_message(embed=embed)
    
    # Trier par nombre d'écoutes
    sorted_songs = sorted(song_stats.items(), key=lambda x: x[1], reverse=True)[:10]
    
    embed = discord.Embed(
        title="📈 Top Musiques du Serveur",
        description="Les musiques les plus écoutées sur ce serveur",
        color=discord.Color.gold()
    )
    
    for i, (song_title, count) in enumerate(sorted_songs, 1):
        embed.add_field(
            name=f"#{i} {song_title[:40]}{'...' if len(song_title) > 40 else ''}",
            value=f"🎵 Écoutée **{count}** fois",
            inline=False
        )
    
    await interaction.response.send_message(embed=embed)

# =================================:
# COMMANDES SOCIALES
# =================================:
@bot.tree.command(name="duel", description="Défie un autre utilisateur en musique")
@app_commands.describe(utilisateur="Utilisateur à défier")
async def duel_command(interaction: discord.Interaction, utilisateur: discord.Member):
    """Défie un autre utilisateur à un duel musical"""
    guild_id = interaction.guild.id
    
    if utilisateur == interaction.user:
        embed = discord.Embed(
            title="❌ Auto-défi Interdit",
            description="Tu ne peux pas te défier toi-même !",
            color=discord.Color.red()
        )
        return await interaction.response.send_message(embed=embed, ephemeral=True)
    
    # Initialiser les duels si nécessaire
    if not hasattr(bot, 'music_duels'):
        bot.music_duels = {}
    
    if guild_id not in bot.music_duels:
        bot.music_duels[guild_id] = {}
    
    # Vérifier si l'utilisateur est déjà dans un duel
    if interaction.user.id in bot.music_duels[guild_id]:
        embed = discord.Embed(
            title="⚔️ Duel en Cours",
            description="Tu es déjà dans un duel musical !",
            color=discord.Color.orange()
        )
        return await interaction.response.send_message(embed=embed, ephemeral=True)
    
    # Créer le duel
    duel_id = f"{interaction.user.id}-{utilisateur.id}"
    bot.music_duels[guild_id][duel_id] = {
        'challenger': interaction.user.id,
        'challenged': utilisateur.id,
        'challenger_score': 0,
        'challenged_score': 0,
        'round': 1,
        'active': True
    }
    
    embed = discord.Embed(
        title="⚔️ Défi Musical Lancé !",
        description=f"**{interaction.user.display_name}** défie **{utilisateur.display_name}** !\n\n{utilisateur.mention}, acceptes-tu le défi ?",
        color=discord.Color.red()
    )
    
    view = discord.ui.View()
    accept_btn = discord.ui.Button(label="Accepter", style=discord.ButtonStyle.green, emoji="✅")
    decline_btn = discord.ui.Button(label="Refuser", style=discord.ButtonStyle.red, emoji="❌")
    
    async def accept_callback(interaction: discord.Interaction):
        if interaction.user != utilisateur:
            await interaction.response.send_message("Tu ne peux pas accepter ce duel !", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="⚔️ Duel Accepté !",
            description=f"**{utilisateur.display_name}** a accepté le défi de **{interaction.user.display_name}** !\n\nLe duel commence maintenant !",
            color=discord.Color.green()
        )
        await interaction.response.edit_message(embed=embed, view=None)
        
        # Logique du duel (à implémenter)
        # Par exemple, jouer une musique et deviner le titre, etc.
    
    async def decline_callback(interaction: discord.Interaction):
        if interaction.user != utilisateur:
            await interaction.response.send_message("Tu ne peux pas refuser ce duel !", ephemeral=True)
            return
        
        # Supprimer le duel
        if duel_id in bot.music_duels[guild_id]:
            del bot.music_duels[guild_id][duel_id]
        
        embed = discord.Embed(
            title="❌ Défi Refusé",
            description=f"**{utilisateur.display_name}** a refusé le défi de **{interaction.user.display_name}**.",
            color=discord.Color.red()
        )
        await interaction.response.edit_message(embed=embed, view=None)
    
    accept_btn.callback = accept_callback
    decline_btn.callback = decline_callback
    
    view.add_item(accept_btn)
    view.add_item(decline_btn)
    
    await interaction.response.send_message(embed=embed, view=view)

@bot.tree.command(name="vote-skip", description="Lance un vote pour passer à la musique suivante")
async def vote_skip_command(interaction: discord.Interaction):
    """Lance un vote pour passer à la musique suivante"""
    guild_id = interaction.guild.id
    voice_client = voice_clients.get(guild_id)
    
    if not voice_client or not voice_client.is_playing():
        embed = discord.Embed(
            title="❌ Aucune Musique",
            description="Aucune musique n'est en train de jouer.",
            color=discord.Color.orange()
        )
        return await interaction.response.send_message(embed=embed)
    
    # Initialiser les sessions de vote si nécessaire
    if not hasattr(bot, 'vote_skip_sessions'):
        bot.vote_skip_sessions = {}
    
    if guild_id not in bot.vote_skip_sessions:
        bot.vote_skip_sessions[guild_id] = {}
    
    # Vérifier si un vote est déjà en cours
    if bot.vote_skip_sessions[guild_id].get('active', False):
        embed = discord.Embed(
            title="🗳️ Vote en Cours",
            description="Un vote pour passer la musique est déjà en cours !",
            color=discord.Color.orange()
        )
        return await interaction.response.send_message(embed=embed)
    
    # Compter le nombre d'utilisateurs dans le salon vocal
    voice_channel = voice_client.channel
    members_in_voice = [m for m in voice_channel.members if not m.bot]
    required_votes = max(2, len(members_in_voice) // 2 + 1)
    
    # Créer la session de vote
    bot.vote_skip_sessions[guild_id] = {
        'active': True,
        'votes': [interaction.user.id],
        'required': required_votes,
        'message_id': None
    }
    
    embed = discord.Embed(
        title="🗳️ Vote pour Passer",
        description=f"**{interaction.user.display_name}** a lancé un vote pour passer la musique actuelle.\n\n**{len(bot.vote_skip_sessions[guild_id]['votes'])}/{required_votes}** votes nécessaires",
        color=discord.Color.blue()
    )
    
    view = discord.ui.View()
    vote_btn = discord.ui.Button(label="Voter pour passer", style=discord.ButtonStyle.green, emoji="👍")
    
    async def vote_callback(interaction: discord.Interaction):
        if interaction.user.id in bot.vote_skip_sessions[guild_id]['votes']:
            await interaction.response.send_message("Tu as déjà voté !", ephemeral=True)
            return
        
        bot.vote_skip_sessions[guild_id]['votes'].append(interaction.user.id)
        current_votes = len(bot.vote_skip_sessions[guild_id]['votes'])
        
        if current_votes >= required_votes:
            # Vote réussi, passer la musique
            voice_client.stop()
            
            embed = discord.Embed(
                title="✅ Vote Réussi !",
                description="Le vote pour passer la musique a réussi ! Passage à la musique suivante...",
                color=discord.Color.green()
            )
            await interaction.response.edit_message(embed=embed, view=None)
            
            # Réinitialiser la session de vote
            bot.vote_skip_sessions[guild_id]['active'] = False
        else:
            # Mettre à jour le message
            embed = discord.Embed(
                title="🗳️ Vote pour Passer",
                description=f"**{current_votes}/{required_votes}** votes nécessaires",
                color=discord.Color.blue()
            )
            await interaction.response.edit_message(embed=embed)
    
    vote_btn.callback = vote_callback
    view.add_item(vote_btn)
    
    message = await interaction.response.send_message(embed=embed, view=view)
    bot.vote_skip_sessions[guild_id]['message_id'] = message.id

@bot.tree.command(name="song-request", description="Fais une demande de musique aux autres utilisateurs")
@app_commands.describe(titre="Titre de la musique demandée")
async def song_request_command(interaction: discord.Interaction, titre: str):
    """Fais une demande de musique aux autres utilisateurs"""
    guild_id = interaction.guild.id
    
    embed = discord.Embed(
        title="🎵 Demande de Musique",
        description=f"**{interaction.user.display_name}** demande la musique :\n\n**{titre}**",
        color=discord.Color.purple()
    )
    
    embed.add_field(name="💡 Comment aider", value="Si tu connais cette musique, envoie le lien YouTube dans le salon !", inline=False)
    embed.set_footer(text="Utilise /search pour trouver des musiques")
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="history", description="Affiche l'historique des musiques écoutées")
async def history_command(interaction: discord.Interaction):
    """Affiche l'historique des musiques écoutées par l'utilisateur"""
    guild_id = interaction.guild.id
    user_id = interaction.user.id
    
    # Initialiser l'historique si nécessaire
    if not hasattr(bot, 'music_history'):
        bot.music_history = {}
    
    if guild_id not in bot.music_history:
        bot.music_history[guild_id] = {}
    
    if user_id not in bot.music_history[guild_id]:
        bot.music_history[guild_id][user_id] = []
    
    history = bot.music_history[guild_id][user_id]
    
    if not history:
        embed = discord.Embed(
            title="📜 Aucun Historique",
            description="Tu n'as pas encore écouté de musique.",
            color=discord.Color.orange()
        )
        return await interaction.response.send_message(embed=embed)
    
    embed = discord.Embed(
        title="📜 Ton Historique Musical",
        description=f"Les dernières musiques écoutées par **{interaction.user.display_name}**",
        color=discord.Color.purple()
    )
    
    # Afficher les 10 dernières musiques
    for i, song_title in enumerate(history[-10:], 1):
        embed.add_field(
            name=f"#{i} {song_title[:40]}{'...' if len(song_title) > 40 else ''}",
            value=f"Écoutée récemment",
            inline=False
        )
    
    await interaction.response.send_message(embed=embed)

# =================================:
# COMMANDES D'ADMINISTRATION MUSICALE
# =================================:
@bot.tree.command(name="music-lock", description="Verrouille/déverrouille l'utilisation des commandes musicales")
@app_commands.describe(etat="Verrouiller ou déverrouiller")
async def music_lock_command(interaction: discord.Interaction, etat: str):
    """Verrouille ou déverrouille les commandes musicales"""
    guild_id = interaction.guild.id
    
    # Vérifier les permissions
    if not interaction.user.guild_permissions.administrator:
        embed = discord.Embed(
            title="❌ Permission Refusée",
            description="Tu dois être administrateur pour utiliser cette commande.",
            color=discord.Color.red()
        )
        return await interaction.response.send_message(embed=embed, ephemeral=True)
    
    etat = etat.lower()
    if etat not in ["verrouiller", "déverrouiller", "lock", "unlock"]:
        embed = discord.Embed(
            title="❌ État Invalide",
            description="Utilise : verrouiller, déverrouiller, lock ou unlock",
            color=discord.Color.red()
        )
        return await interaction.response.send_message(embed=embed)
    
    # Initialiser les verrous si nécessaire
    if not hasattr(bot, 'music_locks'):
        bot.music_locks = {}
    
    is_locked = etat in ["verrouiller", "lock"]
    bot.music_locks[guild_id] = is_locked
    
    if is_locked:
        embed = discord.Embed(
            title="🔒 Commandes Musicales Verrouillées",
            description="Seuls les administrateurs peuvent utiliser les commandes musicales.",
            color=discord.Color.orange()
        )
    else:
        embed = discord.Embed(
            title="🔓 Commandes Musicales Déverrouillées",
            description="Tout le monde peut utiliser les commandes musicales.",
            color=discord.Color.green()
        )
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="max-duration", description="Définit la durée maximale des musiques")
@app_commands.describe(minutes="Durée maximale en minutes")
async def max_duration_command(interaction: discord.Interaction, minutes: int):
    """Définit la durée maximale des musiques"""
    guild_id = interaction.guild.id
    
    # Vérifier les permissions
    if not interaction.user.guild_permissions.administrator:
        embed = discord.Embed(
            title="❌ Permission Refusée",
            description="Tu dois être administrateur pour utiliser cette commande.",
            color=discord.Color.red()
        )
        return await interaction.response.send_message(embed=embed, ephemeral=True)
    
    if minutes < 1 or minutes > 60:
        embed = discord.Embed(
            title="❌ Durée Invalide",
            description="La durée doit être entre 1 et 60 minutes.",
            color=discord.Color.red()
        )
        return await interaction.response.send_message(embed=embed)
    
    # Initialiser les durées maximales si nécessaire
    if not hasattr(bot, 'max_durations'):
        bot.max_durations = {}
    
    bot.max_durations[guild_id] = minutes * 60  # Convertir en secondes
    
    embed = discord.Embed(
        title="⏱️ Durée Maximale Définie",
        description=f"Les musiques ne pourront pas dépasser **{minutes} minutes**.",
        color=discord.Color.green()
    )
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="blacklist", description="Ajoute un mot à la liste noire")
@app_commands.describe(mot="Mot à blacklist")
async def blacklist_command(interaction: discord.Interaction, mot: str):
    """Ajoute un mot à la liste noire des titres"""
    guild_id = interaction.guild.id
    
    # Vérifier les permissions
    if not interaction.user.guild_permissions.administrator:
        embed = discord.Embed(
            title="❌ Permission Refusée",
            description="Tu dois être administrateur pour utiliser cette commande.",
            color=discord.Color.red()
        )
        return await interaction.response.send_message(embed=embed, ephemeral=True)
    
    mot = mot.lower()
    
    # Initialiser la liste noire si nécessaire
    if not hasattr(bot, 'music_blacklist'):
        bot.music_blacklist = {}
    
    if guild_id not in bot.music_blacklist:
        bot.music_blacklist[guild_id] = []
    
    if mot in bot.music_blacklist[guild_id]:
        embed = discord.Embed(
            title="⚠️ Déjà Blacklisté",
            description=f"Le mot **{mot}** est déjà dans la liste noire.",
            color=discord.Color.orange()
        )
        return await interaction.response.send_message(embed=embed)
    
    bot.music_blacklist[guild_id].append(mot)
    
    embed = discord.Embed(
        title="🚫 Mot Blacklisté",
        description=f"Le mot **{mot}** a été ajouté à la liste noire.\n\nLes musiques contenant ce mot ne seront pas jouées.",
        color=discord.Color.green()
    )
    
    await interaction.response.send_message(embed=embed)

# ==================================
# COMMANDE /musique (VERSION SLASH)
# ==================================
@bot.tree.command(name="musique", description="Joue une musique dans ton salon vocal")
@app_commands.describe(lien="Lien YouTube, Spotify, SoundCloud, etc.")
async def musique_command(interaction: discord.Interaction, lien: str):
    """Joue une musique dans le salon vocal"""
    guild_id = interaction.guild.id
    
    # Vérifier si l'utilisateur est dans un salon vocal
    if not interaction.user.voice or not interaction.user.voice.channel:
        embed = discord.Embed(
            title="❌ Salon Vocal Requis",
            description="Tu dois être dans un salon vocal pour que je puisse jouer de la musique !",
            color=discord.Color.orange()
        )
        return await interaction.response.send_message(embed=embed, ephemeral=True)
    
    try:
        # Initialiser la file d'attente si nécessaire
        if guild_id not in music_queues:
            music_queues[guild_id] = []
        
        # Extraire les informations de la musique
        song_info = extract_video_info(lien)
        if not song_info:
            embed = discord.Embed(
                title="❌ Erreur de Lecture",
                description="Impossible de lire ce lien. Vérifie qu'il s'agit d'un lien valide.",
                color=discord.Color.red()
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)
        
        # Vérifier si le bot est déjà connecté
        voice_client = voice_clients.get(guild_id)
        
        if not voice_client:
            # Rejoindre le salon vocal
            try:
                voice_client = await interaction.user.voice.channel.connect()
            except RuntimeError as e:
                if "PyNaCl library needed" in str(e):
                    embed = discord.Embed(
                        title="❌ Bibliothèque Manquante",
                        description="La bibliothèque PyNaCl est requise pour les fonctionnalités vocales. Contacte l'administrateur du bot.",
                        color=discord.Color.red()
                    )
                    return await interaction.response.send_message(embed=embed, ephemeral=True)
                else:
                    raise e
            voice_clients[guild_id] = voice_client
            
            # Ajouter à la file d'attente et jouer
            music_queues[guild_id].append(song_info)
            success = await play_music(guild_id, voice_client, song_info)
            
            if success:
                embed = discord.Embed(
                    title="🎵 Musique Lancée !",
                    description=f"Je rejoint **{interaction.user.voice.channel.name}** et je joue :\n**{song_info['title']}**",
                    color=discord.Color.green()
                )
                if song_info.get('thumbnail'):
                    embed.set_thumbnail(url=song_info['thumbnail'])
                embed.add_field(name="⏱️ Durée", value=f"{song_info.get('duration', 0)} secondes", inline=True)
                embed.add_field(name="👤 Artiste", value=song_info.get('uploader', 'Inconnu'), inline=True)
                await interaction.response.send_message(embed=embed)
            else:
                embed = discord.Embed(
                    title="❌ Erreur de Lecture",
                    description="Impossible de lire cette musique.",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
            
        else:
            # Ajouter à la file d'attente
            music_queues[guild_id].append(song_info)
            
            embed = discord.Embed(
                title="🎵 Ajoutée à la File d'Attente",
                description=f"**{song_info['title']}** a été ajoutée à la file d'attente.\nPosition : {len(music_queues[guild_id])}",
                color=discord.Color.blue()
            )
            if song_info.get('thumbnail'):
                embed.set_thumbnail(url=song_info['thumbnail'])
            await interaction.response.send_message(embed=embed)
            
    except Exception as e:
        print(f"Erreur musique: {e}")
        embed = discord.Embed(
            title="❌ Erreur Technique",
            description="Une erreur est survenue lors de la lecture de la musique. Réessaie plus tard.",
            color=discord.Color.red()
        )
        if not interaction.response.is_done():
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await interaction.followup.send(embed=embed, ephemeral=True)

@bot.listen('on_message')
async def on_message_music(message):
    # ... (code existant)
    if message.author.bot:
        return
    
    guild_id = message.guild.id
    
    # Vérifier si le salon est configuré pour la musique
    if guild_id not in music_channels:
        # Charger depuis les données si pas en mémoire
        if str(guild_id) in data.get("config", {}) and "music_channel" in data["config"][str(guild_id)]:
            music_channels[guild_id] = data["config"][str(guild_id)]["music_channel"]
        else:
            return
    
    # Vérifier si le message est dans le bon salon
    if message.channel.id != music_channels[guild_id]:
        return
    
    # Vérifier si le message contient "skip" pour passer à la musique suivante
    if message.content.lower().strip() == "skip":
        voice_client = voice_clients.get(guild_id)
        
        # Vérifier si le bot est connecté
        if not voice_client:
            embed = discord.Embed(
                title="❌ Bot Non Connecté",
                description="Je ne suis pas dans un salon vocal.",
                color=discord.Color.orange()
            )
            await message.reply(embed=embed, mention_author=False)
            return
        
        # Vérifier si quelque chose est en train de jouer
        if not voice_client.is_playing():
            embed = discord.Embed(
                title="❌ Aucune Musique en Lecture",
                description="Aucune musique n'est en train de jouer.",
                color=discord.Color.orange()
            )
            await message.reply(embed=embed, mention_author=False)
            return
        
        # Vérifier s'il y a une musique suivante
        if guild_id not in music_queues or not music_queues[guild_id]:
            embed = discord.Embed(
                title="❌ File d'Attente Vide",
                description="Il n'y a pas de musique suivante dans la file d'attente.",
                color=discord.Color.orange()
            )
            await message.reply(embed=embed, mention_author=False)
            return
        
        # Arrêter la musique actuelle (play_next_song sera appelé automatiquement)
        voice_client.stop()
        
        embed = discord.Embed(
            title="⏭️ Musique Passée",
            description="Passage à la musique suivante...",
            color=discord.Color.green()
        )
        await message.reply(embed=embed, mention_author=False)
        return
    
    # Vérifier si le message contient un lien de musique et l'extraire
    music_url = extract_music_url(message.content)
    if not music_url:
        return
    
    # Vérifier si l'utilisateur est dans un salon vocal
    if not message.author.voice or not message.author.voice.channel:
        embed = discord.Embed(
            title="❌ Salon Vocal Requis",
            description="Tu dois être dans un salon vocal pour que je puisse jouer de la musique !",
            color=discord.Color.orange()
        )
        await message.reply(embed=embed, mention_author=False)
        return
    
    try:
        # Initialiser la file d'attente si nécessaire
        if guild_id not in music_queues:
            music_queues[guild_id] = []
        
        # Extraire les informations de la musique
        song_info = extract_video_info(music_url)
        if not song_info:
            embed = discord.Embed(
                title="❌ Erreur de Lecture",
                description="Impossible de lire ce lien. Vérifie qu'il s'agit d'un lien valide.",
                color=discord.Color.red()
            )
            await message.reply(embed=embed, mention_author=False)
            return
        
        # Vérifier si le bot est déjà connecté
        voice_client = voice_clients.get(guild_id)
        
        if not voice_client:
            # Rejoindre le salon vocal
            try:
                voice_client = await message.author.voice.channel.connect()
            except RuntimeError as e:
                if "PyNaCl library needed" in str(e):
                    embed = discord.Embed(
                        title="❌ Bibliothèque Manquante",
                        description="La bibliothèque PyNaCl est requise pour les fonctionnalités vocales. Contacte l'administrateur du bot.",
                        color=discord.Color.red()
                    )
                    await message.reply(embed=embed, mention_author=False)
                    return
                else:
                    raise e
            voice_clients[guild_id] = voice_client
            
            # Ajouter à la file d'attente et jouer
            music_queues[guild_id].append(song_info)
            await play_music(guild_id, voice_client, song_info)
            
            embed = discord.Embed(
                title="🎵 Musique Lancée !",
                description=f"Je rejoint **{message.author.voice.channel.name}** et je joue :\n**{song_info['title']}**",
                color=discord.Color.green()
            )
            if song_info.get('thumbnail'):
                embed.set_thumbnail(url=song_info['thumbnail'])
            embed.add_field(name="⏱️ Durée", value=f"{song_info.get('duration', 0)} secondes", inline=True)
            embed.add_field(name="👤 Artiste", value=song_info.get('uploader', 'Inconnu'), inline=True)
            await message.reply(embed=embed, mention_author=False)
            
        else:
            # Ajouter à la file d'attente
            music_queues[guild_id].append(song_info)
            
            embed = discord.Embed(
                title="🎵 Ajoutée à la File d'Attente",
                description=f"**{song_info['title']}** a été ajoutée à la file d'attente.\nPosition : {len(music_queues[guild_id])}",
                color=discord.Color.blue()
            )
            if song_info.get('thumbnail'):
                embed.set_thumbnail(url=song_info['thumbnail'])
            await message.reply(embed=embed, mention_author=False)
            
    except Exception as e:
        print(f"Erreur musique: {e}")
        embed = discord.Embed(
            title="❌ Erreur Technique",
            description="Une erreur est survenue lors de la lecture de la musique. Réessaie plus tard.",
            color=discord.Color.red()
        )
        await message.reply(embed=embed, mention_author=False)

# ==================================
# LISTE DES STATUTS DU BOT
# ==================================
STATUS_LIST = [
    "💰 Récupère ton /daily !",
    "🎯 Fais tes /quests quotidiennes",
    "🧠 Discute dans le salon IA",
    "🛠️ En développement constant...",
    "🛠️ Version 3.1.0",
    "🌍 {guild_count} serveurs connectés"
]

# Un compteur pour suivre l'index de la liste
status_index = 0

@tasks.loop(seconds=30)  # Réduit à 30 secondes pour éviter les erreurs de rate limit
async def change_status():
    global status_index
    
    try:
        # Vérifier si le bot est prêt avant de continuer
        if not bot.is_ready():
            return
            
        # Construction du statut avec l'information dynamique du nombre de serveurs
        current_status = STATUS_LIST[status_index % len(STATUS_LIST)]
        if "{guild_count}" in current_status:
            current_status = current_status.format(guild_count=len(bot.guilds))

        # Changement du statut avec gestion d'erreur
        try:
            await bot.change_presence(activity=discord.Game(name=current_status))
        except Exception as e:
            # Ne pas afficher l'erreur si c'est une déconnexion en cours
            if not isinstance(e, (discord.errors.ConnectionClosed, 
                               discord.errors.HTTPException, 
                               aiohttp.ClientConnectionError)):
                print(f"Erreur lors du changement de statut: {type(e).__name__}: {e}")
            return

        # Incrémentation de l'index pour le prochain statut
        status_index = (status_index + 1) % len(STATUS_LIST)
        
    except Exception as e:
        print(f"Erreur dans la boucle de changement de statut: {type(e).__name__}: {e}")
        # En cas d'erreur, on attend un peu avant de réessayer
        await asyncio.sleep(10)
    
# ==================================
# 🌐 ÉVÉNEMENT ON_READY (MISE À JOUR)
# ==================================
@bot.event
async def on_ready():
    print(f"✅ {bot.user.name} est en ligne !")
    print(f"📊 Prêt sur {len(bot.guilds)} serveurs")
    print("🎵 Système musical activé")
    
    # Démarrer la tâche de vérification du salon vocal
    bot.loop.create_task(voice_check_task())
    
    await bot.change_presence(
        activity=discord.Game(name=f"Démarrage...")
    )
    
    # 2. SYNCHRONISATION DES COMMANDES SLASH
    try:
        synced = await bot.tree.sync()
        bot.add_view(TicketButton())
        print(f"✅ Synchronisation Slash Commands réussie. ({len(synced)} commandes)")
    except Exception as e:
        print(f"❌ Erreur lors de la synchronisation des Slash Commands : {e}")
        
    # 3. DÉMARRAGE DE LA BOUCLE DE STATUT (NOUVEAU)
    change_status.start()
    print(f"✅ Boucle de statut démarrée.")

    # 4. Récupération du salon de statut (si configuré)
    channel = bot.get_channel(STATUS_CHANNEL_ID)
    
    # 5. Envoi du message de démarrage dans le salon de statut
    try:
        if channel:
            # Création de l'embed de notification de démarrage
            startup_embed = discord.Embed(
                title="🟢 Bôt Démarré et Prêt",
                description=f"Le bot **{bot.user.name}** a été redémarré avec succès et toutes les fonctionnalités sont actives.",
                color=discord.Color.green()
            )
            # Ajout d'un horodatage précis (UTC)
            startup_embed.timestamp = datetime.datetime.now(datetime.timezone.utc)
            
            # Envoi du message dans le salon ciblé
            await channel.send(embed=startup_embed)
            print(f'✅ Message de démarrage envoyé dans le salon {channel.name}.')
        else:
            print(f"❌ Avertissement: Le salon ID {STATUS_CHANNEL_ID} n'a pas été trouvé ou n'est pas accessible.")

    except discord.Forbidden:
        # Gère l'erreur de permission
        print(f"❌ Erreur: Permissions insuffisantes pour envoyer un message dans le salon ID {STATUS_CHANNEL_ID}.")
    except Exception as e:
        # Gère toute autre erreur inattendue
        print(f"❌ Erreur inattendue lors de l'envoi du message de démarrage : {e}")
        
    # LIGNE DE STATUT FINALE (ANCIENNE) SUPPRIMÉE: Elle est gérée par change_status.start

async def voice_check_task():
    """Tâche de fond qui vérifie périodiquement si le bot est seul dans les salons vocaux"""
    await bot.wait_until_ready()
    
    while not bot.is_closed():
        try:
            # Parcourir tous les clients vocaux actifs
            for guild_id, voice_client in list(voice_clients.items()):
                await check_alone_in_voice(guild_id)
            
            # Attendre 30 secondes avant la prochaine vérification
            await asyncio.sleep(30)
        except Exception as e:
            print(f"Erreur dans voice_check_task: {e}")
            await asyncio.sleep(30)
# ==================================
# COMMANDE /kick
# ==================================
@bot.tree.command(name="kick", description="[STAFF] Exclut un membre du serveur.")
@app_commands.describe(
    membre="Le membre à exclure.",
    raison="La raison de l'exclusion (optionnel)."
)
@checks.has_permissions(kick_members=True)
async def kick_slash(interaction: discord.Interaction, membre: discord.Member, raison: str = "Aucune raison spécifiée."):

    # 1. Vérification des permissions
    # Empêche de kicker le bot, le propriétaire du serveur, ou un membre de rang supérieur
    if membre == interaction.user:
        return await interaction.response.send_message("❌ Vous ne pouvez pas vous exclure vous-même !", ephemeral=True)
    if membre.top_role >= interaction.user.top_role and membre != interaction.user:
        return await interaction.response.send_message("❌ Vous ne pouvez pas exclure un membre ayant un rôle égal ou supérieur au vôtre.", ephemeral=True)
    if not membre.kickable:
        return await interaction.response.send_message("❌ Je n'ai pas la permission ou le rôle requis pour exclure ce membre.", ephemeral=True)

    # 2. Exécution de l'action
    try:
        # Envoie un DM au membre pour l'informer (si possible)
        try:
            dm_embed = discord.Embed(
                title="🚪 Vous avez été exclu(e)",
                description=f"Serveur : **{interaction.guild.name}**\nRaison : **{raison}**\nModérateur : **{interaction.user.name}**",
                color=discord.Color.orange()
            )
            await membre.send(embed=dm_embed)
        except:
            # Si le DM échoue, continuer l'action
            pass
            
        await membre.kick(reason=raison)
        
        # 3. Réponse de confirmation
        embed = discord.Embed(
            title="✅ Membre Exclu (Kick)",
            description=f"**{membre.display_name}** a été exclu du serveur.\n**Raison :** {raison}",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed)

    except discord.Forbidden:
        await interaction.response.send_message("❌ **Permission Bot Refusée :** Le bot n'a pas la permission `Kick Members`.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ Une erreur inattendue s'est produite : `{e}`", ephemeral=True)

# Gère l'erreur de permission pour les utilisateurs non autorisés
@kick_slash.error
async def kick_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, checks.MissingPermissions):
        await interaction.response.send_message("❌ **Accès Refusé :** Vous devez avoir la permission `Exclure des membres` pour utiliser cette commande.", ephemeral=True)
    else:
        # Laisse passer les autres erreurs à la gestion standard
        raise error
        
# ==================================
# 🛡️ COMMANDE /ban
# ==================================
@bot.tree.command(name="ban", description="[STAFF] Bannit un membre du serveur.")
@app_commands.describe(
    membre="Le membre à bannir.",
    raison="La raison du bannissement (optionnel)."
)
# Vérifie si l'utilisateur qui exécute la commande a la permission 'ban_members'
@checks.has_permissions(ban_members=True)
async def ban_slash(interaction: discord.Interaction, membre: discord.Member, raison: str = "Aucune raison spécifiée."):
    
    # 1. Vérification des permissions
    if membre == interaction.user:
        return await interaction.response.send_message("❌ Vous ne pouvez pas vous bannir vous-même !", ephemeral=True)
    if membre.top_role >= interaction.user.top_role and membre != interaction.user:
        return await interaction.response.send_message("❌ Vous ne pouvez pas bannir un membre ayant un rôle égal ou supérieur au vôtre.", ephemeral=True)
    if not membre.bannable:
        return await interaction.response.send_message("❌ Je n'ai pas la permission ou le rôle requis pour bannir ce membre.", ephemeral=True)

    # 2. Exécution de l'action
    try:
        # Envoie un DM au membre pour l'informer (si possible)
        try:
            dm_embed = discord.Embed(
                title="🔨 Vous avez été banni(e)",
                description=f"Serveur : **{interaction.guild.name}**\nRaison : **{raison}**\nModérateur : **{interaction.user.name}**",
                color=discord.Color.red()
            )
            await membre.send(embed=dm_embed)
        except:
            # Si le DM échoue, continuer l'action
            pass
            
        await membre.ban(reason=raison)
        
        # 3. Réponse de confirmation
        embed = discord.Embed(
            title="✅ Membre Banni (Ban)",
            description=f"**{membre.display_name}** a été banni du serveur.\n**Raison :** {raison}",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed)

    except discord.Forbidden:
        await interaction.response.send_message("❌ **Permission Bot Refusée :** Le bot n'a pas la permission `Ban Members`.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ Une erreur inattendue s'est produite : `{e}`", ephemeral=True)

# Gère l'erreur de permission pour les utilisateurs non autorisés
@ban_slash.error
async def ban_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, checks.MissingPermissions):
        await interaction.response.send_message("❌ **Accès Refusé :** Vous devez avoir la permission `Bannir des membres` pour utiliser cette commande.", ephemeral=True)
    else:
        # Laisse passer les autres erreurs à la gestion standard
        raise error
        
# ==================================
# 🛡️ COMMANDE /mute
# ==================================
# NOTE: Discord limite la durée du timeout à 28 jours (2419200 secondes).
@bot.tree.command(name="mute", description="[STAFF] Empêche un membre de parler pendant une durée spécifiée (timeout).")
@app_commands.describe(
    membre="Le membre à mettre en timeout.",
    duree_minutes="La durée du timeout en minutes (max 28 jours).",
    raison="La raison du timeout (optionnel)."
)
# Permission requise pour utiliser le timeout
@checks.has_permissions(moderate_members=True)
async def mute_slash(interaction: discord.Interaction, membre: discord.Member, duree_minutes: int, raison: str = "Aucune raison spécifiée."):
    
    # 1. Vérifications de base
    if membre == interaction.user:
        return await interaction.response.send_message("❌ Vous ne pouvez pas vous mute vous-même.", ephemeral=True)
    if membre.top_role >= interaction.user.top_role and membre != interaction.user:
        return await interaction.response.send_message("❌ Vous ne pouvez pas mute un membre ayant un rôle égal ou supérieur au vôtre.", ephemeral=True)
    if not membre.guild_permissions.moderate_members:
        # Vérifie que le bot peut effectuer des actions de modération sur la cible
        pass

    # 2. Calcul de la durée du timeout
    
    # Conversion en timedelta
    if duree_minutes <= 0:
        return await interaction.response.send_message("❌ La durée doit être supérieure à 0 minute.", ephemeral=True)
        
    try:
        duration = datetime.timedelta(minutes=duree_minutes)
    except OverflowError:
        return await interaction.response.send_message("❌ La durée spécifiée est trop longue (max 28 jours).", ephemeral=True)

    # Vérification de la limite Discord (28 jours)
    MAX_DURATION = datetime.timedelta(days=28)
    if duration > MAX_DURATION:
        return await interaction.response.send_message("❌ Discord ne permet pas de mute pour plus de 28 jours.", ephemeral=True)

    # 3. Exécution de l'action
    try:
        # Applique le timeout au membre
        await membre.timeout(duration, reason=raison)
        
        # 4. Réponse de confirmation (DM et canal)
        
        # Envoi d'un DM au membre (si possible)
        try:
            dm_embed = discord.Embed(
                title="🔇 Vous avez été mis(e) en Timeout",
                description=f"Serveur : **{interaction.guild.name}**\nDurée : **{duree_minutes} minutes**\nRaison : **{raison}**\nModérateur : **{interaction.user.name}**",
                color=discord.Color.dark_orange()
            )
            await membre.send(embed=dm_embed)
        except:
            pass
            
        # Réponse dans le canal
        embed = discord.Embed(
            title="✅ Membre Mute (Timeout)",
            description=f"**{membre.display_name}** est en timeout pour **{duree_minutes} minutes**.\n**Raison :** {raison}",
            color=discord.Color.dark_orange()
        )
        await interaction.response.send_message(embed=embed)

    except discord.Forbidden:
        await interaction.response.send_message("❌ **Permission Bot Refusée :** Le bot n'a pas la permission `Modérer les membres`.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ Une erreur inattendue s'est produite lors du mute : `{e}`", ephemeral=True)

# Gère l'erreur de permission pour les utilisateurs non autorisés
@mute_slash.error
async def mute_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, checks.MissingPermissions):
        await interaction.response.send_message("❌ **Accès Refusé :** Vous devez avoir la permission `Modérer les membres` pour utiliser cette commande.", ephemeral=True)
    else:
        raise error
        
# ==================================
# 🛡️ COMMANDE /warn
# ==================================
@bot.tree.command(name="warn", description="[STAFF] Envoie un avertissement officiel à un membre (sans stockage).")
@app_commands.describe(
    membre="Le membre à avertir.",
    raison="La raison de l'avertissement."
)
# Permission requise: Modérer les membres
@checks.has_permissions(moderate_members=True)
async def warn_slash(interaction: discord.Interaction, membre: discord.Member, raison: str):
    
    # 1. Vérifications
    if membre == interaction.user:
        return await interaction.response.send_message("❌ Vous ne pouvez pas vous avertir vous-même.", ephemeral=True)
    if membre.bot:
        return await interaction.response.send_message("❌ Vous ne pouvez pas avertir un bot.", ephemeral=True)
    if membre.top_role >= interaction.user.top_role:
        return await interaction.response.send_message("❌ Vous ne pouvez pas avertir un membre ayant un rôle égal ou supérieur au vôtre.", ephemeral=True)

    # 2. Exécution de l'action
    
    # Envoi du message privé (DM)
    try:
        dm_embed = discord.Embed(
            title="🚨 Avertissement Officiel du Serveur",
            description=f"Vous avez reçu un avertissement sur le serveur **{interaction.guild.name}**.\n\n**Raison :** **{raison}**\n\n**Ceci est un avertissement. Veuillez lire les règles pour éviter d'autres sanctions.**",
            color=discord.Color.red()
        )
        dm_embed.set_footer(text=f"Avertissement émis par : {interaction.user.display_name}")
        await membre.send(embed=dm_embed)
        dm_status = "✅ Message Privé (DM) envoyé."
    except:
        dm_status = "❌ Échec de l'envoi du Message Privé (DM)."

    # 3. Réponse de confirmation (Public)
    
    embed = discord.Embed(
        title="⚠️ Avertissement Émis",
        description=f"L'utilisateur **{membre.display_name}** a été averti.\n**Raison :** {raison}",
        color=discord.Color.orange()
    )
    embed.add_field(name="Statut du DM", value=dm_status, inline=False)
    
    # Réponse dans le canal public
    await interaction.response.send_message(embed=embed)

# Gère l'erreur de permission pour les utilisateurs non autorisés
@warn_slash.error
async def warn_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, checks.MissingPermissions):
        await interaction.response.send_message("❌ **Accès Refusé :** Vous devez avoir la permission `Modérer les membres` pour utiliser cette commande.", ephemeral=True)
    else:
        # Laisse passer les autres erreurs à la gestion standard
        raise error

        
# ==================================
# ⚙️ COMMANDES ADMINISTRATION ÉVÉNEMENT
# ==================================
@bot.tree.command(name="seteventmode", description="[ADMIN] Active/Désactive un événement spécial (Nexus Day) et les multiplicateurs de crédits.")
@app_commands.describe(etat_ia="Activer ou désactiver l'IA illimitée pour tous (Nexus Day).", multiplicateur_credits="Définir le multiplicateur pour les crédits gagnés (Ex: 2.0 pour doubler).")
async def set_event_mode(interaction: discord.Interaction, etat_ia: bool, multiplicateur_credits: float):
    # Vérification de l'administrateur
    if interaction.user.id != OWNER_ID:
        await interaction.response.send_message("❌ **Accès Refusé :** Seul l'administrateur principal peut utiliser cette commande.", ephemeral=True)
        return

    # Mettre à jour les variables globales (accès depuis le module)
    global EVENT_MODE_ENABLED
    global CREDIT_BOOST_MULTIPLIER
    
    EVENT_MODE_ENABLED = etat_ia
    CREDIT_BOOST_MULTIPLIER = multiplicateur_credits

    # Construction de l'embed de confirmation
    if EVENT_MODE_ENABLED:
        statut_ia = "✅ **ACTIF** (IA illimitée pour tous !)"
    else:
        statut_ia = "❌ **INACTIF** (Mode normal)"
        
    embed = discord.Embed(
        title="⚙️ Mode Événement Mis à Jour",
        color=discord.Color.gold(),
        timestamp=datetime.datetime.now()
    )
    embed.add_field(name="Mode IA Illimitée (Nexus Day)", value=statut_ia, inline=False)
    embed.add_field(name="Multiplicateur de Crédits", value=f"x{CREDIT_BOOST_MULTIPLIER:.1f}", inline=False)
    embed.set_footer(text=f"Mis à jour par {interaction.user.name}")

    await interaction.response.send_message(embed=embed)
    
# ==================================
# 👑 COMMANDES D'ADMINISTRATION (OWNER)
# ==================================

@bot.command(name="addcredits")
@commands.is_owner()
async def add_credits(ctx, user: discord.Member, amount: int):
    """[OWNER] Ajoute manuellement des crédits IA à un utilisateur."""
    if amount <= 0:
        return await ctx.send("❌ Le montant doit être supérieur à zéro.")

    user_id = str(user.id)
    # Assure l'existence de l'utilisateur dans la base de données
    ensure_user(user_id) 
    
    # Ajout des crédits IA (la clé 'credits' a été confirmée dans ensure_user)
    data[user_id]["credits"] += amount
    save_data()
    
    await ctx.send(f"✅ **Succès :** **{amount} Crédits IA** ajoutés à **{user.display_name}**.")
    
    # Notification à l'utilisateur
    try:
        await user.send(f"🎉 **Bonus Crédit IA :** Vous avez reçu **{amount} Crédits IA** de la part de l'équipe de Nexus AI pour votre parrainage réussi !")
    except:
        # Échoue silencieusement si les DMs sont désactivés
        pass
        
# ==================================
# 🛡️ COMMANDE /unban
# ==================================
@bot.tree.command(name="unban", description="[STAFF] Lève le bannissement d'un utilisateur via son ID Discord.")
@app_commands.describe(
    user_id="L'ID Discord de l'utilisateur à débannir.",
    raison="La raison du débannissement (optionnel)."
)
# Permission requise: Bannir des membres
@checks.has_permissions(ban_members=True)
async def unban_slash(interaction: discord.Interaction, user_id: str, raison: str = "Aucune raison spécifiée."):
    guild = interaction.guild
    
    # 1. Vérification de l'ID
    try:
        # Tente de convertir l'ID en entier
        user_id_int = int(user_id)
    except ValueError:
        return await interaction.response.send_message("❌ **ID Invalide :** L'ID doit être un nombre.", ephemeral=True)

    # 2. Exécution de l'action
    try:
        # Récupère l'objet User à partir de l'ID (même s'il n'est pas dans le serveur)
        user = await bot.fetch_user(user_id_int)
        
        # Débannissement
        await guild.unban(user, reason=raison)
        
        # 3. Réponse de confirmation
        embed = discord.Embed(
            title="✅ Bannissement Levée (Unban)",
            description=f"L'utilisateur **{user.name}** (`{user_id_int}`) n'est plus banni du serveur.\n**Raison :** {raison}",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed)

    except discord.NotFound:
        # Se produit si l'utilisateur n'est pas banni (ou si l'ID n'existe pas)
        await interaction.response.send_message(f"❌ **Non banni :** L'ID `{user_id_int}` n'est pas (ou plus) banni de ce serveur.", ephemeral=True)
    except discord.Forbidden:
        await interaction.response.send_message("❌ **Permission Bot Refusée :** Le bot n'a pas la permission `Bannir des membres`.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ Une erreur inattendue s'est produite : `{e}`", ephemeral=True)

# Gère l'erreur de permission pour les utilisateurs non autorisés
@unban_slash.error
async def unban_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, checks.MissingPermissions):
        await interaction.response.send_message("❌ **Accès Refusé :** Vous devez avoir la permission `Bannir des membres` pour utiliser cette commande.", ephemeral=True)
    else:
        raise error
        
# ==================================
# ⚙️ COMMANDE /purge
# ==================================
@bot.tree.command(name="purge", description="[STAFF] Supprime un nombre spécifié de messages dans le canal (max 100).")
@app_commands.describe(
    nombre="Le nombre de messages à supprimer (entre 1 et 100).",
)
# Permission requise: Gérer les messages
@checks.has_permissions(manage_messages=True)
async def purge_slash(interaction: discord.Interaction, nombre: int):
    
    # 1. Vérification du nombre
    if nombre < 1 or nombre > 100:
        return await interaction.response.send_message("❌ **Nombre Invalide :** Vous devez spécifier un nombre entre 1 et 100.", ephemeral=True)

    # 2. Exécution de l'action
    try:
        # La suppression doit inclure la commande elle-même, donc on ajoute 1 au count
        deleted = await interaction.channel.purge(limit=nombre + 1)
        
        # 3. Réponse de confirmation (éphémère)
        # On utilise interaction.followup.send pour éviter une erreur car purge n'est pas une réponse d'interaction
        # et pour envoyer le message après l'exécution de la purge
        
        # Réponse rapide, qui sera supprimée après 5 secondes
        await interaction.response.send_message(
            f"✅ **Nettoyage terminé :** **{len(deleted) - 1}** messages supprimés dans ce canal.",
            ephemeral=True,
            delete_after=5
        )

    except discord.Forbidden:
        await interaction.response.send_message("❌ **Permission Bot Refusée :** Le bot n'a pas la permission `Gérer les messages`.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ Une erreur inattendue s'est produite lors du purge : `{e}`", ephemeral=True)

# Gère l'erreur de permission pour les utilisateurs non autorisés
@purge_slash.error
async def purge_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, checks.MissingPermissions):
        await interaction.response.send_message("❌ **Accès Refusé :** Vous devez avoir la permission `Gérer les messages` pour utiliser cette commande.", ephemeral=True)
    else:
        raise error
        
# ==================================
# ⚙️ COMMANDE /lock
# ==================================
@bot.tree.command(name="lock", description="[STAFF] Verrouille le canal pour empêcher les messages.")
@app_commands.describe(
    canal="Le canal à verrouiller (laisse vide pour le canal actuel)."
)
# Permission requise: Gérer les canaux
@checks.has_permissions(manage_channels=True)
async def lock_slash(interaction: discord.Interaction, canal: discord.TextChannel = None):
    # Utilise le canal actuel si aucun n'est spécifié
    target_channel = canal if canal else interaction.channel
    
    # Récupère le rôle @everyone
    everyone_role = interaction.guild.default_role
    
    # Définition de la permission: Interdire l'envoi de messages
    overwrites = target_channel.overwrites_for(everyone_role)
    
    # Vérifie si le canal est déjà verrouillé
    if overwrites.send_messages is False:
        return await interaction.response.send_message(f"❌ Le canal {target_channel.mention} est déjà verrouillé.", ephemeral=True)

    try:
        # Applique la modification: Interdire l'envoi de messages
        overwrites.send_messages = False
        await target_channel.set_permissions(everyone_role, overwrite=overwrites, reason=f"Verrouillé par {interaction.user.name}")
        
        # Réponse de confirmation
        embed = discord.Embed(
            title="🔒 Canal Verrouillé",
            description=f"Le canal {target_channel.mention} a été verrouillé par **{interaction.user.display_name}**.\nPersonne (sauf le Staff) ne peut envoyer de messages.",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed)
        
    except discord.Forbidden:
        await interaction.response.send_message("❌ **Permission Bot Refusée :** Je n'ai pas la permission de modifier les canaux.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ Une erreur inattendue s'est produite : `{e}`", ephemeral=True)

# Gère l'erreur de permission pour les utilisateurs non autorisés
@lock_slash.error
async def lock_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, checks.MissingPermissions):
        await interaction.response.send_message("❌ **Accès Refusé :** Vous devez avoir la permission `Gérer les canaux` pour verrouiller.", ephemeral=True)
    else:
        raise error
        
# ==================================
# ⚙️ COMMANDE /unlock
# ==================================
@bot.tree.command(name="unlock", description="[STAFF] Déverrouille le canal pour autoriser les messages.")
@app_commands.describe(
    canal="Le canal à déverrouiller (laisse vide pour le canal actuel)."
)
# Permission requise: Gérer les canaux
@checks.has_permissions(manage_channels=True)
async def unlock_slash(interaction: discord.Interaction, canal: discord.TextChannel = None):
    # Utilise le canal actuel si aucun n'est spécifié
    target_channel = canal if canal else interaction.channel
    
    # Récupère le rôle @everyone
    everyone_role = interaction.guild.default_role
    
    # Définition de la permission: Autoriser l'envoi de messages
    overwrites = target_channel.overwrites_for(everyone_role)
    
    # Vérifie si le canal n'est pas déjà déverrouillé (ou neutre)
    if overwrites.send_messages is None or overwrites.send_messages is True:
        return await interaction.response.send_message(f"❌ Le canal {target_channel.mention} n'est pas actuellement verrouillé (ou la permission est neutre).", ephemeral=True)

    try:
        # Applique la modification: Rétablir l'envoi de messages (rôle @everyone)
        # NOTE: Mettre None retire l'overwrite et revient aux permissions de base du rôle.
        # Nous allons mettre True pour s'assurer que l'overwrite est bien actif si les permissions de base ne sont pas suffisantes.
        overwrites.send_messages = True 
        await target_channel.set_permissions(everyone_role, overwrite=overwrites, reason=f"Déverrouillé par {interaction.user.name}")
        
        # Réponse de confirmation
        embed = discord.Embed(
            title="🔓 Canal Déverrouillé",
            description=f"Le canal {target_channel.mention} a été déverrouillé par **{interaction.user.display_name}**.\nLes membres peuvent à nouveau envoyer des messages.",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed)
        
    except discord.Forbidden:
        await interaction.response.send_message("❌ **Permission Bot Refusée :** Je n'ai pas la permission de modifier les canaux.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ Une erreur inattendue s'est produite : `{e}`", ephemeral=True)

# Gère l'erreur de permission pour les utilisateurs non autorisés
@unlock_slash.error
async def unlock_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, checks.MissingPermissions):
        await interaction.response.send_message("❌ **Accès Refusé :** Vous devez avoir la permission `Gérer les canaux` pour déverrouiller.", ephemeral=True)
    else:
        await interaction.response.send_message(f"⚠️ Une erreur est survenue : {error}", ephemeral=True)

# ==================================
# 🎉 COMMANDE /giveway
# ==================================

# Stockage des giveaways actifs
active_giveaways = {}

class GiveawayView(discord.ui.View):
    def __init__(self, giveaway_id: str):
        super().__init__(timeout=None)
        self.giveaway_id = giveaway_id
        self.participants = set()
        
    @discord.ui.button(label="🎉 Participer", style=discord.ButtonStyle.green, custom_id="giveaway_join")
    async def join_giveaway(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = str(interaction.user.id)
        
        # Vérifier si le giveaway est toujours actif
        if self.giveaway_id not in active_giveaways:
            button.disabled = True
            button.label = "⏰ Terminé"
            await interaction.response.edit_message(view=self)
            return
        
        # Vérifier si l'utilisateur participe déjà
        if user_id in self.participants:
            return await interaction.response.send_message("⚠️ Vous participez déjà à ce giveaway !", ephemeral=True)
        
        giveaway_data = active_giveaways[self.giveaway_id]
        condition_type = giveaway_data.get("condition_type", "aucun")
        condition_amount = giveaway_data.get("condition_amount", 0)
        
        # Vérifier les conditions
        if condition_type == "credits":
            ensure_user(user_id)
            user_data = data[user_id]
            if user_data.get("credits", 0) < condition_amount:
                return await interaction.response.send_message(
                    f"❌ Crédits insuffisants ! Vous avez **{user_data.get('credits', 0)}** crédits mais il en faut **{condition_amount}**.", 
                    ephemeral=True
                )
            # Déduire les crédits
            user_data["credits"] -= condition_amount
            save_data()
            
        elif condition_type in ["messages_normaux", "messages_ia"]:
            # Vérifier le nombre de messages
            user_data = data.get(user_id, {})
            message_key = "messages_normaux" if condition_type == "messages_normaux" else "messages_ia"
            message_count = user_data.get(message_key, 0)
            
            if message_count < condition_amount:
                channel_type = "salons normaux" if condition_type == "messages_normaux" else "salons IA"
                return await interaction.response.send_message(
                    f"❌ Messages insuffisants ! Vous avez envoyé **{message_count}** messages dans les {channel_type} mais il en faut **{condition_amount}**.", 
                    ephemeral=True
                )
            
            # Ajouter le participant
            self.participants.add(user_id)
            
            # Mettre à jour le message
            embed = interaction.message.embeds[0]
            embed.set_field_at(1, name="👥 Participants", value=f"**{len(self.participants)}** personnes ont participé !")
            
            await interaction.response.send_message(
                f"✅ Vous participez maintenant au giveaway !\n" 
                f"Condition validée: {condition_type.replace('_', ' ').title()}", 
                ephemeral=True
            )
            await interaction.message.edit(embed=embed, view=self)
            return
            
        # Ajouter le participant (pour les cas sans condition ou crédits)
        self.participants.add(user_id)
        
        # Mettre à jour le message
        embed = interaction.message.embeds[0]
        embed.set_field_at(1, name="👥 Participants", value=f"**{len(self.participants)}** personnes ont participé !")
        
        await interaction.response.send_message("✅ Vous participez maintenant au giveaway !", ephemeral=True)
        await interaction.message.edit(embed=embed, view=self)

@bot.tree.command(name="giveway", description="[ADMIN] Crée un giveaway automatique")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(
    titre="Le titre du giveaway",
    gain="Le gain à remporter",
    temps="La durée en secondes",
    condition="Optionnel - Condition: credits:montant, messages_normaux:nombre, messages_ia:nombre"
)
async def create_giveaway(interaction: discord.Interaction, titre: str, gain: str, temps: int, condition: str = None):
    """Crée un giveaway automatique avec titre, gain et durée en secondes"""
    
    # Validation de la durée
    if temps < 10:
        return await interaction.response.send_message("❌ La durée doit être d'au moins 10 secondes.", ephemeral=True)
    if temps > 86400 * 7:  # Maximum 7 jours
        return await interaction.response.send_message("❌ La durée ne peut pas dépasser 7 jours.", ephemeral=True)
    
    # Parser la condition si fournie
    type_condition = "aucun"
    condition_amount = 0
    
    if condition:
        if ":" not in condition:
            return await interaction.response.send_message(
                "❌ Format de condition invalide. Utilisez: `credits:montant`, `messages_normaux:nombre` ou `messages_ia:nombre`", 
                ephemeral=True
            )
        
        parts = condition.split(":", 1)
        if len(parts) != 2:
            return await interaction.response.send_message(
                "❌ Format de condition invalide. Utilisez: `credits:montant`, `messages_normaux:nombre` ou `messages_ia:nombre`", 
                ephemeral=True
            )
        
        type_condition = parts[0].strip().lower()
        try:
            condition_amount = int(parts[1].strip())
        except ValueError:
            return await interaction.response.send_message(
                "❌ Le montant/nombre doit être un entier valide.", 
                ephemeral=True
            )
        
        # Validation du type de condition
        valid_conditions = ["credits", "messages_normaux", "messages_ia"]
        if type_condition not in valid_conditions:
            return await interaction.response.send_message(
                f"❌ Type de condition invalide. Valeurs valides: {', '.join(valid_conditions)}", 
                ephemeral=True
            )
        
        if condition_amount <= 0:
            return await interaction.response.send_message(
                "❌ Le montant/nombre doit être supérieur à 0.", 
                ephemeral=True
            )
    
    # Générer un ID unique pour le giveaway
    giveaway_id = f"{interaction.guild.id}_{int(time.time())}"
    
    # Créer la vue pour le giveaway
    view = GiveawayView(giveaway_id)
    
    # Préparer le texte des conditions
    condition_text = "Aucune condition"
    if type_condition == "credits":
        condition_text = f"💰 Payer {condition_amount} crédits"
    elif type_condition == "messages_normaux":
        condition_text = f"💬 Envoyer {condition_amount} messages (salons normaux)"
    elif type_condition == "messages_ia":
        condition_text = f"🤖 Envoyer {condition_amount} messages (salons IA)"
    
    # Créer l'embed du giveaway
    embed = discord.Embed(
        title=f"🎉 {titre}",
        description=f"**Gain :** {gain}\n\n**Durée :** {temps} secondes\n\n**Condition :** {condition_text}\n\nCliquez sur le bouton ci-dessous pour participer !",
        color=discord.Color.gold()
    )
    embed.set_thumbnail(url="https://cdn-icons-png.flaticon.com/512/3236/3236555.png")
    embed.add_field(name="⏰ Temps restant", value=f"{temps} secondes", inline=True)
    embed.add_field(name="👥 Participants", value="**0** personnes ont participé !", inline=True)
    embed.set_footer(text=f"Giveaway ID: {giveaway_id} | Créé par {interaction.user.display_name}")
    
    # Stocker les informations du giveaway
    active_giveaways[giveaway_id] = {
        "title": titre,
        "prize": gain,
        "duration": temps,
        "start_time": time.time(),
        "channel_id": interaction.channel.id,
        "guild_id": interaction.guild.id,
        "creator_id": interaction.user.id,
        "message_id": None,  # Sera mis à jour après l'envoi
        "condition_type": type_condition,
        "condition_amount": condition_amount
    }
    
    # Envoyer le message du giveaway
    message = await interaction.channel.send(embed=embed, view=view)
    
    # Mettre à jour le message_id dans les données
    active_giveaways[giveaway_id]["message_id"] = message.id
    
    # Démarrer la tâche de fin automatique
    asyncio.create_task(end_giveaway(giveaway_id, view))
    
    await interaction.response.send_message(f"🎉 Giveaway **{titre}** créé avec succès !", ephemeral=True)

async def end_giveaway(giveaway_id: str, view: GiveawayView):
    """Termine un giveaway et choisit un gagnant"""
    
    # Attendre la durée du giveaway
    giveaway_data = active_giveaways[giveaway_id]
    await asyncio.sleep(giveaway_data["duration"])
    
    try:
        # Récupérer le message et le canal
        guild = bot.get_guild(giveaway_data["guild_id"])
        channel = guild.get_channel(giveaway_data["channel_id"])
        message = await channel.fetch_message(giveaway_data["message_id"])
        
        # Désactiver le bouton
        for item in view.children:
            if item.custom_id == "giveaway_join":
                item.disabled = True
                item.label = "⏰ Terminé"
                break
        
        # Vérifier s'il y a des participants
        if not view.participants:
            embed = message.embeds[0]
            embed.description = f"**Gain :** {giveaway_data['prize']}\n\n**Aucun participant !**\nLe giveaway s'est terminé sans gagnant."
            embed.color = discord.Color.red()
            await message.edit(embed=embed, view=view)
        else:
            # Choisir un gagnant au hasard
            winner_id = random.choice(list(view.participants))
            winner = guild.get_member(int(winner_id))
            
            # Mettre à jour l'embed
            embed = message.embeds[0]
            embed.description = f"**Gain :** {giveaway_data['prize']}\n\n**🎊 Gagnant :** {winner.mention}\nFélicitations !"
            embed.color = discord.Color.green()
            embed.set_field_at(0, name="🏆 Statut", value="**Terminé**", inline=True)
            
            await message.edit(embed=embed, view=view)
            
            # Annoncer le gagnant
            await channel.send(f"🎊 **Félicitations à {winner.mention}** qui a remporté le giveaway **{giveaway_data['title']}** !")
            
            # Envoyer un DM au gagnant
            try:
                await winner.send(
                    f"🎉 **Félicitations !** Vous avez remporté le giveaway **{giveaway_data['title']}** sur le serveur **{guild.name}** !\n\n"
                    f"**Gain :** {giveaway_data['prize']}\n"
                    f"Contactez l'organisateur pour réclamer votre prix."
                )
            except discord.Forbidden:
                pass  # Le DM a échoué, mais ce n'est pas grave
        
        # Supprimer le giveaway des actifs
        del active_giveaways[giveaway_id]
        
    except Exception as e:
        print(f"Erreur lors de la fin du giveaway {giveaway_id}: {e}")
        # Nettoyer même en cas d'erreur
        if giveaway_id in active_giveaways:
            del active_giveaways[giveaway_id]

@create_giveaway.error
async def giveaway_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message("❌ **Accès Refusé :** Vous devez être administrateur pour créer un giveaway.", ephemeral=True)
    else:
        await interaction.response.send_message(f"⚠️ Une erreur est survenue : {error}", ephemeral=True)

class ConfigButtonView(discord.ui.View):
    def __init__(self, category: str, user_id: int):
        super().__init__(timeout=180)
        self.category = category
        self.user_id = user_id
        
        # Bouton pour afficher la configuration actuelle
        self.add_item(discord.ui.Button(
            label="Voir la configuration actuelle",
            style=discord.ButtonStyle.primary,
            custom_id=f"view_config_{category.lower()}"
        ))
        
        # Bouton pour modifier la configuration
        self.add_item(discord.ui.Button(
            label="Modifier les paramètres",
            style=discord.ButtonStyle.secondary,
            custom_id=f"edit_config_{category.lower()}"
        ))
        
        # Boutons spécifiques à la catégorie
        if category == "IA":
            self.add_item(discord.ui.Button(
                label="Définir le salon IA",
                style=discord.ButtonStyle.primary,
                custom_id="set_ia_channel"
            ))
            
        elif category == "Tickets":
            self.add_item(discord.ui.Button(
                label="Définir la catégorie",
                style=discord.ButtonStyle.primary,
                custom_id="set_ticket_category"
            ))
            self.add_item(discord.ui.Button(
                label="Définir le rôle support",
                style=discord.ButtonStyle.primary,
                custom_id="set_support_role"
            ))
            
        elif category == "Musique":
            self.add_item(discord.ui.Button(
                label="Activer/Désactiver le mode DJ",
                style=discord.ButtonStyle.primary,
                custom_id="toggle_dj_mode"
            ))
            
        elif category == "Modération":
            self.add_item(discord.ui.Button(
                label="Définir le salon des logs",
                style=discord.ButtonStyle.primary,
                custom_id="set_log_channel"
            ))
            self.add_item(discord.ui.Button(
                label="Gérer les rôles de modération",
                style=discord.ButtonStyle.primary,
                custom_id="manage_mod_roles"
            ))
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        # Vérifier que l'utilisateur qui interagit est bien celui qui a lancé la commande
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "❌ Seul l'utilisateur qui a lancé la commande peut interagir avec ce menu.",
                ephemeral=True
            )
            return False
        return True

# ==================================
# 🚀 LANCEMENT
# ==================================
bot.run(DISCORD_TOKEN)