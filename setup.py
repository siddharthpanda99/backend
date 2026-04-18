from setuptools import setup, find_packages

setup(
    name="backend",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "fastapi[standard]>=0.128.0",
        "sqlmodel>=0.0.22",
        "pyyaml>=6.0.2",
        "requests>=2.31.0",
        "rich>=13.7.0",
    ],
    entry_points={
        "console_scripts": [
            "nexus=cli.main:cli",
            "nexus-test=tests.test_crud:cli",
        ],
    },
)
