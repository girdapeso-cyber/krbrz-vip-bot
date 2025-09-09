# -*- coding: utf-8 -*-
"""
KRBRZ VIP Bot - Gelişmiş AI ile Telegram Botu
Yapay zeka, artık sadece şablon doldurmuyor; anlıyor, analiz ediyor ve yaratıyor.
"""

# --- Gerekli Kütüphaneler ---
import os
import logging
import json
import io
import base64
import sqlite3
import asyncio
from datetime import datetime
from threading import Thread
from typing import List, Dict
import httpx
from PIL import Image, ImageDraw, ImageFont
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters, ContextTypes,
    ConversationHandler, CallbackQueryHandler
)
from flask import Flask
from functools import lru_cache

# --- Güvenli Ortam Değişkenleri ---
try:
    BOT_TOKEN = os.environ['BOT_TOKEN']
    ADMIN_USER_ID = int(os.environ['ADMIN_USER_ID'])
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
    PORT = int(os.environ.get('PORT', 5000))
except (KeyError, ValueError) as e:
    print(f"!!! HATA: Gerekli environment variable bulunamadı: {e}")
    exit()

# --- Gelişmiş Loglama ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("bot.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# --- Veritabanı Kurulumu ---
def init_database():
    conn = sqlite3.connect('bot_data.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS message_stats (id INTEGER PRIMARY KEY, channel_id TEXT, message_type TEXT, ai_enhanced BOOLEAN, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)')
    cursor.execute('CREATE TABLE IF NOT EXISTS message_templates (id INTEGER PRIMARY KEY, name TEXT UNIQUE, content TEXT, category TEXT)')
    conn.commit()
    conn.close()

init_database()

# --- Konfigürasyon Yönetimi ---
CONFIG_FILE = "bot_config.json"

def load_config():
    defaults = {
        "source_channels": [],
        "destination_channels": [],
        "is_paused": False,
        "ai_text_enhancement_enabled": True,
        "ai_image_analysis_enabled": True,
        "ai_persona": "Agresif Pazarlamacı",
        "watermark": {"text": "KRBRZ_VIP", "position": "sag-alt", "color": "beyaz", "enabled": True},
        "statistics_enabled": True
    }
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = json.load(f)
            defaults.update(config)
    return defaults

bot_config = load_config()

def save_config():
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(bot_config, f, indent=4, ensure_ascii=False)

# --- YAPAY ZEKAYI DAHA AKILLI HALE GETİREN FONKSİYONLAR ---

def get_ai_persona_prompt(persona: str) -> str:
    personas = {
        "Agresif Pazarlamacı": ("Sen PUBG hileleri satan agresif ve iddialı bir pazarlamacısın. Kısa, dikkat çekici ve güçlü ifadeler kullan. Rakiplerine göz dağı ver. Emojileri (🔥, 👑, 🚀, ☠️) cesurca kullan. Cümlelerin sonunda mutlaka '@KRBRZ063' ve '#PUBGHACK #KRBRZ #Zirve' etiketleri bulunsun."),
        "Profesyonel Satıcı": ("Sen PUBG bypass hizmeti sunan profesyonel ve güvenilir bir satıcısın. Net, bilgilendirici ve ikna edici bir dil kullan. Güvenilirlik ve kalite vurgusu yap. Emojileri (✅, 💯, 🛡️, 🏆) yerinde kullan. Cümlelerin sonunda mutlaka '@KRBRZ063' ve '#PUBG #Bypass #Güvenilir' etiketleri bulunsun."),
        "Eğlenceli Oyuncu": ("Sen yetenekli ve eğlenceli bir PUBG oyuncususun. Takipçilerinle samimi bir dille konuşuyorsun. Esprili, enerjik ve oyuncu jargonuna hakim bir dil kullan. Emojileri (😂, 😎, 🎉, 🎮) bolca kullan. Cümlelerin sonunda mutlaka '@KRBRZ063' ve '#PUBGMobile #Oyun #Eğlence' etiketleri bulunsun.")
    }
    return personas.get(persona, personas["Agresif Pazarlamacı"])

