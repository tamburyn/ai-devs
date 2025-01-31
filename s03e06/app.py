import requests
import json
import logging
from typing import Dict, List
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
        load_dotenv()
        
        # Initialize OpenAI
        self.openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        
        # API configuration
        self.api_key = "95e20ae1-e5a4-4a45-9350-f0b71ec099ce"
        self.base_url = "https://centrala.ag3nts.org"
        self.phone_data_url = f"{self.base_url}/data/{self.api_key}/phone.json"
        self.questions_url = f"{self.base_url}/data/{self.api_key}/phone_questions.json"
        self.report_url = f"{self.base_url}/report"

        # Load facts
        self.facts = self.load_facts()
        
        # Store conversations and analysis
        self.conversations = {}
        self.questions = {}
        self.analysis = {}

    def load_facts(self) -> Dict[str, str]:
        """Load facts from the facts folder."""
        facts = {}
        facts_dir = "s05e01/pliki_z_fabryki/facts"
        
        try:
            for filename in os.listdir(facts_dir):
                if filename.endswith(".txt"):
                    with open(os.path.join(facts_dir, filename), 'r', encoding='utf-8') as f:
                        facts[filename] = f.read()
            self.logger.info(f"Loaded {len(facts)} fact files")
            return facts
        except Exception as e:
            self.logger.error(f"Error loading facts: {e}")
            return {}

    def get_phone_data(self) -> bool:
        """Fetch phone conversation data from API."""
        try:
            response = requests.get(self.phone_data_url)
            response.raise_for_status()
            self.conversations = response.json()
            self.logger.info("Successfully fetched phone data")
            return True
        except Exception as e:
            self.logger.error(f"Error fetching phone data: {e}")
            return False

    def get_questions(self) -> bool:
        """Fetch questions from API."""
        try:
            response = requests.get(self.questions_url)
            response.raise_for_status()
            self.questions = response.json()
            self.logger.info("Successfully fetched questions")
            return True
        except Exception as e:
            self.logger.error(f"Error fetching questions: {e}")
            return False

    def analyze_conversations(self):
        """Analyze conversations using LLM."""
        prompt = """Przeanalizuj poniższe rozmowy i odpowiedz na następujące pytania:
1. Kim są rozmówcy?
2. Jakie są główne tematy rozmów?
3. Czy ktoś kłamie lub wprowadza w błąd?
4. Jakie są powiązania między osobami?

Rozmowy:
{conversations}

Znane fakty:
{facts}

Odpowiedz w formacie JSON:
{
    "participants": {{"name": "opis roli i powiązań"}},
    "main_topics": ["temat1", "temat2"],
    "suspicious_behavior": ["podejrzane zachowanie1"],
    "connections": ["powiązanie1", "powiązanie2"]
}"""

        try:
            conversations_text = json.dumps(self.conversations, indent=2, ensure_ascii=False)
            facts_text = "\n\n".join(self.facts.values())
            
            response = self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "Jesteś analitykiem śledczym analizującym transkrypcje rozmów."},
                    {"role": "user", "content": prompt.format(
                        conversations=conversations_text,
                        facts=facts_text
                    )}
                ]
            )
            
            self.analysis = json.loads(response.choices[0].message.content)
            self.logger.info("Conversation analysis completed")
            self.logger.info(f"Analysis results: {json.dumps(self.analysis, indent=2, ensure_ascii=False)}")
            
        except Exception as e:
            self.logger.error(f"Error analyzing conversations: {e}")

    def prepare_answers(self) -> Dict[str, str]:
        """Prepare answers to questions based on analysis."""
        prompt = """Na podstawie analizy rozmów i faktów, odpowiedz na następujące pytania:

Analiza:
{analysis}

Pytania:
{questions}

Odpowiedz krótko i zwięźle w formacie JSON:
{{
    "01": "odpowiedź1",
    "02": "odpowiedź2",
    ...
}}"""

        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "Jesteś analitykiem odpowiadającym na pytania na podstawie analizy rozmów."},
                    {"role": "user", "content": prompt.format(
                        analysis=json.dumps(self.analysis, indent=2, ensure_ascii=False),
                        questions=json.dumps(self.questions, indent=2, ensure_ascii=False)
                    )}
                ]
            )
            
            answers = json.loads(response.choices[0].message.content)
            self.logger.info(f"Prepared answers: {json.dumps(answers, indent=2, ensure_ascii=False)}")
            return answers
            
        except Exception as e:
            self.logger.error(f"Error preparing answers: {e}")
            return {}

    def submit_answers(self, answers: Dict[str, str]) -> Dict:
        """Submit answers to the central system."""
        payload = {
            "task": "phone",
            "apikey": self.api_key,
            "answer": answers
        }
        
        try:
            response = requests.post(
                self.report_url,
                json=payload
            )
            result = response.json()
            self.logger.info(f"Submit response: {result}")
            return result
        except Exception as e:
            self.logger.error(f"Error submitting answers: {e}")
            return {}

    def solve(self):
        """Main solving method."""
        try:
            # Get data
            if not self.get_phone_data():
                return
            if not self.get_questions():
                return
                
            # Analyze conversations
            self.analyze_conversations()
            
            # Prepare answers
            answers = self.prepare_answers()
            
            # Submit answers
            if answers:
                response = self.submit_answers(answers)
                if "flag" in response:
                    self.logger.info(f"Successfully solved! Flag: {response['flag']}")
                else:
                    self.logger.info("No flag in response. Answers might be incorrect.")
            
        except Exception as e:
            self.logger.error(f"An error occurred: {str(e)}", exc_info=True)

def main():
    analyzer = PhoneAnalyzer()
    analyzer.solve()

if __name__ == "__main__":
    main() 