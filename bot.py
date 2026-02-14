import os
import logging
import asyncio
import threading
import time
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from config import BOT_TOKEN, ADMIN_IDS
from database import Database
from certificate_generator import CertificateGenerator

# Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# DB va generator
db = Database()
cert_gen = CertificateGenerator(template_path='template.jpg')

# Flask app
app = Flask(__name__)

@app.route('/')
def home():
    return 'Bot ishlayapti!', 200

@app.route('/health')
def health():
    return 'OK', 200

# Bot handlerlar
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = context.args
    
    referred_by = None
    if args and args[0].startswith('REF'):
        referrer = db.get_user_by_referral_code(args[0])
        if referrer:
            referred_by = referrer.user_id
    
    user_data = db.add_user(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        referred_by=referred_by
    )
    
    if not user_data:
        user_data = db.get_user(user.id)
    
    bot_username = (await context.bot.get_me()).username
    referral_link = f"https://t.me/{bot_username}?start={user_data.referral_code}"
    
    can_claim, claim_msg = db.can_claim_certificate(user.id)
    
    text = (
        f"👋 Assalomu alaykum, {user.first_name}!\n\n"
        f"🎓 **Five Million AI Leaders** sertifikatini olish uchun "
        f"10 ta do'stingizni taklif qilishingiz kerak.\n\n"
        f"📊 **Sizning statistikangiz:**\n"
        f"• Taklif qilganlar: `{user_data.referrals_count}/10`\n"
        f"• Sertifikat: {'✅ Mavjud' if user_data.certificate_claimed else '❌ Hali yoq'}\n\n"
        f"🔗 **Sizning taklif havolangiz:**\n"
        f"`{referral_link}`\n\n"
        f"{claim_msg}"
    )
    
    keyboard = [
        [InlineKeyboardButton("👥 Taklif qilganlar", callback_data="referrals")],
        [InlineKeyboardButton("🎓 Sertifikat olish", callback_data="claim")],
        [InlineKeyboardButton("📊 Reyting", callback_data="leaderboard")]
    ]
    
    if user.id in ADMIN_IDS:
        keyboard.append([InlineKeyboardButton("📈 Admin panel", callback_data="admin")])
    
    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    if query.data == "referrals":
        referrals = db.get_referrals(user_id)
        if not referrals:
            text = "Siz hali hech kimni taklif qilmagansiz."
        else:
            text = "👥 **Siz taklif qilganlar:**\n\n"
            for i, (ref_id, username, name, date) in enumerate(referrals, 1):
                text += f"{i}. {name} (@{username}) - {str(date)[:10]}\n"
        
        await query.edit_message_text(text, parse_mode='Markdown')
        
        keyboard = [[InlineKeyboardButton("🔙 Orqaga", callback_data="back")]]
        await query.edit_message_reply_markup(InlineKeyboardMarkup(keyboard))
    
    elif query.data == "claim":
        can_claim, msg = db.can_claim_certificate(user_id)
        
        if not can_claim:
            await query.edit_message_text(f"❌ {msg}")
            keyboard = [[InlineKeyboardButton("🔙 Orqaga", callback_data="back")]]
            await query.edit_message_reply_markup(InlineKeyboardMarkup(keyboard))
            return
        
        success, result = db.claim_certificate(user_id)
        if success:
            user = db.get_user(user_id)
            cert_path = cert_gen.generate(user, result)
            
            with open(cert_path, 'rb') as f:
                await query.message.reply_photo(
                    photo=f,
                    caption=f"🎉 **Tabriklaymiz!**\n\nSertifikatingiz tayyor!\nID: `{result}`",
                    parse_mode='Markdown'
                )
            
            await query.edit_message_text("✅ Sertifikatingiz yuborildi!")
        else:
            await query.edit_message_text(f"❌ Xatolik: {result}")
    
    elif query.data == "leaderboard":
        # Leaderboard uchun alohida so'rov
        await query.edit_message_text("🏆 Leaderboard tez orada qo'shiladi")
        keyboard = [[InlineKeyboardButton("🔙 Orqaga", callback_data="back")]]
        await query.edit_message_reply_markup(InlineKeyboardMarkup(keyboard))
    
    elif query.data == "admin" and query.from_user.id in ADMIN_IDS:
        stats = db.get_stats()
        text = (
            f"📊 **Admin Panel**\n\n"
            f"👥 Umumiy foydalanuvchilar: `{stats['total_users']}`\n"
            f"🎓 Sertifikat olganlar: `{stats['total_certificates']}`\n"
            f"🔗 Jami referallar: `{stats['total_referrals']}`"
        )
        await query.edit_message_text(text, parse_mode='Markdown')
    
    elif query.data == "back":
        # Orqaga qaytish - start ni chaqirish
        await start(query, context)

