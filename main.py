# -*- coding: utf-8 -*-
"""
KRBRZ VIP Bot - Gelişmiş AI ile Telegram Botu
Bu versiyon, ayar menüsünün kilitlenmesini engellemek için profesyonel ve durumsuz bir yapı kullanır.
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
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ForceReply
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters, ContextTypes,
    CallbackQueryHandler
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
        "statistics_enabled": True,
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
        user_id = update.effective_user.id
        if user_id != ADMIN_USER_ID:
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
        "🔹 `/durdur` - Botun mesaj iletmesini duraklatır/başlatır."
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

# --- YENİ PROFESYONEL AYAR MENÜSÜ SİSTEMİ (ForceReply ile) ---

async def get_main_menu_content():
    text_ai_status = "✅" if bot_config["ai_text_enhancement_enabled"] else "❌"
    image_ai_status = "✅" if bot_config["ai_image_analysis_enabled"] else "❌"
    wm_status = "✅" if bot_config['watermark']['enabled'] else "❌"
    text = "🚀 **KRBRZ VIP Bot Yönetim Paneli**"
    keyboard = [
        [InlineKeyboardButton("📡 Kaynak Kanalları", callback_data='menu_channels_source'), InlineKeyboardButton("📤 Hedef Kanalları", callback_data='menu_channels_destination')],
        [InlineKeyboardButton(f"{text_ai_status} Akıllı Metin", callback_data='toggle_text_ai'), InlineKeyboardButton(f"{image_ai_status} Akıllı Görüntü", callback_data='toggle_image_ai')],
        [InlineKeyboardButton(f"🎭 AI Kişiliği: {bot_config['ai_persona']}", callback_data='menu_persona')],
        [InlineKeyboardButton(f"{wm_status} Filigran", callback_data='toggle_watermark')],
        [InlineKeyboardButton("✅ Menüyü Kapat", callback_data='menu_close')],
    ]
    return text, InlineKeyboardMarkup(keyboard)

async def get_channels_menu_content(channel_type: str):
    config_key = f"{channel_type}_channels"
    channels = bot_config.get(config_key, [])
    title = "Kaynak" if channel_type == 'source' else "Hedef"
    text = f"⚙️ **{title} Kanalları Yönetimi**\n\nMevcut kanallar:\n" + ("\n".join(f"`{ch}`" for ch in channels) or "_Boş_")
    keyboard = [[InlineKeyboardButton(f"🗑️ Sil: {ch}", callback_data=f'remove_{channel_type}_{ch}')] for ch in channels]
    keyboard.append([InlineKeyboardButton(f"➕ Yeni {title} Kanalı Ekle", callback_data=f'add_{channel_type}')])
    keyboard.append([InlineKeyboardButton("⬅️ Ana Menüye Dön", callback_data='menu_main')])
    return text, InlineKeyboardMarkup(keyboard)

async def get_persona_menu_content():
    text = "🎭 Yapay zeka için bir kişilik seçin:"
    keyboard = [
        [InlineKeyboardButton("Agresif Pazarlamacı", callback_data='set_persona_Agresif Pazarlamacı')],
        [InlineKeyboardButton("Profesyonel Satıcı", callback_data='set_persona_Profesyonel Satıcı')],
        [InlineKeyboardButton("Eğlenceli Oyuncu", callback_data='set_persona_Eğlenceli Oyuncu')],
        [InlineKeyboardButton("⬅️ Geri", callback_data='menu_main')],
    ]
    return text, InlineKeyboardMarkup(keyboard)

@admin_only
async def setup_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if 'menu_message_id' in context.user_data:
        try:
            await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=context.user_data.pop('menu_message_id'))
        except Exception: pass
    
    text, reply_markup = await get_main_menu_content()
    sent_message = await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    context.user_data['menu_message_id'] = sent_message.message_id

async def menu_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    
    if data == 'menu_main':
        text, reply_markup = await get_main_menu_content()
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

    elif data.startswith('menu_channels_'):
        channel_type = data.split('_')[-1]
        text, reply_markup = await get_channels_menu_content(channel_type)
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

    elif data == 'menu_persona':
        text, reply_markup = await get_persona_menu_content()
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

    elif data.startswith('toggle_'):
        key_part = data.replace('toggle_', '')
        if key_part == "watermark":
            bot_config['watermark']['enabled'] = not bot_config['watermark']['enabled']
        else:
            bot_config[f"{key_part}_enabled"] = not bot_config[f"{key_part}_enabled"]
        save_config()
        text, reply_markup = await get_main_menu_content()
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

    elif data.startswith('set_persona_'):
        persona = data.replace('set_persona_', '')
        bot_config["ai_persona"] = persona
        save_config()
        text, reply_markup = await get_main_menu_content()
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

    elif data.startswith('add_'):
        channel_type = data.replace('add_', '')
        title = "Kaynak" if channel_type == 'source' else "Hedef"
        
        await query.message.delete()
        context.user_data.pop('menu_message_id', None)
        
        reply_text = f"➕ Eklenecek yeni **{title}** kanalının adını yazıp bu mesaja yanıt verin."
        sent_reply_message = await query.message.reply_text(
            reply_text,
            reply_markup=ForceReply(selective=True),
            parse_mode='Markdown'
        )
        context.user_data['force_reply_info'] = {
            'type': f'add_channel_{channel_type}',
            'message_id': sent_reply_message.message_id
        }

    elif data.startswith('remove_'):
        _, channel_type, channel_name = data.split('_', 2)
        config_key = f"{channel_type}_channels"
        if channel_name in bot_config[config_key]:
            bot_config[config_key].remove(channel_name)
            save_config()
        text, reply_markup = await get_channels_menu_content(channel_type)
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

    elif data == 'menu_close':
        await query.message.delete()
        context.user_data.pop('menu_message_id', None)

@admin_only
async def reply_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message or 'force_reply_info' not in context.user_data:
        return

    reply_info = context.user_data['force_reply_info']
    
    if update.message.reply_to_message.message_id != reply_info['message_id']:
        return

    if reply_info['type'].startswith('add_channel_'):
        channel_type = reply_info['type'].replace('add_channel_', '')
        channel_name = update.message.text.strip()
        config_key = f"{channel_type}_channels"

        if channel_name not in bot_config[config_key]:
            bot_config[config_key].append(channel_name)
            save_config()
        
        await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=reply_info['message_id'])
        await update.message.delete()

        del context.user_data['force_reply_info']
        await setup_command(update, context)

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
    
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("ayarla", setup_command))
    application.add_handler(CommandHandler("durum", status_command))
    application.add_handler(CommandHandler("durdur", pause_command))
    
    application.add_handler(CallbackQueryHandler(menu_callback_handler))
    application.add_handler(MessageHandler(filters.REPLY & filters.TEXT & ~filters.COMMAND, reply_handler))
    
    application.add_handler(MessageHandler(filters.UpdateType.CHANNEL_POST, forwarder))
    
    logger.info("✅ Bot başarıyla yapılandırıldı ve dinlemede.")
    application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    Thread(target=run_flask, daemon=True).start()
    logger.info(f"🌐 Flask sunucusu {PORT} portunda başlatıldı.")
    main()

