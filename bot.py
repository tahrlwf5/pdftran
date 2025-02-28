import os
import logging
from tempfile import NamedTemporaryFile
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
)
from PyPDF2 import PdfReader, PdfWriter

# إعدادات البوت
TOKEN = os.environ.get("BOT_TOKEN")

MAIN_PDF, PAGE_PDF, POSITION = range(3)


USER_DATA = {}

# بدء المحادثة بالأمر /addpages
async def addpages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "مرحبًا! أرسل ملف PDF الرئيسي أولاً."
    )
    return MAIN_PDF


async def handle_main_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    document = update.message.document

    if document.mime_type != "application/pdf":
        await update.message.reply_text("يرجى إرسال ملف PDF فقط!")
        return MAIN_PDF


    file = await document.get_file()
    file_name = document.file_name  
    with NamedTemporaryFile(delete=False, suffix=".pdf") as temp:
        await file.download_to_memory(temp)
        USER_DATA[user_id] = {"main_pdf": temp.name, "file_name": file_name}

    await update.message.reply_text("تم استلام الملف الرئيسي. الآن أرسل الصفحة المُراد إضافتها.")
    return PAGE_PDF


async def handle_page_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    document = update.message.document

    if document.mime_type != "application/pdf":
        await update.message.reply_text("يرجى إرسال ملف PDF فقط!")
        return PAGE_PDF


    file = await document.get_file()
    with NamedTemporaryFile(delete=False, suffix=".pdf") as temp:
        await file.download_to_memory(temp)
        USER_DATA[user_id]["page_to_add"] = temp.name

    await update.message.reply_text("تم استلام الصفحة. الآن أرسل رقم الموضع (مثال: 2).")
    return POSITION


async def handle_position(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text

    if not text.isdigit():
        await update.message.reply_text("يرجى إرسال رقم صحيح فقط!")
        return POSITION

    position = int(text) - 1  

    try:
      
        main_pdf = PdfReader(USER_DATA[user_id]["main_pdf"])
        page_pdf = PdfReader(USER_DATA[user_id]["page_to_add"])


        writer = PdfWriter()


        for i in range(position):
            writer.add_page(main_pdf.pages[i])


        writer.add_page(page_pdf.pages[0])


        for i in range(position, len(main_pdf.pages)):
            writer.add_page(main_pdf.pages[i])


        output_file_name = USER_DATA[user_id]["file_name"]
        with NamedTemporaryFile(suffix=".pdf", delete=False) as output_temp:
            with open(output_temp.name, "wb") as f:
                writer.write(f)


            await update.message.reply_document(
                document=open(output_temp.name, "rb"),
                filename=output_file_name,
            )

    except Exception as e:
        await update.message.reply_text(f"حدث خطأ: {str(e)}")
        logging.error(e)

    finally:

        if user_id in USER_DATA:
            if "main_pdf" in USER_DATA[user_id]:
                os.unlink(USER_DATA[user_id]["main_pdf"])
            if "page_to_add" in USER_DATA[user_id]:
                os.unlink(USER_DATA[user_id]["page_to_add"])
            del USER_DATA[user_id]

    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id in USER_DATA:
        if "main_pdf" in USER_DATA[user_id]:
            os.unlink(USER_DATA[user_id]["main_pdf"])
        if "page_to_add" in USER_DATA[user_id]:
            os.unlink(USER_DATA[user_id]["page_to_add"])
        del USER_DATA[user_id]

    await update.message.reply_text("تم إلغاء العملية.")
    return ConversationHandler.END


if __name__ == "__main__":
    application = Application.builder().token(TOKEN).build()


    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("addpages", addpages)],  
        states={
            MAIN_PDF: [MessageHandler(filters.Document.PDF, handle_main_pdf)],
            PAGE_PDF: [MessageHandler(filters.Document.PDF, handle_page_pdf)],
            POSITION: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_position)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(conv_handler)


    application.add_handler(MessageHandler(filters.Document.PDF, lambda update, context: None))

    application.run_polling()
