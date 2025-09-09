# -*- coding: utf-8 -*-
"""
KRBRZ VIP Bot - Advanced AI-Powered Telegram Bot
Railway optimized version with enhanced features
"""

# --- Required Libraries ---
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
from flask import Flask, render_template_string, jsonify, request
from functools import lru_cache
import schedule
import time

# --- Secure Environment Variables ---
try:
    BOT_TOKEN = os.environ['BOT_TOKEN']
    ADMIN_USER_ID = int(os.environ['ADMIN_USER_ID'])
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
    PORT = int(os.environ.get('PORT', 5000))
except (KeyError, ValueError) as e:
    print(f"!!! HATA: Gerekli environment variable bulunamadı: {e}")
    exit()

# --- Enhanced Logging ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("bot.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# --- Database Setup ---
def init_database():
    """Initialize SQLite database for statistics and scheduling"""
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    
    # Statistics table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS message_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_id TEXT,
            message_type TEXT,
            ai_enhanced BOOLEAN,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            engagement_score INTEGER DEFAULT 0
        )
    ''')
    
    # Scheduled messages table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS scheduled_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT,
            channels TEXT,
            schedule_time DATETIME,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            sent BOOLEAN DEFAULT FALSE
        )
    ''')
    
    # Templates table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS message_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            content TEXT,
            category TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()

init_database()

# --- Configuration Management ---
CONFIG_FILE = "bot_config.json"

def load_config():
    """Load configuration with enhanced defaults"""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = json.load(f)
    else:
        config = {
            "source_channels": [],
            "destination_channels": [],
            "is_paused": False,
            "ai_text_enhancement_enabled": True,
            "ai_image_analysis_enabled": True,
            "watermark": {
                "text": "KRBRZ_VIP",
                "position": "sag-alt",
                "color": "beyaz",
                "enabled": True
            },
            "auto_schedule_enabled": False,
            "daily_promo_time": "09:00",
            "template_system_enabled": True,
            "statistics_enabled": True,
            "max_message_length": 60  # Yeni: Mesaj uzunluk sınırı
        }
    
    # Add missing keys for backward compatibility
    config.setdefault("auto_schedule_enabled", False)
    config.setdefault("daily_promo_time", "09:00")
    config.setdefault("template_system_enabled", True)
    config.setdefault("statistics_enabled", True)
    config.setdefault("max_message_length", 60)
    
    return config

bot_config = load_config()

def save_config():
    """Save configuration to file"""
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(bot_config, f, indent=4, ensure_ascii=False)

# --- Enhanced AI Functions ---
@lru_cache(maxsize=100)
async def enhance_text_with_gemini_cached(original_text: str) -> str:
    """Cached version of text enhancement"""
    return await enhance_text_with_gemini(original_text)

async def enhance_text_with_gemini(original_text: str) -> str:
    """Enhanced text with shorter output and better prompts"""
    if not GEMINI_API_KEY or not original_text:
        return original_text
    
    max_length = bot_config.get("max_message_length", 60)
    
    system_prompt = (
        "Sen KRBRZ VIP PUBG bypass/hack satış uzmanısın. "
        f"ÇOK KISA metin yaz (maksimum {max_length} karakter, 1-2 satır). "
        "Haftalık/aylık paketleri vurgula. "
        "Aciliyet yarat (sınırlı stok, özel fiyat). "
        "Sadece bu emojileri kullan: 🔥💎⚡🎯💀👑🚀 "
        "Hashtag: #KRBRZ_VIP #PUBGBypass #Hack "
        "Direkt satış odaklı, uzun açıklama yok. "
        "SADECE kısa satış metni döndür."
    )
    
    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp:generateContent?key={GEMINI_API_KEY}"
    payload = {
        "contents": [{"parts": [{"text": original_text}]}],
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "generationConfig": {
            "maxOutputTokens": 50,
            "temperature": 0.7
        }
    }
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(api_url, json=payload)
            response.raise_for_status()
            result = response.json()
            enhanced_text = result["candidates"][0]["content"]["parts"][0]["text"].strip()
            
            # Ensure length limit
            if len(enhanced_text) > max_length:
                enhanced_text = enhanced_text[:max_length-3] + "..."
            
            return enhanced_text
    except Exception as e:
        logger.error(f"Gemini Text API error: {e}")
        return original_text

