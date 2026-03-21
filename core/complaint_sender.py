# core/complaint_sender.py
import aiohttp
import asyncio
import random
import re
from typing import Optional, List
from core.telegram_client import client_manager
from config import Config
from utils.logger import logger

class ComplaintSender:
    """Отправка жалоб через Telegram API с генерацией текста через Ollama"""
    
    def __init__(self):
        self.ollama_url = "http://localhost:11434/api/generate"
        self.model = "llama3.2"  # Модель по умолчанию
    
    async def test_ollama(self) -> dict:
        """Проверить доступность Ollama"""
        try:
            async with aiohttp.ClientSession() as session:
                payload = {
                    "model": self.model,
                    "prompt": "test",
                    "stream": False
                }
                async with session.post(self.ollama_url, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        return {'status': 'success', 'model': self.model}
                    else:
                        return {'status': 'error', 'message': f'Ollama returned {resp.status}'}
        except Exception as e:
            logger.error(f"[OLLAMA] Test failed: {e}")
            return {'status': 'error', 'message': str(e)}
    
    async def generate_complaint(self, reason: str, custom_prompt: str = None) -> str:
        """Сгенерировать текст жалобы через Ollama"""
        
        # Промпты для разных причин
        prompts = {
            'spam': "Напиши короткую жалобу на русском языке на спам-сообщение в Telegram. Жалоба должна быть убедительной и содержать причину: 'Спам'.",
            'fake': "Напиши короткую жалобу на русском языке на мошенническое/фейковое сообщение в Telegram. Жалоба должна быть убедительной.",
            'abuse': "Напиши короткую жалобу на русском языке на оскорбительное/агрессивное сообщение в Telegram. Жалоба должна быть убедительной.",
            'illegal': "Напиши короткую жалобу на русском языке на незаконный контент в Telegram. Укажи что это нарушает правила Telegram.",
        }
        
        prompt = custom_prompt if custom_prompt else prompts.get(reason, prompts['spam'])
        
        try:
            async with aiohttp.ClientSession() as session:
                payload = {
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.7,
                        "max_tokens": 200
                    }
                }
                
                async with session.post(self.ollama_url, json=payload, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get('response', '').strip()
                    else:
                        logger.error(f"[OLLAMA] Generation failed: {resp.status}")
                        return self._get_default_complaint(reason)
                        
        except Exception as e:
            logger.error(f"[OLLAMA] Error: {e}")
            return self._get_default_complaint(reason)
    
    def _get_default_complaint(self, reason: str) -> str:
        """Дефолтные жалобы если Ollama недоступна"""
        complaints = {
            'spam': "Данное сообщение является спамом и нарушает правила использования Telegram. Прошу принять меры.",
            'fake': "Данное сообщение содержит мошенническую информацию и обман пользователей. Прошу проверить и заблокировать.",
            'abuse': "Данное сообщение содержит оскорбления и нарушает правила Telegram. Прошу принять меры.",
            'illegal': "Данное сообщение содержит незаконный контент и нарушает законы РФ и правила Telegram.",
            'ai': "Данный контент создан искусственным интеллектом и выдаётся за реальный. Это вводит пользователей в заблуждение."
        }
        return complaints.get(reason, complaints['spam'])
    
    async def send_complaint(self, phone: str, message_link: str, complaint_text: str) -> dict:
        """Отправить жалобу на сообщение через Telegram аккаунт"""
        try:
            # Парсим ссылку
            match = re.search(r't\.me/([a-zA-Z0-9_]+)/(-?\d+)', message_link)
            if not match:
                match = re.search(r't\.me/c/(-?\d+)/(-?\d+)', message_link)
            
            if not match:
                return {'status': 'error', 'message': 'Invalid link'}
            
            channel = match.group(1)
            message_id = int(match.group(2))
            
            client = client_manager.get_client(phone)
            if not client:
                return {'status': 'error', 'message': 'Client not found'}
            
            is_auth = client_manager._run(client.is_user_authorized())
            if not is_auth:
                return {'status': 'error', 'message': 'Not authorized'}
            
            # Пробуем отправить жалобу через report
            async def _report():
                try:
                    # Получаем сообщение
                    message = await client.get_messages(channel, ids=message_id)
                    if message:
                        # Пытаемся отправить жалобу
                        await client.report_peer(message.input_chat, reason='spam')
                        return {'status': 'success'}
                except Exception as e:
                    logger.warning(f"[COMPLAINT] Direct report failed: {e}")
                    # Если нельзя через API, пробуем открыть диалог с поддержкой
                    return {'status': 'fallback', 'message': str(e)}
            
            result = await _report()
            return result
            
        except Exception as e:
            logger.error(f"[COMPLAINT] Error for {phone}: {e}")
            return {'status': 'error', 'message': str(e)}
    
    async def send_account_complaint(self, phone: str, username: str, reason: str, complaint_text: str) -> dict:
        """Отправить жалобу на аккаунт пользователя"""
        try:
            client = client_manager.get_client(phone)
            if not client:
                return {'status': 'error', 'message': 'Client not found'}
            
            is_auth = client_manager._run(client.is_user_authorized())
            if not is_auth:
                return {'status': 'error', 'message': 'Not authorized'}
            
            # Маппинг причин для Telegram
            reason_map = {
                'spam': 'spam',
                'fake': 'fake',
                'abuse': 'violence',
                'illegal': 'illegal',
                'ai': 'spam'
            }
            
            telegram_reason = reason_map.get(reason, 'spam')
            
            async def _report():
                try:
                    # Получаем entity пользователя
                    entity = await client.get_entity(username)
                    # Отправляем жалобу
                    await client.report_peer(entity, reason=telegram_reason)
                    return {'status': 'success'}
                except Exception as e:
                    logger.warning(f"[ACCOUNT COMPLAINT] Report failed: {e}")
                    return {'status': 'fallback', 'message': str(e)}
            
            result = await _report()
            return result
            
        except Exception as e:
            logger.error(f"[ACCOUNT COMPLAINT] Error for {phone}: {e}")
            return {'status': 'error', 'message': str(e)}
    
    async def send_complaints_batch(self, phones: List[str], message_link: str, 
                                    reason: str, custom_prompt: str = None,
                                    delay_range: tuple = (5, 15)) -> dict:
        """Отправить жалобы с нескольких аккаунтов"""
        import time
        
        # Генерируем текст жалобы через Ollama (один раз)
        complaint_text = await self.generate_complaint(reason, custom_prompt)
        logger.info(f"[COMPLAINTS] Generated complaint: {complaint_text[:50]}...")
        
        results = []
        
        for i, phone in enumerate(phones):
            try:
                result = await self.send_complaint(phone, message_link, complaint_text)
                results.append({
                    'phone': phone,
                    'status': 'success' if result['status'] in ['success', 'fallback'] else 'error',
                    'complaint': complaint_text,
                    'message': result.get('message', '')
                })
                logger.info(f"[COMPLAINT] {phone}: {result['status']}")
                
            except Exception as e:
                results.append({
                    'phone': phone,
                    'status': 'error',
                    'message': str(e)
                })
                logger.error(f"[COMPLAINT] Error for {phone}: {e}")
            
            # Задержка между аккаунтами
            if delay_range[1] > 0 and i < len(phones) - 1:
                delay = random.uniform(delay_range[0], delay_range[1])
                await asyncio.sleep(delay)
        
        successful = len([r for r in results if r['status'] == 'success'])
        
        return {
            'status': 'completed',
            'total': len(phones),
            'successful': successful,
            'failed': len(phones) - successful,
            'results': results
        }

    async def send_account_complaints_batch(self, phones: List[str], username: str,
                                           reason: str, custom_prompt: str = None,
                                           delay_range: tuple = (5, 15)) -> dict:
        """Отправить жалобы на аккаунт с нескольких аккаунтов"""
        
        # Генерируем текст жалобы через Ollama (один раз)
        complaint_text = await self.generate_complaint(reason, custom_prompt)
        logger.info(f"[ACCOUNT COMPLAINTS] Generated complaint for @{username}: {complaint_text[:50]}...")
        
        results = []
        
        for i, phone in enumerate(phones):
            try:
                result = await self.send_account_complaint(phone, username, reason, complaint_text)
                results.append({
                    'phone': phone,
                    'status': 'success' if result['status'] in ['success', 'fallback'] else 'error',
                    'complaint': complaint_text,
                    'message': result.get('message', '')
                })
                logger.info(f"[ACCOUNT COMPLAINT] {phone} -> @{username}: {result['status']}")
                
            except Exception as e:
                results.append({
                    'phone': phone,
                    'status': 'error',
                    'message': str(e)
                })
                logger.error(f"[ACCOUNT COMPLAINT] Error for {phone}: {e}")
            
            # Задержка между аккаунтами
            if delay_range[1] > 0 and i < len(phones) - 1:
                delay = random.uniform(delay_range[0], delay_range[1])
                await asyncio.sleep(delay)
        
        successful = len([r for r in results if r['status'] == 'success'])
        
        return {
            'status': 'completed',
            'total': len(phones),
            'successful': successful,
            'failed': len(phones) - successful,
            'results': results
        }

# Global instance
complaint_sender = ComplaintSender()
