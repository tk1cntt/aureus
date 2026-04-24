---
phase: quick-260424-sbg
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - .planning/quick/260424-sbg-ph-n-ti-ch-nguy-n-nh-n-timeout-cu-a-lu-n/260424-sbg-REPORT.md
  - .planning/quick/260424-sbg-ph-n-ti-ch-nguy-n-nh-n-timeout-cu-a-lu-n/260424-sbg-SUMMARY.md
  - .planning/STATE.md
autonomous: true
requirements:
  - QUICK-260424-SBG
---

<objective>
Phân tích nguyên nhân timeout trong luồng dispatch order (ACK timeout, Result timeout, NACK DUPLICATE) dựa trên log đã cung cấp và code hiện tại, sau đó tạo report hành động.
</objective>

<tasks>
<task type="auto">
  <name>Task 1: Thu thập bằng chứng và dựng timeline</name>
  <files>services/aureus-trader/dispatcher.py, services/aureus-trader/main.py, mql5/AureusProvider.mq5</files>
  <action>Đối chiếu thứ tự timeout trong log với cơ chế ack/result wait, retry, idempotency phía trader và EA để xác định điểm nghẽn.</action>
  <verify><manual>Timeline trong report khớp log theo mốc thời gian và hành vi code.</manual></verify>
</task>

<task type="auto">
  <name>Task 2: Viết report nguyên nhân gốc + khuyến nghị</name>
  <files>.planning/quick/260424-sbg-ph-n-ti-ch-nguy-n-nh-n-timeout-cu-a-lu-n/260424-sbg-REPORT.md</files>
  <action>Tạo report gồm: root cause, contributing factors, mức độ tin cậy, hành động fix ngắn hạn/trung hạn, checklist verify.</action>
  <verify><manual>Report có đủ evidence, giả thuyết, và action items có thể thực thi.</manual></verify>
</task>
</tasks>
