from flask import Flask, request, jsonify
import requests
from dotenv import load_dotenv
import os
from datetime import datetime
import threading
import time
from pyngrok import ngrok
from openai import OpenAI
import json

# Load environment variables
load_dotenv()

app = Flask(__name__)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def log_step(step: str, message: str):
    """Helper function for consistent logging"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n[{timestamp}] {step}")
    print("-" * 50)
    print(message)
    print("-" * 50)

class WebhookHandler:
    def __init__(self):
        self.base_url = "https://centrala.ag3nts.org"
        self.api_key = os.getenv("API_KEY", "95e20ae1-e5a4-4a45-9350-f0b71ec099ce")
        self.local_port = 5022
        self.report_url = f"{self.base_url}/report"
        
        # Start ngrok tunnel
        self.webhook_url = self.setup_ngrok()

    def setup_ngrok(self):
        """Setup ngrok tunnel"""
        try:
            # Configure ngrok
            ngrok.set_auth_token("2rTxwR4jI6kDbxNQaXZuoAT117i_2XkYnEn7vgAYcKAPhuESj")
            
            # Kill any existing ngrok processes
            ngrok.kill()
            
            # Start ngrok tunnel
            tunnel = ngrok.connect(self.local_port)
            ngrok_url = tunnel.public_url
            
            # Replace http with https if needed
            if ngrok_url.startswith('http://'):
                ngrok_url = ngrok_url.replace('http://', 'https://')
                
            log_step("Ngrok Setup", f"Tunnel established at: {ngrok_url}")
            return f"{ngrok_url}/moje_api"
            
        except Exception as e:
            log_step("Error", f"Failed to setup ngrok: {str(e)}")
            return None

    def register_webhook(self):
        """Register webhook URL with centrala"""
        if not self.webhook_url:
            log_step("Error", "No webhook URL available")
            return False

        payload = {
            "task": "webhook",
            "apikey": self.api_key,
            "answer": self.webhook_url
        }

        try:
            log_step("Registering Webhook", f"Sending payload: {payload}")
            response = requests.post(self.report_url, json=payload)
            response.raise_for_status()
            
            log_step("Success", f"""
Status Code: {response.status_code}
Response: {response.json()}
""")
            return True
        except Exception as e:
            log_step("Error", f"""
Failed to register webhook: {str(e)}
Response status: {getattr(e.response, 'status_code', 'N/A')}
Response text: {getattr(e.response, 'text', 'N/A')}
""")
            return False

def analyze_instruction(instruction: str) -> dict:
    """Analyze drone flight instruction using GPT-4"""
    system_prompt = """Jesteś ekspertem od nawigacji dronów. Pomagasz interpretować instrukcje lotu i określać lokalizację na mapie 4x4.

    Mapa terenu (współrzędne w formacie [x,y] gdzie [0,0] to lewy górny róg):
    [0,0]: lokalizacja
    [1,0]: trawa
    [2,0]: drzewo
    [3,0]: dom
    [0,1]: puste
    [1,1]: wiatrak
    [2,1]: trawa
    [3,1]: puste
    [0,2]: puste
    [1,2]: trawa
    [2,2]: skały
    [3,2]: drzewa
    [0,3]: góry
    [1,3]: góry
    [2,3]: samochód
    [3,3]: jaskinia

    Twoje zadanie:
    1. Przeanalizuj instrukcję lotu drona
    2. Określ końcową pozycję drona [x,y]
    3. Podaj co znajduje się w tym miejscu (maksymalnie 2 słowa, po polsku)
    4. Odpowiedz TYLKO w formacie JSON:
    {
        "analysis": "opis analizy ruchu",
        "position": "[x,y]",
        "description": "opis terenu"
    }

    Przykłady:
    Instrukcja: "leć na sam dół i w prawo"
    Odpowiedź:
    {
        "analysis": "1. Na sam dół: y=3, 2. W prawo: x=3",
        "position": "[3,3]",
        "description": "jaskinia"
    }

    Instrukcja: "leć maksymalnie w prawo, potem dwa pola w dół"
    Odpowiedź:
    {
        "analysis": "1. Maksymalnie w prawo: x=3, 2. Dwa pola w dół: y=2",
        "position": "[3,2]",
        "description": "drzewa"
    }"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Instrukcja: {instruction}"}
            ],
            response_format={"type": "json_object"}
        )
        
        result = response.choices[0].message.content
        log_step("GPT Analysis", result)
        return json.loads(result)
        
    except Exception as e:
        log_step("Error", f"GPT Analysis failed: {str(e)}")
        return None

@app.route('/moje_api', methods=['POST'])
def handle_instruction():
    try:
        data = request.get_json()
        instruction = data.get('instruction')
        
        log_step("Received Instruction", instruction)
        
        # Analyze instruction using GPT-4
        analysis = analyze_instruction(instruction)
        
        if not analysis:
            return jsonify({
                "description": "błąd analizy",
                "error": "Failed to analyze instruction"
            }), 500
            
        # Log the analysis
        log_step("Analysis Result", f"""
Position: {analysis['position']}
Description: {analysis['description']}
Analysis: {analysis['analysis']}
""")
        
        return jsonify({
            "description": analysis['description'],
            "debug": analysis
        })
        
    except Exception as e:
        log_step("Error", f"Request processing failed: {str(e)}")
        return jsonify({
            "description": "błąd systemu",
            "error": str(e)
        }), 500

def main():
    handler = WebhookHandler()
    
    # Najpierw uruchom serwer
    log_step("Server Starting", "Starting Flask server...")
    
    # Uruchom Flask w osobnym wątku
    server_thread = threading.Thread(
        target=lambda: app.run(host='0.0.0.0', port=handler.local_port)
    )
    server_thread.daemon = True
    server_thread.start()
    
    # Poczekaj aż serwer się uruchomi
    time.sleep(2)
    
    # Teraz zarejestruj webhook
    handler.register_webhook()
    
    # Kontynuuj działanie serwera
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        log_step("Shutdown", "Server shutting down...")

if __name__ == "__main__":
    main() 