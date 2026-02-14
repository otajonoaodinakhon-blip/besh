import os
import logging
import asyncio
import threading
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from config import BOT_TOKEN, ADMIN_IDS
from database import Database
from certificate_generator import CertificateGenerator

# Flask health check server (Render uchun)
app = Flask(__name__)

@app.route('/')
def home():
    return 'Bot ishlayapti!', 200

@app.route('/health')
def health():
    return 'OK', 200

# Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# DB va generator (papkalarni Render uchun moslash)
db = Database()
cert_gen = CertificateGenerator(template_path='template.png')

# Bot handlerlar (o'zgarishsiz, avvalgi kodi)
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = context.args
    
    referred_by = None
    if args and args[0].startswith('REF'):
        referrer = db.get_user_by_referral_code(args[0])
        if referrer:
            referred_by = referrer[0]
    
    user_data = db.add_user(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        referred_by=referred_by
    )
    
    bot_username = (await context.bot.get_me()).username
    referral_link = f"https://t.me/{bot_username}?start={user_data[4]}"
    
    can_claim, claim_msg = db.can_claim_certificate(user.id)
    
    text = (
        f"👋 Assalomu alaykum, {user.first_name}!\n\n"
        f"🎓 **Five Million AI Leaders** sertifikatini olish uchun "
        f"10 ta do'stingizni taklif qilishingiz kerak.\n\n"
        f"📊 **Sizning statistikangiz:**\n"
        f"• Taklif qilganlar: `{user_data[6]}/10`\n"
        f"• Sertifikat: {'✅ Mavjud' if user_data[7] else '❌ Hali yoq'}\n\n"
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
                text += f"{i}. {name} (@{username}) - {date[:10]}\n"
        
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
        db.cursor.execute('''
        SELECT first_name, referrals_count FROM users 
        ORDER BY referrals_count DESC LIMIT 10
        ''')
        top = db.cursor.fetchall()
        
        text = "🏆 **TOP 10 TAKLIF QILUVCHILAR** 🏆\n\n"
        for i, (name, count) in enumerate(top, 1):
            text += f"{i}. {name}: {count} ta do'st\n"
        
        await query.edit_message_text(text, parse_mode='Markdown')
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
        await start(query, context)

async def referral_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = db.get_user(user.id)
    
    if not user_data:
        await update.message.reply_text("❌ Avval /start ni bosing!")
        return
    
    bot_username = (await context.bot.get_me()).username
    referral_link = f"https://t.me/{bot_username}?start={user_data[4]}"
    
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
        f"🆔 ID: `{user_data[0]}`\n"
        f"👤 Ism: {user_data[2]}\n"
        f"👥 Taklif qilganlar: `{user_data[6]}/10`\n"
        f"🎓 Sertifikat: {'✅ Olgan' if user_data[7] else '❌ Olmagan'}\n"
        f"📅 Qo'shilgan: {user_data[11][:10]}"
    )
    
    if user_data[7]:
        text += f"\n📜 Sertifikat ID: `{user_data[8]}`"
    
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

def run_bot():
    """Botni alohida threadda ishga tushirish"""
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("referral", referral_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_error_handler(error_handler)
    
    print("🤖 Bot ishga tushdi...")
    app.run_polling()

if __name__ == "__main__":
    # Bot threadini ishga tushirish
    import threading
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    
    # Flask health check serverni ishga tushirish (Render uchun)
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)