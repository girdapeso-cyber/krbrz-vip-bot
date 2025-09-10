# -*- coding: utf-8 -*-
"""
KRBRZ VIP Bot - Gelişmiş AI ile Telegram Botu
Bu versiyon, API limitlerine karşı "Exponential Backoff" mekanizması ile güçlendirilmiştir.
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
from threading import Lock
from typing import List, Dict
import httpx
from PIL import Image, ImageDraw, ImageFont
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ForceReply
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters, ContextTypes,
    CallbackQueryHandler
)
from functools import lru_cache
import uuid
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import time
from flask import Flask, render_template_string, request, redirect, url_for, flash
from threading import Thread

# --- Güvenli Ortam Değişkenleri ---
try:
    BOT_TOKEN = os.environ['BOT_TOKEN']
    ADMIN_USER_ID = int(os.environ['ADMIN_USER_ID'])
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
    PORT = int(os.environ.get('PORT', 5000))
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

# --- Konfigürasyon Yönetimi ---
CONFIG_FILE = "bot_config.json"
config_lock = Lock()

def load_config():
    with config_lock:
        defaults = {
            "source_channels": [], "destination_channels": [], "is_paused": False,
            "ai_text_enhancement_enabled": True, "ai_image_analysis_enabled": True,
            "ai_model": "gemini-1.5-flash-latest", # Varsayılan model Flash olarak ayarlandı.
            "ai_persona": "Agresif Pazarlamacı",
            "personas": {
                "Agresif Pazarlamacı": "Sen KRBRZ VIP BYPASS adlı bir emülatör bypass'ı satıyorsun. Agresif, iddialı ve güçlü bir dil kullan. Cümlelerin sonunda mutlaka '@KRBRZ063 #KRBRZVipBypass #PUBG' etiketleri bulunsun.",
                "Profesyonel Satıcı": "Sen KRBRZ VIP BYPASS adlı bir emülatör bypass'ı satıyorsun. Net, güvenilir ve profesyonel bir dil kullan. Cümlelerin sonunda mutlaka '@KRBRZ063 #KRBRZVipBypass #PUBG' etiketleri bulunsun.",
                "Eğlenceli Oyuncu": "Sen KRBRZ VIP BYPASS kullanan yetenekli ve eğlenceli bir oyuncusun. Samimi bir dil kullan. Cümlelerin sonunda mutlaka '@KRBRZ063 #KRBRZVipBypass #PUBG' etiketleri bulunsun."
            },
            "watermark": {"text": "KRBRZ_VIP", "position": "sag-alt", "color": "beyaz", "enabled": True},
            "admin_ids": [], "auto_post_enabled": True, "auto_post_time": "19:00"
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

# --- YAPAY ZEKA FONKSİYONLARI ---

async def api_request_with_backoff(api_url: str, payload: Dict) -> Dict:
    """API'ye üstel geri çekilme ile istek gönderir."""
    max_retries = 5
    base_delay = 2
    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(api_url, json=payload)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                delay = base_delay * (2 ** attempt)
                logger.warning(f"API Rate limit aşıldı. {delay} saniye bekleniyor...")
                await asyncio.sleep(delay)
            else:
                logger.error(f"API'ye istekte HTTP hatası: {e}")
                return {}
        except Exception as e:
            logger.error(f"API'ye istekte beklenmedik hata: {e}")
            return {}
    logger.error("Maksimum deneme sayısına ulaşıldı, API isteği başarısız.")
    return {}

def get_ai_persona_prompt(persona: str) -> str:
    return bot_config.get("personas", {}).get(persona, "Normal bir şekilde yaz.")

