from flask import Flask, render_template, request, jsonify
import google.generativeai as genai
import PyPDF2
import os
from dotenv import load_dotenv
from datetime import datetime
import re

app = Flask(__name__)
load_dotenv()

# Configure Gemini API
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
if not GOOGLE_API_KEY:
    raise ValueError("GOOGLE_API_KEY not found in environment variables. Please check your .env file.")

genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel('gemini-2.0-pro-exp')  # Changed from gemini-1.5-flash to gemini-pro as it's more stable

# Store character descriptions and chat history in memory (in a real app, you'd use a database)
characters = {}

class Character:
    def __init__(self, name, description, created_at):
        self.name = name
        self.description = description
        self.created_at = created_at
        self.chat_history = []

def extract_text_from_pdf(pdf_file):
    pdf_reader = PyPDF2.PdfReader(pdf_file)
    text = ""
    for page in pdf_reader.pages:
        text += page.extract_text()
    return text

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/upload_character', methods=['POST'])
def upload_character():
    if 'pdf_file' in request.files:
        pdf_file = request.files['pdf_file']
        if pdf_file.filename != '':
            character_text = extract_text_from_pdf(pdf_file)
            character_name = request.form.get('name', f"Character {len(characters)}")
            character_id = f"character_{len(characters)}"
            characters[character_id] = Character(
                name=character_name,
                description=character_text,
                created_at=datetime.now().isoformat()
            )
            return jsonify({
                "success": True,
                "character_id": character_id,
                "name": character_name
            })
    
    return jsonify({"success": False, "error": "No file uploaded"})

@app.route('/set_character_description', methods=['POST'])
def set_character_description():
    data = request.json
    description = data.get('description')
    name = data.get('name', f"Character {len(characters)}")
    
    if description:
        character_id = f"character_{len(characters)}"
        characters[character_id] = Character(
            name=name,
            description=description,
            created_at=datetime.now().isoformat()
        )
        return jsonify({
            "success": True,
            "character_id": character_id,
            "name": name
        })
    
    return jsonify({"success": False, "error": "No description provided"})

@app.route('/get_characters', methods=['GET'])
def get_characters():
    return jsonify({
        "success": True,
        "characters": [
            {
                "id": char_id,
                "name": char.name,
                "created_at": char.created_at
            }
            for char_id, char in characters.items()
        ]
    })

@app.route('/get_chat_history/<character_id>', methods=['GET'])
def get_chat_history(character_id):
    if character_id in characters:
        return jsonify({
            "success": True,
            "chat_history": characters[character_id].chat_history
        })
    return jsonify({"success": False, "error": "Character not found"})

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    message = data.get('message')
    character_id = data.get('character_id')
    
    print(f"Received chat request - Message: {message}, Character ID: {character_id}")  # Debug log
    
    if not message:
        return jsonify({"success": False, "error": "Message is required"})
    if not character_id:
        return jsonify({"success": False, "error": "Character ID is required"})
    if character_id not in characters:
        return jsonify({"success": False, "error": f"Character with ID {character_id} not found"})
    
    character = characters[character_id]
    
    # Build context from chat history (last 5 messages)
    context = ""
    if character.chat_history:
        recent_history = character.chat_history[-5:]
        for msg in recent_history:
            context += f"{msg['role']}: {msg['content']}\n"
    
    prompt = f"""You are a chatbot that should act and respond like the following character:
    {character.description}
    
    Important Instructions:
    1. Respond naturally as if in a real conversation
    2. DO NOT use asterisks (*) or describe actions
    3. DO NOT use roleplay-style text or emotes
    4. Speak directly as the character would speak
    5. Keep responses concise and natural
    
    Previous conversation:
    {context}
    
    User: {message}
    Character:"""
    
    try:
        response = model.generate_content(prompt)
        response_text = response.text
        
        # Clean up the response by removing action descriptions
        cleaned_response = response_text
        # Remove text between asterisks and the asterisks themselves
        cleaned_response = re.sub(r'\*[^*]*\*', '', cleaned_response)
        # Remove text between parentheses
        cleaned_response = re.sub(r'\([^)]*\)', '', cleaned_response)
        # Remove text between brackets
        cleaned_response = re.sub(r'\[[^\]]*\]', '', cleaned_response)
        # Clean up any extra whitespace
        cleaned_response = ' '.join(cleaned_response.split())
        
        # Store the conversation
        character.chat_history.append({
            "role": "user",
            "content": message,
            "timestamp": datetime.now().isoformat()
        })
        character.chat_history.append({
            "role": "character",
            "content": cleaned_response,
            "timestamp": datetime.now().isoformat()
        })
        
        return jsonify({
            "success": True,
            "response": cleaned_response,
            "character_name": character.name
        })
    except Exception as e:
        print(f"Error in chat: {str(e)}")  # Debug log
        return jsonify({"success": False, "error": str(e)})

if __name__ == '__main__':
    app.run(debug=True) 