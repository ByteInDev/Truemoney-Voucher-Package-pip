<br>

<div align="center">

# Truemoney-Voucher (pip)

**ไคลเอนต์แบบ zero-dependency สำหรับ REST APIs ของ Truemoney-Voucher** — แลกรับ TrueMoney gift voucher จาก pip, uv, poetry หรือ Python runtime ใดก็ได้

![License: MIT](https://img.shields.io/badge/license-MIT-yellow.svg)
![Python](https://img.shields.io/badge/Python-%3E%3D3.10-3776AB?logo=python&logoColor=white)
![Zero dependencies](https://img.shields.io/badge/dependencies-0-6DA55F)
![PyPI version](https://img.shields.io/pypi/v/truemoney-voucher)

[English](README.md) - **ไทย**

</div>

---

ไคลเอนต์แบบ zero-dependency สำหรับตระกูล API [Truemoney-Voucher](https://github.com/ByteInDev) — มี backend สามตัวที่ใช้ HTTP contract เดียวกัน **และไคลเอนต์เลือกตัวที่เร็วที่สุดให้อัตโนมัติ**:

| Provider | Backend | ที่อยู่ |
| --- | --- | --- |
| `auto` (ค่าเริ่มต้น) | probe ทั้งสามตัว ใช้ตัว healthy ที่เร็วที่สุด | failover อัตโนมัติเมื่อ network error |
| `go` | [Go](https://github.com/ByteInDev/Truemoney-Voucher-Go) (uTLS `HelloFirefox_148` + HTTP/2 framer) | https://truemoney-voucher-go.vercel.app |
| `nestjs` | [NestJS](https://github.com/ByteInDev/Truemoney-Voucher-NestJS) (cycletls Firefox 148 fingerprint) | https://truemoney-voucher-nestjs.vercel.app |
| `fastapi` | [FastAPI](https://github.com/ByteInDev/Truemoney-Voucher-FastAPI) (curl_cffi Firefox 147 fingerprint) | https://truemoney-voucher-fastapi.vercel.app |

## ความสามารถ

| ความสามารถ | รายละเอียด |
| ----------- | ----------- |
| แลกรับโค้ด | `Client.redeem(code, mobile)` — ใส่โค้ดตรงๆ หรือลิงก์เต็ม `gift.truemoney.com` ก็ได้ |
| Auto provider | ค่าเริ่มต้น `'auto'` — probe ทุก backend แล้วใช้ตัว healthy ที่เร็วสุด พร้อม failover เมื่อ network error |
| Static API | `from truemoney_voucher import Client` — ไม่ต้องสร้าง instance ไม่ต้อง config แค่ `Client.redeem(...)` |
| Zero dependencies | Python standard library ล้วน — `urllib` + `threading` ไม่มี install deps |
| รันได้ทุกที่ | CPython >= 3.10 (ทดสอบถึง 3.14) — stdlib-only ไม่มี compiled extensions |
| Error แบบมี type | `TruemoneyApiError`, `TruemoneyTimeoutError`, `TruemoneyError` พร้อมเข้าถึง envelope ได้ |

## เริ่มต้นใช้งาน

ติดตั้งด้วย package manager ตัวไหนก็ได้:

```bash
pip install truemoney-voucher
# หรือ
uv add truemoney-voucher
# หรือ
poetry add truemoney-voucher
```

ไม่ต้องตั้งค่าอะไร — `Client` คือ static wrapper พร้อมใช้ ครอบ instance ที่ config แบบ auto ให้แล้ว:

```python
from truemoney_voucher import Client

# auto: probe backend สามตัวที่โฮสต์อยู่ แล้วใช้ตัว healthy ที่เร็วที่สุด
result = Client.redeem("12345678901234", "0812345678")
print(result.status.code)  # เช่น "VOUCHER_NOT_FOUND", "TARGET_USER_REDEEMED"

# ตรวจว่า service ยังทำงานอยู่:
alive = Client.status()

# ข้อมูลบริการ:
info = Client.info()
```

### เลือก provider เอง (หรือใช้ deployment ของตัวเอง)

```python
from truemoney_voucher import create_client

# เลือก backend ตัวใดตัวหนึ่งจากสามตัวที่โฮสต์อยู่:
client = create_client(provider="nestjs")  # "go" | "nestjs" | "fastapi"

# หรือใช้ base URL ของตัวเอง (ชนะ `provider` เสมอ):
custom = create_client(
    base_url="https://api.example.com",
    timeout_ms=15_000,
)

# Client.configure() สร้าง instance ใหม่ด้วยวิธีเดียวกัน:
Client.configure(provider="fastapi")
```

## API Reference

### Static `Client` (ไม่ต้องสร้าง instance)

| Method | คำอธิบาย |
| --- | --- |
| `Client.redeem(code, mobile)` | แลกรับโค้ดตรงๆ หรือ campaign URL เต็ม ผ่าน backend healthy ที่เร็วที่สุด |
| `Client.status()` | `True` เมื่อมี backend อย่างน้อยหนึ่งตัวตอบ 2xx ที่ `/status` |
| `Client.info()` | service info + routes ของ backend ที่เลือก |
| `Client.configure(**kwargs)` | แทนที่ instance ร่วม (ค่าเริ่มต้น auto) |

### `create_client(**kwargs) => TruemoneyClient`

| ตัวเลือก | Type | ค่าเริ่มต้น | คำอธิบาย |
| --- | --- | --- | --- |
| `provider` | `str` | `'auto'` | backend ที่จะเรียก — `'auto'` probe แล้วเลือกตัว healthy ที่เร็วสุด |
| `base_url` | `str \| None` | URL ของ provider | base URL เต็ม (ชนะ `provider`) |
| `timeout_ms` | `int` | `30_000` | หมดเวลา per-request |
| `urlopen` | `callable` | `urllib.request.urlopen` | opener แบบกำหนดเอง (ทดสอบ, proxy) |
| `user_agent` | `str \| None` | `truemoney-voucher/1.1.0` | header `User-Agent` |
| `headers` | `dict[str, str]` | — | header เพิ่มเติมในทุก request |

### Auto provider

- ใน request แรก (หรือเมื่อ cache 60 วินาทีหมดอายุ) backend ทั้งสามจะถูก probe พร้อมกัน (thread pool, `GET /status`, probe timeout 3 วินาที) และจัดอันดับตาม latency
- `redeem`, `status()` และ `info()` ไปที่ backend healthy ที่เร็วที่สุด — การจัดอันดับ cache ไว้ 60 วินาที
- ถ้า redeem ล้มเหลวด้วย **network error** ไคลเอนต์ลอง backend healthy ตัวถัดไปอัตโนมัติ — validation error (`TruemoneyApiError`) **ไม่** trigger failover เพราะ redeem ใช้ครั้งเดียว ย้อนไม่ได้ failover แล้วก็ไม่ซ้ำ — กรณีแย่สุดแค่ `TARGET_USER_REDEEMED`
- `client.explicit_base_url` คืน base URL ของ backend ที่เลือกแบบชัดเจน (`None` สำหรับ auto)

### `client.redeem(code, mobile) => RedeemResult`

รับโค้ดตรงๆ **หรือ** ลิงก์เต็ม campaign URL (percent-encode ลงใน path —
backend รักษา `%2F` ไว้ ตรงกับ CLI ต้นฉบับ)

- สำเร็จ → คืน `RedeemResult(ok=True, status=TrueMoneyStatus(message, code), data=...)` เมื่อ upstream call สำเร็จ
- ผิดพลาด → raise `TruemoneyApiError` สำหรับ validation/routing errors (`{ code, message }` envelope หรือ error body แบบ Spring ที่ normalize ให้แล้ว)

### `client.status() => bool`

`True` เมื่อได้ 2xx, `False` เมื่ออื่นๆ — ไม่ raise เด็ดขาด ปลอดภัยสำหรับ uptime checks
โหมด auto: `True` เมื่อมี backend อย่างน้อยหนึ่งตัว healthy

### `client.info() => dict`

ชื่อ service, เวอร์ชันที่ deploy (ถ้ามีการ expose), และรายการ routes

### Errors

| Error | เมื่อเกิด |
| --- | --- |
| `TruemoneyApiError` | API ตอบ `{ code, message }` (validation 400, not found 404, …) หรือ error body แบบ Spring — เปิดดู `status`, `code`, `envelope` ได้ |
| `TruemoneyTimeoutError` | ไม่มีการตอบกลับภายใน `timeout_ms` |
| `TruemoneyError` | network ล้มเหลว, response ไม่ใช่ JSON, envelope แปลกๆ |

ทุก error สืบทอดจาก `TruemoneyError`:

```python
from truemoney_voucher import TruemoneyApiError

try:
    Client.redeem(code, mobile)
except TruemoneyApiError as err:
    print(err.code, err.message)  # 400 "Bad Request"
```

## TrueMoney status codes

เมื่อ upstream call สำเร็จ `result.status.code` จะมีคำตอบของ TrueMoney:

| Code | ความหมาย |
| ---- | -------- |
| `SUCCESS` | รับเงินสำเร็จ |
| `TARGET_USER_REDEEMED` | คุณแลกโค้ดนี้ไปแล้ว |
| `VOUCHER_OUT_OF_STOCK` | คนอื่นแลกไปแล้ว |
| `VOUCHER_EXPIRED` | วอเล็ต voucher หมดอายุแล้ว |
| `VOUCHER_NOT_FOUND` | ไม่พบโค้ดในระบบ |
| `CANNOT_GET_OWN_VOUCHER` | แลกโค้ดของตัวเองไม่ได้ |
| `TARGET_USER_NOT_FOUND` | ไม่พบเบอร์โทรศัพท์ในระบบ |
| `INTERNAL_ERROR` | ไม่พบโค้ด หรือ URL ผิด |

## การทดสอบ

```bash
pip install -e ".[dev]"
pytest tests/test_client.py tests/test_auto_client.py   # unit tests แบบ offline
set LIVE=1 && pytest tests/test_live.py                 # ตรวจกับ backend ที่โฮสต์อยู่ทั้งสามตัวแบบ real
```

ชุดเทสต์แบบ live รัน `status`/`info` และตรวจ invalid voucher กับ Vercel
deployments ทั้งสามตัว บวก upstream call จริง

## Contributing

ยินดีรับ contribution! กรุณา:

1. เปิด issue ก่อนสำหรับการเปลี่ยนแปลงใหญ่ๆ
2. รักษา `pytest tests` ให้เขียวเสมอ
3. เพิ่ม `version` ใน `pyproject.toml` พร้อมกับ `src/truemoney_voucher/version.py`

## ข้อควรทราบ

> **สำหรับการศึกษาหรือที่ผู้ให้บริการอนุญาตเท่านั้น**
> การแลกโค้ดย้อนกลับไม่ได้ และอยู่ภายใต้ข้อกำหนดการใช้งานของ TrueMoney
> โค้ด voucher เทียบเท่าเงินสด — อย่า log โค้ดเต็ม

## License

Licensed under the [MIT License](./LICENSE) © 2026 ByteInDev