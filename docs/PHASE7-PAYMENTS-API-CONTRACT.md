# Phase 7 Payments API Contract

Base path: `/api/v1/payments`

All amounts are in paisa.

## 1) Create payment

`POST /api/v1/payments`

Request:

```json
{
  "order_id": "uuid",
  "method_code": "cash",
  "amount": 250000,
  "tendered_amount": 300000,
  "reference": "optional",
  "note": "optional"
}
```

Response `201` (`PaymentSummary`):

```json
{
  "order_id": "uuid",
  "order_total": 450000,
  "paid_amount": 250000,
  "refunded_amount": 0,
  "due_amount": 200000,
  "payment_status": "partial",
  "payments": []
}
```

## 2) Split payment

`POST /api/v1/payments/split`

Request:

```json
{
  "order_id": "uuid",
  "allocations": [
    { "method_code": "cash", "amount": 100000, "tendered_amount": 120000 },
    { "method_code": "card", "amount": 150000, "reference": "TXN-445" }
  ],
  "note": "optional"
}
```

Response `201`: `PaymentSummary`

## 3) Refund

`POST /api/v1/payments/refund`

Request:

```json
{
  "payment_id": "uuid",
  "amount": 50000,
  "note": "optional"
}
```

Response `201`: `PaymentSummary`

## 4) Drawer status

`GET /api/v1/payments/drawer/session`

Response `200`:
- `null` when no open session
- `CashDrawerSessionResponse` when session is open

## 5) Drawer open

`POST /api/v1/payments/drawer/open`

Request:

```json
{
  "opening_float": 50000,
  "note": "optional"
}
```

Response `201`: `CashDrawerSessionResponse`

## 6) Drawer close

`POST /api/v1/payments/drawer/close`

Request:

```json
{
  "closing_balance_counted": 285000,
  "note": "optional"
}
```

Response `200`: `CashDrawerSessionResponse` (closed session snapshot)

## Supporting endpoints

- `GET /api/v1/payments/methods`
- `GET /api/v1/payments/orders/{order_id}/summary`
