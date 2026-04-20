# DermAI — AI-Powered Skin Health Analysis

A full-stack dermatology web application that analyzes skin health using:
- **Facial images** via OpenCV (Haar Cascade, LAB/HSV color analysis)
- **Real-time AQI** from OpenWeatherMap (PM2.5, PM10, O₃, NO₂)
- **Sleep patterns & stress** (cortisol + barrier function modeling)
- **Hormonal phase** (cycle-aware personalization)

## 🚀 Quick Start

### 1. Install Python dependencies
```bash
pip install -r requirements.txt
```

### 2. Set your OpenWeather API key (optional but recommended)
Get a free key at https://openweathermap.org/api/air-pollution

```bash
# Linux / Mac
export OPENWEATHER_API_KEY=your_key_here

# Windows
set OPENWEATHER_API_KEY=your_key_here
```

> Without a key, the app uses estimated AQI data for major Indian cities.

### 3. Run the server
```bash
python app.py
```

### 4. Open in browser
```
http://localhost:5000
```

## 📁 Project Structure
```
dermai/
├── app.py                  # Flask backend
├── requirements.txt
├── templates/
│   └── index.html          # Main HTML template
└── static/
    ├── css/style.css       # Dark luxury UI styles
    ├── js/main.js          # Frontend interactivity
    └── uploads/            # Temporary image storage (auto-cleaned)
```

## 🔬 How It Works

1. **Image Upload** → OpenCV reads it using Haar Cascade for face detection
2. **Pixel Analysis** → RGB, HSV, LAB channels analyzed for:
   - Redness (R channel dominance)
   - Oiliness (HSV saturation)
   - Texture roughness (Laplacian variance)
   - Dark spots (L channel below mean)
   - Moisture estimate (composite score)
3. **AQI Fetch** → OpenWeatherMap Geocoding + Air Pollution APIs
4. **Scoring** → Weighted formula produces 0–100 skin health score
5. **Recommendations** → Rule-based engine outputs SPF, active ingredients, lifestyle tips

## 🌐 Deployment (Production)

```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

For cloud deployment (Render, Railway, Heroku), set the `OPENWEATHER_API_KEY` environment variable in your platform's dashboard.

## 🛡️ Disclaimer
DermAI is for informational and educational purposes only. It does not substitute professional dermatological advice.
