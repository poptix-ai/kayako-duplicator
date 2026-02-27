# Kayako Email Duplicator / Multi-Queue Forwarder

Receives one inbound email and delivers a uniquely modified copy to each of N
destination addresses (Kayako queues), so that Kayako treats every copy as a
distinct new ticket instead of deduplicating them.

## How It Works

```
Inbound mail → Postfix → Procmail → kayako_duplicator.py addr1,addr2,...
                                            ↓
                        For each address: modify + re-inject via sendmail
                                            ↓
                   Postfix delivers each copy to its respective Kayako queue
```

Each copy gets:
- A fresh, unique `Message-ID`
- A unique 4-character random tag appended to the `Subject`
- An `X-Kayako-Dup: 1` header (anti-loop sentinel)
- `In-Reply-To` and `References` stripped (prevents Kayako threading copies)

Re-injection goes back through Postfix (not direct SMTP), so Postfix handles
TLS, queuing, and retry automatically.

## Requirements

- Python 3.6+
- Postfix with Procmail as the local delivery agent
- `/usr/sbin/sendmail` available (standard on Postfix systems)

## Installation

### 1. Copy the script

```bash
cp kayako_duplicator.py /usr/local/bin/kayako_duplicator.py
chmod +x /usr/local/bin/kayako_duplicator.py
```

### 2. Configure Procmail

Append the contents of `procmailrc.example` to your Procmail configuration:

```bash
# System-wide:
cat procmailrc.example >> /etc/procmailrc

# Or per-user:
cat procmailrc.example >> ~/.procmailrc
```

Then edit the address list in the recipe:

```procmail
:0
| /usr/local/bin/kayako_duplicator.py support@kayako.com,billing@kayako.com
```

Replace `support@kayako.com,billing@kayako.com` with your actual Kayako queue
addresses. Use commas with no spaces between addresses.

### 3. Ensure Procmail is the local delivery agent

In `/etc/postfix/main.cf`:

```
mailbox_command = /usr/bin/procmail
```

Or for a virtual user setup, configure accordingly.

## Verification

1. Send a test email to the address handled by this Procmail recipe.
2. Check each Kayako queue — one new ticket should appear per queue, each with
   a distinct subject tag (e.g. `[aB3x]`).
3. Repeat the send — fresh tickets should be created (no false deduplication).
4. Check `/var/log/mail.log` — you should see one sendmail call per address
   and no looping (re-injected copies should not re-trigger the recipe).
5. Temporarily block one destination — Postfix should queue it for retry while
   the others deliver normally.

## Running Tests

```bash
cd tests
python3 -m pytest test_duplicator.py -v
# or
python3 -m unittest test_duplicator -v
```

## Security Notes

- The script uses `subprocess.Popen` with a list argument (no shell=True),
  avoiding shell injection.
- The envelope sender is extracted from the `From` header via
  `email.utils.parseaddr`, which safely handles malformed addresses.
- No external dependencies; stdlib only.

## Troubleshooting

| Symptom | Check |
|---------|-------|
| Copies not arriving in Kayako | `/var/log/mail.log` for sendmail errors |
| Loop / infinite copies | Confirm `X-Kayako-Dup` recipe is first in procmailrc |
| All copies land in one ticket | Kayako may be matching on `From`+`To`; verify subject tags differ |
| Script not found | Confirm `/usr/local/bin/kayako_duplicator.py` is executable |
