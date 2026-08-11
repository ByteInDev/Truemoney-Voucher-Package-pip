"""The three hosted backends behind the Truemoney-Voucher API family.

All three serve the same HTTP contract — only the browser-fingerprint
transport differs (uTLS / cycletls / curl_cffi).
"""

PROVIDERS: dict[str, str] = {
    "go": "https://truemoney-voucher-go.vercel.app",
    "nestjs": "https://truemoney-voucher-nestjs.vercel.app",
    "fastapi": "https://truemoney-voucher-fastapi.vercel.app",
}