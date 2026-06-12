from slowapi import Limiter
from fastapi import Request

def get_real_ip(request: Request) -> str:
    # Check for Cloudflare specific header first
    cf_ip = request.headers.get("CF-Connecting-IP")
    if cf_ip:
        return cf_ip
        
    # Fallback to standard forwarded-for
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
        
    # Final fallback to standard client host
    return request.client.host if request.client else "127.0.0.1"

limiter = Limiter(key_func=get_real_ip)
