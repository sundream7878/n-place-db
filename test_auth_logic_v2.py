import hashlib
import unittest
from unittest.mock import MagicMock, patch

# Mocking modules
import sys
sys.modules['wmi'] = MagicMock()
sys.modules['firebase_admin'] = MagicMock()

from auth import AuthManager

class TestAuthLogicRefined(unittest.TestCase):
    def setUp(self):
        AuthManager._db = MagicMock()
        self.mock_db = AuthManager._db
        self.hwid = AuthManager.get_hwid()

    def test_validate_already_used_with_correct_hwid(self):
        """Test validation when status is 'used' but HWID matches (user's current situation)"""
        mock_doc = MagicMock()
        mock_doc.exists = True
        # Note: 'is_active' is missing, 'status' is 'used'
        mock_doc.to_dict.return_value = {"status": "used", "hwid": self.hwid}
        self.mock_db.collection().document().get.return_value = mock_doc

        with patch.object(AuthManager, 'save_local_license'):
            success, msg = AuthManager.validate_and_bind_key("NP-VYNB-6229")
            self.assertTrue(success)

    def test_validate_mismatch_hwid_used(self):
        """Test validation failure when status is 'used' and HWID mismatches"""
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {"status": "used", "hwid": "OTHER-HWID"}
        self.mock_db.collection().document().get.return_value = mock_doc

        success, msg = AuthManager.validate_and_bind_key("TEST-KEY")
        self.assertFalse(success)

    def test_validate_new_key_active(self):
        """Test validation for a new key that is 'active'"""
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {"status": "active", "hwid": None}
        self.mock_db.collection().document().get.return_value = mock_doc

        with patch.object(AuthManager, 'save_local_license'):
            success, msg = AuthManager.validate_and_bind_key("NEW-KEY")
            self.assertTrue(success)
            # Should update status to 'used' and set hwid
            self.mock_db.collection().document().update.assert_called_with({
                "hwid": self.hwid,
                "status": "used",
                "used_at": unittest.mock.ANY
            })

if __name__ == "__main__":
    unittest.main()
