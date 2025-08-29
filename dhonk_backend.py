from flask import Flask, request, jsonify   # type: ignore
from flask_cors import CORS                 # type: ignore
import psycopg2    # type: ignore
from psycopg2.extras import RealDictCursor   # type: ignore
import re
import os
from dotenv import load_dotenv

# ✅ Load environment variables
load_dotenv()

# ✅ OpenAI SDK import (new version)
from openai import OpenAI   # type: ignore

# ✅ Import Dhonk Craft Intent Functions
from intent_handler import detect_intent, get_intent_response   # ✅ Correct

app = Flask(__name__)
CORS(app)

# 🔐 OpenAI Config from ENV
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY)
MODEL_NAME = "gpt-4o-mini"

# 🛢️ PostgreSQL Database Config from ENV
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "database": os.getenv("DB_NAME", "dhonk_craft_user"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "123456789"),
    "port": int(os.getenv("DB_PORT", 5432))
}

# 📞 Contact Info
CONTACTS = {
    "founder": {
        "name": "Divya Khandal",
        "email": "divz333@gmail.com",
        "phone": "9166167005",
        "role": "Founder"
    },
    "gm": {
        "name": "Mr. Maan Singh",
        "email": "mansinghr4@gmail.com",
        "phone": "9829854896",
        "role": "General Manager"
    }
}

# 🌐 Hindi Detection
def is_hindi(text):
    return re.search('[\u0900-\u097F]', text) is not None

# 🔍 Smart Filter
def smart_filter(content, query, max_sentences=3):
    sentences = re.split(r'(?<=[.?!])\s+', content.strip())
    query_words = query.lower().split()
    scored = [(sum(1 for w in query_words if w in s.lower()), s) 
              for s in sentences if any(w in s.lower() for w in query_words)]
    scored.sort(reverse=True)
    filtered = [s for _, s in scored]
    return " ".join(filtered[:max_sentences]) if filtered else " ".join(sentences[:max_sentences])

# 🔎 Search DB
def search_database(query):
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("""
            SELECT title, url, content FROM dhonk_pages
            WHERE content ILIKE %s ORDER BY LENGTH(content) ASC LIMIT 1
        """, (f"%{query}%",))
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        return result
    except Exception as e:
        print("DB Error:", e)
        return None

# 📬 Fallback Contact Info Handler
def contact_response(msg):
    msg = msg.lower()
    if "founder" in msg or "divya" in msg:
        return f"👩‍💼 *Founder*: {CONTACTS['founder']['name']}\n📧 Email: {CONTACTS['founder']['email']}\n📞 Phone: {CONTACTS['founder']['phone']}"
    elif "general manager" in msg or "maan singh" in msg or "gm" in msg:
        return f"👨‍💼 *General Manager*: {CONTACTS['gm']['name']}\n📧 Email: {CONTACTS['gm']['email']}\n📞 Phone: {CONTACTS['gm']['phone']}"
    elif "contact" in msg:
        return (
            f"📞 *Founder*: {CONTACTS['founder']['phone']} | *GM*: {CONTACTS['gm']['phone']}\n"
            f"📧 *Emails*: {CONTACTS['founder']['email']}, {CONTACTS['gm']['email']}"
        )
    return None

# 📌 System Prompts
system_prompt_en = (
    "You are ONLY an AI assistant for Dhonk Craft, a sustainable clothing and craft brand in India. "
    "Only answer questions related to Dhonk Craft: its founders, products, services, policies, or vision. "
    "Founders: Divya Khandal (Creative Director), Dharmendra Khandal (CEO). Do NOT answer unrelated questions."
)

system_prompt_hi = (
    "आप Dhonk Craft के लिए एक सहायक बॉट हैं। जब कोई हिंदी में सवाल पूछे, "
    "तो आप साफ़ और सरल हिंदी में जवाब दें। Dhonk Craft एक भारतीय ब्रांड है "
    "जो हस्तशिल्प और टिकाऊ कपड़ों के लिए जाना जाता है। आप केवल इससे जुड़े सवालों के जवाब देंगे।"
)

# ✅ Health Check
@app.route("/", methods=["GET"])
def home():
    return jsonify({"status": "✅ Dhonk Craft Backend with OpenAI is running!"})

# ✅ Main Chat Route
@app.route("/chat", methods=["POST"])
def chat():
    user_msg = request.json.get("message", "").strip()
    if not user_msg:
        return jsonify({"answer": "❌ Please type something."}), 400

    # Step 1: Intent Detection
    intent = detect_intent(user_msg)
    intent_response = get_intent_response(intent)
    if intent_response:
        return jsonify({"answer": intent_response})

    # Step 2: Contact Info
    contact_reply = contact_response(user_msg)
    if contact_reply:
        return jsonify({"answer": contact_reply})

    # Step 3: Database Search
    db_result = search_database(user_msg)
    if db_result:
        short_answer = smart_filter(db_result['content'], user_msg)
        if db_result['url']:
            short_answer += f"\n\n🔗 [More Info]({db_result['url']})"
        return jsonify({"answer": short_answer})

    # Step 4: Fallback → OpenAI
    try:
        system_prompt = system_prompt_hi if is_hindi(user_msg) else system_prompt_en
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_msg}
            ],
            temperature=0.6
        )
        reply = response.choices[0].message.content
        return jsonify({"answer": reply})
    except Exception as e:
        return jsonify({"answer": f"❌ OpenAI Error: {str(e)}"}), 500

# ✅ Run Server
if __name__ == "__main__":
    print("✅ Dhonk Craft Chatbot Running...")
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