async def referral_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = db.get_user(user.id)
    
    if not user_data:
        await update.message.reply_text("❌ Avval /start ni bosing!")
        return
    
    bot_username = (await context.bot.get_me()).username
    referral_link = f"https://t.me/{bot_username}?start={user_data.referral_code}"
    
    text = (
        f"🔗 **Sizning taklif havolangiz:**\n"
        f"`{referral_link}`\n\n"
        f"Bu havolani do'stlaringizga yuboring. Har bir do'stingiz "
        f"ro'yxatdan o'tganda, sizning ballaringiz ortadi!"
    )
    
    await update.message.reply_text(text, parse_mode='Markdown')

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = db.get_user(user.id)
    
    if not user_data:
        await update.message.reply_text("❌ Avval /start ni bosing!")
        return
    
    text = (
        f"📊 **Sizning statistikangiz**\n\n"
        f"🆔 ID: `{user_data.user_id}`\n"
        f"👤 Ism: {user_data.first_name}\n"
        f"👥 Taklif qilganlar: `{user_data.referrals_count}/10`\n"
        f"🎓 Sertifikat: {'✅ Olgan' if user_data.certificate_claimed else '❌ Olmagan'}\n"
        f"📅 Qo'shilgan: {user_data.created_at}"
    )
    
    if user_data.certificate_claimed:
        text += f"\n📜 Sertifikat ID: `{user_data.certificate_id}`"
    
    await update.message.reply_text(text, parse_mode='Markdown')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🔰 **Yordam**\n\n"
        "/start - Botni ishga tushirish\n"
        "/referral - Taklif havolangizni ko'rish\n"
        "/stats - Shaxsiy statistika\n"
        "/help - Yordam oynasi\n\n"
        "**Sertifikat olish qoidalari:**\n"
        "1. 10 ta do'stingizni taklif qiling\n"
        "2. Har bir do'stingiz botga kirishi kerak\n"
        "3. 'Sertifikat olish' tugmasini bosing"
    )
    await update.message.reply_text(text, parse_mode='Markdown')

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Xatolik: {context.error}")

# Botni ishga tushirish funksiyasi
def run_bot():
    """Yagona bot instance ini ishga tushirish"""
    try:
        print("🤖 Bot ishga tushmoqda...")
        
        # Yangi event loop yaratish
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Bot application yaratish
        application = Application.builder().token(BOT_TOKEN).build()
        
        # Handlerlar
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("referral", referral_command))
        application.add_handler(CommandHandler("stats", stats_command))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CallbackQueryHandler(button_handler))
        application.add_error_handler(error_handler)
        
        # Botni ishga tushirish (polling)
        application.run_polling(
            drop_pending_updates=True,  # Eski xabarlarni o'chirish
            allowed_updates=['message', 'callback_query']
        )
        
    except Exception as e:
        print(f"❌ Bot xatoligi: {e}")
        logger.error(f"Bot xatoligi: {e}")

if __name__ == "__main__":
    # PORT ni olish
    port = int(os.environ.get('PORT', 5000))
    
    # Flask ni alohida threadda ishga tushirish
    flask_thread = threading.Thread(
        target=lambda: app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
    )
    flask_thread.daemon = True
    flask_thread.start()
    
    # Botni ishga tushirishdan oldin biroz kutish
    time.sleep(2)
    
    # Botni ishga tushirish (asosiy threadda)
    run_bot()
