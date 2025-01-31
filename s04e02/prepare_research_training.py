import json
import os

def prepare_training_data():
    # Get the directory where this script is located
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    training_data = []
    
    # Load correct samples
    correct_path = os.path.join(script_dir, 'context', 'correct.txt')
    incorrect_path = os.path.join(script_dir, 'context', 'incorrect.txt')
    training_path = os.path.join(script_dir, 'training', 'research_training.jsonl')
    
    # Create training directory if it doesn't exist
    os.makedirs(os.path.dirname(training_path), exist_ok=True)
    
    try:
        # Load correct samples
        with open(correct_path, 'r') as f:
            correct_samples = f.readlines()
            for sample in correct_samples:
                training_data.append({
                    "messages": [
                        {"role": "system", "content": "validate research sample"},
                        {"role": "user", "content": sample.strip()},
                        {"role": "assistant", "content": "1"}
                    ]
                })
        
        # Load incorrect samples
        with open(incorrect_path, 'r') as f:
            incorrect_samples = f.readlines()
            for sample in incorrect_samples:
                training_data.append({
                    "messages": [
                        {"role": "system", "content": "validate research sample"},
                        {"role": "user", "content": sample.strip()},
                        {"role": "assistant", "content": "0"}
                    ]
                })
        
        # Save training data
        with open(training_path, 'w') as f:
            for item in training_data:
                f.write(json.dumps(item) + '\n')
        
        print(f"Training data saved to: {training_path}")
        print(f"Total samples: {len(training_data)}")
        print(f"Correct samples: {len(correct_samples)}")
        print(f"Incorrect samples: {len(incorrect_samples)}")
        
    except FileNotFoundError as e:
        print(f"Error: Could not find file: {e.filename}")
        print("Make sure the following files exist:")
        print(f"- {correct_path}")
        print(f"- {incorrect_path}")
    except Exception as e:
        print(f"Error preparing training data: {str(e)}")

if __name__ == "__main__":
    prepare_training_data() 