async def generate_caption_from_image(image_bytes: bytes) -> str:
    """Enhanced image analysis with shorter captions"""
    if not GEMINI_API_KEY:
        return ""

    max_length = bot_config.get("max_message_length", 60)
    image_b64 = base64.b64encode(image_bytes).decode('utf-8')
    
    prompt = (
        f"KRBRZ VIP PUBG bypass/hack satış kanalı için ÇOK KISA başlık yaz (max {max_length} karakter). "
        "Bu resimde zafer/başarı varsa bypass/hack ürünle bağla. "
        "Satış odaklı yaz - haftalık/aylık paket tanıt. "
        "Emojiler: 🔥💎⚡🎯💀👑 "
        "Hashtag: #KRBRZ_VIP #PUBGBypass #Hack "
        "Acil satış metni döndür."
    )

    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp:generateContent?key={GEMINI_API_KEY}"
    payload = {
        "contents": [{
            "parts": [
                {"text": prompt},
                {"inline_data": {"mime_type": "image/jpeg", "data": image_b64}}
            ]
        }],
        "generationConfig": {
            "maxOutputTokens": 40,
            "temperature": 0.8
        }
    }

    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await client.post(api_url, json=payload)
            response.raise_for_status()
            result = response.json()
            caption = result["candidates"][0]["content"]["parts"][0]["text"].strip()
            
            if len(caption) > max_length:
                caption = caption[:max_length-3] + "..."
            
            return caption
    except Exception as e:
        logger.error(f"Gemini Image API error: {e}")
        return ""

# --- Statistics System ---
class StatisticsManager:
    @staticmethod
    def log_message(channel_id: str, message_type: str, ai_enhanced: bool = False):
        """Log message for statistics"""
        if not bot_config.get("statistics_enabled", True):
            return
            
        conn = sqlite3.connect('bot_data.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO message_stats (channel_id, message_type, ai_enhanced)
            VALUES (?, ?, ?)
        ''', (channel_id, message_type, ai_enhanced))
        conn.commit()
        conn.close()
    
    @staticmethod
    def get_daily_stats() -> Dict:
        """Get today's statistics"""
        conn = sqlite3.connect('bot_data.db')
        cursor = conn.cursor()
        
        today = datetime.now().strftime('%Y-%m-%d')
        cursor.execute('''
            SELECT 
                COUNT(*) as total_messages,
                SUM(CASE WHEN ai_enhanced = 1 THEN 1 ELSE 0 END) as ai_enhanced_messages,
                COUNT(DISTINCT channel_id) as active_channels
            FROM message_stats 
            WHERE DATE(timestamp) = ?
        ''', (today,))
        
        result = cursor.fetchone()
        conn.close()
        
        return {
            "total_messages": result[0] if result else 0,
            "ai_enhanced_messages": result[1] if result else 0,
            "active_channels": result[2] if result else 0,
            "date": today
        }

# --- Template System ---
class TemplateManager:
    @staticmethod
    def add_template(name: str, content: str, category: str = "general"):
        """Add a new message template"""
        conn = sqlite3.connect('bot_data.db')
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO message_templates (name, content, category)
                VALUES (?, ?, ?)
            ''', (name, content, category))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
        finally:
            conn.close()
    
    @staticmethod
    def get_templates(category: str = None) -> List[Dict]:
        """Get templates by category"""
        conn = sqlite3.connect('bot_data.db')
        cursor = conn.cursor()
        
        if category:
            cursor.execute('SELECT * FROM message_templates WHERE category = ?', (category,))
        else:
            cursor.execute('SELECT * FROM message_templates')
        
        templates = []
        for row in cursor.fetchall():
            templates.append({
                "id": row[0],
                "name": row[1],
                "content": row[2],
                "category": row[3],
                "created_at": row[4]
            })
        
        conn.close()
        return templates

