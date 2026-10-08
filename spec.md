# BHTTP/1 — A Binary HTTP Protocol

## 1. Overview

BHTTP is a binary, request/response protocol carried over a single
persistent TCP connection. A client opens one TCP connection, sends a
sequence of `REQUEST` frames, and reads one `RESPONSE` frame back per
request. The connection stays open across multiple request/response
exchanges; the client is responsible for closing it when done. The server
never initiates a second connection to the same client and never
multiplexes requests — one request is answered before the next is read.

All integers are unsigned and big-endian ("network byte order"). All
strings are length-prefixed byte sequences, never NUL-terminated.

## 2. Frame Header

Every frame starts with a fixed 9-byte header, followed by `Length` bytes
of payload:

```
 0                   1                   2                   3
 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                 Length (24)                  |  Type (8)     |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|   Flags (8)   |R|            Stream ID (31)                  |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                        Payload (Length bytes) ...            |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
```

| Field     | Width | Meaning                                             |
|-----------|-------|------------------------------------------------------|
| Length    | 24    | Number of payload bytes following this header.       |
| Type      | 8     | Frame type (see §3).                                  |
| Flags     | 8     | Per-type bit flags. No type defines any flags yet.    |
| R         | 1     | Reserved, must be sent as 0, ignored on receipt.      |
| Stream ID | 31    | Always 0 in this version (see below).                 |

**Why 24 / 8 / 8 / 31?** A single file served by this project is always
well under 16 MiB, so 24 bits of length is generous without inviting a
client to declare a multi-gigabyte frame and force the server to
over-allocate — the width itself is the defense. One byte of frame type
is far more than the handful of types this protocol or a version 2 will
ever need, and keeping it byte-aligned keeps the parser a straight
offset read instead of a bitfield. The last word is split 1/31 rather
than given wholly to Stream ID: this version never multiplexes (the
client opens exactly one connection and keeps exactly one request in
flight), so the field is always 0 today, but reserving it now means a
future version that adds multiplexed streams changes nothing about the
header shape — only starts using a field that was already there. The one
bit taken from the 32-bit word (`R`) rather than folded into Stream ID is
reserved rather than spent, so a future version can use it as a cheap
per-frame signal bit without widening the header, and so an
implementation that stores Stream ID in a signed 32-bit integer never has
to worry about the sign bit.

## 3. Frame Types

| Type | Name     | Sent by | Meaning                      |
|------|----------|---------|-------------------------------|
| 0x01 | REQUEST  | client  | One HTTP-like request.       |
| 0x02 | RESPONSE | server  | One HTTP-like response.      |

**Unknown frame types.** A receiver that gets a frame whose `Type` it
does not implement for that role MUST skip it cleanly: read `Length`
bytes of payload, discard them, and continue reading frames on the
connection. It must never guess the payload's shape or close the
connection because of it. This is the only way a version 2 of this
protocol can introduce a new frame type without breaking a version-1
peer.

## 4. Header Field Encoding

Both `REQUEST` and `RESPONSE` payloads carry a small list of header
fields. Ten names are used often enough in this protocol to earn a
number in a shared static table; every other name is sent literally,
length-prefixed. This borrows HPACK's two cheapest tricks — a static
table of common names, and length-prefixed literals for everything else
— without HPACK's dynamic table or Huffman coding.

Static table:

| Index | Name            |
|-------|-----------------|
| 1     | `:path`         |
| 2     | `:status`       |
| 3     | `content-type`  |
| 4     | `content-length`|
| 5     | `host`          |
| 6     | `user-agent`    |
| 7     | `accept`        |
| 8     | `server`        |
| 9     | `connection`    |
| 10    | `date`          |

A single header field is encoded as:

```
+--------+--------------------------------+
| Index  | 1 byte                         |
+--------+--------------------------------+
| Name   | 2-byte length + bytes          |  (only if Index == 0)
+--------+--------------------------------+
| Value  | 2-byte length + bytes          |
+--------+--------------------------------+
```

If `Index` is 1–10, the name is looked up in the static table above and
no name bytes are sent. If `Index` is 0, a 2-byte length-prefixed name
immediately follows, then the 2-byte length-prefixed value always
follows. A header list is itself prefixed by a single byte giving the
number of fields (0–255) in the list.

## 5. REQUEST Payload (Type 0x01)

```
+---------------+
| Method (8)    |   0x00 = GET (only method defined)
+---------------+
| Path length (16) |
+-------------------+
| Path bytes (UTF-8, must start with '/') |
+------------------------------------------+
| Header count (8) |
+-------------------+
| Header fields ... |
+--------------------+
```

## 6. RESPONSE Payload (Type 0x02)

```
+-------------------+
| Status code (16)  |   e.g. 200, 400, 404
+-------------------+
| Header count (8)  |
+--------------------+
| Header fields ... |
+---------------------+
| Body (remaining bytes in the frame) |
+----------------------------------------+
```

The body is whatever bytes remain in the frame after the status, header
count and header fields — there is no separate body-length field,
because `Length` in the frame header already bounds it. The server
always sends `content-type` and `content-length` as response headers.

## 7. Server Behavior

1. Bind and listen on the given port; accept one TCP connection at a
   time.
2. On a connection, read frames in a loop until the client closes the
   socket:
   - Read the 9-byte frame header, then exactly `Length` bytes of
     payload. If the connection closes before either is complete, the
     connection is done — stop, close the socket, and go back to
     accepting.
   - If `Type` is not `REQUEST`, skip the payload (§3) and read the
     next frame.
   - Map the request path to a file under the server's root directory.
     `/` maps to `index.html`. A path that would resolve outside the
     root (e.g. via `..`) is treated as not found.
   - If the file does not exist, reply with a `RESPONSE` frame,
     status `404`.
   - If the `REQUEST` payload cannot be parsed (truncated fields, a
     path that doesn't start with `/`, an unknown header index, an
     unsupported method, etc.), reply with a `RESPONSE` frame, status
     `400`, and keep the connection open for the next frame — a
     malformed request is the client's mistake, not a reason to drop
     the connection.
   - Otherwise reply with a `RESPONSE` frame, status `200`, the file's
     bytes as the body, and `content-type` guessed from the file
     extension.
3. The connection is never closed by the server after a single
   request/response — only when the client closes it, or the TCP
   connection otherwise drops.

## 8. Status Codes Used

| Code | Meaning                                              |
|------|-------------------------------------------------------|
| 200  | File found and returned.                             |
| 400  | The `REQUEST` frame could not be parsed.             |
| 404  | The path does not map to a file under the root.      |

## 9. Edge Cases

- A name or value byte sequence that is not valid ASCII/UTF-8 makes the
  frame malformed (`400`), same as a bad length field.
- Request header fields are accepted but otherwise ignored by this
  version of the server — they exist so a client can send them without
  being rejected.
- An extension this server doesn't recognize gets `content-type:
  application/octet-stream`.
- If a `Length` a sender declared is never fully delivered (the
  connection stalls or drops mid-payload), the receiver is blocked on
  that read; it never guesses a shorter frame.
