# HƯỚNG DẪN TRIỂN KHAI HỆ THỐNG WIPTER CONTAINER ĐA NODE (x86_64 & ARM64)

Dự án này là phiên bản đóng gói độc lập của **Wipter Headless Node** (chạy trên nền **Alpine Linux** siêu nhẹ, tiêu thụ chỉ ~100MB RAM/container thay vì ~800MB như app Electron giao diện), được tối ưu hóa để triển khai quy mô lớn (hàng chục đến hàng trăm node) trên các máy tính x86_64 hoặc ARM64 khác.

---

## 📂 1. Cấu Trúc Thư Mục Dự Án

```
wipter-x86-deploy/
├── Dockerfile                  # File build image đa nền tảng (x86_64 & ARM64)
├── entrypoint.sh               # Script tự động nhận diện kiến trúc CPU & khởi tạo
├── deploy-nodes.py             # Script master khởi chạy & quản lý hàng loạt node
├── check-proxies.py            # Công cụ kiểm tra & lọc ra IP Residential thật
├── wipter-status.py            # Dashboard theo dõi realtime thu nhập & traffic
├── wipter-token-refresher.py   # Tự động làm mới Access Token từ AWS Cognito
├── residential_proxies.txt     # File danh sách proxy residential (đã kèm sẵn 6 node mẫu)
├── proxies.txt.example         # File mẫu các định dạng proxy được hỗ trợ
├── app/                        # Mã nguồn headless Wipter & mock-electron
├── config/                     # Chứa secure-credentials.json & refresh_token.txt
└── resources/                  # Chứa binary wipter-tunnel (x86_64 & arm64 tĩnh)
```

---

## 🚀 2. Cách Chuyển Thư Mục Sang Máy x86 Khác

### Bước 2.1: Nén thư mục dự án trên máy hiện tại
Tại máy ARM hiện tại, chạy lệnh:
```bash
cd /root
tar -czvf wipter-x86-deploy.tar.gz wipter-x86-deploy/
```

### Bước 2.2: Copy sang máy x86 qua SCP / SFTP
```bash
# Thay thế IP_MAY_X86 bằng địa chỉ IP của máy x86 đích
scp /root/wipter-x86-deploy.tar.gz root@IP_MAY_X86:/root/
```

### Bước 2.3: Giải nén trên máy x86
Trên máy x86, chạy lệnh:
```bash
cd /root
tar -xzvf wipter-x86-deploy.tar.gz
cd wipter-x86-deploy
```

---

## 🛠️ 3. Triển Khai Trên Máy x86

### Bước 3.1: Build Docker Image
Trên máy x86, chạy lệnh sau để build image `wipter-node:latest`:
```bash
docker build -t wipter-node:latest .
```
*(Image sẽ tự động tích hợp binary `wipter-tunnel` dành riêng cho kiến trúc x86_64).*

### Bước 3.2: Chuẩn bị danh sách Proxy
Tạo file `proxies.txt` hoặc dùng file `residential_proxies.txt` có sẵn. Các định dạng được hỗ trợ:
```text
http://username:password@ip:port
socks5://username:password@ip:port
ip:port:username:password
ip:port
```

Nếu có một danh sách proxy lớn chưa biết IP nào là Residential, chạy bộ lọc tự động:
```bash
python3 check-proxies.py -i proxies.txt -o residential_proxies.txt
```
*(Script sẽ chỉ lọc các IP có ISP gia đình, loại bỏ hoàn toàn Datacenter/Hosting).*

### Bước 3.3: Khởi chạy hàng loạt Node
Chạy lệnh triển khai:
```bash
# Khởi chạy tất cả proxy có trong residential_proxies.txt
python3 deploy-nodes.py -p residential_proxies.txt

# Hoặc giới hạn số lượng (ví dụ chỉ chạy 20 node đầu tiên):
python3 deploy-nodes.py -p residential_proxies.txt -l 20
```

*Mỗi node sẽ:*
* Chạy riêng biệt trong một Docker container.
* Gán giới hạn RAM (`--memory=256m`) để máy chủ không bao giờ bị tràn RAM khi chạy số lượng lớn.
* Mở một cổng HTTP API riêng (`19001`, `19002`,...) để giám sát.
* Có machine-id độc lập để Wipter backend ghi nhận thiết bị mới.

---

## 📊 4. Giám Sát & Quản Trị

### Xem bảng trạng thái realtime (Realtime Dashboard)
```bash
python3 wipter-status.py
```
*Hiển thị bảng chi tiết: Tên container, Trạng thái (Online 🟢), Loại IP, Địa điểm (Quốc gia/Thành phố), Dung lượng đã share (MB) và Tiền đã kiếm được (USD).*

### Dừng và xóa toàn bộ các node khi cần bảo trì
```bash
python3 deploy-nodes.py --stop-all
```

---

## 🔄 5. Cơ Chế Tự Động Làm Mới Token (Cronjob)

Wipter dùng AWS Cognito JWT token (hết hạn sau 24 giờ). Để các node hoạt động liên tục 24/7 không bao giờ bị văng (`EXPIRED_TOKEN`):

Trên máy x86, hãy thêm cronjob tự động làm mới token mỗi 12 giờ:
```bash
crontab -e
```
Thêm dòng sau vào cuối:
```cron
0 */12 * * * cd /root/wipter-x86-deploy && python3 wipter-token-refresher.py >> /var/log/wipter-refresh.log 2>&1
```

Script này sẽ tự động gọi API AWS Cognito để lấy AccessToken mới và đồng bộ tức thời vào tất cả các node đang chạy.
