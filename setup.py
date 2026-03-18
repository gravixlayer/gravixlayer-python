"""
GravixLayer Python SDK Setup Configuration
"""

import os
from setuptools import setup, find_packages

# Read README
with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="gravixlayer",
    version="0.1.1",
    author="Team Gravix",
    author_email="info@gravixlayer.com",
    description="GravixLayer Python SDK - Official Python client for GravixLayer API",
    license="Apache-2.0",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/gravixlayer/gravixlayer-python",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Internet :: WWW/HTTP :: Dynamic Content",
    ],
    python_requires=">=3.9",
    install_requires=[
        "python-dotenv>=0.19.0",
        "httpx[http2]>=0.24.0",
    ],
    entry_points={
        'console_scripts': [
            'gravixlayer=gravixlayer.cli:main',
        ],
    },
    keywords="gravixlayer, llm, ai, api, sdk, compatible",
    project_urls={
        "Bug Reports": "https://github.com/gravixlayer/gravixlayer-python/issues",
        "Source": "https://github.com/gravixlayer/gravixlayer-python",
        "Documentation": "https://github.com/gravixlayer/gravixlayer-python/blob/main/README.md",
    },
)
