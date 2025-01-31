import os
from openai import OpenAI
from dotenv import load_dotenv
from datetime import datetime

# Load environment variables
load_dotenv()

def log_step(step: str, message: str):
    """Helper function for consistent logging"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n[{timestamp}] {step}")
    print("-" * 50)
    print(message)
    print("-" * 50)

def start_fine_tuning():
    """Start fine-tuning process for research model"""
    client = OpenAI()
    
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        training_file = os.path.join(script_dir, 'training', 'research_training.jsonl')
        
        # Upload the training file
        with open(training_file, 'rb') as f:
            upload_response = client.files.create(
                file=f,
                purpose='fine-tune'
            )
        
        log_step("File Upload", f"""
File ID: {upload_response.id}
Filename: {upload_response.filename}
Status: {upload_response.status}
""")

        # Start fine-tuning
        job = client.fine_tuning.jobs.create(
            training_file=upload_response.id,
            model="gpt-3.5-turbo-0125",
            suffix="research"
        )
        
        log_step("Fine-tuning Started", f"""
Job ID: {job.id}
Model: {job.model}
Status: {job.status}
Created at: {job.created_at}
""")

    except Exception as e:
        log_step("Error", f"Failed to start fine-tuning: {str(e)}")

if __name__ == "__main__":
    start_fine_tuning() 