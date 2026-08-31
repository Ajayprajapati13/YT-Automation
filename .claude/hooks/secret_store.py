#!/usr/bin/env python3
"""Windows DPAPI-backed local secret storage for the supervisor.

The encrypted blob is stored outside the repository under %LOCALAPPDATA%.
DPAPI CurrentUser scope means only the same Windows user on the same machine
can normally decrypt it.
"""
from __future__ import annotations

import ctypes
import os
from ctypes import wintypes
from pathlib import Path

STORE_DIR = Path(os.environ.get("LOCALAPPDATA", "")) / "YT-Automation"
STORE_PATH = STORE_DIR / "openai_api_key.dpapi"

class DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_ubyte))]


def _blob(data: bytes):
    buf = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
    return DATA_BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_ubyte))), buf


def _bytes(blob: DATA_BLOB) -> bytes:
    if not blob.cbData or not blob.pbData:
        return b""
    return ctypes.string_at(blob.pbData, blob.cbData)


def _crypt32():
    if os.name != "nt":
        raise RuntimeError("DPAPI secret storage is supported only on Windows")
    dll = ctypes.WinDLL("crypt32", use_last_error=True)
    dll.CryptProtectData.argtypes = [
        ctypes.POINTER(DATA_BLOB), wintypes.LPCWSTR, ctypes.POINTER(DATA_BLOB),
        wintypes.LPVOID, wintypes.LPVOID, wintypes.DWORD, ctypes.POINTER(DATA_BLOB)
    ]
    dll.CryptProtectData.restype = wintypes.BOOL
    dll.CryptUnprotectData.argtypes = [
        ctypes.POINTER(DATA_BLOB), ctypes.POINTER(wintypes.LPWSTR), ctypes.POINTER(DATA_BLOB),
        wintypes.LPVOID, wintypes.LPVOID, wintypes.DWORD, ctypes.POINTER(DATA_BLOB)
    ]
    dll.CryptUnprotectData.restype = wintypes.BOOL
    return dll


def _local_free(pointer) -> None:
    # CryptProtectData/CryptUnprotectData allocate returned buffers with
    # LocalAlloc; LocalFree is exported by kernel32, not crypt32.
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.LocalFree.argtypes = [wintypes.HLOCAL]
    kernel32.LocalFree.restype = wintypes.HLOCAL
    if pointer:
        kernel32.LocalFree(pointer)


def protect(secret: str) -> None:
    if not secret:
        raise ValueError("Secret is empty")
    dll = _crypt32()
    source, source_buf = _blob(secret.encode("utf-8"))
    protected = DATA_BLOB()
    if not dll.CryptProtectData(ctypes.byref(source), "YT-Automation OpenAI API key", None, None, None, 0, ctypes.byref(protected)):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        STORE_DIR.mkdir(parents=True, exist_ok=True)
        tmp = STORE_PATH.with_suffix(".tmp")
        tmp.write_bytes(_bytes(protected))
        os.replace(tmp, STORE_PATH)
    finally:
        if protected.pbData:
            _local_free(protected.pbData)
        _ = source_buf


def unprotect() -> str | None:
    if os.name != "nt" or not STORE_PATH.is_file():
        return None
    encrypted = STORE_PATH.read_bytes()
    if not encrypted:
        return None
    dll = _crypt32()
    source, source_buf = _blob(encrypted)
    decrypted = DATA_BLOB()
    if not dll.CryptUnprotectData(ctypes.byref(source), None, None, None, None, 0, ctypes.byref(decrypted)):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return _bytes(decrypted).decode("utf-8")
    finally:
        if decrypted.pbData:
            _local_free(decrypted.pbData)
        _ = source_buf


def has_secret() -> bool:
    return STORE_PATH.is_file() and STORE_PATH.stat().st_size > 0
