#!/usr/bin/env python
import os
# Force SQLite settings
os.environ['USE_POSTGRES'] = 'False'
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'SURPLUSSYNC.settings')

import django
django.setup()

from accounts.models import User

print("=== SQLite Users ===\n")
users = User.objects.all().values(
    'id', 'username', 'email', 'role', 'is_staff', 'is_superuser', 'organization_id'
)

for u in users:
    role = u['role']
    is_staff = 'YES' if u['is_staff'] else 'NO'
    is_super = 'YES' if u['is_superuser'] else 'NO'
    org = u['organization_id'] or 'NULL'
    print(f"ID: {u['id']:2} | Username: {u['username']:15} | Email: {u['email']}")
    print(f"       Role: {role:10} | Staff: {is_staff:3} | Super: {is_super:3} | Org: {org}")
    print()

print(f"Total users: {User.objects.count()}")
