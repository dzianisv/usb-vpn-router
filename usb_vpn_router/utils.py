"""
USB VPN Router Utilities
Common utility functions used throughout the package.
"""

import os
import sys
import subprocess
import logging
from typing import List, Optional, Union
from pathlib import Path


# Colors for terminal output
class Colors:
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    PURPLE = '\033[0;35m'
    CYAN = '\033[0;36m'
    WHITE = '\033[1;37m'
    NC = '\033[0m'  # No Color


def log_info(message: str):
    """Log info message with color."""
    print(f"{Colors.GREEN}[INFO]{Colors.NC} {message}")


def log_warn(message: str):
    """Log warning message with color."""
    print(f"{Colors.YELLOW}[WARN]{Colors.NC} {message}")


def log_error(message: str):
    """Log error message with color."""
    print(f"{Colors.RED}[ERROR]{Colors.NC} {message}")


def log_debug(message: str):
    """Log debug message with color."""
    print(f"{Colors.CYAN}[DEBUG]{Colors.NC} {message}")


def check_root():
    """Check if running as root user."""
    if os.geteuid() != 0:
        log_error("This script must be run as root")
        sys.exit(1)


def run_command(
    cmd: List[str], 
    check: bool = True, 
    capture_output: bool = False,
    text: bool = True,
    timeout: Optional[int] = None,
    stdout_file: Optional[str] = None,
    stderr_file: Optional[str] = None,
    env: Optional[dict] = None
) -> subprocess.CompletedProcess:
    """
    Run a system command with proper error handling.
    
    Args:
        cmd: Command and arguments as list
        check: Raise exception on non-zero exit code
        capture_output: Capture stdout and stderr
        text: Return output as text instead of bytes
        timeout: Command timeout in seconds
        stdout_file: File to redirect stdout to
        stderr_file: File to redirect stderr to
    
    Returns:
        CompletedProcess instance
    
    Raises:
        subprocess.CalledProcessError: If command fails and check=True
    """
    log_debug(f"Running command: {' '.join(cmd)}")
    
    # Handle file redirections
    stdout = None
    stderr = None
    
    if stdout_file:
        stdout = open(stdout_file, 'w')
    elif capture_output:
        stdout = subprocess.PIPE
    
    if stderr_file:
        stderr = open(stderr_file, 'w')
    elif capture_output:
        stderr = subprocess.PIPE
    
    try:
        result = subprocess.run(
            cmd,
            check=check,
            stdout=stdout,
            stderr=stderr,
            text=text,
            timeout=timeout,
            env=env
        )
        return result
    
    except subprocess.CalledProcessError as e:
        log_error(f"Command failed: {' '.join(cmd)}")
        log_error(f"Exit code: {e.returncode}")
        if e.stdout:
            log_error(f"Stdout: {e.stdout}")
        if e.stderr:
            log_error(f"Stderr: {e.stderr}")
        raise
    
    except subprocess.TimeoutExpired as e:
        log_error(f"Command timed out: {' '.join(cmd)}")
        raise
    
    finally:
        # Close file handles
        if stdout_file and stdout:
            stdout.close()
        if stderr_file and stderr:
            stderr.close()


def get_system_info() -> dict:
    """Get basic system information."""
    import platform
    import psutil
    
    return {
        'system': platform.system(),
        'release': platform.release(),
        'machine': platform.machine(),
        'processor': platform.processor(),
        'cpu_count': psutil.cpu_count(),
        'memory_total': psutil.virtual_memory().total,
        'disk_total': psutil.disk_usage('/').total,
    }


def check_interface_exists(interface: str) -> bool:
    """Check if network interface exists."""
    try:
        result = run_command(['ip', 'link', 'show', interface], 
                           capture_output=True, check=False)
        return result.returncode == 0
    except Exception:
        return False


def check_service_status(service: str) -> str:
    """Check systemd service status."""
    try:
        result = run_command(['systemctl', 'is-active', service], 
                           capture_output=True, check=False)
        return result.stdout.strip() if result.stdout else 'unknown'
    except Exception:
        return 'unknown'


