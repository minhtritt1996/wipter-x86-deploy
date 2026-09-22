#!/usr/bin/env python3
"""
WIPTER MASS NODE DEPLOYER (x86_64 / ARM64)
Tự động dựng và khởi chạy hàng loạt Wipter container node theo danh sách proxy.
"""

import os
import sys
import json
import shutil
import subprocess
import argparse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_DIR = os.path.join(BASE_DIR, "config")
CRED_FILE = os.path.join(CONFIG_DIR, "secure-credentials.json")
DATA_DIR = os.path.join(BASE_DIR, "data")
NODES_DIR = os.path.join(DATA_DIR, "nodes")
STATE_FILE = os.path.join(DATA_DIR, "deployed_nodes.json")

DEFAULT_IMAGE = "wipter-node:latest"

def run_cmd(cmd, check=True):
    print(f"[$] {cmd}")
    res = subprocess.run(cmd, shell=True, text=True, capture_output=True)
    if check and res.returncode != 0:
        print(f"[ERROR] Lỗi thực thi ({res.returncode}):\n{res.stderr}")
    return res

def build_image(image_name):
    print("=" * 70)
    print(f"🛠️ ĐANG BUILD DOCKER IMAGE: {image_name}")
    print("=" * 70)
    res = run_cmd(f"docker build -t {image_name} {BASE_DIR}")
    if res.returncode != 0:
        print("[ERROR] Build Docker image thất bại!")
        sys.exit(1)
    print("[SUCCESS] Build Docker image thành công!\n")

def stop_all(prefix="wipter-node"):
    print("=" * 70)
    print(f"🛑 ĐANG DỪNG VÀ XÓA TẤT CẢ CONTAINER ({prefix}*)...")
    print("=" * 70)
    cmd = f"docker ps -a --filter 'name={prefix}' --format '{{{{.Names}}}}'"
    res = subprocess.run(cmd, shell=True, text=True, capture_output=True)
    names = [n.strip() for n in res.stdout.splitlines() if n.strip()]
    if not names:
        print("[INFO] Không có container nào đang chạy.")
        return

    print(f"Tìm thấy {len(names)} container: {', '.join(names[:5])}...")
    run_cmd(f"docker rm -f {' '.join(names)}")
    if os.path.exists(STATE_FILE):
        os.remove(STATE_FILE)
    print("[SUCCESS] Đã dọn dẹp sạch sẽ toàn bộ container.")

def parse_proxy_line(line):
    line = line.strip()
    if not line or line.startswith("#"):
        return None
    if line.startswith("http://") or line.startswith("socks5://"):
        return line
    parts = line.split(":")
    if len(parts) == 4:
        # host:port:user:pass
        h, p, u, pwd = parts
        return f"http://{u}:{pwd}@{h}:{p}"
    elif len(parts) == 2:
        # host:port
        h, p = parts
        return f"http://{h}:{p}"
    return None

def deploy(args):
    # Đảm bảo có credentials
    if not os.path.exists(CRED_FILE):
        print("[WARN] Chưa có secure-credentials.json trong thư mục config!")
        # Thử chạy token refresher
        refresher = os.path.join(BASE_DIR, "wipter-token-refresher.py")
        if os.path.exists(refresher):
            print("[INFO] Đang chạy wipter-token-refresher.py để tạo credentials...")
            subprocess.run(["python3", refresher])
        
        if not os.path.exists(CRED_FILE):
            print(f"[ERROR] Vẫn không tìm thấy {CRED_FILE}! Vui lòng kiểm tra lại.")
            sys.exit(1)

    if args.build:
        build_image(args.image)

    # Đọc danh sách proxy
    if not os.path.exists(args.proxies):
        print(f"[ERROR] Không tìm thấy file danh sách proxy: {args.proxies}")
        sys.exit(1)

    proxy_list = []
    with open(args.proxies, "r") as f:
        for line in f:
            p = parse_proxy_line(line)
            if p:
                proxy_list.append(p)

    if args.limit and args.limit > 0:
        proxy_list = proxy_list[:args.limit]

    print("=" * 70)
    print(f"🚀 KHỞI CHẠY HÀNG LOẠT WIPTER NODES")
    print(f"   Số lượng node: {len(proxy_list)}")
    print(f"   Docker Image: {args.image}")
    print(f"   Port khởi đầu: {args.start_port}")
    print("=" * 70)

    os.makedirs(NODES_DIR, exist_ok=True)
    deployed_records = []

    for idx, proxy_url in enumerate(proxy_list, 1):
        cname = f"{args.prefix}-{idx:03d}"
        status_port = args.start_port + idx - 1
        node_dir = os.path.join(NODES_DIR, f"node_{idx:03d}")
        os.makedirs(node_dir, exist_ok=True)

        # Copy credentials vào thư mục node
        shutil.copy2(CRED_FILE, os.path.join(node_dir, "secure-credentials.json"))

        # Xóa container cũ nếu trùng tên
        subprocess.run(f"docker rm -f {cname} 2>/dev/null", shell=True)

        # Cấu hình RAM limit để chống crash khi chạy số lượng lớn
        mem_flag = f"--memory={args.mem_limit}" if args.mem_limit else ""

        run_cmd_str = (
            f"docker run -d "
            f"--name {cname} "
            f"--restart unless-stopped "
            f"--net=host "
            f"{mem_flag} "
            f"-e WIPTER_PROXY='{proxy_url}' "
            f"-e STATUS_PORT={status_port} "
            f"-e WIPTER_USER_DATA=/root/.config/wipter-app "
            f"-v {node_dir}:/root/.config/wipter-app "
            f"{args.image}"
        )

        res = subprocess.run(run_cmd_str, shell=True, text=True, capture_output=True)
        if res.returncode == 0:
            cid = res.stdout.strip()[:12]
            print(f"[OK] Đã khởi chạy: {cname} (CID: {cid}) | Status Port: {status_port} | Proxy: {proxy_url[:40]}...")
            deployed_records.append({
                "index": idx,
                "container_name": cname,
                "container_id": cid,
                "status_port": status_port,
                "proxy_url": proxy_url,
                "node_dir": node_dir
            })
        else:
            print(f"[FAIL] Khởi chạy thất bại {cname}: {res.stderr.strip()}")

    # Lưu state
    with open(STATE_FILE, "w") as f:
        json.dump(deployed_records, f, indent=2)

    print("\n" + "=" * 70)
    print(f"🎉 HOÀN TẤT! Đã triển khai thành công {len(deployed_records)}/{len(proxy_list)} nodes.")
    print(f"   Xem trạng thái nhanh: python3 wipter-status.py")
    print("=" * 70)

def main():
    parser = argparse.ArgumentParser(description="Wipter Multi-Node Deployer")
    parser.add_argument("-p", "--proxies", default="residential_proxies.txt", help="Proxy list file")
    parser.add_argument("-l", "--limit", type=int, default=0, help="Limit number of nodes (0 = all)")
    parser.add_argument("--image", default=DEFAULT_IMAGE, help="Docker image tag")
    parser.add_argument("--start-port", type=int, default=19001, help="Starting status port")
    parser.add_argument("--mem-limit", default="256m", help="RAM limit per container (e.g. 256m, 180m)")
    parser.add_argument("--prefix", default="wipter-node", help="Container name prefix")
    parser.add_argument("--build", action="store_true", help="Build Docker image before deploying")
    parser.add_argument("--stop-all", action="store_true", help="Stop and remove all deployed containers")

    args = parser.parse_args()

    if args.stop_all:
        stop_all(args.prefix)
    else:
        deploy(args)

if __name__ == "__main__":
    main()
