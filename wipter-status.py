#!/usr/bin/env python3
"""
WIPTER REALTIME STATUS DASHBOARD
Hiển thị trạng thái kết nối, địa điểm, IP type, lưu lượng và số tiền kiếm được.
"""

import os
import sys
import json
import urllib.request
import subprocess

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(BASE_DIR, "data", "deployed_nodes.json")

def get_node_status(port):
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{port}/api/status")
        with urllib.request.urlopen(req, timeout=2.0) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return None

def main():
    print("=" * 96)
    print("                         WIPTER CONTAINER CLUSTER STATUS DASHBOARD                              ")
    print("=" * 96)

    nodes = []
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                nodes = json.load(f)
        except Exception:
            pass

    # Nếu không có state file, tự động quét container theo tên
    if not nodes:
        cmd = "docker ps --filter 'name=wipter' --format '{{.Names}}'"
        res = subprocess.run(cmd, shell=True, text=True, capture_output=True)
        cnames = [c.strip() for c in res.stdout.splitlines() if c.strip()]
        for c in cnames:
            # Kiểm tra port env
            env_cmd = f"docker inspect {c} --format '{{{{json .Config.Env}}}}'"
            res_env = subprocess.run(env_cmd, shell=True, text=True, capture_output=True)
            port = None
            if res_env.returncode == 0:
                try:
                    envs = json.loads(res_env.stdout)
                    for e in envs:
                        if e.startswith("STATUS_PORT="):
                            port = int(e.split("=")[1])
                except Exception:
                    pass
            nodes.append({
                "container_name": c,
                "status_port": port or 9222,
                "proxy_url": "N/A"
            })

    print(f"Tổng số node được quản lý: {len(nodes)}")
    print("-" * 96)
    header = (
        f"{'Container':<18} "
        f"{'Status':<14} "
        f"{'IP Type':<16} "
        f"{'Location':<24} "
        f"{'Traffic':<11} "
        f"{'Earnings':<10}"
    )
    print(header)
    print("-" * 96)

    total_online = 0
    total_earned = "USD 0.00"

    for node in nodes:
        cname = node.get("container_name", "wipter-node")
        port = node.get("status_port")
        stat = get_node_status(port) if port else None

        if stat:
            status_str = stat.get("status", "Online 🟢")
            iptype_str = stat.get("ipType", "Residential")[:15]
            loc_str = stat.get("location", "Unknown")[:23]
            traffic_str = stat.get("traffic", "0.00 MB")
            earn_str = stat.get("totalEarned", "USD 0.00")
            total_online += 1
            total_earned = earn_str
        else:
            status_str = "Offline 🔴"
            iptype_str = "-"
            loc_str = "-"
            traffic_str = "-"
            earn_str = "-"

        print(f"{cname:<18} {status_str:<14} {iptype_str:<16} {loc_str:<24} {traffic_str:<11} {earn_str:<10}")

    print("=" * 96)
    print(f"Tóm tắt: Online {total_online}/{len(nodes)} Nodes | Tổng thu nhập tài khoản: {total_earned}")
    try:
        mem = subprocess.run("free -h | awk '/^Mem:/ {print \"RAM: \" $3 \" used / \" $2 \" total | Available: \" $7}'", shell=True, text=True, capture_output=True).stdout.strip()
        print(f"Hệ thống: {mem}")
    except Exception:
        pass
    print("=" * 96)

if __name__ == "__main__":
    main()
