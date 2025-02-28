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
MAIN_PDF, PAGE_PDF, CHOOSE_OPTION, POSITION = range(4)

# تخزين البيانات المؤقتة
USER_DATA = {}

# بدء المحادثة بالأمر /addpages
async def addpages(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    file_name = document.file_name  # استخراج اسم الملف الأصلي
    with NamedTemporaryFile(delete=False, suffix=".pdf") as temp:
        await file.download_to_memory(temp)
        USER_DATA[user_id] = {"main_pdf": temp.name, "file_name": file_name}

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

    # التحقق من عدد الصفحات
    page_pdf = PdfReader(USER_DATA[user_id]["page_to_add"])
    if len(page_pdf.pages) > 1:
        # إذا كان الملف يحتوي على أكثر من صفحة
        await update.message.reply_text(
            "يحتوي الملف على أكثر من صفحة. اختر:\n"
            "1. إضافة كافة الصفحات.\n"
            "2. إضافة صفحة واحدة فقط."
        )
        return CHOOSE_OPTION
    else:
        # إذا كان الملف يحتوي على صفحة واحدة
        await update.message.reply_text("تم استلام الصفحة. الآن أرسل رقم الموضع (مثال: 2).")
        return POSITION

# معالجة اختيار المستخدم
async def handle_option(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text

    if text not in ["1", "2"]:
        await update.message.reply_text("يرجى اختيار 1 أو 2 فقط!")
        return CHOOSE_OPTION

    if text == "1":
        # إضافة كافة الصفحات
        USER_DATA[user_id]["add_all_pages"] = True
        await update.message.reply_text("سيتم إضافة كافة الصفحات. الآن أرسل رقم الموضع (مثال: 2).")
    else:
        # إضافة صفحة واحدة فقط
        USER_DATA[user_id]["add_all_pages"] = False
        await update.message.reply_text("سيتم إضافة صفحة واحدة فقط. الآن أرسل رقم الموضع (مثال: 2).")

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

        # إضافة الصفحات الجديدة
        if USER_DATA[user_id].get("add_all_pages", False):
            # إضافة كافة الصفحات
            for page in page_pdf.pages:
                writer.add_page(page)
        else:
            # إضافة صفحة واحدة فقط
            writer.add_page(page_pdf.pages[0])

        # إضافة بقية الصفحات
        for i in range(position, len(main_pdf.pages)):
            writer.add_page(main_pdf.pages[i])

        # حفظ الملف النهائي بنفس اسم الملف الرئيسي
        output_file_name = USER_DATA[user_id]["file_name"]
        with NamedTemporaryFile(suffix=".pdf", delete=False) as output_temp:
            with open(output_temp.name, "wb") as f:
                writer.write(f)

            # إرسال الملف للمستخدم بنفس الاسم
            await update.message.reply_document(
                document=open(output_temp.name, "rb"),
                filename=output_file_name,
            )

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
        entry_points=[CommandHandler("addpages", addpages)],  # الأمر الجديد
        states={
            MAIN_PDF: [MessageHandler(filters.Document.PDF, handle_main_pdf)],
            PAGE_PDF: [MessageHandler(filters.Document.PDF, handle_page_pdf)],
            CHOOSE_OPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_option)],
            POSITION: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_position)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # إضافة ConversationHandler
    application.add_handler(conv_handler)

    # تجاهل أي ملفات PDF يتم إرسالها دون الأمر /addpages
    application.add_handler(MessageHandler(filters.Document.PDF, lambda update, context: None))

    application.run_polling()
