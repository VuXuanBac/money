# MoneyApp

Ứng dụng quản lý chi tiêu trên giao diện console với các chức năng sau:

- Quản lý theo tài khoản, ví, thanh khoản, các giao dịch, hạng mục (để nhóm các giao dịch)
- Quản lý các giao dịch mức độ chi tiết hơn như giao dịch đặt hàng, các giao dịch chia sẻ chi tiêu với nhiều người
- Lưu dữ liệu giao dịch từ một ứng dụng ghi chú (Notesnook) hoặc từ tệp cục bộ trên máy với nhiều định dạng khác nhau (CSV, JSON, YAML)
- Báo cáo chi tiêu cá nhân, chi tiêu theo nhóm, tính toán chia sẻ từng người trong nhóm sau mỗi dịp tổng kết
- Xuất báo cáo giao dịch ra tệp (hỗ trợ thêm xuất ra HTML)

Cụ thể:

- `import`: Nạp các ghi chú từ một tệp trên máy (định dạng CSV, JSON, YAML) hoặc từ [Notesnook Monograph](https://monogr.ph/) (giao diện bảng)
  - Có thể lưu sẵn các đường dẫn và cấu hình cơ bản cho các kho lưu trữ này với lệnh `create resource`
- `report`: Tổng kết các giao dịch theo thời gian, người gửi, người nhận, đơn vị tiền tệ,... và tạo báo cáo: Số lượng tiền vào và ra theo từng hạng mục và tài khoản (ví, tài khoản người dùng)
  - Có thể lưu các báo cáo này vào database qua đối số `--save`
- `event`: Tổng kết các giao dịch chia sẻ với nhiều người
  - Các giao dịch này gọi là `Sharing`
  - Trong đó mỗi giao dịch xác định thêm những người chia sẻ chi phí của giao dịch và tỷ lệ chia sẻ (tương đối) của từng người
  - Các giao dịch thuộc vào event sẽ được đánh dấu bằng một tag. Ví dụ với event `Tổng kết chi tiêu tháng 12 của phòng 07` thì có thể tạo tag là `dec24`
  - Có thể lưu báo cáo này vào database qua đối số `--save`

## Chạy ứng dụng

1. Đổi đường dẫn tới tệp để lưu dữ liệu của database tại [biến `DATABASE_NAME` tệp main.py](money/main.py)
2. Tải các thư viện của ứng dụng

```
python = "^3.10"
cmdapp = {path = "https://github.com/VuXuanBac/cmdapp"}
beautifulsoup4 = "^4.12.3"
requests = "^2.32.3"
```

3. `python -m money.main`
