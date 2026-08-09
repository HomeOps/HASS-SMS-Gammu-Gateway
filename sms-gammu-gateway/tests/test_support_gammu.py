"""Integration tests for support.py against gammu's dummy phone.

These exercise the add-on's own helpers, not just libgammu, so a regression in
retrieveAllSms or deleteSms is caught without a modem.
"""

import pytest

from support import deleteSms, encodeSms, retrieveAllSms

pytestmark = pytest.mark.integration


def send(machine, smsc, text, number="+14252146123"):
    """Send one message through the same encode path the add-on uses."""
    smsinfo = {
        "Class": -1,
        "Unicode": False,
        "Entries": [{"ID": "ConcatenatedTextLong", "Buffer": text}],
    }
    refs = []
    for message in encodeSms(smsinfo):
        message["SMSC"] = smsc
        message["Number"] = number
        refs.append(machine.SendSMS(message))
    return refs


class TestEncodeSms:
    def test_short_text_is_one_part(self):
        smsinfo = {
            "Class": -1,
            "Unicode": False,
            "Entries": [{"ID": "ConcatenatedTextLong", "Buffer": "short"}],
        }
        assert len(encodeSms(smsinfo)) == 1

    def test_long_text_is_split_into_parts(self):
        smsinfo = {
            "Class": -1,
            "Unicode": False,
            "Entries": [{"ID": "ConcatenatedTextLong", "Buffer": "x" * 500}],
        }
        assert len(encodeSms(smsinfo)) > 1

    def test_unicode_text_encodes(self):
        smsinfo = {
            "Class": -1,
            "Unicode": True,
            "Entries": [{"ID": "ConcatenatedTextLong", "Buffer": "příliš žluťoučký kůň"}],
        }
        assert len(encodeSms(smsinfo)) >= 1


class TestSending:
    def test_send_returns_a_reference(self, dummy_phone, smsc):
        refs = send(dummy_phone, smsc, "hello")
        assert len(refs) == 1
        assert isinstance(refs[0], int)

    def test_multipart_send_returns_a_reference_per_part(self, dummy_phone, smsc):
        refs = send(dummy_phone, smsc, "y" * 500)
        assert len(refs) > 1


class TestRetrieveAndDelete:
    def test_empty_store_returns_no_messages(self, dummy_phone):
        assert retrieveAllSms(dummy_phone) == []

    def test_status_reports_an_empty_store(self, dummy_phone):
        status = dummy_phone.GetSMSStatus()
        assert status["SIMUsed"] == 0
        assert status["PhoneUsed"] == 0

    def test_retrieve_reads_back_a_stored_message(self, dummy_phone, smsc):
        dummy_phone.AddSMS(
            {
                # Folder 0 means "any" when reading and is not a writable
                # location; 1 is the first real folder.
                "Folder": 1,
                "State": "UnRead",
                "Number": "+14252146123",
                "SMSC": smsc,
                "Text": "stored message",
                "Class": -1,
            }
        )
        messages = retrieveAllSms(dummy_phone)
        assert len(messages) == 1
        assert messages[0]["Number"] == "+14252146123"

    def test_delete_removes_the_message(self, dummy_phone, smsc):
        dummy_phone.AddSMS(
            {
                # Folder 0 means "any" when reading and is not a writable
                # location; 1 is the first real folder.
                "Folder": 1,
                "State": "UnRead",
                "Number": "+14252146123",
                "SMSC": smsc,
                "Text": "to be deleted",
                "Class": -1,
            }
        )
        messages = retrieveAllSms(dummy_phone)
        assert len(messages) == 1

        deleteSms(dummy_phone, messages[0])
        assert retrieveAllSms(dummy_phone) == []