async def enhance_text_with_gemini_smarter(original_text: str) -> str:
    """Metin tabanlı AI geliştirmesi için fonksiyon."""
    if not GEMINI_API_KEY or not original_text: return original_text + " @KRBRZ063 #KRBRZVipBypass"
    model_name = bot_config.get("ai_model", "gemini-1.5-flash-latest")
    persona_prompt = get_ai_persona_prompt(bot_config.get("ai_persona", "Agresif Pazarlamacı"))
    user_prompt = f"Senin ürünün 'KRBRZ VIP BYPASS' adlı bir emülatör bypass'ı. Sana verilen '{original_text}' metnini analiz et. Bu metnin ana fikrine (örn: güncelleme, bakım, satış) uygun olarak, seçtiğim kişiliğe göre kısa ve dikkat çekici bir sosyal medya başlığı oluştur. Sadece oluşturduğun başlığı yaz."
    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={GEMINI_API_KEY}"
    payload = {"contents": [{"parts": [{"text": user_prompt}]}],"systemInstruction": {"parts": [{"text": persona_prompt}]},"generationConfig": {"maxOutputTokens": 80,"temperature": 0.8,"topP": 0.9,"topK": 40}}
    result = await api_request_with_backoff(api_url, payload)
    if not result:
        return original_text + " @KRBRZ063 #KRBRZVipBypass"
    try:
        return result.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip() or original_text
    except IndexError:
        logger.error(f"AI Metin çıktısı işlenemedi.")
        return original_text + " @KRBRZ063 #KRBRZVipBypass"

async def generate_caption_from_image(image_bytes: bytes) -> str:
    """Bir görsel için tek, akıllı bir başlık üretir."""
    if not GEMINI_API_KEY: return "Zirve bizimdir! 👑 @KRBRZ063 #KRBRZVipBypass"
    model_name = bot_config.get("ai_model", "gemini-1.5-flash-latest")
    persona_prompt = get_ai_persona_prompt(bot_config.get("ai_persona", "Agresif Pazarlamacı"))
    image_b64 = base64.b64encode(image_bytes).decode('utf-8')
    user_prompt = ("Bu bir PUBG Mobile emülatör oyununa ait ekran görüntüsü. Sattığımız ürünün adı 'KRBRZ VIP BYPASS'. "
                   "Görüntüyü analiz et ve içeriğine (zafer, çatışma vb.) uygun olarak, seçtiğim kişiliğe göre kısa, satış odaklı ve etkileyici tek bir sosyal medya başlığı oluştur. "
                   "Sadece oluşturduğun başlığı yaz, başka bir şey ekleme.")
    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={GEMINI_API_KEY}"
    payload = {"contents": [{"parts": [{"text": user_prompt}, {"inline_data": {"mime_type": "image/jpeg", "data": image_b64}}]}],"systemInstruction": {"parts": [{"text": persona_prompt}]},"generationConfig": {"maxOutputTokens": 80,"temperature": 0.8}}
    result = await api_request_with_backoff(api_url, payload)
    if not result:
        return "Zirve bizimdir! 👑 @KRBRZ063 #KRBRZVipBypass"
    try:
        return result.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip() or "Zirve bizimdir! 👑"
    except IndexError:
        logger.error(f"AI Görsel başlık çıktısı işlenemedi.")
        return "Zirve bizimdir! 👑 @KRBRZ063 #KRBRZVipBypass"


async def generate_automated_post(application: Application) -> None:
    logger.info("Otomatik gönderi zamanı geldi, AI içerik üretiyor...")
    if not GEMINI_API_KEY: 
        logger.warning("Otomatik gönderi için Gemini API anahtarı bulunamadı.")
        return

    user_prompt = "KRBRZ VIP BYPASS ürününü tanıtmak için, insanları satın almaya teşvik eden, kısa ve güçlü bir reklam metni yaz. FOMO (kaçırma korkusu) veya ayrıcalık gibi satış taktikleri kullan."
    
    post_text = await enhance_text_with_gemini_smarter(user_prompt)
    if not post_text:
        logger.error("Otomatik gönderi için AI içerik üretemedi.")
        return
    
    for dest in bot_config["destination_channels"]:
        try:
            await application.bot.send_message(chat_id=dest, text=post_text)
            logger.info(f"Otomatik gönderi {dest} kanalına gönderildi.")
        except Exception as e:
            logger.error(f"Otomatik gönderi hatası ({dest}): {e}")
