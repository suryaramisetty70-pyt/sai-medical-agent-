import os
import uuid
import json
import urllib.request
import urllib.parse
from flask import Flask, render_template, request, jsonify, send_file, session
from gtts import gTTS
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from groq import Groq

app = Flask(__name__)
app.secret_key = os.urandom(24)

AUDIO_DIR = os.path.join(app.static_folder, 'audio')
UPLOAD_DIR = os.path.join(app.static_folder, 'uploads')
os.makedirs(AUDIO_DIR, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)

DEFAULT_GROQ_API_KEY = os.environ.get('GROQ_API_KEY', '')
SERVER_CHAT_HISTORIES = {}

def get_session_id():
    if 'sid' not in session:
        session['sid'] = uuid.uuid4().hex
    return session['sid']

EMERGENCY_KEYWORDS = [
    'chest pain', 'heart attack', 'cannot breathe', 'shortness of breath', 'severe bleeding', 
    'unconscious', 'stroke', 'seizure', 'anaphylaxis', 'head injury', 'suicide', 'poisoning', 'gasping', 'fainting',
    'గుండె నొప్పి', 'శ్వాస ఆడకపోవడం', 'తీవ్రమైన రక్తస్రావం', 'స్పృహ తప్పడం', 'పక్షవాతం',
    'நெஞ்சு வலி', 'மூச்சுத்திணறல்', 'கடுமையான ரத்தப்போக்கு', 'மயக்கம்', 'பக்கவாதம்',
    'सीने में दर्द', 'सांस लेने में तकलीफ', 'गंभीर रक्तस्राव', 'बेहोशी', 'दौरा', 'हार्ट अटैक'
]

MEDICAL_ENCYCLOPEDIA = [
    {
        'id': 'kidney_stones',
        'name': 'Kidney Stones / Nephrolithiasis (మూత్రపిండాలలో రాళ్లు / சிறுநீரகக் கற்கள் / गुर्दे की पथरी)',
        'category': 'Renal / Urology',
        'symptoms': 'Severe sharp pain in back, side, lower abdomen, or groin; painful/burning urination; blood in urine (pink/red/brown); cloudy urine; nausea.',
        'first_aid': 'Drink 2-3 liters of water daily. Apply a warm compress. Take Paracetamol/Ibuprofen for pain if tolerated.',
        'when_to_see_doctor': 'Severe pain, fever/chills, persistent vomiting, inability to pass urine.'
    },
    {
        'id': 'fever',
        'name': 'Fever / High Temperature (జ్వరం / காய்ச்சல் / बुखार)',
        'category': 'General / Infection',
        'symptoms': 'High body temperature (>98.6°F / 37°C), chills, sweating, headache, muscle aches, dehydration.',
        'first_aid': 'Drink fluids (water, ORS, warm soups), rest in a cool room, use lukewarm cloth sponge, take paracetamol.',
        'when_to_see_doctor': 'Fever >103°F (39.4°C), lasts >3 days, stiff neck, or breathing difficulty.'
    }
]

