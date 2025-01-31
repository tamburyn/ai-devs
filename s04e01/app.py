import requests
import json
from openai import OpenAI
import os
from dotenv import load_dotenv
import re
import base64

# Load environment variables from .env file
load_dotenv()

class PhotoAnalyzer:
    def __init__(self):
        self.base_url = "https://centrala.ag3nts.org"
        self.api_key = "95e20ae1-e5a4-4a45-9350-f0b71ec099ce"
        self.report_url = f"{self.base_url}/report"
        self.openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        self.photo_context = {}

    def send_request(self, answer: str) -> dict:
        """Send request to the central API."""
        payload = {
            "task": "photos",
            "apikey": self.api_key,
            "answer": answer
        }
        
        try:
            response = requests.post(
                self.report_url,
                json=payload
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error: {e}")
            return {}

    def extract_urls(self, message: str) -> list:
        """Extract image URLs from the response message."""
        urls = re.findall(r'https://[\w\./\-]+\.PNG', message)
        return urls

    def download_and_encode_image(self, image_url: str) -> str:
        """Download image from URL and encode it to base64."""
        try:
            response = requests.get(image_url)
            response.raise_for_status()
            return base64.b64encode(response.content).decode('utf-8')
        except Exception as e:
            print(f"Error downloading/encoding image: {e}")
            return None

    def analyze_image_quality(self, image_url: str) -> str:
        """Ask GPT-4o to analyze image quality and suggest improvements."""
        try:
            # Download and encode image
            base64_image = self.download_and_encode_image(image_url)
            if not base64_image:
                return "NONE"

            response = self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "Analyze this image and suggest which command (REPAIR, DARKEN, or BRIGHTEN) should be applied to better reveal a person named Barbara. Focus on image quality and visibility. Respond with just one word: REPAIR, DARKEN, BRIGHTEN, or NONE."
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=50
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"Error analyzing image quality: {e}")
            return "NONE"

    def analyze_barbara(self, image_url: str) -> str:
        """Analyze image to find and describe Barbara."""
        try:
            base64_image = self.download_and_encode_image(image_url)
            if not base64_image:
                return ""

            prompt = """Opisz szczegółowo wszystkie osoby widoczne na zdjęciu, zwracając uwagę na:
            1. Wygląd fizyczny (wzrost, budowa ciała)
            2. Cechy charakterystyczne twarzy
            3. Kolor i styl włosów
            4. Ubiór i akcesoria
            5. Pozycję i zachowanie na zdjęciu
            
            Odpowiedz po polsku, opisując każdą osobę osobno."""

            response = self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": prompt
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=500
            )
            
            description = response.choices[0].message.content.strip()
            print(f"\nOpis ze zdjęcia {image_url}:")
            print(description)
            
            return description

        except Exception as e:
            print(f"Error analyzing image: {e}")
            return ""

    def analyze_response(self, response: dict) -> dict:
        """Analyze automaton response to determine next steps."""
        try:
            if not response or 'message' not in response:
                return {'action': 'SKIP', 'reason': 'No response from automaton'}

            message = response['message']
            base_url = "https://centrala.ag3nts.org/dane/barbara"
            
            # First check for full URLs in response
            urls = re.findall(r'https://[\w\./\-]+\.PNG', message)
            if urls:
                return {
                    'action': 'ANALYZE',
                    'url': urls[0],
                    'reason': 'Found full image URL in response'
                }
            
            # Then check for image filenames (e.g. IMG_559_FGR4.PNG)
            filenames = re.findall(r'IMG_\d+(?:_[A-Z0-9]+)?\.PNG', message)
            if filenames:
                return {
                    'action': 'ANALYZE',
                    'url': f"{base_url}/{filenames[0]}",
                    'reason': f'Found image filename: {filenames[0]}'
                }
            
            # Check for error messages or suggestions
            if 'nie udało się' in message.lower() or 'błąd' in message.lower():
                return {
                    'action': 'SKIP',
                    'reason': 'Error in processing image'
                }
            
            # Check for suggestions to try different method
            if 'spróbuj' in message.lower():
                if 'jaśniej' in message.lower() or 'rozjaśnić' in message.lower():
                    return {
                        'action': 'RETRY',
                        'method': 'BRIGHTEN',
                        'reason': 'Automaton suggests brightening'
                    }
                if 'ciemniej' in message.lower() or 'przyciemnić' in message.lower():
                    return {
                        'action': 'RETRY',
                        'method': 'DARKEN',
                        'reason': 'Automaton suggests darkening'
                    }
            
            return {
                'action': 'SKIP',
                'reason': 'No actionable information in response'
            }

        except Exception as e:
            print(f"Error analyzing response: {e}")
            return {'action': 'SKIP', 'reason': str(e)}

    def process_photos(self):
        print("Rozpoczynam analizę zdjęć...")
        
        # Start conversation
        initial_response = self.send_request("START")
        if not initial_response or 'message' not in initial_response:
            print("Nie udało się rozpocząć analizy.")
            return
        
        print(f"\nOdpowiedź automatu: {initial_response['message']}")
        
        # Extract photo names from initial response
        photo_names = re.findall(r'IMG_\d+\.PNG', initial_response['message'])
        if not photo_names:
            print("Nie znaleziono nazw zdjęć w odpowiedzi automatu.")
            return
        
        print(f"Znalezione zdjęcia: {photo_names}")
        useful_descriptions = []
        
        for photo_name in photo_names:
            print(f"\n=== Analiza zdjęcia: {photo_name} ===")
            
            # First try REPAIR
            print(f"Próba naprawy zdjęcia...")
            repair_response = self.send_request(f"REPAIR {photo_name}")
            print(f"Odpowiedź automatu (REPAIR): {repair_response['message']}")
            
            # Analyze response to see if we got improved image
            repair_analysis = self.analyze_response(repair_response)
            if repair_analysis['action'] == 'ANALYZE':
                print(f"Analizuję naprawione zdjęcie: {repair_analysis['url']}")
                description = self.analyze_barbara(repair_analysis['url'])
                if self.is_useful_description(description):
                    print("Znaleziono użyteczny opis po naprawie!")
                    useful_descriptions.append(description)
            
            # Try brightness adjustments based on automaton's response
            for method in ['BRIGHTEN', 'DARKEN']:
                print(f"\nPróba dostosowania jasności: {method}")
                adjust_response = self.send_request(f"{method} {photo_name}")
                print(f"Odpowiedź automatu ({method}): {adjust_response['message']}")
                
                adjust_analysis = self.analyze_response(adjust_response)
                if adjust_analysis['action'] == 'ANALYZE':
                    print(f"Analizuję zdjęcie po {method}: {adjust_analysis['url']}")
                    description = self.analyze_barbara(adjust_analysis['url'])
                    if self.is_useful_description(description):
                        print(f"Znaleziono użyteczny opis po {method}!")
                        useful_descriptions.append(description)
                elif adjust_analysis['action'] == 'RETRY':
                    suggested_method = adjust_analysis.get('method')
                    if suggested_method and suggested_method not in [method, 'REPAIR']:
                        print(f"Próba sugerowanej metody: {suggested_method}")
                        suggested_response = self.send_request(f"{suggested_method} {photo_name}")
                        print(f"Odpowiedź automatu ({suggested_method}): {suggested_response['message']}")
                        
                        suggested_analysis = self.analyze_response(suggested_response)
                        if suggested_analysis['action'] == 'ANALYZE':
                            print(f"Analizuję zdjęcie po {suggested_method}: {suggested_analysis['url']}")
                            description = self.analyze_barbara(suggested_analysis['url'])
                            if self.is_useful_description(description):
                                print(f"Znaleziono użyteczny opis po {suggested_method}!")
                                useful_descriptions.append(description)
        
        if useful_descriptions:
            print("\n=== Tworzenie końcowego rysopisu ===")
            print(f"Liczba zebranych opisów: {len(useful_descriptions)}")
            
            prompt = f"""Przeanalizuj poniższe opisy i stwórz spójny rysopis Barbary.
            Opisy z różnych zdjęć:
            {json.dumps(useful_descriptions, indent=2, ensure_ascii=False)}
            
            Stwórz jeden szczegółowy rysopis zawierający:
            1. Wygląd fizyczny (wzrost, budowa ciała)
            2. Charakterystyczne cechy twarzy
            3. Kolor i styl włosów
            4. Ubiór i akcesoria
            5. Inne wyróżniające się cechy
            
            Rysopis powinien być spójny i zawierać tylko potwierdzone informacje."""
            
            final_description = self.create_final_description(prompt)
            print("\n=== Końcowy rysopis ===")
            print(final_description)
            
            print("\n=== Wysyłanie rysopisu do centrali ===")
            response = self.send_request(final_description)
            print(f"Odpowiedź centrali: {json.dumps(response, indent=2, ensure_ascii=False)}")
        else:
            print("\nNie udało się stworzyć rysopisu Barbary - brak użytecznych opisów.")

    def is_useful_description(self, description: str) -> bool:
        """Check if the description contains useful information."""
        if not description:
            return False
        
        negative_phrases = [
            'nie mogę', 'przepraszam', 'brak', 
            'nie udało się', 'nie jestem w stanie',
            'nie widać', 'niewyraźne'
        ]
        
        # Check if description contains any negative phrases
        if any(phrase in description.lower() for phrase in negative_phrases):
            return False
        
        # Check if description has minimum length and contains relevant keywords
        relevant_keywords = ['twarz', 'włosy', 'ubrana', 'wzrost', 'sylwetka', 'oczy']
        has_relevant_info = any(keyword in description.lower() for keyword in relevant_keywords)
        
        return len(description) > 50 and has_relevant_info

    def create_final_description(self, prompt: str) -> str:
        """Create final description using GPT to combine all useful information."""
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=1000
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"Error creating final description: {e}")
            return ""

def main():
    analyzer = PhotoAnalyzer()
    analyzer.process_photos()

if __name__ == "__main__":
    main()