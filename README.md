# KRBRZ VIP Bot - Railway Deployment

## 🚀 Railway'e Deploy Etme Rehberi

### 1. Hazırlık
1. GitHub hesabı oluşturun (yoksa)
2. Railway hesabı oluşturun: [railway.app](https://railway.app)
3. Bu dosyaları GitHub'a yükleyin

### 2. Railway Setup
1. Railway'e giriş yapın
2. "New Project" → "Deploy from GitHub repo"
3. Bu repository'yi seçin
4. Environment variables ekleyin:

```
BOT_TOKEN=telegram_bot_token_buraya
ADMIN_USER_ID=telegram_user_id_buraya  
GEMINI_API_KEY=gemini_api_key_buraya
```

### 3. Bot Token Alma
1. [@BotFather](https://t.me/BotFather)'a gidin
2. `/newbot` komutunu kullanın
3. Bot adını ve username'ini verin
4. Token'ı kopyalayın

### 4. Gemini API Key Alma
1. [Google AI Studio](https://makersuite.google.com/app/apikey)'ya gidin
2. "Create API Key" butonuna tıklayın
3. API key'i kopyalayın

### 5. User ID Bulma
1. [@userinfobot](https://t.me/userinfobot)'a gidin
2. Size verilen ID'yi kopyalayın

### 6. Deploy Kontrolü
- Railway otomatik deploy başlatacak
- Logs'da hata olup olmadığını kontrol edin
- Health check: `https://your-app.railway.app/health`

## 📱 Bot Komutları

### Admin Komutları:
- `/start` - Bot bilgilerini göster
- `/ayarla` - Gelişmiş setup sihirbazı
- `/pause` - Bot'u duraklat/devam ettir
- `/broadcast <mesaj>` - Tüm kanallara mesaj gönder
- `/template <ad> <içerik>` - Yeni template ekle

### 🆕 Yeni Özellikler:

#### 📊 İstatistik Sistemi
- Günlük mesaj sayısı
- AI geliştirme oranları  
- Kanal aktivite takibi
- Web admin paneli

#### 🤖 Gelişmiş AI
- Daha kısa mesajlar (60 karakter limit)
- Önbellekleme sistemi
- Hata toleransı
- Çoklu prompt desteği

#### 📝 Template Sistemi  
- Hazır mesaj şablonları
- Kategori bazlı organizasyon
- Dinamik değişken desteği
- Yönetim komutları

#### ⏰ Zamanlama Sistemi
- Otomatik günlük promosyonlar
- Zamanlanmış mesajlar
- Tekrarlanan görevler

#### 🎨 Gelişmiş Filigran
- 5 farklı renk seçeneği
- Daha iyi font desteği
- Yüksek kalite output
- Hata handling

#### 🔧 Admin Paneli
- Web tabanlı yönetim
- Gerçek zamanlı istatistikler
- Görsel dashboard
- API endpoints

## 🌐 Web Admin Panel

Railway deploy edildikten sonra:
- Ana panel: `https://your-app.railway.app/`
- Health check: `https://your-app.railway.app/health`
- İstatistikler: `https://your-app.railway.app/api/stats`
- Ayarlar: `https://your-app.railway.app/api/config`

## 🚨 Troubleshooting

### Deploy Hataları:
1. Environment variables kontrolü
2. Requirements.txt kontrolü  
3. Railway logs kontrolü
4. Python version uyumluluğu

### Bot Çalışmıyor:
1. Token doğruluğu
2. Bot admin yetkisi
3. Kanal ayarları
4. API key geçerliliği

## 📈 Performans Optimizasyonları

- SQLite database ile hızlı statistics
- LRU cache ile AI call azaltma
- Async/await ile concurrent processing
- Error recovery ve retry logic
- Memory efficient image processing

## 🔒 Güvenlik

- Environment variables ile güvenli config
- Admin-only komutlar
- Input validation
- Error handling
- Rate limiting hazır

## 📞 Destek

Railway deployment sorunları için:
1. Railway docs kontrol edin
2. GitHub issues açın  
3. Railway community'ye sorun

Bot yapılandırma için:
- Telegram'da `/ayarla` komutunu kullanın
- Web admin panelini kontrol edin