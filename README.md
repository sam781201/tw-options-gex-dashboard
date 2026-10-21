# 台指選擇權 GEX / VEX 盤後曝險研究儀表板

免費、靜態 GitHub Pages 網頁，GitHub Actions 在交易日盤後嘗試抓取期交所公開資料。**不含虛構即時數據**。

## 一次性部署
1. 上傳 `docs/`, `scripts/`, `.github/` 等目錄到 GitHub 主分支。
2. Settings → Pages → Build and deployment → Deploy from a branch，選 `main` / `/docs`，Save。
3. Actions → Update TAIFEX TXO Data → Run workflow，檢查執行結果與 `docs/data.json`。
4. 成功後開 `https://<帳號>.github.io/<儲存庫名稱>/`。

## 重要注意
* GitHub Actions 定時排程採 UTC 10:30、12:30、14:30（臺灣 18:30、20:30、22:30），僅週一至週五；假日可能沿用最近一次有效快照。GitHub 排程可能延遲或被停用。
* 期交所 API schema/端點可能調整：程式預設嘗試 `DailyMarketReportOpt` 與 `DailyMarketReportOption`；若抓取失敗，必須核對期交所 [OpenAPI 文件](https://openapi.taifex.com.tw/) 後設定 `TAIFEX_OPTION_URL`。目前尚未在線上成功測試端點，**自動更新不保證已可用**。
* 原始「造市商」淨持倉不公開。以全部未平倉量代替其部位，並採簡化方向假設，數字僅用於情境研究。
* 本儀表板的 `GEX+` 定義為**正 GEX 加總**，而不是原圖作者尚未公開的公式。
* 單靠盤後 OI 無法合理判斷強多或強空。故方向狀態保守顯示未確認；未來接上具時間序列的價格、歷史 IV、成交量資料，才可驗證與開啟五種行情分類。
* Spot、IV、距到期日由使用者輸入。預填價格只是履約價中位數，**不是最新指數值**。
* Put/Call Wall 依模型下各方 Gamma 絕對曝險最高之履約價估計，並非保證的支撐或壓力。
* Black–Scholes 模型用以計算 Greeks 近似，並非交易所官方 Greeks。VEX 是 Vanna 曝險簡化代理；注意方向、單位與資料誤差。

## 本機處理資料
Python 3.12+，僅標準函式庫：
```bash
python scripts/update_data.py
```
成功時寫入 `docs/data.json`，失敗時退出且**不覆蓋舊資料**。

## 後續升級
加入可驗證的期貨收盤價趨勢（日 K / MA5 / MA20 / MA60）、成交量、IV 序列、PCR、波動率與回測後，才啟用「強多／偏多／盤整／偏空／強空」和具體策略風險比對。這些數據不得以無根據的固定數值替代。
