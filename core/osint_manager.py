# core/osint_manager.py
import os
import csv
import requests
import logging
from pathlib import Path
from datetime import datetime

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='[OSINT] %(message)s'
)
logger = logging.getLogger(__name__)

# Папка для результатов
PARS_DIR = Path(__file__).parent.parent / 'pars'
RESULTS_DIR = PARS_DIR / 'results'
os.makedirs(RESULTS_DIR, exist_ok=True)

# WhatsMyName список сайтов (основные)
SITES_DATA = [
    {"name": "GitHub", "url": "https://github.com/{}", "method": "GET", "body": None},
    {"name": "Twitter", "url": "https://twitter.com/{}", "method": "GET", "body": None},
    {"name": "Instagram", "url": "https://instagram.com/{}", "method": "GET", "body": None},
    {"name": "Facebook", "url": "https://facebook.com/{}", "method": "GET", "body": None},
    {"name": "Telegram", "url": "https://t.me/{}", "method": "GET", "body": None},
    {"name": "VK", "url": "https://vk.com/{}", "method": "GET", "body": None},
    {"name": "TikTok", "url": "https://www.tiktok.com/@{}", "method": "GET", "body": None},
    {"name": "YouTube", "url": "https://www.youtube.com/@{}", "method": "GET", "body": None},
    {"name": "Reddit", "url": "https://www.reddit.com/user/{}", "method": "GET", "body": None},
    {"name": "Twitch", "url": "https://www.twitch.tv/{}", "method": "GET", "body": None},
    {"name": "Steam", "url": "https://steamcommunity.com/id/{}", "method": "GET", "body": None},
    {"name": "SoundCloud", "url": "https://soundcloud.com/{}", "method": "GET", "body": None},
    {"name": "Medium", "url": "https://medium.com/@{}", "method": "GET", "body": None},
    {"name": "Pinterest", "url": "https://www.pinterest.com/{}", "method": "GET", "body": None},
    {"name": "Snapchat", "url": "https://www.snapchat.com/add/{}", "method": "GET", "body": None},
    {"name": "Discord", "url": "https://discord.com/users/{}", "method": "GET", "body": None},
    {"name": "LinkedIn", "url": "https://www.linkedin.com/in/{}", "method": "GET", "body": None},
    {"name": "Flickr", "url": "https://www.flickr.com/people/{}", "method": "GET", "body": None},
    {"name": "Vimeo", "url": "https://vimeo.com/{}", "method": "GET", "body": None},
    {"name": "Dribbble", "url": "https://dribbble.com/{}", "method": "GET", "body": None},
    {"name": "Behance", "url": "https://www.behance.net/{}", "method": "GET", "body": None},
    {"name": "DeviantArt", "url": "https://{}.deviantart.com", "method": "GET", "body": None},
    {"name": "Imgur", "url": "https://imgur.com/user/{}", "method": "GET", "body": None},
    {"name": "Pastebin", "url": "https://pastebin.com/u/{}", "method": "GET", "body": None},
    {"name": "GitLab", "url": "https://gitlab.com/{}", "method": "GET", "body": None},
    {"name": "Bitbucket", "url": "https://bitbucket.org/{}", "method": "GET", "body": None},
    {"name": "StackOverflow", "url": "https://stackoverflow.com/users/{}", "method": "GET", "body": None},
    {"name": "Last.fm", "url": "https://www.last.fm/user/{}", "method": "GET", "body": None},
    {"name": "Patreon", "url": "https://www.patreon.com/{}", "method": "GET", "body": None},
    {"name": "OnlyFans", "url": "https://onlyfans.com/{}", "method": "GET", "body": None},
]

# NSFW сайты
NSFW_SITES = [
    {"name": "Pornhub", "url": "https://www.pornhub.com/users/{}", "method": "GET", "body": None},
    {"name": "XVideos", "url": "https://www.xvideos.com/profile/{}", "method": "GET", "body": None},
    {"name": "XNXX", "url": "https://www.xnxx.com/profile/{}", "method": "GET", "body": None},
    {"name": "RedTube", "url": "https://www.redtube.com/users/{}", "method": "GET", "body": None},
]