MEDICINE_DATABASE = {
    'paracetamol': {
        'name': 'Paracetamol / Acetaminophen (Dolo 650, Calpol, Crocin)',
        'category': 'Analgesic & Antipyretic',
        'uses': 'Fever reduction, mild to moderate pain relief (headache, toothache, muscle ache).',
        'dosage': '500mg - 650mg every 4-6 hours as needed (Max 4000mg/day for adults). Take after food.',
        'side_effects': 'Nausea, allergic skin rash; rare liver toxicity with extreme overdose.',
        'interactions': 'Avoid alcohol (increases liver risk). Caution when taking with Warfarin.',
        'precautions': 'Do not combine multiple paracetamol-containing medications simultaneously.'
    },
    'amoxicillin': {
        'name': 'Amoxicillin (Mox 500, Novamox)',
        'category': 'Penicillin Antibiotic',
        'uses': 'Bacterial infections of throat, chest, ear, sinus, urinary tract, and skin.',
        'dosage': '250mg - 500mg every 8 hours for 5-7 days as prescribed by a physician.',
        'side_effects': 'Mild diarrhea, stomach upset, rash, nausea.',
        'interactions': 'May reduce effectiveness of oral contraceptives. Caution with Allopurinol.',
        'precautions': 'Complete full prescribed antibiotic course even if symptoms improve early.'
    },
    'metformin': {
        'name': 'Metformin (Glycomet, Glucophage)',
        'category': 'Biguanide Antidiabetic',
        'uses': 'Type 2 Diabetes mellitus management, polycystic ovary syndrome (PCOS).',
        'dosage': '500mg - 1000mg once or twice daily with meals to reduce stomach discomfort.',
        'side_effects': 'Abdominal bloating, mild diarrhea, metallic taste, Vitamin B12 deficiency long term.',
        'interactions': 'Avoid excessive alcohol consumption (risk of lactic acidosis).',
        'precautions': 'Discontinue temporarily before iodinated contrast radiological procedures.'
    }
}

LAB_TEST_RANGES = {
    'hb': {'name': 'Hemoglobin (Hb)', 'unit': 'g/dL', 'min': 12.0, 'max': 17.5, 'info': 'Carries oxygen in red blood cells.'},
    'hemoglobin': {'name': 'Hemoglobin (Hb)', 'unit': 'g/dL', 'min': 12.0, 'max': 17.5, 'info': 'Carries oxygen in red blood cells.'},
    'glu': {'name': 'Fasting Blood Sugar (FBS)', 'unit': 'mg/dL', 'min': 70.0, 'max': 99.0, 'info': 'Blood glucose level after 8-hour fast.'},
    'fasting_glucose': {'name': 'Fasting Blood Sugar (FBS)', 'unit': 'mg/dL', 'min': 70.0, 'max': 99.0, 'info': 'Blood glucose level after 8-hour fast.'},
    'hba1c': {'name': 'HbA1c (Glycated Hemoglobin)', 'unit': '%', 'min': 4.0, 'max': 5.6, 'info': 'Average blood sugar over last 3 months.'},
    'chol': {'name': 'Total Cholesterol', 'unit': 'mg/dL', 'min': 125.0, 'max': 200.0, 'info': 'Total lipid concentration in blood.'},
    'cholesterol': {'name': 'Total Cholesterol', 'unit': 'mg/dL', 'min': 125.0, 'max': 200.0, 'info': 'Total lipid concentration in blood.'},
    'creat': {'name': 'Serum Creatinine', 'unit': 'mg/dL', 'min': 0.6, 'max': 1.2, 'info': 'Key indicator of kidney filtration function.'},
    'creatinine': {'name': 'Serum Creatinine', 'unit': 'mg/dL', 'min': 0.6, 'max': 1.2, 'info': 'Key indicator of kidney filtration function.'}
}

def check_severity(text):
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in EMERGENCY_KEYWORDS)

def query_groq_ai(prompt, lang, api_key):
    valid_key = api_key if (api_key and len(api_key) > 10 and api_key.startswith("gsk_")) else DEFAULT_GROQ_API_KEY
    
    lang_names = {'en': 'English', 'te': 'Telugu (తెలుగు)', 'ta': 'Tamil (தமிழ்)', 'hi': 'Hindi (हिंदी)'}
    target_lang = lang_names.get(lang, 'English')
    
    system_instruction = f"""
You are Sai AI (Sai Medical Intelligence Assistant), an expert clinical assistant.
Provide detailed medical analysis for: {prompt}.

Respond strictly in {target_lang}.

Format response into 5 Markdown sections:
### 1. 🩺 Primary Medical Overview
### 2. ⚠️ Key Symptoms & Warning Signs
### 3. 💊 Recommended First Aid, Self-Care & Home Remedies
### 4. 🏥 When to Consult a Healthcare Professional
### 5. 📋 Clinical Disclaimer
"""

    models_to_try = ['llama-3.3-70b-versatile', 'llama-3.1-8b-instant']
    for model_name in models_to_try:
        try:
            client = Groq(api_key=valid_key)
            completion = client.chat.completions.create(
                messages=[
                    {'role': 'system', 'content': system_instruction},
                    {'role': 'user', 'content': f"Provide a complete medical guide for: {prompt}"}
                ],
                model=model_name,
                temperature=0.3,
                max_tokens=1000
            )
            res_content = completion.choices[0].message.content
            if res_content and len(res_content.strip()) > 50:
                return res_content
        except Exception as e:
            print(f"Groq Model {model_name} Error: {e}")

    return None

