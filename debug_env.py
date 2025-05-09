#!/usr/bin/env python3
# debug_env.py
import os


def print_env():
    print("===== Environment Variables =====")
    # Sort env vars for better readability
    env_vars = sorted(os.environ.items())
    for key, value in env_vars:
        if 'SECRET' in key.upper() or 'PASSWORD' in key.upper() or 'KEY' in key.upper():
            print(f"{key}=********")
        else:
            print(f"{key}={value}")
    print("================================")


if __name__ == "__main__":
    print_env()
