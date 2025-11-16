# -*- coding: utf-8 -*-
"""
Coze模块认证中间件
从 flask_web_server.py 和 certutil.py 提取并适配 FastAPI
"""

import os
import requests
from typing import Optional
from fastapi import HTTPException, Request

from .config import get_coze_config
from .logging_config import get_coze_logger

logger = get_coze_logger()
config = get_coze_config()


def verify_jwt_token(http_scheme: str, request_host: str, root_token: str) -> bool:
    """
    验证JWT token
    
    Args:
        http_scheme: HTTP协议方案（http:// 或 https://）
        request_host: 请求主机
        root_token: JWT token
    
    Returns:
        bool: 验证是否通过
    
    Raises:
        requests.exceptions.HTTPError: HTTP错误
        Exception: 其他错误
    """
    logger.info(f"Verify jwt token: scheme[{http_scheme}]")
    logger.info(f"Verify jwt token: host[{request_host}]")
    logger.info(f"Verify jwt token: token[{root_token[:20]}...]")
    
    request_url = http_scheme + request_host + "/api/v1/uc/verify_jwt_token"
    
    try:
        response = requests.post(
            request_url,
            headers={
                'Authorization': root_token,
                'HtyHost': request_host
            }
        )
        
        # 如果响应不成功，抛出异常
        response.raise_for_status()
        
        logger.info('Verify jwt token success')
        json_string = response.json()
        return json_string.get('r', False)
        
    except requests.exceptions.HTTPError as http_err:
        logger.error(f'Verify jwt token fail with http error occurred: [{http_err}]')
        raise http_err
    except Exception as err:
        logger.error(f'Verify jwt token fail with other error occurred: [{err}]')
        raise err


async def verify_request_header_host_token(request: Request) -> bool:
    """
    FastAPI依赖函数：验证请求头中的token和host
    
    Args:
        request: FastAPI请求对象
    
    Returns:
        bool: 验证是否通过
    
    Raises:
        HTTPException: 验证失败时抛出
    """
    # 检查是否启用身份验证
    if not config.enable_auth:
        logger.info("Authentication disabled, skipping verification")
        return True
    
    # 从请求头获取token和host
    hty_sudoer_token = request.headers.get("HtySudoerToken")
    hty_host = request.headers.get("HtyHost")
    
    logger.info(f"HtySudoerToken :  [{hty_sudoer_token[:20] if hty_sudoer_token else None}...]")
    logger.info(f"HtyHost :  [{hty_host}]")
    
    if not hty_sudoer_token:
        logger.error("HtySudoerToken not found in header.")
        raise HTTPException(
            status_code=401,
            detail="HtySudoerToken not found in header"
        )
    
    if not hty_host:
        logger.error("HtyHost not found in header.")
        raise HTTPException(
            status_code=401,
            detail="HtyHost not found in header"
        )
    
    logger.info(f"Request header host :  [{hty_host}]")
    
    # 检查请求host
    validated_host = None
    if config.alchemy_host in hty_host:
        logger.info(f"Request header host :  [{hty_host}] valid (alchemy).")
        validated_host = "admin." + config.alchemy_host
    elif config.moicen_host in hty_host:
        logger.info(f"Request header host :  [{hty_host}] valid (moicen).")
        validated_host = "admin." + config.moicen_host
    elif config.huiwings_host in hty_host:
        logger.info(f"Request header host :  [{hty_host}] valid (huiwings).")
        validated_host = "admin." + config.huiwings_host
    elif config.local_host in hty_host:
        logger.info(f"Request header host :  [{hty_host}] valid (local).")
        validated_host = "admin." + config.local_host
    else:
        logger.error(f"Request header host :  [{hty_host}] invalid.")
        raise HTTPException(
            status_code=401,
            detail="Request header host invalid"
        )
    
    # 验证JWT token
    try:
        verify_response = verify_jwt_token(
            config.http_scheme,
            validated_host,
            hty_sudoer_token
        )
        logger.info(f"Verify response token result is : [{verify_response}]")
        
        if not verify_response:
            logger.error("JWT token verification failed")
            raise HTTPException(
                status_code=401,
                detail="JWT token verification failed"
            )
        
        return True
        
    except requests.exceptions.HTTPError as http_err:
        logger.error(f"JWT token verification HTTP error: {http_err}")
        raise HTTPException(
            status_code=401,
            detail=f"JWT token verification failed: {str(http_err)}"
        )
    except Exception as err:
        logger.error(f"JWT token verification error: {err}")
        raise HTTPException(
            status_code=401,
            detail=f"JWT token verification failed: {str(err)}"
        )

