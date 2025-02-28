import os
import logging
from tempfile import NamedTemporaryFile
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from PyPDF2 import PdfReader, PdfWriter

TOKEN = os.environ.get('6334414905:AAE8vd9W6_s3VemxX261CiqY9cxT04LkWg4')
USER_DATA = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "مرحبًا! أرسل ملف PDF الرئيسي أولاً، ثم أرسل الصفحة المُراد إضافتها،"
        "وأخيرًا أرسل رقم الموضع (مثال: 2)"
    )

async def handle_main_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    document = update.message.document
    
    if document.mime_type != 'application/pdf':
        await update.message.reply_text("يرجى إرسال ملف PDF فقط!")
        return
    
    file = await document.get_file()
    with NamedTemporaryFile(delete=False, suffix=".pdf") as temp:
        await file.download_to_memory(temp)
        USER_DATA[user_id] = {
            'main_pdf': temp.name,
            'page_to_add': None,
            'position': None
        }
    
    await update.message.reply_text("تم استلام PDF الرئيسي. الآن أرسل الصفحة المُراد إضافتها.")

async def handle_page_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    document = update.message.document
    
    if user_id not in USER_DATA:
        await update.message.reply_text("أرسل الملف الرئيسي أولاً!")
        return
    
    if document.mime_type != 'application/pdf':
        await update.message.reply_text("يرجى إرسال ملف PDF فقط!")
        return
    
    file = await document.get_file()
    with NamedTemporaryFile(delete=False, suffix=".pdf") as temp:
        await file.download_to_memory(temp)
        USER_DATA[user_id]['page_to_add'] = temp.name
    
    await update.message.reply_text("تم استلام الصفحة. الآن أرسل رقم الموضع (مثال: 3)")

async def handle_position(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text
    
    if not text.isdigit():
        await update.message.reply_text("يرجى إرسال رقم صحيح فقط!")
        return
    
    position = int(text) - 1  # Convert to 0-based index
    USER_DATA[user_id]['position'] = position
    
    try:
        # معالجة الPDF
        main_pdf = PdfReader(USER_DATA[user_id]['main_pdf'])
        page_pdf = PdfReader(USER_DATA[user_id]['page_to_add'])
        writer = PdfWriter()
        
        # إضافة الصفحات حتى الموضع المحدد
        for i in range(position):
            writer.add_page(main_pdf.pages[i])
        
        # إضافة الصفحة الجديدة
        writer.add_page(page_pdf.pages[0])
        
        # إضافة باقي الصفحات
        for i in range(position, len(main_pdf.pages)):
            writer.add_page(main_pdf.pages[i])
        
        # حفظ الناتج
        with NamedTemporaryFile(suffix=".pdf") as output_temp:
            with open(output_temp.name, 'wb') as f:
                writer.write(f)
            
            await update.message.reply_document(document=open(output_temp.name, 'rb'))
        
        # تنظيف الملفات
        os.unlink(USER_DATA[user_id]['main_pdf'])
        os.unlink(USER_DATA[user_id]['page_to_add'])
        del USER_DATA[user_id]
        
    except Exception as e:
        await update.message.reply_text(f"حدث خطأ: {str(e)}")
        logging.error(e)

if __name__ == '__main__':
    application = Application.builder().token(TOKEN).build()
    
    application.add_handler(CommandHandler('start', start))
    application.add_handler(MessageHandler(
        filters.Document.PDF & ~filters.COMMAND, 
        handle_main_pdf
    ))
    application.add_handler(MessageHandler(
        filters.Document.PDF & filters.User(USER_DATA.keys()),
        handle_page_pdf
    ))
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_position
    ))
    
    application.run_polling()
