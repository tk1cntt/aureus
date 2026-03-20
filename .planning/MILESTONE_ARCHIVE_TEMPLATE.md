# Milestone Archive Template

Mục tiêu: lưu milestone đã hoàn thành theo chuẩn, để `.planning/` chỉ giữ milestone đang active.

---

## 1) Cấu trúc thư mục đề xuất

```text
.planning/
  archive/
    v1.1-signal-optimization/
      SNAPSHOT_DATE.md
      PROJECT.md
      REQUIREMENTS.md
      ROADMAP.md
      STATE.md
      config.json
      specs/
        SPEC_ADAPTIVE_SCORING.md
        SPEC_DECISION_TRACE_SCHEMA.md
        SPEC_ROLLOUT_GATES.md
        SPEC_SIGNAL_STRATEGY_V1.md
        SPEC_STRATEGY_PLUGIN_INTERFACE.md
      process/
        SIGNAL_INTEGRATION_PROCESS.md
      phases/
        01-baseline-parity/
          RESEARCH.md
          PLAN.md
          VALIDATION.md
          SUMMARY.md
        02-plugin-runtime/
          RESEARCH.md
          PLAN.md
          VALIDATION.md
          SUMMARY.md
        03-rollout-gates/
          RESEARCH.md
          PLAN.md
          VALIDATION.md
          SUMMARY.md
      codebase/
        (copy from .planning/codebase at close time)
      outcomes/
        SUMMARY.md
        VERIFICATION.md
        RISKS_AND_FOLLOWUPS.md
```

> Naming convention milestone folder:  
> `v<major>.<minor>-<short-name>`  
> Ví dụ: `v1.1-signal-optimization`.

---

## 2) Nội dung bắt buộc trong archive

### `SNAPSHOT_DATE.md`
- Snapshot timestamp (UTC+7 hoặc UTC, ghi rõ timezone).
- Commit hash tương ứng.
- Người đóng milestone.

### `outcomes/SUMMARY.md`
- Mục tiêu milestone.
- Những gì đã hoàn thành.
- Những gì deferred sang milestone sau.

### `outcomes/VERIFICATION.md`
- Danh sách lệnh test/check đã chạy.
- Kết quả pass/fail cuối cùng.
- Link/log evidence (nếu có).

### `outcomes/RISKS_AND_FOLLOWUPS.md`
- Known limitations.
- Technical debt.
- TODO/next actions cho milestone kế tiếp.

---

## 3) Checklist đóng milestone (copy/paste)

- [ ] `PROJECT.md` phản ánh đúng trạng thái “milestone complete”.
- [ ] `ROADMAP.md` đánh dấu phase đã done + ghi rõ next milestone.
- [ ] `STATE.md` nhất quán với roadmap cuối.
- [ ] Đã chạy health check: `node ".agent/get-shit-done/bin/gsd-tools.cjs" validate health`.
- [ ] Tạo thư mục archive theo naming convention.
- [ ] Copy các file planning chính vào archive.
- [ ] Copy toàn bộ `.planning/codebase/` vào archive snapshot.
- [ ] Tạo thư mục riêng cho từng phase trong `phases/` theo format `NN-phase-name`.
- [ ] Mỗi phase có đủ file tối thiểu: `RESEARCH.md`, `PLAN.md`, `VALIDATION.md`, `SUMMARY.md`.
- [ ] Không dùng chung file markdown giữa các phase.
- [ ] Tạo đầy đủ 3 file outcomes (`SUMMARY.md`, `VERIFICATION.md`, `RISKS_AND_FOLLOWUPS.md`).
- [ ] Ghi snapshot date + commit hash vào `SNAPSHOT_DATE.md`.
- [ ] Re-run health check sau khi archive xong.

---

## 4) Quy ước vận hành

- `.planning/` root chỉ giữ **1 milestone active**.
- Mọi milestone đã hoàn thành phải chuyển vào `.planning/archive/`.
- Mỗi phase trong milestone **phải có folder riêng** dưới `phases/`.
- Không dùng chung file markdown giữa các phase; mỗi phase tự quản lý bộ file của chính nó.
- Không chỉnh sửa archive cũ, trừ khi thêm note correction (append-only).
- Nếu cần tham chiếu lại quyết định cũ, link trực tiếp tới file trong archive milestone tương ứng.

---

## 5) Template nhanh cho `SNAPSHOT_DATE.md`

```md
# Snapshot Metadata

- Milestone: vX.Y-short-name
- Snapshot time: YYYY-MM-DD HH:mm:ss +07:00
- Git commit: <hash>
- Closed by: <name>
- Notes: <optional>
```

## 6) Template nhanh cho `outcomes/SUMMARY.md`

```md
# Milestone Summary

## Goal
...

## Completed
- ...

## Deferred
- ...

## Impact
- ...
```
