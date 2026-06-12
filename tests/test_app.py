import io
import tempfile
import unittest
from pathlib import Path

from app import create_app


class AppFlowTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        base_path = Path(self.temp_dir.name)
        self.app = create_app(
            {
                "TESTING": True,
                "SECRET_KEY": "test-secret",
                "DATABASE": str(base_path / "test.sqlite3"),
                "UPLOAD_FOLDER": str(base_path / "uploads"),
            }
        )
        self.client = self.app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    def signup(self, email="alex@example.com", password="password123"):
        return self.client.post(
            "/signup",
            data={
                "name": "Alex Morgan",
                "email": email,
                "password": password,
                "confirm_password": password,
            },
            follow_redirects=True,
        )

    def login(self, email="alex@example.com", password="password123"):
        return self.client.post(
            "/login",
            data={"email": email, "password": password},
            follow_redirects=True,
        )

    def test_signup_logs_user_into_dashboard(self):
        response = self.signup()

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Alex Morgan's file workspace", response.data)

    def test_dashboard_requires_login(self):
        response = self.client.get("/dashboard", follow_redirects=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Sign in to continue.", response.data)
        self.assertIn(b"Access your protected files", response.data)

    def test_login_rejects_bad_credentials(self):
        self.signup()
        self.client.post("/logout", follow_redirects=True)

        response = self.client.post(
            "/login",
            data={"email": "alex@example.com", "password": "wrongpass"},
            follow_redirects=True,
        )

        self.assertIn(b"Invalid email or password.", response.data)

    def test_upload_download_and_delete_file(self):
        self.signup()
        upload = self.client.post(
            "/upload",
            data={"files": (io.BytesIO(b"assessment notes"), "notes.txt")},
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        self.assertIn(b"notes.txt", upload.data)

        with self.app.app_context():
            file_record = self.app.get_db().execute("SELECT * FROM files").fetchone()
            stored_path = Path(self.app.config["UPLOAD_FOLDER"]) / file_record["stored_name"]
            self.assertTrue(stored_path.exists())

        download = self.client.get(f"/download/{file_record['id']}")
        self.assertEqual(download.status_code, 200)
        self.assertEqual(download.data, b"assessment notes")
        download.close()

        delete = self.client.post(f"/delete/{file_record['id']}", follow_redirects=True)
        self.assertIn(b"Deleted notes.txt.", delete.data)
        self.assertFalse(stored_path.exists())

    def test_user_cannot_download_another_users_file(self):
        self.signup("first@example.com")
        self.client.post(
            "/upload",
            data={"files": (io.BytesIO(b"private"), "private.txt")},
            content_type="multipart/form-data",
        )
        with self.app.app_context():
            file_id = self.app.get_db().execute("SELECT id FROM files").fetchone()["id"]

        self.client.post("/logout", follow_redirects=True)
        self.signup("second@example.com")

        response = self.client.get(f"/download/{file_id}")

        self.assertEqual(response.status_code, 404)

    def test_invalid_file_type_is_rejected(self):
        self.signup()
        response = self.client.post(
            "/upload",
            data={"files": (io.BytesIO(b"print(1)"), "script.exe")},
            content_type="multipart/form-data",
            follow_redirects=True,
        )

        self.assertIn(b"script.exe is not an allowed file type.", response.data)
        with self.app.app_context():
            count = self.app.get_db().execute("SELECT COUNT(*) FROM files").fetchone()[0]
        self.assertEqual(count, 0)


if __name__ == "__main__":
    unittest.main()
