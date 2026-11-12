#!/usr/bin/env python3
"""Tiny PNG helpers with no dependencies (no PIL needed).

  png_tools.py info  <img.png>
  png_tools.py color <img.png> x0,y0,x1,y1 [...]     darkest pixel in each region (= text colour on light bg)
  png_tools.py crop  <img.png> <out.png> y0 y1        keep rows y0..y1 (full width)
  png_tools.py slice <img.png> <prefix> <step>        split a tall image into <prefix>_00.png, _01.png ... of <step> rows

Run with `python3 -I` when the image came from a download.
"""
import struct
import sys
import zlib


def load(path):
    data = open(path, 'rb').read()
    i, idat = 8, b''
    while i < len(data):
        length, = struct.unpack('>I', data[i:i + 4])
        kind, chunk = data[i + 4:i + 8], data[i + 8:i + 8 + length]
        i += 12 + length
        if kind == b'IHDR':
            w, h, depth, ctype = struct.unpack('>IIBB', chunk[:10])
            if depth != 8 or ctype not in (2, 6):
                raise SystemExit('only 8-bit RGB/RGBA PNGs supported')
        elif kind == b'IDAT':
            idat += chunk
    raw = zlib.decompress(idat)
    bpp = 3 if ctype == 2 else 4
    stride = w * bpp
    rows, prev, o = [], bytearray(stride), 0
    for _ in range(h):
        f = raw[o]; o += 1
        line = bytearray(raw[o:o + stride]); o += stride
        for x in range(stride):
            a = line[x - bpp] if x >= bpp else 0
            b = prev[x]
            c = prev[x - bpp] if x >= bpp else 0
            if f == 1: line[x] = (line[x] + a) & 255
            elif f == 2: line[x] = (line[x] + b) & 255
            elif f == 3: line[x] = (line[x] + (a + b) // 2) & 255
            elif f == 4:
                pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                line[x] = (line[x] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        rows.append(line); prev = line
    return w, h, bpp, rows


def save(path, w, bpp, rows):
    def chunk(kind, body):
        return struct.pack('>I', len(body)) + kind + body + struct.pack('>I', zlib.crc32(kind + body) & 0xffffffff)
    raw = b''.join(b'\x00' + bytes(r) for r in rows)
    ihdr = struct.pack('>IIBBBBB', w, len(rows), 8, 2 if bpp == 3 else 6, 0, 0, 0)
    open(path, 'wb').write(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', ihdr) + chunk(b'IDAT', zlib.compress(raw, 6)) + chunk(b'IEND', b''))


def main():
    cmd, path = sys.argv[1], sys.argv[2]
    w, h, bpp, rows = load(path)
    if cmd == 'info':
        print(f'{w}x{h}')
    elif cmd == 'color':
        for reg in sys.argv[3:]:
            x0, y0, x1, y1 = map(int, reg.split(','))
            best = min((sum(rows[y][x * bpp:x * bpp + 3]), tuple(rows[y][x * bpp:x * bpp + 3]))
                       for y in range(y0, min(y1, h)) for x in range(x0, min(x1, w)))
            print(reg, '#%02X%02X%02X' % best[1])
    elif cmd == 'crop':
        out, y0, y1 = sys.argv[3], int(sys.argv[4]), int(sys.argv[5])
        save(out, w, bpp, rows[y0:y1]); print(out)
    elif cmd == 'slice':
        prefix, step = sys.argv[3], int(sys.argv[4])
        for n, y in enumerate(range(0, h, step)):
            save(f'{prefix}_{n:02d}.png', w, bpp, rows[y:y + step]); print(f'{prefix}_{n:02d}.png')
    else:
        raise SystemExit(__doc__)


if __name__ == '__main__':
    main()
