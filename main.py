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
from datetime import datetime, timedelta
from threading import Thread
from typing import Optional, List, Dict
import httpx
from PIL import Image, ImageDraw, ImageFont
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters, ContextTypes,
    ConversationHandler, CallbackQueryHandler
)
from flask import Flask, render_template_string, jsonify
from functools import lru_cache
import time

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
        "ai_persona": "Agresif Pazarlamacı", # YENİ: AI Kişiliği
        "watermark": {"text": "KRBRZ_VIP", "position": "sag-alt", "color": "beyaz", "enabled": True},
        "statistics_enabled": True
    }
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = json.load(f)
            defaults.update(config) # Mevcut ayarları koru, eksikleri ekle
    return defaults

bot_config = load_config()

def save_config():
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(bot_config, f, indent=4, ensure_ascii=False)

# --- YAPAY ZEKAYI DAHA AKILLI HALE GETİREN YENİ FONKSİYONLAR ---

def get_ai_persona_prompt(persona: str) -> str:
    """Seçilen kişiliğe göre AI için sistem talimatı döndürür."""
    personas = {
        "Agresif Pazarlamacı": (
            "Sen PUBG hileleri satan agresif ve iddialı bir pazarlamacısın. "
            "Kısa, dikkat çekici ve güçlü ifadeler kullan. Rakiplerine göz dağı ver. "
            "Emojileri (🔥, 👑, 🚀, ☠️) cesurca kullan. "
            "Cümlelerin sonunda mutlaka '@KRBRZ063' ve '#PUBGHACK #KRBRZ #Zirve' etiketleri bulunsun."
        ),
        "Profesyonel Satıcı": (
            "Sen PUBG bypass hizmeti sunan profesyonel ve güvenilir bir satıcısın. "
            "Net, bilgilendirici ve ikna edici bir dil kullan. Güvenilirlik ve kalite vurgusu yap. "
            "Emojileri (✅, 💯, 🛡️, 🏆) yerinde kullan. "
            "Cümlelerin sonunda mutlaka '@KRBRZ063' ve '#PUBG #Bypass #Güvenilir' etiketleri bulunsun."
        ),
        "Eğlenceli Oyuncu": (
            "Sen yetenekli ve eğlenceli bir PUBG oyuncususun. Takipçilerinle samimi bir dille konuşuyorsun. "
            "Esprili, enerjik ve oyuncu jargonuna hakim bir dil kullan. "
            "Emojileri (😂, 😎, 🎉, 🎮) bolca kullan. "
            "Cümlelerin sonunda mutlaka '@KRBRZ063' ve '#PUBGMobile #Oyun #Eğlence' etiketleri bulunsun."
        )
    }
    return personas.get(persona, personas["Agresif Pazarlamacı"])