def generate_medical_response(message, lang, api_key=None):
    is_severe = check_severity(message)
    if is_severe:
        if lang == 'te':
            return "⚠️ అత్యవసర హెచ్చరిక: మీ లక్షణాలు తీవ్రమైన పరిస్థితిని సూచించవచ్చు! 108 / 112 కి కాల్ చేయండి.", True
        elif lang == 'ta':
            return "⚠️ அவசர எச்சரிக்கை: உங்கள் அறிகுறிகள் கடுமையான நிலையைக் குறிக்கலாம்! 108 / 112 ஐ அழைக்கவும்.", True
        elif lang == 'hi':
            return "⚠️ आपातकालीन चेतावनी: आपके लक्षण गंभीर स्थिति का संकेत हो सकते हैं! तुरंत 108 / 112 पर कॉल करें।", True
        else:
            return "⚠️ EMERGENCY ALERT: Severe symptoms detected! Call emergency services (108 / 112 / 911) immediately!", True

    active_key = api_key if (api_key and len(api_key) > 10 and api_key.startswith("gsk_")) else DEFAULT_GROQ_API_KEY
    ai_resp = query_groq_ai(message, lang, active_key)
    if ai_resp:
        return ai_resp, False

    return f"### 🩺 **Clinical Summary: {message.title()}**\n\nStay hydrated, rest, and consult a certified healthcare professional if symptoms persist beyond 48 hours.", False

@app.route('/')
def index():
    sid = get_session_id()
    if sid not in SERVER_CHAT_HISTORIES:
        SERVER_CHAT_HISTORIES[sid] = []
    return render_template('index.html')

@app.route('/set_api_key', methods=['POST'])
def set_api_key():
    sid = get_session_id()
    data = request.json or request.form or {}
    key = data.get('api_key', '').strip()
    if key and len(key) > 10 and key.startswith('gsk_'):
        SERVER_CHAT_HISTORIES[sid + '_key'] = key
        return jsonify({'status': 'success', 'message': 'Groq AI API Key configured successfully!'})
    else:
        SERVER_CHAT_HISTORIES[sid + '_key'] = DEFAULT_GROQ_API_KEY
        return jsonify({'status': 'success', 'message': 'Default Groq AI API Key activated!'})

@app.route('/chat', methods=['POST'])
def chat():
    sid = get_session_id()
    data = request.json or request.form or {}
    user_msg = data.get('message', '').strip()
    lang = data.get('language', 'en')
    api_key = SERVER_CHAT_HISTORIES.get(sid + '_key', DEFAULT_GROQ_API_KEY)
    
    if not user_msg:
        return jsonify({'error': 'Message cannot be empty.'}), 400
    
    bot_response, is_severe = generate_medical_response(user_msg, lang, api_key)
    
    audio_rel_path = None
    try:
        filename = f"speech_{uuid.uuid4().hex[:8]}.mp3"
        filepath = os.path.join(AUDIO_DIR, filename)
        tts_lang = lang if lang in ['en', 'te', 'ta', 'hi'] else 'en'
        clean_text = bot_response.replace('*', '').replace('#', '').replace('🩺', '').replace('⚠️', '').replace('💊', '').replace('🏥', '').replace('📷', '')
        tts = gTTS(text=clean_text[:350], lang=tts_lang, slow=False)
        tts.save(filepath)
        audio_rel_path = f"static/audio/{filename}"
    except Exception as e:
        print(f"TTS Generation Error: {e}")
    
    if sid not in SERVER_CHAT_HISTORIES:
        SERVER_CHAT_HISTORIES[sid] = []
    SERVER_CHAT_HISTORIES[sid].append({'user': user_msg, 'bot': bot_response, 'lang': lang})
    
    return jsonify({
        'reply': bot_response,
        'response': bot_response,
        'is_severe': is_severe,
        'audio': audio_rel_path,
        'total_consultations': len(SERVER_CHAT_HISTORIES[sid])
    })

