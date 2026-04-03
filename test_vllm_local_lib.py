import asyncio
import httpx
import sys

async def test_vllm_docker():
    url = "http://localhost:8001/v1/chat/completions"
    payload = {
        "model": "/model/Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf",
        "messages": [
            {"role": "user", "content": "Explain agentic systems in 1 sentence."}
        ],
        "max_tokens": 100,
        "temperature": 0.2
    }

    print(f"Testing vLLM Docker at {url}...")
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            print("\nSUCCESS!")
            print(f"Response: {data['choices'][0]['message']['content']}")
    except Exception as e:
        print(f"\nFAILURE: Could not connect to vLLM Docker. {e}")
        print("Make sure you ran 'docker-compose -f docker-compose.vllm.yml up -d' and the container is healthy.")

if __name__ == "__main__":
    asyncio.run(test_vllm_docker())