def get_interface_ip(interface: str) -> Optional[str]:
    """Get IP address of network interface."""
    try:
        result = run_command(['ip', 'addr', 'show', interface], 
                           capture_output=True, check=False)
        
        if result.returncode == 0 and result.stdout:
            import re
            ip_match = re.search(r'inet (\d+\.\d+\.\d+\.\d+)/\d+', result.stdout)
            if ip_match:
                return ip_match.group(1)
        
        return None
    except Exception:
        return None


def is_port_open(host: str, port: int) -> bool:
    """Check if a port is open on a host."""
    import socket
    
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(3)
            result = sock.connect_ex((host, port))
            return result == 0
    except Exception:
        return False


def read_file_safe(file_path: Union[str, Path]) -> Optional[str]:
    """Safely read file content."""
    try:
        with open(file_path, 'r') as f:
            return f.read()
    except Exception:
        return None


def write_file_safe(file_path: Union[str, Path], content: str, mode: int = 0o644) -> bool:
    """Safely write content to file."""
    try:
        # Ensure parent directory exists
        Path(file_path).parent.mkdir(parents=True, exist_ok=True)
        
        with open(file_path, 'w') as f:
            f.write(content)
        
        # Set file permissions
        os.chmod(file_path, mode)
        return True
    except Exception as e:
        log_error(f"Failed to write file {file_path}: {e}")
        return False


def backup_file(file_path: Union[str, Path], backup_suffix: str = '.bak') -> bool:
    """Create backup of file."""
    try:
        if Path(file_path).exists():
            backup_path = f"{file_path}{backup_suffix}"
            run_command(['cp', str(file_path), backup_path])
            log_info(f"Backed up {file_path} to {backup_path}")
            return True
        return False
    except Exception as e:
        log_error(f"Failed to backup {file_path}: {e}")
        return False


def setup_logging(log_level: str = 'INFO', log_file: Optional[str] = None):
    """Setup logging configuration."""
    level = getattr(logging, log_level.upper(), logging.INFO)
    
    # Configure logging format
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Setup handlers
    handlers = [logging.StreamHandler(sys.stdout)]
    
    if log_file:
        handlers.append(logging.FileHandler(log_file))
    
    # Configure root logger
    logging.basicConfig(
        level=level,
        handlers=handlers,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


def get_package_version() -> str:
    """Get package version."""
    try:
        from . import __version__
        return __version__
    except ImportError:
        return 'unknown'


def validate_ip_address(ip: str) -> bool:
    """Validate IP address format."""
    import ipaddress
    try:
        ipaddress.IPv4Address(ip)
        return True
    except ValueError:
        return False


def validate_network_cidr(cidr: str) -> bool:
    """Validate network CIDR format."""
    import ipaddress
    try:
        ipaddress.IPv4Network(cidr, strict=False)
        return True
    except ValueError:
        return False


def get_available_interfaces() -> List[str]:
    """Get list of available network interfaces."""
    try:
        result = run_command(['ip', 'link', 'show'], capture_output=True)
        interfaces = []
        
        for line in result.stdout.split('\n'):
            if ':' in line and not line.startswith(' '):
                # Extract interface name
                parts = line.split(':')
                if len(parts) >= 2:
                    interface = parts[1].strip().split('@')[0]
                    if interface != 'lo':  # Skip loopback
                        interfaces.append(interface)
        
        return interfaces
    except Exception:
        return []


def check_dependencies() -> dict:
    """Check if required system dependencies are available."""
    dependencies = {
        'iptables': False,
        'ip': False,
        'systemctl': False,
        'modprobe': False,
        'dnsmasq': False,
    }
    
    for dep in dependencies.keys():
        try:
            result = run_command(['which', dep], capture_output=True, check=False)
            dependencies[dep] = result.returncode == 0
        except Exception:
            dependencies[dep] = False
    
    return dependencies