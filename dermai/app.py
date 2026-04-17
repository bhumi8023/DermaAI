from flask import Flask, request, jsonify, render_template, send_from_directory
import cv2
import numpy as np
import requests
import os
import base64
from werkzeug.utils import secure_filename
import json
import math

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max

OPENWEATHER_API_KEY = os.environ.get('OPENWEATHER_API_KEY', 'demo_key')

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ─── AQI Fetcher ────────────────────────────────────────────────────────────
def get_aqi_data(city):
    try:
        geo_url = f"http://api.openweathermap.org/geo/1.0/direct?q={city}&limit=1&appid={OPENWEATHER_API_KEY}"
        geo_resp = requests.get(geo_url, timeout=5).json()
        if not geo_resp:
            return get_mock_aqi(city)
        lat, lon = geo_resp[0]['lat'], geo_resp[0]['lon']

        aqi_url = f"http://api.openweathermap.org/data/2.5/air_pollution?lat={lat}&lon={lon}&appid={OPENWEATHER_API_KEY}"
        aqi_data = requests.get(aqi_url, timeout=5).json()

        components = aqi_data['list'][0]['components']
        aqi_index = aqi_data['list'][0]['main']['aqi']

        return {
            'aqi': aqi_index,
            'pm2_5': components.get('pm2_5', 0),
            'pm10': components.get('pm10', 0),
            'o3': components.get('o3', 0),
            'no2': components.get('no2', 0),
            'city': city,
            'source': 'live'
        }
    except Exception as e:
        return get_mock_aqi(city)

def get_mock_aqi(city):
    city_lower = city.lower()
    # Approximate AQI profiles for major Indian cities
    profiles = {
        'delhi': {'aqi': 5, 'pm2_5': 85.0, 'pm10': 120.0, 'o3': 30.0, 'no2': 45.0},
        'mumbai': {'aqi': 3, 'pm2_5': 45.0, 'pm10': 65.0, 'o3': 25.0, 'no2': 30.0},
        'bangalore': {'aqi': 2, 'pm2_5': 28.0, 'pm10': 42.0, 'o3': 20.0, 'no2': 20.0},
        'indore': {'aqi': 3, 'pm2_5': 50.0, 'pm10': 75.0, 'o3': 28.0, 'no2': 35.0},
        'chennai': {'aqi': 2, 'pm2_5': 32.0, 'pm10': 48.0, 'o3': 22.0, 'no2': 22.0},
        'kolkata': {'aqi': 4, 'pm2_5': 68.0, 'pm10': 95.0, 'o3': 28.0, 'no2': 40.0},
    }
    for key in profiles:
        if key in city_lower:
            data = profiles[key].copy()
            data['city'] = city
            data['source'] = 'estimated'
            return data

    return {'aqi': 3, 'pm2_5': 45.0, 'pm10': 65.0, 'o3': 25.0, 'no2': 30.0, 'city': city, 'source': 'default'}


# ─── OpenCV Skin Analyzer ───────────────────────────────────────────────────
def analyze_skin_image(image_path):
    try:
        img = cv2.imread(image_path)
        if img is None:
            return get_default_skin_analysis()

        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        img_hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        img_lab = cv2.cvtColor(img, cv2.COLOR_BGR2Lab)

        # Detect face region using Haar Cascade
        face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.1, 4)

        if len(faces) > 0:
            x, y, w, h = faces[0]
            roi_rgb = img_rgb[y:y+h, x:x+w]
            roi_hsv = img_hsv[y:y+h, x:x+w]
            roi_lab = img_lab[y:y+h, x:x+w]
        else:
            # Use center 60% if no face detected
            h_img, w_img = img.shape[:2]
            y1, y2 = int(h_img*0.2), int(h_img*0.8)
            x1, x2 = int(w_img*0.2), int(w_img*0.8)
            roi_rgb = img_rgb[y1:y2, x1:x2]
            roi_hsv = img_hsv[y1:y2, x1:x2]
            roi_lab = img_lab[y1:y2, x1:x2]

        # ── Tone / Brightness
        avg_brightness = float(np.mean(roi_rgb))
        l_channel = roi_lab[:, :, 0]
        avg_L = float(np.mean(l_channel))

        # ── Redness detection
        r_channel = roi_rgb[:, :, 0].astype(float)
        g_channel = roi_rgb[:, :, 1].astype(float)
        b_channel = roi_rgb[:, :, 2].astype(float)
        redness_map = r_channel - (g_channel + b_channel) / 2
        redness_score = float(np.clip(np.mean(redness_map) / 50.0, 0, 1))

        # ── Uneven tone (std dev of L channel)
        tone_unevenness = float(np.std(l_channel) / 30.0)
        tone_unevenness = min(tone_unevenness, 1.0)

        # ── Oiliness via saturation
        s_channel = roi_hsv[:, :, 1]
        avg_saturation = float(np.mean(s_channel))
        oiliness_score = float(np.clip(avg_saturation / 150.0, 0, 1))

        # ── Texture / roughness via Laplacian variance
        gray_roi = cv2.cvtColor(roi_rgb, cv2.COLOR_RGB2GRAY)
        laplacian_var = float(cv2.Laplacian(gray_roi, cv2.CV_64F).var())
        texture_score = float(np.clip(laplacian_var / 500.0, 0, 1))

        # ── Dark spots detection
        dark_mask = l_channel < (avg_L * 0.75)
        dark_spot_ratio = float(np.sum(dark_mask) / dark_mask.size)
        dark_spots_score = min(dark_spot_ratio * 5.0, 1.0)

        # ── Moisture estimate (inverse of texture + low redness)
        moisture_score = float(1.0 - (texture_score * 0.5 + redness_score * 0.3 + oiliness_score * 0.2))
        moisture_score = max(0, min(1, moisture_score))

        # ── Overall skin health score
        health_score = 100 - (
            redness_score * 20 +
            tone_unevenness * 15 +
            oiliness_score * 15 +
            texture_score * 20 +
            dark_spots_score * 15 +
            (1 - moisture_score) * 15
        )
        health_score = max(0, min(100, health_score))

        face_detected = len(faces) > 0

        return {
            'health_score': round(health_score, 1),
            'redness': round(redness_score * 100, 1),
            'oiliness': round(oiliness_score * 100, 1),
            'texture_roughness': round(texture_score * 100, 1),
            'tone_unevenness': round(tone_unevenness * 100, 1),
            'dark_spots': round(dark_spots_score * 100, 1),
            'moisture': round(moisture_score * 100, 1),
            'brightness': round(avg_brightness, 1),
            'face_detected': face_detected,
            'analysis_source': 'opencv'
        }

    except Exception as e:
        return get_default_skin_analysis()

