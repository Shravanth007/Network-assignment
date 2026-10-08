# bserve — BHTTP/1 Server (Track 1)

A binary HTTP-like server. One TCP connection, one frame-based wire
protocol, static files off disk. Full protocol definition is in
[`spec.md`](spec.md); a byte-by-byte walkthrough of a real
request/response is in [`hexdump.md`](hexdump.md).

This repo is Track 1 only (the server). Track 2 (a client, `bcurl`) is
not part of this submission.

## Requirements

Python 3, standard library only. Nothing to install.

## Run it

```
python bserve <root> <port>
```

or, on a Unix-like shell where the executable bit and shebang resolve
(Linux, WSL, macOS):

```
./bserve <root> <port>
```

Example:

```
./bserve ./www 9000
```

Serves files out of `./www` on port 9000. `GET /` maps to
`./www/index.html`. The server keeps listening and keeps each client
connection open across multiple requests until the client disconnects.

## Files

| File             | What it is                                            |
|------------------|--------------------------------------------------------|
| `bserve`         | The server.                                           |
| `spec.md`        | The two-page protocol spec.                          |
| `hexdump.md`     | Annotated hexdump of a real request/response exchange. |
| `www/index.html` | Sample file served by the example above.              |
| `test_bserve.py` | Automated tests (see below).                          |

## Tests

```
python -m unittest test_bserve -v
```

Starts a real `bserve` subprocess against a throwaway temp directory
and a throwaway port (9091, so it won't collide with a `bserve` you
already have running on 9000), drives it over real sockets using the
same frame-encoding helpers `bserve` itself uses, and tears it down
afterward. Covers:

- a normal `200` fetch, including `content-type` / `content-length`
- `/` resolving to `index.html`, and a nested path under the root
- `404` for a missing file and for a path that tries to escape the root
  (`/../outside.txt`)
- `400` for a too-short frame, a bad method byte, and an invalid-UTF-8
  path — and that the connection stays open afterward
- an unknown frame type being skipped cleanly instead of breaking the
  connection
- many requests served back-to-back on one connection, and a second
  connection being accepted after the first one closes