class OsintManager:
    def __init__(self):
        self.results_dir = RESULTS_DIR
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def export_to_csv(self, results: list, search_type: str, query: str) -> str:
        """Экспорт результатов в CSV файл"""
        if not results:
            return None
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"osint_{search_type}_{query}_{timestamp}.csv"
        filepath = self.results_dir / filename
        
        try:
            with open(filepath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(["name", "url", "status", "category"])
                
                for result in results:
                    writer.writerow([
                        result.get('name', ''),
                        result.get('url', ''),
                        result.get('status', 'unknown'),
                        result.get('category', 'social')
                    ])
            
            return str(filepath)
        except Exception as e:
            print(f"[OSINT] CSV export error: {e}")
            return None
    
    def check_site(self, site: dict, query: str, timeout: int = 10) -> dict:
        """Проверка одного сайта"""
        url = site['url'].format(query)
        
        try:
            response = self.session.get(url, timeout=timeout, allow_redirects=False)
            
            # Считаем что аккаунт существует если:
            # - статус 200 и не редирект на главную или страницу входа
            # - специфические признаки
            
            if response.status_code == 200:
                # Проверяем что это не страница "пользователь не найден"
                if any(x in response.text.lower() for x in ['not found', 'doesn\'t exist', 'указан неверно', 'страница не найдена']):
                    return None
                return {
                    'name': site['name'],
                    'url': url,
                    'status': 'found',
                    'category': 'nsfw' if site in NSFW_SITES else 'social'
                }
            elif response.status_code in [301, 302]:
                # Редирект может означать что пользователь существует
                return {
                    'name': site['name'],
                    'url': url,
                    'status': 'found',
                    'category': 'nsfw' if site in NSFW_SITES else 'social'
                }
        except requests.exceptions.Timeout:
            pass
        except Exception as e:
            pass
        
        return None
    
    def search_username(self, username: str, config_data: dict = None) -> dict:
        """Поиск аккаунтов по username"""
        timeout = config_data.get('timeout', 10) if config_data else 10
        include_nsfw = config_data.get('no_nsfw', False) if config_data else True
        export_csv = config_data.get('export_csv', False) if config_data else False
        
        # Используем только безопасные сайты если no_nsfw = True
        sites = SITES_DATA + (NSFW_SITES if include_nsfw else [])
        
        logger.info(f"🔍 Начинаем поиск username: {username}")
        logger.info(f"📋 Всего сайтов для проверки: {len(sites)}")
        
        accounts = []
        checked = 0
        
        for site in sites:
            checked += 1
            logger.info(f"  [{checked}/{len(sites)}] Проверяем: {site['name']}...", extra={'end': '\r'})
            
            result = self.check_site(site, username, timeout)
            if result:
                accounts.append(result)
                logger.info(f"  ✅ НАЙДЕН: {site['name']} -> {result['url']}")
        
        logger.info(f"\n✅ Поиск завершён! Проверено сайтов: {checked}, Найдено аккаунтов: {len(accounts)}")
        
        # Экспорт в CSV
        csv_path = None
        if accounts and export_csv:
            csv_path = self.export_to_csv(accounts, 'username', username)
        
        return {
            'status': 'success',
            'username': username,
            'found': len(accounts),
            'accounts': accounts,
            'csv_export': csv_path
        }
    
    def search_email(self, email: str, config_data: dict = None) -> dict:
        """Поиск аккаунтов по email (упрощённый)"""
        # Простой поиск - проверяем только несколько сервисов
        sites = [
            {"name": "HaveIBeenPwned", "url": f"https://haveibeenpwned.com/account/{email}", "category": "security"},
            {"name": "Dehashed", "url": f"https://www.dehashed.com/search?query={email}", "category": "security"},
        ]
        
        logger.info(f"📧 Начинаем поиск email: {email}")
        logger.info(f"📋 Всего сервисов для проверки: {len(sites)}")
        
        accounts = []
        timeout = config_data.get('timeout', 10) if config_data else 10 if config_data else 10
        export_csv = config_data.get('export_csv', False) if config_data else False
        
        for i, site in enumerate(sites, 1):
            logger.info(f"  [{i}/{len(sites)}] Проверяем: {site['name']}...")
            
            result = self.check_site(site, "", timeout)
            # Для email результаты всегда "unknown" так как сложно проверить
            if result:
                result['url'] = site['url']
                accounts.append(result)
                logger.info(f"  ✅ НАЙДЕН: {site['name']}")
        
        logger.info(f"✅ Поиск email завершён! Найдено совпадений: {len(accounts)}")
        
        csv_path = None
        if accounts and export_csv:
            csv_path = self.export_to_csv(accounts, 'email', email.replace('@', '_at_'))
        
        return {
            'status': 'success',
            'email': email,
            'found': len(accounts),
            'accounts': accounts,
            'csv_export': csv_path
        }
    
    def search_phone(self, phone: str) -> dict:
        """Поиск информации по номеру телефона"""
        import phonenumbers
        from phonenumbers import timezone, geocoder, carrier
        
        logger.info(f"📱 Начинаем поиск по номеру телефона: {phone}")
        
        try:
            parse_number = phonenumbers.parse(phone)
            
            if phonenumbers.is_valid_number(parse_number) and phonenumbers.is_possible_number(parse_number):
                result = {
                    'status': 'success',
                    'phone': phone,
                    'exists': True,
                    'e164': phonenumbers.format_number(parse_number, phonenumbers.PhoneNumberFormat.E164),
                    'carrier': carrier.name_for_number(parse_number, 'en'),
                    'region': geocoder.description_for_number(parse_number, 'en'),
                    'timezone': ', '.join(timezone.time_zones_for_number(parse_number)),
                    'country_code': parse_number.country_code,
                    'national_number': parse_number.national_number
                }
                
                # Экспорт в CSV
                csv_path = self.export_to_csv([{
                    'name': 'Phone Info',
                    'url': '',
                    'status': 'valid',
                    'category': 'phone',
                    **result
                }], 'phone', phone.replace('+', ''))
                result['csv_export'] = csv_path
                
                logger.info(f"✅ Информация о номере получена: {result.get('region')}, {result.get('carrier')}")
                
                return result
            else:
                return {
                    'status': 'success',
                    'phone': phone,
                    'exists': False,
                    'error': 'Invalid or impossible number'
                }
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
    
    def search_ip(self, ip: str, timeout: int = 10) -> dict:
        """Поиск информации по IP адресу"""
        logger.info(f"🌐 Начинаем поиск по IP: {ip}")
        
        try:
            response = requests.get(
                url=f'http://ip-api.com/json/{ip}',
                timeout=timeout
            ).json()
            
            if response.get('status') == 'fail':
                return {
                    'status': 'success',
                    'ip': ip,
                    'exists': False,
                    'error': response.get('message', 'Unknown error')
                }
            
            result = {
                'status': 'success',
                'ip': ip,
                'exists': True,
                'isp': response.get('isp'),
                'org': response.get('org'),
                'country': response.get('country'),
                'region': response.get('regionName'),
                'city': response.get('city'),
                'zip': response.get('zip'),
                'lat': response.get('lat'),
                'lon': response.get('lon')
            }
            
            # Экспорт в CSV
            csv_path = self.export_to_csv([{
                'name': 'IP Info',
                'url': f'https://ip-api.com/#{ip}',
                'status': 'found',
                'category': 'ip',
                **result
            }], 'ip', ip.replace('.', '_'))
            result['csv_export'] = csv_path
            
            logger.info(f"✅ Информация об IP получена: {result.get('country')}, {result.get('city')}, {result.get('isp')}")
            
            return result
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
    
    def get_results_dir(self) -> str:
        """Получить путь к папке с результатами"""
        return str(self.results_dir)


osint_manager = OsintManager()