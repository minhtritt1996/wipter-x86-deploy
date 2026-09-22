#!/usr/bin/env python3
"""
FAST PROXY CHECKER & RESIDENTIAL FILTER FOR WIPTER
Quét danh sách proxy và trích xuất các proxy đạt chuẩn RESIDENTIAL IP.
"""

import asyncio
import aiohttp
import json
import time
import os
import sys
import argparse

CONCURRENCY = 30
TIMEOUT_SEC = 6

async def check_proxy(sem, session, proxy_url):
    result = {
        "proxy_url": proxy_url,
        "status": "OFFLINE",
        "ip": None,
        "country": None,
        "city": None,
        "isp": None,
        "is_residential": False
    }

    async with sem:
        # Step 1: Query ip-api
        try:
            t0 = time.time()
            async with session.get(
                "http://ip-api.com/json/?fields=status,country,city,isp,org,as,hosting,query",
                proxy=proxy_url,
                timeout=aiohttp.ClientTimeout(total=TIMEOUT_SEC)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("status") == "success":
                        result["status"] = "ONLINE"
                        result["ip"] = data.get("query")
                        result["country"] = data.get("country")
                        result["city"] = data.get("city")
                        result["isp"] = data.get("isp")
                        result["hosting"] = data.get("hosting")
                        result["rtt_ms"] = round((time.time() - t0) * 1000, 1)
        except Exception:
            return result

        # Step 2: If ip-api hosting == False, check ipinfo company type
        if result["status"] == "ONLINE" and result.get("hosting") is False and result["ip"]:
            try:
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                    "Referer": "https://ipinfo.io/"
                }
                async with session.get(
                    f"https://ipinfo.io/widget/demo/{result['ip']}",
                    proxy=proxy_url,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=TIMEOUT_SEC)
                ) as resp:
                    if resp.status == 200:
                        info = await resp.json()
                        company = info.get("data", {}).get("company", {})
                        ip_type = company.get("type")
                        if ip_type == "isp":
                            result["is_residential"] = True
            except Exception:
                # Fallback to direct query
                try:
                    async with session.get(
                        f"https://ipinfo.io/widget/demo/{result['ip']}",
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=TIMEOUT_SEC)
                    ) as resp2:
                        if resp2.status == 200:
                            info = await resp2.json()
                            company = info.get("data", {}).get("company", {})
                            if company.get("type") == "isp":
                                result["is_residential"] = True
                except Exception:
                    pass

    return result

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

async def main():
    parser = argparse.ArgumentParser(description="Wipter Residential Proxy Filter")
    parser.add_argument("-i", "--input", default="proxies.txt", help="Input proxy file path")
    parser.add_argument("-o", "--output", default="residential_proxies.txt", help="Output file for residential proxies")
    parser.add_argument("-c", "--concurrency", type=int, default=CONCURRENCY, help="Number of concurrent workers")
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"[ERROR] Không tìm thấy file danh sách proxy: {args.input}")
        sys.exit(1)

    proxy_urls = []
    with open(args.input, "r") as f:
        for line in f:
            p = parse_proxy_line(line)
            if p:
                proxy_urls.append(p)

    print("=" * 70)
    print(f"🚀 QUÉT RESIDENTIAL PROXIES CHO WIPTER")
    print(f"   Tổng số proxy: {len(proxy_urls)} | Luồng: {args.concurrency}")
    print("=" * 70)

    sem = asyncio.Semaphore(args.concurrency)
    connector = aiohttp.TCPConnector(limit=args.concurrency * 2, ssl=False)

    start_time = time.time()
    results = []

    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [check_proxy(sem, session, p) for p in proxy_urls]
        done = 0
        res_count = 0
        online_count = 0

        for fut in asyncio.as_completed(tasks):
            r = await fut
            results.append(r)
            done += 1
            if r["status"] == "ONLINE":
                online_count += 1
                if r["is_residential"]:
                    res_count += 1
                    print(f"[+] RESIDENTIAL: {r['proxy_url']} -> IP: {r['ip']} ({r['country']}) ISP: {r['isp']}")

            if done % 20 == 0 or done == len(proxy_urls):
                print(f"Tiến độ: {done}/{len(proxy_urls)} | Online: {online_count} | Residential: {res_count}", end="\r", flush=True)

    print("\n\nQuét hoàn tất!")
    residential = [r for r in results if r["is_residential"]]

    with open(args.output, "w") as f:
        for r in residential:
            f.write(f"{r['proxy_url']}\n")

    print(f"-> Đã lưu {len(residential)} Residential proxies vào: {args.output}")

if __name__ == "__main__":
    asyncio.run(main())
