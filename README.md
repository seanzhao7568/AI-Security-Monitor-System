#AI安全監控系統（AI Security Monitoring System）

1.專案介紹
本專案為一套即時 AI 安全監控系統，能夠在公共或個人環境中即時偵測潛在危險。
系統整合電腦視覺、姿態辨識與聲音分析，可偵測：
 人物靠近
 武器（刀 / 槍）
 攻擊性行為
 異常巨大聲響
當系統判斷風險時，會即時觸發警報並可透過 Telegram 發送通知。

2.系統特色
 使用 YOLOv8 進行即時物件偵測
 姿態辨識分析攻擊行為
 聲音分貝（dB）監測異常聲響
 風險評分機制（Risk Scoring）
 智慧警報系統（避免重複觸發）

3.技術架構
 Python
 OpenCV
 YOLOv8（Ultralytics）
 Flask
 Pygame
 Telegram Bot API

4.專案結構
AI-Security-Monitor-System/
--app.py
--config.py
--monitor/

--web/
--assets/
--requirements.txt
--models/模型因檔案過大未上傳

5.安裝方式
pip install -r requirements.txt

6.執行方式
python app.py

7.test畫面
![weapon](https://github.com/user-attachments/assets/d9dd5770-4cbc-4e9f-9a0e-e071e6b503bf)
![LOUD](https://github.com/user-attachments/assets/cb23f6d2-9c18-497b-a398-2de98c1d1d43)
![AGG](https://github.com/user-attachments/assets/2063b369-ef4d-490f-83ff-a57c970ef30c)
![PC](https://github.com/user-attachments/assets/9b3270a7-883e-4523-8360-a8814129e670)

本專案為結合電腦視覺與多模態分析的 AI 安全監控系統，具備即時危險偵測與警報能力。
