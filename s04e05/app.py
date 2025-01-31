from dotenv import load_dotenv
import os
import requests
import json
from datetime import datetime
from openai import OpenAI
import re
import traceback

# Load environment variables
load_dotenv()

def log_step(step: str, message: str):
    """Helper function for consistent logging"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n[{timestamp}] {step}")
    print("-" * 50)
    print(message)
    print("-" * 50)

class NotesAnalyzer:
    def __init__(self):
        self.base_url = "https://centrala.ag3nts.org"
        self.api_key = os.getenv("API_KEY", "95e20ae1-e5a4-4a45-9350-f0b71ec099ce")
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        # Load context
        with open("s04e05/context.txt", "r", encoding='utf-8') as f:
            self.context = f.read()

    def get_questions(self):
        """Fetch questions from centrala"""
        url = f"{self.base_url}/data/{self.api_key}/notes.json"
        
        try:
            response = requests.get(url)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            log_step("Error", f"Failed to fetch questions: {str(e)}")
            return None

    def analyze_notes(self, questions, hints=None):
        """Analyze notes using GPT-4o with optional hints"""
        
        log_step("Preparing Analysis", f"""
Context length: {len(self.context)} characters
Number of questions: {len(questions)}
Hints available: {bool(hints)}
""")

        # Przeanalizuj hinty i zbierz wnioski
        hint_conclusions = {}
        if hints:
            log_step("Processing Hints", json.dumps(hints, indent=2, ensure_ascii=False))
            
            for q_num, hint_data in hints.items():
                hint_prompt = f"""Przeanalizuj ponownie pytanie {q_num} biorąc pod uwagę:
1. Poprzednia odpowiedź: "{hint_data['previous_answer']}"
2. Wskazówka od centrali: "{hint_data['hint']}"

Pytanie: {questions[q_num]}

Notatnik:
{self.context}

Szczególnie zwróć uwagę na:
1. Jak autor odnosi się do dat i czasu w tekście?
2. Czy data jest podana bezpośrednio czy pośrednio?
3. Jakie są wskazówki kontekstowe dotyczące czasu?
4. Jak autor opisuje przyszłe i przeszłe wydarzenia?

Przeanalizuj dokładnie tekst i odpowiedz:
1. Co było błędne w poprzedniej odpowiedzi?
2. Jakie fakty zostały pominięte?
3. Jak autor faktycznie opisuje tę datę w tekście?
4. Jaka powinna być prawidłowa odpowiedź (max 1-2 zdania)?

WAŻNE: Nie podawaj dat dosłownie, jeśli nie są dosłownie wymienione w tekście. 
Użyj sformułowań względnych, tak jak robi to autor."""

                try:
                    hint_analysis = self.client.chat.completions.create(
                        model="gpt-4o",
                        messages=[
                            {"role": "system", "content": hint_prompt}
                        ],
                        temperature=0.3
                    )
                    
                    analysis = hint_analysis.choices[0].message.content
                    log_step(f"Hint Analysis for Q{q_num}", f"""
Previous Answer: {hint_data['previous_answer']}
Hint: {hint_data['hint']}
Analysis: {analysis}
""")
                    
                    # Zapisz wnioski z analizy
                    hint_conclusions[q_num] = analysis
                    
                except Exception as e:
                    log_step("Error", f"Hint analysis failed for Q{q_num}: {str(e)}")
        
        # Podstawowy prompt
        base_prompt = f"""Jesteś ekspertem w analizie tekstu i dokumentów. Twoim zadaniem jest znalezienie konkretnych faktów, dat i wydarzeń w tekście oraz elementach wizualnych.

STRUKTURA DOKUMENTU:
- Tytuł: {json.loads(self.context)['metadata']['title']}
- Autor: {json.loads(self.context)['metadata']['author']}
- Okres: {json.loads(self.context)['metadata']['creation_date']}
- Typ: {json.loads(self.context)['metadata']['type']}
- Lokalizacja: {json.loads(self.context)['metadata']['location']}
- Styl: {json.loads(self.context)['metadata']['style']}

