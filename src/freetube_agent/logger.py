"""
Logging and Error Handling Module
Provides comprehensive logging, error tracking, and retry mechanisms.
"""

from __future__ import annotations
import logging
import sys
from pathlib import Path
from typing import Optional, Callable, Any
from functools import wraps
from datetime import datetime
import traceback
import json

from .paths import DATA


# Log directory
LOG_DIR = DATA / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Log files
MAIN_LOG = LOG_DIR / "freetube_agent.log"
ERROR_LOG = LOG_DIR / "errors.log"
PERFORMANCE_LOG = LOG_DIR / "performance.log"


class ColoredFormatter(logging.Formatter):
    """Colored console output formatter"""
    
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[32m',       # Green
        'WARNING': '\033[33m',    # Yellow
        'ERROR': '\033[31m',      # Red
        'CRITICAL': '\033[35m',   # Magenta
        'RESET': '\033[0m'        # Reset
    }
    
    def format(self, record):
        if hasattr(sys.stdout, 'isatty') and sys.stdout.isatty():
            levelname = record.levelname
            if levelname in self.COLORS:
                record.levelname = f"{self.COLORS[levelname]}{levelname}{self.COLORS['RESET']}"
        return super().format(record)


def setup_logger(name: str = "freetube_agent", level: int = logging.INFO) -> logging.Logger:
    """
    Set up logger with file and console handlers.
    
    Args:
        name: Logger name
        level: Logging level
    
    Returns:
        Configured logger
    """
    logger = logging.getLogger(name)
    
    # Avoid duplicate handlers
    if logger.handlers:
        return logger
    
    logger.setLevel(level)
    
    # Format
    file_format = logging.Formatter(
        '%(asctime)s | %(name)s | %(levelname)s | %(module)s:%(funcName)s:%(lineno)d | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_format = ColoredFormatter(
        '%(levelname)s | %(message)s'
    )
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)
    
    # Main log file handler
    try:
        file_handler = logging.FileHandler(MAIN_LOG, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(file_format)
        logger.addHandler(file_handler)
    except Exception as e:
        print(f"Warning: Could not create log file handler: {e}")
    
    # Error log file handler
    try:
        error_handler = logging.FileHandler(ERROR_LOG, encoding='utf-8')
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(file_format)
        logger.addHandler(error_handler)
    except Exception as e:
        print(f"Warning: Could not create error log file handler: {e}")
    
    return logger


# Global logger instance
logger = setup_logger()


class ErrorTracker:
    """Track and log errors with context"""
    
    def __init__(self):
        self.error_log_path = LOG_DIR / "error_tracker.json"
        self.errors = self._load_errors()
    
    def _load_errors(self) -> list:
        """Load error history from file"""
        if self.error_log_path.exists():
            try:
                with open(self.error_log_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                return []
        return []
    
    def _save_errors(self):
        """Save error history to file"""
        try:
            with open(self.error_log_path, 'w', encoding='utf-8') as f:
                json.dump(self.errors[-1000:], f, indent=2)  # Keep last 1000 errors
        except Exception as e:
            logger.error(f"Failed to save error history: {e}")
    
    def log_error(
        self,
        error: Exception,
        context: str = "",
        module: str = "",
        function: str = "",
        user_message: str = ""
    ):
        """
        Log an error with full context.
        
        Args:
            error: The exception that occurred
            context: Additional context about the error
            module: Module where error occurred
            function: Function where error occurred
            user_message: User-friendly error message
        """
        error_entry = {
            'timestamp': datetime.now().isoformat(),
            'type': type(error).__name__,
            'message': str(error),
            'context': context,
            'module': module,
            'function': function,
            'user_message': user_message,
            'traceback': traceback.format_exc()
        }
        
        self.errors.append(error_entry)
        self._save_errors()
        
        # Log to file
        logger.error(
            f"Error in {module}.{function}: {error}\n"
            f"Context: {context}\n"
            f"Traceback: {traceback.format_exc()}"
        )
    
    def get_recent_errors(self, count: int = 10) -> list:
        """Get most recent errors"""
        return self.errors[-count:]
    
    def get_error_summary(self) -> dict:
        """Get summary of errors"""
        if not self.errors:
            return {'total': 0, 'by_type': {}, 'by_module': {}}
        
        by_type = {}
        by_module = {}
        
        for error in self.errors:
            # Count by type
            error_type = error.get('type', 'Unknown')
            by_type[error_type] = by_type.get(error_type, 0) + 1
            
            # Count by module
            module = error.get('module', 'Unknown')
            by_module[module] = by_module.get(module, 0) + 1
        
        return {
            'total': len(self.errors),
            'by_type': by_type,
            'by_module': by_module
        }


# Global error tracker
error_tracker = ErrorTracker()


def retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,)
):
    """
    Decorator to retry a function on failure.
    
    Args:
        max_attempts: Maximum number of attempts
        delay: Initial delay between attempts (seconds)
        backoff: Multiplier for delay after each attempt
        exceptions: Tuple of exceptions to catch
    
    Example:
        @retry(max_attempts=3, delay=1.0)
        def download_file(url):
            # ... code that might fail
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            attempt = 1
            current_delay = delay
            
            while attempt <= max_attempts:
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    if attempt == max_attempts:
                        logger.error(
                            f"Function {func.__name__} failed after {max_attempts} attempts: {e}"
                        )
                        raise
                    
                    logger.warning(
                        f"Attempt {attempt}/{max_attempts} failed for {func.__name__}: {e}. "
                        f"Retrying in {current_delay}s..."
                    )
                    
                    import time
                    time.sleep(current_delay)
                    current_delay *= backoff
                    attempt += 1
        
        return wrapper
    return decorator


def safe_execute(
    func: Callable,
    default_return: Any = None,
    error_message: str = "Operation failed",
    log_error: bool = True
) -> Any:
    """
    Safely execute a function and return default value on error.
    
    Args:
        func: Function to execute
        default_return: Value to return on error
        error_message: Message to log on error
        log_error: Whether to log the error
    
    Returns:
        Function result or default_return on error
    """
    try:
        return func()
    except Exception as e:
        if log_error:
            logger.error(f"{error_message}: {e}")
            error_tracker.log_error(
                e,
                context=error_message,
                function=func.__name__ if hasattr(func, '__name__') else 'unknown'
            )
        return default_return


def get_user_friendly_error(error: Exception) -> str:
    """
    Convert technical error to user-friendly message.
    
    Args:
        error: The exception
    
    Returns:
        User-friendly error message
    """
    error_type = type(error).__name__
    error_msg = str(error)
    
    # Common error mappings
    friendly_messages = {
        'FileNotFoundError': f"File not found: {error_msg}",
        'PermissionError': "Permission denied. Please check file permissions or run as administrator.",
        'ConnectionError': "Network connection failed. Please check your internet connection.",
        'TimeoutError': "Operation timed out. Please try again.",
        'ValueError': f"Invalid value: {error_msg}",
        'RuntimeError': f"Runtime error: {error_msg}",
        'ImportError': f"Missing dependency: {error_msg}. Please reinstall requirements.",
        'OSError': f"System error: {error_msg}",
    }
    
    return friendly_messages.get(error_type, f"An error occurred: {error_msg}")


class PerformanceLogger:
    """Log performance metrics"""
    
    def __init__(self):
        self.metrics_file = PERFORMANCE_LOG
    
    def log_metric(
        self,
        operation: str,
        duration: float,
        success: bool = True,
        details: dict = None
    ):
        """Log a performance metric"""
        entry = {
            'timestamp': datetime.now().isoformat(),
            'operation': operation,
            'duration_seconds': duration,
            'success': success,
            'details': details or {}
        }
        
        try:
            with open(self.metrics_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(entry) + '\n')
        except Exception as e:
            logger.error(f"Failed to log performance metric: {e}")
    
    def measure(self, operation: str):
        """
        Context manager to measure operation time.
        
        Example:
            with perf_logger.measure("download_video"):
                download_video(url)
        """
        import time
        
        class Timer:
            def __enter__(self):
                self.start = time.time()
                return self
            
            def __exit__(self, exc_type, exc_val, exc_tb):
                duration = time.time() - self.start
                success = exc_type is None
                self.parent.log_metric(operation, duration, success)
        
        timer = Timer()
        timer.parent = self
        return timer


# Global performance logger
perf_logger = PerformanceLogger()


def log_function_call(func: Callable) -> Callable:
    """Decorator to log function calls and execution time"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        import time
        
        func_name = f"{func.__module__}.{func.__name__}"
        logger.debug(f"Calling {func_name}")
        
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            duration = time.time() - start_time
            logger.debug(f"Completed {func_name} in {duration:.2f}s")
            perf_logger.log_metric(func_name, duration, True)
            return result
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"Error in {func_name} after {duration:.2f}s: {e}")
            perf_logger.log_metric(func_name, duration, False)
            raise
    
    return wrapper


def clear_old_logs(days: int = 30):
    """Delete log files older than specified days"""
    import time
    
    current_time = time.time()
    cutoff_time = current_time - (days * 86400)  # days to seconds
    
    deleted_count = 0
    for log_file in LOG_DIR.glob("*.log"):
        try:
            if log_file.stat().st_mtime < cutoff_time:
                log_file.unlink()
                deleted_count += 1
        except Exception as e:
            logger.warning(f"Failed to delete old log file {log_file}: {e}")
    
    logger.info(f"Cleaned up {deleted_count} old log files")
