from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI()

# ID twojego joba
job_id = "ftjob-4ShI7F54bIJjB2dubDctvCRF"

# Sprawdź status
job = client.fine_tuning.jobs.retrieve(job_id)
print(f"Status: {job.status}")

# Jeśli job jest zakończony, pokaż nazwę modelu
if job.status == "succeeded":
    print(f"Fine-tuned model: {job.fine_tuned_model}") 