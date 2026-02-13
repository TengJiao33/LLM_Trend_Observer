import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()

class WXPusherNotifier:
    def __init__(self):
        self.app_token = os.getenv("WXPUSHER_APP_TOKEN")
        self.uids = os.getenv("WXPUSHER_UIDS", "").split(",")
        self.api_url = "https://wxpusher.zjiecode.com/api/send/message"

    def send_report(self, content, summary="LLM Trend Observer Report"):
        """
        发送 Markdown 格式的报告
        """
        if not self.app_token or not self.uids or not self.uids[0]:
            print("Warning: WXPusher credentials missing. Skipping notification.")
            return False

        payload = {
            "appToken": self.app_token,
            "content": content,
            "summary": summary,
            "contentType": 3,  # 1表示文字  2表示html(只发送body标签内部的数据) 3表示markdown
            "uids": self.uids
        }

        try:
            response = requests.post(self.api_url, json=payload, timeout=10)
            result = response.json()
            if result.get("code") == 1000:
                print("Notification sent successfully via WXPusher.")
                return True
            else:
                print(f"Failed to send notification: {result.get('msg')}")
                return False
        except Exception as e:
            print(f"Error calling WXPusher API: {e}")
            return False

if __name__ == "__main__":
    # Test notification
    notifier = WXPusherNotifier()
    notifier.send_report("### 这是一个测试报告\n- 测试项 1\n- 测试项 2", "测试通知")