@lru_cache(maxsize=100)
async def enhance_text_with_gemini_smarter(original_text: str) -> str:
    if not GEMINI_API_KEY or not original_text: return original_text + " @KRBRZ063 #KRBRZ"
    persona_prompt = get_ai_persona_prompt(bot_config.get("ai_persona", "Agresif Pazarlamacı"))
    user_prompt = f"Aşağıdaki metnin içeriğini analiz et: '{original_text}'. Bu içeriğe dayanarak, seçtiğim kişiliğe uygun, kısa, yaratıcı ve dikkat çekici bir sosyal medya başlığı oluştur. Sadece oluşturduğun başlığı yaz, başka bir açıklama yapma."
    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={GEMINI_API_KEY}"
    payload = {"contents": [{"parts": [{"text": user_prompt}]}],"systemInstruction": {"parts": [{"text": persona_prompt}]},"generationConfig": {"maxOutputTokens": 80,"temperature": 0.8,"topP": 0.9,"topK": 40}}
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(api_url, json=payload)
            response.raise_for_status()
            result = response.json()
            return result["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as e:
        logger.error(f"Akıllı Metin API hatası: {e}")
        return original_text + " @KRBRZ063 #KRBRZ"

async def generate_caption_from_image_smarter(image_bytes: bytes) -> str:
    if not GEMINI_API_KEY: return "@KRBRZ063 #KRBRZ"
    persona_prompt = get_ai_persona_prompt(bot_config.get("ai_persona", "Agresif Pazarlamacı"))
    image_b64 = base64.b64encode(image_bytes).decode('utf-8')
    user_prompt = ("Bu bir PUBG Mobile oyununa ait ekran görüntüsü. Görüntüyü dikkatlice analiz et. Görüntüde ne oluyor? (Örn: Bir zafer anı mı? 'Winner Winner Chicken Dinner' yazısı var mı? Yoğun bir çatışma mı var?) Bu analizine dayanarak, seçtiğim kişiliğe uygun, kısa ve etkileyici bir sosyal medya başlığı oluştur. Sadece oluşturduğun başlığı yaz, başka bir şey ekleme.")
    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={GEMINI_API_KEY}"
    payload = {"contents": [{"parts": [{"text": user_prompt},{"inline_data": {"mime_type": "image/jpeg", "data": image_b64}}]}],"systemInstruction": {"parts": [{"text": persona_prompt}]},"generationConfig": {"maxOutputTokens": 80,"temperature": 0.8}}
    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await client.post(api_url, json=payload)
            response.raise_for_status()
            result = response.json()
            return result["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as e:
        logger.error(f"Akıllı Görüntü API hatası: {e}")
        return "Zirve bizimdir! 👑 @KRBRZ063 #PUBGHACK #KRBRZ"

# --- Filigran Fonksiyonu ---
async def apply_watermark(photo_bytes: bytes) -> bytes:
    wm_config = bot_config.get("watermark", {})
    if not wm_config.get("enabled"): return photo_bytes
    try:
        with Image.open(io.BytesIO(photo_bytes)).convert("RGBA") as base:
            txt = Image.new("RGBA", base.size, (255, 255, 255, 0))
            font_size = max(15, base.size[1] // 25)
            try: font = ImageFont.truetype("arial.ttf", size=font_size)
            except IOError: font = ImageFont.load_default()
            d = ImageDraw.Draw(txt)
            colors = {"beyaz": (255, 255, 255, 180),"siyah": (0, 0, 0, 180),"kirmizi": (255, 0, 0, 180)}
            fill_color = colors.get(wm_config.get("color", "beyaz").lower(), (255, 255, 255, 180))
            text = wm_config.get("text", "KRBRZ_VIP")
            text_bbox = d.textbbox((0, 0), text, font=font)
            text_width, text_height = text_bbox[2] - text_bbox[0], text_bbox[3] - text_bbox[1]
            margin = 15
            positions = {'sag-alt': (base.width - text_width - margin, base.height - text_height - margin),'sol-ust': (margin, margin)}
            x, y = positions.get(wm_config.get("position", "sag-alt"), positions['sag-alt'])
            d.text((x, y), text, font=font, fill=fill_color)
            out = Image.alpha_composite(base, txt)
            buffer = io.BytesIO()
            out.convert("RGB").save(buffer, format="JPEG", quality=95)
            buffer.seek(0)
            return buffer.getvalue()
    except Exception as e:
        logger.error(f"Filigran hatası: {e}")
        return photo_bytes

# --- Admin ve Ayar Komutları ---
def admin_only(func):
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        if update.effective_user.id != ADMIN_USER_ID:
            await update.message.reply_text("❌ Bu komut sadece admin tarafından kullanılabilir.")
            return
        return await func(update, context, *args, **kwargs)
    return wrapped

@admin_only
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚀 **KRBRZ VIP Bot Aktif!**\n\n"
        "İşte kullanabileceğiniz komutlar:\n"
        "🔹 `/ayarla` - Botun yönetim panelini açar.\n"
        "🔹 `/durum` - Botun çalışıp çalışmadığını kontrol eder.\n"
        "🔹 `/durdur` - Botun mesaj iletmesini duraklatır/başlatır.\n"
        "🔹 `/iptal` - Ayar menüsündeki bir işlemi iptal eder."
        , parse_mode='Markdown'
    )

@admin_only
async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    status = "▶️ Çalışıyor ve Mesajları İletiyor" if not bot_config.get('is_paused') else "⏸️ Duraklatıldı"
    await update.message.reply_text(f"✅ Bot Aktif!\n\n**Durum:** {status}", parse_mode='Markdown')

@admin_only
async def pause_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot_config["is_paused"] = not bot_config.get("is_paused", False)
    save_config()
    status_text = "⏸️ Duraklatıldı" if bot_config["is_paused"] else "▶️ Devam Ettiriliyor"
    await update.message.reply_text(f"**Bot mesaj iletimi {status_text}**", parse_mode='Markdown')

# --- DAHA STABİL HALE GETİRİLEN KURULUM SİHİRBAZI ---
(SETUP_MENU, GET_PERSONA, MANAGE_SOURCE, MANAGE_DEST, ADD_SOURCE, ADD_DEST) = range(6)

@admin_only
async def setup_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text_ai_status = "✅ Aktif" if bot_config["ai_text_enhancement_enabled"] else "❌ Pasif"
    image_ai_status = "✅ Aktif" if bot_config["ai_image_analysis_enabled"] else "❌ Pasif"
    wm_status = f"✅ Aktif" if bot_config['watermark']['enabled'] else "❌ Pasif"
    
    keyboard = [
        [InlineKeyboardButton("📡 Kaynak Kanalları Yönet", callback_data='manage_source')],
        [InlineKeyboardButton("📤 Hedef Kanalları Yönet", callback_data='manage_dest')],
        [InlineKeyboardButton(f"🤖 Akıllı Metin: {text_ai_status}", callback_data='toggle_text_ai')],
        [InlineKeyboardButton(f"🖼️ Akıllı Görüntü: {image_ai_status}", callback_data='toggle_image_ai')],
        [InlineKeyboardButton(f"🎭 AI Kişiliği: {bot_config['ai_persona']}", callback_data='set_persona')],
        [InlineKeyboardButton(f"💧 Filigran: {wm_status}", callback_data='toggle_watermark')],
        [InlineKeyboardButton("✅ Çıkış", callback_data='exit_setup')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    message_content = "🚀 **KRBRZ VIP Bot Yönetim Paneli**\n\nYapay zeka ayarlarını ve kanal yapılandırmasını buradan yönetin."
    
    if update.message:
        # Menü mesajını sakla ki daha sonra silebilelim
        sent_message = await update.message.reply_text(message_content, reply_markup=reply_markup, parse_mode='Markdown')
        context.user_data['menu_message_id'] = sent_message.message_id
    elif update.callback_query:
        await update.callback_query.edit_message_text(message_content, reply_markup=reply_markup, parse_mode='Markdown')
        context.user_data['menu_message_id'] = update.callback_query.message.message_id
            
    return SETUP_MENU

async def setup_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    data = query.data
    
    if data == 'manage_source':
        await display_channels_menu(update, context, 'source')
        return MANAGE_SOURCE
    elif data == 'manage_dest':
        await display_channels_menu(update, context, 'dest')
        return MANAGE_DEST
    elif data == 'toggle_text_ai':
        bot_config["ai_text_enhancement_enabled"] = not bot_config["ai_text_enhancement_enabled"]
    elif data == 'toggle_image_ai':
        bot_config["ai_image_analysis_enabled"] = not bot_config["ai_image_analysis_enabled"]
    elif data == 'toggle_watermark':
        bot_config['watermark']['enabled'] = not bot_config['watermark']['enabled']
    elif data == 'set_persona':
        keyboard = [
            [InlineKeyboardButton("Agresif Pazarlamacı", callback_data='persona_Agresif Pazarlamacı')],
            [InlineKeyboardButton("Profesyonel Satıcı", callback_data='persona_Profesyonel Satıcı')],
            [InlineKeyboardButton("Eğlenceli Oyuncu", callback_data='persona_Eğlenceli Oyuncu')],
            [InlineKeyboardButton("⬅️ Geri", callback_data='back_to_main_menu')],
        ]
        await query.edit_message_text("🎭 Yapay zeka için bir kişilik seçin:", reply_markup=InlineKeyboardMarkup(keyboard))
        return GET_PERSONA
    elif data == 'exit_setup':
        await query.edit_message_text("✅ Ayarlar kaydedildi. Bot çalışıyor!")
        save_config()
        if 'menu_message_id' in context.user_data:
            del context.user_data['menu_message_id']
        return ConversationHandler.END
    
    save_config()
    return await setup_command(update, context)

async def persona_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if query.data == 'back_to_main_menu': return await setup_command(update, context)
    persona = query.data.split('_')[1]
    bot_config["ai_persona"] = persona
    save_config()
    await query.message.reply_text(f"✅ AI kişiliği '{persona}' olarak ayarlandı.")
    return await setup_command(update, context)

async def display_channels_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, channel_type: str):
    """Kanal yönetimi menüsünü gösterir/günceller."""
    config_key = f"{channel_type}_channels"
    channels = bot_config.get(config_key, [])
    title = "Kaynak" if channel_type == 'source' else "Hedef"
    text = f"⚙️ **{title} Kanalları Yönetimi**\n\nMevcut kanallar:"
    if not channels: text += "\n\n_Henüz kanal eklenmemiş._"
    keyboard = []
    for channel in channels:
        keyboard.append([InlineKeyboardButton(f"🗑️ Sil: {channel}", callback_data=f'remove_{channel_type}_{channel}')])
    keyboard.append([InlineKeyboardButton(f"➕ Yeni {title} Kanalı Ekle", callback_data=f'add_{channel_type}')])
    keyboard.append([InlineKeyboardButton("⬅️ Ana Menüye Dön", callback_data='back_to_main_menu')])
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Menü mesajını düzenle
    menu_message_id = context.user_data.get('menu_message_id')
    if menu_message_id:
        try:
            await context.bot.edit_message_text(
                chat_id=update.effective_chat.id,
                message_id=menu_message_id,
                text=text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.warning(f"Menü mesajı düzenlenemedi, yeni mesaj gönderiliyor: {e}")
            sent_message = await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            context.user_data['menu_message_id'] = sent_message.message_id

async def source_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    data = query.data
    if data == 'add_source':
        await query.edit_message_text("📡 Eklenecek yeni **Kaynak** kanalının adını yazın (@ile veya ID olarak).")
        return ADD_SOURCE
    elif data.startswith('remove_source_'):
        channel_name = data.replace('remove_source_', '')
        if channel_name in bot_config['source_channels']:
            bot_config['source_channels'].remove(channel_name)
            save_config()
        await display_channels_menu(update, context, 'source')
        return MANAGE_SOURCE
    elif data == 'back_to_main_menu':
        await setup_command(update, context)
        return SETUP_MENU

async def dest_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    data = query.data
    if data == 'add_dest':
        await query.edit_message_text("📤 Eklenecek yeni **Hedef** kanalının adını yazın (@ile veya ID olarak).")
        return ADD_DEST
    elif data.startswith('remove_dest_'):
        channel_name = data.replace('remove_dest_', '')
        if channel_name in bot_config['destination_channels']:
            bot_config['destination_channels'].remove(channel_name)
            save_config()
        await display_channels_menu(update, context, 'dest')
        return MANAGE_DEST
    elif data == 'back_to_main_menu':
        await setup_command(update, context)
        return SETUP_MENU

async def add_channel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, channel_type: str) -> int:
    """Kanal ekler ve menüyü günceller."""
    channel = update.message.text.strip()
    config_key = f"{channel_type}_channels"
    
    # Kullanıcının gönderdiği kanal adı mesajını sil
    await update.message.delete()

    if channel not in bot_config[config_key]:
        bot_config[config_key].append(channel)
        save_config()
    else:
        # Geçici bir uyarı mesajı gönder ve kısa süre sonra sil
        warning_msg = await update.message.reply_text(f"⚠️ Bu kanal zaten listede: {channel}", parse_mode='Markdown')
        await asyncio.sleep(3)
        await warning_msg.delete()
    
    # Güncellenmiş kanal menüsünü göster
    await display_channels_menu(update, context, channel_type)
    
    # Doğru state'e geri dönmeliyiz ki menü butonları çalışsın
    return MANAGE_SOURCE if channel_type == 'source' else MANAGE_DEST

async def add_source_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await add_channel_handler(update, context, 'source')

async def add_dest_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await add_channel_handler(update, context, 'dest')

async def cancel_setup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("✅ Ayar menüsü kapatıldı.")
    if 'menu_message_id' in context.user_data:
            del context.user_data['menu_message_id']
    return ConversationHandler.END

# --- Ana Mesaj Yönlendirici ---
async def forwarder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if bot_config["is_paused"]: return
    message = update.channel_post
    if not message: return

    chat_identifier = f"@{message.chat.username}" if message.chat.username else str(message.chat.id)
    if chat_identifier not in bot_config["source_channels"]: return

    try:
        final_caption = ""
        photo_bytes = None
        
        if message.photo:
            file = await context.bot.get_file(message.photo[-1].file_id)
            photo_bytes = await file.download_as_bytearray()
            photo_bytes = bytes(photo_bytes)

        if message.caption and bot_config["ai_text_enhancement_enabled"]:
            final_caption = await enhance_text_with_gemini_smarter(message.caption)
        elif photo_bytes and bot_config["ai_image_analysis_enabled"]:
            final_caption = await generate_caption_from_image_smarter(photo_bytes)
        else:
             final_caption = message.caption or message.text or ""
             if "@KRBRZ063" not in final_caption:
                 final_caption += "\n\n@KRBRZ063 #KRBRZ"

        for dest in bot_config["destination_channels"]:
            try:
                if photo_bytes:
                    watermarked_photo = await apply_watermark(photo_bytes)
                    await context.bot.send_photo(chat_id=dest, photo=watermarked_photo, caption=final_caption)
                elif message.video:
                    await message.copy(chat_id=dest, caption=final_caption)
                else:
                    await context.bot.send_message(chat_id=dest, text=final_caption)
                logger.info(f"Mesaj {dest} kanalına başarıyla yönlendirildi.")
            except Exception as e:
                logger.error(f"{dest} kanalına yönlendirme hatası: {e}")
    except Exception as e:
        logger.error(f"Genel yönlendirici hatası: {e}")

# --- Flask Web Sunucusu ---
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return f"<h1>KRBRZ VIP Bot Aktif</h1><p>AI Durumu: {'✅' if bot_config['ai_text_enhancement_enabled'] else '❌'}</p><p>Bot Durumu: {'▶️ Çalışıyor' if not bot_config['is_paused'] else '⏸️ Duraklatıldı'}</p>"

def run_flask():
    flask_app.run(host='0.0.0.0', port=PORT, debug=False)

# --- Botun Başlatılması ---
def main():
    logger.info("🚀 KRBRZ VIP Bot başlatılıyor...")
    application = Application.builder().token(BOT_TOKEN).build()
    
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("ayarla", setup_command)],
        states={
            SETUP_MENU: [CallbackQueryHandler(setup_menu_handler)],
            GET_PERSONA: [CallbackQueryHandler(persona_handler)],
            MANAGE_SOURCE: [CallbackQueryHandler(source_menu_handler)],
            MANAGE_DEST: [CallbackQueryHandler(dest_menu_handler)],
            ADD_SOURCE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_source_handler)],
            ADD_DEST: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_dest_handler)],
        },
        fallbacks=[
            CommandHandler("iptal", cancel_setup),
            CallbackQueryHandler(setup_command, pattern='^back_to_main_menu$')
        ],
        conversation_timeout=300.0,
        allow_reentry=True
    )
    
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("durum", status_command))
    application.add_handler(CommandHandler("durdur", pause_command))
    application.add_handler(conv_handler)
    application.add_handler(MessageHandler(filters.UpdateType.CHANNEL_POST, forwarder))
    
    logger.info("✅ Bot başarıyla yapılandırıldı ve dinlemede.")
    application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    Thread(target=run_flask, daemon=True).start()
    logger.info(f"🌐 Flask sunucusu {PORT} portunda başlatıldı.")
    main()

