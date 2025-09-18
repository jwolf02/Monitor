from setuptools import setup

setup(
    name="monitor",
    version="0.1",
    install_requires=["pyserial", "termcolor"],
    py_modules=["monitor"],
    entry_points={
        "console_scripts": [
            "monitor=monitor:main",
        ],
    },
)
