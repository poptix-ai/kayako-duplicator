# Kayako Email Duplicator / Multi-Queue Forwarder

Receives one inbound email and delivers a uniquely modified copy to each of N
destination addresses (Kayako queues), so that Kayako treats every copy as a
distinct new ticket instead of deduplicating them.

## How It Works

```
Inbound mail → Postfix → /etc/aliases pipe
                               ↓
                  procmail -m /etc/procmail/kayako.rc
                               ↓
                  kayako_duplicator.py addr1,addr2,...
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
TLS, queuing, and retry automatically. Postfix does **not** need procmail as
its global LDA — only the aliased address is piped through procmail.

## Requirements

- Python 3.6+
- Postfix (standard configuration)
- `/usr/sbin/sendmail` available (standard on Postfix systems)
- `procmail` installed (`apt install procmail` / `yum install procmail`)

## Installation

### 1. Copy the script

```bash
cp kayako_duplicator.py /usr/local/bin/kayako_duplicator.py
chmod +x /usr/local/bin/kayako_duplicator.py
```

### 2. Install the Procmail config

```bash
mkdir -p /etc/procmail
cp procmailrc.example /etc/procmail/kayako.rc
```

Edit the address list in `/etc/procmail/kayako.rc`:

```procmail
:0
| /usr/local/bin/kayako_duplicator.py support@kayako.com,billing@kayako.com
```

Replace `support@kayako.com,billing@kayako.com` with your actual Kayako queue
addresses. Use commas with no spaces between addresses.

### 3. Add the alias in `/etc/aliases`

```
kayako-inbound: "|/usr/bin/procmail -m /etc/procmail/kayako.rc"
```

Replace `kayako-inbound` with whatever local address should trigger the
forwarder (e.g. the address your inbound email pipe points at).

Then rebuild the alias database:

```bash
newaliases
```

### 4. Point your inbound email at the alias

Configure your MX or Postfix transport so that the relevant inbound address
(e.g. `tickets@company.com`) routes to the `kayako-inbound` alias. This is
typically done via a `virtual` or `transport` map entry, or by setting the
alias address as the delivery target in your DNS/mail routing.

## Verification

1. Send a test email to the aliased address.
2. Check each Kayako queue — one new ticket should appear per queue, each with
   a distinct subject tag (e.g. `[aB3x]`).
3. Repeat the send — fresh tickets should be created (no false deduplication).
4. Check `/var/log/mail.log` — you should see one sendmail call per address
   and no looping (re-injected copies must not re-trigger the recipe).
5. Temporarily block one destination — Postfix should queue it for retry while
   the others deliver normally.

## Running Tests

```bash
cd tests
python3 -m unittest test_duplicator -v
# or, if pytest is available:
python3 -m pytest test_duplicator.py -v
```

## Security Notes

- The script uses `subprocess.Popen` with a list argument (no `shell=True`),
  avoiding shell injection.
- The envelope sender is extracted from the `From` header via
  `email.utils.parseaddr`, which safely handles malformed addresses.
- No external dependencies; stdlib only.

## Troubleshooting

| Symptom | Check |
|---------|-------|
| Copies not arriving in Kayako | `/var/log/mail.log` for sendmail errors |
| Loop / infinite copies | Confirm `X-Kayako-Dup` recipe is first in `kayako.rc` |
| All copies land in one ticket | Kayako may be matching on `From`+`To`; verify subject tags differ |
| Script not found | Confirm `/usr/local/bin/kayako_duplicator.py` is executable |
| Alias not firing | Run `newaliases` after editing `/etc/aliases`; check Postfix logs |
