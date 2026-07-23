# Security policy

## Reporting a vulnerability

Do not open a public issue for a vulnerability or suspected credential leak.
Use GitHub's private vulnerability reporting for this repository. If that
option is unavailable, contact the maintainer through the private contact method
listed on their GitHub profile.

Include only the minimum reproduction details. Never include a Client ID,
Client Secret, access or refresh token, authorization code, complete OAuth
redirect URL, car ID, Home Assistant access token, or unredacted diagnostics.

## Supported versions

Security fixes are provided for the latest published release. Users should
update before reporting behavior already fixed on `main`.

## Credential handling

Credentials are stored in Home Assistant config entries. Access tokens are
kept in memory; rotated refresh tokens are persisted so later refreshes remain
valid. Diagnostics redact configured credentials, tokens, and vehicle IDs, but
reporters must inspect exported material before sharing it.

If a secret or OAuth redirect URL has been disclosed, revoke or rotate it in
the appropriate Hyundai/Kia developer console and reauthorize the integration.
