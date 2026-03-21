import random
import re

def process_spintax(text: str) -> str:
    """
    Обработка Spintax формата
    Пример: {Привет|Здравствуйте|Добрый день}, {друг|товарищ|колега}!
    """
    def replace_match(match):
        options = match.group(1).split('|')
        return random.choice(options)
    
    # Рекурсивная обработка вложенных spintax
    while '{' in text and '}' in text:
        new_text = re.sub(r'\{([^{}]+)\}', replace_match, text)
        if new_text == text:
            break
        text = new_text
    
    return text

def generate_variations(text: str, count: int = 5) -> list[str]:
    """Сгенерировать несколько вариантов текста"""
    variations = []
    for _ in range(count):
        variations.append(process_spintax(text))
    return variations

# Пример использования:
# text = "{Привет|Здравствуйте}, {как дела|как жизнь|как настроение}?"
# print(process_spintax(text))