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

# تعريف الحالات
MAIN_PDF, PAGE_PDF, POSITION = range(3)

# تخزين البيانات المؤقتة
USER_DATA = {}

# بدء المحادثة
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "مرحبًا! أرسل ملف PDF الرئيسي أولاً."
    )
    return MAIN_PDF

# معالجة الملف الرئيسي
async def handle_main_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    document = update.message.document

    if document.mime_type != "application/pdf":
        await update.message.reply_text("يرجى إرسال ملف PDF فقط!")
        return MAIN_PDF

    # حفظ الملف الرئيسي
    file = await document.get_file()
    with NamedTemporaryFile(delete=False, suffix=".pdf") as temp:
        await file.download_to_memory(temp)
        USER_DATA[user_id] = {"main_pdf": temp.name}

    await update.message.reply_text("تم استلام الملف الرئيسي. الآن أرسل الصفحة المُراد إضافتها.")
    return PAGE_PDF

# معالجة صفحة الإضافة
async def handle_page_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    document = update.message.document

    if document.mime_type != "application/pdf":
        await update.message.reply_text("يرجى إرسال ملف PDF فقط!")
        return PAGE_PDF

    # حفظ صفحة الإضافة
    file = await document.get_file()
    with NamedTemporaryFile(delete=False, suffix=".pdf") as temp:
        await file.download_to_memory(temp)
        USER_DATA[user_id]["page_to_add"] = temp.name

    await update.message.reply_text("تم استلام الصفحة. الآن أرسل رقم الموضع (مثال: 2).")
    return POSITION

# معالجة رقم الموضع
async def handle_position(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text

    if not text.isdigit():
        await update.message.reply_text("يرجى إرسال رقم صحيح فقط!")
        return POSITION

    position = int(text) - 1  # تحويل إلى فهرس يبدأ من الصفر

    try:
        # قراءة الملفات
        main_pdf = PdfReader(USER_DATA[user_id]["main_pdf"])
        page_pdf = PdfReader(USER_DATA[user_id]["page_to_add"])

        # إنشاء ملف جديد
        writer = PdfWriter()

        # إضافة الصفحات حتى الموضع المحدد
        for i in range(position):
            writer.add_page(main_pdf.pages[i])

        # إضافة الصفحة الجديدة
        writer.add_page(page_pdf.pages[0])

        # إضافة بقية الصفحات
        for i in range(position, len(main_pdf.pages)):
            writer.add_page(main_pdf.pages[i])

        # حفظ الملف النهائي
        with NamedTemporaryFile(suffix=".pdf") as output_temp:
            with open(output_temp.name, "wb") as f:
                writer.write(f)

            # إرسال الملف للمستخدم
            await update.message.reply_document(document=open(output_temp.name, "rb"))

    except Exception as e:
        await update.message.reply_text(f"حدث خطأ: {str(e)}")
        logging.error(e)

    finally:
        # تنظيف الملفات المؤقتة
        if user_id in USER_DATA:
            if "main_pdf" in USER_DATA[user_id]:
                os.unlink(USER_DATA[user_id]["main_pdf"])
            if "page_to_add" in USER_DATA[user_id]:
                os.unlink(USER_DATA[user_id]["page_to_add"])
            del USER_DATA[user_id]

    return ConversationHandler.END

# إلغاء المحادثة
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

# تشغيل البوت
if __name__ == "__main__":
    application = Application.builder().token(TOKEN).build()

    # تعريف ConversationHandler
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            MAIN_PDF: [MessageHandler(filters.Document.PDF, handle_main_pdf)],
            PAGE_PDF: [MessageHandler(filters.Document.PDF, handle_page_pdf)],
            POSITION: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_position)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(conv_handler)
    application.run_polling()
