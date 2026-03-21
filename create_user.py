#!/usr/bin/env python3
"""Скрипт для создания администраторов"""
import sys
import os
import json
import hashlib
import secrets

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ADMINS_FILE = os.path.join(os.path.dirname(__file__), 'admins.json')


def load_admins():
    if os.path.exists(ADMINS_FILE):
        with open(ADMINS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_admins(admins):
    with open(ADMINS_FILE, 'w', encoding='utf-8') as f:
        json.dump(admins, f, indent=4, ensure_ascii=False)


def hash_password(password: str, salt: str = '') -> str:
    combined = password + salt
    return hashlib.sha256(combined.encode()).hexdigest()


def create_user(username: str, password: str):
    admins = load_admins()
    
    salt = secrets.token_hex(16)
    password_hash = hash_password(password, salt)
    
    admins[username] = {
        'password_hash': password_hash,
        'salt': salt
    }
    
    save_admins(admins)
    print(f"User '{username}' created successfully!")
    print(f"Password: {password}")


def list_users():
    admins = load_admins()
    print("\n=== Admins ===")
    for username in admins:
        print(f"  - {username}")
    print()


def delete_user(username: str):
    admins = load_admins()
    if username in admins:
        del admins[username]
        save_admins(admins)
        print(f"User '{username}' deleted")
    else:
        print(f"User '{username}' not found")


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Admin user manager')
    parser.add_argument('-c', '--create', metavar='USER', help='Create user')
    parser.add_argument('-p', '--password', metavar='PASS', help='Password')
    parser.add_argument('-l', '--list', action='store_true', help='List users')
    parser.add_argument('-d', '--delete', metavar='USER', help='Delete user')
    
    args = parser.parse_args()
    
    if args.list:
        list_users()
    elif args.delete:
        delete_user(args.delete)
    elif args.create and args.password:
        create_user(args.create, args.password)
    else:
        print("Usage:")
        print("  python create_user.py -c admin -p password123  (create user)")
        print("  python create_user.py -l                        (list users)")
        print("  python create_user.py -d username               (delete user)")