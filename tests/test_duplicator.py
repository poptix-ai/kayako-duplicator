"""
Unit tests for kayako_duplicator.py

Tests use the module's make_copy() function directly (no sendmail calls).
"""

import email
import os
import sys
import unittest

# Allow importing the script as a module from the project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import kayako_duplicator as kd  # noqa: E402

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def load_fixture(name):
    path = os.path.join(FIXTURES, name)
    with open(path, "rb") as f:
        return f.read()


def copies_for(raw_bytes, addresses):
    """Return a list of email.Message objects, one per address."""
    return [kd.make_copy(raw_bytes, addr) for addr in addresses]


class TestMessageID(unittest.TestCase):
    def test_all_copies_have_unique_message_ids(self):
        raw = load_fixture("simple.eml")
        copies = copies_for(raw, ["a@x.com", "b@x.com", "c@x.com"])
        ids = [c["Message-ID"] for c in copies]
        self.assertEqual(len(ids), len(set(ids)), "Message-IDs must all be unique")

    def test_copy_message_id_differs_from_original(self):
        raw = load_fixture("simple.eml")
        original = email.message_from_bytes(raw)
        copy = kd.make_copy(raw, "a@x.com")
        self.assertNotEqual(copy["Message-ID"], original["Message-ID"])

    def test_message_id_format(self):
        raw = load_fixture("simple.eml")
        copy = kd.make_copy(raw, "a@x.com")
        mid = copy["Message-ID"]
        self.assertTrue(mid.startswith("<"), f"Message-ID should start with <: {mid}")
        self.assertTrue(mid.endswith(">"), f"Message-ID should end with >: {mid}")

    def test_five_copies_all_unique_ids(self):
        raw = load_fixture("simple.eml")
        addrs = [f"q{i}@kayako.com" for i in range(5)]
        copies = copies_for(raw, addrs)
        ids = [c["Message-ID"] for c in copies]
        self.assertEqual(len(ids), len(set(ids)))


class TestSubject(unittest.TestCase):
    def test_all_copies_have_unique_subject_suffixes(self):
        raw = load_fixture("simple.eml")
        copies = copies_for(raw, ["a@x.com", "b@x.com", "c@x.com"])
        subjects = [c["Subject"] for c in copies]
        self.assertEqual(
            len(subjects), len(set(subjects)), "Subjects must all be unique"
        )

    def test_subject_contains_original_text(self):
        raw = load_fixture("simple.eml")
        original = email.message_from_bytes(raw)
        copy = kd.make_copy(raw, "a@x.com")
        self.assertIn(original["Subject"], copy["Subject"])

    def test_subject_tag_format(self):
        raw = load_fixture("simple.eml")
        copy = kd.make_copy(raw, "a@x.com")
        subject = copy["Subject"]
        # Should end with " [XXXX]" where XXXX is 4 alphanumeric chars
        import re
        self.assertRegex(subject, r"\[[A-Za-z0-9]{4}\]$")

    def test_five_copies_all_unique_subjects(self):
        raw = load_fixture("simple.eml")
        addrs = [f"q{i}@kayako.com" for i in range(5)]
        copies = copies_for(raw, addrs)
        subjects = [c["Subject"] for c in copies]
        self.assertEqual(len(subjects), len(set(subjects)))


class TestSentinelHeader(unittest.TestCase):
    def test_x_kayako_dup_present(self):
        raw = load_fixture("simple.eml")
        copy = kd.make_copy(raw, "a@x.com")
        self.assertEqual(copy["X-Kayako-Dup"], "1")

    def test_x_kayako_dup_present_multipart(self):
        raw = load_fixture("multipart.eml")
        copy = kd.make_copy(raw, "a@x.com")
        self.assertEqual(copy["X-Kayako-Dup"], "1")

    def test_x_kayako_dup_on_all_copies(self):
        raw = load_fixture("simple.eml")
        copies = copies_for(raw, ["a@x.com", "b@x.com"])
        for c in copies:
            self.assertEqual(c["X-Kayako-Dup"], "1")


class TestThreadingHeaders(unittest.TestCase):
    def test_in_reply_to_stripped(self):
        raw = load_fixture("simple.eml")
        copy = kd.make_copy(raw, "a@x.com")
        self.assertIsNone(copy["In-Reply-To"], "In-Reply-To must be absent")

    def test_references_stripped(self):
        raw = load_fixture("simple.eml")
        copy = kd.make_copy(raw, "a@x.com")
        self.assertIsNone(copy["References"], "References must be absent")

    def test_threading_headers_stripped_multipart(self):
        raw = load_fixture("multipart.eml")
        copy = kd.make_copy(raw, "a@x.com")
        self.assertIsNone(copy["In-Reply-To"])
        self.assertIsNone(copy["References"])


