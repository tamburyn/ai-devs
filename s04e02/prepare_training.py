import json
from pathlib import Path
from typing import List
from openai import OpenAI
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def load_data(filename: str) -> List[List[float]]:
    """Load and parse data from file."""
    file_path = Path(__file__).parent / 'context' / filename
    data = []
    try:
        with open(file_path, 'r') as f:
            for line in f:
                # Convert string numbers to float
                numbers = [float(x) for x in line.strip().split(',')]
                data.append(numbers)
        return data
    except Exception as e:
        print(f"Error loading {filename}: {e}")
        return []

def prepare_jsonl():
    """Prepare training data in JSONL format."""
    # Load data
    correct_data = load_data('correct.txt')
    incorrect_data = load_data('incorrect.txt')
    
    # Create output directory if it doesn't exist
    output_dir = Path(__file__).parent / 'training'
    output_dir.mkdir(exist_ok=True)
    
    # Prepare training data
    training_data = []
    
    # Add correct examples
    for data in correct_data:
        example = {
            "messages": [
                {"role": "system", "content": "validate numbers"},
                {"role": "user", "content": ",".join(map(str, data))},
                {"role": "assistant", "content": "1"}
            ]
        }
        training_data.append(example)
    
    # Add incorrect examples
    for data in incorrect_data:
        example = {
            "messages": [
                {"role": "system", "content": "validate numbers"},
                {"role": "user", "content": ",".join(map(str, data))},
                {"role": "assistant", "content": "0"}
            ]
        }
        training_data.append(example)
    
    # Save to JSONL file
    output_file = output_dir / 'training.jsonl'
    with open(output_file, 'w') as f:
        for item in training_data:
            f.write(json.dumps(item) + '\n')
    
    print(f"Absolute path to training file: {output_file.absolute()}")
    print(f"Created training data file: {output_file}")
    print(f"Total examples: {len(training_data)}")
    print(f"Correct examples: {len(correct_data)}")
    print(f"Incorrect examples: {len(incorrect_data)}")

def prepare_and_upload():
    """Prepare training data and upload to OpenAI."""
    prepare_jsonl()  # Najpierw przygotuj plik
    
    # Użyj bezpośredniej ścieżki
    file_path = "/Users/adrianlewtak/3rd-devs/s04e02/training/training.jsonl"
    
    print(f"Uploading file: {file_path}")
    
    # Upload pliku
    try:
        with open(file_path, 'rb') as f:
            client = OpenAI()  # Upewnij się, że OPENAI_API_KEY jest ustawiony w .env
            response = client.files.create(
                file=f,
                purpose='fine-tune'
            )
        print(f"File uploaded successfully. File ID: {response.id}")
        
        # Od razu utwórz job fine-tuningu
        job = client.fine_tuning.jobs.create(
            training_file=response.id,
            model="gpt-3.5-turbo"
        )
        print(f"Fine-tuning job created: {job.id}")
        return job.id
    except Exception as e:
        print(f"Error: {e}")
        return None

if __name__ == "__main__":
    file_id = prepare_and_upload()
    if file_id:
        print("\nTo create fine-tuning job, run:")
        print(f"openai api fine_tuning.create -t {file_id} -m gpt-3.5-turbo") 