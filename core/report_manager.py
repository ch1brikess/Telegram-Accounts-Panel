# core/report_manager.py
import asyncio
import aiohttp
from typing import Optional
from core.telegram_client import client_manager
from config import Config
from database.db_manager import db_manager

class ReportManager:
    """Менеджер репортов"""
    
    def __init__(self):
        self.client_manager = client_manager
    
    async def generate_report_text(self, target_type: str, target_username: str = None) -> str:
        """Сгенерировать текст репорта через Ollama"""
        if not Config.OLLAMA_ENABLED:
            # Дефолтные тексты репортов
            default_texts = {
                'spam': 'This account is posting spam and unwanted advertisements.',
                'abuse': 'This user is engaging in harassment and abusive behavior.',
                'fake': 'This account is impersonating another person or entity.',
                'illegal': 'This content violates Telegram terms of service.',
                'scam': 'This account is involved in fraudulent activities.'
            }
            return default_texts.get(target_type, 'This content violates Telegram rules.')
        
        try:
            prompt = f"""Generate a short and natural spam report text for Telegram about a {target_type} account @{target_username or 'unknown'}. 
The report should sound like a normal user complaint. Keep it under 50 words. 
Report reason: {target_type}"""

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f'{Config.OLLAMA_URL}/api/generate',
                    json={
                        'model': Config.OLLAMA_MODEL,
                        'prompt': prompt,
                        'stream': False
                    },
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get('response', '').strip()
        except Exception as e:
            print(f"[Ollama] Error: {e}")
        
        # Fallback
        return f'Report for {target_type}: suspicious activity from user {target_username}'
    
    async def report_user(self, phone: str, user_id: int, 
                         username: str = None, reason: str = 'spam',
                         report_text: str = None) -> dict:
        """Отправить репорт на пользователя"""
        client = self.client_manager.get_client(phone)
        if not client or not client.is_user_authorized():
            return {'status': 'error', 'message': 'Not authorized'}
        
        try:
            # Генерируем текст репорта если не передан
            if not report_text:
                report_text = await self.generate_report_text(reason, username)
            
            # Отправляем репорт
            await client.report_peer(user_id, reason, report_text)
            
            # Логируем
            db_manager.add_report_log(
                phone=phone,
                target_type='user',
                target_id=user_id,
                target_username=username,
                reason=reason,
                report_text=report_text
            )
            db_manager.update_stats(reports_sent=1)
            
            return {'status': 'success', 'message': f'Reported user {username or user_id}'}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
    
    async def report_message(self, phone: str, channel_username: str,
                            message_id: int, reason: str = 'spam',
                            report_text: str = None) -> dict:
        """Отправить репорт на сообщение"""
        client = self.client_manager.get_client(phone)
        if not client or not client.is_user_authorized():
            return {'status': 'error', 'message': 'Not authorized'}
        
        try:
            # Генерируем текст репорта если не передан
            if not report_text:
                report_text = await self.generate_report_text(reason, channel_username)
            
            # Отправляем репорт на сообщение
            await client.report_message(channel_username, message_id, reason)
            
            # Логируем
            db_manager.add_report_log(
                phone=phone,
                target_type='message',
                target_id=message_id,
                target_username=channel_username,
                reason=reason,
                report_text=report_text
            )
            db_manager.update_stats(reports_sent=1)
            
            return {'status': 'success', 'message': f'Reported message {message_id}'}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
    
    async def report_from_all_accounts(self, user_id: int, username: str = None,
                                       reason: str = 'spam',
                                       report_text: str = None) -> dict:
        """Отправить репорт со всех аккаунтов"""
        from core.account_manager import AccountManager
        from database.db_manager import db_manager
        
        account_manager = AccountManager(db_manager)
        accounts = account_manager.get_all_accounts()
        
        results = []
        for idx, account in enumerate(accounts):
            phone = account.get('phone')
            if not phone:
                continue
            
            # Генерируем уникальный текст для каждого аккаунта
            unique_text = report_text
            if report_text and Config.OLLAMA_ENABLED:
                try:
                    prompt = f"Перепиши этот текст другими словами, сохрани смысл, максимум 150 символов, русский язык: {report_text}"
                    async with aiohttp.ClientSession() as session:
                        async with session.post(
                            f'{Config.OLLAMA_URL}/api/generate',
                            json={
                                'model': Config.OLLAMA_MODEL,
                                'prompt': prompt,
                                'stream': False
                            },
                            timeout=aiohttp.ClientTimeout(total=30)
                        ) as resp:
                            if resp.status == 200:
                                data = await resp.json()
                                unique_text = data.get('response', '').strip()[:150]
                except Exception as e:
                    print(f"[Ollama] Error generating unique text: {e}")
            
            result = await self.report_user(phone, user_id, username, reason, unique_text)
            results.append({
                'phone': phone,
                'status': result['status'],
                'message': result.get('message', '')
            })
            
            # Задержка между аккаунтами
            await asyncio.sleep(1)
        
        successful = len([r for r in results if r['status'] == 'success'])
        return {
            'status': 'completed',
            'total': len(accounts),
            'successful': successful,
            'results': results
        }

report_manager = ReportManager()
