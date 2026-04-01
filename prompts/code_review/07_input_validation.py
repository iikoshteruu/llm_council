"""User input handling for a web API with search, filtering, and export.
Review this code for injection vulnerabilities, validation gaps, and correctness problems."""

import sqlite3
import re
import csv
import io
from datetime import datetime, timedelta

class UserQueryHandler:
    def __init__(self, db_path):
        self.conn = sqlite3.connect(db_path)

    def search_users(self, query, filters=None, sort_by="name", limit=50):
        """Search users with optional filters and sorting."""
        sql = f"SELECT id, name, email, role, created_at FROM users WHERE name LIKE '%{query}%'"

        if filters:
            if filters.get("role"):
                sql += f" AND role = '{filters['role']}'"
            if filters.get("created_after"):
                sql += f" AND created_at > '{filters['created_after']}'"
            if filters.get("email_domain"):
                domain = filters["email_domain"]
                sql += f" AND email LIKE '%@{domain}'"

        sql += f" ORDER BY {sort_by}"
        sql += f" LIMIT {limit}"

        cursor = self.conn.execute(sql)
        return [dict(zip(["id", "name", "email", "role", "created_at"], row)) for row in cursor.fetchall()]

    def update_user_role(self, user_id, new_role, admin_id):
        """Update a user's role. Only admins can do this."""
        valid_roles = ["user", "moderator", "admin"]
        if new_role not in valid_roles:
            raise ValueError(f"Invalid role: {new_role}")

        self.conn.execute(
            f"UPDATE users SET role = '{new_role}', updated_by = '{admin_id}' WHERE id = {user_id}"
        )
        self.conn.commit()
        return True

    def export_users(self, format="csv", filters=None):
        """Export filtered user data."""
        users = self.search_users("", filters)

        if format == "csv":
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=["id", "name", "email", "role", "created_at"])
            writer.writeheader()
            for user in users:
                writer.writerow(user)
            return output.getvalue()
        elif format == "json":
            import json
            return json.dumps(users, indent=2)
        else:
            return str(users)

    def validate_email(self, email):
        """Validate email format."""
        pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
        return bool(re.match(pattern, email))

    def create_user(self, name, email, role="user"):
        """Create a new user."""
        if not name or len(name) > 200:
            raise ValueError("Invalid name")
        if not self.validate_email(email):
            raise ValueError("Invalid email")

        self.conn.execute(
            "INSERT INTO users (name, email, role, created_at) VALUES (?, ?, ?, ?)",
            (name, email, role, datetime.now().isoformat()),
        )
        self.conn.commit()

    def delete_user(self, user_id):
        """Soft delete a user by setting deleted_at."""
        self.conn.execute(
            f"UPDATE users SET deleted_at = '{datetime.now().isoformat()}' WHERE id = {user_id}"
        )
        self.conn.commit()

    def get_login_attempts(self, email, window_minutes=15):
        """Get recent failed login attempts for rate limiting."""
        cutoff = (datetime.now() - timedelta(minutes=window_minutes)).isoformat()
        cursor = self.conn.execute(
            f"SELECT COUNT(*) FROM login_attempts WHERE email = '{email}' AND attempted_at > '{cutoff}' AND success = 0"
        )
        return cursor.fetchone()[0]

    def log_login_attempt(self, email, success, ip_address):
        """Log a login attempt."""
        self.conn.execute(
            "INSERT INTO login_attempts (email, success, ip_address, attempted_at) VALUES (?, ?, ?, ?)",
            (email, int(success), ip_address, datetime.now().isoformat()),
        )
        self.conn.commit()

    def search_audit_log(self, action=None, user_id=None, start_date=None, end_date=None):
        """Search the audit log with filters."""
        conditions = []
        if action:
            conditions.append(f"action = '{action}'")
        if user_id:
            conditions.append(f"user_id = {user_id}")
        if start_date:
            conditions.append(f"timestamp >= '{start_date}'")
        if end_date:
            conditions.append(f"timestamp <= '{end_date}'")

        where = " AND ".join(conditions) if conditions else "1=1"
        sql = f"SELECT * FROM audit_log WHERE {where} ORDER BY timestamp DESC LIMIT 100"

        cursor = self.conn.execute(sql)
        return cursor.fetchall()