# --- Initialize default templates ---
def init_default_templates():
    """Initialize default message templates"""
    default_templates = [
        ("weekly_bypass", "🔥 Haftalık BYPASS! Sadece {price}₺ 👑 #KRBRZ_VIP #PUBGBypass", "promo"),
        ("monthly_hack", "💎 Aylık HACK paketi! {features} ⚡ #KRBRZ_VIP #Hack", "promo"),
        ("victory_post", "💀 Zafer! KRBRZ VIP ile {kills} kill 🎯 #PUBG #Win #KRBRZ_VIP", "victory"),
        ("urgent_sale", "🚀 SON {hours} SAAT! Özel fiyat 🔥 #KRBRZ_VIP #PUBGBypass", "urgent")
    ]
    
    for name, content, category in default_templates:
        TemplateManager.add_template(name, content, category)

init_default_templates()

# --- Enhanced Watermark Function ---
async def apply_watermark(photo_bytes: bytes) -> bytes:
    """Apply watermark with enhanced error handling"""
    wm_config = bot_config.get("watermark", {})
    if not wm_config.get("enabled") or not wm_config.get("text"):
        return photo_bytes
    
    try:
        with Image.open(io.BytesIO(photo_bytes)).convert("RGBA") as base:
            txt = Image.new("RGBA", base.size, (255, 255, 255, 0))
            
            # Enhanced font loading with fallbacks
            font_size = max(15, base.size[1] // 25)
            font = None
            
            for font_path in ['arial.ttf', 'Arial.ttf', '/System/Library/Fonts/Arial.ttf']:
                try:
                    font = ImageFont.truetype(font_path, size=font_size)
                    break
                except (IOError, OSError):
                    continue
            
            if font is None:
                font = ImageFont.load_default()
            
            d = ImageDraw.Draw(txt)
            colors = {
                "beyaz": (255, 255, 255, 180),
                "siyah": (0, 0, 0, 180),
                "kirmizi": (255, 0, 0, 180),
                "mavi": (0, 100, 255, 180),
                "yesil": (0, 255, 100, 180)
            }
            
            fill_color = colors.get(wm_config.get("color", "beyaz").lower(), (255, 255, 255, 180))
            text_bbox = d.textbbox((0, 0), wm_config["text"], font=font)
            text_width = text_bbox[2] - text_bbox[0]
            text_height = text_bbox[3] - text_bbox[1]
            margin = 15
            
            position_map = {
                'sol-ust': (margin, margin),
                'orta-ust': ((base.width - text_width) / 2, margin),
                'sag-ust': (base.width - text_width - margin, margin),
                'sol-orta': (margin, (base.height - text_height) / 2),
                'orta': ((base.width - text_width) / 2, (base.height - text_height) / 2),
                'sag-orta': (base.width - text_width - margin, (base.height - text_height) / 2),
                'sol-alt': (margin, base.height - text_height - margin),
                'orta-alt': ((base.width - text_width) / 2, base.height - text_height - margin),
                'sag-alt': (base.width - text_width - margin, base.height - text_height - margin)
            }
            
            x, y = position_map.get(wm_config.get("position", "sag-alt"), position_map['sag-alt'])
            d.text((x, y), wm_config["text"], font=font, fill=fill_color)
            
            out = Image.alpha_composite(base, txt)
            buffer = io.BytesIO()
            out.convert("RGB").save(buffer, format="JPEG", quality=95)
            buffer.seek(0)
            return buffer.getvalue()
            
    except Exception as e:
        logger.error(f"Watermark error: {e}")
        return photo_bytes

# --- Admin Security Filter ---
def admin_only(func):
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        if update.effective_user.id != ADMIN_USER_ID:
            await update.message.reply_text("❌ Bu komut sadece admin tarafından kullanılabilir.")
            return
        return await func(update, context, *args, **kwargs)
    return wrapped

# --- Enhanced Setup Wizard ---
SETUP_MENU, GET_SOURCE, GET_DEST, GET_WATERMARK_TEXT, GET_TEMPLATE, GET_SCHEDULE = range(6)

@admin_only
async def setup_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Enhanced setup wizard with new features"""
    text_ai_status = "✅ Aktif" if bot_config.get("ai_text_enhancement_enabled") else "❌ Pasif"
    image_ai_status = "✅ Aktif" if bot_config.get("ai_image_analysis_enabled") else "❌ Pasif"
    wm_status = f"✅ Aktif ({bot_config['watermark']['text']})" if bot_config['watermark'].get('enabled') else "❌ Pasif"
    template_status = "✅ Aktif" if bot_config.get("template_system_enabled") else "❌ Pasif"
    stats_status = "✅ Aktif" if bot_config.get("statistics_enabled") else "❌ Pasif"
    auto_schedule_status = "✅ Aktif" if bot_config.get("auto_schedule_enabled") else "❌ Pasif"
    
    keyboard = [
        [
            InlineKeyboardButton("📡 Kaynak Kanallar", callback_data='set_source'),
            InlineKeyboardButton("📤 Hedef Kanallar", callback_data='set_dest')
        ],
        [InlineKeyboardButton(f"🤖 Yazı Güzelleştirme: {text_ai_status}", callback_data='toggle_text_ai')],
        [InlineKeyboardButton(f"🖼️ Oto. Başlık Üretme: {image_ai_status}", callback_data='toggle_image_ai')],
        [InlineKeyboardButton(f"💧 Filigran: {wm_status}", callback_data='set_watermark')],
        [InlineKeyboardButton(f"📋 Template Sistemi: {template_status}", callback_data='toggle_template')],
        [InlineKeyboardButton(f"📊 İstatistikler: {stats_status}", callback_data='toggle_stats')],
        [InlineKeyboardButton(f"⏰ Otomatik Program: {auto_schedule_status}", callback_data='toggle_schedule')],
        [
            InlineKeyboardButton("📊 İstatistikleri Gör", callback_data='view_stats'),
            InlineKeyboardButton("📋 Template Yönet", callback_data='manage_templates')
        ],
        [InlineKeyboardButton("✅ Sihirbazdan Çık", callback_data='exit_setup')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    stats = StatisticsManager.get_daily_stats()
    message_content = f"""🚀 **KRBRZ VIP Bot Yönetim Paneli**

📈 **Bugünkü İstatistikler:**
• Toplam Mesaj: {stats['total_messages']}
• AI İyileştirme: {stats['ai_enhanced_messages']}
• Aktif Kanal: {stats['active_channels']}

⚙️ **Bot Ayarlarını Yönetin:**"""
    
    if update.message:
        await update.message.reply_text(message_content, reply_markup=reply_markup, parse_mode='Markdown')
    elif update.callback_query:
        try:
            await update.callback_query.edit_message_text(message_content, reply_markup=reply_markup, parse_mode='Markdown')
        except Exception:
            pass
            
    return SETUP_MENU

async def setup_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Enhanced menu handler with new features"""
    query = update.callback_query
    await query.answer()
    data = query.data
    
    if data == 'set_source':
        await query.edit_message_text("📡 Dinlenecek kaynak kanalın adını yazıp gönderin (@ile başlayın).")
        return GET_SOURCE
    elif data == 'set_dest':
        await query.edit_message_text("📤 Gönderilerin yapılacağı hedef kanalın adını yazıp gönderin.")
        return GET_DEST
    elif data == 'toggle_text_ai':
        bot_config["ai_text_enhancement_enabled"] = not bot_config.get("ai_text_enhancement_enabled", False)
        save_config()
        return await setup_command(query, context)
    elif data == 'toggle_image_ai':
        bot_config["ai_image_analysis_enabled"] = not bot_config.get("ai_image_analysis_enabled", False)
        save_config()
        return await setup_command(query, context)
    elif data == 'toggle_template':
        bot_config["template_system_enabled"] = not bot_config.get("template_system_enabled", False)
        save_config()
        return await setup_command(query, context)
    elif data == 'toggle_stats':
        bot_config["statistics_enabled"] = not bot_config.get("statistics_enabled", False)
        save_config()
        return await setup_command(query, context)
    elif data == 'toggle_schedule':
        bot_config["auto_schedule_enabled"] = not bot_config.get("auto_schedule_enabled", False)
        save_config()
        return await setup_command(query, context)
    elif data == 'set_watermark':
        await query.edit_message_text("💧 Yeni filigran metnini girin. Kapatmak için 'kapat' yazın.")
        return GET_WATERMARK_TEXT
    elif data == 'view_stats':
        stats = StatisticsManager.get_daily_stats()
        stats_text = f"""📈 **Detaylı İstatistikler**

📅 **Tarih:** {stats['date']}
📨 **Toplam Mesaj:** {stats['total_messages']}
🤖 **AI İyileştirme:** {stats['ai_enhanced_messages']}
📡 **Aktif Kanallar:** {stats['active_channels']}

📈 **Başarım Oranı:** {(stats['ai_enhanced_messages']/max(1,stats['total_messages'])*100):.1f}%"""
        
        keyboard = [[InlineKeyboardButton("⬅️ Geri Dön", callback_data='back_to_menu')]]
        await query.edit_message_text(stats_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        return SETUP_MENU
    elif data == 'manage_templates':
        templates = TemplateManager.get_templates()
        template_text = "📋 **Mevcut Template'ler:**\n\n"
        
        for template in templates[:10]:  # Show first 10
            template_text += f"• **{template['name']}:** {template['content'][:50]}...\n"
        
        template_text += "\n📝 Yeni template eklemek için: `/template <ad> <içerik>`"
        
        keyboard = [[InlineKeyboardButton("⬅️ Geri Dön", callback_data='back_to_menu')]]
        await query.edit_message_text(template_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        return SETUP_MENU
    elif data == 'back_to_menu':
        return await setup_command(query, context)
    elif data == 'exit_setup':
        await query.edit_message_text("✅ Kurulum kapatıldı. Bot çalışıyor!")
        return ConversationHandler.END
    
    return SETUP_MENU

async def channel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, channel_type: str) -> int:
    """Enhanced channel handler with validation"""
    channel = update.message.text.strip()
    config_key = f"{channel_type}_channels"
    
    # Validate channel format
    if not (channel.startswith('@') or channel.startswith('-') or channel.lstrip('-').isdigit()):
        await update.message.reply_text("⚠️ Geçersiz kanal formatı! '@kanaladı' veya kanal ID'si kullanın.")
        return await setup_command(update, context)
    
    if channel in bot_config[config_key]:
        bot_config[config_key].remove(channel)
        await update.message.reply_text(f"🗑️ {channel_type.capitalize()} silindi: {channel}")
    else:
        bot_config[config_key].append(channel)
        await update.message.reply_text(f"✅ {channel_type.capitalize()} eklendi: {channel}")
    
    save_config()
    await setup_command(update, context)
    return ConversationHandler.END

async def get_source_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await channel_handler(update, context, "source")

async def get_dest_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await channel_handler(update, context, "destination")

async def get_watermark_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if text.lower() == 'kapat':
        bot_config['watermark']['enabled'] = False
        await update.message.reply_text("❌ Filigran kapatıldı.")
    else:
        bot_config['watermark']['text'] = text
        bot_config['watermark']['enabled'] = True
        await update.message.reply_text(f"✅ Filigran metni ayarlandı: '{text}'")
    
    save_config()
    await setup_command(update, context)
    return ConversationHandler.END

async def cancel_setup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("❌ İşlem iptal edildi.")
    return ConversationHandler.END

# --- Enhanced Admin Commands ---
@admin_only
async def template_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add new template via command"""
    if len(context.args) < 2:
        await update.message.reply_text("📝 Kullanım: `/template <ad> <içerik>`", parse_mode='Markdown')
        return
    
    name = context.args[0]
    content = ' '.join(context.args[1:])
    
    if TemplateManager.add_template(name, content):
        await update.message.reply_text(f"✅ Template '{name}' başarıyla eklendi!")
    else:
        await update.message.reply_text(f"⚠️ Template '{name}' zaten mevcut!")

@admin_only
async def pause_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Pause/unpause bot"""
    bot_config["is_paused"] = not bot_config.get("is_paused", False)
    save_config()
    
    status = "duraklatıldı" if bot_config["is_paused"] else "devam ediyor"
    emoji = "⏸️" if bot_config["is_paused"] else "▶️"
    await update.message.reply_text(f"{emoji} Bot {status}!")

@admin_only
async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Broadcast message to all destination channels"""
    if not context.args:
        await update.message.reply_text("📢 Kullanım: `/broadcast <mesaj>`")
        return
    
    message = ' '.join(context.args)
    
    # Apply AI enhancement if enabled
    if bot_config.get("ai_text_enhancement_enabled"):
        message = await enhance_text_with_gemini(message)
    
    success_count = 0
    for channel in bot_config.get("destination_channels", []):
        try:
            await context.bot.send_message(chat_id=channel, text=message)
            success_count += 1
        except Exception as e:
            logger.error(f"Broadcast error to {channel}: {e}")
    
    await update.message.reply_text(f"📢 Mesaj {success_count}/{len(bot_config.get('destination_channels', []))} kanala gönderildi!")

# --- Enhanced Main Forwarder ---
async def forwarder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Enhanced message forwarder with statistics and error handling"""
    if bot_config.get("is_paused", False):
        return
    
    message = update.channel_post
    if not message:
        return

    chat_identifier = f"@{message.chat.username}" if message.chat.username else str(message.chat.id)
    if chat_identifier not in bot_config["source_channels"]:
        return

    try:
        final_caption = ""
        photo_bytes = None
        message_type = "text"
        ai_enhanced = False

        # Download photo if exists
        if message.photo:
            message_type = "photo"
            file = await context.bot.get_file(message.photo[-1].file_id)
            async with httpx.AsyncClient() as client:
                photo_bytes = (await client.get(file.file_path)).content

        # Determine caption
        if message.caption:
            # Enhance existing caption if enabled
            if bot_config.get("ai_text_enhancement_enabled"):
                await context.bot.send_chat_action(chat_id=message.chat_id, action="typing")
                final_caption = await enhance_text_with_gemini(message.caption)
                ai_enhanced = True
            else:
                final_caption = message.caption
        elif message.photo and not message.caption:
            # Generate caption from image if enabled
            if bot_config.get("ai_image_analysis_enabled"):
                await context.bot.send_chat_action(chat_id=message.chat_id, action="typing")
                final_caption = await generate_caption_from_image(photo_bytes)
                ai_enhanced = True
        elif message.text:
            # Handle text-only messages
            message_type = "text"
            if bot_config.get("ai_text_enhancement_enabled"):
                await context.bot.send_chat_action(chat_id=message.chat_id, action="typing")
                final_caption = await enhance_text_with_gemini(message.text)
                ai_enhanced = True
            else:
                final_caption = message.text

        # Forward to destination channels
        success_count = 0
        for dest in bot_config["destination_channels"]:
            try:
                if photo_bytes:  # Photo message
                    watermarked_photo = await apply_watermark(photo_bytes)
                    await context.bot.send_photo(
                        chat_id=dest, 
                        photo=watermarked_photo, 
                        caption=final_caption
                    )
                elif message.video:
                    await message.copy(chat_id=dest, caption=final_caption if message.caption else None)
                elif message.document:
                    await message.copy(chat_id=dest, caption=final_caption if message.caption else None)
                else:  # Text message
                    await context.bot.send_message(chat_id=dest, text=final_caption)
                
                success_count += 1
                logger.info(f"Message forwarded to {dest} successfully")
                
            except Exception as e:
                logger.error(f"Forward error to {dest}: {e}")

        # Log statistics
        StatisticsManager.log_message(
            channel_id=chat_identifier,
            message_type=message_type,
            ai_enhanced=ai_enhanced
        )
        
        logger.info(f"Message processed: {success_count}/{len(bot_config['destination_channels'])} channels")
        
    except Exception as e:
        logger.error(f"Forwarder error: {e}")

# --- Scheduled Tasks ---
def run_scheduled_tasks():
    """Run scheduled promotional messages"""
    def job():
        if not bot_config.get("auto_schedule_enabled"):
            return
            
        # This would need to be integrated with the bot context
        # For now, it's a placeholder for scheduled functionality
        logger.info("Scheduled task executed")
    
    schedule.every().day.at(bot_config.get("daily_promo_time", "09:00")).do(job)
    
    while True:
        schedule.run_pending()
        time.sleep(60)

# --- Enhanced Flask Web Server ---
flask_app = Flask(__name__)

# Admin Panel HTML Template
ADMIN_PANEL_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>KRBRZ VIP Bot Admin Panel</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #1a1a2e; color: #eee; }
        .container { max-width: 1200px; margin: 0 auto; padding: 20px; }
        .header { text-align: center; margin-bottom: 30px; }
        .header h1 { color: #00d4aa; font-size: 2.5em; margin-bottom: 10px; }
        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 30px; }
        .stat-card { background: #16213e; padding: 20px; border-radius: 10px; border: 1px solid #0f3460; }
        .stat-card h3 { color: #00d4aa; margin-bottom: 10px; }
        .stat-value { font-size: 2em; font-weight: bold; color: #fff; }
        .config-section { background: #16213e; padding: 20px; border-radius: 10px; border: 1px solid #0f3460; }
        .config-item { margin: 10px 0; padding: 10px; background: #0f3460; border-radius: 5px; }
        .status-badge { padding: 3px 8px; border-radius: 12px; font-size: 0.8em; font-weight: bold; }
        .active { background: #28a745; }
        .inactive { background: #dc3545; }
        .footer { text-align: center; margin-top: 30px; color: #666; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 KRBRZ VIP Bot</h1>
            <p>Advanced AI-Powered Telegram Bot | Railway Deployment</p>
        </div>
        
        <div class="stats-grid">
            <div class="stat-card">
                <h3>📈 Today's Messages</h3>
                <div class="stat-value">{{ stats.total_messages }}</div>
            </div>
            <div class="stat-card">
                <h3>🤖 AI Enhanced</h3>
                <div class="stat-value">{{ stats.ai_enhanced_messages }}</div>
            </div>
            <div class="stat-card">
                <h3>📡 Active Channels</h3>
                <div class="stat-value">{{ stats.active_channels }}</div>
            </div>
            <div class="stat-card">
                <h3>⚡ Success Rate</h3>
                <div class="stat-value">{{ success_rate }}%</div>
            </div>
        </div>
        
        <div class="config-section">
            <h2>🔧 Bot Configuration</h2>
            <div class="config-item">
                <strong>AI Text Enhancement:</strong> 
                <span class="status-badge {{ 'active' if config.ai_text_enhancement_enabled else 'inactive' }}">
                    {{ 'Active' if config.ai_text_enhancement_enabled else 'Inactive' }}
                </span>
            </div>
            <div class="config-item">
                <strong>AI Image Analysis:</strong> 
                <span class="status-badge {{ 'active' if config.ai_image_analysis_enabled else 'inactive' }}">
                    {{ 'Active' if config.ai_image_analysis_enabled else 'Inactive' }}
                </span>
            </div>
            <div class="config-item">
                <strong>Watermark:</strong> 
                <span class="status-badge {{ 'active' if config.watermark.enabled else 'inactive' }}">
                    {{ config.watermark.text if config.watermark.enabled else 'Disabled' }}
                </span>
            </div>
            <div class="config-item">
                <strong>Source Channels:</strong> {{ config.source_channels|length }}
            </div>
            <div class="config-item">
                <strong>Destination Channels:</strong> {{ config.destination_channels|length }}
            </div>
        </div>
        
        <div class="footer">
            <p>© 2024 KRBRZ VIP Bot - Powered by Gemini AI & Railway</p>
            <p>Use /ayarla command in Telegram for configuration</p>
        </div>
    </div>
</body>
</html>
"""

@flask_app.route('/')
def home():
    """Enhanced home page with admin panel"""
    stats = StatisticsManager.get_daily_stats()
    success_rate = (stats['ai_enhanced_messages'] / max(1, stats['total_messages']) * 100)
    
    return render_template_string(ADMIN_PANEL_HTML, 
                                stats=stats, 
                                config=type('obj', (object,), bot_config),
                                success_rate=f"{success_rate:.1f}")

@flask_app.route('/health')
def health():
    """Health check endpoint for Railway"""
    stats = StatisticsManager.get_daily_stats()
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "bot_config": {
            "ai_text_enabled": bot_config.get("ai_text_enhancement_enabled", False),
            "ai_image_enabled": bot_config.get("ai_image_analysis_enabled", False),
            "watermark_enabled": bot_config.get("watermark", {}).get("enabled", False),
            "is_paused": bot_config.get("is_paused", False)
        },
        "daily_stats": stats,
        "channels": {
            "source_count": len(bot_config.get("source_channels", [])),
            "destination_count": len(bot_config.get("destination_channels", []))
        }
    })

@flask_app.route('/api/stats')
def api_stats():
    """API endpoint for statistics"""
    return jsonify(StatisticsManager.get_daily_stats())

@flask_app.route('/api/config')
def api_config():
    """API endpoint for configuration (safe version)"""
    safe_config = {
        "ai_text_enhancement_enabled": bot_config.get("ai_text_enhancement_enabled", False),
        "ai_image_analysis_enabled": bot_config.get("ai_image_analysis_enabled", False),
        "watermark_enabled": bot_config.get("watermark", {}).get("enabled", False),
        "template_system_enabled": bot_config.get("template_system_enabled", False),
        "statistics_enabled": bot_config.get("statistics_enabled", False),
        "is_paused": bot_config.get("is_paused", False),
        "source_channels_count": len(bot_config.get("source_channels", [])),
        "destination_channels_count": len(bot_config.get("destination_channels", []))
    }
    return jsonify(safe_config)

def run_flask():
    """Run Flask server for Railway"""
    flask_app.run(host='0.0.0.0', port=PORT, debug=False)

# --- Main Bot Function ---
def main():
    """Enhanced main function with comprehensive bot setup"""
    logger.info("🚀 KRBRZ VIP Bot starting - Railway Enhanced Version")
    
    # Initialize bot application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Setup conversation handler for enhanced wizard
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("ayarla", setup_command)],
        states={
            SETUP_MENU: [CallbackQueryHandler(setup_menu_handler)],
            GET_SOURCE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_source_handler)],
            GET_DEST: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_dest_handler)],
            GET_WATERMARK_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_watermark_text_handler)],
        },
        fallbacks=[CommandHandler("iptal", cancel_setup)],
        per_message=False
    )
    
    # Add handlers
    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("start", lambda u, c: u.message.reply_text(
        "🚀 **KRBRZ VIP Bot Aktif!**\n\n"
        "🔧 Ayarlar için: `/ayarla`\n"
        "⏸️ Duraklat için: `/pause`\n"
        "📢 Broadcast için: `/broadcast <mesaj>`\n"
        "📝 Template için: `/template <ad> <içerik>`\n\n"
        "💻 Admin Panel: Railway URL\n"
        "📊 Bot durumu: Aktif ve hazır!",
        parse_mode='Markdown'
    )))
    application.add_handler(CommandHandler("template", template_command))
    application.add_handler(CommandHandler("pause", pause_command))
    application.add_handler(CommandHandler("broadcast", broadcast_command))
    application.add_handler(MessageHandler(filters.UpdateType.CHANNEL_POST, forwarder))
    
    logger.info("✅ Bot handlers configured successfully")
    logger.info(f"📊 Statistics: {StatisticsManager.get_daily_stats()}")
    logger.info(f"🔧 Config loaded: {len(bot_config.get('source_channels', []))} source, {len(bot_config.get('destination_channels', []))} destination channels")
    
    # Start scheduled tasks in background
    if bot_config.get("auto_schedule_enabled"):
        Thread(target=run_scheduled_tasks, daemon=True).start()
        logger.info("⏰ Scheduled tasks enabled")
    
    logger.info("🌐 Starting Telegram bot polling...")
    application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    # Flask app assignment for Railway compatibility
    app = flask_app
    
    # Start Flask server in background thread
    Thread(target=run_flask, daemon=True).start()
    logger.info(f"🌐 Flask server started on port {PORT}")
    
    # Start main bot
    main()