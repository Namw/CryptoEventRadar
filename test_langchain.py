import os
import time
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from dotenv import load_dotenv

load_dotenv()

def test_translate():
    start_time = time.time()
    try:
        # Based on grep, the key is OPENAI_MODEL
        model_name = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")
        print(f"Using model: {model_name}")
        chat = ChatOpenAI(model=model_name)
        messages = [HumanMessage(content="Translate 'Hello, world!' to Chinese.")]
        response = chat.invoke(messages)
        duration = time.time() - start_time
        print(f"Status: Success")
        print(f"Response: {response.content}")
        print(f"Duration: {duration:.2f}s")
    except Exception as e:
        duration = time.time() - start_time
        print(f"Status: Failed")
        print(f"Error Type: {type(e).__name__}")
        print(f"Error Message: {e}")
        print(f"Duration: {duration:.2f}s")

if __name__ == "__main__":
    test_translate()
