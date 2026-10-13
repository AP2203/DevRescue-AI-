import pytest
from app.services.security_service import security_service
from app.services.recovered_2d2mesh_models import get_2d2mesh_repair_patch


def test_security_scan_empty_patch():
    res = security_service.scan_patch("")
    assert res["status"] == "NOT_IMPLEMENTED"
    assert res["executed"] is False
    assert res["clean"] is False
    assert "limitations" in res


def test_security_scan_clean_patch():
    patch = get_2d2mesh_repair_patch()
    res = security_service.scan_patch(patch)
    assert res["status"] == "PASSED"
    assert res["clean"] is True
    assert res["executed"] is True
    assert res["findings_count"] == 0
    assert "limitations" in res


def test_security_scan_detects_hardcoded_api_key():
    diff = """--- a/backend/config.py
+++ b/backend/config.py
@@ -10,1 +10,2 @@
+API_KEY = "ghp_1234567890abcdef1234567890abcdef1234"
"""
    res = security_service.scan_patch(diff)
    assert res["status"] == "FAILED"
    assert res["clean"] is False
    assert res["critical_count"] >= 1
    assert any(f["rule_id"] == "GITHUB_PERSONAL_ACCESS_TOKEN" for f in res["findings"])


def test_security_scan_detects_private_key():
    diff = """--- a/keys.py
+++ b/keys.py
@@ -1,1 +1,3 @@
+-----BEGIN RSA PRIVATE KEY-----
+MIIEowIBAAKCAQEA0Y7...
"""
    res = security_service.scan_patch(diff)
    assert res["status"] == "FAILED"
    assert res["critical_count"] >= 1
    assert any(f["rule_id"] == "PRIVATE_KEY_MATERIAL" for f in res["findings"])


def test_security_scan_detects_unsafe_os_system():
    diff = """--- a/runner.py
+++ b/runner.py
@@ -5,1 +5,2 @@
+os.system("rm -rf " + target_dir)
"""
    res = security_service.scan_patch(diff)
    assert res["status"] == "FAILED"
    assert res["high_count"] >= 1
    assert any(f["rule_id"] == "UNSAFE_OS_SYSTEM" for f in res["findings"])


def test_security_scan_detects_subprocess_shell_true():
    diff = """--- a/runner.py
+++ b/runner.py
@@ -5,1 +5,2 @@
+subprocess.run(f"cat {filename}", shell=True)
"""
    res = security_service.scan_patch(diff)
    assert res["status"] == "FAILED"
    assert res["high_count"] >= 1
    assert any(f["rule_id"] == "SUBPROCESS_SHELL_TRUE" for f in res["findings"])


def test_security_scan_detects_dangerous_eval():
    diff = """--- a/calc.py
+++ b/calc.py
@@ -2,1 +2,2 @@
+result = eval(user_expression)
"""
    res = security_service.scan_patch(diff)
    assert res["status"] == "FAILED"
    assert res["high_count"] >= 1
    assert any(f["rule_id"] == "UNSAFE_EVAL_EXEC" for f in res["findings"])


def test_security_scan_detects_sql_injection_fstring():
    diff = """--- a/db.py
+++ b/db.py
@@ -10,1 +10,2 @@
+cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")
"""
    res = security_service.scan_patch(diff)
    assert res["status"] == "FAILED"
    assert res["high_count"] >= 1
    assert any(f["rule_id"] == "SQLI_FSTRING" for f in res["findings"])


def test_security_scan_detects_medium_warning():
    diff = """--- a/net.py
+++ b/net.py
@@ -10,1 +10,2 @@
+response = requests.get(url, verify=False)
"""
    res = security_service.scan_patch(diff)
    assert res["status"] == "WARNINGS"
    assert res["clean"] is False
    assert res["medium_count"] >= 1
    assert any(f["rule_id"] == "INSECURE_TLS_VERIFY_FALSE" for f in res["findings"])

