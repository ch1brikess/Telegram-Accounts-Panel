from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import simpleSplit
import sys
import os

sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src"))
)

from ..export.file_operations import generateName
from ..utils.log import logError


def saveToPdf(foundAccounts, resultType, config):
    regularFontFile = os.path.join(
        os.getcwd(),
        config.ASSETS_DIRECTORY,
        config.FONTS_DIRECTORY,
        config.FONT_REGULAR_FILE,
    )
    boldFontFile = os.path.join(
        os.getcwd(),
        config.ASSETS_DIRECTORY,
        config.FONTS_DIRECTORY,
        config.FONT_BOLD_FILE,
    )
    try:
        pdfmetrics.registerFont(TTFont(config.FONT_NAME_REGULAR, regularFontFile))
        pdfmetrics.registerFont(TTFont(config.FONT_NAME_BOLD, boldFontFile))

        fileName = generateName(config, "pdf")
        path = os.path.join(config.saveDirectory, fileName)

        width, height = letter
        canva = canvas.Canvas(path, pagesize=letter)
        accountsCount = len(foundAccounts)

        # Логотип
        canva.drawImage(
            os.path.join(
                os.getcwd(),
                config.ASSETS_DIRECTORY,
                config.IMAGES_DIRECTORY,
                "blackbird-logo.png",
            ),
            35,
            height - 90,
            width=60,
            height=60,
        )
        canva.setFont(config.FONT_NAME_BOLD, 15)
        canva.drawCentredString((width / 2) - 5, height - 70, "Report")
        canva.setFont(config.FONT_NAME_REGULAR, 7)
        canva.drawString(width - 90, height - 70, config.datePretty)
        canva.setFont(config.FONT_NAME_REGULAR, 5)
        canva.drawString(
            width - 185,
            height - 25,
            "This report was generated using the Blackbird OSINT Tool.",
        )

        # Заголовок с идентификатором
        canva.setFillColor("#EDEBED")
        canva.setStrokeColor("#BAB8BA")
        canva.rect(40, height - 160, 530, 35, stroke=1, fill=1)
        canva.setFillColor("#000000")

        # 🔥 ОПРЕДЕЛЕНИЕ ИДЕНТИФИКАТОРА ДЛЯ ЛЮБОГО ТИПА
        if resultType == "username":
            identifier = config.currentUser or "unknown"
        elif resultType == "email":
            identifier = config.currentEmail or "unknown"
        elif resultType == "ip":
            identifier = config.currentIp or "unknown_ip"
        elif resultType == "phone":
            identifier = config.currentPhone or "unknown_phone"
        else:
            identifier = "osint_target"

        identifierWidth = stringWidth(identifier, config.FONT_NAME_BOLD, 11)
        canva.drawImage(
            os.path.join(
                os.getcwd(),
                config.ASSETS_DIRECTORY,
                config.IMAGES_DIRECTORY,
                "correct.png",
            ),
            (width / 2) - ((identifierWidth / 2) + 15),
            height - 147,
            width=10,
            height=10,
            mask="auto",
        )
        canva.setFont(config.FONT_NAME_BOLD, 11)
        canva.drawCentredString(width / 2, height - 145, identifier)

        # Предупреждение
        canva.setFillColor("#FFF8C5")
        canva.setStrokeColor("#D9C884")
        canva.rect(40, height - 210, 530, 35, stroke=1, fill=1)
        canva.setFillColor("#57523f")
        canva.setFont(config.FONT_NAME_REGULAR, 8)
        canva.drawImage(
            os.path.join(
                os.getcwd(),
                config.ASSETS_DIRECTORY,
                config.IMAGES_DIRECTORY,
                "warning.png",
            ),
            55,
            height - 197,
            width=10,
            height=10,
            mask="auto",
        )
        canva.drawString(
            70,
            height - 195,
            "Blackbird can make mistakes. Consider checking the information.",
        )

        # AI-анализ (если есть)
        if config.ai_analysis:
            canva.setFillColor("#F4F6F8")
            canva.setStrokeColor("#D0D5DA")
            canva.rect(40, height - 545, 530, 320, stroke=1, fill=1)

            canva.setFillColor("#000000")
            canva.drawImage(
                os.path.join(os.getcwd(), config.ASSETS_DIRECTORY, config.IMAGES_DIRECTORY, "ai-stars.png"),
                55, height - 245, width=12, height=12, mask="auto"
            )
            canva.setFont(config.FONT_NAME_BOLD, 10)
            canva.drawString(70, height - 242, "AI Analysis - Behavioral Summary")
            canva.setFont(config.FONT_NAME_REGULAR, 8)
            canva.drawString(55, height - 255, "This behavioral summary was generated using AI based on the detected online presence.")

            y_position = height - 270

            if config.ai_analysis.get("summary"):
                canva.setFont(config.FONT_NAME_BOLD, 10)
                canva.drawString(55, y_position, "Summary")
                y_position -= 12

                lines = simpleSplit(config.ai_analysis["summary"], config.FONT_NAME_REGULAR, 8, 510)
                text = canva.beginText()
                text.setTextOrigin(55, y_position)
                text.setFont(config.FONT_NAME_REGULAR, 8)
                for line in lines:
                    text.textLine(line)
                    y_position -= 10
                canva.drawText(text)
                y_position -= 10

            if config.ai_analysis.get("categorization"):
                canva.setFont(config.FONT_NAME_BOLD, 10)
                canva.drawString(55, y_position + 3, "Categorization")
                y_position -= 10
                canva.setFont(config.FONT_NAME_REGULAR, 8)
                canva.drawString(55, y_position, config.ai_analysis["categorization"])
                y_position -= 15

            if config.ai_analysis.get("insights"):
                canva.setFont(config.FONT_NAME_BOLD, 10)
                canva.drawString(55, y_position + 3, "Insights")
                y_position -= 10
                canva.setFont(config.FONT_NAME_REGULAR, 8)
                for insight in config.ai_analysis["insights"]:
                    canva.drawString(55, y_position, "- " + insight)
                    y_position -= 10
                y_position -= 5

            if config.ai_analysis.get("risk_flags"):
                canva.setFont(config.FONT_NAME_BOLD, 10)
                canva.drawString(55, y_position + 3, "Risk Flags")
                y_position -= 10
                canva.setFont(config.FONT_NAME_REGULAR, 8)
                for risk in config.ai_analysis["risk_flags"]:
                    canva.drawString(55, y_position, "- " + risk)
                    y_position -= 10
                y_position -= 5

            if config.ai_analysis.get("tags"):
                canva.setFont(config.FONT_NAME_BOLD, 10)
                canva.drawString(55, y_position + 3, "Tags")
                y_position -= 10
                canva.setFont(config.FONT_NAME_REGULAR, 8)
                for tag in config.ai_analysis["tags"]:
                    canva.drawString(55, y_position, "- " + tag)
                    y_position -= 10
                y_position -= 5

        # Результаты
        if accountsCount >= 1:
            if config.ai_analysis:
                height -= 325
            canva.setFillColor("#000000")
            canva.setFont(config.FONT_NAME_REGULAR, 15)
            canva.drawImage(
                os.path.join(
                    os.getcwd(),
                    config.ASSETS_DIRECTORY,
                    config.IMAGES_DIRECTORY,
                    "arrow.png",
                ),
                40,
                height - 245,
                width=12,
                height=12,
                mask="auto",
            )
            canva.drawString(55, height - 245, f"Results ({accountsCount})")

            y_position = height - 270
            for result in foundAccounts:
                if y_position < 72:
                    canva.showPage()
                    y_position = height - 50

                canva.setFont(config.FONT_NAME_BOLD, 12)
                canva.drawString(72, y_position, f"{result['name']}")

                siteWidth = stringWidth(f"{result['name']}", config.FONT_NAME_BOLD, 12)
                canva.drawImage(
                    os.path.join(
                        os.getcwd(),
                        config.ASSETS_DIRECTORY,
                        config.IMAGES_DIRECTORY,
                        "link.png",
                    ),
                    77 + siteWidth,
                    y_position,
                    width=10,
                    height=10,
                    mask="auto",
                )
                canva.linkURL(
                    result["url"],
                    (77 + siteWidth, y_position, 77 + siteWidth + 10, y_position + 10),
                    relative=1,
                )

                # Метаданные (если есть)
                try:
                    if result.get("metadata"):
                        initialWidth = y_position - 10
                        y_position -= 25
                        canva.setFont(config.FONT_NAME_REGULAR, 7)
                        for data in result["metadata"]:
                            if data["type"] == "String":
                                value_str = f"{data['name']}:  {data['value']}"
                                metadataWidth = stringWidth(value_str, config.FONT_NAME_REGULAR, 7)
                                canva.setFillColor("#EDEBED")
                                canva.roundRect(90, y_position - 4, metadataWidth + 5, 13, 6, fill=1, stroke=0)
                                canva.setFillColor("#000000")
                                canva.setFont(config.FONT_NAME_BOLD, 7)
                                canva.drawString(93, y_position, f"{data['name']}:")
                                nameWidth = stringWidth(f"{data['name']}:", config.FONT_NAME_BOLD, 7)
                                canva.setFont(config.FONT_NAME_REGULAR, 7)
                                canva.drawString(93 + nameWidth, y_position, f"{data['value']}")
                                y_position -= 15
                            elif data["type"] == "Array":
                                nameWidth = stringWidth(f"{data['name']}:", config.FONT_NAME_BOLD, 7)
                                canva.setFillColor("#EDEBED")
                                canva.roundRect(90, y_position - 4, nameWidth + 5, 13, 6, fill=1, stroke=0)
                                canva.setFillColor("#000000")
                                canva.setFont(config.FONT_NAME_BOLD, 7)
                                canva.drawString(93, y_position, f"{data['name']}:")
                                y_position -= 15
                                for value in data["value"]:
                                    valWidth = stringWidth(value, config.FONT_NAME_REGULAR, 7)
                                    canva.setFillColor("#EDEBED")
                                    canva.roundRect(100, y_position - 4, valWidth + 5, 13, 6, fill=1, stroke=0)
                                    canva.setFillColor("#000000")
                                    canva.setFont(config.FONT_NAME_REGULAR, 7)
                                    canva.drawString(103, y_position, value)
                                    y_position -= 15
                            elif data["type"] == "Image":
                                if data.get("downloaded"):
                                    y_position -= 25
                                    img_path = os.path.join(
                                        config.saveDirectory,
                                        f"images_{identifier}",
                                        f"{result['name']}_image.jpg",
                                    )
                                    if os.path.exists(img_path):
                                        canva.drawImage(img_path, 90, y_position, width=35, height=35)
                                    y_position -= 15
                        endWidth = y_position
                        canva.setStrokeColor("#CE0000")
                        canva.line(85, initialWidth, 85, endWidth)
                    y_position -= 25
                except Exception as e:
                    logError(e, "Error rendering metadata in PDF", config)

        canva.save()
        config.console.print(f"💾  Saved results to '[cyan1]{fileName}[/cyan1]'")
        return True

    except Exception as e:
        logError(e, "Couldn't save results to PDF file!", config)
        return False