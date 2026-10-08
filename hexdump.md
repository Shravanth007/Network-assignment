# Annotated Hexdump — One Complete Request/Response

Captured from a live `bserve ./www 9000`, request for `GET /index.html`.

## REQUEST frame (47 bytes on the wire)

```
0000  00 00 26 01 00 00 00 00 00 00 00 0b 2f 69 6e 64  ..&........./ind
0010  65 78 2e 68 74 6d 6c 02 05 00 0e 6c 6f 63 61 6c  ex.html....local
0020  68 6f 73 74 3a 39 30 30 30 07 00 03 2a 2f 2a     host:9000...*/*
```

| Bytes          | Hex                               | Field                     | Value                     |
|----------------|------------------------------------|---------------------------|----------------------------|
| 0x00–0x02      | `00 00 26`                          | Length                    | 0x26 = 38 payload bytes   |
| 0x03           | `01`                                | Type                      | 0x01 = REQUEST            |
| 0x04           | `00`                                | Flags                     | 0 (none defined)          |
| 0x05–0x08      | `00 00 00 00`                      | Reserved(1) + Stream ID   | Stream ID 0               |
| 0x09           | `00`                                | Method                    | 0x00 = GET                |
| 0x0a–0x0b      | `00 0b`                            | Path length                | 11                         |
| 0x0c–0x16      | `2f 69 6e 64 65 78 2e 68 74 6d 6c` | Path bytes                 | `/index.html`              |
| 0x17           | `02`                                | Header count                | 2                          |
| 0x18           | `05`                                | Header 1 — name index      | 5 = `host`                 |
| 0x19–0x1a      | `00 0e`                             | Header 1 — value length     | 14                         |
| 0x1b–0x28      | `6c 6f 63 61 6c 68 6f 73 74 3a 39 30 30 30` | Header 1 — value | `localhost:9000`           |
| 0x29           | `07`                                | Header 2 — name index       | 7 = `accept`                |
| 0x2a–0x2b      | `00 03`                             | Header 2 — value length      | 3                          |
| 0x2c–0x2e      | `2a 2f 2a`                          | Header 2 — value             | `*/*`                       |

9-byte header + 38-byte payload = 47 bytes total, matching the frame's own `Length` field.

## RESPONSE frame (168 bytes on the wire)

```
0000  00 00 9f 02 00 00 00 00 00 00 c8 02 03 00 09 74  ...............t
0010  65 78 74 2f 68 74 6d 6c 04 00 03 31 33 38 3c 21  ext/html...138<!
0020  64 6f 63 74 79 70 65 20 68 74 6d 6c 3e 0a 3c 68  doctype html>.<h
0030  74 6d 6c 3e 0a 3c 68 65 61 64 3e 3c 74 69 74 6c  tml>.<head><titl
0040  65 3e 62 73 65 72 76 65 3c 2f 74 69 74 6c 65 3e  e>bserve</title>
0050  3c 2f 68 65 61 64 3e 0a 3c 62 6f 64 79 3e 0a 3c  </head>.<body>.<
0060  68 31 3e 49 74 20 77 6f 72 6b 73 2e 3c 2f 68 31  h1>It works.</h1
0070  3e 0a 3c 70 3e 53 65 72 76 65 64 20 6f 76 65 72  >.<p>Served over
0080  20 42 48 54 54 50 2f 31 20 62 79 20 62 73 65 72   BHTTP/1 by bser
0090  76 65 2e 3c 2f 70 3e 0a 3c 2f 62 6f 64 79 3e 0a  ve.</p>.</body>.
00a0  3c 2f 68 74 6d 6c 3e 0a                          </html>.
```

| Bytes          | Hex                               | Field                      | Value                      |
|----------------|------------------------------------|------------------------------|------------------------------|
| 0x00–0x02      | `00 00 9f`                          | Length                       | 0x9f = 159 payload bytes    |
| 0x03           | `02`                                | Type                          | 0x02 = RESPONSE             |
| 0x04           | `00`                                | Flags                         | 0                            |
| 0x05–0x08      | `00 00 00 00`                      | Reserved(1) + Stream ID       | Stream ID 0                 |
| 0x09–0x0a      | `00 c8`                             | Status code                    | 200                          |
| 0x0b           | `02`                                | Header count                   | 2                            |
| 0x0c           | `03`                                | Header 1 — name index          | 3 = `content-type`           |
| 0x0d–0x0e      | `00 09`                             | Header 1 — value length         | 9                            |
| 0x0f–0x17      | `74 65 78 74 2f 68 74 6d 6c`        | Header 1 — value                | `text/html`                   |
| 0x18           | `04`                                | Header 2 — name index            | 4 = `content-length`          |
| 0x19–0x1a      | `00 03`                             | Header 2 — value length           | 3                             |
| 0x1b–0x1d      | `31 33 38`                          | Header 2 — value                   | `"138"`                        |
| 0x1e–0xa7      | *(138 bytes)*                      | Body                                | contents of `www/index.html` |

9-byte header + 159-byte payload = 168 bytes total; the body is 138 bytes,
exactly matching the `content-length: 138` header, and is the literal
contents of `www/index.html`.

## For comparison — the 404 and 400 cases

Request for `/nope.html` (file does not exist under root):

```
REQUEST  00 00 0e 01 00 00 00 00 00 00 00 0a 2f 6e 6f 70 65 2e 68 74 6d 6c 00
RESPONSE 00 00 1d 02 00 00 00 00 00 01 94 02 03 00 0a 74 65 78 74 2f 70 6c 61
         69 6e 04 00 01 39 4e 6f 74 20 46 6f 75 6e 64
```
Status field is `01 94` = 404, body is the ASCII text `Not Found`.

A deliberately malformed frame — `Type = REQUEST`, `Length = 3`, payload
`ff ff ff` (too short to even hold a path length, so parsing fails
immediately):

```
REQUEST  00 00 03 01 00 00 00 00 00 ff ff ff
RESPONSE 00 00 20 02 00 00 00 00 00 01 90 02 03 00 0a 74 65 78 74 2f 70 6c 61
         69 6e 04 00 02 31 31 42 61 64 20 52 65 71 75 65 73 74
```
Status field is `01 90` = 400, body is the ASCII text `Bad Request`. The
connection stayed open for all three requests above — it was never closed
by the server.

## Proof of the one line you may not skip

A frame with `Type = 0x7e`, a value this protocol never defines, followed
immediately by a normal, well-formed `GET /index.html` request on the
same connection:

```
UNKNOWN  00 00 05 7e 00 00 00 00 00 68 65 6c 6c 6f
REQUEST  00 00 0f 01 00 00 00 00 00 00 00 0b 2f 69 6e 64 65 78 2e 68 74 6d 6c 00
```

The `REQUEST` frame's payload (15 bytes) is: method `00`, path length
`00 0b` = 11, path `2f 69 6e 64 65 78 2e 68 74 6d 6c` = `/index.html`,
header count `00`.

The server read the unknown frame's `Length` (5), discarded exactly those
5 payload bytes (`68 65 6c 6c 6f` = `"hello"`) without inspecting them,
and went straight on to read and answer the next frame — a `200` for
`/index.html` on the very same connection (168-byte `RESPONSE` frame,
same as the main example above), with no error and no dropped
connection. This is the receiver-skips-unknown-types behavior the spec
requires in §3. Verified against the live server, not hand-assembled.
