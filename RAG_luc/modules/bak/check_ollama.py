import ollama

try:
    response = ollama.list()
    print("Connection successful!")

    print("Models found:", [m.model for m in response.models])
except Exception as e:
    print(f"Connection failed: {e}")
