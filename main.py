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
from threading import Thread, Lock
from typing import List, Dict
import httpx
from PIL import Image, ImageDraw, ImageFont
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ForceReply
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters, ContextTypes,
    CallbackQueryHandler
)
# --- Flask için Ek Kütüphaneler ---
from flask import Flask, render_template_string, request, redirect, url_for, flash
from functools import lru_cache

# --- Güvenli Ortam Değişkenleri ---
try:
    BOT_TOKEN = os.environ['BOT_TOKEN']
    ADMIN_USER_ID = int(os.environ['ADMIN_USER_ID'])
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
    PORT = int(os.environ.get('PORT', 5000))
    # DÜZELTME: Flask için sabit bir secret key
    FLASK_SECRET_KEY = os.environ.get('FLASK_SECRET_KEY', 'varsayilan_cok_guvenli_bir_anahtar_:)')
except (KeyError, ValueError) as e:
    print(f"!!! HATA: Gerekli environment variable bulunamadı: {e}")
    exit()

# --- Gelişmiş Loglama ---
LOG_FILE = "bot.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# --- Veritabanı Kurulumu ---
def init_database():
    conn = sqlite3.connect('bot_data.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS message_stats (id INTEGER PRIMARY KEY, channel_id TEXT, message_type TEXT, ai_enhanced BOOLEAN, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)')
    conn.commit()
    conn.close()

init_database()

# --- Konfigürasyon Yönetimi ---
CONFIG_FILE = "bot_config.json"
config_lock = Lock() # DÜZELTME: Race condition'ı engellemek için kilit

def load_config():
    with config_lock:
        defaults = {
            "source_channels": [],
            "destination_channels": [],
            "is_paused": False,
            "ai_text_enhancement_enabled": True,
            "ai_image_analysis_enabled": True,
            "ai_persona": "Agresif Pazarlamacı",
            "personas": {
                "Agresif Pazarlamacı": "Sen PUBG hileleri satan agresif ve iddialı bir pazarlamacısın. Kısa, dikkat çekici ve güçlü ifadeler kullan. Rakiplerine göz dağı ver. Emojileri (🔥, 👑, 🚀, ☠️) cesurca kullan. Cümlelerin sonunda mutlaka '@KRBRZ063' ve '#PUBGHACK #KRBRZ #Zirve' etiketleri bulunsun.",
                "Profesyonel Satıcı": "Sen PUBG bypass hizmeti sunan profesyonel ve güvenilir bir satıcısın. Net, bilgilendirici ve ikna edici bir dil kullan. Güvenilirlik ve kalite vurgusu yap. Emojileri (✅, 💯, 🛡️, 🏆) yerinde kullan. Cümlelerin sonunda mutlaka '@KRBRZ063' ve '#PUBG #Bypass #Güvenilir' etiketleri bulunsun.",
                "Eğlenceli Oyuncu": "Sen yetenekli ve eğlenceli bir PUBG oyuncususun. Takipçilerinle samimi bir dille konuşuyorsun. Esprili, enerjik ve oyuncu jargonuna hakim bir dil kullan. Emojileri (😂, 😎, 🎉, 🎮) bolca kullan. Cümlelerin sonunda mutlaka '@KRBRZ063' ve '#PUBGMobile #Oyun #Eğlence' etiketleri bulunsun."
            },
            "watermark": {"text": "KRBRZ_VIP", "position": "sag-alt", "color": "beyaz", "enabled": True},
            "statistics_enabled": True,
            "admin_ids": [], # Çoklu admin sistemi için
        }
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
                defaults.update(config)
        
        if ADMIN_USER_ID not in defaults['admin_ids']:
            defaults['admin_ids'].append(ADMIN_USER_ID)
            
        return defaults

bot_config = load_config()

def save_config():
    with config_lock:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(bot_config, f, indent=4, ensure_ascii=False)

