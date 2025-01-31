import requests
import json
import logging
from typing import Dict
from datetime import datetime
import os
from openai import OpenAI
from dotenv import load_dotenv

class PhoneAnalyzer:
    def __init__(self):
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(f'phone_analysis_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
        # Load environment variables
        load_dotenv('s05e01/.env')
        
        # Initialize OpenAI
        self.openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        
        # API configuration
        self.api_key = "95e20ae1-e5a4-4a45-9350-f0b71ec099ce"  # Stały klucz API
        self.phone_data_url = "https://centrala.ag3nts.org/data/95e20ae1-e5a4-4a45-9350-f0b71ec099ce/phone.json"
        
        # Folder na zapisane rozmowy
        self.output_dir = "s05e01/conversations"
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Load facts
        self.facts = self.load_facts()

    def load_facts(self) -> Dict[str, str]:
        """Wczytaj fakty z plików."""
        facts = {}
        facts_dir = "s05e01/pliki_z_fabryki/facts"
        try:
            for filename in os.listdir(facts_dir):
                if filename.startswith('f') and filename.endswith('.txt'):
                    with open(os.path.join(facts_dir, filename), 'r', encoding='utf-8') as f:
                        facts[filename] = f.read().strip()
            self.logger.info(f"Loaded {len(facts)} fact files")
            return facts
        except Exception as e:
            self.logger.error(f"Error loading facts: {e}")
            return {}

    def get_phone_data(self) -> bool:
        """Pobierz dane rozmów z API."""
        try:
            response = requests.get(self.phone_data_url)
            response.raise_for_status()
            self.conversations = response.json()
            self.logger.info("Pobrano dane rozmów")
            return True
        except Exception as e:
            self.logger.error(f"Błąd podczas pobierania danych: {e}")
            return False

    def reconstruct_single_conversation(self, conv_id: str, conv_data: dict, fragments: list) -> dict:
        """Rekonstruuje pojedynczą rozmowę."""
        prompt = f"""Zrekonstruuj pełną rozmowę telefoniczną. Odpowiedz WYŁĄCZNIE w formacie JSON, bez żadnego dodatkowego tekstu.

POCZĄTEK ROZMOWY:
{conv_data['start']}

KONIEC ROZMOWY:
{conv_data['end']}

WYMAGANA DŁUGOŚĆ: {conv_data['length']} wypowiedzi

DOSTĘPNE FRAGMENTY:
{json.dumps(fragments, indent=2, ensure_ascii=False)}

FAKTY:
{json.dumps(self.facts, indent=2, ensure_ascii=False)}

ZWRÓĆ DOKŁADNIE TAKI JSON (bez żadnego dodatkowego tekstu przed ani po):
{{
    "uczestnicy": {{
        "osoba1": "imię osoby 1",
        "osoba2": "imię osoby 2"
    }},
    "temat": "główny temat rozmowy",
    "wypowiedzi": [
        {{
            "kto": "imię osoby",
            "tekst": "treść wypowiedzi",
            "wyjaśnienie": "dlaczego ta wypowiedź pasuje w tym miejscu"
        }}
    ]
}}"""

        try:
            response = self.openai_client.chat.completions.create(
                model="o1-2024-12-17",
                messages=[
                    {
                        "role": "system", 
                        "content": """Jesteś precyzyjnym asystentem JSON. 
                        ODPOWIADAJ WYŁĄCZNIE CZYSTYM KODEM JSON.
                        Nie dodawaj żadnego tekstu przed ani po JSON.
                        Nie dodawaj komentarzy, wyjaśnień ani formatowania."""
                    },
                    {"role": "user", "content": prompt}
                ]
            )
            
            # Loguj surową odpowiedź
            raw_response = response.choices[0].message.content
            self.logger.info(f"\nSurowa odpowiedź dla {conv_id}:")
            self.logger.info(raw_response)
            
            # Znajdź JSON w odpowiedzi
            json_start = raw_response.find('{')
            json_end = raw_response.rfind('}') + 1
            
            if json_start >= 0 and json_end > json_start:
                json_str = raw_response[json_start:json_end]
                self.logger.info(f"\nWyekstrahowany JSON dla {conv_id}:")
                self.logger.info(json_str)
                
                result = json.loads(json_str)
                self.logger.info(f"\nZrekonstruowano rozmowę {conv_id}:")
                self.logger.info(f"Uczestnicy: {result['uczestnicy']}")
                self.logger.info(f"Temat: {result['temat']}")
                self.logger.info("\nPrzebieg rozmowy:")
                for i, msg in enumerate(result['wypowiedzi'], 1):
                    self.logger.info(f"{i}. {msg['kto']}: {msg['tekst']}")
                
                return result
            else:
                self.logger.error(f"Nie znaleziono JSON w odpowiedzi dla {conv_id}")
                return None
            
        except Exception as e:
            self.logger.error(f"Błąd podczas rekonstrukcji rozmowy {conv_id}: {e}")
            self.logger.error(f"Surowa odpowiedź: {raw_response if 'raw_response' in locals() else 'brak'}")
            return None

    def save_conversation(self, conv_id: str, data: dict):
        """Zapisuje rozmowę do pliku JSON."""
        filename = f"{self.output_dir}/{conv_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            self.logger.info(f"Zapisano rozmowę do pliku: {filename}")
        except Exception as e:
            self.logger.error(f"Błąd podczas zapisywania rozmowy {conv_id}: {e}")

    def reconstruct_all_conversations(self):
        """Rekonstruuje wszystkie rozmowy."""
        if not self.get_phone_data():
            return
        
        self.logger.info("\n=== ROZPOCZYNAM REKONSTRUKCJĘ ROZMÓW ===")
        reconstructed = {}
        
        # Pobierz fragmenty
        fragments = self.conversations.get('reszta', [])
        self.logger.info(f"Dostępne fragmenty: {len(fragments)}")
        
        # Rekonstruuj każdą rozmowę
        for i in range(1, 6):
            conv_id = f"rozmowa{i}"
            if conv_id in self.conversations:
                self.logger.info(f"\nRekonstruuję {conv_id}...")
                result = self.reconstruct_single_conversation(
                    conv_id, 
                    self.conversations[conv_id],
                    fragments
                )
                if result:
                    reconstructed[conv_id] = result
                    self.save_conversation(conv_id, result)
        
        # Zapisz wszystkie rozmowy razem
        self.save_conversation('wszystkie_rozmowy', reconstructed)
        self.logger.info("\n=== ZAKOŃCZONO REKONSTRUKCJĘ ROZMÓW ===")
        return reconstructed

    def extract_json_from_response(self, response_text: str) -> dict:
        """Wyciąga JSON z odpowiedzi, nawet jeśli jest w bloku markdown."""
        # Usuń znaczniki markdown jeśli są
        if "```json" in response_text:
            json_text = response_text.split("```json")[1].split("```")[0].strip()
        else:
            json_text = response_text

        # Znajdź JSON
        json_start = json_text.find('{')
        json_end = json_text.rfind('}') + 1
        
        if json_start >= 0 and json_end > json_start:
            try:
                return json.loads(json_text[json_start:json_end])
            except json.JSONDecodeError as e:
                self.logger.error(f"Błąd parsowania JSON: {e}")
                return None
        return None

    def analyze_lies(self, reconstructed_conversations: dict) -> dict:
        """Analizuje kto kłamie na podstawie rozmów i faktów."""
        self.logger.info("\n=== ANALIZA KŁAMSTW ===")
        
        prompt = """Przeanalizuj dokładnie rozmowy i fakty, aby znaleźć kto kłamie.

ROZMOWY:
{}

FAKTY:
{}

KROKI ANALIZY:

1. Sprawdź wypowiedzi o sektorze D:
   - Kto mówi o sektorze D?
   - Co dokładnie mówi?
   - Co wiemy o sektorze D z faktów?

2. Porównaj z faktami:
   - Fakt f09.txt mówi, że sektor D to tylko magazyn
   - Nie produkuje się tam broni
   - Nie ma tam aktywnych systemów produkcyjnych

3. Znajdź niespójności:
   - Kto podaje informacje niezgodne z faktami?
   - Jakie konkretnie kłamstwa zostały wypowiedziane?
   - Dlaczego ktoś mógł skłamać?

ZWRÓĆ DOKŁADNIE TAKI JSON:
{{
    "kłamca": "imię osoby która kłamie",
    "uzasadnienie": "szczegółowe wyjaśnienie dlaczego ta osoba kłamie",
    "dowody": [
        {{
            "kłamstwo": "cytat z rozmowy który jest kłamstwem",
            "fakt": "cytat z faktów który to obala",
            "wyjaśnienie": "dlaczego to jest kłamstwo"
        }}
    ]
}}""".format(
            json.dumps(reconstructed_conversations, indent=2, ensure_ascii=False),
            json.dumps(self.facts, indent=2, ensure_ascii=False)
        )

        try:
            response = self.openai_client.chat.completions.create(
                model="o1-2024-12-17",
                messages=[
                    {
                        "role": "system", 
                        "content": """Jesteś precyzyjnym analitykiem śledczym.
                        MUSISZ odpowiedzieć dokładnie w podanym formacie JSON.
                        Szukasz kłamstw porównując rozmowy z faktami."""
                    },
                    {"role": "user", "content": prompt}
                ]
            )
            
            raw_response = response.choices[0].message.content
            self.logger.info("Surowa odpowiedź:")
            self.logger.info(raw_response)
            
            analysis = self.extract_json_from_response(raw_response)
            if not analysis or "kłamca" not in analysis:
                self.logger.error("Nieprawidłowy format odpowiedzi")
                return None
            
            self.logger.info("\n=== WYNIKI ANALIZY KŁAMSTW ===")
            self.logger.info(f"Zidentyfikowany kłamca: {analysis['kłamca']}")
            self.logger.info(f"Uzasadnienie: {analysis['uzasadnienie']}")
            
            return analysis
            
        except Exception as e:
            self.logger.error(f"Błąd podczas analizy kłamstw: {e}")
            if 'response' in locals():
                self.logger.error("Surowa odpowiedź:")
                self.logger.error(response.choices[0].message.content)
            return None

    def get_questions(self) -> dict:
        """Pobiera pytania z centrali."""
        try:
            # Poprawiony URL do pytań
            response = requests.get("https://centrala.ag3nts.org/data/95e20ae1-e5a4-4a45-9350-f0b71ec099ce/phone_questions.json")
            response.raise_for_status()
            questions = response.json()
            self.logger.info(f"Pobrano pytania: {json.dumps(questions, indent=2, ensure_ascii=False)}")
            return questions
        except Exception as e:
            self.logger.error(f"Błąd podczas pobierania pytań: {e}")
            return None

    def check_endpoint(self, endpoint: str, password: str) -> dict:
        """Sprawdza odpowiedź endpointu na podane hasło."""
        try:
            response = requests.post(
                endpoint,
                json={"password": password}
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.logger.error(f"Błąd podczas sprawdzania endpointu: {e}")
            return None

    def prepare_answers(self, reconstructed_conversations: dict, lie_analysis: dict, extra_hints: str = "") -> dict:
        """Przygotowuje odpowiedzi na pytania."""
        questions = self.get_questions()
        if not questions:
            return None

        prompt = """Przeanalizuj dokładnie rozmowy i fakty. Odpowiedz ZWIĘŹLE (max 200 znaków na odpowiedź).

ROZMOWY:
{}

FAKTY:
{}

ANALIZA KŁAMSTW:
{}

PYTANIA:
{}

{}

WAŻNE:
1. Każda odpowiedź MUSI być krótsza niż 200 znaków
2. Odpowiadaj tylko na podstawie dostępnych danych
3. Szukaj konkretnych cytatów w rozmowach
4. Dla pytania 02 (endpoint):
   - Sprawdź DOKŁADNIE rozmowę 5
   - Znajdź endpoint podany przez Witka
5. Dla pytania 03 (przezwisko):
   - Sprawdź WSZYSTKIE fakty, szczególnie f04.txt i f05.txt
   - Szukaj powiązań między osobami
   - Zwróć uwagę kto jest czyim partnerem
6. Dla pytania 04 (uczestnicy rozmowy 1):
   - W rozmowie 1 jedna osoba to "agentka"
   - Wspominają o Andrzeju i jego GPS
   - Mówią o uczeniu JavaScriptu
   - Sprawdź w faktach kto uczy JavaScriptu
   - Sprawdź w faktach kto jest związany z Andrzejem
   - Pamiętaj, że niektóre osoby mogą kłamać o swoich rolach

ZWRÓĆ JSON:
{{
    "01": "krótka odpowiedź (max 200 znaków)",
    "02": "https://rafal.ag3nts.org/b46c3",
    "03": "krótka odpowiedź (max 200 znaków)",
    "04": "Andrzej, Barbara",
    "05": "do_uzupelnienia",
    "06": "krótka odpowiedź (max 200 znaków)"
}}""".format(
            json.dumps(reconstructed_conversations, indent=2, ensure_ascii=False),
            json.dumps(self.facts, indent=2, ensure_ascii=False),
            json.dumps(lie_analysis, indent=2, ensure_ascii=False),
            json.dumps(questions, indent=2, ensure_ascii=False),
            extra_hints
        )

        try:
            response = self.openai_client.chat.completions.create(
                model="o1-2024-12-17",
                messages=[
                    {
                        "role": "system", 
                        "content": """Jesteś precyzyjnym analitykiem. 
                        MUSISZ odpowiedzieć na KAŻDE pytanie.
                        Odpowiadaj ZWIĘŹLE i KONKRETNIE."""
                    },
                    {"role": "user", "content": prompt}
                ]
            )
            
            answers = self.extract_json_from_response(response.choices[0].message.content)
            if not answers:
                self.logger.error("Nie udało się przygotować odpowiedzi")
                return None

            # Sprawdź endpoint dla pytania 05
            if "02" in answers:
                try:
                    endpoint_response = self.check_endpoint(answers["02"], "NONOMNISMORIAR")
                    if endpoint_response:
                        answers["05"] = json.dumps(endpoint_response)
                except Exception as e:
                    self.logger.error(f"Błąd podczas sprawdzania endpointu: {e}")
                    answers["05"] = "nie znaleziono"
            
            # Upewnij się, że mamy wszystkie odpowiedzi
            for q_id in ["01", "02", "03", "04", "05", "06"]:
                if q_id not in answers or not answers[q_id]:
                    answers[q_id] = "nie znaleziono"
            
            self.logger.info("\n=== PRZYGOTOWANE ODPOWIEDZI ===")
            for q_id, answer in answers.items():
                self.logger.info(f"Pytanie {q_id}: {answer}")
            
            return answers
            
        except Exception as e:
            self.logger.error(f"Błąd podczas przygotowywania odpowiedzi: {e}")
            if 'response' in locals():
                self.logger.error("Surowa odpowiedź:")
                self.logger.error(response.choices[0].message.content)
            return None

    def submit_answers(self, answers: dict) -> dict:
        """Wysyła odpowiedzi do centrali."""
        try:
            payload = {
                "task": "phone",
                "apikey": self.api_key,
                "answer": answers
            }
            
            # Formatujemy JSON bez spacji
            json_payload = json.dumps(payload, separators=(',', ':'))
            self.logger.info(f"Wysyłam payload: {json_payload}")
            
            # Wysyłamy na właściwy adres raportu
            response = requests.post(
                "https://centrala.ag3nts.org/report",
                data=json_payload,  # Używamy data z JSON-em bez spacji
                headers={'Content-Type': 'application/json'}
            )
            
            response.raise_for_status()
            result = response.json()
            
            self.logger.info(f"Odpowiedź od centrali: {json.dumps(result, indent=2, ensure_ascii=False)}")
            
            if "flag" in result:
                self.logger.info(f"Otrzymano flagę: {result['flag']}")
            else:
                self.logger.warning("Nie otrzymano flagi - odpowiedzi mogą być niepoprawne")
                
            return result
            
        except Exception as e:
            self.logger.error(f"Błąd podczas wysyłania odpowiedzi: {e}")
            self.logger.error(f"Szczegóły błędu: {str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                self.logger.error(f"Odpowiedź serwera: {e.response.text}")
            return None

    def load_reconstructed_conversations(self) -> dict:
        """Wczytuje posortowane rozmowy z pliku."""
        try:
            with open('s05e01/phone_sorted.json', 'r', encoding='utf-8') as f:
                conversations = json.load(f)
            self.logger.info("Wczytano posortowane rozmowy")
            return conversations
        except Exception as e:
            self.logger.error(f"Błąd podczas wczytywania rozmów: {e}")
            return None

    def solve(self):
        """Główna metoda rozwiązująca zadanie."""
        reconstructed = self.load_reconstructed_conversations()
        if not reconstructed:
            return
            
        lie_analysis = self.analyze_lies(reconstructed)
        if not lie_analysis:
            return
        
        max_attempts = 3
        incorrect_questions = set()  # Zbiór błędnych pytań
        
        for attempt in range(max_attempts):
            self.logger.info(f"\nPróba {attempt + 1} z {max_attempts}")
            
            # Modyfikuj prompt na podstawie poprzednich błędów
            extra_hints = """
WAŻNA INFORMACJA:
- Samuel kłamie o sektorze D, więc jego wypowiedzi mogą być niewiarygodne
- Należy szukać potwierdzeń w innych rozmowach i faktach
"""
            
            if "03" in incorrect_questions:
                extra_hints += """
DODATKOWA ANALIZA dla pytania 03:
- W rozmowie 5 ktoś nie lubi być nazywany "nauczycielem"
- W fakcie f05.txt Barbara była związana z Aleksandrem Ragorskim (nauczycielem)
- W fakcie f04.txt Aleksander Ragowski był nauczycielem angielskiego
- Sprawdź dokładnie relację między tymi faktami
"""
            
            if "04" in incorrect_questions:
                extra_hints += """
DODATKOWA ANALIZA dla pytania 04:
- Skoro Samuel kłamie, nie możemy ufać jego wypowiedziom
- Sprawdź rozmowę 1 jeszcze raz, ignorując informacje od Samuela
- Szukaj potwierdzenia uczestników w innych rozmowach
- Zwróć uwagę na to jak osoby się do siebie zwracają
"""
            
            # 3. Przygotowanie odpowiedzi z dodatkowymi wskazówkami
            answers = self.prepare_answers(reconstructed, lie_analysis, extra_hints)
            if not answers:
                continue
                
            # 4. Wysłanie odpowiedzi
            result = self.submit_answers(answers)
            if result and "code" in result:
                if result["code"] == 0:  # Sukces
                    self.logger.info("Zadanie rozwiązane!")
                    return
                elif "message" in result and "incorrect" in result["message"].lower():
                    question_num = result["message"].split("question ")[1][:2]
                    incorrect_questions.add(question_num)
                    self.logger.info(f"Odpowiedź na pytanie {question_num} jest nieprawidłowa. Próbuję ponownie...")
                    continue
            
        self.logger.error(f"Nie udało się rozwiązać zadania po {max_attempts} próbach")

def main():
    analyzer = PhoneAnalyzer()
    analyzer.solve()

if __name__ == "__main__":
    main() 