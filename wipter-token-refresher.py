#!/usr/bin/env python3
"""
WIPTER COGNITO TOKEN REFRESHER
Tự động làm mới Access Token từ Refresh Token (AWS Cognito)
và cập nhật đồng bộ cho tất cả các container node đang chạy.
"""

import os
import sys
import glob
import json
import base64
import urllib.request
import argparse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REFRESH_TOKEN_FILE = os.path.join(BASE_DIR, "config", "refresh_token.txt")
CONFIG_CRED_FILE = os.path.join(BASE_DIR, "config", "secure-credentials.json")
NODES_DATA_DIR = os.path.join(BASE_DIR, "data", "nodes")
CLIENT_ID = "4isku1tmrioog84a88qkl7cnd4"
COGNITO_URL = "https://cognito-idp.us-west-2.amazonaws.com/"

def refresh():
    if not os.path.exists(REFRESH_TOKEN_FILE):
        print(f"[ERROR] Không tìm thấy refresh token: {REFRESH_TOKEN_FILE}")
        return False

    with open(REFRESH_TOKEN_FILE, "r") as f:
        token_str = f.read().strip()

    if not token_str:
        print(f"[ERROR] Refresh token trong file bị rỗng!")
        return False

    payload = json.dumps({
        "AuthFlow": "REFRESH_TOKEN_AUTH",
        "ClientId": CLIENT_ID,
        "AuthParameters": {
            "REFRESH_TOKEN": token_str
        }
    }).encode("utf-8")

    req = urllib.request.Request(
        COGNITO_URL,
        data=payload,
        headers={
            "Content-Type": "application/x-amz-json-1.1",
            "X-Amz-Target": "AWSCognitoIdentityProviderService.InitiateAuth"
        }
    )

    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read().decode())
            auth_res = data.get("AuthenticationResult", {})
            access_token = auth_res.get("AccessToken")
            if not access_token:
                print(f"[ERROR] Cognito không trả về AccessToken: {data}")
                return False

            b64_val = "plain:" + base64.b64encode(access_token.encode("utf-8")).decode("utf-8")
            cred_dict = {
                "com": {
                    "wipter": {
                        "auth": {
                            "production:root": b64_val
                        }
                    }
                }
            }

            # Ghi vào file config chính
            os.makedirs(os.path.dirname(CONFIG_CRED_FILE), exist_ok=True)
            with open(CONFIG_CRED_FILE, "w") as f:
                json.dump(cred_dict, f, indent=4)
            print(f"[SUCCESS] Đã cập nhật {CONFIG_CRED_FILE} (Hạn dùng: {auth_res.get('ExpiresIn', 86400)}s)")

            # Đồng bộ sang các node data
            updated_nodes = 0
            if os.path.exists(NODES_DATA_DIR):
                for ndir in glob.glob(os.path.join(NODES_DATA_DIR, "node_*")):
                    if os.path.isdir(ndir):
                        target = os.path.join(ndir, "secure-credentials.json")
                        with open(target, "w") as f:
                            json.dump(cred_dict, f, indent=4)
                        updated_nodes += 1

            # Kiểm tra cả thư mục /root/quarkvpn/wipter_nodes nếu đang chạy trên host cũ
            if os.path.exists("/root/quarkvpn/wipter_nodes"):
                for ndir in glob.glob("/root/quarkvpn/wipter_nodes/node_*"):
                    if os.path.isdir(ndir):
                        target = os.path.join(ndir, "secure-credentials.json")
                        with open(target, "w") as f:
                            json.dump(cred_dict, f, indent=4)
                        updated_nodes += 1

            print(f"[SUCCESS] Đã đồng bộ token mới sang {updated_nodes} node directories.")
            return True

    except Exception as e:
        print(f"[ERROR] Làm mới token thất bại: {e}")
        return False

if __name__ == "__main__":
    refresh()
