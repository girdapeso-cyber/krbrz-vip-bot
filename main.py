# -*- coding: utf-8 -*-
"""
KRBRZ VIP Bot - Gelişmiş AI ile Telegram Botu
Bu versiyon, interaktif AI başlık öneri sistemi içerir.
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

# --- Güvenli Ortam Değişkenleri ---
try:
    BOT_TOKEN = os.environ['BOT_TOKEN']
    ADMIN_USER_ID = int(os.environ['ADMIN_USER_ID'])
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
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
            "ai_model": "gemini-1.5-pro-latest",
            "watermark": {"text": "KRBRZ_VIP", "position": "sag-alt", "color": "beyaz", "enabled": True},
            "admin_ids": [],
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

# --- YENİ GELİŞMİŞ YAPAY ZEKA FONKSİYONLARI ---
@lru_cache(maxsize=50)
async def generate_multiple_captions_smarter(image_bytes: bytes) -> List[str]:
    if not GEMINI_API_KEY:
        return ["Varsayılan Başlık 1", "Varsayılan Başlık 2", "Varsayılan Başlık 3"]

    model_name = bot_config.get("ai_model", "gemini-1.5-pro-latest")
    image_b64 = base64.b64encode(image_bytes).decode('utf-8')
    
    user_prompt = (
        "Bu bir PUBG Mobile oyununa ait ekran görüntüsü. Görüntüyü dikkatlice analiz et ve içeriğini anla (zafer anı mı, çatışma mı, komik bir olay mı vb.). "
        "Bu analize dayanarak, 3 FARKLI tonda kısa ve etkileyici sosyal medya başlığı üret. Her başlığın sonunda '@KRBRZ063 #KRBRZ #PUBG' etiketleri bulunsun."
        "Tonlar şunlar olsun:\n"
        "1. **Agresif ve Rekabetçi:** Güç ve zafer vurgusu yap. (Örn: Rakipler diz çöktü!)\n"
        "2. **Mizahi ve Eğlenceli:** Oyundaki komik veya absürt bir duruma odaklan. (Örn: Tava yine hayat kurtardı!)\n"
        "3. **Profesyonel ve Bilgilendirici:** Güvenilirlik ve kalite vurgusu yap. (Örn: Kesintisiz oyun deneyimi için...)\n"
        "Sonucu, sadece 3 başlığı içeren bir JSON listesi olarak döndür. Başka hiçbir açıklama ekleme. Örnek: "
        '["Agresif başlık burada.", "Mizahi başlık burada.", "Profesyonel başlık burada."]'
    )
    
    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={GEMINI_API_KEY}"
    payload = {
        "contents": [{"parts": [
            {"text": user_prompt},
            {"inline_data": {"mime_type": "image/jpeg", "data": image_b64}}
        ]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.8
        }
    }
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(api_url, json=payload)
            response.raise_for_status()
            result = response.json()
            json_string = result.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "[]")
            captions = json.loads(json_string)
            return captions if isinstance(captions, list) and len(captions) > 0 else []
    except Exception as e:
        logger.error(f"Çoklu başlık üretme API hatası: {e}")
        return []

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
        "Tüm ayarları ve komutları görmek için `/ayarla` yazın."
        , parse_mode='Markdown'
    )

# --- İNTERAKTİF PAYLAŞIM SİSTEMİ ---
@admin_only
async def caption_choice_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data.split('_')
    action = data[1]
    post_id = data[2]

    post_data = context.bot_data.get(post_id)
    if not post_data:
        await query.edit_message_text("❌ Bu gönderi zaman aşımına uğradı veya bulunamadı.")
        return

    photo_bytes = post_data['photo']
    original_caption = post_data['original_caption']
    
    final_caption = ""
    if action == 'cancel':
        await query.edit_message_text("✅ Gönderim iptal edildi.")
        del context.bot_data[post_id]
        return
    elif action == 'manual':
        final_caption = original_caption
    else: # Bir AI önerisi seçildi
        choice_index = int(action)
        final_caption = post_data['suggestions'][choice_index]

    await query.edit_message_text("🚀 Gönderiliyor...")
    
    watermarked_photo = await apply_watermark(photo_bytes)
    success_count = 0
    for dest in bot_config["destination_channels"]:
        try:
            await context.bot.send_photo(chat_id=dest, photo=watermarked_photo, caption=final_caption)
            success_count += 1
        except Exception as e:
            logger.error(f"{dest} kanalına gönderim hatası: {e}")

    await query.edit_message_text(f"✅ Gönderim tamamlandı! {success_count} kanala gönderildi.")
    del context.bot_data[post_id]

# --- Ana Mesaj Yönlendirici ---
@admin_only
async def forwarder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if bot_config["is_paused"]: return
    message = update.channel_post
    if not message: return

    chat_identifier = f"@{message.chat.username}" if message.chat.username else str(message.chat.id)
    if chat_identifier not in bot_config["source_channels"]: return

    if not message.photo or not bot_config.get("ai_image_analysis_enabled", True):
        # Eğer AI kapalıysa veya fotoğraf yoksa, eski yöntemle direkt gönder
        # (Bu kısmı isterseniz daha sonra ekleyebiliriz, şimdilik sadece AI odaklı)
        logger.info(f"{chat_identifier} kanalından AI kapalı olduğu için veya fotoğraf olmadığı için standart gönderim yapılacak.")
        # ... standart gönderim kodu buraya eklenebilir ...
        return

    await context.bot.send_message(chat_id=ADMIN_USER_ID, text="⏳ Yeni bir görsel algılandı. AI başlık önerileri üretiliyor...")

    file = await message.photo[-1].get_file()
    photo_bytes = await file.download_as_bytearray()
    
    suggestions = await generate_multiple_captions_smarter(bytes(photo_bytes))
    
    if not suggestions:
        await context.bot.send_message(chat_id=ADMIN_USER_ID, text="❌ AI başlık üretemedi. Lütfen logları kontrol edin.")
        return

    post_id = str(uuid.uuid4())
    context.bot_data[post_id] = {
        'photo': bytes(photo_bytes),
        'suggestions': suggestions,
        'original_caption': message.caption or "Zirve bizimdir! 👑 @KRBRZ063 #KRBRZ"
    }

    keyboard = []
    for i, caption in enumerate(suggestions):
        keyboard.append([InlineKeyboardButton(f"'{caption[:30]}...'", callback_data=f'caption_{i}_{post_id}')])
    
    keyboard.append([InlineKeyboardButton("✍️ Orijinal Yazıyı Kullan", callback_data=f'caption_manual_{post_id}')])
    keyboard.append([InlineKeyboardButton("❌ İptal Et", callback_data=f'caption_cancel_{post_id}')])

    await context.bot.send_photo(
        chat_id=ADMIN_USER_ID,
        photo=bytes(photo_bytes),
        caption="👇 Lütfen bu görsel için bir başlık seçin:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# --- Botun Başlatılması ---
def main():
    logger.info("🚀 KRBRZ VIP Bot başlatılıyor (Sadece Telegram Modu)...")
    application = Application.builder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start_command))
    # DİĞER KOMUTLAR (ayarla, durum vb.) ŞİMDİLİK DEVRE DIŞI BIRAKILDI
    # ÇÜNKÜ YENİ SİSTEM DAHA FARKLI ÇALIŞIYOR.
    
    # Yeni interaktif sistemin handler'ları
    application.add_handler(CallbackQueryHandler(caption_choice_handler, pattern=r'^caption_'))
    application.add_handler(MessageHandler(filters.ChatType.CHANNEL, forwarder))
    
    logger.info("✅ Bot başarıyla yapılandırıldı ve dinlemede.")
    application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()