def get_default_skin_analysis():
    return {
        'health_score': 70.0,
        'redness': 25.0,
        'oiliness': 35.0,
        'texture_roughness': 30.0,
        'tone_unevenness': 28.0,
        'dark_spots': 20.0,
        'moisture': 55.0,
        'brightness': 128.0,
        'face_detected': False,
        'analysis_source': 'default'
    }


# ─── Recommendation Engine ──────────────────────────────────────────────────
def generate_recommendations(skin_analysis, aqi_data, sleep_hours, skin_type, hormonal_phase, stress_level):
    recs = []
    warnings = []
    ingredients = []
    lifestyle = []

    pm25 = aqi_data.get('pm2_5', 30)
    aqi_index = aqi_data.get('aqi', 2)
    redness = skin_analysis.get('redness', 25)
    oiliness = skin_analysis.get('oiliness', 35)
    moisture = skin_analysis.get('moisture', 55)
    texture = skin_analysis.get('texture_roughness', 30)
    dark_spots = skin_analysis.get('dark_spots', 20)
    health_score = skin_analysis.get('health_score', 70)

    sleep_float = float(sleep_hours)
    stress_float = float(stress_level)

    # ── SPF Recommendation
    if aqi_index >= 4 or pm25 > 55:
        spf = "SPF 50+ PA++++ (pollution + UV)"
        recs.append("🛡️ High pollution detected — use mineral SPF 50+ with antioxidants daily")
    elif aqi_index == 3 or pm25 > 25:
        spf = "SPF 30–50 PA++"
        recs.append("☀️ Moderate AQI — SPF 30+ recommended, reapply every 2 hours outdoors")
    else:
        spf = "SPF 30 PA+"
        recs.append("✅ Air quality is decent — SPF 30 is sufficient for daily use")

    # ── Pollution Defense
    if pm25 > 35:
        ingredients.extend(["Niacinamide 10%", "Vitamin C 15%", "Centella Asiatica"])
        recs.append("🌫️ PM2.5 levels are elevated — add an antioxidant serum (Vitamin C) every morning")

    # ── Hydration
    if moisture < 40:
        ingredients.extend(["Hyaluronic Acid", "Ceramides", "Glycerin"])
        recs.append("💧 Your skin appears dehydrated — use a hyaluronic acid serum + ceramide moisturizer")
    elif moisture < 55:
        ingredients.append("Hyaluronic Acid")
        recs.append("💧 Moderate hydration — maintain with a lightweight moisturizer twice daily")

    # ── Oiliness
    if skin_type == 'oily' or oiliness > 60:
        ingredients.extend(["Niacinamide 5%", "Salicylic Acid 2%", "Zinc"])
        recs.append("🧴 Oily zones detected — use niacinamide to regulate sebum; avoid heavy occlusives")
    elif skin_type == 'dry':
        ingredients.extend(["Squalane", "Shea Butter", "Ceramides"])
        recs.append("🫧 Dry skin detected — incorporate a rich ceramide cream at night")

    # ── Redness / Sensitivity
    if redness > 50:
        ingredients.extend(["Centella Asiatica", "Azelaic Acid 10%", "Allantoin"])
        warnings.append("⚠️ Significant redness detected — avoid alcohol-based toners and fragrance")
        recs.append("🌿 Use calming actives: Centella Asiatica or Azelaic Acid to reduce inflammation")

    # ── Texture & Exfoliation
    if texture > 55:
        ingredients.extend(["AHA (Glycolic Acid 8%)", "BHA (Salicylic 2%)", "Polyhydroxy Acid"])
        recs.append("✨ Rough texture noted — introduce a gentle chemical exfoliant 2–3x/week (AHA/BHA)")

    # ── Dark Spots
    if dark_spots > 40:
        ingredients.extend(["Alpha Arbutin 2%", "Kojic Acid", "Vitamin C"])
        recs.append("🔆 Uneven pigmentation present — use Alpha Arbutin or Vitamin C for brightening")

    # ── Sleep Impact
    if sleep_float < 6:
        warnings.append("⚠️ Severe sleep deprivation (<6h) — cortisol spike damages collagen production")
        lifestyle.append("😴 Prioritize 7–9 hours of sleep — it's when your skin repairs itself")
        ingredients.append("Retinol 0.3% (night repair)")
    elif sleep_float < 7:
        lifestyle.append("😴 Aim for 7+ hours of sleep; your skin heals in deep sleep stages")
        recs.append("🌙 Use a peptide night cream to support overnight skin recovery")

    # ── Stress Impact
    if stress_float >= 7:
        warnings.append("⚠️ High stress elevates cortisol — triggers breakouts and barrier damage")
        lifestyle.append("🧘 Practice stress reduction: meditation, yoga, or 10-min breathing exercises daily")
        ingredients.extend(["Adaptogenic Ashwagandha (internal)", "Niacinamide (topical)"])
    elif stress_float >= 5:
        lifestyle.append("🧘 Moderate stress detected — consider mindfulness to reduce inflammatory flares")

    # ── Hormonal Phase
    if hormonal_phase == 'menstrual':
        recs.append("🌸 Menstrual phase: skin may be more sensitive — stick to gentle, soothing products")
        ingredients.append("Centella Asiatica (anti-inflammatory)")
    elif hormonal_phase == 'ovulation':
        recs.append("🌸 Ovulation phase: skin is at its best — good time to do light exfoliation")
    elif hormonal_phase == 'luteal':
        recs.append("🌸 Luteal phase: pre-menstrual breakouts likely — use salicylic acid spot treatment")
        ingredients.append("Salicylic Acid 2% (spot treatment)")
    elif hormonal_phase == 'postpartum':
        recs.append("🌸 Postpartum phase: hormonal fluctuation high — use gentle, fragrance-free products")
        warnings.append("⚠️ Postpartum melasma is common — double sunscreen and use Azelaic Acid")

    # Deduplicate ingredients
    ingredients = list(dict.fromkeys(ingredients))

    return {
        'spf': spf,
        'recommendations': recs,
        'active_ingredients': ingredients[:8],
        'lifestyle': lifestyle,
        'warnings': warnings,
        'overall_risk': get_risk_level(health_score, aqi_index, sleep_float, stress_float)
    }

