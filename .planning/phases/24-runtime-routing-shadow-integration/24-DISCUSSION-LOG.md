# Phase 24: Runtime Routing & Shadow Integration - Discussion Log

**Date:** 2026-04-04

## Area 1: Configuration Hot-Swapping
**Options presented:**
- [A] Thông qua Redis `aureus:sys:config` (có thể đổi nóng chế độ ngay lập tức không cần tắt dịch vụ - Khuyến nghị)
- [B] Qua biến môi trường / `.env` (phải khởi động lại container mỗi khi đổi)
- [C] Cách khác do bạn quyết định
**User selection:** Tùy chọn A (Khuyến nghị)
**Outcome:** Dynamic Redis routing selected.

## Area 2: Shadow Execution Concurrency
**Options presented:**
- [A] Spawn background task bất đồng bộ (async event). Vòng lặp Redis chính vẫn chạy bình thường. (Khuyến nghị)
- [B] Chạy đồng bộ (Sync) ngay trong vòng lặp chính
- [C] Cách khác do bạn quyết định
**User selection:** Tùy chọn A (Khuyến nghị)
**Outcome:** Async shadow processing selected.

## Area 3: Shadow State Isolation
**Options presented:**
- [A] Đẩy vào một namespace hoàn toàn riêng trên Redis, ví dụ `aureus:ai:shadow:{symbol}`. (Khuyến nghị)
- [B] Ghi vào cùng stream/key cũ nhưng nhúng thêm cờ `mode="shadow"`.
- [C] Cách khác do bạn quyết định
**User selection:** Tùy chọn A (Khuyến nghị)
**Outcome:** Dedicated `shadow` Redis namespace selected.

## Area 4: Comparison Baseline
**Options presented:**
- [A] Ghi log và đẩy trực tiếp vào TimescaleDB / Prometheus để phân tích PnL/Drift offline sau này. (Khuyến nghị)
- [B] Bắt engine phải so sánh trực tiếp signal TA với signal cũ ngay tại thời gian thực.
- [C] Cách khác do bạn quyết định
**User selection:** Tùy chọn A (Khuyến nghị)
**Outcome:** Offline validation logging selected.
