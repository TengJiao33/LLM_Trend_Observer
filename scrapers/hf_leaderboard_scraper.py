import requests
import json
import os
from datetime import datetime

def scrape_hf_leaderboard():
    """
    Scrape the top 10 models from Hugging Face Open LLM Leaderboard v2
    using the HF Datasets API (datasets-server).
    """
    print("Starting Hugging Face Open LLM Leaderboard Scrape (via API)...")
    
    # HF Datasets API endpoint for 'open-llm-leaderboard/contents'
    # This dataset contains the actual leaderboard rankings.
    url = "https://datasets-server.huggingface.co/rows?dataset=open-llm-leaderboard/contents&config=default&split=train&offset=0&limit=500"
    
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        rows = data.get("rows", [])
        if not rows:
            print("No data found in HF Leaderboard dataset.")
            return False
            
        leaderboard = []
        for item in rows:
            row = item.get("row", {})
            model_id = row.get("fullname") or row.get("Model")
            average_score = row.get("Average ⬆️")
            
            if model_id and average_score is not None:
                leaderboard.append({
                    "model_id": model_id,
                    "score": round(float(average_score), 2),
                    "timestamp": datetime.now().isoformat()
                })
        
        # Sort by score descending and take top 10
        leaderboard.sort(key=lambda x: x["score"], reverse=True)
        top_10 = leaderboard[:10]
        
        # Add rank
        for i, item in enumerate(top_10):
            item["rank"] = i + 1
            
        if top_10:
            os.makedirs("data", exist_ok=True)
            output_file = "data/hf_leaderboard_current.json"
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(top_10, f, indent=4, ensure_ascii=False)
            print(f"HF Leaderboard Scrape successful. Data saved to {output_file}")
            return True
        else:
            print("Failed to extract any valid models from HF Leaderboard.")
            return False
            
    except Exception as e:
        print(f"Error during HF Leaderboard scrape: {e}")
        return False

if __name__ == "__main__":
    scrape_hf_leaderboard()
