#!/usr/bin/env python3
"""
kayako_duplicator.py - Kayako Email Duplicator / Multi-Queue Forwarder

Reads one raw email from stdin, produces a uniquely modified copy for each
destination address, and re-injects each copy via sendmail so Kayako treats
them as distinct new tickets.

Usage:
    kayako_duplicator.py <addr1,addr2,...>

Example:
    kayako_duplicator.py support@kayako.com,billing@kayako.com
"""

import email
import email.utils
import random
import socket
import string
import subprocess
import sys
import time
import uuid


def generate_message_id():
    """Generate a unique RFC-compliant Message-ID."""
    ts = int(time.time())
    uid = uuid.uuid4().hex[:12]
    fqdn = socket.getfqdn()
    return f"<{ts}.{uid}@{fqdn}>"


def random_tag(length=4):
    """Return a random alphanumeric tag of the given length."""
    chars = string.ascii_letters + string.digits
    return "".join(random.choices(chars, k=length))


def make_copy(original_bytes, destination):
    """
    Produce a modified copy of the email for a single destination.

    Changes applied:
    - To: replaced with the destination address (Kayako discards mismatches)
    - New unique Message-ID
    - Subject appended with a random 4-char tag
    - X-Kayako-Dup: 1 sentinel added
    - In-Reply-To and References stripped
    """
    msg = email.message_from_bytes(original_bytes)

    # Replace To: with the destination so Kayako accepts the message
    del msg["To"]
    msg["To"] = destination

    # Replace Message-ID
    del msg["Message-ID"]
    msg["Message-ID"] = generate_message_id()

    # Append unique tag to Subject
    subject = msg.get("Subject", "")
    del msg["Subject"]
    msg["Subject"] = f"{subject} [{random_tag()}]"

    # Add anti-loop sentinel
    del msg["X-Kayako-Dup"]
    msg["X-Kayako-Dup"] = "1"

    # Strip threading headers so Kayako doesn't link copies together
    del msg["In-Reply-To"]
    del msg["References"]

    return msg


def send_copy(msg, envelope_sender, destination):
    """Re-inject a message via sendmail."""
    cmd = ["/usr/sbin/sendmail", "-i", "-f", envelope_sender, destination]
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    stdout, stderr = proc.communicate(msg.as_bytes())
    if proc.returncode != 0:
        raise RuntimeError(
            f"sendmail failed for {destination} (exit {proc.returncode}): "
            f"{stderr.decode(errors='replace').strip()}"
        )


def main():
    if len(sys.argv) < 2:
        print(
            f"Usage: {sys.argv[0]} <addr1,addr2,...>",
            file=sys.stderr,
        )
        sys.exit(1)

    destinations = [a.strip() for a in sys.argv[1].split(",") if a.strip()]
    if not destinations:
        print("Error: no destination addresses provided.", file=sys.stderr)
        sys.exit(1)

    raw = sys.stdin.buffer.read()
    if not raw:
        print("Error: no email data on stdin.", file=sys.stderr)
        sys.exit(1)

    # Parse once just to extract the envelope sender
    original = email.message_from_bytes(raw)
    envelope_sender = email.utils.parseaddr(original.get("From", ""))[1]

    errors = []
    for dest in destinations:
        try:
            copy = make_copy(raw, dest)
            send_copy(copy, envelope_sender, dest)
        except Exception as exc:
            errors.append(f"{dest}: {exc}")

    if errors:
        for err in errors:
            print(f"Error: {err}", file=sys.stderr)
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
