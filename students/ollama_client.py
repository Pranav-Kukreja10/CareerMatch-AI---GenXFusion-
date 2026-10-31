import os
import json
import requests

class OllamaClient:
    """
    Service client to communicate with the local Ollama instance on Windows 11.
    Utilizes Qwen 3.5 9B in strict JSON schema mode.
    """
    @staticmethod
    def analyze_resume_text(raw_text: str) -> dict:
        ollama_host = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
        model_name = os.getenv("OLLAMA_MODEL", "qwen3.5:9b")
        
        # 1. Truncate the raw text to prevent massive context overloads
        # A standard resume is ~3000 chars. We cut off anything beyond 6000.
        safe_text = raw_text[:6000]
        
        # 2. Ultra-simplified prompt to speed up generation
        system_prompt = (
            "Extract skills and one project from this resume. "
            "Return ONLY JSON: {\"skills\": [\"A\"], \"projects\": [{\"title\": \"B\", \"technologies\": [\"C\"], \"description\": \"D\"}]}"
        )

        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Resume Text:\n{safe_text}"}
            ],
            "stream": False,
            "format": "json",
            # "keep_alive": -1,
            "options": {
                "num_ctx": 2048, # Reduced context size to save memory
                "temperature": 0.1 # Low temp = faster, more deterministic generation
            }
        }

        try:
            # 3. Remove the timeout entirely for this diagnostic run
            response = requests.post(f"{ollama_host}/api/chat", json=payload)
            response.raise_for_status()
            
            result_data = response.json()
            message_content = result_data["message"]["content"]
            return json.loads(message_content)
            
        except requests.exceptions.RequestException as e:
            raise ConnectionError(f"Failed to connect to local Ollama server at {ollama_host}: {str(e)}")
        except Exception as e:
            raise ValueError(f"Ollama JSON parsing error: {str(e)}")
