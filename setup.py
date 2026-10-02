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
            # Repointed 2026-10-03 (CLI retirement) from `cli.main:cli`, which lived in
            # the retired Backend/cli/ package, to the canonical CLI's runner. This is
            # the same target common_lib/pyproject.toml declares as `cli`.
            "nexus=common_lib.modules.cli.runtime.runner:main",
            # `tests.test_crud:cli` is this test module's OWN click group (defined at
            # tests/test_crud.py:552) — it never referenced Backend/cli/ and is unchanged.
            "nexus-test=tests.test_crud:cli",
        ],
    },
)
