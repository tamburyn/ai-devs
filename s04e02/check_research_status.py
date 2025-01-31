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

def check_fine_tuning_status():
    """Check status of research model fine-tuning"""
    client = OpenAI()
    
    try:
        # Get list of fine-tuning jobs
        jobs = client.fine_tuning.jobs.list(limit=10)
        
        # Find the most recent research job (checking by ID from previous run)
        latest_job = None
        for job in jobs:
            if job.id == "ftjob-qAOLCOoxdkFRfvqeRlhvGbiN":  # ID from your previous run
                latest_job = job
                break
        
        if not latest_job:
            log_step("Status", "Research fine-tuning job not found")
            return
        
        # Format status message based on job state
        status_msg = f"""
Job ID: {latest_job.id}
Status: {latest_job.status}
Created at: {latest_job.created_at}
"""
        # Add model ID only if training is completed
        if hasattr(latest_job, 'fine_tuned_model') and latest_job.fine_tuned_model:
            status_msg += f"Fine-tuned model: {latest_job.fine_tuned_model}\n"
        
        if hasattr(latest_job, 'finished_at') and latest_job.finished_at:
            status_msg += f"Finished at: {latest_job.finished_at}\n"
        
        status_msg += f"""
Training file: {latest_job.training_file}
Validation file: {latest_job.validation_file if latest_job.validation_file else 'None'}
"""

        log_step("Fine-tuning Status", status_msg)

    except Exception as e:
        log_step("Error", f"Failed to check status: {str(e)}")
        import traceback
        print(traceback.format_exc())

if __name__ == "__main__":
    check_fine_tuning_status() 