# --- YAPAY ZEKAYI DAHA AKILLI HALE GETİREN FONKSİYONLAR ---
def get_ai_persona_prompt(persona: str) -> str:
    return bot_config.get("personas", {}).get(persona, "Normal bir şekilde yaz.")
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
            # DÜZELTME: Güvenli veri erişimi
            return result.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip() or original_text
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
            # DÜZELTME: Güvenli veri erişimi
            return result.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip() or "Zirve bizimdir! 👑"
    except Exception as e:
        logger.error(f"Akıllı Görüntü API hatası: {e}")
        return "Zirve bizimdir! 👑 @KRBRZ063 #PUBGHACK #KRBRZ"

# --- Filigran Fonksiyonu ---
async def apply_watermark(photo_bytes: bytes) -> bytes:
    wm_config = bot_config.get("watermark", {})
    if not wm_config.get("enabled"): return photo_bytes
    logger.info("Filigran uygulanıyor...")
    try:
        with Image.open(io.BytesIO(photo_bytes)).convert("RGBA") as base:
            txt = Image.new("RGBA", base.size, (255, 255, 255, 0))
            font_size = max(15, base.size[1] // 25)
            font = None
            font_paths = ['/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 'arial.ttf', '/System/Library/Fonts/Supplemental/Arial.ttf']
            for path in font_paths:
                try:
                    font = ImageFont.truetype(path, size=font_size)
                    logger.info(f"Font bulundu: {path}")
                    break
                except IOError:
                    continue
            if not font:
                logger.warning("Uygun font bulunamadı, varsayılan font kullanılıyor.")
                font = ImageFont.load_default()
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
            logger.info("Filigran başarıyla uygulandı.")
            return buffer.getvalue()
    except Exception as e:
        logger.error(f"Filigran hatası: {e}")
        return photo_bytes

# --- Admin ve Ayar Komutları (Telegram) ---
def admin_only(func):
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        if update.effective_user.id not in bot_config.get('admin_ids', [ADMIN_USER_ID]):
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
    text = "🚀 **KRBRZ VIP - Gelişmiş Kontrol Merkezi**"
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
        if not channel_name.startswith("@") and not channel_name.startswith("-100"):
            channel_name = f"@{channel_name}"
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
    if (
        chat_identifier not in bot_config["source_channels"]
        and str(message.chat.id) not in bot_config["source_channels"]
    ):
        return
    ai_used = False
    try:
        final_caption = ""
        photo_bytes = None
        if message.photo:
            file = await context.bot.get_file(message.photo[-1].file_id)
            photo_bytes = await file.download_as_bytearray()
            photo_bytes = bytes(photo_bytes)
        if message.caption and bot_config["ai_text_enhancement_enabled"]:
            final_caption = await enhance_text_with_gemini_smarter(message.caption)
            ai_used = True
        elif photo_bytes and bot_config["ai_image_analysis_enabled"]:
            final_caption = await generate_caption_from_image_smarter(photo_bytes)
            ai_used = True
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
                    # DÜZELTME: Daha güvenli video gönderimi
                    await context.bot.send_video(chat_id=dest, video=message.video.file_id, caption=final_caption)
                else:
                    await context.bot.send_message(chat_id=dest, text=final_caption)
                logger.info(f"Mesaj {dest} kanalına başarıyla yönlendirildi.")
            except Exception as e:
                logger.error(f"{dest} kanalına yönlendirme hatası: {e}")
    except Exception as e:
        logger.error(f"Genel yönlendirici hatası: {e}")
    
    try:
        conn = sqlite3.connect('bot_data.db')
        cursor = conn.cursor()
        cursor.execute("INSERT INTO message_stats (channel_id, message_type, ai_enhanced) VALUES (?, ?, ?)", 
                       (chat_identifier, 'photo' if message.photo else 'text', ai_used))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"İstatistik kaydı hatası: {e}")

# --- Flask Web Sunucusu + AI KONTROL MERKEZİ ---
flask_app = Flask(__name__)
flask_app.secret_key = FLASK_SECRET_KEY
# --- HTML Şablonları ---
HTML_LAYOUT = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>KRBRZ VIP - AI Kontrol Merkezi</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #121212; color: #e0e0e0; margin: 0; padding: 20px; }
        .container { max-width: 900px; margin: auto; background-color: #1e1e1e; padding: 25px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.5); }
        h1, h2 { color: #bb86fc; border-bottom: 2px solid #373737; padding-bottom: 10px; }
        nav { margin-bottom: 20px; display: flex; flex-wrap: wrap; gap: 10px; }
        nav a { color: #03dac6; text-decoration: none; padding: 10px 15px; border-radius: 5px; background-color: #333; transition: background-color 0.3s; }
        nav a:hover { background-color: #444; }
        .card { background-color: #2c2c2c; padding: 20px; border-radius: 8px; margin-bottom: 20px; }
        .form-group { margin-bottom: 15px; }
        label { display: block; margin-bottom: 5px; color: #a0a0a0; }
        textarea, input, select { width: 95%; background-color: #333; border: 1px solid #555; color: #e0e0e0; padding: 10px; border-radius: 5px; font-size: 1em; }
        button { background-color: #bb86fc; color: #121212; border: none; padding: 12px 20px; border-radius: 5px; cursor: pointer; font-size: 1em; font-weight: bold; transition: background-color 0.3s; }
        button:hover { background-color: #a362f7; }
        .persona-cards { display: flex; gap: 15px; justify-content: center; flex-wrap: wrap; }
        .persona-card { flex: 1; min-width: 200px; border: 2px solid #333; padding: 15px; border-radius: 8px; text-align: center; cursor: pointer; transition: all 0.3s; }
        .persona-card.active { border-color: #03dac6; background-color: #03dac620; }
        .persona-card h3 { margin-top: 0; color: #03dac6; }
        .result { background-color: #333; padding: 15px; border-radius: 5px; margin-top: 15px; white-space: pre-wrap; font-family: Consolas, monaco, monospace; }
        table { width: 100%; border-collapse: collapse; margin-top: 15px; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #444; }
        th { background-color: #333; }
        .flash { padding: 15px; margin-bottom: 15px; border-radius: 5px; background-color: #03dac6; color: #121212; }
        pre { background: #111; padding: 10px; border-radius: 5px; white-space: pre-wrap; word-wrap: break-word; }
    </style>
</head>
<body>
    <div class="container">
        {% with messages = get_flashed_messages() %}
            {% if messages %}
                <div class="flash">{{ messages[0] }}</div>
            {% endif %}
        {% endwith %}
        {% block content %}{% endblock %}
    </div>
</body>
</html>
"""

HTML_DASHBOARD = """
{% extends "layout" %}
{% block content %}
    <h1>🚀 KRBRZ VIP - Gelişmiş Kontrol Merkezi</h1>
    <nav>
        <a href="/">Gösterge Paneli</a>
        <a href="/ai-test">AI Metin Test</a>
        <a href="/admins">Admin Yönetimi</a>
        <a href="/watermark">Filigran Ayarları</a>
        <a href="/stats">İstatistikler</a>
        <a href="/logs">Loglar</a>
    </nav>
    <h2>📊 Bot Durumu</h2>
    <div class="card">
        <p><strong>Genel Durum:</strong> {{ '▶️ Çalışıyor' if not is_paused else '⏸️ Duraklatıldı' }}</p>
        <p><strong>Kaynak Kanallar:</strong> {{ source_channels|length }} adet</p>
        <p><strong>Hedef Kanallar:</strong> {{ destination_channels|length }} adet</p>
        <form action="/toggle-pause" method="POST" style="margin-top:15px;">
            <button type="submit">{{ 'Botu Duraklat' if not is_paused else 'Botu Devam Ettir' }}</button>
        </form>
    </div>
    <h2>🎭 AI Persona Yönetimi</h2>
    <div class="card">
        <p>Botun kullanacağı yapay zeka kişiliğini seçin. Tüm metinler bu karaktere göre üretilecektir.</p>
        <div class="persona-cards">
            {% for name in personas %}
            <div class="persona-card {% if name == active_persona %}active{% endif %}" onclick="window.location.href='/set-persona/{{ name }}'">
                <h3>{{ name }}</h3>
                <small>{{ personas[name][:80] }}...</small>
            </div>
            {% endfor %}
        </div>
    </div>
{% endblock %}
"""

HTML_AI_TEST = """
{% extends "layout" %}
{% block content %}
    <h1>🔬 AI Metin Test Paneli</h1>
    <nav>
        <a href="/">Gösterge Paneli</a>
        <a href="/ai-test">AI Metin Test</a>
        <a href="/admins">Admin Yönetimi</a>
        <a href="/watermark">Filigran Ayarları</a>
        <a href="/stats">İstatistikler</a>
        <a href="/logs">Loglar</a>
    </nav>
    <div class="card">
        <form method="POST">
            <div class="form-group">
                <label for="content">Test edilecek orijinal metin:</label>
                <textarea name="content" id="content" rows="4">{{ input_text or '' }}</textarea>
            </div>
            <button type="submit">AI ile Geliştir (Persona: {{ active_persona }})</button>
        </form>
        {% if output_text %}
        <div class="result">
            <strong>✨ AI Sonucu:</strong><br>{{ output_text }}
        </div>
        {% endif %}
    </div>
{% endblock %}
"""

HTML_ADMINS = """
{% extends "layout" %}
{% block content %}
    <h1>👥 Admin Yönetimi</h1>
    <nav>
        <a href="/">Gösterge Paneli</a>
        <a href="/ai-test">AI Metin Test</a>
        <a href="/admins">Admin Yönetimi</a>
        <a href="/watermark">Filigran Ayarları</a>
        <a href="/stats">İstatistikler</a>
        <a href="/logs">Loglar</a>
    </nav>
    <div class="card">
        <h2>Mevcut Adminler</h2>
        <table>
            <thead><tr><th>Kullanıcı ID</th><th>İşlem</th></tr></thead>
            <tbody>
            {% for admin_id in admin_ids %}
                <tr>
                    <td>{{ admin_id }} {% if admin_id == owner_id %}(👑 Kurucu){% endif %}</td>
                    <td>
                        {% if admin_id != owner_id %}
                        <a href="/admins/remove/{{ admin_id }}">Sil</a>
                        {% endif %}
                    </td>
                </tr>
            {% endfor %}
            </tbody>
        </table>
    </div>
    <div class="card">
        <h2>Yeni Admin Ekle</h2>
        <form method="POST">
            <div class="form-group">
                <label for="new_admin_id">Telegram Kullanıcı ID:</label>
                <input type="number" name="new_admin_id" required>
            </div>
            <button type="submit">Ekle</button>
        </form>
    </div>
{% endblock %}
"""

HTML_WATERMARK = """
{% extends "layout" %}
{% block content %}
    <h1>💧 Filigran Ayarları</h1>
    <nav>
        <a href="/">Gösterge Paneli</a>
        <a href="/ai-test">AI Metin Test</a>
        <a href="/admins">Admin Yönetimi</a>
        <a href="/watermark">Filigran Ayarları</a>
        <a href="/stats">İstatistikler</a>
        <a href="/logs">Loglar</a>
    </nav>
    <div class="card">
        <form method="POST">
            <div class="form-group">
                <label for="text">Filigran Metni:</label>
                <input type="text" name="text" value="{{ watermark.text }}">
            </div>
            <div class="form-group">
                <label for="color">Renk:</label>
                <select name="color">
                    <option value="beyaz" {% if watermark.color == 'beyaz' %}selected{% endif %}>Beyaz</option>
                    <option value="siyah" {% if watermark.color == 'siyah' %}selected{% endif %}>Siyah</option>
                    <option value="kirmizi" {% if watermark.color == 'kirmizi' %}selected{% endif %}>Kırmızı</option>
                </select>
            </div>
            <div class="form-group">
                <label for="position">Pozisyon:</label>
                <select name="position">
                    <option value="sag-alt" {% if watermark.position == 'sag-alt' %}selected{% endif %}>Sağ Alt</option>
                    <option value="sol-ust" {% if watermark.position == 'sol-ust' %}selected{% endif %}>Sol Üst</option>
                </select>
            </div>
            <button type="submit">Kaydet</button>
        </form>
    </div>
{% endblock %}
"""

HTML_STATS = """
{% extends "layout" %}
{% block content %}
    <h1>📊 İstatistikler</h1>
    <nav>
        <a href="/">Gösterge Paneli</a>
        <a href="/ai-test">AI Metin Test</a>
        <a href="/admins">Admin Yönetimi</a>
        <a href="/watermark">Filigran Ayarları</a>
        <a href="/stats">İstatistikler</a>
        <a href="/logs">Loglar</a>
    </nav>
    <div class="card">
        <h2>Günlük Mesaj İstatistikleri</h2>
        {% if stats %}
        <table>
            <thead><tr><th>Tarih</th><th>Toplam Mesaj</th></tr></thead>
            <tbody>
            {% for row in stats %}
                <tr>
                    <td>{{ row.day }}</td>
                    <td>{{ row.count }}</td>
                </tr>
            {% endfor %}
            </tbody>
        </table>
        {% else %}
        <p>Henüz görüntülenecek istatistik yok.</p>
        {% endif %}
    </div>
{% endblock %}
"""

HTML_LOGS = """
{% extends "layout" %}
{% block content %}
    <h1>📝 Bot Logları</h1>
    <nav>
        <a href="/">Gösterge Paneli</a>
        <a href="/ai-test">AI Metin Test</a>
        <a href="/admins">Admin Yönetimi</a>
        <a href="/watermark">Filigran Ayarları</a>
        <a href="/stats">İstatistikler</a>
        <a href="/logs">Loglar</a>
    </nav>
    <div class="card">
        <h2>Son 100 Log Kaydı</h2>
        <pre>{{ logs }}</pre>
    </div>
{% endblock %}
"""

@flask_app.route('/')
def home():
    context = {
        "is_paused": bot_config.get('is_paused', False),
        "source_channels": bot_config.get('source_channels', []),
        "destination_channels": bot_config.get('destination_channels', []),
        "active_persona": bot_config.get('ai_persona'),
        "personas": bot_config.get('personas', {})
    }
    full_html = HTML_LAYOUT.replace('{% block content %}{% endblock %}', HTML_DASHBOARD)
    return render_template_string(full_html, **context)

@flask_app.route('/toggle-pause', methods=['POST'])
def toggle_pause_web():
    bot_config["is_paused"] = not bot_config.get("is_paused", False)
    save_config()
    flash("Bot durumu güncellendi.")
    return redirect(url_for('home'))

@flask_app.route('/set-persona/<string:name>')
def set_persona(name):
    if name in bot_config.get('personas', {}):
        bot_config['ai_persona'] = name
        save_config()
        flash(f"AI Kişiliği '{name}' olarak ayarlandı.")
    return redirect(url_for('home'))

@flask_app.route('/ai-test', methods=['GET', 'POST'])
def ai_test():
    input_text, output_text = "", ""
    if request.method == 'POST':
        input_text = request.form.get('content')
        if input_text:
            try:
                # DÜZELTME: Daha güvenli asenkron çalıştırma
                output_text = asyncio.run(enhance_text_with_gemini_smarter(input_text))
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                output_text = loop.run_until_complete(enhance_text_with_gemini_smarter(input_text))
                loop.close()
    context = { "active_persona": bot_config.get('ai_persona'), "input_text": input_text, "output_text": output_text }
    full_html = HTML_LAYOUT.replace('{% block content %}{% endblock %}', HTML_AI_TEST)
    return render_template_string(full_html, **context)

@flask_app.route('/admins', methods=['GET', 'POST'])
def manage_admins():
    if request.method == 'POST':
        new_admin_id = int(request.form.get('new_admin_id'))
        if new_admin_id not in bot_config['admin_ids']:
            bot_config['admin_ids'].append(new_admin_id)
            save_config()
            flash(f"Admin {new_admin_id} eklendi.")
    context = {"admin_ids": bot_config.get('admin_ids', []), "owner_id": ADMIN_USER_ID}
    full_html = HTML_LAYOUT.replace('{% block content %}{% endblock %}', HTML_ADMINS)
    return render_template_string(full_html, **context)

@flask_app.route('/admins/remove/<int:admin_id>')
def remove_admin(admin_id):
    if admin_id != ADMIN_USER_ID and admin_id in bot_config['admin_ids']:
        bot_config['admin_ids'].remove(admin_id)
        save_config()
        flash(f"Admin {admin_id} silindi.")
    return redirect(url_for('manage_admins'))

@flask_app.route('/watermark', methods=['GET', 'POST'])
def manage_watermark():
    if request.method == 'POST':
        bot_config['watermark']['text'] = request.form.get('text')
        bot_config['watermark']['color'] = request.form.get('color')
        bot_config['watermark']['position'] = request.form.get('position')
        save_config()
        flash("Filigran ayarları kaydedildi.")
    full_html = HTML_LAYOUT.replace('{% block content %}{% endblock %}', HTML_WATERMARK)
    return render_template_string(full_html, watermark=bot_config.get('watermark', {}))

@flask_app.route('/stats')
def show_stats():
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute("SELECT date(timestamp) as day, COUNT(*) as count FROM message_stats GROUP BY day ORDER BY day DESC LIMIT 30")
    stats_data = [{"day": row[0], "count": row[1]} for row in cursor.fetchall()]
    conn.close()
    full_html = HTML_LAYOUT.replace('{% block content %}{% endblock %}', HTML_STATS)
    return render_template_string(full_html, stats=stats_data)

@flask_app.route('/logs')
def show_logs():
    try:
        with open(LOG_FILE, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            log_content = "".join(lines[-100:])
    except FileNotFoundError:
        log_content = "Log dosyası henüz oluşturulmadı."
    full_html = HTML_LAYOUT.replace('{% block content %}{% endblock %}', HTML_LOGS)
    return render_template_string(full_html, logs=log_content)

# --- Botun Başlatılması ---
def main():
    logger.info("🚀 KRBRZ VIP Bot başlatılıyor...")
    application = Application.builder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("ayarla", setup_command))
    application.add_handler(CommandHandler("durum", status_command))
    application.add_handler(CommandHandler("durdur", pause_command))
    
    application.add_handler(CallbackQueryHandler(menu_callback_handler))
    # DÜZELTME: filters.REPLY, kütüphane versiyonuna göre uyumlu hale getirildi.
    application.add_handler(MessageHandler(filters.REPLY & filters.TEXT & ~filters.COMMAND, reply_handler))
    
    application.add_handler(MessageHandler(filters.ALL & filters.ChatType.CHANNEL, forwarder))
    
    logger.info("✅ Bot başarıyla yapılandırıldı ve dinlemede.")
    application.run_polling(drop_pending_updates=True)

def run_flask():
    flask_app.run(host='0.0.0.0', port=PORT, debug=False)

if __name__ == "__main__":
    Thread(target=run_flask, daemon=True).start()
    logger.info(f"🌐 Flask sunucusu {PORT} portunda başlatıldı.")
    main()

