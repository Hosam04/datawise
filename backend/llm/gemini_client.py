import os
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv
from diskcache import Cache
import hashlib

load_dotenv()

cache = Cache('./storage/llm_cache')

class GeminiClientWrapper:
    _instance = None

    def __init__(self):
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            google_api_key=os.getenv("GEMINI_API_KEY"),
            temperature=0
        )

    def invoke_cached(self, prompt: str, structure_model=None):
        key = hashlib.md5(prompt.encode()).hexdigest()
    
        if key in cache:
            print("Gemini Client: Returning cached result.")
            raw = cache[key]
            if structure_model:
                return structure_model.model_validate(raw)
            return raw
    
        if structure_model:
            llm_to_run = self.llm.with_structured_output(structure_model)
        else:
            llm_to_run = self.llm
        
        result = llm_to_run.invoke(prompt)
    
        cache[key] = result.model_dump() if hasattr(result, 'model_dump') else result
        return result

# Singleton instance
client_wrapper = GeminiClientWrapper()

def get_gemini_client():
    return client_wrapper


def get_chat_model():
    return client_wrapper.llm