import os
from setuptools import setup, find_packages

# Read version
exec(open('version.py').read())

# Read README
with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

# Read requirements
with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="gravixlayer",
    version="0.0.22",
    author="Sukrith",
    author_email="sukrithpvs@gmail.com",
    description="GravixLayer Python SDK - OpenAI Compatible",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/sukrithpvs/gravixlayer-python",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Internet :: WWW/HTTP :: Dynamic Content",
    ],
    python_requires=">=3.7",
    install_requires=requirements,
    entry_points={
        'console_scripts': [
            'gravixlayer=gravixlayer.cli:main',
        ],
    },
    keywords="gravixlayer, openai, llm, ai, api, sdk",
    project_urls={
        "Bug Reports": "https://github.com/sukrithpvs/gravixlayer-python/issues",
        "Source": "https://github.com/sukrithpvs/gravixlayer-python",
        "Documentation": "https://github.com/sukrithpvs/gravixlayer-python/blob/main/README.md",
    },
)