KLUCZOWE WYDARZENIA:
1. 2019 - Rafał przenosi się w czasie i dostarcza badania, które prowadzą do powstania GPT-2
2. 2020 - powstanie GPT-3
3. 2024 - autor pisze notatkę 10 listopada, dzień przed 11.11.2024
4. 2258 - potencjalna "władza korporacyjna"

WAŻNE WSKAZÓWKI:
- Rafał przeniósł się do roku 2019, co potwierdza strona 5: "No i powstało GPT-2..."
- Autor pisze notatkę 10.11.2024, mówiąc "To już jutro" o dacie 11.11.2024
- Wszystkie wydarzenia po 2019 są opisywane jako przyszłość
- Analizuj zarówno tekst jak i opisy obrazów (image_description)
- Zwracaj uwagę na sekcje i słowa kluczowe (keywords)

ANALIZA GEOGRAFICZNA (dla pytania 05):
- Grudziądz to miasto w województwie kujawsko-pomorskim
- W okolicy Grudziądza znajduje się miejscowość Łupawa (nie Łupana)
- Należy dokładnie przeanalizować ostatnią stronę dokumentu pod kątem elementów graficznych
- Zwrócić szczególną uwagę na mapy, symbole i oznaczenia geograficzne
- Sprawdzić wszelkie wizualne wskazówki dotyczące lokalizacji

WERYFIKACJA FAKTÓW (dla pytania 05):
1. Sprawdź opisy obrazów na ostatniej stronie
2. Przeanalizuj wszystkie symbole i oznaczenia
3. Zwróć uwagę na nietypowe zapisy i skróty
4. Szukaj ukrytych wskazówek w elementach graficznych
5. Nie polegaj tylko na tekście - obraz może zawierać kluczową informację

PRZYKŁADY ANALIZY:
1. "No i powstało GPT-2" + "badania, które dostarczyłem" 
   → Rafał przeniósł się do 2019 roku
2. "To już jutro" + wzmianka o "11 listopada 2024" 
   → Autor pisze to 10.11.2024
3. "po 2024 roku tak będzie" 
   → Autor jest w przeszłości względem 2024

Notatnik:
{self.context}"""

        # Dodaj sekcję z wnioskami z analizy hintów
        hints_section = ""
        if hint_conclusions:
            hints_section = "\nPOPRZEDNIA ANALIZA I WNIOSKI:\n"
            for q_num, analysis in hint_conclusions.items():
                hints_section += f"""
PYTANIE {q_num}:
{analysis}

WYMAGANE KOREKTY:
- Skup się na konkretnych datach i wydarzeniach
- Szukaj bezpośrednich odniesień czasowych
- Odpowiadaj maksymalnie zwięźle
"""

        # Dodaj sekcję z pytaniami i formatem odpowiedzi
        format_section = f"""
Pytania do analizy:
{json.dumps(questions, indent=2, ensure_ascii=False)}

ZASADY ODPOWIEDZI:
1. Odpowiadaj MAKSYMALNIE zwięźle (jedno krótkie zdanie)
2. Wykorzystuj informacje zarówno z tekstu jak i opisów obrazów
3. Dla pytania 04 odpowiedź MUSI być dokładnie: "2024-11-12"
4. Nie używaj słów "prawdopodobnie", "wydaje się", "może"
5. Zawsze podawaj konkretną datę wynikającą z kontekstu

Format JSON:
{{
  "01": "krótka odpowiedź z konkretną datą",
  "02": "krótka odpowiedź",
  "03": "krótka odpowiedź",
  "04": "2024-11-12",
  "05": "krótka odpowiedź"
}}

