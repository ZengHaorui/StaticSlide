```markdown
# Video Slides Player (Python / Flask)

Single-page app (Flask serving static files) that plays a local video as "slides" with quick-jump and looping behavior. Includes a visual editor to mark clips and export JSON.

Features
- Load local video, load / import JSON that describes clips.
- Space / Enter: fast-forward to next clip start at configured jump speed, then loop that clip.
- Left Arrow: rewind quickly to previous clip start at configured jump speed, then loop that clip.
- jump_speed may be configured in JSON globally or per clip.
- Visual timeline, markers, editor panel to create/edit/delete clips and markers.
- Export / Import JSON.
- No npm required.

Run
1. Create a virtual env (recommended) and install:
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt

2. Start server:
   python app.py

3. Open your browser at:
   http://127.0.0.1:5000

Packaging
- To create a zip of the project files, run:
  python create_zip.py

JSON format accepted/generated
- Two forms accepted:
  1) Array of clip objects:
     [
       { "number":1, "start":"00:00:00.000", "end":"00:00:04.500", "type":"loop", "description":"Intro", "animate_curve":"ease", "jump_speed":6 },
       ...
     ]
  2) Object with global jump speed:
     {
       "jump_speed": 6,
       "clips": [ { ... }, ... ]
     }

- Each clip's start/end can be a number (seconds) or timecode string "MM:SS.mmm" / "HH:MM:SS.mmm".
- If clip has "jump_speed", it overrides the global jump speed used when jumping into that clip.

Notes
- Browser restrictions: fast reverse playback is simulated by stepping backward; smoothness depends on browser.
- The app is fully client-side for video playback; Flask only serves the static files and local UI.
```