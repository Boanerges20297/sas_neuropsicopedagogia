"""SQL scope invariants: clinical data owner only, including platform admins."""
import unittest
from unittest.mock import patch

import saas_admin_workspace
import saas_neurocore_store
import saas_store


class ScopeQueryContracts(unittest.TestCase):
    def test_admin_clinic_requires_owner_identity_not_just_membership(self):
        with patch.object(saas_store, "one", return_value=None) as query:
            self.assertIsNone(saas_admin_workspace.own_admin_workspace(17))
        statement, params = query.call_args.args
        self.assertIn("t.owner_user_id=%s", statement)
        self.assertIn("m.membership_role='owner'", statement)
        self.assertEqual(params, (17, 17))

    def test_patient_lookups_are_bound_to_professional_and_tenant(self):
        with patch.object(saas_store, "one", return_value=None) as query:
            self.assertIsNone(saas_neurocore_store.scoped_client(17, 9, 23))
        statement, params = query.call_args.args
        self.assertIn("c.tenant_id=%s", statement)
        self.assertIn("c.professional_user_id=%s", statement)
        self.assertIn("m.status='active'", statement)
        self.assertEqual(params, (23, 9, 17, 17))

    def test_unknown_client_is_not_a_review_oracle(self):
        with patch.object(saas_neurocore_store, "scoped_client", return_value=None):
            with patch.object(saas_store, "one") as query, patch.object(
                    saas_store, "all_rows") as query_list:
                self.assertIsNone(
                    saas_neurocore_store.get_review(17, 9, 23, "tea"))
                self.assertEqual(
                    saas_neurocore_store.list_reviews(17, 9, 23), [])
                query.assert_not_called()
                query_list.assert_not_called()


if __name__ == "__main__":
    unittest.main()
