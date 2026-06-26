# TLS certificates

This folder must contain `selfsigned.crt` and `selfsigned.key` (or your real
certificate files, keeping these filenames or updating `nginx.conf` to match).

## Local development (self-signed)

```bash
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout selfsigned.key \
  -out selfsigned.crt \
  -subj "/CN=localhost"
```

Browsers and WhatsApp's webhook verification will show a certificate warning
for self-signed certs — that's expected for local development only.

## Production

Use a certificate from a trusted CA (e.g. Let's Encrypt via certbot). Meta's
WhatsApp Cloud API **requires** a valid, trusted TLS certificate on your
webhook URL — self-signed certificates will be rejected.

Example with certbot (standalone mode, stop nginx first):

```bash
certbot certonly --standalone -d yourdomain.com
cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem selfsigned.crt
cp /etc/letsencrypt/live/yourdomain.com/privkey.pem selfsigned.key
```

Remember to set up auto-renewal (`certbot renew`) and restart nginx after
each renewal.
