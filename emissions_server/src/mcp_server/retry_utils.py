"""
Retry utilities for Emissions Server.

This module provides decorators for retry logic and fallback mechanisms
to handle transient errors and provide graceful degradation.
"""

import time
import random
import logging
from typing import Any, Callable, Type, TypeVar, Union, Optional, cast, Tuple
from functools import wraps

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("climatemcp.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("climatemcp")

# Type variables for better type checking
F = TypeVar('F', bound=Callable[..., Any])
T = TypeVar('T')
ExceptionType = Union[Type[Exception], Tuple[Type[Exception], ...]]

def retry(exceptions: ExceptionType, tries: int = 4, delay: float = 3, 
          backoff: float = 2, logger: Optional[logging.Logger] = None) -> Callable[[F], F]:
    """
    Retry decorator with exponential backoff.
    
    Args:
        exceptions: Exception or tuple of exceptions to catch
        tries: Number of times to try before giving up
        delay: Initial delay between retries in seconds
        backoff: Backoff multiplier (e.g. value of 2 will double the delay each retry)
        logger: Logger to use. If None, print is used.
    
    Returns:
        Decorated function that will retry on specified exceptions
    """
    def deco_retry(func: F) -> F:
        @wraps(func)
        def f_retry(*args: Any, **kwargs: Any) -> Any:
            mtries, mdelay = tries, delay
            while mtries > 1:
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    msg = f"{func.__name__}: {str(e)}, retrying in {mdelay} seconds..."
                    if logger:
                        logger.warning(msg)
                    else:
                        print(msg)
                    time.sleep(mdelay)
                    mtries -= 1
                    mdelay *= backoff
                    # Add some randomness to prevent overloading
                    mdelay += random.uniform(0, 1)
            
            # Last attempt
            try:
                return func(*args, **kwargs)
            except exceptions as e:
                msg = f"Error in {func.__name__}: {str(e)} (after {tries} attempts)"
                if logger:
                    logger.error(msg)
                else:
                    print(msg)
                raise  # Re-raise the last exception
        return cast(F, f_retry)
    return deco_retry

def fallback(default_return: Any = None, logger: Optional[logging.Logger] = None) -> Callable[[F], F]:
    """
    Fallback decorator that returns a default value if the function fails.
    
    Args:
        default_return: Value or function to return if the function fails.
                        If callable, it will be called with the exception.
        logger: Logger to use. If None, print is used.
    
    Returns:
        Decorated function that will return a fallback value on exception
    """
    def deco_fallback(func: F) -> F:
        @wraps(func)
        def f_fallback(*args: Any, **kwargs: Any) -> Any:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                msg = f"Error in {func.__name__}: {str(e)}, using fallback value"
                if logger:
                    logger.warning(msg)
                else:
                    print(msg)
                
                # If default_return is callable, call it with the error
                if callable(default_return):
                    return default_return(e)
                return default_return
        return cast(F, f_fallback)
    return deco_fallback