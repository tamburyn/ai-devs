import requests
import json
import logging
from typing import Set, List

class BarbaraFinder:
    def __init__(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
        
        # Initialize API endpoints and key
        self.api_key = "95e20ae1-e5a4-4a45-9350-f0b71ec099ce"
        self.base_url = "https://centrala.ag3nts.org"
        self.people_url = f"{self.base_url}/people"
        self.places_url = f"{self.base_url}/places"
        self.report_url = f"{self.base_url}/report"
        
        # Sets to keep track of discovered data
        self.discovered_people = set()
        self.discovered_places = set()
        self.checked_items = set()

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
            return response.json()
        except Exception as e:
            self.logger.error(f"API error for query '{query}': {e}")
            return {}

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

    def solve(self):
        """Main solving method."""
        try:
            # Get and analyze Barbara's note
            note = self.get_barbara_note()
            self.logger.info(f"Retrieved note:\n{note}")
            
            # Start with Barbara
            self.discovered_people.add("BARBARA")
            
            while True:
                initial_size = len(self.checked_items)
                
                # Check all discovered people
                for person in list(self.discovered_people):
                    places = self.search_person(person)
                    if "BARBARA" in self.search_place(next(iter(places))) if places else set():
                        self.logger.info(f"Found Barbara in {next(iter(places))}!")
                        self.submit_answer(next(iter(places)))
                        return
                
                # Check all discovered places
                for place in list(self.discovered_places):
                    self.search_place(place)
                
                # If no new items were discovered, break
                if len(self.checked_items) == initial_size:
                    self.logger.info("No new information found.")
                    break

            self.logger.info("Search completed without finding Barbara's location.")
            
        except Exception as e:
            self.logger.error(f"An error occurred: {str(e)}", exc_info=True)

def main():
    finder = BarbaraFinder()
    finder.solve()

if __name__ == "__main__":
    main() 