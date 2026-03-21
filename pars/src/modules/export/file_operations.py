from pathlib import Path
from rich.markup import escape
import os


# Creates directory to save PDF, CSV and HTML content
def createSaveDirectory(config):
    folderName = generateName(config)

    strPath = os.path.join(
        os.path.dirname(__file__), "..", "..", "..", "results", Path(folderName)
    )
    config.saveDirectory = strPath
    path = Path(strPath)
    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)
        if config.verbose:
            config.console.print(
                escape(f"🆕 Created directory to save search data [{folderName}]")
            )

    if config.dump:
        if config.currentUser:
            createDumpDirectory(config.currentUser, config)

        if config.currentEmail:
            createDumpDirectory(config.currentEmail, config)

    if config.pdf:
        if config.currentUser:
            createImagesDirectory(config.currentUser, config)

        if config.currentEmail:
            createImagesDirectory(config.currentEmail, config)

    return True


def createDumpDirectory(identifier, config):
    folderName = f"dump_{identifier}"
    strPath = os.path.join(config.saveDirectory, folderName)
    path = Path(strPath)
    if not path.exists():
        if config.verbose:
            config.console.print(
                escape(f"🆕 Created directory to save dump data [{folderName}]")
            )
        path.mkdir(parents=True, exist_ok=True)


def createImagesDirectory(identifier, config):
    folderName = f"images_{identifier}"
    strPath = os.path.join(config.saveDirectory, folderName)
    path = Path(strPath)
    if not path.exists():
        if config.verbose:
            config.console.print(
                escape(f"🆕 Created directory to save images [{folderName}]")
            )
        path.mkdir(parents=True, exist_ok=True)


def generateName(config, extension=None):
    # Определяем целевой идентификатор в порядке приоритета
    if config.currentUser:
        target = config.currentUser
    elif config.currentEmail:
        target = config.currentEmail
    elif getattr(config, 'currentPhone', None):
        # Оставляем только цифры для имени папки (удаляем +, -, пробелы и т.д.)
        target = ''.join(filter(str.isdigit, str(config.currentPhone))) or config.currentPhone
    elif getattr(config, 'currentIp', None):
        target = str(config.currentIp).replace('.', '_')
    else:
        target = "osint_target"

    # Формируем базовое имя
    folderName = f"{target}_{config.dateRaw}_blackbird"

    if extension:
        folderName = folderName + "." + extension

    # Удаляем или заменяем недопустимые символы для имени папки
    import re
    folderName = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', folderName)
    # Ограничиваем длину (опционально)
    folderName = folderName[:100]

    return folderName