"""
Module de chargement de la configuration pour le bot Nexus
Permet de charger les variables depuis config.yml
"""

import yaml
import os
from typing import Dict, Any


def load_config(config_path: str = "config.yml") -> Dict[str, Any]:
    """
    Charge la configuration depuis le fichier YAML
    
    Args:
        config_path: Chemin vers le fichier de configuration
        
    Returns:
        Dictionnaire contenant la configuration
        
    Raises:
        FileNotFoundError: Si le fichier de configuration n'existe pas
        yaml.YAMLError: Si le fichier YAML est mal formaté
    """
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Le fichier de configuration '{config_path}' n'existe pas.")
    
    try:
        with open(config_path, 'r', encoding='utf-8') as file:
            config = yaml.safe_load(file)
            return config if config is not None else {}
    except yaml.YAMLError as e:
        raise yaml.YAMLError(f"Erreur de lecture du fichier YAML: {e}")


def get_config_value(config: Dict[str, Any], key_path: str, default=None):
    """
    Récupère une valeur de configuration en utilisant une notation par points
    
    Args:
        config: Dictionnaire de configuration
        key_path: Chemin de la clé (ex: "ai.openai_api_key")
        default: Valeur par défaut si la clé n'existe pas
        
    Returns:
        La valeur de configuration ou la valeur par défaut
    """
    keys = key_path.split('.')
    value = config
    
    try:
        for key in keys:
            value = value[key]
        return value
    except (KeyError, TypeError):
        return default


# Charger la configuration globale
CONFIG = load_config()

# Variables globales pour la rétrocompatibilité
def init_config():
    """Initialise toutes les variables de configuration depuis le YAML"""
    
    # Configuration bot
    global DISCORD_TOKEN, OWNER_ID, SUPPORT_SERVER_ID, INVITE_URL
    DISCORD_TOKEN = get_config_value(CONFIG, 'bot.token', "VOTRE TOKEN DISCORD")
    OWNER_ID = get_config_value(CONFIG, 'bot.owner_id', 1139156246965002310)
    SUPPORT_SERVER_ID = get_config_value(CONFIG, 'bot.support_server_id', 1430518750397988967)
    INVITE_URL = get_config_value(CONFIG, 'bot.invite_url', "VOTRE INVITE POUR LE BOT")
    
    # Configuration IA
    global OPENAI_API_KEY, IA_COMPORTEMENT, COST_IMAGE, LIMIT, PERIOD
    OPENAI_API_KEY = get_config_value(CONFIG, 'ai.openai_api_key', "VOTRE API CHATGPT")
    IA_COMPORTEMENT = get_config_value(CONFIG, 'ai.behavior_prompt', "")
    COST_IMAGE = get_config_value(CONFIG, 'ai.image_generation_cost', 5)
    LIMIT = get_config_value(CONFIG, 'ai.message_limit', 3)
    PERIOD = get_config_value(CONFIG, 'ai.period_seconds', 60)
    
    # Configuration musique
    global FFMPEG_OPTIONS, YDL_OPTIONS
    FFMPEG_OPTIONS = get_config_value(CONFIG, 'music.ffmpeg_options', {
        'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
        'options': '-vn'
    })
    YDL_OPTIONS = get_config_value(CONFIG, 'music.ydl_options', {
        'format': 'bestaudio/best',
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True
    })
    
    # Configuration économie
    global CREDIT_BOOST_MULTIPLIER
    CREDIT_BOOST_MULTIPLIER = get_config_value(CONFIG, 'economy.credit_boost_multiplier', 1)
    
    # Configuration quêtes
    global TIER_1_QUESTS_REQUIRED, TIER_2_QUESTS_REQUIRED, MAX_TIER, POSSIBLE_QUESTS
    TIER_1_QUESTS_REQUIRED = get_config_value(CONFIG, 'quests.tier_1_quests_required', 5)
    TIER_2_QUESTS_REQUIRED = get_config_value(CONFIG, 'quests.tier_2_quests_required', 15)
    MAX_TIER = get_config_value(CONFIG, 'quests.max_tier', 3)
    POSSIBLE_QUESTS = get_config_value(CONFIG, 'quests.possible_quests', [])
    
    # Configuration rôles
    global VIP_ROLE_ID, TICKET_CATEGORY_ID
    VIP_ROLE_ID = get_config_value(CONFIG, 'roles.vip_role_id', None)
    TICKET_CATEGORY_ID = get_config_value(CONFIG, 'roles.ticket_category_id', 0)
    
    # Configuration fonctionnalités
    global IMAGINE_MAINTENANCE, EVENT_MODE_ENABLED
    IMAGINE_MAINTENANCE = get_config_value(CONFIG, 'features.imagine_maintenance', False)
    EVENT_MODE_ENABLED = get_config_value(CONFIG, 'features.event_mode_enabled', False)
    
    # Configuration stockage
    global DATA_FILE
    DATA_FILE = get_config_value(CONFIG, 'storage.data_file', "data.json")
    
    # Configuration économie (détails)
    global STARTING_CREDITS, STARTING_MONEY, DAILY_REWARD_MIN, DAILY_REWARD_MAX
    STARTING_CREDITS = get_config_value(CONFIG, 'economy.starting_credits', 10)
    STARTING_MONEY = get_config_value(CONFIG, 'economy.starting_money', 0)
    DAILY_REWARD_MIN = get_config_value(CONFIG, 'economy.daily_reward_min', 3)
    DAILY_REWARD_MAX = get_config_value(CONFIG, 'economy.daily_reward_max', 5)
