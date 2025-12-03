import json
import argparse
import os
import sys # Imported for sys.exit(1)
from google import genai
from google.genai.errors import APIError

def count_tokens_in_jsonl(file_path: str, model_name: str = "gemini-2.0-flash-001") -> tuple[int, int]:
    """
    Calculates the total number of tokens in a JSONL file using the Google GenAI SDK,
    which provides the official token count for billing purposes.
    """
    
    # Check 1: File existence
    if not os.path.exists(file_path):
        print(f"❌ Error: Dataset file not found at path: {file_path}")
        sys.exit(1)
    
    # Check 2: Environment variables for Vertex AI context
    project_id = os.environ.get('GCP_PROJECT')
    location = os.environ.get('GCP_LOCATION')
    
    if not project_id or not location:
        print("❌ Error: GCP_PROJECT or GCP_LOCATION environment variables are missing.")
        print("Ensure they are set in the workflow YAML (e.g., env: GCP_PROJECT: ${{ secrets.GCP_PROJECT_ID }}).")
        sys.exit(1)
        
    total_tokens = 0
    total_examples = 0
    
    try:
        # Initialize the client with explicit Vertex AI context
        client = genai.Client(vertexai=True, project=project_id, location=location)
    except Exception as e:
        print("❌ Error initializing GenAI client. Check project/location and WIF token scope.")
        print(e)
        sys.exit(1)

    print(f"Counting tokens for model: {model_name} in {location}...")
    print("-" * 30)

    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            try:
                data = json.loads(line)
                
                # --- Token Counting Logic ---
                system_instruction = data.get('systemInstruction', {}).get('parts', [{}])[0].get('text', '')
                contents = data.get('contents', [])
                
                text_to_count = []
                if system_instruction:
                    text_to_count.append(system_instruction)

                for content in contents:
                    if content.get('parts'):
                        # Append the text from all role parts (user and model)
                        text_to_count.append(content['parts'][0]['text'])

                # Call the API for the exact token count
                response = client.models.count_tokens(
                    model=model_name,
                    contents=text_to_count
                )
                
                total_tokens += response.total_tokens
                total_examples += 1

            except json.JSONDecodeError:
                print(f"Skipping line {total_examples + 1}: Invalid JSON format. Run schema validator!")
            except APIError as e:
                print(f"❌ API Error on line {total_examples + 1}. Check model name or quotas.")
                print(e)
                sys.exit(1)
            except Exception as e:
                print(f"An unexpected error occurred: {e}")
                sys.exit(1)
                
    # Final Output
    print("\n==========================================")
    print("✨ GEMINI TRAINING TOKEN ESTIMATE")
    print("==========================================")
    print(f"File: {file_path}")
    print(f"Total Examples: {total_examples}")
    print(f"Total Training Tokens: {total_tokens:,}")
    
    # Estimate Total Cost Tokens based on 3 Epochs (common default)
    estimated_cost_tokens = total_tokens * 3
    print(f"Estimated Tokens (3 Epochs): {estimated_cost_tokens:,}")
    print("==========================================")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Calculate training tokens for a Gemini JSONL dataset.")
    parser.add_argument("file_path", nargs='?', default='data/training.jsonl',
                        help="Path to the training data JSONL file (defaults to data/training.jsonl).")
    parser.add_argument("--model", default="gemini-2.0-flash-001", 
                        help="The base Gemini model used for tuning.")
    
    args = parser.parse_args()
    
    # Use the provided argument path
    file_to_check = args.file_path
    
    # Handle the case where the argument is passed as an empty string (from workflow_dispatch)
    if not file_to_check or file_to_check.isspace():
        file_to_check = 'data/training.jsonl'
    
    count_tokens_in_jsonl(file_to_check, args.model)