def get_risk_level(health_score, aqi, sleep, stress):
    score = 0
    if health_score < 50: score += 3
    elif health_score < 70: score += 1
    if aqi >= 4: score += 2
    elif aqi == 3: score += 1
    if sleep < 6: score += 2
    elif sleep < 7: score += 1
    if stress >= 7: score += 2
    elif stress >= 5: score += 1

    if score >= 6: return {'level': 'High', 'color': '#e74c3c', 'emoji': '🔴'}
    elif score >= 3: return {'level': 'Moderate', 'color': '#f39c12', 'emoji': '🟡'}
    else: return {'level': 'Low', 'color': '#27ae60', 'emoji': '🟢'}


# ─── Routes ─────────────────────────────────────────────────────────────────
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/analyze', methods=['POST'])
def analyze():
    try:
        city = request.form.get('city', 'Mumbai')
        sleep_hours = request.form.get('sleep', '7')
        skin_type = request.form.get('skin_type', 'normal')
        hormonal_phase = request.form.get('hormonal_phase', 'none')
        stress_level = request.form.get('stress', '5')

        # Process uploaded image
        skin_analysis = get_default_skin_analysis()
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
                file.save(filepath)
                skin_analysis = analyze_skin_image(filepath)
                # Clean up
                try: os.remove(filepath)
                except: pass

        # Get AQI
        aqi_data = get_aqi_data(city)

        # Generate recommendations
        recommendations = generate_recommendations(
            skin_analysis, aqi_data,
            float(sleep_hours), skin_type,
            hormonal_phase, float(stress_level)
        )

        return jsonify({
            'success': True,
            'skin_analysis': skin_analysis,
            'aqi_data': aqi_data,
            'recommendations': recommendations
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/aqi/<city>')
def get_aqi(city):
    data = get_aqi_data(city)
    return jsonify(data)

if __name__ == '__main__':
    os.makedirs('static/uploads', exist_ok=True)
    app.run(debug=True, port=5000)