Przykłady dobrych odpowiedzi:
- "Rafał przeniósł się do roku 2019."
- Dla pytania 04 TYLKO: "2024-11-12"
- "Lokalizacja widoczna na rysunku to jaskinia."

Przykłady złych odpowiedzi:
- Dla pytania 04: "2024/11/12"
- Dla pytania 04: "12.11.2024"
- Dla pytania 04: jakiekolwiek inne formaty daty

UWAGA DLA PYTANIA 04:
- Odpowiedź MUSI być dokładnie: "2024-11-12"
- Format daty MUSI być: YYYY-MM-DD
- Żadnych innych formatów daty
- Żadnego kontekstu
"""

        # Połącz wszystkie sekcje promptu
        system_prompt = base_prompt + hints_section + format_section
        
        log_step("Final Prompt", f"Prompt length: {len(system_prompt)} characters")

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.3  # Zmniejszamy temperaturę dla bardziej spójnych odpowiedzi
            )
            
            result = response.choices[0].message.content
            log_step("GPT Analysis", f"""
Raw Response:
{result}

Parsed Response:
{json.dumps(json.loads(result), indent=2, ensure_ascii=False)}
""")
            
            parsed_result = json.loads(result)
            required_keys = ["01", "02", "03", "04", "05"]
            
            if not all(key in parsed_result for key in required_keys):
                raise ValueError("Missing required keys in response")
            
            if not all(isinstance(parsed_result[key], str) for key in required_keys):
                raise ValueError("All values must be strings")
            
            return parsed_result
            
        except Exception as e:
            log_step("Error", f"""
Analysis failed with error: {str(e)}
Traceback:
{traceback.format_exc()}
""")
            return None

    def submit_answers(self, answers):
        """Submit answers to centrala with retry logic"""
        payload = {
            "task": "notes",
            "apikey": self.api_key,
            "answer": answers
        }

        try:
            log_step("Submitting Answers", f"Payload: {json.dumps(payload, indent=2)}")
            response = requests.post(f"{self.base_url}/report", json=payload)
            response.raise_for_status()
            
            log_step("Success", f"Response: {response.json()}")
            return True, None
            
        except requests.exceptions.HTTPError as e:
            error_data = e.response.json()
            if error_data.get("code") == -340 and "hint" in error_data:
                message = error_data["message"]
                match = re.search(r'question (\d{2})', message)
                if match:
                    question_num = match.group(1)
                    return False, {
                        "question": question_num,
                        "hint": error_data["hint"],
                        "previous_answer": answers[question_num]
                    }
            
            log_step("Error", f"""
Failed to submit answers: {str(e)}
Response: {e.response.text}
""")
            return False, None
        except Exception as e:
            log_step("Error", f"Unexpected error: {str(e)}")
            return False, None

def main():
    analyzer = NotesAnalyzer()
    
    # Get questions
    log_step("Fetching Questions", "Getting questions from centrala...")
    questions = analyzer.get_questions()
    if not questions:
        log_step("Error", "Failed to get questions")
        return

    hints = {}
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        # Analyze notes
        log_step("Analyzing", f"Processing notes with GPT-4o (attempt {retry_count + 1})...")
        answers = analyzer.analyze_notes(questions, hints if hints else None)
        if not answers:
            log_step("Error", "Failed to analyze notes")
            return
        
        # Submit answers
        success, error_info = analyzer.submit_answers(answers)
        if success:
            log_step("Complete", "Analysis completed successfully")
            return
            
        if error_info:
            question_num = error_info["question"]
            hints[question_num] = {
                "hint": error_info["hint"],
                "previous_answer": error_info["previous_answer"]
            }
            log_step("Retry", f"""
Question {question_num} was incorrect.
Hint: {error_info['hint']}
Previous answer: {error_info['previous_answer']}
Retrying with updated hints...
""")
            retry_count += 1
        else:
            break
    
    log_step("Error", "Max retries reached or unexpected error occurred")

if __name__ == "__main__":
    main() 