class TestPreservedFields(unittest.TestCase):
    def test_from_preserved(self):
        raw = load_fixture("simple.eml")
        original = email.message_from_bytes(raw)
        copy = kd.make_copy(raw, "a@x.com")
        self.assertEqual(copy["From"], original["From"])

    def test_to_set_to_destination(self):
        raw = load_fixture("simple.eml")
        copy = kd.make_copy(raw, "a@x.com")
        self.assertEqual(copy["To"], "a@x.com")

    def test_to_differs_per_copy(self):
        raw = load_fixture("simple.eml")
        copies = copies_for(raw, ["a@x.com", "b@x.com"])
        self.assertEqual(copies[0]["To"], "a@x.com")
        self.assertEqual(copies[1]["To"], "b@x.com")

    def test_plain_text_body_preserved(self):
        raw = load_fixture("simple.eml")
        original = email.message_from_bytes(raw)
        copy = kd.make_copy(raw, "a@x.com")
        self.assertEqual(
            copy.get_payload(),
            original.get_payload(),
            "Plain text body must be unchanged",
        )

    def test_date_preserved(self):
        raw = load_fixture("simple.eml")
        original = email.message_from_bytes(raw)
        copy = kd.make_copy(raw, "a@x.com")
        self.assertEqual(copy["Date"], original["Date"])


class TestMultipart(unittest.TestCase):
    def test_multipart_structure_intact(self):
        raw = load_fixture("multipart.eml")
        copy = kd.make_copy(raw, "a@x.com")
        self.assertTrue(copy.is_multipart(), "Copy must still be multipart")

    def test_multipart_part_count(self):
        raw = load_fixture("multipart.eml")
        original = email.message_from_bytes(raw)
        copy = kd.make_copy(raw, "a@x.com")
        self.assertEqual(
            len(copy.get_payload()),
            len(original.get_payload()),
            "Part count must be unchanged",
        )

    def test_multipart_body_content_preserved(self):
        raw = load_fixture("multipart.eml")
        original = email.message_from_bytes(raw)
        copy = kd.make_copy(raw, "a@x.com")
        orig_parts = original.get_payload()
        copy_parts = copy.get_payload()
        for i, (op, cp) in enumerate(zip(orig_parts, copy_parts)):
            self.assertEqual(
                op.get_payload(),
                cp.get_payload(),
                f"Part {i} content must be unchanged",
            )

    def test_multipart_unique_message_ids(self):
        raw = load_fixture("multipart.eml")
        copies = copies_for(raw, ["a@x.com", "b@x.com"])
        ids = [c["Message-ID"] for c in copies]
        self.assertEqual(len(ids), len(set(ids)))


class TestEdgeCases(unittest.TestCase):
    def test_single_address(self):
        raw = load_fixture("simple.eml")
        copies = copies_for(raw, ["only@x.com"])
        self.assertEqual(len(copies), 1)
        self.assertEqual(copies[0]["X-Kayako-Dup"], "1")

    def test_two_addresses(self):
        raw = load_fixture("simple.eml")
        copies = copies_for(raw, ["a@x.com", "b@x.com"])
        self.assertEqual(len(copies), 2)
        ids = [c["Message-ID"] for c in copies]
        self.assertEqual(len(set(ids)), 2)

    def test_five_addresses(self):
        raw = load_fixture("simple.eml")
        addrs = [f"q{i}@kayako.com" for i in range(5)]
        copies = copies_for(raw, addrs)
        self.assertEqual(len(copies), 5)
        ids = [c["Message-ID"] for c in copies]
        subjects = [c["Subject"] for c in copies]
        self.assertEqual(len(set(ids)), 5)
        self.assertEqual(len(set(subjects)), 5)

    def test_generate_message_id_is_unique(self):
        ids = {kd.generate_message_id() for _ in range(100)}
        self.assertEqual(len(ids), 100, "generate_message_id must be unique per call")

    def test_random_tag_length(self):
        for _ in range(20):
            tag = kd.random_tag()
            self.assertEqual(len(tag), 4)

    def test_random_tag_alphanumeric(self):
        import re
        for _ in range(20):
            tag = kd.random_tag()
            self.assertRegex(tag, r"^[A-Za-z0-9]{4}$")


if __name__ == "__main__":
    unittest.main()
