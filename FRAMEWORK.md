# TRONIFY 兩種會員路徑

從 Telegram 機器人打開頁面後，系統只分兩種人。

## 1. 新註冊（還沒綁過錢包）

1. 機器人帶 `tg_id` 打開頁面
2. `/api/user_status` 回 `registered: false`
3. 使用者點連接錢包
4. 選 TronLink / TokenPocket / imToken
5. WalletConnect（或錢包內建瀏覽器）授權
6. 簽名（不是轉帳）
7. `POST /api/bind`，`intent=register`
8. 回機器人：`?start=bind_地址`

## 2. 切換錢包（這個 Telegram 已經綁過）

1. `/api/user_status` 回 `registered: true` + 舊地址
2. 頁面打開「這個帳號已綁過錢包」
3. 選「切換錢包」
4. 再走授權 + 簽名
5. `POST /api/bind`，`intent=switch`
6. 回機器人：`?start=switch_新地址`

選「新註冊」會清掉本機舊狀態，再當第一次加入。
