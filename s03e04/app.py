import requests
import json
import logging
from typing import Set, List, Dict, Tuple
from openai import OpenAI
import os
from datetime import datetime

class BarbaraFinderAI:
    def __init__(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(f'barbara_search_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
        # Initialize APIs
        self.api_key = "95e20ae1-e5a4-4a45-9350-f0b71ec099ce"
        self.base_url = "https://centrala.ag3nts.org"
        self.people_url = f"{self.base_url}/people"
        self.places_url = f"{self.base_url}/places"
        self.report_url = f"{self.base_url}/report"
        
        # Initialize OpenAI
        self.openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        
        # Initialize tracking sets and knowledge base
        self.discovered_people = set()
        self.discovered_places = set()
        self.checked_items = set()
        self.knowledge_base = {
            "notes": [],
            "connections": [],
            "locations": {},
            "people": {}
        }

    def analyze_note(self, note: str) -> None:
        """Analyze Barbara's note using LLM."""
        prompt = """Przeanalizuj notatkę i wyodrębnij:
1. Wszystkie wspomniane osoby (imiona w mianowniku, bez polskich znaków)
2. Wszystkie wspomniane miejsca (bez polskich znaków)
3. Chronologię wydarzeń
4. Kluczowe powiązania między osobami

Format odpowiedzi (JSON):
{
    "people": ["IMIE1", "IMIE2"],
    "places": ["MIASTO1", "MIASTO2"],
    "timeline": [
        {"year": "2019", "event": "opis"},
        {"year": "2021", "event": "opis"}
    ],
    "connections": [
        {"person1": "OSOBA1", "person2": "OSOBA2", "relationship": "opis"}
    ]
}

Pamiętaj:
- Imiona muszą być w mianowniku (ALEKSANDER nie ALEKSANDREM)
- Bez polskich znaków (RAFAL nie RAFAŁ)
- Wszystkie nazwy wielkimi literami
- Tylko konkretne, wymienione informacje

Notatka do analizy:
{text}"""
        
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are an intelligence analyst. Extract information from the note and return it in JSON format."},
                    {"role": "user", "content": prompt.format(text=note)}
                ]
            )
            
            # Próbujemy sparsować odpowiedź jako JSON
            try:
                analysis = json.loads(response.choices[0].message.content)
                self.logger.info(f"Note analysis: {json.dumps(analysis, indent=2)}")
                
                # Dodaj znalezione osoby i miejsca do zbiorów do sprawdzenia
                if "people" in analysis:
                    self.discovered_people.update(set(analysis["people"]))
                    self.logger.info(f"Discovered people: {self.discovered_people}")
                
                if "places" in analysis:
                    self.discovered_places.update(set(analysis["places"]))
                    self.logger.info(f"Discovered places: {self.discovered_places}")
                
                # Zaktualizuj bazę wiedzy
                self.knowledge_base["notes"].append({
                    "source": "barbara_note",
                    "analysis": analysis
                })
                
            except json.JSONDecodeError as e:
                self.logger.error(f"Failed to parse JSON response: {response.choices[0].message.content}")
                self.logger.error(f"JSON error: {str(e)}")
                
                # Spróbujmy ręcznie wydobyć osoby i miejsca z tekstu odpowiedzi
                content = response.choices[0].message.content
                if '"people"' in content and '"places"' in content:
                    try:
                        # Wyciągnij sekcję people
                        people_start = content.find('"people"') + len('"people"')
                        people_end = content.find(']', people_start) + 1
                        people_json = content[people_start:people_end].strip().strip(':')
                        people = json.loads(people_json)
                        self.discovered_people.update(set(people))
                        self.logger.info(f"Manually extracted people: {people}")
                        
                        # Wyciągnij sekcję places
                        places_start = content.find('"places"') + len('"places"')
                        places_end = content.find(']', places_start) + 1
                        places_json = content[places_start:places_end].strip().strip(':')
                        places = json.loads(places_json)
                        self.discovered_places.update(set(places))
                        self.logger.info(f"Manually extracted places: {places}")
                    except Exception as e:
                        self.logger.error(f"Manual extraction failed: {str(e)}")
                        
                        # Ostateczna próba - proste wydobycie z tekstu
                        self.discovered_people.update({"BARBARA", "ALEKSANDER", "ANDRZEJ", "RAFAL"})
                        self.discovered_places.update({"KRAKOW", "WARSZAWA"})
                        self.logger.info("Added hardcoded initial set of people and places")
            
        except Exception as e:
            self.logger.error(f"Error during note analysis: {str(e)}")
            # Dodaj podstawowy zestaw osób i miejsc jako zabezpieczenie
            self.discovered_people.update({"BARBARA", "ALEKSANDER", "ANDRZEJ", "RAFAL"})
            self.discovered_places.update({"KRAKOW", "WARSZAWA"})
            self.logger.info("Added hardcoded initial set of people and places as fallback")

    def get_barbara_note(self) -> str:
        """Download and read Barbara's note."""
        try:
            response = requests.get(f"{self.base_url}/dane/barbara.txt")
            response.raise_for_status()
            return response.text
        except Exception as e:
            self.logger.error(f"Error downloading Barbara's note: {e}")
            return ""

    def query_api(self, endpoint: str, query: str) -> dict:
        """Make API request to specified endpoint."""
        payload = {
            "apikey": self.api_key,
            "query": query
        }
        
        try:
            response = requests.post(endpoint, json=payload)
            response.raise_for_status()
            result = response.json()
            
            # Jeśli otrzymaliśmy odpowiedź z message, przekonwertuj ją na listę
            if "message" in result:
                if result["message"] == "[**RESTRICTED DATA**]":
                    return {"reply": []}  # Pusta lista dla zastrzeżonych danych
                else:
                    # Zakładamy, że message zawiera listę imion/miejsc oddzielonych spacją
                    return {"reply": result["message"].split()}
            return result
        except Exception as e:
            self.logger.error(f"API error for query '{query}': {e}")
            return {"reply": []}

    def check_for_flag(self, data: dict) -> None:
        """Check response for hidden flag."""
        data_str = json.dumps(data)
        if "FLG:" in data_str:
            self.logger.info(f"!!! FOUND FLAG IN RESPONSE: {data_str} !!!")

    def search_person(self, name: str) -> Set[str]:
        """Search for places where person was seen."""
        if name in self.checked_items:
            return set()
            
        self.logger.info(f"Searching for person: {name}")
        result = self.query_api(self.people_url, name)
        self.check_for_flag(result)
        
        places = set()
        if "reply" in result:
            places = set(result["reply"])
            self.discovered_places.update(places)
            
        self.checked_items.add(name)
        return places

    def search_place(self, place: str) -> Set[str]:
        """Search for people seen in given place."""
        if place in self.checked_items:
            return set()
            
        self.logger.info(f"Searching place: {place}")
        result = self.query_api(self.places_url, place)
        self.check_for_flag(result)
        
        people = set()
        if "reply" in result:
            people = set(result["reply"])
            self.discovered_people.update(people)
            
            # Jeśli znaleźliśmy Barbarę, od razu wysyłamy odpowiedź
            if "BARBARA" in people:
                self.logger.info(f"Found Barbara in {place}!")
                response = self.submit_answer(place)
                self.logger.info(f"Submit response: {response}")
            
        self.checked_items.add(place)
        return people

    def submit_answer(self, city: str) -> dict:
        """Submit found city to the central system."""
        payload = {
            "task": "loop",
            "apikey": self.api_key,
            "answer": city
        }
        
        try:
            response = requests.post(
                self.report_url,
                data=json.dumps(payload, separators=(',', ':')),
                headers={'Content-Type': 'application/json'}
            )
            result = response.json()
            self.check_for_flag(result)
            return result
        except Exception as e:
            self.logger.error(f"Error submitting answer: {e}")
            return {}

    def analyze_connections_with_llm(self) -> List[str]:
        """Use LLM to analyze connections and suggest next places to check."""
        knowledge_summary = {
            "discovered_people": list(self.discovered_people),
            "discovered_places": list(self.discovered_places),
            "checked_items": list(self.checked_items),
            "knowledge_base": self.knowledge_base
        }
        
        prompt = f"""Analizując zebrane informacje:
{json.dumps(knowledge_summary, indent=2)}

Pomóż znaleźć Barbarę:
1. Przeanalizuj powiązania między osobami
2. Sprawdź wzorce w odwiedzanych miejscach
3. Zasugeruj najbardziej prawdopodobne miejsca, gdzie może być Barbara

Zwróć odpowiedź w formacie JSON:
{{
    "analysis": "twoja analiza sytuacji",
    "suggested_places": ["MIASTO1", "MIASTO2"],
    "reasoning": "wyjaśnienie dlaczego te miejsca"
}}

Pamiętaj:
- Nazwy miast bez polskich znaków i wielkimi literami
- Uwzględnij miejsca, których jeszcze nie sprawdziliśmy
- Skup się na powiązaniach między osobami"""

        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "Jesteś analitykiem pomagającym znaleźć Barbarę. Analizujesz powiązania i wzorce."},
                    {"role": "user", "content": prompt}
                ]
            )
            
            try:
                analysis = json.loads(response.choices[0].message.content)
                self.logger.info(f"LLM Analysis: {json.dumps(analysis, indent=2)}")
                return analysis.get("suggested_places", [])
            except json.JSONDecodeError:
                self.logger.error("Failed to parse LLM response")
                return []
            
        except Exception as e:
            self.logger.error(f"Error during LLM analysis: {e}")
            return []

    def execute_search_loop(self) -> bool:
        """Execute main search loop until Barbara is found."""
        iteration = 0
        max_iterations = 50  # Zabezpieczenie przed nieskończoną pętlą
        
        while iteration < max_iterations:
            self.logger.info(f"\nIteration {iteration + 1}")
            initial_people = set(self.discovered_people)
            initial_places = set(self.discovered_places)
            
            # Użyj LLM do analizy i sugestii miejsc
            suggested_places = self.analyze_connections_with_llm()
            self.logger.info(f"LLM suggested places to check: {suggested_places}")
            
            # Najpierw sprawdź sugerowane miejsca
            for place in suggested_places:
                if place not in self.checked_items:
                    self.logger.info(f"Checking LLM-suggested place: {place}")
                    new_people = self.search_place(place)
                    if "BARBARA" in new_people:
                        response = self.submit_answer(place)
                        if "Bad answer" not in response.get("message", ""):
                            self.logger.info(f"Successfully found Barbara in {place}!")
                            return True
            
            # Sprawdź wszystkie nowe osoby
            for person in list(self.discovered_people - self.checked_items):
                self.logger.info(f"Checking person: {person}")
                new_places = self.search_person(person)
                
                # Sprawdź każde nowe miejsce od razu
                for place in new_places:
                    if place not in self.checked_items:
                        new_people = self.search_place(place)
                        if "BARBARA" in new_people:
                            response = self.submit_answer(place)
                            if "Bad answer" not in response.get("message", ""):
                                self.logger.info(f"Successfully found Barbara in {place}!")
                                return True
            
            # Sprawdź pozostałe nowe miejsca
            for place in list(self.discovered_places - self.checked_items):
                self.logger.info(f"Checking place: {place}")
                new_people = self.search_place(place)
                if "BARBARA" in new_people:
                    response = self.submit_answer(place)
                    if "Bad answer" not in response.get("message", ""):
                        self.logger.info(f"Successfully found Barbara in {place}!")
                        return True
            
            # Sprawdź czy znaleźliśmy coś nowego
            if (len(self.discovered_people) == len(initial_people) and 
                len(self.discovered_places) == len(initial_places)):
                self.logger.info("No new information found.")
                break
            
            self.logger.info(f"Current discovered people: {self.discovered_people}")
            self.logger.info(f"Current discovered places: {self.discovered_places}")
            
            iteration += 1
        
        self.logger.info("Search completed without finding Barbara's true location.")
        return False

    def solve(self):
        """Main solving method."""
        try:
            # Get and analyze Barbara's note
            note = self.get_barbara_note()
            self.logger.info(f"Retrieved note:\n{note}")
            self.analyze_note(note)
            
            # Start search loop
            if self.execute_search_loop():
                self.logger.info("Search completed successfully!")
            else:
                self.logger.info("Search completed without finding Barbara.")
            
        except Exception as e:
            self.logger.error(f"An error occurred: {str(e)}", exc_info=True)

def main():
    finder = BarbaraFinderAI()
    finder.solve()

if __name__ == "__main__":
    main() 