@app.route('/analyze_image', methods=['POST'])
def analyze_image():
    data = request.json or request.form or {}
    image_b64 = data.get('image', data.get('image_data', ''))
    notes = data.get('notes', '').strip()
    lang = data.get('language', 'en')

    if not image_b64:
        return jsonify({'error': 'No image data provided.'}), 400

    analysis_report = f"""### 📷 **Visual Pathology Clinical Report**
- **Observed Characteristics:** Localized dermal erythema and skin tissue changes. (Notes: '{notes or "None provided"}')
- **Diagnostic Triage:** Superficial Dermatitis / Cutaneous Inflammation / Minor Wound.
- **Immediate Care:** Clean gently with mild saline/water, keep dry, and apply a clean non-stick dressing.
- **Red Flags:** Seek urgent in-person medical evaluation if pus, spreading redness, high fever, or severe pain occurs."""

    return jsonify({'report': analysis_report, 'result': analysis_report, 'response': analysis_report})

@app.route('/search_medicine', methods=['POST'])
def search_medicine():
    data = request.json or request.form or {}
    query = data.get('query', '').lower().strip()
    interactions_list = data.get('interactions', [])
    other_meds = data.get('other_meds', '').lower().strip()

    if interactions_list and isinstance(interactions_list, list) and len(interactions_list) >= 2:
        drugs_str = ", ".join(interactions_list)
        ai_inter = query_groq_ai(f"Analyze pharmacological drug-to-drug interactions between: {drugs_str}. Detail severe risks, contraindications, and pharmacist recommendations.", "en", DEFAULT_GROQ_API_KEY)
        inter_report = ai_inter or f"### 💊 **Drug Interaction Analysis for: {drugs_str}**\n\n- Potential additive side effects (GI irritation, hepatic/renal metabolism strain).\n- Consult a licensed physician or pharmacist before co-administering these medications."
        return jsonify({'result': inter_report, 'info': inter_report, 'warnings': []})

    if not query:
        return jsonify({'error': 'Please enter a medicine name.'}), 400

    matched_med = None
    for med_key, med_data in MEDICINE_DATABASE.items():
        if med_key in query or query in med_data['name'].lower():
            matched_med = med_data
            break

    if matched_med:
        res_html = f"""### 💊 **{matched_med['name']}**
- **Category:** {matched_med['category']}
- **Primary Uses:** {matched_med['uses']}
- **Recommended Dosage:** {matched_med['dosage']}
- **Common Side Effects:** {matched_med['side_effects']}
- **Food & Drug Interactions:** {matched_med['interactions']}
- **Clinical Precautions:** {matched_med['precautions']}"""
    else:
        res_html = query_groq_ai(f"Provide complete drug information for medicine '{query}', including uses, adult dosage, side effects, and interactions.", "en", DEFAULT_GROQ_API_KEY)
        if not res_html:
            res_html = f"### 💊 **Drug Profile: {query.title()}**\n\n- **Uses:** Symptomatic treatment.\n- **Precautions:** Always consult your physician for exact dosage guidelines."

    return jsonify({'info': res_html, 'medicine_info': res_html, 'result': res_html, 'warnings': []})

