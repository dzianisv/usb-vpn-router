#!/usr/bin/env python3
"""
USB VPN Router Setup Package
Turn your Orange Pi into a secure USB ethernet gadget with VPN routing and web dashboard.
"""

from setuptools import setup, find_packages
import os

# Read the README file for long description
def read_readme():
    with open(os.path.join(os.path.dirname(__file__), 'README.md'), 'r', encoding='utf-8') as f:
        return f.read()

setup(
    name='usb-vpn-router',
    version='1.0.0',
    author='USB VPN Router Team',
    author_email='support@example.com',
    description='Turn your Orange Pi into a secure USB ethernet gadget with VPN routing',
    long_description=read_readme(),
    long_description_content_type='text/markdown',
    url='https://github.com/dzianisv/usb-vpn-router',
    packages=find_packages(),
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: MIT License',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Topic :: System :: Networking',
        'Topic :: Internet :: WWW/HTTP :: WSGI :: Application',
    ],
    python_requires='>=3.7',
    install_requires=[
        'psutil>=5.8.0',
        'netifaces>=0.11.0',
        'flask>=2.0.0',
        'flask-socketio>=5.0.0',
        'python-socketio>=5.0.0',
        'requests>=2.25.0',
        'pyyaml>=5.4.0',
        'click>=8.0.0',
        'jinja2>=3.0.0',
        'werkzeug>=2.0.0',
    ],
    extras_require={
        'ajenti': [
            'ajenti-panel',
            'ajenti.plugin.core',
            'ajenti.plugin.dashboard',
        ],
        'dev': [
            'pytest>=6.0.0',
            'black>=21.0.0',
            'flake8>=3.9.0',
            'mypy>=0.910',
        ],
    },
    entry_points={
        'console_scripts': [
            'usb-router-setup=usb_vpn_router.installer:main',
            'usb-router-dashboard=usb_vpn_router.dashboard:main',
            'usb-router-status=usb_vpn_router.cli:status',
            'usb-router-reset=usb_vpn_router.cli:reset',
            'usb-router-tailscale=usb_vpn_router.cli:tailscale_control',
            'usb-router-vpn-monitor=usb_vpn_router.monitor:main',
        ],
    },
    package_data={
        'usb_vpn_router': [
            'templates/*',
            'static/*/*',
            'ajenti_plugins/*/*',
            'configs/*',
        ],
    },
    data_files=[
        ('share/usb-vpn-router', ['setup-usb-router.sh']),
    ],
    include_package_data=True,
    zip_safe=False,
    platforms=['Linux'],
    keywords='usb ethernet gadget vpn router tailscale openvpn orange-pi raspberry-pi',
)