import os
try:
    from google import genai
    from google.genai import types
    HAS_GEMINI = True
except ImportError:
    HAS_GEMINI = False

def check_model_metadata():
    if not HAS_GEMINI:
        print("google-genai not installed")
        return

    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not api_key:
        # Try reading from resources/keys.txt as mentioned in earlier turns
        keys_path = r"c:\Users\91797\Documents\Dev\JS\Monorepo\Backend Monorepo\Backend\resources\keys.txt"
        if os.path.exists(keys_path):
            with open(keys_path, 'r') as f:
                for line in f:
                    if "GOOGLE_API_KEY" in line or "GEMINI_API_KEY" in line:
                        api_key = line.split("=")[1].strip().strip('"')
                        break

    if not api_key:
        print("No API key found")
        return

    client = genai.Client(api_key=api_key)
    try:
        model = client.models.get(model="gemini-1.5-flash")
        print(f"Model: {model.name}")
        print(f"Display Name: {model.display_name}")
        print(f"Description: {model.description}")
        print(f"Input Token Limit: {model.input_token_limit}")
        print(f"Output Token Limit: {model.output_token_limit}")
        # Check if there are any other attributes
        attrs = [a for a in dir(model) if not a.startswith('_')]
        print(f"Attributes: {attrs}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_model_metadata()