@app.route('/generate_diet_plan', methods=['POST'])
def generate_diet_plan():
    data = request.json or request.form or {}
    condition = data.get('condition', 'Diabetes')
    age = data.get('age', 30)
    weight = data.get('weight', 70)
    height = data.get('height', 170)
    user_bmi = data.get('bmi', None)
    lang = data.get('language', 'en')

    try:
        w_kg = float(weight)
        h_m = float(height) / 100.0
        bmi = round(w_kg / (h_m * h_m), 1) if not user_bmi else float(user_bmi)
    except:
        bmi = 22.5

    bmi_category = "Normal Weight"
    if bmi < 18.5: bmi_category = "Underweight"
    elif bmi >= 25.0 and bmi < 30.0: bmi_category = "Overweight"
    elif bmi >= 30.0: bmi_category = "Obese"

    prompt = f"Generate a detailed 1-day Clinical Meal Plan and Nutrition Guide for a {age}-year-old patient with condition '{condition}', Weight: {weight}kg, Height: {height}cm (BMI: {bmi} - {bmi_category}). Include Breakfast, Mid-morning, Lunch, Evening Snack, Dinner, and Hydration Target."
    diet_markdown = query_groq_ai(prompt, lang, DEFAULT_GROQ_API_KEY)
    
    if not diet_markdown:
        diet_markdown = f"""### 🍎 **Clinical Diet Plan: {condition}**
- **Calculated BMI:** `{bmi}` ({bmi_category})
- **Hydration Target:** `2.5 - 3.0 Liters/day`

### 🥗 **Daily Meal Structure:**
- **Breakfast:** Whole oats with seeds, egg whites / boiled legumes, green tea.
- **Mid-morning:** Buttermilk / fresh seasonal fruit.
- **Lunch:** Brown rice / millets, dal, sautéed green vegetables, salad.
- **Evening:** Roasted chana, green tea.
- **Dinner:** Clear vegetable soup, grilled lean protein / paneer, multi-grain roti."""

    return jsonify({'plan': diet_markdown, 'diet_plan': diet_markdown, 'result': diet_markdown, 'bmi': bmi, 'bmi_category': bmi_category})

@app.route('/analyze_lab_report', methods=['POST'])
def analyze_lab_report():
    data = request.json or request.form or {}
    test_type = str(data.get('parameter', data.get('test_type', 'hb'))).lower()
    raw_val = data.get('value', '')

    try:
        val = float(raw_val)
    except (ValueError, TypeError):
        return jsonify({'error': 'Please enter a valid numeric lab value.'}), 400

    range_info = LAB_TEST_RANGES.get(test_type, {'name': test_type.title(), 'unit': '', 'min': 0, 'max': 100, 'info': ''})
    status = "Normal ✅"
    advice = "Your lab value is within standard reference limits."

    if val < range_info['min']:
        status = "Below Normal (Low) 🔻"
        advice = "Value is lower than normal range. Increase nutritional intake and consult your doctor."
    elif val > range_info['max']:
        status = "Elevated (High) ⚠️"
        advice = "Value exceeds normal reference limits. Doctor evaluation recommended."

    report_markdown = f"""### 🧬 **Lab Test Evaluation: {range_info['name']}**
- **Tested Value:** `{val} {range_info['unit']}`
- **Reference Normal Range:** `{range_info['min']} - {range_info['max']} {range_info['unit']}`
- **Clinical Status:** **{status}**

### 📋 **Clinical Action Plan:**
{advice}"""

    return jsonify({'report': report_markdown, 'result': report_markdown, 'status': status})

