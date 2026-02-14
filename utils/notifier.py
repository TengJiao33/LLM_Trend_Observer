import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()

class ServerChanNotifier:
    def __init__(self):
        self.sendkey = os.getenv("SERVERCHAN_SENDKEY")
        self.api_url = f"https://sctapi.ftqq.com/{self.sendkey}.send" if self.sendkey else None

    def send(self, content, title="LLM Trend Observer Report"):
        if not self.api_url:
            return False
        payload = {"title": title, "desp": content}
        try:
            response = requests.post(self.api_url, data=payload, timeout=10)
            result = response.json()
            if result.get("code") == 0 or (result.get("data") and result.get("data").get("errno") == 0):
                print(f"Success: Sent via ServerChan.")
                return True
            print(f"Error: ServerChan failed: {result}")
        except Exception as e:
            print(f"Error: ServerChan exception: {e}")
        return False

class WXPusherNotifier:
    def __init__(self):
        self.app_token = os.getenv("WXPUSHER_APP_TOKEN")
        self.uids = [u for u in os.getenv("WXPUSHER_UIDS", "").split(",") if u]
        self.topic_ids = [t for t in os.getenv("WXPUSHER_TOPIC_IDS", "").split(",") if t]
        self.api_url = "https://wxpusher.zjiecode.com/api/send/message"

    def send(self, content, summary="LLM Trend Observer Report"):
        if not self.app_token:
            return False
        if not self.uids and not self.topic_ids:
            return False
        payload = {
            "appToken": self.app_token,
            "content": content,
            "summary": summary,
            "contentType": 3,
            "uids": self.uids,
            "topicIds": self.topic_ids
        }
        try:
            response = requests.post(self.api_url, json=payload, timeout=10)
            result = response.json()
            if result.get("code") == 1000:
                print(f"Success: Sent via WXPusher.")
                return True
            print(f"Error: WXPusher failed: {result}")
        except Exception as e:
            print(f"Error: WXPusher exception: {e}")
        return False

class HubNotifier:
    def __init__(self):
        self.notifiers = []
        if os.getenv("SERVERCHAN_SENDKEY"):
            self.notifiers.append(ServerChanNotifier())
        # 用户要求：持续关闭 WXPusher 直到明确要求开启
        # if os.getenv("WXPUSHER_APP_TOKEN"):
        #     self.notifiers.append(WXPusherNotifier())

    def send_all(self, content, title="LLM Trend Observer Report"):
        results = []
        for n in self.notifiers:
            results.append(n.send(content, title))
        return any(results)