@lru_cache(maxsize=100)
async def enhance_text_with_gemini_smarter(original_text: str) -> str:
    """
    YENİLENDİ: Metni sadece güzelleştirmez, içeriği ANALİZ EDER ve seçilen kişiliğe göre
    dinamik ve yaratıcı bir pazarlama metni oluşturur.
    """
    if not GEMINI_API_KEY or not original_text:
        return original_text + " @KRBRZ063 #KRBRZ"

    # AI kişiliğini ve sistem talimatını config'den al
    persona_prompt = get_ai_persona_prompt(bot_config.get("ai_persona", "Agresif Pazarlamacı"))
    
    # AI'ye gönderilen talimat çok daha akıllı ve dinamik
    user_prompt = f"Aşağıdaki metnin içeriğini analiz et: '{original_text}'. Bu içeriğe dayanarak, seçtiğim kişiliğe uygun, kısa, yaratıcı ve dikkat çekici bir sosyal medya başlığı oluştur. Sadece oluşturduğun başlığı yaz, başka bir açıklama yapma."

    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={GEMINI_API_KEY}"
    payload = {
        "contents": [{"parts": [{"text": user_prompt}]}],
        "systemInstruction": {"parts": [{"text": persona_prompt}]},
        "generationConfig": {
            "maxOutputTokens": 80,  # Yaratıcılık için biraz daha alan
            "temperature": 0.8,    # Daha yaratıcı ve çeşitli sonuçlar için sıcaklık artırıldı
            "topP": 0.9,
            "topK": 40
        }
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(api_url, json=payload)
            response.raise_for_status()
            result = response.json()
            enhanced_text = result["candidates"][0]["content"]["parts"][0]["text"].strip()
            return enhanced_text
    except Exception as e:
        logger.error(f"Akıllı Metin API hatası: {e}")
        return original_text + " @KRBRZ063 #KRBRZ" # Hata durumunda bile etiket ekle


async def generate_caption_from_image_smarter(image_bytes: bytes) -> str:
    """
    YENİLENDİ: Görüntüyü KÖRÜ KÖRÜNE değil, içeriğini ANALİZ EDEREK yorumlar.
    Zafer anını, çatışmayı veya önemli bir olayı tespit edip ona göre başlık üretir.
    """
    if not GEMINI_API_KEY:
        return "@KRBRZ063 #KRBRZ"

    persona_prompt = get_ai_persona_prompt(bot_config.get("ai_persona", "Agresif Pazarlamacı"))
    image_b64 = base64.b64encode(image_bytes).decode('utf-8')

    # AI'ye gönderilen talimat artık görseli analiz etmesini istiyor
    user_prompt = (
        "Bu bir PUBG Mobile oyununa ait ekran görüntüsü. Görüntüyü dikkatlice analiz et. "
        "Görüntüde ne oluyor? (Örn: Bir zafer anı mı? 'Winner Winner Chicken Dinner' yazısı var mı? Yoğun bir çatışma mı var? Bir oyuncu dürbünle rakip mi arıyor?) "
        "Bu analizine dayanarak, seçtiğim kişiliğe uygun, kısa ve etkileyici bir sosyal medya başlığı oluştur. "
        "Sadece oluşturduğun başlığı yaz, başka bir şey ekleme."
    )

    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={GEMINI_API_KEY}"
    payload = {
        "contents": [{
            "parts": [
                {"text": user_prompt},
                {"inline_data": {"mime_type": "image/jpeg", "data": image_b64}}
            ]
        }],
        "systemInstruction": {"parts": [{"text": persona_prompt}]},
        "generationConfig": {
            "maxOutputTokens": 80,
            "temperature": 0.8
        }
    }

    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await client.post(api_url, json=payload)
            response.raise_for_status()
            result = response.json()
            caption = result["candidates"][0]["content"]["parts"][0]["text"].strip()
            return caption
    except Exception as e:
        logger.error(f"Akıllı Görüntü API hatası: {e}")
        return "Zirve bizimdir! 👑 @KRBRZ063 #PUBGHACK #KRBRZ" # Hata durumunda genel bir başlık


# --- Filigran Fonksiyonu (Değişiklik yok) ---
async def apply_watermark(photo_bytes: bytes) -> bytes:
    wm_config = bot_config.get("watermark", {})
    if not wm_config.get("enabled"):
        return photo_bytes
    try:
        with Image.open(io.BytesIO(photo_bytes)).convert("RGBA") as base:
            txt = Image.new("RGBA", base.size, (255, 255, 255, 0))
            font_size = max(15, base.size[1] // 25)
            try:
                font = ImageFont.truetype("arial.ttf", size=font_size)
            except IOError:
                font = ImageFont.load_default()
            
            d = ImageDraw.Draw(txt)
            fill_color = tuple(int(wm_config.get("color", "255,255,255,180").split(',')[i]) for i in range(4))
            text = wm_config.get("text", "KRBRZ_VIP")
            
            text_bbox = d.textbbox((0, 0), text, font=font)
            text_width, text_height = text_bbox[2] - text_bbox[0], text_bbox[3] - text_bbox[1]
            margin = 15
            
            positions = {
                'sag-alt': (base.width - text_width - margin, base.height - text_height - margin),
                'sol-ust': (margin, margin)
            }
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

# --- Kurulum Sihirbazı ---
SETUP_MENU, GET_SOURCE, GET_DEST, GET_PERSONA = range(4)

@admin_only
async def setup_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """YENİLENDİ: AI Kişilik ayarı eklendi."""
    text_ai_status = "✅ Aktif" if bot_config["ai_text_enhancement_enabled"] else "❌ Pasif"
    image_ai_status = "✅ Aktif" if bot_config["ai_image_analysis_enabled"] else "❌ Pasif"
    wm_status = f"✅ Aktif" if bot_config['watermark']['enabled'] else "❌ Pasif"
    
    keyboard = [
        [InlineKeyboardButton("📡 Kaynak Kanallar", callback_data='set_source'), InlineKeyboardButton("📤 Hedef Kanallar", callback_data='set_dest')],
        [InlineKeyboardButton(f"🤖 Akıllı Metin: {text_ai_status}", callback_data='toggle_text_ai')],
        [InlineKeyboardButton(f"🖼️ Akıllı Görüntü: {image_ai_status}", callback_data='toggle_image_ai')],
        [InlineKeyboardButton(f"🎭 AI Kişiliği: {bot_config['ai_persona']}", callback_data='set_persona')],
        [InlineKeyboardButton(f"💧 Filigran: {wm_status}", callback_data='toggle_watermark')],
        [InlineKeyboardButton("✅ Çıkış", callback_data='exit_setup')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message_content = "🚀 **KRBRZ VIP Bot Yönetim Paneli**\n\nYapay zeka ayarlarını ve kanal yapılandırmasını buradan yönetin."
    
    if update.message:
        await update.message.reply_text(message_content, reply_markup=reply_markup, parse_mode='Markdown')
    elif update.callback_query:
        await update.callback_query.edit_message_text(message_content, reply_markup=reply_markup, parse_mode='Markdown')
            
    return SETUP_MENU

async def setup_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    data = query.data
    
    if data == 'set_source':
        await query.edit_message_text("📡 Kaynak kanal adını yazın (@ile başlayın). Mevcutları silmek için tekrar yazın.")
        return GET_SOURCE
    elif data == 'set_dest':
        await query.edit_message_text("📤 Hedef kanal adını yazın. Mevcutları silmek için tekrar yazın.")
        return GET_DEST
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
            [InlineKeyboardButton("⬅️ Geri", callback_data='back_to_menu')],
        ]
        await query.edit_message_text("🎭 Yapay zeka için bir kişilik seçin:", reply_markup=InlineKeyboardMarkup(keyboard))
        return GET_PERSONA
    elif data == 'exit_setup':
        await query.edit_message_text("✅ Ayarlar kaydedildi. Bot çalışıyor!")
        save_config()
        return ConversationHandler.END
    
    save_config()
    return await setup_command(query, context)

async def persona_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    persona = query.data.split('_')[1]
    bot_config["ai_persona"] = persona
    save_config()
    await query.message.reply_text(f"✅ AI kişiliği '{persona}' olarak ayarlandı.")
    return await setup_command(query, context)

async def channel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, channel_type: str) -> int:
    channel = update.message.text.strip()
    config_key = f"{channel_type}_channels"
    if channel in bot_config[config_key]:
        bot_config[config_key].remove(channel)
        await update.message.reply_text(f"🗑️ Kanal silindi: {channel}")
    else:
        bot_config[config_key].append(channel)
        await update.message.reply_text(f"✅ Kanal eklendi: {channel}")
    return SETUP_MENU

async def get_source_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await channel_handler(update, context, "source")
    await update.message.reply_text("Kaynak kanallar güncellendi. Başka ekleyebilir veya /ayarla ile menüye dönebilirsiniz.")
    return GET_SOURCE

async def get_dest_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await channel_handler(update, context, "destination")
    await update.message.reply_text("Hedef kanallar güncellendi. Başka ekleyebilir veya /ayarla ile menüye dönebilirsiniz.")
    return GET_DEST

async def cancel_setup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("❌ İşlem iptal edildi.")
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

        await context.bot.send_chat_action(chat_id=ADMIN_USER_ID, action="typing")

        if message.caption and bot_config["ai_text_enhancement_enabled"]:
            final_caption = await enhance_text_with_gemini_smarter(message.caption)
        elif photo_bytes and bot_config["ai_image_analysis_enabled"]:
            final_caption = await generate_caption_from_image_smarter(photo_bytes)
        else: # AI kapalıysa veya sadece metin varsa
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
            GET_SOURCE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_source_handler)],
            GET_DEST: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_dest_handler)],
            GET_PERSONA: [CallbackQueryHandler(persona_handler, pattern='^persona_')]
        },
        fallbacks=[CallbackQueryHandler(setup_command, pattern='^back_to_menu'), CommandHandler("iptal", cancel_setup)],
        per_message=False
    )
    
    application.add_handler(conv_handler)
    application.add_handler(MessageHandler(filters.UpdateType.CHANNEL_POST, forwarder))
    
    logger.info("✅ Bot başarıyla yapılandırıldı ve dinlemede.")
    application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    Thread(target=run_flask, daemon=True).start()
    logger.info(f"🌐 Flask sunucusu {PORT} portunda başlatıldı.")
    main()