async def generate_user_reply(user_message: str) -> str:
    if not GEMINI_API_KEY: return "Merhaba, KRBRZ VIP BYPASS ile ilgilendiğiniz için teşekkürler. Detaylar için ana kanalımızı takip edin."
    persona = get_ai_persona_prompt("Profesyonel Satıcı")
    user_prompt = f"Bir müşteri sana şu soruyu sordu: '{user_message}'. Ona KRBRZ VIP BYPASS ürününü tanıtan, ana kanala yönlendiren, kibar ve profesyonel bir yanıt yaz."
    
    return await enhance_text_with_gemini_smarter(user_prompt)
async def apply_watermark(photo_bytes: bytes) -> bytes:
    wm_config = bot_config.get("watermark", {})
    if not wm_config.get("enabled"): return photo_bytes
    try:
        with Image.open(io.BytesIO(photo_bytes)).convert("RGBA") as base:
            txt = Image.new("RGBA", base.size, (255, 255, 255, 0))
            font_size = max(15, base.size[1] // 25)
            font = None
            font_paths = ['/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 'arial.ttf', '/System/Library/Fonts/Supplemental/Arial.ttf']
            for path in font_paths:
                try:
                    font = ImageFont.truetype(path, size=font_size)
                    break
                except IOError:
                    continue
            if not font:
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
        "Tüm komutları görmek ve ayarları yönetmek için `/ayarla` yazın."
        , parse_mode='Markdown'
    )
@admin_only
async def pause_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot_config["is_paused"] = not bot_config.get("is_paused", False)
    save_config()
    status_text = "⏸️ Duraklatıldı" if bot_config["is_paused"] else "▶️ Devam Ettiriliyor"
    await update.message.reply_text(f"**Bot mesaj iletimi {status_text}**", parse_mode='Markdown')

# --- YENİ TELEGRAM KONTROL MERKEZİ ---
async def get_main_menu_content():
    text_ai_status = "✅" if bot_config["ai_text_enhancement_enabled"] else "❌"
    image_ai_status = "✅" if bot_config["ai_image_analysis_enabled"] else "❌"
    wm_status = "✅" if bot_config['watermark']['enabled'] else "❌"
    auto_post_status = "✅" if bot_config['auto_post_enabled'] else "❌"
    text = "🚀 **KRBRZ VIP - Kontrol Merkezi**"
    keyboard = [
        [InlineKeyboardButton("📡 Kaynak Kanalları", callback_data='menu_channels_source'), InlineKeyboardButton("📤 Hedef Kanalları", callback_data='menu_channels_destination')],
        [InlineKeyboardButton("👥 Admin Yönetimi", callback_data='menu_admins')],
        [InlineKeyboardButton(f"{text_ai_status} Akıllı Metin", callback_data='toggle_text_ai'), InlineKeyboardButton(f"{image_ai_status} Akıllı Görüntü", callback_data='toggle_image_ai')],
        [InlineKeyboardButton("🧠 AI Ayarları", callback_data='menu_ai_settings'), InlineKeyboardButton(f"{wm_status} Filigran", callback_data='toggle_watermark')],
        [InlineKeyboardButton(f"{auto_post_status} Oto. Gönderi ({bot_config['auto_post_time']})", callback_data='toggle_auto_post')],
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
async def get_admins_menu_content():
    admins = bot_config.get('admin_ids', [])
    text = "👥 **Admin Yönetimi**\n\nMevcut adminler:\n" + ("\n".join(f"`{admin_id}`" for admin_id in admins) or "_Boş_")
    keyboard = [[InlineKeyboardButton(f"🗑️ Sil: {admin_id}", callback_data=f'remove_admin_{admin_id}')] for admin_id in admins if admin_id != ADMIN_USER_ID]
    keyboard.append([InlineKeyboardButton("➕ Yeni Admin Ekle", callback_data=f'add_admin')])
    keyboard.append([InlineKeyboardButton("⬅️ Ana Menüye Dön", callback_data='menu_main')])
    return text, InlineKeyboardMarkup(keyboard)
async def get_ai_settings_menu_content():
    text = f"🧠 **AI Ayarları**\n\n- Aktif Model: `{bot_config['ai_model']}`\n- Aktif Persona: `{bot_config['ai_persona']}`"
    keyboard = [
        [InlineKeyboardButton("🤖 Modeli Değiştir", callback_data='menu_ai_model')],
        [InlineKeyboardButton("🎭 Personayı Değiştir", callback_data='menu_persona')],
        [InlineKeyboardButton("⬅️ Geri", callback_data='menu_main')],
    ]
    return text, InlineKeyboardMarkup(keyboard)
async def get_persona_menu_content():
    text = "🎭 Yapay zeka için bir kişilik seçin:"
    keyboard = [
        [InlineKeyboardButton(f"{'➡️ ' if bot_config['ai_persona'] == p else ''}{p}", callback_data=f'set_persona_{p}')] for p in bot_config['personas']
    ]
    keyboard.append([InlineKeyboardButton("⬅️ Geri", callback_data='menu_ai_settings')])
    return text, InlineKeyboardMarkup(keyboard)
async def get_model_menu_content():
    text = "🤖 Kullanılacak AI modelini seçin:"
    models = ["gemini-1.5-flash-latest", "gemini-1.5-pro-latest"]
    keyboard = [
        [InlineKeyboardButton(f"{'➡️ ' if bot_config['ai_model'] == m else ''}{m}", callback_data=f'set_model_{m}')] for m in models
    ]
    keyboard.append([InlineKeyboardButton("⬅️ Geri", callback_data='menu_ai_settings')])
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
    data = query.data
    text, reply_markup = None, None
    toggle_map = {"toggle_text_ai": "Akıllı Metin", "toggle_image_ai": "Akıllı Görüntü", "toggle_watermark": "Filigran", "toggle_auto_post": "Otomatik Gönderi"}
    if data in toggle_map:
        await query.answer()
        key_part = data.replace('toggle_', '')
        config_key = 'enabled' if key_part == 'watermark' else f'{key_part}_enabled'
        target_dict = bot_config['watermark'] if key_part == 'watermark' else bot_config
        target_dict[config_key] = not target_dict[config_key]
        status = "açıldı" if target_dict[config_key] else "kapatıldı"
        await query.answer(f"✅ {toggle_map[data]} {status}", show_alert=True)
        save_config()
        text, reply_markup = await get_main_menu_content()
    elif data == 'menu_main':
        await query.answer()
        text, reply_markup = await get_main_menu_content()
    elif data.startswith('menu_channels_'):
        await query.answer()
        channel_type = data.split('_')[-1]
        text, reply_markup = await get_channels_menu_content(channel_type)
    elif data == 'menu_admins':
        await query.answer()
        text, reply_markup = await get_admins_menu_content()
    elif data == 'menu_ai_settings':
        await query.answer()
        text, reply_markup = await get_ai_settings_menu_content()
    elif data == 'menu_persona':
        await query.answer()
        text, reply_markup = await get_persona_menu_content()
    elif data == 'menu_ai_model':
        await query.answer()
        text, reply_markup = await get_model_menu_content()
    elif data.startswith('set_persona_'):
        persona = data.replace('set_persona_', '')
        bot_config["ai_persona"] = persona
        save_config()
        await query.answer(f"✅ Kişilik '{persona}' olarak ayarlandı")
        text, reply_markup = await get_ai_settings_menu_content()
    elif data.startswith('set_model_'):
        await query.answer()
        model = data.replace('set_model_', '')
        bot_config["ai_model"] = model
        save_config()
        await query.answer(f"✅ Model '{model}' olarak ayarlandı", show_alert=True)
        text, reply_markup = await get_ai_settings_menu_content()
    elif data.startswith('add_'):
        await query.answer()
        item_type = data.replace('add_', '')
        context_map = {'source': 'Kaynak Kanalı', 'destination': 'Hedef Kanalı', 'admin': 'Admin ID'}
        prompt_text = f"➕ Eklenecek yeni **{context_map[item_type]}** adını/ID'sini yazıp bu mesaja yanıt verin."
        await query.message.delete()
        context.user_data.pop('menu_message_id', None)
        sent_reply_message = await query.message.reply_text(prompt_text, reply_markup=ForceReply(selective=True), parse_mode='Markdown')
        context.user_data['force_reply_info'] = {'type': f'add_{item_type}', 'message_id': sent_reply_message.message_id}
        return
    elif data.startswith('remove_'):
        await query.answer()
        _, item_type, item_id_str = data.split('_', 2)
        if item_type in ["source", "destination"]:
            config_key = f"{item_type}_channels"
            item_id = item_id_str
        else:
            config_key = "admin_ids"
            item_id = int(item_id_str)
        if item_id in bot_config[config_key]:
            bot_config[config_key].remove(item_id)
            save_config()
            await query.answer(f"🗑️ {item_id} silindi.", show_alert=True)
        if item_type in ["source", "destination"]:
             text, reply_markup = await get_channels_menu_content(item_type)
        else:
             text, reply_markup = await get_admins_menu_content()
    elif data == 'menu_close':
        await query.answer()
        await query.message.delete()
        context.user_data.pop('menu_message_id', None)
        await query.message.reply_text("ℹ️ Menü kapatıldı. Tekrar açmak için /ayarla yazın.")
        return
    if text and reply_markup:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
@admin_only
async def reply_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message or 'force_reply_info' not in context.user_data:
        return
    reply_info = context.user_data['force_reply_info']
    if update.message.reply_to_message.message_id != reply_info['message_id']:
        return
    item_type = reply_info['type'].replace('add_', '')
    item_value = update.message.text.strip()
    if item_type in ['source', 'destination']:
        config_key = f"{item_type}_channels"
        if not item_value.startswith("@") and not item_value.startswith("-100"):
            item_value = f"@{item_value}"
        if item_value not in bot_config[config_key]:
            bot_config[config_key].append(item_value)
            save_config()
    elif item_type == 'admin':
        try:
            admin_id = int(item_value)
            if admin_id not in bot_config['admin_ids']:
                bot_config['admin_ids'].append(admin_id)
                save_config()
        except ValueError:
            pass
    await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=reply_info['message_id'])
    await update.message.delete()
    del context.user_data['force_reply_info']
    await setup_command(update, context)

async def forwarder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if bot_config["is_paused"]: return
    message = update.channel_post
    if not message: return
    chat_identifier = f"@{message.chat.username}" if message.chat.username else str(message.chat.id)
    if (chat_identifier not in bot_config["source_channels"] and str(message.chat.id) not in bot_config["source_channels"]):
        return

    ai_used = False
    try:
        final_caption = ""
        photo_bytes = None

        if message.photo:
            file = await message.photo[-1].get_file()
            photo_bytes = await file.download_as_bytearray()
            photo_bytes = bytes(photo_bytes)

        if photo_bytes and bot_config["ai_image_analysis_enabled"]:
            final_caption = await generate_caption_from_image(photo_bytes)
            ai_used = True
        elif (message.text or message.caption) and bot_config["ai_text_enhancement_enabled"]:
            original_text = message.text or message.caption
            final_caption = await enhance_text_with_gemini_smarter(original_text)
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
                    await context.bot.send_video(chat_id=dest, video=message.video.file_id, caption=final_caption)
                elif message.text:
                    await context.bot.send_message(chat_id=dest, text=final_caption)
                else:
                    await message.copy(chat_id=dest)
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
async def user_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id in bot_config.get('admin_ids', [ADMIN_USER_ID]):
        return
    user_text = update.message.text
    await update.message.reply_chat_action('typing')
    ai_reply = await generate_user_reply(user_text)
    await update.message.reply_text(ai_reply, parse_mode='Markdown')

@admin_only
async def list_channels_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    source = "\n".join(f"`{ch}`" for ch in bot_config['source_channels']) or "_Yok_"
    dest = "\n".join(f"`{ch}`" for ch in bot_config['destination_channels']) or "_Yok_"
    text = f"📡 **Kaynak Kanallar:**\n{source}\n\n📤 **Hedef Kanallar:**\n{dest}"
    await update.message.reply_text(text, parse_mode='Markdown')

@admin_only
async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute("SELECT date(timestamp) as day, COUNT(*) as count FROM message_stats WHERE date(timestamp) = date('now')")
    today_stats = cursor.fetchone()
    cursor.execute("SELECT COUNT(*) FROM message_stats")
    total_stats = cursor.fetchone()
    conn.close()
    
    today_count = today_stats[1] if today_stats and today_stats[1] is not None else 0
    total_count = total_stats[0] if total_stats and total_stats[0] is not None else 0
    
    text = f"📊 **Mesaj İstatistikleri**\n\n- **Bugün İşlenen:** `{today_count}`\n- **Toplam İşlenen:** `{total_count}`"
    await update.message.reply_text(text, parse_mode='Markdown')
    
@admin_only
async def logs_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        with open(LOG_FILE, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            log_content = "".join(lines[-20:])
        if not log_content: log_content = "Log dosyası boş."
        await update.message.reply_text(f"📝 **Son 20 Log Kaydı:**\n\n`{log_content}`", parse_mode='Markdown')
    except FileNotFoundError:
        await update.message.reply_text("Log dosyası henüz oluşturulmadı.")

@admin_only
async def test_ai_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Kullanım: `/testai <denenecek metin>`")
        return
    
    original_text = " ".join(context.args)
    await update.message.reply_chat_action('typing')
    enhanced_text = await enhance_text_with_gemini_smarter(original_text)
    await update.message.reply_text(f"**Orijinal:**\n`{original_text}`\n\n**✨ AI Sonucu:**\n`{enhanced_text}`", parse_mode='Markdown')

# --- Botun Başlatılması ---
def main():
    logger.info("🚀 KRBRZ VIP Bot başlatılıyor (Tamamen Telegram Entegre)...")
    init_database()
    application = Application.builder().token(BOT_TOKEN).build()
    
    scheduler = AsyncIOScheduler(timezone="Europe/Istanbul")
    if bot_config.get("auto_post_enabled"):
        time_parts = bot_config.get("auto_post_time", "19:00").split(':')
        scheduler.add_job(generate_automated_post, 'cron', hour=int(time_parts[0]), minute=int(time_parts[1]), args=[application])
        scheduler.start()
        logger.info(f"Otomatik gönderi saat {bot_config['auto_post_time']} için zamanlandı.")

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("ayarla", setup_command))
    application.add_handler(CommandHandler("durdur", pause_command))
    application.add_handler(CommandHandler("kanallar", list_channels_command))
    application.add_handler(CommandHandler("istatistik", stats_command))
    application.add_handler(CommandHandler("loglar", logs_command))
    application.add_handler(CommandHandler("testai", test_ai_command))
    
    application.add_handler(CallbackQueryHandler(menu_callback_handler))
    application.add_handler(MessageHandler(filters.REPLY & filters.TEXT & ~filters.COMMAND, reply_handler))
    
    application.add_handler(MessageHandler(filters.ALL & filters.ChatType.CHANNEL, forwarder))
    application.add_handler(MessageHandler(filters.ChatType.PRIVATE & ~filters.COMMAND, user_message_handler))
    
    logger.info("✅ Bot başarıyla yapılandırıldı ve dinlemede.")
    application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()

