import os
import sys
import configparser
from sqlalchemy import create_engine, text

# Hardcoded nexus_db connection string from config.ini
DB_URL = "postgresql://nexus:nexus_password@localhost:5432/nexus_db"

def update_db():
    engine = create_engine(DB_URL)
    with engine.connect() as conn:
        print("Optimizing models in DB...")
        
        # 1. Update Qwen
        conn.execute(text("""
            UPDATE model_requirements
            SET max_model_len = 4096,
                gpu_memory_utilization = 0.80
            WHERE model_id = 'qwen-2.5-7b-awq'
        """))
        
        # 2. Update Llama
        conn.execute(text("""
            UPDATE model_requirements
            SET max_model_len = 4096,
                gpu_memory_utilization = 0.80
            WHERE model_id = 'meta-llama-3-8b'
        """))
        
        # 3. Ensure Llama path is set correctly if it is intended for vLLM
        # Note: We use the exact filename as the model_id suffix for vllm_manager
        conn.execute(text("""
            UPDATE ai_models
            SET file_path = 'Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf',
                provider = 'vllm',
                repo_id = 'meta-llama/Meta-Llama-3.1-8B-Instruct'
            WHERE id = 'meta-llama-3-8b'
        """))
        
        conn.commit()
        print("DB Updated successfully.")

def update_config():
    config_path = "../config.ini"
    if not os.path.exists(config_path):
        print(f"Config not found at {config_path}")
        return
        
    config = configparser.ConfigParser()
    config.read(config_path)
    
    if "Inference" in config:
        print("Updating config.ini [Inference] section for Llama (STABILIZING MEMORY)...")
        config["Inference"]["default_model"] = "meta-llama-3-8b"
        config["Inference"]["vllm_model_name"] = "/model/Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf"
        config["Inference"]["vllm_max_model_len"] = "1024" # Final reduction
        config["Inference"]["vllm_gpu_memory_utilization"] = "0.50" # Final reduction
        config["Inference"]["vllm_quantization"] = "none"






        
        with open(config_path, "w") as f:
            config.write(f)
        print("config.ini updated successfully.")

if __name__ == "__main__":
    update_db()
    update_config()

