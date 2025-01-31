import os
import requests
from openai import OpenAI
from dotenv import load_dotenv
import json
from datetime import datetime
import zipfile
import io

# Load environment variables
load_dotenv()

def log_step(step: str, message: str):
    """Helper function for consistent logging"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n[{timestamp}] {step}")
    print("-" * 50)
    print(message)
    print("-" * 50)

class ResearchValidator:
    def __init__(self):
        self.base_url = "https://centrala.ag3nts.org"
        self.api_key = os.getenv("API_KEY", "95e20ae1-e5a4-4a45-9350-f0b71ec099ce")
        self.data_url = "https://centrala.ag3nts.org/dane/lab_data.zip"
        self.report_url = f"{self.base_url}/report"
        self.client = OpenAI()
        self.model_id = "ft:gpt-3.5-turbo-0125:tambu:research:AnYFGb1B"  # Nowy model
        
        log_step("Initialization", f"""
Base URL: {self.base_url}
Data URL: {self.data_url}
Report URL: {self.report_url}
Model: {self.model_id}
""")

    def get_research_data(self) -> list:
        """Download and extract research data"""
        log_step("Fetching Data", f"Downloading from {self.data_url}")
        
        try:
            response = requests.get(self.data_url)
            response.raise_for_status()
            
            # Extract ZIP content
            with zipfile.ZipFile(io.BytesIO(response.content)) as zip_ref:
                # Read verify.txt from ZIP
                with zip_ref.open('verify.txt') as f:
                    samples = [line.decode('utf-8').strip() for line in f.readlines()]
            
            log_step("Data Received", f"""
Status Code: {response.status_code}
Samples count: {len(samples)}
First few samples:
{json.dumps(samples[:3], indent=2)}
""")
            return samples
            
        except Exception as e:
            log_step("Error", f"Failed to fetch data: {str(e)}")
            return []

    def validate_sample(self, sample: str) -> bool:
        """Validate research sample using fine-tuned model"""
        log_step("Validating Sample", f"Processing: {sample}")
        
        try:
            response = self.client.chat.completions.create(
                model=self.model_id,
                messages=[
                    {"role": "system", "content": "validate research sample"},
                    {"role": "user", "content": sample}
                ],
                temperature=0
            )
            
            result = response.choices[0].message.content
            valid = result.strip() == "1"
            
            log_step("Validation Result", f"""
Sample: {sample}
Model response: {result}
Valid: {valid}
""")
            return valid
            
        except Exception as e:
            log_step("Error", f"Validation failed: {str(e)}")
            return False

    def send_report(self, valid_ids: list) -> bool:
        """Send validation results to API"""
        try:
            # Konwertuj ID na format dwucyfrowy z wiodącym zerem
            formatted_ids = []
            for id_str in valid_ids:
                # Upewnij się, że ID jest poprawne i dodaj wiodące zero jeśli potrzeba
                if id_str.isdigit():
                    formatted_ids.append(f"{int(id_str):02d}")
            
            payload = {
                "task": "research",
                "apikey": self.api_key,
                "answer": formatted_ids  # Lista stringów w formacie "01", "02", etc.
            }

            log_step("Sending Report", f"""
Sending POST request to {self.report_url}
Payload:
{json.dumps(payload, indent=2)}
""")

            response = requests.post(
                self.report_url,
                json=payload
            )
            response.raise_for_status()
            
            log_step("Report Sent", f"""
Status Code: {response.status_code}
Response:
{json.dumps(response.json(), indent=2)}
""")
            return True
            
        except Exception as e:
            error_msg = f"Failed to send report: {str(e)}"
            if hasattr(e, 'response'):
                error_msg += f"\nStatus code: {e.response.status_code}"
                error_msg += f"\nResponse text: {e.response.text}"
            log_step("Error", error_msg)
            return False

    def extract_id(self, sample: str) -> str:
        """Extract ID from sample line"""
        try:
            # Format danych to "XX=YY,..." gdzie XX to ID linii
            id_part = sample.split('=')[0]  # Weź część przed '='
            return id_part.strip()  # Usuń whitespace
        except Exception as e:
            log_step("Error", f"Failed to extract ID from sample: {sample}")
            return ""

    def process_all(self):
        """Main processing function"""
        log_step("Processing Started", "Beginning research validation...")
        
        # Get research data
        samples = self.get_research_data()
        if not samples:
            log_step("Error", "No samples to process")
            return

        # Validate samples and collect valid IDs
        valid_ids = []
        for sample in samples:
            if self.validate_sample(sample):
                sample_id = self.extract_id(sample)
                if sample_id:
                    valid_ids.append(sample_id)

        # Send report
        if valid_ids:
            success = self.send_report(valid_ids)
            
            log_step("Processing Completed", f"""
Total samples processed: {len(samples)}
Valid samples: {len(valid_ids)}
Invalid samples: {len(samples) - len(valid_ids)}
Valid IDs: {json.dumps(valid_ids, indent=2)}
Report sent: {'Success' if success else 'Failed'}
""")

def main():
    try:
        validator = ResearchValidator()
        validator.process_all()
    except Exception as e:
        log_step("Fatal Error", f"Application crashed: {str(e)}")

if __name__ == "__main__":
    main()