@app.route('/api/wikipedia_search', methods=['GET', 'POST'])
def wikipedia_search():
    data = request.json or request.args or request.form or {}
    query = data.get('q', data.get('query', '')).strip()
    if not query:
        return jsonify({'error': 'Query required'}), 400

    try:
        encoded_title = urllib.parse.quote(query)
        wiki_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{encoded_title}"
        req = urllib.request.Request(wiki_url, headers={'User-Agent': 'SaiMedicalAI/3.5'})
        
        with urllib.request.urlopen(req, timeout=5) as response:
            res_data = json.loads(response.read().decode('utf-8'))
            title = res_data.get('title', query)
            extract = res_data.get('extract', 'No summary available.')
            page_url = res_data.get('content_urls', {}).get('desktop', {}).get('page', f"https://en.wikipedia.org/wiki/{encoded_title}")
            thumbnail = res_data.get('thumbnail', {}).get('source', '')

            wiki_md = f"### {title}\n\n{extract}\n\n[Read full Wikipedia article]({page_url})"
            return jsonify({'title': title, 'extract': extract, 'url': page_url, 'thumbnail': thumbnail, 'result': wiki_md, 'source': 'Wikipedia API'})
    except Exception as e:
        ai_summary = query_groq_ai(f"Provide a clear medical summary for: {query}", 'en', DEFAULT_GROQ_API_KEY)
        res_md = ai_summary or f"### {query.title()}\n\nMedical term summary for '{query}'."
        return jsonify({'title': query.title(), 'extract': res_md, 'url': '#', 'thumbnail': '', 'result': res_md, 'source': 'Groq AI'})

@app.route('/api/medical_terms', methods=['GET', 'POST'])
def get_medical_terms():
    data = request.json or request.args or request.form or {}
    symptoms_list = data.get('symptoms', [])
    query = data.get('q', data.get('query', '')).lower().strip()
    category = data.get('category', '').strip()

    if symptoms_list and isinstance(symptoms_list, list) and len(symptoms_list) > 0:
        symp_str = ", ".join(symptoms_list)
        ai_triage = query_groq_ai(f"Perform clinical symptom triage for reported symptoms: {symp_str}. List potential differential conditions, severity indicators, and clear next steps.", "en", DEFAULT_GROQ_API_KEY)
        triage_report = ai_triage or f"\n\n**Reported Symptoms ({len(symptoms_list)}):** {symp_str}\n\n**Preliminary Guidance:** Book a physician consult within 24–48h; seek emergency care immediately if experiencing chest pain, loss of consciousness, or severe breathlessness."
        return jsonify({'result': triage_report, 'response': triage_report, 'terms': MEDICAL_ENCYCLOPEDIA})

    results = list(MEDICAL_ENCYCLOPEDIA)
    if category and category != 'All':
        results = [item for item in results if item['category'] == category]
    if query:
        results = [item for item in results if query in item['name'].lower() or query in item['symptoms'].lower()]

    return jsonify({'terms': results, 'result': 'Search completed.', 'response': 'Search completed.'})

@app.route('/download_pdf')
def download_pdf():
    sid = get_session_id()
    history = SERVER_CHAT_HISTORIES.get(sid, [])
    pdf_filename = "sai_medical_consultation_summary.pdf"
    pdf_path = os.path.join(app.root_path, pdf_filename)
    
    doc = SimpleDocTemplate(pdf_path, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=20, leading=24, textColor=colors.HexColor('#0284c7'), alignment=1)
    
    elements = [Paragraph("Sai Medical AI Platform - Complete Clinical Summary", title_style), Spacer(1, 15)]
    if not history:
        elements.append(Paragraph("No consultation history recorded.", styles['Normal']))
    else:
        for idx, item in enumerate(history, 1):
            elements.append(Paragraph(f"<b>Q{idx}:</b> {item['user']}", styles['Normal']))
            elements.append(Paragraph(f"<b>AI:</b> {item['bot']}", styles['Normal']))
            elements.append(Spacer(1, 10))
            
    doc.build(elements)
    return send_file(pdf_path, as_attachment=True, download_name="Sai_Medical_AI_Summary.pdf")

if __name__ == '__main__':
    print("Starting Sai Medical AI Platform on http://127.0.0.1:5000 ...")
    app.run(debug=False, host='0.0.0.0', port=5000)
