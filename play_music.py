import sys
import urllib.request
import urllib.parse
import re
import webbrowser

if len(sys.argv) < 2:
    print("Please provide a song name.")
    sys.exit(1)

song_name = " ".join(sys.argv[1:])
print(f"Searching for '{song_name}' on YouTube...")

try:
    query = urllib.parse.quote(song_name)
    url = f"https://www.youtube.com/results?search_query={query}"
    html = urllib.request.urlopen(url).read().decode()
    video_ids = re.findall(r"watch\?v=(\S{11})", html)
    if video_ids:
        final_url = f"https://www.youtube.com/watch?v={video_ids[0]}"
        print(f"Playing {final_url} ...")
        # Launch browser natively across any OS
        webbrowser.open(final_url)
    else:
        print("Could not find any video for that search.")
except Exception as e:
    print(f"Error playing music: {e}")
