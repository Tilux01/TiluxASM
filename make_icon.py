import urllib.request
svg_code = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" fill="#a855f7"><path d="M256 512A256 256 0 1 0 256 0a256 256 0 1 0 0 512zm0-352a96 96 0 1 1 0 192 96 96 0 1 1 0-192z"/></svg>'
with open("tilux-client/src/icon.svg", "w") as f:
    f.write(svg_code)
